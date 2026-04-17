"""Test reload functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch

import pytest

from viseron.components import ComponentError, ComponentErrorSource, ValidationResult
from viseron.config import ComponentChange, ConfigDiff, DomainChange, IdentifierChange
from viseron.domain_registry import DomainEntry, DomainState
from viseron.reload import (
    ReloadChanges,
    ReloadResult,
    SetupPlan,
    _apply_setup_plan,
    _check_default_component_changes,
    _get_changes,
    _handle_added_components,
    _handle_cancelled_retries,
    _handle_modified_components,
    _handle_modified_domains,
    _handle_modified_identifiers,
    _handle_removed_components,
    _load_and_diff_config,
    _process_identifier_changes,
    _reload_config,
    _unload_dependents_of_pending_domains,
    _validate_config,
    reload_config,
)

if TYPE_CHECKING:
    from viseron.viseron_types import SupportedDomains


def _make_domain_entry(
    component_name: str = "ffmpeg",
    domain: SupportedDomains = "camera",
    identifier: str = "cam1",
) -> DomainEntry:
    """Create a DomainEntry."""
    return DomainEntry(
        component_name=component_name,
        component_path=f"viseron.components.{component_name}",
        domain=domain,
        identifier=identifier,
        config={},
    )


class TestProcessIdentifierChanges:
    """Test _process_identifier_changes function."""

    def test_no_changes_both_empty(self) -> None:
        """Test with both old and new configs empty."""
        result = _process_identifier_changes("ffmpeg", "camera", {}, {})
        assert not result

    def test_no_changes_identical_configs(self) -> None:
        """Test with identical old and new configs."""
        config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = _process_identifier_changes("ffmpeg", "camera", config, config.copy())
        assert not result

    def test_single_identifier_added(self) -> None:
        """Test detection of a single newly added identifier."""
        old_config: dict[str, Any] = {}
        new_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_added is True
        assert result[0].component_name == "ffmpeg"
        assert result[0].domain == "camera"
        assert result[0].old_config is None
        assert result[0].new_config == {"host": "192.168.1.1"}

    def test_multiple_identifiers_added(self) -> None:
        """Test detection of multiple newly added identifiers."""
        old_config: dict[str, Any] = {}
        new_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert len(result) == len(new_config)
        identifiers = {c.identifier for c in result}
        assert identifiers == {"cam1", "cam2"}
        assert all(c.is_added for c in result)

    def test_single_identifier_removed(self) -> None:
        """Test detection of a single removed identifier."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {}

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_removed is True
        assert result[0].old_config == {"host": "192.168.1.1"}
        assert result[0].new_config is None

    def test_multiple_identifiers_removed(self) -> None:
        """Test detection of multiple removed identifiers."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        new_config: dict[str, Any] = {}

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert len(result) == len(old_config)
        identifiers = {c.identifier for c in result}
        assert identifiers == {"cam1", "cam2"}
        assert all(c.is_removed for c in result)

    def test_single_identifier_modified(self) -> None:
        """Test detection of a single modified identifier."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {"cam1": {"host": "10.0.0.1"}}

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_added is False
        assert result[0].is_removed is False
        assert result[0].is_identifier_level_change is True
        assert result[0].old_config == {"host": "192.168.1.1"}
        assert result[0].new_config == {"host": "10.0.0.1"}

    def test_mixed_added_removed_modified(self) -> None:
        """Test simultaneous added, removed, and modified identifiers."""
        old_config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        new_config: dict[str, Any] = {
            "cam1": {"host": "10.0.0.1"},
            "cam3": {"host": "192.168.1.3"},
        }

        result = _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        changes_by_id = {c.identifier: c for c in result}
        assert len(result) == 3
        assert changes_by_id["cam1"].is_identifier_level_change is True
        assert changes_by_id["cam1"].old_config == {"host": "192.168.1.1"}
        assert changes_by_id["cam1"].new_config == {"host": "10.0.0.1"}
        assert changes_by_id["cam2"].is_removed is True
        assert changes_by_id["cam3"].is_added is True

    def test_filters_out_non_identifier_level_changes(self) -> None:
        """Test that changes where is_identifier_level_change is False are filtered."""
        # Create changes: one that is identifier-level and one that is not
        identifier_change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config={"host": "192.168.1.1"},
            new_config={"host": "10.0.0.1"},
        )
        non_identifier_change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam2",
            old_config=None,
            new_config=None,
        )

        with patch(
            "viseron.reload.diff_identifier_config",
            return_value=[identifier_change, non_identifier_change],
        ):
            result = _process_identifier_changes("ffmpeg", "camera", {}, {})

        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_identifier_level_change is True

    def test_passes_arguments_to_diff_identifier_config(self) -> None:
        """Test that arguments are correctly forwarded to diff_identifier_config."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {"cam2": {"host": "192.168.1.2"}}

        with patch(
            "viseron.reload.diff_identifier_config",
            return_value=[],
        ) as mock_diff:
            _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        mock_diff.assert_called_once_with("ffmpeg", "camera", old_config, new_config)

    def test_nested_config_changes(self) -> None:
        """Test with deeply nested configuration values."""
        old_config: dict[str, Any] = {
            "cam1": {"zones": {"zone1": {"coordinates": [[0, 0], [100, 100]]}}},
        }
        new_config: dict[str, Any] = {
            "cam1": {"zones": {"zone1": {"coordinates": [[0, 0], [200, 200]]}}},
        }

        result = _process_identifier_changes(
            "darknet", "object_detector", old_config, new_config
        )

        assert len(result) == 1
        assert result[0].identifier == "cam1"
        assert result[0].is_identifier_level_change is True

    def test_original_configs_not_mutated(self) -> None:
        """Test that the original config dicts are not mutated."""
        old_config: dict[str, Any] = {"cam1": {"host": "192.168.1.1"}}
        new_config: dict[str, Any] = {"cam1": {"host": "10.0.0.1"}}
        old_copy = {"cam1": {"host": "192.168.1.1"}}
        new_copy = {"cam1": {"host": "10.0.0.1"}}

        _process_identifier_changes("ffmpeg", "camera", old_config, new_config)

        assert old_config == old_copy
        assert new_config == new_copy


class TestGetChanges:
    """Test _get_changes function."""

    def test_empty_diff(self) -> None:
        """Test with no changes in the diff."""
        diff = ConfigDiff()

        result = _get_changes(diff)

        assert not result.components_to_reload
        assert not result.domains_to_reload
        assert not result.identifiers_to_reload

    def test_only_added_and_removed_components_ignored(self) -> None:
        """Test that added/removed components are not returned as modified."""
        diff = ConfigDiff(
            component_changes={
                "new_comp": ComponentChange(
                    component_name="new_comp",
                    old_config=None,
                    new_config={"key": "val"},
                ),
                "old_comp": ComponentChange(
                    component_name="old_comp",
                    old_config={"key": "val"},
                    new_config=None,
                ),
            }
        )

        result = _get_changes(diff)

        assert not result.components_to_reload
        assert not result.domains_to_reload
        assert not result.identifiers_to_reload

    def test_component_level_change(self) -> None:
        """Test that a component-level change is classified correctly."""
        change = ComponentChange(
            component_name="ffmpeg",
            old_config={"test": 2},
            new_config={"test": 4},
        )
        diff = ConfigDiff(component_changes={"ffmpeg": change})

        result = _get_changes(diff)

        assert len(result.components_to_reload) == 1
        assert result.components_to_reload[0].component_name == "ffmpeg"
        assert not result.domains_to_reload
        assert not result.identifiers_to_reload

    @patch("viseron.reload._process_domain_changes")
    def test_domain_level_change(self, mock_process: MagicMock) -> None:
        """Test that domain-level changes are routed to domains_to_reload."""
        domain_change = DomainChange(
            component_name="darknet",
            domain="object_detector",
            old_config={"threshold": 0.5, "cameras": {}},
            new_config={"threshold": 0.8, "cameras": {}},
        )
        mock_process.return_value = ([domain_change], [])

        change = ComponentChange(
            component_name="darknet",
            old_config={"object_detector": {"threshold": 0.5, "cameras": {}}},
            new_config={"object_detector": {"threshold": 0.8, "cameras": {}}},
        )
        diff = ConfigDiff(component_changes={"darknet": change})

        result = _get_changes(diff)

        assert not result.components_to_reload
        assert len(result.domains_to_reload) == 1
        assert result.domains_to_reload[0].component_name == "darknet"
        assert not result.identifiers_to_reload

    @patch("viseron.reload._process_domain_changes")
    def test_identifier_level_change(self, mock_process: MagicMock) -> None:
        """Test that identifier-level changes are routed to identifiers_to_reload."""
        id_change = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config={"host": "192.168.1.1"},
            new_config={"host": "10.0.0.1"},
        )
        mock_process.return_value = ([], [id_change])

        change = ComponentChange(
            component_name="ffmpeg",
            old_config={"camera": {"cam1": {"host": "192.168.1.1"}}},
            new_config={"camera": {"cam1": {"host": "10.0.0.1"}}},
        )
        diff = ConfigDiff(component_changes={"ffmpeg": change})

        result = _get_changes(diff)

        assert not result.components_to_reload
        assert not result.domains_to_reload
        assert len(result.identifiers_to_reload) == 1
        assert result.identifiers_to_reload[0].identifier == "cam1"

    @patch("viseron.reload._process_domain_changes")
    def test_mixed_component_and_domain_changes(self, mock_process: MagicMock) -> None:
        """Test mix of component-level and domain-level changes across components."""
        domain_change = DomainChange(
            component_name="darknet",
            domain="object_detector",
            old_config={"threshold": 0.5, "cameras": {}},
            new_config={"threshold": 0.8, "cameras": {}},
        )
        mock_process.return_value = ([domain_change], [])

        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config={"test": 2},
                    new_config={"test": 4},
                ),
                "darknet": ComponentChange(
                    component_name="darknet",
                    old_config={"object_detector": {"threshold": 0.5, "cameras": {}}},
                    new_config={"object_detector": {"threshold": 0.8, "cameras": {}}},
                ),
            }
        )

        result = _get_changes(diff)

        assert len(result.components_to_reload) == 1
        assert result.components_to_reload[0].component_name == "ffmpeg"
        assert len(result.domains_to_reload) == 1
        assert result.domains_to_reload[0].component_name == "darknet"


class TestLoadAndDiffConfig:
    """Test _load_and_diff_config function."""

    @patch("viseron.reload._get_changes")
    @patch("viseron.reload.diff_config")
    @patch("viseron.reload.load_config")
    def test_returns_new_config_diff_and_changes(
        self,
        mock_load: MagicMock,
        mock_diff: MagicMock,
        mock_get_changes: MagicMock,
    ) -> None:
        """Test the return tuple structure."""
        vis = MagicMock()
        vis.config = {"ffmpeg": {"camera": {"cam1": {}}}}
        new_cfg = {"ffmpeg": {"camera": {"cam1": {"host": "10.0.0.1"}}}}
        mock_load.return_value = new_cfg
        mock_diff.return_value = ConfigDiff()
        mock_get_changes.return_value = ReloadChanges()

        result_config, result_diff, result_changes = _load_and_diff_config(vis)

        assert result_config is new_cfg
        assert isinstance(result_diff, ConfigDiff)
        assert isinstance(result_changes, ReloadChanges)
        mock_load.assert_called_once()
        mock_diff.assert_called_once_with(vis.config, new_cfg)
        mock_get_changes.assert_called_once_with(mock_diff.return_value)


class TestCheckDefaultComponentChanges:
    """Test _check_default_component_changes function."""

    @pytest.mark.parametrize(
        ("diff", "expected"),
        [
            pytest.param(
                ConfigDiff(),
                set(),
                id="no_default_component_changes",
            ),
            pytest.param(
                ConfigDiff(
                    component_changes={
                        "webserver": ComponentChange(
                            component_name="webserver",
                            old_config=None,
                            new_config={"auth": {}},
                        ),
                    }
                ),
                {"webserver"},
                id="default_component_added",
            ),
            pytest.param(
                ConfigDiff(
                    component_changes={
                        "webserver": ComponentChange(
                            component_name="webserver",
                            old_config={"auth": {}},
                            new_config=None,
                        ),
                    }
                ),
                {"webserver"},
                id="default_component_removed",
            ),
            pytest.param(
                ConfigDiff(
                    component_changes={
                        "webserver": ComponentChange(
                            component_name="webserver",
                            old_config={"auth": {"enabled": False}},
                            new_config={"auth": {"enabled": True}},
                        ),
                    }
                ),
                {"webserver"},
                id="default_component_modified",
            ),
        ],
    )
    def test_check_default_component_changes(
        self, diff: ConfigDiff, expected: set
    ) -> None:
        """Test _check_default_component_changes with various scenarios."""
        result = _check_default_component_changes(diff)

        assert result == expected


class TestReloadChangesRemoveDefaultComponents:
    """Test ReloadChanges.remove_default_components method."""

    def test_empty_lists_unchanged(self) -> None:
        """Test that empty lists remain empty after filtering."""
        changes = ReloadChanges()
        changes.remove_default_components()

        assert not changes.components_to_reload
        assert not changes.domains_to_reload
        assert not changes.identifiers_to_reload

    def test_only_default_components_are_removed(self) -> None:
        """Test that entries for DEFAULT_COMPONENTS are removed from all lists."""
        changes = ReloadChanges(
            components_to_reload=[
                ComponentChange(
                    component_name="webserver",
                    old_config={"key": "old"},
                    new_config={"key": "new"},
                ),
                ComponentChange(
                    component_name="storage",
                    old_config={"key": "old"},
                    new_config={"key": "new"},
                ),
            ],
        )
        changes.remove_default_components()

        assert not changes.components_to_reload
        assert not changes.domains_to_reload
        assert not changes.identifiers_to_reload

    def test_non_default_components_are_kept(self) -> None:
        """Test that entries for non-default components are not removed."""
        ffmpeg_comp = ComponentChange(
            component_name="ffmpeg",
            old_config={"key": "old"},
            new_config={"key": "new"},
        )
        ffmpeg_domain = DomainChange(
            component_name="ffmpeg",
            domain="camera",
            old_config=None,
            new_config={"cam1": {}},
        )
        ffmpeg_id = IdentifierChange(
            component_name="ffmpeg",
            domain="camera",
            identifier="cam1",
            old_config=None,
            new_config={"host": "192.168.1.1"},
        )
        changes = ReloadChanges(
            components_to_reload=[ffmpeg_comp],
            domains_to_reload=[ffmpeg_domain],
            identifiers_to_reload=[ffmpeg_id],
        )
        changes.remove_default_components()

        assert changes.components_to_reload == [ffmpeg_comp]
        assert changes.domains_to_reload == [ffmpeg_domain]
        assert changes.identifiers_to_reload == [ffmpeg_id]


class TestHandleRemovedComponents:
    """Test _handle_removed_components function."""

    @patch("viseron.reload.unload_component")
    def test_no_removed_components(self, mock_unload: MagicMock) -> None:
        """Test with no removed components in the diff."""
        vis = MagicMock()
        diff = ConfigDiff()
        plan = SetupPlan()

        _handle_removed_components(vis, diff, plan)

        mock_unload.assert_not_called()
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_component", return_value=None)
    def test_removed_no_affected(self, mock_unload: MagicMock) -> None:
        """Test removed component with no affected components."""
        vis = MagicMock()
        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config={"camera": {}},
                    new_config=None,
                ),
            }
        )
        plan = SetupPlan()

        _handle_removed_components(vis, diff, plan)

        mock_unload.assert_called_once_with(vis, "ffmpeg")
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_component")
    def test_removed_with_affected_components(self, mock_unload: MagicMock) -> None:
        """Test removed component that returns affected components."""
        vis = MagicMock()
        mock_unload.return_value = {"darknet", "nvr"}
        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config={"camera": {}},
                    new_config=None,
                ),
            }
        )
        plan = SetupPlan()

        _handle_removed_components(vis, diff, plan)

        mock_unload.assert_called_once_with(vis, "ffmpeg")
        assert plan.domain_components == {"darknet", "nvr"}

    @patch("viseron.reload.unload_component")
    def test_multiple_removed_components(self, mock_unload: MagicMock) -> None:
        """Test multiple removed components accumulate affected."""
        vis = MagicMock()
        mock_unload.side_effect = [{"darknet"}, {"mqtt"}]
        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config={"camera": {}},
                    new_config=None,
                ),
                "gstreamer": ComponentChange(
                    component_name="gstreamer",
                    old_config={"camera": {}},
                    new_config=None,
                ),
            }
        )
        plan = SetupPlan()

        _handle_removed_components(vis, diff, plan)

        assert mock_unload.call_count == 2
        assert plan.domain_components == {"darknet", "mqtt"}


class TestHandleAddedComponents:
    """Test _handle_added_components function."""

    def test_no_added_components(self) -> None:
        """Test with no added components in the diff."""
        diff = ConfigDiff()
        plan = SetupPlan()

        _handle_added_components(diff, plan)

        assert plan.components == set()

    def test_multiple_added_components(self) -> None:
        """Test that all added components are marked for setup."""
        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config=None,
                    new_config={"camera": {}},
                ),
                "darknet": ComponentChange(
                    component_name="darknet",
                    old_config=None,
                    new_config={"object_detector": {}},
                ),
                "mqtt": ComponentChange(
                    component_name="mqtt",
                    old_config={"host": "old"},
                    new_config={"host": "new"},
                ),
            }
        )
        plan = SetupPlan()

        _handle_added_components(diff, plan)

        assert plan.components == {"ffmpeg", "darknet"}
        assert plan.domain_components == set()


class TestHandleModifiedComponents:
    """Test _handle_modified_components function."""

    @patch("viseron.reload.unload_component")
    def test_no_modified_components(self, mock_unload: MagicMock) -> None:
        """Test with empty components_to_reload."""
        vis = MagicMock()
        changes = ReloadChanges()
        plan = SetupPlan()

        _handle_modified_components(vis, changes, plan)

        mock_unload.assert_not_called()
        assert plan.components == set()
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_component")
    def test_modified_with_and_without_affected(self, mock_unload: MagicMock) -> None:
        """Test modified components with and without affected dependents."""
        vis = MagicMock()
        mock_unload.side_effect = [{"nvr", "darknet"}, None]
        changes = ReloadChanges(
            components_to_reload=[
                ComponentChange(
                    component_name="ffmpeg",
                    old_config={"test": 2},
                    new_config={"test": 4},
                ),
                ComponentChange(
                    component_name="mqtt",
                    old_config={"host": "old"},
                    new_config={"host": "new"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_components(vis, changes, plan)

        assert plan.components == {"ffmpeg", "mqtt"}
        assert plan.domain_components == {"nvr", "darknet"}
        assert mock_unload.call_count == 2
        mock_unload.assert_any_call(vis, "ffmpeg")
        mock_unload.assert_any_call(vis, "mqtt")


class TestHandleModifiedDomains:
    """Test _handle_modified_domains function."""

    @patch("viseron.reload.unload_domain")
    def test_no_modified_domains(self, mock_unload: MagicMock) -> None:
        """Test with empty domains_to_reload."""
        vis = MagicMock()
        changes = ReloadChanges()
        plan = SetupPlan()

        _handle_modified_domains(vis, changes, plan)

        mock_unload.assert_not_called()
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_domain")
    def test_domain_unload_called_with_component_and_domain(
        self, mock_unload: MagicMock
    ) -> None:
        """Test that unload_domain is called with component name and domain."""
        vis = MagicMock()
        mock_unload.return_value = None
        changes = ReloadChanges(
            domains_to_reload=[
                DomainChange(
                    component_name="darknet",
                    domain="object_detector",
                    old_config={"threshold": 0.5, "cameras": {}},
                    new_config={"threshold": 0.8, "cameras": {}},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_domains(vis, changes, plan)

        assert plan.domain_components == {"darknet"}
        mock_unload.assert_called_once_with(vis, "darknet", "object_detector")

    @patch("viseron.reload.unload_domain")
    def test_domain_affected_components_added_to_plan(
        self, mock_unload: MagicMock
    ) -> None:
        """Test that affected components returned by unload_domain are added to plan."""
        vis = MagicMock()
        mock_unload.return_value = {"nvr", "darknet"}
        changes = ReloadChanges(
            domains_to_reload=[
                DomainChange(
                    component_name="ffmpeg",
                    domain="camera",
                    old_config={"width": 1920},
                    new_config={"width": 1280},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_domains(vis, changes, plan)

        assert plan.domain_components == {"ffmpeg", "nvr", "darknet"}
        mock_unload.assert_called_once_with(vis, "ffmpeg", "camera")

    @patch("viseron.reload.unload_domain")
    def test_domain_no_affected_components(self, mock_unload: MagicMock) -> None:
        """Test that None return from unload_domain does not update plan."""
        vis = MagicMock()
        mock_unload.return_value = None
        changes = ReloadChanges(
            domains_to_reload=[
                DomainChange(
                    component_name="darknet",
                    domain="object_detector",
                    old_config={"threshold": 0.5, "cameras": {}},
                    new_config={"threshold": 0.8, "cameras": {}},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_domains(vis, changes, plan)

        # Only the direct component_name is added; no extra components
        assert plan.domain_components == {"darknet"}

    @patch("viseron.reload.unload_domain")
    def test_multiple_domain_changes(self, mock_unload: MagicMock) -> None:
        """Test multiple domain changes call unload_domain for each and merge plan."""
        vis = MagicMock()
        mock_unload.side_effect = [{"nvr"}, None]
        changes = ReloadChanges(
            domains_to_reload=[
                DomainChange(
                    component_name="darknet",
                    domain="object_detector",
                    old_config={"threshold": 0.5, "cameras": {}},
                    new_config={"threshold": 0.8, "cameras": {}},
                ),
                DomainChange(
                    component_name="ffmpeg",
                    domain="camera",
                    old_config={"width": 1920},
                    new_config={"width": 1280},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_domains(vis, changes, plan)

        assert plan.domain_components == {"darknet", "ffmpeg", "nvr"}
        assert mock_unload.call_count == 2
        mock_unload.assert_any_call(vis, "darknet", "object_detector")
        mock_unload.assert_any_call(vis, "ffmpeg", "camera")


class TestHandleModifiedIdentifiers:
    """Test _handle_modified_identifiers function."""

    @patch("viseron.reload.unload_domain_chain")
    def test_no_modified_identifiers(self, mock_chain: MagicMock) -> None:
        """Test with empty identifiers_to_reload."""
        vis = MagicMock()
        changes = ReloadChanges()
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        mock_chain.assert_not_called()
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_domain_chain")
    def test_identifier_found_unloads_chain(self, mock_chain: MagicMock) -> None:
        """Test that a found identifier triggers chain unload and updates plan."""
        vis = MagicMock()
        entry = _make_domain_entry()
        vis.domain_registry.get_by_identifier.return_value = entry
        changes = ReloadChanges(
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam1",
                    old_config={"host": "192.168.1.1"},
                    new_config={"host": "10.0.0.1"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        assert "ffmpeg" in plan.domain_components
        vis.domain_registry.get_by_identifier.assert_called_once_with("camera", "cam1")
        mock_chain.assert_called_once_with(vis, entry.domain, entry.identifier)

    @patch("viseron.reload.unload_domain_chain")
    def test_identifier_not_found_no_unload(self, mock_chain: MagicMock) -> None:
        """Test that a missing identifier does not trigger chain unload."""
        vis = MagicMock()
        vis.domain_registry.get_by_identifier.return_value = None
        vis.domain_registry.get_dependents.return_value = []
        changes = ReloadChanges(
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam1",
                    old_config={"host": "192.168.1.1"},
                    new_config={"host": "10.0.0.1"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        assert "ffmpeg" in plan.domain_components
        mock_chain.assert_not_called()

    @patch("viseron.reload.unload_domain_chain")
    def test_multiple_identifiers_mixed(self, mock_chain: MagicMock) -> None:
        """Test multiple identifiers with mixed found/not-found results."""
        vis = MagicMock()
        entry = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        vis.domain_registry.get_by_identifier.side_effect = [entry, None]
        changes = ReloadChanges(
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="darknet",
                    domain="object_detector",
                    identifier="cam1",
                    old_config={"threshold": 0.5},
                    new_config={"threshold": 0.8},
                ),
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam2",
                    old_config={"host": "192.168.1.1"},
                    new_config={"host": "10.0.0.1"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        assert plan.domain_components == {"darknet", "ffmpeg"}
        mock_chain.assert_called_once_with(vis, entry.domain, entry.identifier)

    @patch("viseron.reload.unload_domain_chain")
    def test_added_identifier_unloads_dependents(self, mock_chain: MagicMock) -> None:
        """Test that adding an identifier unloads its dependents via chain."""
        vis = MagicMock()
        vis.domain_registry.get_by_identifier.return_value = None
        changes = ReloadChanges(
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam1",
                    old_config=None,
                    new_config={"host": "10.0.0.1"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        assert "ffmpeg" in plan.domain_components
        mock_chain.assert_called_once_with(vis, "camera", "cam1")

    @patch("viseron.reload.unload_domain_chain")
    def test_modified_identifier_does_not_check_dependents(
        self, mock_chain: MagicMock
    ) -> None:
        """Test that modifying an identifier does not check dependents."""
        vis = MagicMock()
        entry = _make_domain_entry()
        vis.domain_registry.get_by_identifier.return_value = entry
        changes = ReloadChanges(
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam1",
                    old_config={"host": "192.168.1.1"},
                    new_config={"host": "10.0.0.1"},
                ),
            ]
        )
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        # Should only call unload_domain_chain for the entry itself,
        # not a second time since it's a modification, not addition.
        mock_chain.assert_called_once_with(vis, entry.domain, entry.identifier)


class TestHandleCancelledRetries:
    """Test _handle_cancelled_retries function."""

    @patch("viseron.reload.unload_domain_chain")
    def test_no_cancelled_retries(self, mock_chain: MagicMock) -> None:
        """Test with an empty cancelled retries list."""
        vis = MagicMock()
        plan = SetupPlan()

        _handle_cancelled_retries(vis, [], plan)

        mock_chain.assert_not_called()

    @patch("viseron.reload.unload_domain_chain")
    def test_multiple_cancelled_retries(self, mock_chain: MagicMock) -> None:
        """Test that each cancelled retry triggers its own chain unload."""
        mock_chain.return_value = set()
        vis = MagicMock()
        entry1 = _make_domain_entry(identifier="cam1")
        entry2 = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam2",
        )
        plan = SetupPlan()

        _handle_cancelled_retries(vis, [entry1, entry2], plan)

        assert mock_chain.call_count == 2
        mock_chain.assert_has_calls(
            [
                call(vis, entry1.domain, entry1.identifier),
                call(vis, entry2.domain, entry2.identifier),
            ]
        )


class TestUnloadLoadedDependentsOfPendingDomains:
    """Test _unload_dependents_of_pending_domains function."""

    @patch("viseron.reload.unload_domain_chain")
    def test_no_pending_domains(self, mock_chain: MagicMock) -> None:
        """Test with no pending domains."""
        vis = MagicMock()
        vis.domain_registry.get_pending.return_value = []
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        mock_chain.assert_not_called()

    @patch("viseron.reload.unload_domain_chain")
    def test_pending_domain_with_no_dependents(self, mock_chain: MagicMock) -> None:
        """Test pending domain that has no dependents."""
        vis = MagicMock()
        pending = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        pending.state = DomainState.PENDING
        vis.domain_registry.get_pending.return_value = [pending]
        vis.domain_registry.get_dependents.return_value = []
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        vis.domain_registry.get_dependents.assert_called_once_with(
            "object_detector", "cam1"
        )
        mock_chain.assert_not_called()

    @patch("viseron.reload.unload_domain_chain")
    def test_loaded_dependent_is_unloaded(self, mock_chain: MagicMock) -> None:
        """Test that a LOADED dependent of a pending domain is unloaded."""
        vis = MagicMock()
        pending = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        pending.state = DomainState.PENDING
        loaded_dep = _make_domain_entry(
            component_name="nvr",
            domain="nvr",
            identifier="cam1",
        )
        loaded_dep.state = DomainState.LOADED
        vis.domain_registry.get_pending.return_value = [pending]
        vis.domain_registry.get_dependents.return_value = [loaded_dep]
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        mock_chain.assert_called_once_with(
            vis, loaded_dep.domain, loaded_dep.identifier
        )

    @patch("viseron.reload.unload_domain_chain")
    def test_pending_dependents_are_skipped(self, mock_chain: MagicMock) -> None:
        """Test that PENDING dependents are not unloaded."""
        vis = MagicMock()
        pending = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        pending.state = DomainState.PENDING
        pending_dep = _make_domain_entry(
            component_name="some_component",
            domain="license_plate_recognition",
            identifier="cam1",
        )
        pending_dep.state = DomainState.PENDING
        vis.domain_registry.get_pending.return_value = [pending]
        vis.domain_registry.get_dependents.return_value = [pending_dep]
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        mock_chain.assert_not_called()

    @patch("viseron.reload.unload_domain_chain")
    def test_multiple_pending_with_loaded_dependents(
        self, mock_chain: MagicMock
    ) -> None:
        """Test multiple pending domains each with loaded dependents."""
        mock_chain.return_value = set()
        vis = MagicMock()
        pending1 = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        pending1.state = DomainState.PENDING
        pending2 = _make_domain_entry(
            component_name="background_subtractor",
            domain="motion_detector",
            identifier="cam1",
        )
        pending2.state = DomainState.PENDING
        nvr_dep = _make_domain_entry(
            component_name="nvr", domain="nvr", identifier="cam1"
        )
        nvr_dep.state = DomainState.LOADED

        vis.domain_registry.get_pending.return_value = [pending1, pending2]
        vis.domain_registry.get_dependents.side_effect = [
            [nvr_dep],  # dependents of object_detector/cam1
            [nvr_dep],  # dependents of motion_detector/cam1
        ]
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        # NVR is found as dependent of both, but unload_domain_chain
        # is called for each (deduplication happens inside the chain)
        assert mock_chain.call_count == 2
        mock_chain.assert_has_calls(
            [
                call(vis, nvr_dep.domain, nvr_dep.identifier),
                call(vis, nvr_dep.domain, nvr_dep.identifier),
            ]
        )

    @patch("viseron.reload.unload_domain_chain")
    def test_mixed_loaded_and_non_loaded_dependents(
        self, mock_chain: MagicMock
    ) -> None:
        """Test that non-PENDING dependents are unloaded from a mixed set."""
        mock_chain.return_value = set()
        vis = MagicMock()
        pending = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        pending.state = DomainState.PENDING
        loaded_dep = _make_domain_entry(
            component_name="nvr", domain="nvr", identifier="cam1"
        )
        loaded_dep.state = DomainState.LOADED
        failed_dep = _make_domain_entry(
            component_name="some_comp",
            domain="license_plate_recognition",
            identifier="cam1",
        )
        failed_dep.state = DomainState.FAILED
        pending_dep = _make_domain_entry(
            component_name="another_comp",
            domain="face_recognition",
            identifier="cam1",
        )
        pending_dep.state = DomainState.PENDING
        vis.domain_registry.get_pending.return_value = [pending]
        vis.domain_registry.get_dependents.return_value = [
            loaded_dep,
            failed_dep,
            pending_dep,
        ]
        plan = SetupPlan()

        _unload_dependents_of_pending_domains(vis, plan)

        # Both LOADED and FAILED are unloaded, but PENDING is skipped
        assert mock_chain.call_count == 2
        mock_chain.assert_has_calls(
            [
                call(vis, loaded_dep.domain, loaded_dep.identifier),
                call(vis, failed_dep.domain, failed_dep.identifier),
            ]
        )


class TestApplySetupPlan:
    """Test _apply_setup_plan function."""

    @patch("viseron.reload._unload_dependents_of_pending_domains")
    @patch("viseron.reload.setup_domains")
    @patch("viseron.reload.setup_components")
    def test_calls_setup_in_correct_order(
        self,
        mock_setup_components: MagicMock,
        mock_setup_domains: MagicMock,
        mock_unload_dependents: MagicMock,
    ) -> None:
        """Test that components, domain components, and domains are set up in order."""
        vis = MagicMock()
        new_config: dict[str, dict[str, dict]] = {"ffmpeg": {"camera": {}}}
        plan = SetupPlan(
            components={"ffmpeg", "mqtt"},
            domain_components={"darknet"},
        )

        _apply_setup_plan(vis, new_config, plan)

        assert mock_setup_components.call_count == 2
        mock_setup_components.assert_has_calls(
            [
                call(
                    vis,
                    new_config,
                    reloading=True,
                    components={"ffmpeg", "mqtt"},
                ),
                call(
                    vis,
                    new_config,
                    reloading=True,
                    domains_only=True,
                    components={"darknet"},
                ),
            ]
        )
        mock_unload_dependents.assert_called_once_with(vis, plan)
        mock_setup_domains.assert_called_once_with(vis)

    @patch("viseron.reload._unload_dependents_of_pending_domains")
    @patch("viseron.reload.setup_domains")
    @patch("viseron.reload.setup_components")
    def test_empty_plan(
        self,
        mock_setup_components: MagicMock,
        mock_setup_domains: MagicMock,
        mock_unload_loaded: MagicMock,
    ) -> None:
        """Test that an empty plan returns early."""
        vis = MagicMock()
        plan = SetupPlan()

        _apply_setup_plan(vis, {}, plan)

        mock_setup_components.assert_not_called()
        mock_setup_domains.assert_not_called()
        mock_unload_loaded.assert_not_called()


class TestValidateConfig:
    """Test _validate_config function."""

    @patch("viseron.reload.get_component")
    def test_no_changes_returns_true(self, mock_get: MagicMock) -> None:
        """Test that an empty changes object validates successfully."""
        vis = MagicMock()

        result = _validate_config(vis, {}, ReloadChanges())

        assert not result
        mock_get.assert_not_called()

    @patch("viseron.reload.get_component")
    def test_all_change_types_collected(self, mock_get: MagicMock) -> None:
        """Test components from all change types are validated and deduplicated."""
        vis = MagicMock()
        mock_instance = MagicMock()
        mock_instance.validate_component_config.return_value = ValidationResult(
            success=True
        )
        mock_get.return_value = mock_instance
        new_config: dict[str, dict] = {"ffmpeg": {}, "darknet": {}}
        changes = ReloadChanges(
            components_to_reload=[
                ComponentChange(
                    component_name="ffmpeg",
                    old_config={"test": 2},
                    new_config={"test": 4},
                ),
            ],
            domains_to_reload=[
                DomainChange(
                    component_name="darknet",
                    domain="object_detector",
                    old_config={"threshold": 0.5},
                    new_config={"threshold": 0.8},
                ),
            ],
            identifiers_to_reload=[
                IdentifierChange(
                    component_name="ffmpeg",
                    domain="camera",
                    identifier="cam1",
                    old_config={"host": "192.168.1.1"},
                    new_config={"host": "10.0.0.1"},
                ),
            ],
        )

        result = _validate_config(vis, new_config, changes)

        assert not result
        # ffmpeg appears in both components and identifiers but should be deduplicated
        assert mock_get.call_count == 2
        validated = {c.args[1] for c in mock_get.call_args_list}
        assert validated == {"ffmpeg", "darknet"}

    @patch("viseron.reload.get_component")
    def test_validation_returns_false(self, mock_get: MagicMock) -> None:
        """Test that False from validate_component_config fails validation."""
        vis = MagicMock()
        mock_instance = MagicMock()
        mock_instance.validate_component_config.return_value = ValidationResult(
            success=False, error="test validation error"
        )
        mock_get.return_value = mock_instance
        changes = ReloadChanges(
            components_to_reload=[
                ComponentChange(
                    component_name="ffmpeg",
                    old_config={"test": 2},
                    new_config={"test": 4},
                ),
            ],
        )

        result = _validate_config(vis, {}, changes)

        assert len(result) == 1
        assert result[0].component_name == "ffmpeg"
        assert "test validation error" in result[0].message

    @patch("viseron.reload.get_component")
    def test_validation_exception_returns_false(self, mock_get: MagicMock) -> None:
        """Test that an exception during validation fails gracefully."""
        vis = MagicMock()
        mock_instance = MagicMock()
        mock_instance.validate_component_config.side_effect = RuntimeError("boom")
        mock_get.return_value = mock_instance
        changes = ReloadChanges(
            components_to_reload=[
                ComponentChange(
                    component_name="ffmpeg",
                    old_config={"test": 2},
                    new_config={"test": 4},
                ),
            ],
        )

        result = _validate_config(vis, {}, changes)

        assert len(result) == 1
        assert result[0].component_name == "ffmpeg"
        assert "boom" in result[0].message


class TestReloadConfig:
    """Test _reload_config function."""

    @patch("viseron.reload._load_and_diff_config")
    def test_load_failure_returns_error(self, mock_load: MagicMock) -> None:
        """Test that an exception during config loading returns a failed result."""
        vis = MagicMock()
        mock_load.side_effect = RuntimeError("parse error")

        result = _reload_config(vis, [])

        assert result.success is False
        assert len(result.errors) == 1
        assert "parse error" in result.errors[0].message

    @patch("viseron.reload._apply_setup_plan")
    @patch("viseron.reload._validate_config")
    @patch("viseron.reload._handle_added_components")
    @patch("viseron.reload._handle_removed_components")
    @patch("viseron.reload._load_and_diff_config")
    @patch("viseron.reload._check_default_component_changes", return_value=set())
    def test_validation_failure_aborts(
        self,
        mock_check_defaults: MagicMock,
        mock_load: MagicMock,
        mock_removed: MagicMock,
        mock_added: MagicMock,
        mock_validate: MagicMock,
        mock_apply: MagicMock,
    ) -> None:
        """Test that failed validation aborts before modifying components."""
        vis = MagicMock()
        mock_load.return_value = ({}, ConfigDiff(), ReloadChanges())
        mock_validate.return_value = [
            ComponentError(
                source=ComponentErrorSource.VALIDATION,
                message="Config validation failed for component 'test'",
                component_name="test",
            )
        ]

        result = _reload_config(vis, [])

        assert result.success is False
        assert "Config validation failed" in result.errors[0].message
        mock_removed.assert_not_called()
        mock_added.assert_not_called()
        mock_check_defaults.assert_called_once()
        mock_apply.assert_not_called()
        vis.set_config.assert_not_called()

    @patch("viseron.reload._apply_setup_plan")
    @patch("viseron.reload._handle_cancelled_retries")
    @patch("viseron.reload._handle_modified_identifiers")
    @patch("viseron.reload._handle_modified_domains")
    @patch("viseron.reload._handle_modified_components")
    @patch("viseron.reload._validate_config", return_value=[])
    @patch("viseron.reload._handle_added_components")
    @patch("viseron.reload._handle_removed_components")
    @patch("viseron.reload._load_and_diff_config")
    @patch("viseron.reload._check_default_component_changes", return_value=set())
    def test_successful_reload(
        self,
        mock_check_defaults: MagicMock,
        mock_load: MagicMock,
        mock_removed: MagicMock,
        mock_added: MagicMock,
        mock_validate: MagicMock,
        mock_modified_comp: MagicMock,
        mock_modified_dom: MagicMock,
        mock_modified_id: MagicMock,
        mock_cancelled: MagicMock,
        mock_apply: MagicMock,
    ) -> None:
        """Test a successful reload calls all steps and updates config."""
        vis = MagicMock()
        new_config: dict[str, dict] = {"ffmpeg": {}}
        diff = ConfigDiff()
        changes = ReloadChanges()
        mock_load.return_value = (new_config, diff, changes)
        cancelled = [_make_domain_entry()]

        result = _reload_config(vis, cancelled)

        assert result.success is True
        assert result.restart_required is False
        assert not result.errors
        mock_removed.assert_called_once()
        mock_added.assert_called_once()
        mock_validate.assert_called_once()
        mock_modified_comp.assert_called_once()
        mock_modified_dom.assert_called_once()
        mock_modified_id.assert_called_once()
        mock_cancelled.assert_called_once()
        mock_apply.assert_called_once()
        mock_check_defaults.assert_called_once_with(diff)
        vis.set_config.assert_called_once_with(new_config)

    @patch("viseron.reload._apply_setup_plan")
    @patch("viseron.reload._handle_cancelled_retries")
    @patch("viseron.reload._handle_modified_identifiers")
    @patch("viseron.reload._handle_modified_domains")
    @patch("viseron.reload._handle_modified_components")
    @patch("viseron.reload._validate_config", return_value=[])
    @patch("viseron.reload._handle_added_components")
    @patch("viseron.reload._handle_removed_components")
    @patch("viseron.reload._load_and_diff_config")
    @patch("viseron.reload._check_default_component_changes")
    def test_default_component_changes(
        self,
        mock_check_defaults: MagicMock,
        mock_load: MagicMock,
        mock_removed: MagicMock,
        mock_added: MagicMock,
        mock_validate: MagicMock,
        mock_modified_comp: MagicMock,
        mock_modified_dom: MagicMock,
        mock_modified_id: MagicMock,
        mock_cancelled: MagicMock,
        mock_apply: MagicMock,
    ) -> None:
        """Test that default component changes are handled correctly."""
        vis = MagicMock()
        new_config: dict[str, dict] = {
            "ffmpeg": {"key": "val"},
            "webserver": {"key": "val"},
        }
        diff = ConfigDiff(
            component_changes={
                "ffmpeg": ComponentChange(
                    component_name="ffmpeg",
                    old_config=None,
                    new_config=new_config["ffmpeg"],
                ),
                "webserver": ComponentChange(
                    component_name="webserver",
                    old_config=None,
                    new_config=new_config["webserver"],
                ),
            }
        )
        changes = ReloadChanges()
        mock_load.return_value = (new_config, diff, changes)
        mock_check_defaults.return_value = {"webserver"}

        result = _reload_config(vis, [])

        assert result.success is True
        assert result.restart_required is True
        assert "webserver" not in diff.component_changes
        assert "ffmpeg" in diff.component_changes
        assert not result.errors
        mock_removed.assert_called_once()
        mock_added.assert_called_once()
        mock_validate.assert_called_once()
        mock_modified_comp.assert_called_once()
        mock_modified_dom.assert_called_once()
        mock_modified_id.assert_called_once()
        mock_cancelled.assert_called_once()
        mock_apply.assert_called_once()
        mock_check_defaults.assert_called_once_with(diff)
        vis.set_config.assert_called_once_with(new_config)


class TestReloadConfigPublic:
    """Test reload_config function."""

    @patch("viseron.reload._reload_config")
    def test_cancels_retries_and_delegates(
        self, mock_inner: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that retries are cancelled, lock is acquired, and result returned."""
        vis = MagicMock()
        cancelled = [_make_domain_entry()]
        vis.domain_registry.cancel_all_retries.return_value = cancelled
        diff = ConfigDiff(
            component_changes={
                "new_comp": ComponentChange(
                    component_name="new_comp",
                    old_config=None,
                    new_config={"key": "val"},
                ),
            }
        )
        expected = ReloadResult(success=True, diff=diff)
        mock_inner.return_value = expected

        with caplog.at_level("DEBUG", logger="viseron.reload"):
            result = reload_config(vis)

        assert result is expected
        vis.domain_registry.cancel_all_retries.assert_called_once()
        vis.initialized_event.wait.assert_called_once()
        mock_inner.assert_called_once_with(vis, cancelled)
        assert "Config reload completed in" in caplog.text

    @patch("viseron.reload._reload_config")
    def test_reload_config_no_changes(
        self, mock_inner: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that reload_config logs no changes when diff has no changes."""
        vis = MagicMock()
        diff = ConfigDiff()
        expected = ReloadResult(success=True, diff=diff)
        mock_inner.return_value = expected

        with caplog.at_level("DEBUG", logger="viseron.reload"):
            result = reload_config(vis)

        assert result is expected
        vis.domain_registry.cancel_all_retries.assert_called_once()
        vis.initialized_event.wait.assert_called_once()
        assert "No configuration changes detected" in caplog.text

    @patch("viseron.reload._reload_config")
    def test_reload_config_result_error(
        self, mock_inner: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that reload_config logs an error when the reload fails."""
        vis = MagicMock()
        expected = ReloadResult(success=False)
        mock_inner.return_value = expected

        with caplog.at_level("DEBUG", logger="viseron.reload"):
            result = reload_config(vis)

        assert result is expected
        vis.domain_registry.cancel_all_retries.assert_called_once()
        vis.initialized_event.wait.assert_called_once()
        assert "Config reload failed with errors" in caplog.text
