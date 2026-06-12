from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

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
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

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

    def test_order_list_has_screen_reader_name_and_keyboard_help(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderList

        order_list = ProfileOrderList()
        self.addCleanup(order_list.deleteLater)

        self.assertEqual(order_list.accessibleName(), "Порядок profile")
        self.assertIn("PageUp и PageDown", order_list.accessibleDescription())
        self.assertEqual(order_list._view.accessibleName(), "Порядок profile: список пока загружается")
        self.assertEqual(
            order_list._view.property("screenReaderStateText"),
            "Порядок profile: список пока загружается",
        )
        self.assertIn("меняют порядок выбранного profile", order_list._view.accessibleDescription())

    def test_order_list_moves_selected_profile_from_keyboard(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderList

        order_list = ProfileOrderList()
        self.addCleanup(order_list.deleteLater)
        order_list._model.set_profiles(
            (
                _item("A", key="profile:a", profile_index=0),
                _item("B", key="profile:b", profile_index=1),
            )
        )
        order_list._view.setCurrentIndex(order_list._model.index(1, 0))
        requested: list[tuple[str, str]] = []
        order_list.profile_move_requested.connect(lambda source, destination: requested.append((source, destination)))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, int(Qt.Key.Key_PageUp), Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(order_list._view, event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(requested, [("profile:b", "profile:a")])

    def test_order_page_explains_priority_and_uses_order_workers(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        build_source = inspect.getsource(ProfileOrderPageBase._build_content)
        load_source = inspect.getsource(ProfileOrderPageBase._reload_order_profiles)
        move_request_source = inspect.getsource(ProfileOrderPageBase._request_profile_order_move)
        move_start_source = inspect.getsource(ProfileOrderPageBase._start_profile_order_move_worker)
        before_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_requested)
        after_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_after_requested)
        end_source = inspect.getsource(ProfileOrderPageBase._on_profile_move_to_end_requested)
        init_source = inspect.getsource(ProfileOrderPageBase.__init__)

        self.assertIn("Profile выше в списке имеет больший приоритет", build_source)
        self.assertIn("create_profile_order_load_worker", load_source)
        self.assertIn("OneShotWorkerRuntime", init_source)
        self.assertIn("_order_load_runtime", init_source)
        self.assertIn("_order_move_runtime", init_source)
        self.assertIn("start_qthread_worker", load_source)
        self.assertIn("_start_profile_order_move_worker", move_request_source)
        self.assertIn("start_qthread_worker", move_start_source)
        self.assertNotIn("worker.start()", load_source)
        self.assertNotIn("worker.start()", move_request_source)
        self.assertNotIn("worker.start()", move_start_source)
        self.assertIn("_request_profile_order_move", before_source)
        self.assertIn("_request_profile_order_move", after_source)
        self.assertIn("_request_profile_order_move", end_source)
        self.assertNotIn("list_preset_order_profiles", load_source)
        self.assertNotIn("move_preset_profile_before", before_source)
        self.assertNotIn("move_preset_profile_after", after_source)
        self.assertNotIn("move_preset_profile_to_end", end_source)

    def test_order_page_repeat_activation_skips_clean_payload_reload(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_payload_loaded_once = True
        page._order_payload_dirty = False
        page._reload_order_profiles = Mock()

        ProfileOrderPageBase.on_page_activated(page)

        page._reload_order_profiles.assert_not_called()

    def test_order_page_clean_activation_restores_heavy_list_after_show(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        class _List:
            def __init__(self) -> None:
                self.visible_calls: list[bool] = []

            def setVisible(self, value: bool) -> None:  # noqa: N802
                self.visible_calls.append(bool(value))

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        order_list = _List()
        page._order_list = order_list
        page._order_payload_loaded_once = True
        page._order_payload_dirty = False
        page._order_list_show_scheduled = False
        page._cleanup_in_progress = False
        page._reload_order_profiles = Mock(
            side_effect=AssertionError("clean order activation must not reload payload")
        )
        scheduled: list[object] = []

        with patch(
            "profile.ui.profile_order_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled.append(callback),
        ):
            ProfileOrderPageBase.on_page_hidden(page)
            ProfileOrderPageBase.on_page_activated(page)

        self.assertEqual(order_list.visible_calls, [False])
        page._reload_order_profiles.assert_not_called()
        self.assertEqual(len(scheduled), 1)

        scheduled[0]()

        self.assertEqual(order_list.visible_calls, [False, True])

    def test_order_page_ui_state_change_marks_payload_dirty(self) -> None:
        from app.state_store import MainWindowStateStore
        from profile.ui.profile_order_page import ProfileOrderPageBase

        store = MainWindowStateStore()
        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._ui_state_store = None
        page._ui_state_unsubscribe = None
        page._cleanup_in_progress = False
        page._order_payload_dirty = False
        page.isVisible = Mock(return_value=False)

        ProfileOrderPageBase.bind_ui_state_store(page, store)
        store.bump_preset_content_revision()

        self.assertTrue(page._order_payload_dirty)

    def test_order_page_updates_visible_list_locally_after_move_worker(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderList
        from profile.ui.profile_order_page import ProfileOrderPageBase

        moved_source = inspect.getsource(ProfileOrderPageBase._on_profile_order_moved)
        local_source = inspect.getsource(ProfileOrderPageBase._apply_profile_order_move_locally)
        list_source = inspect.getsource(ProfileOrderList)

        self.assertIn("_apply_profile_order_move_locally", moved_source)
        self.assertIn("_reload_order_profiles", moved_source)
        self.assertLess(moved_source.index("_apply_profile_order_move_locally"), moved_source.rindex("_reload_order_profiles"))
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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page.launch_method = "zapret2_mode"
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_load_dirty = False
        page._cleanup_in_progress = False
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
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _RunningWorker:
            def isRunning(self) -> bool:
                return True

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_runtime.worker = _RunningWorker()
        page._order_load_runtime.request_id = 7
        page._order_load_dirty = False
        page._create_profile_order_load_worker = Mock()
        page._payload = "current"
        page._cleanup_in_progress = False
        callbacks = []

        ProfileOrderPageBase._reload_order_profiles(page, force=True)
        ProfileOrderPageBase._on_order_profiles_loaded(page, 7, "stale")

        self.assertEqual(page._order_load_runtime.request_id, 8)
        self.assertTrue(page._order_load_dirty)
        page._create_profile_order_load_worker.assert_not_called()
        self.assertEqual(page._payload, "current")

        page._order_load_runtime.worker = None
        with patch(
            "profile.ui.profile_order_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileOrderPageBase._on_order_profiles_worker_finished(page, object())

        page._create_profile_order_load_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_profile_order_load_worker.assert_called_once_with(9, "zapret2_mode", page)

    def test_order_page_reload_waits_while_restart_is_scheduled(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_dirty = True
        page._order_load_restart_scheduled = True
        page._create_profile_order_load_worker = Mock()

        ProfileOrderPageBase._reload_order_profiles(page, force=True)

        page._create_profile_order_load_worker.assert_not_called()
        self.assertTrue(page._order_load_dirty)

    def test_stale_order_load_worker_finished_does_not_schedule_reload(self) -> None:
        import profile.ui.profile_order_page as order_page
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_runtime.request_id = 5
        page._order_load_dirty = True
        page._schedule_order_profiles_reload = Mock(
            side_effect=AssertionError("stale profile order load worker must not restart reload")
        )

        with patch.object(order_page, "QTimer") as timer_mock:
            ProfileOrderPageBase._on_order_profiles_worker_finished(
                page,
                SimpleNamespace(_request_id=4),
            )

        timer_mock.singleShot.assert_not_called()
        self.assertTrue(page._order_load_dirty)
        page._schedule_order_profiles_reload.assert_not_called()

    def test_order_page_defers_list_apply_after_load_worker_signal(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        payload = SimpleNamespace(items=(_item("A", key="profile:a"),))
        callbacks = []
        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_runtime.request_id = 3
        page._cleanup_in_progress = False
        page._payload = None
        page._order_list = Mock()
        page._rebuild_breadcrumb = Mock()

        with patch(
            "profile.ui.profile_order_page.QTimer",
            SimpleNamespace(singleShot=lambda _delay, callback: callbacks.append(callback)),
            create=True,
        ):
            ProfileOrderPageBase._on_order_profiles_loaded(page, 3, payload)

        page._order_list.set_profiles.assert_not_called()
        page._rebuild_breadcrumb.assert_not_called()
        self.assertIs(page._payload, payload)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._order_list.set_profiles.assert_called_once_with(payload.items)
        page._rebuild_breadcrumb.assert_called_once_with()

    def test_pending_order_payload_apply_is_ignored_after_reload_is_requested(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _RunningWorker:
            def isRunning(self) -> bool:
                return True

        payload = SimpleNamespace(items=(_item("Old", key="profile:old"),))
        callbacks = []
        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page.launch_method = "zapret2_mode"
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_runtime.worker = _RunningWorker()
        page._order_load_runtime.request_id = 3
        page._cleanup_in_progress = False
        page._order_load_dirty = False
        page._order_load_restart_scheduled = False
        page._order_payload_apply_scheduled = False
        page._pending_order_payload_apply = None
        page._order_list = Mock()
        page._rebuild_breadcrumb = Mock()

        with patch(
            "profile.ui.profile_order_page.QTimer",
            SimpleNamespace(singleShot=lambda _delay, callback: callbacks.append(callback)),
            create=True,
        ):
            ProfileOrderPageBase._on_order_profiles_loaded(page, 3, payload)

        ProfileOrderPageBase._reload_order_profiles(page, force=True)

        self.assertTrue(page._order_load_dirty)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._order_list.set_profiles.assert_not_called()
        page._rebuild_breadcrumb.assert_not_called()

    def test_order_page_replays_queued_moves_after_running_move_worker_finishes(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _RunningWorker:
            def isRunning(self) -> bool:
                return True

            def quit(self) -> None:
                pass

        class _Worker:
            def __init__(self) -> None:
                self.moved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page.launch_method = "zapret2_mode"
        page._cleanup_in_progress = False
        page._order_move_runtime = OneShotWorkerRuntime()
        running_worker = _RunningWorker()
        page._order_move_runtime.worker = running_worker
        page._order_move_runtime.request_id = 4
        page._pending_profile_order_moves = []
        next_worker = _Worker()
        page._create_profile_order_move_worker = Mock(return_value=next_worker)

        ProfileOrderPageBase._request_profile_order_move(
            page,
            "after",
            "profile-a",
            destination_profile_key="profile-b",
        )
        ProfileOrderPageBase._request_profile_order_move(
            page,
            "end",
            "profile-c",
        )

        page._create_profile_order_move_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-b",
                },
                {
                    "action": "end",
                    "source_profile_key": "profile-c",
                    "destination_profile_key": "",
                },
            ],
        )

        page._order_move_runtime.worker = None
        callbacks = []
        with patch(
            "profile.ui.profile_order_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileOrderPageBase._on_profile_order_move_worker_finished(page, running_worker)

        page._create_profile_order_move_worker.assert_not_called()
        next_worker.start.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_profile_order_move_worker.assert_called_once_with(
            5,
            "zapret2_mode",
            action="after",
            source_profile_key="profile-a",
            destination_profile_key="profile-b",
            parent=page,
        )
        next_worker.start.assert_called_once()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "end",
                    "source_profile_key": "profile-c",
                    "destination_profile_key": "",
                }
            ],
        )

    def test_stale_profile_order_move_worker_finished_does_not_start_pending_move(self) -> None:
        import profile.ui.profile_order_page as order_page
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_move_runtime.request_id = 5
        page._pending_profile_order_moves = [
            {
                "action": "after",
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
            }
        ]
        page._schedule_next_profile_order_move_start = Mock(
            side_effect=AssertionError("stale profile order move worker must not drive pending queue")
        )

        with patch.object(order_page, "QTimer") as timer_mock:
            ProfileOrderPageBase._on_profile_order_move_worker_finished(
                page,
                SimpleNamespace(_request_id=4),
            )

        timer_mock.singleShot.assert_not_called()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-b",
                }
            ],
        )

    def test_stale_profile_order_move_worker_object_does_not_start_pending_move(self) -> None:
        import profile.ui.profile_order_page as order_page
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_move_runtime.worker = object()
        page._pending_profile_order_moves = [
            {
                "action": "after",
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
            }
        ]
        page._schedule_next_profile_order_move_start = Mock(
            side_effect=AssertionError("stale profile order move worker must not drive pending queue")
        )

        with patch.object(order_page, "QTimer") as timer_mock:
            ProfileOrderPageBase._on_profile_order_move_worker_finished(page, object())

        timer_mock.singleShot.assert_not_called()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-b",
                }
            ],
        )

    def test_order_page_move_error_ignored_when_new_move_is_pending(self) -> None:
        import profile.ui.profile_order_page as order_page
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_move_runtime.request_id = 4
        page._cleanup_in_progress = False
        page._pending_profile_order_moves = [
            {
                "action": "before",
                "source_profile_key": "profile-b",
                "destination_profile_key": "profile-a",
            }
        ]
        page._order_move_reload_required = True
        page._reload_order_profiles = Mock()
        page.window = Mock(return_value=object())

        with patch.object(order_page, "log") as log_mock, patch.object(order_page.InfoBar, "error") as error_mock:
            ProfileOrderPageBase._on_profile_order_move_failed(page, 4, "stale error")

        log_mock.assert_not_called()
        error_mock.assert_not_called()
        page._reload_order_profiles.assert_not_called()
        self.assertTrue(page._order_move_reload_required)

    def test_order_page_replaces_pending_move_for_same_profile(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _RunningWorker:
            def isRunning(self) -> bool:
                return True

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_move_runtime.worker = _RunningWorker()
        page._pending_profile_order_moves = []
        page._create_profile_order_move_worker = Mock()

        ProfileOrderPageBase._request_profile_order_move(
            page,
            "before",
            "profile-a",
            destination_profile_key="profile-b",
        )
        ProfileOrderPageBase._request_profile_order_move(
            page,
            "after",
            "profile-a",
            destination_profile_key="profile-c",
        )

        page._create_profile_order_move_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-c",
                },
            ],
        )

    def test_order_page_applies_move_locally_even_when_new_move_is_pending(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_move_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._order_move_reload_required = False
        page._pending_profile_order_moves = [
            {
                "action": "end",
                "source_profile_key": "profile-c",
                "destination_profile_key": "",
            }
        ]
        page._apply_profile_order_move_locally = Mock(return_value=True)
        page._reload_order_profiles = Mock()

        ProfileOrderPageBase._on_profile_order_moved(
            page,
            4,
            "after",
            "profile-a",
            "profile-b",
            True,
        )

        page._apply_profile_order_move_locally.assert_called_once_with(
            "after",
            "profile-a",
            destination_profile_key="profile-b",
        )
        self.assertFalse(page._order_move_reload_required)
        page._reload_order_profiles.assert_not_called()

    def test_order_page_reloads_after_queue_when_pending_move_cannot_apply_locally(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._cleanup_in_progress = False
        page._order_move_runtime = SimpleNamespace(is_current=Mock(return_value=True))
        page._pending_profile_order_moves = [
            {
                "action": "end",
                "source_profile_key": "profile-c",
                "destination_profile_key": "",
            }
        ]
        page._apply_profile_order_move_locally = Mock(return_value=False)
        page._reload_order_profiles = Mock()

        ProfileOrderPageBase._on_profile_order_moved(
            page,
            4,
            "after",
            "profile-a",
            "profile-b",
            True,
        )

        page._apply_profile_order_move_locally.assert_called_once_with(
            "after",
            "profile-a",
            destination_profile_key="profile-b",
        )
        page._pending_profile_order_moves = []
        ProfileOrderPageBase._on_profile_order_moved(
            page,
            5,
            "end",
            "profile-c",
            "",
            True,
        )

        page._reload_order_profiles.assert_called_once_with(force=True)

    def test_profile_order_move_waits_while_restart_is_scheduled(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _Worker:
            def __init__(self) -> None:
                self.moved = Mock(connect=Mock())
                self.failed = Mock(connect=Mock())
                self.finished = Mock(connect=Mock())
                self.start = Mock()
                self.deleteLater = Mock()

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page.launch_method = "zapret2_mode"
        page._cleanup_in_progress = False
        page._order_move_runtime = OneShotWorkerRuntime()
        page._pending_profile_order_moves = [
            {
                "action": "after",
                "source_profile_key": "profile-a",
                "destination_profile_key": "profile-b",
            }
        ]
        page._order_move_start_scheduled = True
        next_worker = _Worker()
        page._create_profile_order_move_worker = Mock(return_value=next_worker)

        ProfileOrderPageBase._request_profile_order_move(page, "end", "profile-c")

        page._create_profile_order_move_worker.assert_not_called()
        next_worker.start.assert_not_called()
        self.assertEqual(
            page._pending_profile_order_moves,
            [
                {
                    "action": "after",
                    "source_profile_key": "profile-a",
                    "destination_profile_key": "profile-b",
                },
                {
                    "action": "end",
                    "source_profile_key": "profile-c",
                    "destination_profile_key": "",
                },
            ],
        )

    def test_order_page_cleanup_stops_order_workers(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.one_shot_worker_runtime import OneShotWorkerRuntime

        class _Worker:
            def __init__(self) -> None:
                self.quit = Mock()

            def isRunning(self) -> bool:
                return True

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        load_worker = _Worker()
        move_worker = _Worker()
        page._order_load_runtime = OneShotWorkerRuntime()
        page._order_load_runtime.worker = load_worker
        page._order_load_runtime.request_id = 3
        page._order_move_runtime = OneShotWorkerRuntime()
        page._order_move_runtime.worker = move_worker
        page._order_move_runtime.request_id = 5
        page._order_load_dirty = True

        ProfileOrderPageBase.cleanup(page)

        load_worker.quit.assert_called_once()
        move_worker.quit.assert_called_once()
        self.assertIsNone(page._order_load_runtime.worker)
        self.assertIsNone(page._order_move_runtime.worker)
        self.assertEqual(page._order_load_runtime.request_id, 4)
        self.assertEqual(page._order_move_runtime.request_id, 6)
        self.assertFalse(page._order_load_dirty)

    def test_order_workers_call_profile_service(self) -> None:
        from profile.profile_order_loader import ProfileOrderListLoadWorker, ProfilePresetOrderMoveWorker

        load_profiles = Mock(return_value=SimpleNamespace(items=()))
        load_worker = ProfileOrderListLoadWorker(2, load_profiles)
        loaded = []
        load_worker.loaded.connect(lambda request_id, payload: loaded.append((request_id, payload)))

        load_worker.run()

        load_profiles.assert_called_once_with()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0][0], 2)
        self.assertIs(loaded[0][1].payload, load_profiles.return_value)
        self.assertIsNone(loaded[0][1].view_state)

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
