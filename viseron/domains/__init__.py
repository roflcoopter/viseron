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
from viseron.helpers.config_validation import ConfigValidationError, validate_config
from viseron.helpers.named_timer import NamedTimer

SETUP_WITH_TRIES_PARAM_COUNT = 4

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.components import Component
    from viseron.viseron_types import SupportedDomains


LOGGER = logging.getLogger(__name__)

DOMAIN_REGISTRY_LOCK = threading.Lock()
# Serializes setup_domains runs, which retry timers also start
SETUP_DOMAINS_LOCK = threading.Lock()


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
    def __post_init__(self, *args, **kwargs) -> None:
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
    if not component_instance:
        raise ValueError(
            f"Component {component} not found for setting up domain {domain}"
        )
    component_instance.add_domain_to_setup(
        domain, config, identifier, require_domains, optional_domains
    )


def _wait_for_dependencies(
    vis: Viseron,
    entry: DomainEntry,
) -> bool | None:
    """Wait for all dependencies to complete setup.

    Returns True if all dependencies loaded, False if any failed and None if any
    is retrying, in which case setup is deferred until the dependency loads.
    """
    registry = vis.domain_registry

    def _slow_warning(futures: list[Future]) -> None:
        running = [f for f in futures if f.running()]
        if running:
            LOGGER.warning(
                f"Domain {entry.domain} with identifier {entry.identifier} "
                "still waiting for dependencies",
            )

    dependencies: list[RequireDomain] = [
        *entry.require_domains,
        *(
            optional
            for optional in entry.optional_domains
            if registry.is_configured(optional.domain, optional.identifier)
        ),
    ]

    futures: list[Future] = []
    states: list[DomainState | None] = []
    for dependency in dependencies:
        dependency_entry = registry.get(dependency.domain, dependency.identifier)
        if dependency_entry is None:
            states.append(None)
        elif dependency_entry.state == DomainState.LOADED:
            continue
        elif dependency_entry.setup_future:
            futures.append(dependency_entry.setup_future)
        elif dependency_entry.state == DomainState.FAILED and isinstance(
            dependency, OptionalDomain
        ):
            # An optional dependency that failed in an earlier setup is ignored
            continue
        else:
            states.append(dependency_entry.state)

    results: list[bool | None] = []
    if futures:
        LOGGER.debug(
            f"Domain {entry.domain} with identifier {entry.identifier} "
            f"waiting for {len(futures)} dependencies",
        )
        slow_warning_job = vis.background_scheduler.add_job(
            _slow_warning,
            "interval",
            seconds=SLOW_DEPENDENCY_WARNING,
            args=[futures],
        )
        results = [future.result() for future in as_completed(futures)]
        try:
            slow_warning_job.remove()
        except Exception:  # pylint: disable=broad-except # noqa: BLE001, S110
            pass

    if False in results or any(state in (None, DomainState.FAILED) for state in states):
        LOGGER.error(
            f"Unable to setup dependencies for domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name}"
        )
        return False
    if None in results or states:
        return None
    return True


def _setup_single_domain(
    vis: Viseron, entry: DomainEntry, tries: int = 1
) -> bool | None:
    """Set up a single domain.

    Returns True if loaded, False if failed and None if the domain is retrying in
    the background or deferred until a retrying dependency loads.
    """
    registry = vis.domain_registry
    component_path = entry.component_path

    LOGGER.info(
        f"Setting up domain {entry.domain} with identifier {entry.identifier} "
        f"for component {entry.component_name}"
        f"{', attempt ' + str(tries) if tries > 1 else ''}"
    )

    # Clear previous errors for this domain/identifier if any when retrying
    if entry.state == DomainState.RETRYING:
        component_instance = vis.data[LOADING].get(
            entry.component_name, vis.data[LOADED].get(entry.component_name)
        )
        if component_instance is not None:
            component_instance.clear_domain_identifier_errors(
                domain=entry.domain,
                identifier=entry.identifier,
            )

    if entry.state != DomainState.RETRYING:
        registry.set_state(entry.domain, entry.identifier, DomainState.LOADING)

    dependencies_ready = _wait_for_dependencies(vis, entry)
    if dependencies_ready is None:
        LOGGER.info(
            f"Deferring setup of domain {entry.domain} "
            f"with identifier {entry.identifier} "
            "until its retrying dependencies are loaded"
        )
        registry.set_state(entry.domain, entry.identifier, DomainState.PENDING)
        return None
    if not dependencies_ready:
        _handle_failed_domain(
            vis, entry, DomainState.FAILED, error="Dependencies failed"
        )
        return False

    # Load domain module
    try:
        domain_module = importlib.import_module(f"{component_path}.{entry.domain}")
    except ModuleNotFoundError as err:
        LOGGER.error(
            f"Failed to load domain module {component_path}.{entry.domain}: {err}"
        )
        _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(err))
        return False

    # Validate config
    config = entry.config
    if hasattr(domain_module, "CONFIG_SCHEMA"):
        try:
            config = validate_config(domain_module.CONFIG_SCHEMA, config)
        except ConfigValidationError as ex:
            error = (
                f"Error validating config for domain {entry.domain} and "
                f"component {entry.component_name}: {ex}"
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
            (
                f"Setup of domain {entry.domain} "
                f"with identifier {entry.identifier} "
                f"for component {entry.component_name} "
                f"is taking longer than {SLOW_SETUP_WARNING} seconds"
            ),
        ),
        name=f"{entry.domain}_{entry.identifier}_slow_setup_warning",
        daemon=True,
    )

    start = time.time()
    result: bool | Any = False
    try:
        slow_setup_warning.start()
        sig = signature(domain_module.setup)
        if len(sig.parameters) == SETUP_WITH_TRIES_PARAM_COUNT:
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
            f"{'shutdown' if vis.shutdown_event.is_set() else 'cancellation'}"
        )
        if vis.shutdown_event.is_set() or entry.cancel_event.is_set():
            LOGGER.warning(warning_text)
            _handle_failed_domain(vis, entry, DomainState.FAILED, error=str(error))
            slow_setup_warning.cancel()
            return False

        _handle_failed_domain(vis, entry, DomainState.RETRYING, error=str(error))
        slow_setup_warning.cancel()

        wait_time = _schedule_domain_retry(vis, entry, tries)
        LOGGER.error(
            f"Domain {entry.domain} "
            f"with identifier {entry.identifier} "
            f"for component {entry.component_name} is not ready. "
            f"Retrying in {wait_time} seconds. "
            f"Error: {error!s}"
        )
        return None
    except Exception as error:  # pylint: disable=broad-except
        LOGGER.exception(
            f"Uncaught exception setting up domain {entry.domain} for"
            f" component {entry.component_name}"
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

    with DOMAIN_REGISTRY_LOCK:
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

    with DOMAIN_REGISTRY_LOCK:
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


def _schedule_domain_retry(vis: Viseron, entry: DomainEntry, tries: int) -> int:
    """Retry setup of a domain in the background after a backoff.

    Returns the backoff in seconds. While retries are paused nothing is scheduled,
    and resume_domain_retries picks the domain up instead.
    """
    wait_time = min(tries * DOMAIN_RETRY_INTERVAL, DOMAIN_RETRY_INTERVAL_MAX)
    retry_timer = NamedTimer(
        wait_time,
        _retry_domain_setup,
        args=(vis, entry, tries + 1),
        name=f"{entry.domain}_{entry.identifier}_retry_timer",
        daemon=True,
    )
    vis.domain_registry.start_retry_timer(entry, retry_timer)
    return wait_time


def _retry_domain_setup(vis: Viseron, entry: DomainEntry, tries: int) -> None:
    """Retry setup of a domain, then resolve the dependents deferred on it."""
    result = _setup_single_domain(vis, entry, tries)
    if result is not None and not vis.shutdown_event.is_set():
        setup_domains(vis)


def pause_domain_retries(vis: Viseron) -> None:
    """Stop scheduled domain retries and wait for running attempts to finish."""
    for retry_timer in vis.domain_registry.pause_retries():
        retry_timer.join()


def resume_domain_retries(vis: Viseron) -> None:
    """Reschedule retries for domains still retrying after a pause."""
    for entry in vis.domain_registry.resume_retries():
        wait_time = _schedule_domain_retry(vis, entry, tries=1)
        LOGGER.debug(
            f"Resuming retries for domain {entry.domain} "
            f"with identifier {entry.identifier} in {wait_time} seconds"
        )


def setup_domains(vis: Viseron) -> None:
    """Set up all pending domains.

    Domains that are not ready retry on a timer, and their dependents stay pending
    until they load, so this never blocks on a retrying domain.
    """
    registry = vis.domain_registry

    with SETUP_DOMAINS_LOCK:
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

        with ThreadPoolExecutor(
            max_workers=100, thread_name_prefix="setup_domains"
        ) as executor:
            for entry in pending:
                _schedule_domain_setup(vis, executor, entry)

            futures = [
                future
                for entry in pending
                if (future := registry.get_future(entry.domain, entry.identifier))
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:  # pylint: disable=broad-except
                    LOGGER.exception("Domain setup raised exception")

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
    except Exception:  # pylint: disable=broad-except # noqa: BLE001
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

    # Propagate domain error to the owning Component instance
    if error:
        component_instance = vis.data[LOADING].get(
            entry.component_name, vis.data[LOADED].get(entry.component_name)
        )
        if component_instance is not None:
            component_instance.add_domain_error(
                error,
                domain=entry.domain,
                identifier=entry.identifier,
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


def unload_domain_identifier(
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

    # Cancel any in-progress retry for this domain
    registry.cancel_retry(domain, identifier)

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
        except Exception as ex:  # pylint: disable=broad-except # noqa: BLE001
            LOGGER.error(
                f"Error unloading domain {domain} with identifier {identifier}: {ex}"
            )
    else:
        LOGGER.debug(
            f"Domain {domain} with identifier {identifier} has no unload method"
        )

    # Unregister from registry
    return registry.unregister(domain, identifier)


def unload_domain_chain(
    vis: Viseron, domain: SupportedDomains, identifier: str
) -> set[str]:
    """Unload a domain and all its dependents in the correct order.

    Returns the component names of dependents that need re-setup.
    The root domain's own component is intentionally excluded.
    """
    unload_order = get_unload_order(vis, domain, identifier)
    affected_components = set()
    for entry in unload_order:
        # Only dependents need to be re-setup, not the root being unloaded.
        if entry.domain != domain or entry.identifier != identifier:
            affected_components.add(entry.component_name)
        unload_domain_identifier(vis, entry.domain, entry.identifier)
    return affected_components


def unload_domain(
    vis: Viseron, component: str, domain: SupportedDomains
) -> set[str] | None:
    """Unload a component's domain and all its identifiers."""
    component_instance: Component | None = vis.data[LOADED].get(component, None)
    if component_instance is None:
        LOGGER.debug(f"Component {component} not found, can't unload domain {domain}")
        return None

    affected_components = set()
    registry = vis.domain_registry

    # Unload any domain identifiers for this component and domain
    domains_to_unload = registry.get_by_component_and_domain(component, domain)
    LOGGER.debug(
        f"Unloading all identifiers for component {component} and domain {domain}"
    )
    if domains_to_unload:
        LOGGER.debug(
            f"Component {component} "
            f"and domain {domain} "
            f"has {len(domains_to_unload)} identifiers to unload: "
            f"{[(e.domain, e.identifier) for e in domains_to_unload]}"
        )

        for entry in domains_to_unload:
            affected_components.update(
                unload_domain_chain(vis, entry.domain, entry.identifier)
            )

    # Call domain's unload method if it exists
    try:
        domain_module = importlib.import_module(f"{component_instance.path}.{domain}")
    except ModuleNotFoundError as err:
        LOGGER.error(
            f"Failed to load domain module {component_instance.path}.{domain}: {err}"
        )
        return affected_components
    if hasattr(domain_module, "unload"):
        try:
            domain_module.unload(vis)
        except Exception as ex:  # pylint: disable=broad-except # noqa: BLE001
            LOGGER.error(
                f"Error unloading domain {domain} for component {component}: {ex}"
            )
    else:
        LOGGER.debug(f"Domain {domain} for component {component} has no unload method")

    return affected_components
