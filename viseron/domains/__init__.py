"""Viseron domains."""
from __future__ import annotations

import importlib
import logging
import threading
import time
from abc import ABCMeta, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from inspect import signature
from typing import TYPE_CHECKING, Any, Literal

import voluptuous as vol
from voluptuous.humanize import humanize_error

from viseron.const import (
    DOMAIN_RETRY_INTERVAL,
    DOMAIN_RETRY_INTERVAL_MAX,
    LOADED,
    LOADING,
    SLOW_DEPENDENCY_WARNING,
    SLOW_SETUP_WARNING,
)
from viseron.domain_registry import DomainEntry, DomainState
from viseron.exceptions import DomainNotReady
from viseron.helpers.named_timer import NamedTimer

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.types import SupportedDomains


LOGGER = logging.getLogger(__name__)

DOMAIN_SETUP_LOCK = threading.Lock()


@dataclass
class RequireDomain:
    """Mark domain with given identifier as a required dependency.

    Viseron will make sure that all required domains are resolved before setting up
    the domain.
    """

    domain: SupportedDomains
    identifier: str


class OptionalDomain(RequireDomain):
    """Mark domain with given identifier as a optional dependency.

    If the optional domain is marked for setup, it will be awaited before setting up
    the domain.
    If the optional domain is NOT marked for setup, Viseron will ignore the dependency.
    """


class DomainMeta(ABCMeta):
    """Metaclass for domains.

    This metaclass will call __post_init__ after __init__ in order to register
    domains without explicitly doing so in __init__.
    """

    def __call__(cls, *args, **kwargs):
        """Call __post_init__ after __init__."""
        instance = super().__call__(*args, **kwargs)
        if hasattr(instance, "__post_init__"):
            instance.__post_init__(*args, **kwargs)
            return instance
        raise NotImplementedError(f"Class {cls} must implement __post_init__")


class AbstractDomain(metaclass=DomainMeta):
    """Abstract domain class."""

    @abstractmethod
    def __post_init__(self, *args, **kwargs):
        """Post init, called automatically after __init__."""


def setup_domain(
    vis: Viseron,
    component: str,
    domain: SupportedDomains,
    config: dict[str, Any],
    identifier: str,
    require_domains: list[RequireDomain] | None = None,
    optional_domains: list[OptionalDomain] | None = None,
) -> None:
    """Set up single domain."""
    component_instance = vis.data[LOADING].get(
        component, vis.data[LOADED].get(component, None)
    )
    component_instance.add_domain_to_setup(
        domain, config, identifier, require_domains, optional_domains
    )


def _wait_for_dependencies(
    vis: Viseron,
    entry: DomainEntry,
) -> bool:
    """Wait for all dependencies to complete setup."""
    registry = vis.domain_registry

    def _slow_warning(futures: list[Future]) -> None:
        running = [f for f in futures if f.running()]
        if running:
            LOGGER.warning(
                f"Domain {entry.domain} with identifier {entry.identifier} "
                "still waiting for dependencies",
            )

    # Collect futures for required domains
    futures: list[Future] = []
    for required in entry.require_domains:
        # Skip if already loaded
        if registry.is_loaded(required.domain, required.identifier):
            continue
        future = registry.get_future(required.domain, required.identifier)
        if future:
            futures.append(future)

    # Collect futures for optional domains
    for optional in entry.optional_domains:
        if not registry.is_configured(optional.domain, optional.identifier):
            continue
        if registry.is_loaded(optional.domain, optional.identifier):
            continue
        future = registry.get_future(optional.domain, optional.identifier)
        if future:
            futures.append(future)

    if not futures:
        return True

    LOGGER.debug(
        f"Domain {entry.domain} with identifier {entry.identifier} "
        f"waiting for {len(futures)} dependencies",
    )

    # Set up slow warning
    slow_warning_job = vis.background_scheduler.add_job(
        _slow_warning,
        "interval",
        seconds=SLOW_DEPENDENCY_WARNING,
        args=[futures],
    )

    # Wait for all dependencies
    failed = []
    for future in as_completed(futures):
        if future.result() is not True:
            failed.append(future)

    try:
        slow_warning_job.remove()
    except Exception:  # pylint: disable=broad-except
        pass

    if failed:
        LOGGER.error(
            f"Unable to setup dependencies for domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name}"
        )
        return False
    return True


def _setup_single_domain(vis: Viseron, entry: DomainEntry, tries: int = 1) -> bool:
    """Set up a single domain."""
    registry = vis.domain_registry
    component_path = entry.component_path

    LOGGER.info(
        (
            f"Setting up domain {entry.domain} with identifier {entry.identifier} "
            f"for component {entry.component_name}"
        )
        + (f", attempt {tries}" if tries > 1 else "")
    )

    registry.set_state(entry.domain, entry.identifier, DomainState.LOADING)

    # Wait for dependencies
    if not _wait_for_dependencies(vis, entry):
        _handle_failed_domain(
            vis, entry, DomainState.FAILED, error="Dependencies failed"
        )
        return False

    # Load domain module
    try:
        domain_module = importlib.import_module(f"{component_path}.{entry.domain}")
    except ModuleNotFoundError as err:
        LOGGER.error(
            "Failed to load domain module " f"{component_path}.{entry.domain}: {err}"
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(err))
        return False

    # Validate config
    config = entry.config
    if hasattr(domain_module, "CONFIG_SCHEMA"):
        try:
            config = domain_module.CONFIG_SCHEMA(config)
        except vol.Invalid as ex:
            error = (
                f"Error validating config for domain {entry.domain} and "
                f"component {entry.component_name}: "
                f"{humanize_error(config, ex)}"
            )
            LOGGER.exception(error)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=error)
            return False
        except Exception:  # pylint: disable=broad-except
            error = (
                "Unknown error calling "
                f"{entry.component_name}.{entry.domain} CONFIG_SCHEMA"
            )
            LOGGER.exception(error)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=error)
            return False

    # Set up slow setup warning
    slow_setup_warning = NamedTimer(
        SLOW_SETUP_WARNING,
        LOGGER.warning,
        args=(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} "
            f"is taking longer than {SLOW_SETUP_WARNING} seconds",
        ),
        name=f"{entry.domain}_{entry.identifier}_slow_setup_warning",
        daemon=True,
    )

    start = time.time()
    result: bool | Any = False
    try:
        slow_setup_warning.start()
        sig = signature(domain_module.setup)
        if len(sig.parameters) == 4:
            # If the setup function has an attempt parameter, we pass it
            result = domain_module.setup(vis, config, entry.identifier, tries)
        else:
            result = domain_module.setup(vis, config, entry.identifier)
    except DomainNotReady as error:
        warning_text = (
            f"Setup retry for domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} "
            "aborted due to "
            f"{'shutdown' if vis.shutdown_event.is_set() else 'reload'}"
        )
        if vis.shutdown_event.is_set() or vis.reloading_event.is_set():
            LOGGER.warning(warning_text)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(error))
            slow_setup_warning.cancel()
            return False

        _handle_failed_domain(vis, entry, DomainState.RETRYING, error=str(error))
        slow_setup_warning.cancel()

        wait_time = min(tries * DOMAIN_RETRY_INTERVAL, DOMAIN_RETRY_INTERVAL_MAX)
        LOGGER.error(
            f"Domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} is not ready. "
            f"Retrying in {wait_time} seconds. "
            f"Error: {str(error)}"
        )

        elapsed = 0.0
        interval = 0.2
        while elapsed < wait_time:
            if vis.shutdown_event.is_set() or vis.reloading_event.is_set():
                LOGGER.warning(warning_text)
                _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(error))
                return False
            time.sleep(interval)
            elapsed += interval
        # Running with ThreadPoolExecutor and awaiting the future does not
        # cause a max recursion error if we retry for a long time
        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="Component.setup_domain"
        ) as executor:
            future = executor.submit(_setup_single_domain, vis, entry, tries + 1)
            return future.result()
    except Exception as error:  # pylint: disable=broad-except
        LOGGER.exception(
            f"Uncaught exception setting up domain {entry.domain} for"
            f" component {entry.component_name}: {error}"
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(error))
        return False
    finally:
        slow_setup_warning.cancel()

    end = time.time()

    if result is True:
        LOGGER.info(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} "
            f"took {end - start:.1f} seconds"
        )
        registry.set_state(entry.domain, entry.identifier, DomainState.LOADED)
        return True

    if result is False:
        LOGGER.error(
            f"Setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} failed"
        )
        _handle_failed_domain(
            vis, entry, DomainState.FAILED, error="Setup returned False"
        )
        return False

    LOGGER.error(
        f"Setup of domain {entry.domain} "
        f"with identifier {entry.identifier} "
        f"for component {entry.component_name} did not return boolean"
    )
    _handle_failed_domain(
        vis, entry, DomainState.FAILED, error="Setup did not return boolean"
    )
    return False


def _submit_domain_setup(
    vis: Viseron,
    executor: ThreadPoolExecutor,
    entry: DomainEntry,
) -> None:
    """Submit a domain for setup in the executor."""
    registry = vis.domain_registry

    with DOMAIN_SETUP_LOCK:
        # Skip if already has a future
        if registry.get_future(entry.domain, entry.identifier):
            return

        future = executor.submit(_setup_single_domain, vis, entry)
        registry.set_future(entry.domain, entry.identifier, future)


def _schedule_domain_setup(
    vis: Viseron,
    executor: ThreadPoolExecutor,
    entry: DomainEntry,
) -> None:
    """Schedule a domain and its dependencies for setup."""
    registry = vis.domain_registry

    with DOMAIN_SETUP_LOCK:
        if registry.get_future(entry.domain, entry.identifier):
            return

    # Schedule required dependencies first
    for req in entry.require_domains:
        req_entry = registry.get(req.domain, req.identifier)
        if req_entry and req_entry.state == DomainState.PENDING:
            _schedule_domain_setup(vis, executor, req_entry)

    # Schedule optional dependencies
    for opt in entry.optional_domains:
        opt_entry = registry.get(opt.domain, opt.identifier)
        if opt_entry and opt_entry.state == DomainState.PENDING:
            _schedule_domain_setup(vis, executor, opt_entry)

    _submit_domain_setup(vis, executor, entry)


def setup_domains(vis: Viseron) -> None:
    """Set up all pending domains."""
    registry = vis.domain_registry

    entries_missing_deps = registry.validate_dependencies()
    for entry in entries_missing_deps:
        LOGGER.error(
            f"Domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"has missing dependencies: {entry.error}",
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=entry.error)

    pending = registry.get_pending()
    if not pending:
        return

    LOGGER.debug(f"Setting up {len(pending)} pending domains")

    with ThreadPoolExecutor(max_workers=100, thread_name_prefix="setup_domains") as ex:
        # Schedule all pending domains
        for entry in pending:
            _schedule_domain_setup(vis, ex, entry)

        # Wait for all to complete
        futures = [
            registry.get_future(e.domain, e.identifier)
            for e in pending
            if registry.get_future(e.domain, e.identifier)
        ]
        for future in as_completed(futures):  # type: ignore[arg-type]
            try:
                future.result()
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Domain setup raised exception")

    # Clear futures and handle failed domains
    for entry in pending:
        registry.clear_future(entry.domain, entry.identifier)


def _handle_failed_domain(
    vis: Viseron,
    entry: DomainEntry,
    state: Literal[DomainState.FAILED, DomainState.RETRYING],
    error: str | None = None,
) -> None:
    """Handle a failed domain setup."""
    error_instance = None
    try:
        domain_module = importlib.import_module(f"viseron.domains.{entry.domain}")
        if hasattr(domain_module, "setup_failed"):
            error_instance = domain_module.setup_failed(vis, entry)
    except Exception:  # pylint: disable=broad-except
        LOGGER.debug(
            f"No setup_failed handler for domain {entry.domain} "
            f"for component {entry.component_name}"
        )
    vis.domain_registry.set_state(
        entry.domain,
        entry.identifier,
        state,
        error_instance=error_instance,
        error=error,
    )


def get_unload_order(
    vis: Viseron, domain: SupportedDomains, identifier: str
) -> list[DomainEntry]:
    """Get domains in unload order (dependents first)."""
    registry = vis.domain_registry
    unload_order: list[DomainEntry] = []
    processed: set[tuple[SupportedDomains, str]] = set()

    def traverse(_domain: SupportedDomains, _identifier: str) -> None:
        key = (_domain, _identifier)
        if key in processed:
            return
        processed.add(key)

        # Process dependents first
        for dep in registry.get_dependents(_domain, _identifier):
            traverse(dep.domain, dep.identifier)

        # Then add this domain
        entry = registry.get(_domain, _identifier)
        if entry:
            unload_order.append(entry)

    traverse(domain, identifier)
    return unload_order


def unload_domain(
    vis: Viseron,
    domain: SupportedDomains,
    identifier: str,
) -> DomainEntry | None:
    """Unload a single domain."""
    registry = vis.domain_registry
    entry = registry.get(domain, identifier)

    if not entry:
        LOGGER.error(
            f"Domain {domain} with identifier {identifier} not found, cannot unload"
        )
        return None

    LOGGER.info(f"Unloading domain {domain} with identifier {identifier}")

    # Unload entities for this domain
    component_name = entry.component_name
    entities_to_remove: list[str] = []
    entity_owner = vis.states.entity_owner.get(component_name)
    domains = entity_owner.get("domains") if entity_owner else None
    domain_info = domains.get(domain) if domains else None
    identifiers = domain_info.get("identifiers") if domain_info else None
    entities_to_remove = identifiers.get(identifier, []) if identifiers else []

    # Need to use copy since unload_entity mutates the array
    for entity_id in entities_to_remove.copy():
        vis.states.unload_entity(entity_id)

    # Call domain's unload method
    if entry.instance and hasattr(entry.instance, "unload"):
        try:
            entry.instance.unload()
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error unloading domain {domain} with identifier {identifier}: {ex}"
            )
    else:
        LOGGER.debug(
            f"Domain {domain} with identifier {identifier} has no unload method"
        )

    # Unregister from registry
    return registry.unregister(domain, identifier)


def reload_domain(vis: Viseron, domain: SupportedDomains, identifier: str) -> None:
    """Reload a domain and all its dependents.

    Reloading is done by unloading all dependent domains first, then
    re-registering and setting them up again in the correct order.
    """
    reload_order = get_unload_order(vis, domain, identifier)

    if not reload_order:
        LOGGER.warning(
            f"Domain {domain} with identifier {identifier} not found for reload"
        )
        return

    LOGGER.info(
        f"Reloading domain {domain} with identifier {identifier}. "
        f"Order: {[(e.domain, e.identifier) for e in reload_order]}",
    )

    # Unload in order (dependents first)
    for entry in reload_order:
        unload_domain(vis, entry.domain, entry.identifier)

    # Re-register in original order
    registry = vis.domain_registry
    for entry in reversed(reload_order):
        registry.register(
            component_name=entry.component_name,
            component_path=entry.component_path,
            domain=entry.domain,
            identifier=entry.identifier,
            config=entry.config,
            require_domains=entry.require_domains,
            optional_domains=entry.optional_domains,
        )

    # Setup all
    setup_domains(vis)
