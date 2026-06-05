from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class AppearanceWorkerQueueTests(unittest.TestCase):
    def test_initial_state_load_queues_while_worker_runs(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_plan = None
        page._initial_state_load_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        page._initial_state_load_pending = False
        page._initial_state_load_pending_force = False

        AppearancePage._request_initial_state_load(page, force=True)

        page._initial_state_load_runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._initial_state_load_pending)
        self.assertTrue(page._initial_state_load_pending_force)

    def test_initial_state_pending_load_restarts_after_event_loop_turn(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_load_pending = True
        page._initial_state_load_pending_force = True
        page._initial_state_load_start_scheduled = False
        page._request_initial_state_load = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_initial_state_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._request_initial_state_load.assert_not_called()

        single_shot.call_args.args[1]()

        page._request_initial_state_load.assert_called_once_with(force=True)
        self.assertFalse(page._initial_state_load_pending)
        self.assertFalse(page._initial_state_load_pending_force)

    def test_stale_initial_state_worker_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_load_runtime = SimpleNamespace(request_id=3)
        page._initial_state_load_pending = True
        page._initial_state_load_pending_force = True
        page._request_initial_state_load = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_initial_state_worker_finished(page, SimpleNamespace(_request_id=2))

        single_shot.assert_not_called()
        page._request_initial_state_load.assert_not_called()
        self.assertTrue(page._initial_state_load_pending)
        self.assertTrue(page._initial_state_load_pending_force)

    def test_stale_initial_state_worker_object_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        old_worker = object()
        current_worker = object()
        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_load_runtime = SimpleNamespace(request_id=3, worker=current_worker)
        page._initial_state_load_pending = True
        page._initial_state_load_pending_force = True
        page._request_initial_state_load = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_initial_state_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._request_initial_state_load.assert_not_called()
        self.assertTrue(page._initial_state_load_pending)
        self.assertTrue(page._initial_state_load_pending_force)

    def test_initial_state_result_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_load_runtime = Mock()
        page._initial_state_load_runtime.is_current.return_value = True
        page._initial_state_load_pending = True
        page._initial_state_plan = "old-plan"
        page._ui_language = "ru"
        page._apply_initial_display_state = Mock()
        page._schedule_lower_sections_build = Mock()
        page._lower_sections_build_scheduled = True
        page.isVisible = Mock(return_value=True)
        plan = SimpleNamespace(ui_language="en")

        AppearancePage._on_initial_state_loaded(page, 12, plan)

        self.assertEqual(page._initial_state_plan, "old-plan")
        self.assertEqual(page._ui_language, "ru")
        page._apply_initial_display_state.assert_not_called()
        page._schedule_lower_sections_build.assert_not_called()

    def test_initial_state_error_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages import appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._initial_state_load_runtime = Mock()
        page._initial_state_load_runtime.is_current.return_value = True
        page._initial_state_load_pending = True
        page._initial_state_plan = None
        page._lower_sections_build_scheduled = True
        page._schedule_lower_sections_build = Mock()
        page.isVisible = Mock(return_value=True)

        with (
            patch.object(appearance_page, "log") as log_mock,
            patch.object(appearance_page.appearance_settings, "build_default_page_initial_state") as default_mock,
        ):
            AppearancePage._on_initial_state_failed(page, 12, "old error")

        log_mock.assert_not_called()
        default_mock.assert_not_called()
        page._schedule_lower_sections_build.assert_not_called()

    def test_appearance_save_pending_restarts_after_event_loop_turn(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_pending = [{"action": "display_mode", "value": "dark"}]
        page._start_appearance_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_appearance_save_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_appearance_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_appearance_save_worker.assert_called_once_with({"action": "display_mode", "value": "dark"})

    def test_stale_appearance_save_worker_finished_does_not_restart_pending_save(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_runtime = SimpleNamespace(request_id=8)
        page._appearance_save_pending = [{"action": "display_mode", "value": "dark"}]
        page._start_appearance_save_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_appearance_save_worker_finished(page, SimpleNamespace(_request_id=7))

        single_shot.assert_not_called()
        page._start_appearance_save_worker.assert_not_called()
        self.assertEqual(page._appearance_save_pending, [{"action": "display_mode", "value": "dark"}])

    def test_stale_appearance_save_worker_object_finished_does_not_restart_pending_save(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        old_worker = object()
        current_worker = object()
        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_runtime = SimpleNamespace(request_id=8, worker=current_worker)
        page._appearance_save_pending = [{"action": "display_mode", "value": "dark"}]
        page._start_appearance_save_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_appearance_save_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_appearance_save_worker.assert_not_called()
        self.assertEqual(page._appearance_save_pending, [{"action": "display_mode", "value": "dark"}])

    def test_appearance_save_scheduled_start_uses_latest_pending_payload(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_pending = [{"action": "display_mode", "value": "dark"}]
        page._appearance_save_start_scheduled = False
        page._appearance_save_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._start_appearance_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_appearance_save_worker_finished(page, object())
            AppearancePage._request_appearance_save(page, "display_mode", "light")

        single_shot.call_args.args[1]()

        page._start_appearance_save_worker.assert_called_once_with(
            {"action": "display_mode", "value": "light", "context_extra": {}}
        )

    def test_appearance_save_result_ignored_when_same_action_is_pending(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_runtime = Mock()
        page._appearance_save_runtime.is_current.return_value = True
        page._appearance_save_pending = [
            {"action": "accent_color", "value": "#222222", "context_extra": {}}
        ]
        page._emit_accent_update = Mock()

        AppearancePage._on_appearance_save_finished(
            page,
            7,
            "accent_color",
            {
                "accent": SimpleNamespace(hex_color="#111111"),
                "tinted": SimpleNamespace(tinted_background=True),
            },
            {"value": "#111111"},
        )

        page._emit_accent_update.assert_not_called()

    def test_appearance_save_error_ignored_when_same_action_is_pending(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._appearance_save_runtime = Mock()
        page._appearance_save_runtime.is_current.return_value = True
        page._appearance_save_pending = [
            {"action": "accent_color", "value": "#222222", "context_extra": {}}
        ]

        with patch("ui.pages.appearance_page.log") as log_mock:
            AppearancePage._on_appearance_save_failed(page, 7, "accent_color", "old error", {})

        log_mock.assert_not_called()

    def test_rkn_background_options_pending_restarts_after_event_loop_turn(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_pending = True
        page._start_rkn_background_options_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_rkn_background_options_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_rkn_background_options_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_rkn_background_options_load_worker.assert_called_once_with()

    def test_stale_rkn_background_options_worker_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_runtime = SimpleNamespace(request_id=5)
        page._rkn_background_options_pending = True
        page._start_rkn_background_options_load_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_rkn_background_options_worker_finished(page, SimpleNamespace(_request_id=4))

        single_shot.assert_not_called()
        page._start_rkn_background_options_load_worker.assert_not_called()
        self.assertTrue(page._rkn_background_options_pending)

    def test_stale_rkn_background_options_worker_object_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        old_worker = object()
        current_worker = object()
        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_runtime = SimpleNamespace(request_id=5, worker=current_worker)
        page._rkn_background_options_pending = True
        page._start_rkn_background_options_load_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_rkn_background_options_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_rkn_background_options_load_worker.assert_not_called()
        self.assertTrue(page._rkn_background_options_pending)

    def test_rkn_background_options_scheduled_start_queues_next_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_start_scheduled = False
        page._rkn_background_options_pending = False
        page._rkn_background_options_runtime = SimpleNamespace(start_qthread_worker=Mock())
        page.create_rkn_background_options_load_worker = Mock(return_value=object())
        page._on_rkn_background_options_loaded = Mock()
        page._on_rkn_background_options_failed = Mock()
        page._on_rkn_background_options_worker_finished = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._schedule_rkn_background_options_load_worker_start(page)
            AppearancePage._schedule_rkn_background_options_load_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._rkn_background_options_pending)

        single_shot.call_args.args[1]()

        page._rkn_background_options_runtime.start_qthread_worker.assert_called_once()
        self.assertTrue(page._rkn_background_options_pending)

    def test_rkn_background_options_result_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_runtime = Mock()
        page._rkn_background_options_runtime.is_current.return_value = True
        page._rkn_background_options_pending = True
        page._apply_rkn_background_options = Mock()

        AppearancePage._on_rkn_background_options_loaded(
            page,
            9,
            {"saved_value": "old.png", "options": (("old.png", "Old"),)},
        )

        page._apply_rkn_background_options.assert_not_called()

    def test_rkn_background_options_error_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages import appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._rkn_background_options_runtime = Mock()
        page._rkn_background_options_runtime.is_current.return_value = True
        page._rkn_background_options_pending = True
        page._apply_rkn_background_options = Mock()

        with patch.object(appearance_page, "log") as log_mock:
            AppearancePage._on_rkn_background_options_failed(page, 9, "old error")

        log_mock.assert_not_called()
        page._apply_rkn_background_options.assert_not_called()

    def test_windows_accent_pending_restarts_after_event_loop_turn(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_pending = True
        page._start_windows_accent_load_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_windows_accent_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_windows_accent_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_windows_accent_load_worker.assert_called_once_with()

    def test_stale_windows_accent_worker_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_runtime = SimpleNamespace(request_id=12)
        page._windows_accent_load_pending = True
        page._start_windows_accent_load_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_windows_accent_worker_finished(page, SimpleNamespace(_request_id=11))

        single_shot.assert_not_called()
        page._start_windows_accent_load_worker.assert_not_called()
        self.assertTrue(page._windows_accent_load_pending)

    def test_stale_windows_accent_worker_object_finished_does_not_restart_pending_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        old_worker = object()
        current_worker = object()
        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_runtime = SimpleNamespace(request_id=12, worker=current_worker)
        page._windows_accent_load_pending = True
        page._start_windows_accent_load_worker = Mock()
        single_shot = Mock()

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._on_windows_accent_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_windows_accent_load_worker.assert_not_called()
        self.assertTrue(page._windows_accent_load_pending)

    def test_windows_accent_scheduled_start_queues_next_load(self) -> None:
        import ui.pages.appearance_page as appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_start_scheduled = False
        page._windows_accent_load_pending = False
        page._windows_accent_load_runtime = SimpleNamespace(start_qthread_worker=Mock())
        page.create_windows_accent_load_worker = Mock(return_value=object())
        page._on_windows_accent_loaded = Mock()
        page._on_windows_accent_failed = Mock()
        page._on_windows_accent_worker_finished = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(appearance_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            AppearancePage._schedule_windows_accent_load_worker_start(page)
            AppearancePage._schedule_windows_accent_load_worker_start(page)

        single_shot.assert_called_once()
        self.assertTrue(page._windows_accent_load_pending)

        single_shot.call_args.args[1]()

        page._windows_accent_load_runtime.start_qthread_worker.assert_called_once()
        self.assertTrue(page._windows_accent_load_pending)

    def test_windows_accent_result_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_runtime = Mock()
        page._windows_accent_load_runtime.is_current.return_value = True
        page._windows_accent_load_pending = True
        page._apply_windows_accent = Mock()

        AppearancePage._on_windows_accent_loaded(page, 11, SimpleNamespace(hex_color="#111111"))

        page._apply_windows_accent.assert_not_called()

    def test_windows_accent_error_ignored_when_new_load_is_pending(self) -> None:
        from ui.pages import appearance_page
        from ui.pages.appearance_page import AppearancePage

        page = AppearancePage.__new__(AppearancePage)
        page._cleanup_in_progress = False
        page._windows_accent_load_runtime = Mock()
        page._windows_accent_load_runtime.is_current.return_value = True
        page._windows_accent_load_pending = True

        with patch.object(appearance_page, "log") as log_mock:
            AppearancePage._on_windows_accent_failed(page, 11, "old error")

        log_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
