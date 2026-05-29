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

    def test_drop_target_uses_lower_half_as_after_row(self) -> None:
        self.assertEqual(
            profile_list_view.profile_drop_target_for_position(4, "profile", y=109, row_top=100, row_height=20),
            {"marker": {"row": 4, "mode": "before"}, "destination_kind": "profile", "destination_row": 4},
        )
        self.assertEqual(
            profile_list_view.profile_drop_target_for_position(4, "profile", y=112, row_top=100, row_height=20),
            {"marker": {"row": 4, "mode": "after"}, "destination_kind": "profile_after", "destination_row": 4},
        )

    def test_adjacent_profile_gap_has_one_canonical_drop_target(self) -> None:
        lower_half_target = profile_list_view.profile_drop_target_for_position(
            4,
            "profile",
            y=112,
            row_top=100,
            row_height=20,
        )

        self.assertEqual(
            profile_list_view.profile_canonical_drop_target_for_next_row(
                lower_half_target,
                next_row=5,
                next_kind="profile",
            ),
            {"marker": {"row": 5, "mode": "before"}, "destination_kind": "profile", "destination_row": 5},
        )

    def test_view_supports_folder_drop_and_clears_marker(self) -> None:
        view_source = inspect.getsource(profile_list_view.ProfileListView)

        self.assertIn("profile_move_to_folder_requested", view_source)
        self.assertIn("set_drop_marker", view_source)
        self.assertIn("dragLeaveEvent", view_source)
        self.assertIn("self.set_drop_marker(-1, \"\")", view_source)

    def test_view_updates_only_drop_marker_rows(self) -> None:
        payload_source = inspect.getsource(profile_list_view.ProfileListView.set_drop_marker_payload)
        update_source = inspect.getsource(profile_list_view.ProfileListView._update_drop_marker_rows)

        self.assertIn("_update_drop_marker_rows", payload_source)
        self.assertNotIn("viewport().update()", payload_source)
        self.assertIn("viewport().update(rect", update_source)

    def test_view_sends_destination_group_with_row_drop(self) -> None:
        view_source = inspect.getsource(profile_list_view.ProfileListView)

        self.assertIn("profile_move_requested = pyqtSignal(str, str, str)", view_source)
        self.assertIn("profile_move_after_requested = pyqtSignal(str, str, str)", view_source)
        self.assertIn("ProfileListModel.GroupRole", view_source)
        self.assertIn("destination_group_key", view_source)

    def test_delegate_draws_folder_and_before_row_drop_markers(self) -> None:
        delegate_source = inspect.getsource(profile_list_delegate.ProfileListDelegate)

        self.assertIn("_paint_drop_marker", delegate_source)
        self.assertIn('marker.get("mode") == "folder"', delegate_source)
        self.assertIn('marker.get("mode") == "before"', delegate_source)
        self.assertIn('marker.get("mode") == "after"', delegate_source)


if __name__ == "__main__":
    unittest.main()
