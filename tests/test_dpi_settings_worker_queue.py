from __future__ import annotations

import sys
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class DpiSettingsWorkerQueueTests(unittest.TestCase):
    def test_dpi_settings_queue_uses_shared_queued_worker_state(self) -> None:
        from settings.dpi.page import DpiSettingsPage
        from ui.queued_worker_state import QueuedWorkerState

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._dpi_settings_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(DpiSettingsPage.__init__)
        request_source = inspect.getsource(DpiSettingsPage._request_dpi_settings_action)
        schedule_source = inspect.getsource(DpiSettingsPage._schedule_dpi_settings_worker_start)
        cleanup_source = inspect.getsource(DpiSettingsPage.cleanup)

        self.assertIsInstance(DpiSettingsPage._dpi_settings_state_obj(page), QueuedWorkerState)
        self.assertNotIn("_dpi_settings_pending: list", init_source)
        self.assertNotIn("_dpi_settings_start_scheduled = False", init_source)
        self.assertIn("_dpi_settings_state_obj()", request_source)
        self.assertIn("_dpi_settings_state_obj()", schedule_source)
        self.assertIn("_dpi_settings_state_obj().reset()", cleanup_source)

    def test_orchestra_settings_save_queue_uses_shared_queued_worker_state(self) -> None:
        from settings.dpi.page import DpiSettingsPage
        from ui.queued_worker_state import QueuedWorkerState

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._orchestra_settings_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(DpiSettingsPage.__init__)
        request_source = inspect.getsource(DpiSettingsPage._request_orchestra_setting_save)
        schedule_source = inspect.getsource(DpiSettingsPage._schedule_orchestra_setting_save_worker_start)
        cleanup_source = inspect.getsource(DpiSettingsPage.cleanup)

        self.assertIsInstance(DpiSettingsPage._orchestra_settings_save_state_obj(page), QueuedWorkerState)
        self.assertNotIn("_orchestra_settings_save_pending: list", init_source)
        self.assertNotIn("_orchestra_settings_save_start_scheduled = False", init_source)
        self.assertIn("_orchestra_settings_save_state_obj()", request_source)
        self.assertIn("_orchestra_settings_save_state_obj()", schedule_source)
        self.assertIn("_orchestra_settings_save_state_obj().reset()", cleanup_source)

    def test_dpi_settings_pending_restarts_after_event_loop_turn(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._dpi_settings_pending = [("apply_launch_method", "zapret2_mode")]
        page._start_dpi_settings_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_dpi_settings_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_dpi_settings_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_dpi_settings_worker.assert_called_once_with(("apply_launch_method", "zapret2_mode"))

    def test_stale_dpi_settings_worker_finished_does_not_start_pending_action(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._dpi_settings_runtime = SimpleNamespace(request_id=2)
        page._dpi_settings_pending = [("apply_launch_method", "zapret2_mode")]
        page._start_dpi_settings_worker = Mock()
        single_shot = Mock()

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_dpi_settings_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page._start_dpi_settings_worker.assert_not_called()
        self.assertEqual(page._dpi_settings_pending, [("apply_launch_method", "zapret2_mode")])

    def test_stale_dpi_settings_worker_object_finished_does_not_start_pending_action(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._dpi_settings_runtime = SimpleNamespace(worker=object())
        page._dpi_settings_pending = [("apply_launch_method", "zapret2_mode")]
        page._start_dpi_settings_worker = Mock()
        single_shot = Mock()

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_dpi_settings_worker_finished(page, object())

        single_shot.assert_not_called()
        page._start_dpi_settings_worker.assert_not_called()
        self.assertEqual(page._dpi_settings_pending, [("apply_launch_method", "zapret2_mode")])

    def test_dpi_settings_scheduled_start_queues_latest_action(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._dpi_settings_start_scheduled = False
        page._dpi_settings_pending = []
        page._start_dpi_settings_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = ("apply_launch_method", "zapret1_mode")
        new_payload = ("apply_launch_method", "zapret2_mode")
        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._schedule_dpi_settings_worker_start(page, old_payload)
            DpiSettingsPage._schedule_dpi_settings_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._dpi_settings_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_dpi_settings_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._dpi_settings_pending, [new_payload])

    def test_selecting_current_launch_method_does_not_reapply_mode(self) -> None:
        from settings.dpi.page import DpiSettingsPage
        from settings.mode import ZAPRET2_MODE

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._selected_launch_method = ZAPRET2_MODE
        page._request_launch_method_apply = Mock()
        page._update_method_selection = Mock()
        page._apply_visibility = Mock()
        page._dpi_settings = SimpleNamespace(
            describe_visibility=Mock(return_value=SimpleNamespace(show_orchestra_settings=False)),
        )

        DpiSettingsPage._select_method(page, ZAPRET2_MODE)

        page._dpi_settings.describe_visibility.assert_not_called()
        page._request_launch_method_apply.assert_not_called()
        page._update_method_selection.assert_not_called()
        page._apply_visibility.assert_not_called()

    def test_orchestra_setting_pending_restarts_after_event_loop_turn(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._orchestra_settings_save_pending = [("debug_file", True)]
        page._start_orchestra_setting_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_orchestra_setting_save_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_orchestra_setting_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_orchestra_setting_save_worker.assert_called_once_with(("debug_file", True))

    def test_stale_orchestra_setting_save_worker_finished_does_not_start_pending_save(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._orchestra_settings_save_runtime = SimpleNamespace(request_id=2)
        page._orchestra_settings_save_pending = [("debug_file", True)]
        page._start_orchestra_setting_save_worker = Mock()
        single_shot = Mock()

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_orchestra_setting_save_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page._start_orchestra_setting_save_worker.assert_not_called()
        self.assertEqual(page._orchestra_settings_save_pending, [("debug_file", True)])

    def test_stale_orchestra_setting_save_worker_object_finished_does_not_start_pending_save(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._orchestra_settings_save_runtime = SimpleNamespace(worker=object())
        page._orchestra_settings_save_pending = [("debug_file", True)]
        page._start_orchestra_setting_save_worker = Mock()
        single_shot = Mock()

        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._on_orchestra_setting_save_worker_finished(page, object())

        single_shot.assert_not_called()
        page._start_orchestra_setting_save_worker.assert_not_called()
        self.assertEqual(page._orchestra_settings_save_pending, [("debug_file", True)])

    def test_orchestra_setting_scheduled_start_queues_latest_value(self) -> None:
        import settings.dpi.page as dpi_page
        from settings.dpi.page import DpiSettingsPage

        page = DpiSettingsPage.__new__(DpiSettingsPage)
        page._cleanup_in_progress = False
        page._orchestra_settings_save_start_scheduled = False
        page._orchestra_settings_save_pending = []
        page._start_orchestra_setting_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = ("debug_file", True)
        new_payload = ("debug_file", False)
        with patch.object(dpi_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            DpiSettingsPage._schedule_orchestra_setting_save_worker_start(page, old_payload)
            DpiSettingsPage._schedule_orchestra_setting_save_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._orchestra_settings_save_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_orchestra_setting_save_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._orchestra_settings_save_pending, [new_payload])


if __name__ == "__main__":
    unittest.main()
