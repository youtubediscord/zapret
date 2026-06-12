from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class ProfileOrderWorkerArchitectureTests(unittest.TestCase):
    def test_profile_order_load_worker_receives_loader_function(self) -> None:
        from profile.profile_order_loader import ProfileOrderListLoadWorker

        init_source = inspect.getsource(ProfileOrderListLoadWorker.__init__)
        run_source = inspect.getsource(ProfileOrderListLoadWorker.run)

        self.assertIn("load_profiles", init_source)
        self.assertIn("self._load_profiles", init_source)
        self.assertNotIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._load_profiles()", run_source)
        self.assertNotIn("self._service.list_preset_order_profiles", run_source)
        self.assertNotIn("self._profile.list_preset_order_profiles", run_source)

    def test_profile_order_load_worker_builds_view_state_off_gui_thread(self) -> None:
        from profile.profile_order_loader import ProfileOrderListLoadWorker

        init_source = inspect.getsource(ProfileOrderListLoadWorker.__init__)
        run_source = inspect.getsource(ProfileOrderListLoadWorker.run)

        self.assertIn("build_view_state", init_source)
        self.assertIn("self._build_view_state", run_source)
        self.assertIn("ProfileOrderListLoadResult", run_source)

    def test_profile_feature_builds_order_state_without_ui_model_import(self) -> None:
        from app.feature_facades.profile import ProfileFeature

        worker_source = inspect.getsource(ProfileFeature.create_profile_order_load_worker)

        self.assertIn("profile.order_view_state", worker_source)
        self.assertNotIn("profile.ui.profile_order_list", worker_source)

    def test_profile_order_move_worker_receives_move_functions(self) -> None:
        from profile.profile_order_loader import ProfilePresetOrderMoveWorker

        init_source = inspect.getsource(ProfilePresetOrderMoveWorker.__init__)
        run_source = inspect.getsource(ProfilePresetOrderMoveWorker.run)

        self.assertIn("move_before", init_source)
        self.assertIn("move_after", init_source)
        self.assertIn("move_to_end", init_source)
        self.assertIn("self._move_before", init_source)
        self.assertIn("self._move_after", init_source)
        self.assertIn("self._move_to_end", init_source)
        self.assertNotIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._move_before(", run_source)
        self.assertIn("self._move_after(", run_source)
        self.assertIn("self._move_to_end(", run_source)
        self.assertNotIn("self._service.move_preset_profile", run_source)
        self.assertNotIn("self._profile.move_preset_profile", run_source)

    def test_profile_order_list_rebuilds_visible_rows_through_worker(self) -> None:
        import profile.ui.profile_order_list as order_list_module
        from profile.ui.profile_order_list import ProfileOrderList
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileOrderList.__new__(ProfileOrderList)
        page._view_state_runtime = Mock()
        list_source = inspect.getsource(ProfileOrderList)
        init_source = inspect.getsource(ProfileOrderList.__init__)
        set_source = inspect.getsource(ProfileOrderList.set_profiles)
        move_source = inspect.getsource(ProfileOrderList.move_profile_item)
        request_source = inspect.getsource(ProfileOrderList._request_view_state_rebuild)
        finished_source = inspect.getsource(ProfileOrderList._on_view_state_worker_finished)
        worker_source = inspect.getsource(order_list_module.ProfileOrderListViewStateWorker.run)

        self.assertIn("LatestValueWorkerState", list_source)
        self.assertTrue(hasattr(ProfileOrderList, "_view_state_state_obj"))
        self.assertIsInstance(page._view_state_state_obj(), LatestValueWorkerState)
        self.assertIn("_view_state_state = LatestValueWorkerState", init_source)
        self.assertNotIn("_view_state_runtime_worker = None", init_source)
        self.assertNotIn("_view_state_rebuild_pending = False", init_source)
        self.assertIn("_view_state_state_obj()", request_source)
        self.assertIn("_view_state_state_obj()", finished_source)
        self.assertIn("_request_view_state_rebuild", set_source)
        self.assertIn("_request_view_state_rebuild", move_source)
        self.assertNotIn("self._model.set_profiles", set_source)
        self.assertNotIn("self._model.move_profile", move_source)
        self.assertIn("build_profile_order_list_view_state", worker_source)

    def test_profile_order_load_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_load_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(ProfileOrderPageBase.__init__)
        reload_source = inspect.getsource(ProfileOrderPageBase._reload_order_profiles)
        finished_source = inspect.getsource(ProfileOrderPageBase._on_order_profiles_worker_finished)
        scheduled_source = inspect.getsource(ProfileOrderPageBase._run_scheduled_order_profiles_reload)
        cleanup_source = inspect.getsource(ProfileOrderPageBase.cleanup)

        self.assertTrue(hasattr(ProfileOrderPageBase, "_order_load_state_obj"))
        self.assertIsInstance(page._order_load_state_obj(), LatestValueWorkerState)
        self.assertIn("_order_load_state = LatestValueWorkerState", init_source)
        self.assertIn("_order_load_state_obj()", reload_source)
        self.assertIn("_order_load_state_obj()", finished_source)
        self.assertIn("_order_load_state_obj()", scheduled_source)
        self.assertIn("_order_load_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._order_load_dirty = False", init_source)
        self.assertNotIn("self._order_load_restart_scheduled = False", init_source)

    def test_profile_order_load_finished_uses_shared_finish_guard(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        finished_source = inspect.getsource(ProfileOrderPageBase._on_order_profiles_worker_finished)

        self.assertIn("schedule_pending_after_finish", finished_source)
        self.assertIn("_is_current_worker_finish", finished_source)
        self.assertNotIn("_schedule_order_profiles_reload()", finished_source)

    def test_profile_order_move_queue_uses_shared_queued_worker_state(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase
        from ui.queued_worker_state import QueuedWorkerState

        page = ProfileOrderPageBase.__new__(ProfileOrderPageBase)
        page._order_move_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(ProfileOrderPageBase.__init__)
        request_source = inspect.getsource(ProfileOrderPageBase._request_profile_order_move)
        queue_source = inspect.getsource(ProfileOrderPageBase._queue_profile_order_move)
        finished_source = inspect.getsource(ProfileOrderPageBase._on_profile_order_move_worker_finished)
        helper_source = inspect.getsource(ProfileOrderPageBase._schedule_next_profile_order_move_after_finish)
        scheduled_source = inspect.getsource(ProfileOrderPageBase._run_scheduled_profile_order_move_start)
        cleanup_source = inspect.getsource(ProfileOrderPageBase.cleanup)

        self.assertTrue(hasattr(ProfileOrderPageBase, "_order_move_state_obj"))
        self.assertIsInstance(page._order_move_state_obj(), QueuedWorkerState)
        self.assertIn("_order_move_state = QueuedWorkerState", init_source)
        self.assertIn("_order_move_state_obj()", request_source)
        self.assertIn("_order_move_state_obj()", queue_source)
        self.assertIn("_order_move_state_obj()", helper_source)
        self.assertIn("_schedule_next_profile_order_move_after_finish", finished_source)
        self.assertIn("_order_move_state_obj()", scheduled_source)
        self.assertIn("_order_move_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_profile_order_moves", init_source)
        self.assertNotIn("self._order_move_start_scheduled = False", init_source)

    def test_profile_order_move_finished_uses_queued_state_finish_guard(self) -> None:
        from profile.ui.profile_order_page import ProfileOrderPageBase

        finished_source = inspect.getsource(ProfileOrderPageBase._on_profile_order_move_worker_finished)
        helper_source = inspect.getsource(ProfileOrderPageBase._schedule_next_profile_order_move_after_finish)

        self.assertIn("schedule_next_after_finish", helper_source)
        self.assertIn("_is_current_worker_finish", helper_source)
        self.assertIn("_schedule_next_profile_order_move_after_finish", finished_source)
        self.assertNotIn("_schedule_next_profile_order_move_start()", finished_source)


if __name__ == "__main__":
    unittest.main()
