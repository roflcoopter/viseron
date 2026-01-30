"""Domain registry for tracking domain lifecycle and state."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic

from typing_extensions import TypeVar

from viseron.const import (
    EVENT_DOMAIN_REGISTERED,
    EVENT_DOMAIN_SETUP_STATUS,
    EVENT_DOMAIN_UNREGISTERED,
)
from viseron.events import EventData, EventEmptyData
from viseron.exceptions import DomainNotRegisteredError
from viseron.types import SupportedDomains

if TYPE_CHECKING:
    from viseron import Viseron
    from viseron.domains import AbstractDomain, OptionalDomain, RequireDomain
    from viseron.domains.camera import FailedCamera

LOGGER = logging.getLogger(__name__)


class DomainState(Enum):
    """State of a domain in its lifecycle."""

    PENDING = "pending"  # Configured, waiting for setup
    LOADING = "loading"  # Currently being set up
    LOADED = "loaded"  # Successfully loaded
    FAILED = "failed"  # Failed to load
    RETRYING = "retrying"  # Failed but will retry


@dataclass
class DomainEntry:
    """Represents a domain throughout its lifecycle."""

    component_name: str
    component_path: str
    domain: SupportedDomains
    identifier: str
    config: dict[str, Any]
    require_domains: list[RequireDomain] = field(default_factory=list)
    optional_domains: list[OptionalDomain] = field(default_factory=list)
    state: DomainState = DomainState.PENDING
    instance: AbstractDomain | None = None
    error: str | None = None
    error_instance: FailedCamera | None = None
    setup_future: Future | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return as dict for serialization."""
        return {
            "component": self.component_name,
            "domain": self.domain,
            "identifier": self.identifier,
            "config": self.config,
            "require_domains": [
                {"domain": r.domain, "identifier": r.identifier}
                for r in self.require_domains
            ],
            "optional_domains": [
                {"domain": o.domain, "identifier": o.identifier}
                for o in self.optional_domains
            ],
            "state": self.state.value,
            "error": self.error,
        }


@dataclass
class EventDomainSetupStatusData(EventData):
    """Event data for domain setup status changes."""

    component: str
    domain: str
    identifier: str
    state: str
    error: str | None = None


T = TypeVar("T")


@dataclass
class EventDomainRegisteredData(EventData, Generic[T]):
    """Event data for domain registered event."""

    json_serializable = False

    domain: str
    identifier: str
    instance: T


class DomainRegistry:
    """Centralized registry for all domain lifecycle management."""

    def __init__(self, vis: Viseron) -> None:
        self._vis = vis
        self._lock = threading.Lock()
        self._domains: dict[str, dict[str, DomainEntry]] = {}

    def register(
        self,
        component_name: str,
        component_path: str,
        domain: SupportedDomains,
        identifier: str,
        config: dict[str, Any],
        require_domains: list[RequireDomain] | None = None,
        optional_domains: list[OptionalDomain] | None = None,
    ) -> DomainEntry:
        """Register a domain for setup.

        Called when a component wants to set up a domain.
        The domain starts in PENDING state.
        """
        with self._lock:
            if domain in self._domains and identifier in self._domains[domain]:
                existing = self._domains[domain][identifier]
                if existing.state in (DomainState.LOADED, DomainState.LOADING):
                    LOGGER.warning(
                        f"Domain {domain} with identifier {identifier} already "
                        f"registered (state: {existing.state.value}). Skipping",
                    )
                    return existing

            entry = DomainEntry(
                component_name=component_name,
                component_path=component_path,
                domain=domain,
                identifier=identifier,
                config=config,
                require_domains=require_domains or [],
                optional_domains=optional_domains or [],
                state=DomainState.PENDING,
            )
            self._domains.setdefault(domain, {})[identifier] = entry
            LOGGER.debug(
                f"Registered domain {domain} with "
                f"identifier {identifier} "
                f"for component {component_name} (state: PENDING)",
            )
            return entry

    def set_state(
        self,
        domain: str,
        identifier: str,
        state: DomainState,
        error: str | None = None,
        instance: AbstractDomain | None = None,
        error_instance: FailedCamera | None = None,
    ) -> None:
        """Update the state of a domain."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            if entry is None:
                LOGGER.error(
                    f"Cannot set state for missing domain {domain} with "
                    f"identifier {identifier}",
                )
                return

            old_state = entry.state
            entry.state = state
            if error is not None:
                entry.error = error
            if instance is not None:
                entry.instance = instance
            if error_instance is not None:
                entry.error_instance = error_instance

            LOGGER.debug(
                f"Changing state for domain {domain} with identifier {identifier} "
                f"for component {entry.component_name} "
                f"from {old_state.value} -> {state.value}",
            )

        # Dispatch event outside lock
        self._dispatch_status_event(entry, state, error)

        # Dispatch domain registered event when loaded
        if state == DomainState.LOADED:
            if entry.instance is None:
                LOGGER.warning(
                    f"Domain {domain} with identifier {identifier} for component "
                    f"{entry.component_name} has been loaded "
                    "but the instance has not been set",
                )
                return
            self._vis.dispatch_event(
                EVENT_DOMAIN_REGISTERED.format(domain=domain),
                EventDomainRegisteredData(
                    domain=domain,
                    identifier=identifier,
                    instance=entry.instance,
                ),
                store=False,
            )

    def set_instance(self, domain: str, identifier: str, instance: Any) -> None:
        """Set the domain instance after successful setup."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            if entry is None:
                LOGGER.error(
                    f"Cannot set instance for missing domain {domain} with "
                    f"identifier {identifier}",
                )
                return
            entry.instance = instance

    def set_future(self, domain: str, identifier: str, future: Future) -> None:
        """Set the setup future for dependency waiting."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            if entry:
                entry.setup_future = future

    def get_future(self, domain: str, identifier: str) -> Future | None:
        """Get the setup future for a domain."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            return entry.setup_future if entry else None

    def unregister(self, domain: str, identifier: str) -> DomainEntry | None:
        """Unregister a domain completely.

        Called during unload/reload. Returns the entry for cleanup.
        """
        with self._lock:
            if domain not in self._domains:
                return None
            entry = self._domains[domain].pop(identifier, None)
            if entry:
                LOGGER.debug(
                    f"Unregistered domain {domain} with identifier {identifier} "
                    f"for component {entry.component_name}"
                )

        if entry:
            self._vis.dispatch_event(
                EVENT_DOMAIN_UNREGISTERED.format(domain=domain),
                EventEmptyData(),
                store=False,
            )
        return entry

    def get(self, domain: str, identifier: str) -> DomainEntry | None:
        """Get a domain entry."""
        with self._lock:
            return self._get_entry(domain, identifier)

    def get_instance(self, domain: str, identifier: str) -> Any:
        """Get the instance for a loaded domain.

        Raises DomainNotRegisteredError if not found or not loaded.
        """
        with self._lock:
            entry = self._get_entry(domain, identifier)
            if entry and entry.state == DomainState.LOADED and entry.instance:
                return entry.instance
        raise DomainNotRegisteredError(domain, identifier=identifier)

    def get_all_instances(self, domain: str) -> dict[str, Any]:
        """Get all loaded instances for a domain type."""
        with self._lock:
            if domain not in self._domains:
                raise DomainNotRegisteredError(domain)
            return {
                identifier: entry.instance
                for identifier, entry in self._domains.get(domain, {}).items()
                if entry.state == DomainState.LOADED and entry.instance
            }

    def get_identifiers(self, domain: str) -> list[str]:
        """Get all identifiers for a domain type."""
        with self._lock:
            return list(self._domains.get(domain, {}).keys())

    def get_by_state(self, state: DomainState) -> list[DomainEntry]:
        """Get all domains in a specific state."""
        with self._lock:
            return [
                entry
                for domain_entries in self._domains.values()
                for entry in domain_entries.values()
                if entry.state == state
            ]

    def get_by_state_for_domain(
        self, domain: str, state: DomainState
    ) -> dict[str, DomainEntry]:
        """Get all entries for a domain type in a specific state."""
        with self._lock:
            return {
                identifier: entry
                for identifier, entry in self._domains.get(domain, {}).items()
                if entry.state == state
            }

    def get_by_states_for_domain(
        self, domain: str, states: list[DomainState]
    ) -> dict[str, DomainEntry]:
        """Get all entries for a domain type in a list of specific states."""
        with self._lock:
            return {
                identifier: entry
                for identifier, entry in self._domains.get(domain, {}).items()
                if entry.state in states
            }

    def get_pending(self) -> list[DomainEntry]:
        """Get all domains pending setup."""
        return self.get_by_state(DomainState.PENDING)

    def get_loaded(self, domain: str) -> dict[str, DomainEntry]:
        """Get all loaded domains for a domain type."""
        return self.get_by_state_for_domain(domain, DomainState.LOADED)

    def get_failed(self, domain: str) -> dict[str, DomainEntry]:
        """Get all failed (and retrying) domains for a domain type."""
        return self.get_by_states_for_domain(
            domain, [DomainState.FAILED, DomainState.RETRYING]
        )

    def is_loaded(self, domain: str, identifier: str) -> bool:
        """Check if a domain is loaded."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            return entry is not None and entry.state == DomainState.LOADED

    def is_configured(self, domain: str, identifier: str) -> bool:
        """Check if a domain is configured (any state)."""
        with self._lock:
            return self._get_entry(domain, identifier) is not None

    def get_by_component(self, component_name: str) -> list[DomainEntry]:
        """Get all domains for a specific component."""
        with self._lock:
            return [
                entry
                for domain_entries in self._domains.values()
                for entry in domain_entries.values()
                if entry.component_name == component_name
            ]

    def get_loaded_by_component(self, component_name: str) -> list[DomainEntry]:
        """Get all loaded domains for a specific component."""
        with self._lock:
            return [
                entry
                for domain_entries in self._domains.values()
                for entry in domain_entries.values()
                if entry.component_name == component_name
                and entry.state == DomainState.LOADED
            ]

    def get_dependents(
        self, target_domain: str, target_identifier: str
    ) -> list[DomainEntry]:
        """Find all loaded domains that depend on the given domain.

        Searches require_domains and optional_domains.
        """
        dependents: list[DomainEntry] = []
        with self._lock:
            for domain_entries in self._domains.values():
                for entry in domain_entries.values():
                    if entry.state != DomainState.LOADED:
                        continue
                    # Check require_domains
                    for req in entry.require_domains:
                        if (
                            req.domain == target_domain
                            and req.identifier == target_identifier
                        ):
                            dependents.append(entry)
                            break
                    else:
                        # Check optional_domains
                        for opt in entry.optional_domains:
                            if (
                                opt.domain == target_domain
                                and opt.identifier == target_identifier
                            ):
                                dependents.append(entry)
                                break
        return dependents

    def validate_dependencies(self) -> list[DomainEntry]:
        """Validate that all required dependencies are marked for setup.

        Returns list of entries with missing dependencies.
        """
        failed: list[DomainEntry] = []
        with self._lock:
            for domain_entries in self._domains.values():
                for entry in domain_entries.values():
                    if entry.state != DomainState.PENDING:
                        continue
                    for req in entry.require_domains:
                        if not self._get_entry(req.domain, req.identifier):
                            entry.error = (
                                f"Required domain {req.domain} "
                                f"with identifier {req.identifier} "
                                "not configured"
                            )
                            failed.append(entry)
                            break
        return failed

    def clear_future(self, domain: str, identifier: str) -> None:
        """Clear the setup future after completion."""
        with self._lock:
            entry = self._get_entry(domain, identifier)
            if entry:
                entry.setup_future = None

    def _get_entry(self, domain: str, identifier: str) -> DomainEntry | None:
        """Get entry."""
        return self._domains.get(domain, {}).get(identifier)

    def _dispatch_status_event(
        self,
        entry: DomainEntry,
        state: DomainState,
        error: str | None,
    ) -> None:
        """Dispatch domain setup status event."""
        component_name = entry.component_name if entry else "unknown"
        self._vis.dispatch_event(
            EVENT_DOMAIN_SETUP_STATUS.format(
                status=entry.state.value,
                domain=entry.domain,
                identifier=entry.identifier,
            ),
            EventDomainSetupStatusData(
                component=component_name,
                domain=entry.domain,
                identifier=entry.identifier,
                state=state.value,
                error=error,
            ),
            store=False,
        )
