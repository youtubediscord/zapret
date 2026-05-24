from __future__ import annotations

import inspect
import unittest

from profile.ui import profile_list_delegate, profile_list_view


class ProfileDragIndicatorTests(unittest.TestCase):
    def test_drop_marker_maps_targets_to_clear_visual_modes(self) -> None:
        self.assertEqual(
            profile_list_view.profile_drop_marker_for_target(2, "folder"),
            {"row": 2, "mode": "folder"},
        )
        self.assertEqual(
            profile_list_view.profile_drop_marker_for_target(4, "profile"),
            {"row": 4, "mode": "before"},
        )
        self.assertEqual(
            profile_list_view.profile_drop_marker_for_target(-1, ""),
            {"row": -1, "mode": ""},
        )

    def test_view_supports_folder_drop_and_clears_marker(self) -> None:
        view_source = inspect.getsource(profile_list_view.ProfileListView)

        self.assertIn("profile_move_to_folder_requested", view_source)
        self.assertIn("set_drop_marker", view_source)
        self.assertIn("dragLeaveEvent", view_source)
        self.assertIn("self.set_drop_marker(-1, \"\")", view_source)

    def test_delegate_draws_folder_and_before_row_drop_markers(self) -> None:
        delegate_source = inspect.getsource(profile_list_delegate.ProfileListDelegate)

        self.assertIn("_paint_drop_marker", delegate_source)
        self.assertIn('marker.get("mode") == "folder"', delegate_source)
        self.assertIn('marker.get("mode") == "before"', delegate_source)


if __name__ == "__main__":
    unittest.main()
