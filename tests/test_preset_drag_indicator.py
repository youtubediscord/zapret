from __future__ import annotations

import inspect
import unittest

from ui.presets_menu import delegate as preset_delegate
from ui.presets_menu import view as preset_view


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


if __name__ == "__main__":
    unittest.main()
