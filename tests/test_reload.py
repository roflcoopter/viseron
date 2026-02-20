"""Test reload functionality."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call, patch

from viseron.config import IdentifierChange
from viseron.domain_registry import DomainEntry
from viseron.reload import SetupPlan, _process_identifier_changes, _unload_domain_chain

if TYPE_CHECKING:
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
        assert result == []

    def test_no_changes_identical_configs(self) -> None:
        """Test with identical old and new configs."""
        config: dict[str, Any] = {
            "cam1": {"host": "192.168.1.1"},
            "cam2": {"host": "192.168.1.2"},
        }
        result = _process_identifier_changes("ffmpeg", "camera", config, config.copy())
        assert result == []

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
