from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from profile.state import ProfileListItem


def _item(name: str, *, key: str, in_preset: bool = True, profile_index: int = 0) -> ProfileListItem:
    return ProfileListItem(
        key=key,
        persistent_key=key,
        profile_index=profile_index,
        display_name=name,
        enabled=True,
        in_preset=in_preset,
        strategy_id="pass",
        strategy_name="pass",
        match_lines=("--filter-tcp=443", f"--hostlist=lists/{name.lower()}.txt"),
        list_type="hostlist",
        rating="",
        favorite=False,
        group="youtube",
        group_name="YouTube",
        order=profile_index,
        profile_name=name,
    )


class ProfileOrderPageTests(unittest.TestCase):
    def test_order_model_is_flat_and_keeps_only_real_preset_profiles(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((_item("YouTube", key="profile:0", profile_index=0), _item("Missing", key="template:0", in_preset=False)))

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.index(0, 0).data(ProfileListModel.KindRole), "profile")
        self.assertEqual(model.index(0, 0).data(ProfileListModel.ProfileKeyRole), "profile:0")
        self.assertEqual(model.index(0, 0).data(ProfileListModel.DisplayNameRole), "YouTube")

    def test_order_model_returns_icon_roles_from_profile_icon_spec(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((_item("YouTube", key="profile:0", profile_index=0),))

        index = model.index(0, 0)

        self.assertEqual(index.data(ProfileListModel.IconNameRole), "simple:youtube:YT")
        self.assertEqual(index.data(ProfileListModel.IconColorRole), "#FF0000")

    def test_order_model_can_move_profile_locally(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((
            _item("A", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
            _item("C", key="profile:c", profile_index=2),
        ))

        self.assertTrue(model.move_profile("profile:c", "before", "profile:a"))
        self.assertEqual(
            [model.index(row, 0).data(ProfileListModel.ProfileKeyRole) for row in range(model.rowCount())],
            ["profile:c", "profile:a", "profile:b"],
        )

    def test_order_model_moves_profile_without_full_reset(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((
            _item("A", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
            _item("C", key="profile:c", profile_index=2),
        ))
        model.beginResetModel = Mock(side_effect=AssertionError("profile order move must not reset the whole model"))

        self.assertTrue(model.move_profile("profile:a", "after", "profile:c"))

        self.assertEqual(
            [model.index(row, 0).data(ProfileListModel.ProfileKeyRole) for row in range(model.rowCount())],
            ["profile:b", "profile:c", "profile:a"],
        )

    def test_order_model_skips_reset_when_profiles_are_unchanged(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((
            _item("A", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
        ))
        model.beginResetModel = Mock(side_effect=AssertionError("unchanged profile order payload must not reset the whole model"))
        model.endResetModel = Mock(side_effect=AssertionError("unchanged profile order payload must not reset the whole model"))

        model.set_profiles((
            _item("A", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
        ))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(
            [model.index(row, 0).data(ProfileListModel.ProfileKeyRole) for row in range(model.rowCount())],
            ["profile:a", "profile:b"],
        )

    def test_order_model_updates_stable_rows_without_full_reset(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileOrderListModel()
        model.set_profiles((
            _item("A", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
        ))
        model.beginResetModel = Mock(side_effect=AssertionError("stable profile order rows must not reset the whole model"))

        model.set_profiles((
            _item("A updated", key="profile:a", profile_index=0),
            _item("B", key="profile:b", profile_index=1),
        ))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(0, 0).data(ProfileListModel.ProfileKeyRole), "profile:a")
        self.assertEqual(model.index(0, 0).data(ProfileListModel.DisplayNameRole), "A updated")

    def test_order_page_explains_priority_and_uses_order_workers(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        build_source = inspect.getsource(ProfileOrderPageBase._build_content)
        load_source = inspect.getsource(ProfileOrderPageBase._reload_order_profiles)
        before_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_requested)
        after_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_after_requested)
        end_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_to_end_requested)

        self.assertIn("Profile выше в списке имеет больший приоритет", build_source)
        self.assertIn("create_profile_order_load_worker", load_source)
        self.assertIn("_request_profile_order_move", before_source)
        self.assertIn("_request_profile_order_move", after_source)
        self.assertIn("_request_profile_order_move", end_source)
        self.assertNotIn("list_preset_order_profiles", load_source)
        self.assertNotIn("move_preset_profile_before", before_source)
        self.assertNotIn("move_preset_profile_after", after_source)
        self.assertNotIn("move_preset_profile_to_end", end_source)

    def test_order_page_updates_visible_list_locally_after_move_worker(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderList
        from profile.ui.profile_order_page import ProfileOrderPageBase

        moved_source = inspect.getsource(ProfileOrderPageBase._on_profile_order_moved)
        local_source = inspect.getsource(ProfileOrderPageBase._apply_profile_order_move_locally)
        list_source = inspect.getsource(ProfileOrderList)

        self.assertIn("_apply_profile_order_move_locally", moved_source)
        self.assertIn("_reload_order_profiles", moved_source)
        self.assertLess(moved_source.index("_apply_profile_order_move_locally"), moved_source.index("_reload_order_profiles"))
        self.assertIn("move_profile_item", list_source)
        self.assertIn("move_profile_item", local_source)

    def test_order_page_starts_workers_without_direct_profile_calls(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.loaded = _Signal()
                self.moved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page.launch_method = "zapret2_mode"
        page._order_load_worker = None
        page._order_load_request_id = 0
        page._order_move_worker = None
        page._order_move_request_id = 0
        load_worker = _Worker()
        move_worker = _Worker()
        page._create_profile_order_load_worker = Mock(return_value=load_worker)
        page._create_profile_order_move_worker = Mock(return_value=move_worker)

        ProfileOrderPageBase._reload_order_profiles(page)
        ProfileOrderPageBase._on_profile_move_requested(page, "profile-1", "profile-2")

        page._create_profile_order_load_worker.assert_called_once_with(1, "zapret2_mode", page)
        page._create_profile_order_move_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="before",
            source_profile_key="profile-1",
            destination_profile_key="profile-2",
            parent=page,
        )
        load_worker.start.assert_called_once()
        move_worker.start.assert_called_once()

    def test_order_page_receives_worker_factories_instead_of_profile_feature(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.page_deps.presets import build_profile_order_page_kwargs
        from ui.navigation_pages import PageName

        init_source = inspect.getsource(ProfileOrderPageBase.__init__)
        page_source = inspect.getsource(ProfileOrderPageBase)

        self.assertIn("create_profile_order_load_worker", init_source)
        self.assertIn("create_preset_profile_order_move_worker", init_source)
        self.assertNotIn("profile_feature", init_source)
        self.assertNotIn("self._profile", page_source)

        profile_feature = Mock()
        kwargs = build_profile_order_page_kwargs(
            page_name=PageName.ZAPRET2_PROFILE_ORDER,
            profile_feature=profile_feature,
            show_page=Mock(),
        )

        self.assertIs(kwargs["create_profile_order_load_worker"], profile_feature.create_profile_order_load_worker)
        self.assertIs(
            kwargs["create_preset_profile_order_move_worker"],
            profile_feature.create_preset_profile_order_move_worker,
        )
        self.assertNotIn("profile_feature", kwargs)

    def test_order_page_invalidates_running_load_before_refresh_after_move(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        class _RunningWorker:
            def isRunning(self) -> bool:
                return True

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_load_worker = _RunningWorker()
        page._order_load_request_id = 7
        page._order_load_dirty = False
        page._create_profile_order_load_worker = Mock()
        page._payload = "current"

        ProfileOrderPageBase._reload_order_profiles(page, force=True)
        ProfileOrderPageBase._on_order_profiles_loaded(page, 7, "stale")

        self.assertEqual(page._order_load_request_id, 8)
        self.assertTrue(page._order_load_dirty)
        page._create_profile_order_load_worker.assert_not_called()
        self.assertEqual(page._payload, "current")

    def test_order_page_cleanup_stops_order_workers(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        class _Worker:
            def __init__(self) -> None:
                self.quit = Mock()

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        load_worker = _Worker()
        move_worker = _Worker()
        page._order_load_worker = load_worker
        page._order_move_worker = move_worker
        page._order_load_request_id = 3
        page._order_move_request_id = 5
        page._order_load_dirty = True

        ProfileOrderPageBase.cleanup(page)

        load_worker.quit.assert_called_once()
        move_worker.quit.assert_called_once()
        self.assertIsNone(page._order_load_worker)
        self.assertIsNone(page._order_move_worker)
        self.assertEqual(page._order_load_request_id, 4)
        self.assertEqual(page._order_move_request_id, 6)
        self.assertFalse(page._order_load_dirty)

    def test_order_workers_call_profile_service(self) -> None:
        from profile.profile_order_loader import ProfileOrderListLoadWorker, ProfilePresetOrderMoveWorker

        load_profiles = Mock(return_value=SimpleNamespace(items=()))
        load_worker = ProfileOrderListLoadWorker(2, load_profiles)
        loaded = []
        load_worker.loaded.connect(lambda request_id, payload: loaded.append((request_id, payload)))

        load_worker.run()

        load_profiles.assert_called_once_with()
        self.assertEqual(loaded, [(2, load_profiles.return_value)])

        move_before = Mock(return_value="profile-1")
        move_after = Mock()
        move_to_end = Mock()
        move_worker = ProfilePresetOrderMoveWorker(
            3,
            move_before,
            move_after,
            move_to_end,
            action="before",
            source_profile_key="profile-1",
            destination_profile_key="profile-2",
        )
        moved = []
        move_worker.moved.connect(
            lambda request_id, action, source_key, destination_key, result: moved.append((
                request_id,
                action,
                source_key,
                destination_key,
                result,
            ))
        )

        move_worker.run()

        move_before.assert_called_once_with("profile-1", "profile-2")
        self.assertEqual(moved, [(3, "before", "profile-1", "profile-2", "profile-1")])

    def test_order_page_has_breadcrumbs_back_to_profiles_and_control(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        build_source = inspect.getsource(ProfileOrderPageBase._build_content)
        breadcrumb_source = inspect.getsource(ProfileOrderPageBase._rebuild_breadcrumb)
        handler_source = inspect.getsource(ProfileOrderPageBase._on_breadcrumb_item_changed)

        self.assertIn("BreadcrumbBar", build_source)
        self.assertIn('"profiles"', breadcrumb_source)
        self.assertIn('"order"', breadcrumb_source)
        self.assertIn("_open_profiles()", handler_source)
        self.assertIn("_open_root()", handler_source)

    def test_order_list_does_not_expose_context_or_folder_actions(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderList

        source = inspect.getsource(ProfileOrderList)

        self.assertNotIn("profile_context_requested", source)
        self.assertNotIn("folder_context_requested", source)
        self.assertNotIn("folder_toggled", source)


if __name__ == "__main__":
    unittest.main()
