"""Configuration reload functionality for Viseron."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from viseron.components import (
    get_component,
    setup_components,
    unload_component,
)
from viseron.config import (
    ComponentChange,
    ConfigDiff,
    DomainChange,
    IdentifierChange,
    diff_config,
    diff_domain_config,
    diff_identifier_config,
    load_config,
)
from viseron.const import DEFAULT_COMPONENTS
from viseron.domain_registry import DomainState
from viseron.domains import get_unload_order, setup_domains, unload_domain

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domain_registry import DomainEntry
    from viseron.viseron_types import SupportedDomains

LOGGER = logging.getLogger(__name__)


@dataclass
class ReloadResult:
    """Result of a config reload operation."""

    success: bool
    diff: ConfigDiff | None = None
    restart_required: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class ReloadChanges:
    """Changes detected during config reload."""

    components_to_reload: list[ComponentChange] = field(default_factory=list)
    domains_to_reload: list[DomainChange] = field(default_factory=list)
    identifiers_to_reload: list[IdentifierChange] = field(default_factory=list)


@dataclass
class SetupPlan:
    """Tracks which components need setup during reload."""

    components: set[str] = field(default_factory=set)
    domain_components: set[str] = field(default_factory=set)


def _unload_domain_chain(
    vis: Viseron, domain: SupportedDomains, identifier: str, plan: SetupPlan
) -> None:
    """Unload a domain and all its dependents in the correct order."""
    unload_order = get_unload_order(vis, domain, identifier)
    for e in unload_order:
        plan.domain_components.add(e.component_name)
        unload_domain(vis, e.domain, e.identifier)


def _process_identifier_changes(
    component: str,
    domain: SupportedDomains,
    old_identifier_config: dict,
    new_identifier_config: dict,
) -> list[IdentifierChange]:
    """Process identifier-level changes for a domain."""
    identifier_changes = diff_identifier_config(
        component,
        domain,
        old_identifier_config,
        new_identifier_config,
    )
    return [
        change for change in identifier_changes if change.is_identifier_level_change
    ]


def _process_domain_changes(
    component: str,
    component_change: ComponentChange,
) -> tuple[list[DomainChange], list[IdentifierChange]]:
    """Process domain-level changes for a component."""
    domains_to_reload: list[DomainChange] = []
    identifiers_to_reload: list[IdentifierChange] = []

    old_domain_config, new_domain_config = component_change.get_domain_configs()
    component_change.domain_changes = diff_domain_config(
        component, old_domain_config, new_domain_config
    )

    for domain_change in component_change.domain_changes:
        if domain_change.is_domain_level_change:
            domains_to_reload.append(domain_change)
            continue

        # Process identifier-level changes
        (
            old_identifier_config,
            new_identifier_config,
        ) = domain_change.get_identifier_configs()
        domain_change.identifier_changes = _process_identifier_changes(
            component,
            domain_change.domain,
            old_identifier_config,
            new_identifier_config,
        )
        identifiers_to_reload.extend(domain_change.identifier_changes)

    return domains_to_reload, identifiers_to_reload


def _get_changes(diff: ConfigDiff) -> ReloadChanges:
    """Get changes to config.yaml."""
    components_to_reload: list[ComponentChange] = []
    domains_to_reload: list[DomainChange] = []
    identifiers_to_reload: list[IdentifierChange] = []

    for component in diff.get_modified_components():
        component_change = diff.get_component_change(component)
        if component_change is None:
            continue

        # Component-level change means we reload the whole component
        if component_change.is_component_level_change:
            components_to_reload.append(component_change)
            continue

        # Process domain and identifier level changes
        domain_changes, identifier_changes = _process_domain_changes(
            component, component_change
        )
        domains_to_reload.extend(domain_changes)
        identifiers_to_reload.extend(identifier_changes)

    return ReloadChanges(
        components_to_reload=components_to_reload,
        domains_to_reload=domains_to_reload,
        identifiers_to_reload=identifiers_to_reload,
    )


def _load_and_diff_config(
    vis: Viseron,
) -> tuple[dict, ConfigDiff, ReloadChanges]:
    """Load new config and compute diff against current config.

    Returns a tuple of (new_config, diff, changes) on success, or None on failure.
    """
    new_config = load_config()
    old_config = vis.config

    diff = diff_config(old_config, new_config)

    LOGGER.debug(
        f"Configuration changes detected: "
        f"{len(diff.get_added_components())} added, "
        f"{len(diff.get_removed_components())} removed, "
        f"{len(diff.get_modified_components())} modified components"
    )

    changes = _get_changes(diff)
    LOGGER.debug(f"Components to add: {diff.get_added_components()}")
    LOGGER.debug(f"Components to remove: {diff.get_removed_components()}")
    LOGGER.debug(f"Components to reload: {changes.components_to_reload}")
    LOGGER.debug(f"Domains to reload: {changes.domains_to_reload}")
    LOGGER.debug(f"Identifiers to reload: {changes.identifiers_to_reload}")

    return new_config, diff, changes


def _check_default_component_changes(diff: ConfigDiff) -> set[str]:
    """Check for changes to DEFAULT_COMPONENTS and return them."""
    component_changes = (
        diff.get_added_components()
        + diff.get_removed_components()
        + diff.get_modified_components()
    )
    return set(component_changes) & set(DEFAULT_COMPONENTS)


def _handle_removed_components(vis: Viseron, diff: ConfigDiff, plan: SetupPlan) -> None:
    """Unload removed components and track affected components for reloading domains."""
    for component_name in diff.get_removed_components():
        affected_components = unload_component(vis, component_name)
        if affected_components:
            plan.domain_components.update(affected_components)
            LOGGER.debug(
                f"Components affected by unloading {component_name}: "
                f"{affected_components}"
            )


def _handle_added_components(diff: ConfigDiff, plan: SetupPlan) -> None:
    """Mark added components for setup."""
    for component_name in diff.get_added_components():
        plan.components.add(component_name)


def _handle_modified_components(
    vis: Viseron, changes: ReloadChanges, plan: SetupPlan
) -> None:
    """Unload modified components and mark them for re-setup.

    Also tracks domains to reload for affected components.
    """
    for component_change in changes.components_to_reload:
        plan.components.add(component_change.component_name)
        affected_components = unload_component(vis, component_change.component_name)
        if affected_components:
            plan.domain_components.update(affected_components)


def _handle_modified_domains(
    vis: Viseron, changes: ReloadChanges, plan: SetupPlan
) -> None:
    """Unload all identifiers for modified domains."""
    for domain_change in changes.domains_to_reload:
        plan.domain_components.add(domain_change.component_name)
        domains_to_unload = vis.domain_registry.get_by_component(
            domain_change.component_name
        )
        if domains_to_unload:
            LOGGER.debug(
                f"Component {domain_change.component_name} "
                f"has {len(domains_to_unload)} domains to unload: "
                f"{[(e.domain, e.identifier) for e in domains_to_unload]}"
            )

            for entry in domains_to_unload:
                _unload_domain_chain(vis, entry.domain, entry.identifier, plan)


def _handle_modified_identifiers(
    vis: Viseron, changes: ReloadChanges, plan: SetupPlan
) -> None:
    """Unload specific identifiers that changed."""
    for identifier_change in changes.identifiers_to_reload:
        plan.domain_components.add(identifier_change.component_name)
        domain_to_unload = vis.domain_registry.get_by_identifier(
            identifier_change.domain, identifier_change.identifier
        )
        if domain_to_unload:
            _unload_domain_chain(
                vis,
                domain_to_unload.domain,
                domain_to_unload.identifier,
                plan,
            )

        if identifier_change.is_added:
            # When an identifier is added (or re-added after being removed),
            # find any dependents of this identifier
            # and unload them so they can be re-setup.
            _unload_domain_chain(
                vis,
                identifier_change.domain,
                identifier_change.identifier,
                plan,
            )


def _handle_cancelled_retries(
    vis: Viseron, cancelled_retries: list[DomainEntry], plan: SetupPlan
) -> None:
    """Unload domain retries that were cancelled before reload."""
    for entry in cancelled_retries:
        LOGGER.debug(
            f"Unloading retrying domain {entry.domain} with identifier "
            f"{entry.identifier} that was cancelled during reload"
        )
        _unload_domain_chain(vis, entry.domain, entry.identifier, plan)


def _unload_dependents_of_pending_domains(vis: Viseron, plan: SetupPlan) -> None:
    """Unload dependents of newly pending domains.

    When new domains become available (e.g., adding a component which provides
    object_detector), existing LOADED domains that have these new domains
    as optional dependencies need to be unloaded and re-setup to incorporate
    the new dependency.
    """
    pending = vis.domain_registry.get_pending()
    for entry in pending:
        dependents = vis.domain_registry.get_dependents(entry.domain, entry.identifier)
        loaded_dependents = [
            dep for dep in dependents if dep.state != DomainState.PENDING
        ]
        for dep in loaded_dependents:
            LOGGER.debug(
                f"Unloading loaded domain {dep.domain} "
                f"with identifier {dep.identifier} "
                f"because its dependency {entry.domain} "
                f"with identifier {entry.identifier} is now available"
            )
            _unload_domain_chain(vis, dep.domain, dep.identifier, plan)


def _apply_setup_plan(vis: Viseron, new_config: dict, plan: SetupPlan) -> None:
    """Set up all components and domains collected in the plan."""
    if not plan.components and not plan.domain_components:
        LOGGER.debug("No components or domains to set up after reload")
        return

    LOGGER.debug(f"Components to setup: {plan.components}")
    setup_components(
        vis,
        new_config,
        reloading=True,
        components=plan.components,
    )
    # After new components register their domains as PENDING, unload any
    # dependents so they can be re-setup with the new dependency.
    _unload_dependents_of_pending_domains(vis, plan)

    LOGGER.debug(f"Components to setup domains for: {plan.domain_components}")
    setup_components(
        vis,
        new_config,
        reloading=True,
        domains_only=True,
        components=plan.domain_components,
    )
    setup_domains(vis)


def _validate_config(
    vis: Viseron,
    new_config: dict,
    changes: ReloadChanges,
) -> bool:
    """Validate new config before applying changes."""
    components_to_validate = set()
    for component_change in changes.components_to_reload:
        components_to_validate.add(component_change.component_name)
    for domain_change in changes.domains_to_reload:
        components_to_validate.add(domain_change.component_name)
    for identifier_change in changes.identifiers_to_reload:
        components_to_validate.add(identifier_change.component_name)

    LOGGER.debug(f"Validating config for components: {components_to_validate}")
    for component_name in components_to_validate:
        component_instance = get_component(vis, component_name, new_config)
        try:
            result = component_instance.validate_component_config()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(f"Config validation failed for component {component_name}")
            return False

        if not result:
            LOGGER.error(f"Config validation failed for component {component_name}")
            return False

    return True


def _reload_config(
    vis: Viseron,
    cancelled_retries: list[DomainEntry],
) -> ReloadResult:
    """Reload configuration from config.yaml and apply changes."""
    result = ReloadResult(success=True)

    try:
        loaded = _load_and_diff_config(vis)
    except Exception as ex:  # pylint: disable=broad-except
        LOGGER.exception("Failed to load new config")
        result.success = False
        result.errors.append(f"Failed to load config.yaml: {ex}")
        return result

    new_config, diff, changes = loaded
    result.diff = diff
    plan = SetupPlan()

    default_components_changed = _check_default_component_changes(diff)
    if default_components_changed:
        result.restart_required = True
        LOGGER.info(
            f"Changes detected in default components {default_components_changed}, "
            f"restart is required to apply these changes"
        )
        diff.remove_default_components()

    _handle_removed_components(vis, diff, plan)
    _handle_added_components(diff, plan)

    if not _validate_config(vis, new_config, changes):
        result.success = False
        result.errors.append("Config validation failed for modified components")
        LOGGER.error("Config validation failed, aborting reload")
        return result

    _handle_modified_components(vis, changes, plan)
    _handle_modified_domains(vis, changes, plan)
    _handle_modified_identifiers(vis, changes, plan)
    _handle_cancelled_retries(vis, cancelled_retries, plan)

    _apply_setup_plan(vis, new_config, plan)

    vis.set_config(new_config)
    return result


def reload_config(vis: Viseron) -> ReloadResult:
    """Reload config.yaml and apply changes."""
    start = time.time()
    LOGGER.info("Config reload requested")

    # Cancel all retrying domains so any in-progress reload
    # can finish and release the lock.
    cancelled_retries = vis.domain_registry.cancel_all_retries()
    with vis.reload_lock:
        # Wait until initial setup is complete before allowing reload
        vis.initialized_event.wait()
        result = _reload_config(vis, cancelled_retries)

    if not result.success:
        LOGGER.error(f"Config reload failed with errors: {result.errors}")
    elif result.diff and result.diff.has_changes:
        end = time.time()
        LOGGER.info(f"Config reload completed in {end - start:.2f} seconds")
    else:
        LOGGER.info("No configuration changes detected")

    return result
