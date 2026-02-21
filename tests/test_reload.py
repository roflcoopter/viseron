"""Test reload functionality."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch

from viseron.config import ComponentChange, ConfigDiff, DomainChange, IdentifierChange
from viseron.domain_registry import DomainEntry
from viseron.reload import (
    ReloadChanges,
    SetupPlan,
    _get_changes,
    _handle_added_components,
    _handle_modified_components,
    _handle_modified_identifiers,
    _handle_removed_components,
    _load_and_diff_config,
    _process_identifier_changes,
    _unload_domain_chain,
)

if TYPE_CHECKING:
    import pytest

    from viseron.types import SupportedDomains


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


class TestUnloadDomainChain:
    """Test _unload_domain_chain function."""

    @patch("viseron.reload.unload_domain")
    @patch("viseron.reload.get_unload_order", return_value=[])
    def test_empty_unload_order(
        self, mock_get_order: MagicMock, mock_unload: MagicMock
    ) -> None:
        """Test with no dependents to unload."""
        vis = MagicMock()
        entry = _make_domain_entry()
        plan = SetupPlan()

        _unload_domain_chain(vis, entry, plan)

        mock_get_order.assert_called_once_with(vis, "camera", "cam1")
        mock_unload.assert_not_called()
        assert plan.domain_components == set()

    @patch("viseron.reload.unload_domain")
    @patch("viseron.reload.get_unload_order")
    def test_single_entry_unloaded(
        self, mock_get_order: MagicMock, mock_unload: MagicMock
    ) -> None:
        """Test unloading a single domain entry."""
        vis = MagicMock()
        entry = _make_domain_entry()
        mock_get_order.return_value = [entry]
        plan = SetupPlan()

        _unload_domain_chain(vis, entry, plan)

        mock_unload.assert_called_once_with(vis, "camera", "cam1")
        assert plan.domain_components == {"ffmpeg"}

    @patch("viseron.reload.unload_domain")
    @patch("viseron.reload.get_unload_order")
    def test_multiple_entries_different_components(
        self, mock_get_order: MagicMock, mock_unload: MagicMock
    ) -> None:
        """Test unloading entries from different components."""
        vis = MagicMock()
        entry = _make_domain_entry()
        dependent = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        mock_get_order.return_value = [dependent, entry]
        plan = SetupPlan()

        _unload_domain_chain(vis, entry, plan)

        assert mock_unload.call_count == 2
        mock_unload.assert_has_calls(
            [
                call(vis, "object_detector", "cam1"),
                call(vis, "camera", "cam1"),
            ]
        )
        assert plan.domain_components == {"ffmpeg", "darknet"}

    @patch("viseron.reload.unload_domain")
    @patch("viseron.reload.get_unload_order")
    def test_multiple_entries_same_component(
        self, mock_get_order: MagicMock, mock_unload: MagicMock
    ) -> None:
        """Test that duplicate component names are deduplicated in the plan."""
        vis = MagicMock()
        entry1 = _make_domain_entry(identifier="cam1")
        entry2 = _make_domain_entry(identifier="cam2")
        mock_get_order.return_value = [entry1, entry2]
        plan = SetupPlan()

        _unload_domain_chain(vis, entry1, plan)

        assert mock_unload.call_count == 2
        assert plan.domain_components == {"ffmpeg"}

    @patch("viseron.reload.get_unload_order")
    def test_preserves_existing_plan_components(
        self,
        mock_get_order: MagicMock,
    ) -> None:
        """Test that existing domain_components in the plan are preserved."""
        vis = MagicMock()
        entry = _make_domain_entry()
        mock_get_order.return_value = [entry]
        plan = SetupPlan(domain_components={"existing_component"})

        with patch("viseron.reload.unload_domain"):
            _unload_domain_chain(vis, entry, plan)

        assert "existing_component" in plan.domain_components
        assert "ffmpeg" in plan.domain_components
        assert len(plan.domain_components) == 2

    @patch("viseron.reload.get_unload_order")
    def test_does_not_modify_plan_components(self, mock_get_order: MagicMock) -> None:
        """Test that plan.components (non-domain) is not modified."""
        vis = MagicMock()
        entry = _make_domain_entry()
        mock_get_order.return_value = [entry]
        plan = SetupPlan(components={"some_component"})
        with patch("viseron.reload.unload_domain"):
            _unload_domain_chain(vis, entry, plan)

        assert plan.components == {"some_component"}

    @patch("viseron.reload.unload_domain")
    @patch("viseron.reload.get_unload_order")
    def test_unload_called_in_order(
        self, mock_get_order: MagicMock, mock_unload: MagicMock
    ) -> None:
        """Test that unload_domain is called in the correct order."""
        vis = MagicMock()
        entry = _make_domain_entry()
        nvr_entry = _make_domain_entry(
            component_name="nvr", domain="nvr", identifier="cam1"
        )
        detector_entry = _make_domain_entry(
            component_name="darknet",
            domain="object_detector",
            identifier="cam1",
        )
        mock_get_order.return_value = [nvr_entry, detector_entry, entry]
        plan = SetupPlan()

        _unload_domain_chain(vis, entry, plan)

        assert mock_unload.call_args_list == [
            call(vis, "nvr", "cam1"),
            call(vis, "object_detector", "cam1"),
            call(vis, "camera", "cam1"),
        ]


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

    @patch("viseron.reload._get_changes")
    @patch("viseron.reload.diff_config")
    @patch("viseron.reload.load_config")
    def test_logs_no_changes(
        self,
        mock_load: MagicMock,
        mock_diff: MagicMock,
        mock_get_changes: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that a log message is emitted when no changes."""
        vis = MagicMock()
        vis.config = {}
        mock_load.return_value = {}
        mock_diff.return_value = ConfigDiff()  # has_changes is False
        mock_get_changes.return_value = ReloadChanges()

        with caplog.at_level("INFO", logger="viseron.reload"):
            _load_and_diff_config(vis)

        assert "No configuration changes detected" in caplog.text

    @patch("viseron.reload._get_changes")
    @patch("viseron.reload.diff_config")
    @patch("viseron.reload.load_config")
    def test_no_log_when_changes_exist(
        self,
        mock_load: MagicMock,
        mock_diff: MagicMock,
        mock_get_changes: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test no 'no changes' log when diff has changes."""
        vis = MagicMock()
        vis.config = {"old": {}}
        mock_load.return_value = {"new": {}}
        diff = ConfigDiff(
            component_changes={
                "new": ComponentChange(
                    component_name="new",
                    old_config=None,
                    new_config={},
                ),
            }
        )
        mock_diff.return_value = diff
        mock_get_changes.return_value = ReloadChanges()

        with caplog.at_level("INFO", logger="viseron.reload"):
            _load_and_diff_config(vis)

        assert "No configuration changes detected" not in caplog.text


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


class TestHandleModifiedIdentifiers:
    """Test _handle_modified_identifiers function."""

    @patch("viseron.reload._unload_domain_chain")
    def test_no_modified_identifiers(self, mock_chain: MagicMock) -> None:
        """Test with empty identifiers_to_reload."""
        vis = MagicMock()
        changes = ReloadChanges()
        plan = SetupPlan()

        _handle_modified_identifiers(vis, changes, plan)

        mock_chain.assert_not_called()
        assert plan.domain_components == set()

    @patch("viseron.reload._unload_domain_chain")
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
        mock_chain.assert_called_once_with(vis, entry, plan)

    @patch("viseron.reload._unload_domain_chain")
    def test_identifier_not_found_logs_error(
        self, mock_chain: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a missing identifier logs an error and does not unload."""
        vis = MagicMock()
        vis.domain_registry.get_by_identifier.return_value = None
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

        with caplog.at_level("ERROR", logger="viseron.reload"):
            _handle_modified_identifiers(vis, changes, plan)

        assert "ffmpeg" in plan.domain_components
        mock_chain.assert_not_called()
        assert "no matching domain found to unload" in caplog.text

    @patch("viseron.reload._unload_domain_chain")
    def test_multiple_identifiers_mixed(
        self, mock_chain: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
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

        with caplog.at_level("ERROR", logger="viseron.reload"):
            _handle_modified_identifiers(vis, changes, plan)

        assert plan.domain_components == {"darknet", "ffmpeg"}
        mock_chain.assert_called_once_with(vis, entry, plan)
        assert "cam2" in caplog.text
