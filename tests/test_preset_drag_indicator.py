from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock

from ui.presets_menu import delegate as preset_delegate
from ui.presets_menu import common as preset_common
from ui.presets_menu.model import PresetListModel
from ui.presets_menu import view as preset_view
from presets.ui.common.user_presets_page import UserPresetsPageBase


class PresetDragIndicatorTests(unittest.TestCase):
    def test_drop_marker_maps_targets_to_clear_visual_modes(self) -> None:
        self.assertEqual(
            preset_view.preset_drop_marker_for_target(2, "folder"),
            {"row": 2, "mode": "folder"},
        )
        self.assertEqual(
            preset_view.preset_drop_marker_for_target(4, "preset"),
            {"row": 4, "mode": "before"},
        )
        self.assertEqual(
            preset_view.preset_drop_marker_for_target(-1, "empty"),
            {"row": -1, "mode": ""},
        )

    def test_drop_target_uses_lower_half_as_after_row(self) -> None:
        self.assertEqual(
            preset_view.preset_drop_target_for_position(4, "preset", y=109, row_top=100, row_height=20),
            {"marker": {"row": 4, "mode": "before"}, "destination_kind": "preset", "destination_row": 4},
        )
        self.assertEqual(
            preset_view.preset_drop_target_for_position(4, "preset", y=112, row_top=100, row_height=20),
            {"marker": {"row": 4, "mode": "after"}, "destination_kind": "preset_after", "destination_row": 4},
        )

    def test_adjacent_preset_gap_has_one_canonical_drop_target(self) -> None:
        lower_half_target = preset_view.preset_drop_target_for_position(
            4,
            "preset",
            y=112,
            row_top=100,
            row_height=20,
        )

        self.assertEqual(
            preset_common.preset_canonical_drop_target_for_next_row(
                lower_half_target,
                next_row=5,
                next_kind="preset",
            ),
            {"marker": {"row": 5, "mode": "before"}, "destination_kind": "preset", "destination_row": 5},
        )

    def test_view_clears_drop_marker_when_drag_finishes_or_leaves(self) -> None:
        view_source = inspect.getsource(preset_view.LinkedWheelListView)

        self.assertIn("set_drop_marker", view_source)
        self.assertIn("dragLeaveEvent", view_source)
        self.assertIn("self.set_drop_marker(-1, \"\")", view_source)

    def test_view_sends_destination_folder_with_drop(self) -> None:
        view_source = inspect.getsource(preset_view.LinkedWheelListView)

        self.assertIn("item_dropped = pyqtSignal(str, str, str, str, str)", view_source)
        self.assertIn("PresetListModel.FolderKeyRole", view_source)
        self.assertIn("destination_folder_key", view_source)
        self.assertIn(
            "self.item_dropped.emit(source_kind, source_id, destination_kind, destination_id, destination_folder_key)",
            view_source,
        )

    def test_delegate_draws_folder_and_before_row_drop_markers(self) -> None:
        delegate_source = inspect.getsource(preset_delegate.PresetListDelegate)

        self.assertIn("_paint_drop_marker", delegate_source)
        self.assertIn('marker.get("mode") == "folder"', delegate_source)
        self.assertIn('marker.get("mode") == "before"', delegate_source)
        self.assertIn('marker.get("mode") == "after"', delegate_source)
        self.assertIn("drag_marker_visible", delegate_source)
        self.assertIn("active=is_active and not drag_marker_visible", delegate_source)
        self.assertIn("show_active_marker=False", delegate_source)

    def test_delegate_action_updates_only_affected_preset_row(self) -> None:
        click_source = inspect.getsource(preset_delegate.PresetListDelegate._handle_action_click)
        clear_source = inspect.getsource(preset_delegate.PresetListDelegate._clear_pending_destructive)
        shake_source = inspect.getsource(preset_delegate.PresetListDelegate._advance_pending_shake)

        self.assertIn("_update_preset_row_view", click_source)
        self.assertIn("_update_pending_destructive_row", clear_source)
        self.assertIn("_update_pending_destructive_row", shake_source)
        self.assertNotIn("viewport().update()", click_source)
        self.assertNotIn("viewport().update()", clear_source)
        self.assertNotIn("viewport().update()", shake_source)

    def test_model_moves_preset_row_without_full_reload(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "folder", "folder_key": "common", "name": "Общие", "count": 1, "is_collapsed": False},
                {"kind": "preset", "file_name": "A.txt", "name": "A", "folder_key": "common"},
                {"kind": "folder", "folder_key": "game-filter", "name": "Game filter", "count": 1, "is_collapsed": False},
                {"kind": "preset", "file_name": "B.txt", "name": "B", "folder_key": "game-filter"},
            ]
        )
        model.beginResetModel = Mock(side_effect=AssertionError("move must not reset the whole preset list"))

        self.assertTrue(model.move_preset("A.txt", "preset_after", "B.txt", "game-filter"))

        rows = [
            (
                model.index(row, 0).data(PresetListModel.KindRole),
                model.index(row, 0).data(PresetListModel.FolderKeyRole),
                model.index(row, 0).data(PresetListModel.FileNameRole),
                model.index(row, 0).data(PresetListModel.CountRole),
            )
            for row in range(model.rowCount())
        ]

        self.assertIn(("preset", "game-filter", "A.txt", 0), rows)
        self.assertNotIn(("preset", "common", "A.txt", 0), rows)
        self.assertIn(("folder", "common", "", 0), rows)
        self.assertIn(("folder", "game-filter", "", 2), rows)

    def test_model_keeps_folder_count_when_preset_moves_inside_same_folder(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "folder", "folder_key": "common", "name": "Общие", "count": 2, "is_collapsed": False},
                {"kind": "preset", "file_name": "A.txt", "name": "A", "folder_key": "common"},
                {"kind": "preset", "file_name": "B.txt", "name": "B", "folder_key": "common"},
            ]
        )
        model.beginResetModel = Mock(side_effect=AssertionError("move must not reset the whole preset list"))

        self.assertTrue(model.move_preset("A.txt", "preset_after", "B.txt", "common"))

        self.assertEqual(model.index(0, 0).data(PresetListModel.CountRole), 2)

    def test_local_preset_move_preserves_scroll_position(self) -> None:
        move_source = inspect.getsource(UserPresetsPageBase._apply_preset_move_locally)

        self.assertIn("capture_presets_view_state", move_source)
        self.assertIn("restore_presets_view_state", move_source)
        self.assertNotIn("ensure_preset_list_current_index", move_source)


if __name__ == "__main__":
    unittest.main()
