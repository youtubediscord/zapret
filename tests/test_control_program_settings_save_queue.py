from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class _SaveRuntime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


class _Page:
    from presets.ui.control.control_page_shared import ControlPageActionMixin

    _request_program_settings_save = ControlPageActionMixin._request_program_settings_save
    _on_program_settings_save_worker_finished = ControlPageActionMixin._on_program_settings_save_worker_finished
    _schedule_program_settings_save_start = ControlPageActionMixin._schedule_program_settings_save_start
    _run_scheduled_program_settings_save_start = ControlPageActionMixin._run_scheduled_program_settings_save_start
    _is_current_worker_finish = ControlPageActionMixin._is_current_worker_finish
    create_program_settings_save_worker = Mock()
    _on_program_settings_save_finished = Mock()
    _on_program_settings_save_failed = Mock()
    _bind_program_settings_save_worker = Mock()


class ControlProgramSettingsSaveQueueTests(unittest.TestCase):
    def _make_page(self, *, running: bool):
        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

        save_runtime = _SaveRuntime(running=running)
        page = _Page()
        page._cleanup_in_progress = False
        page._refresh_runtime = ModeControlRefreshRuntime()
        page._refresh_runtime.program_settings_save_runtime = save_runtime
        page.create_program_settings_save_worker = Mock(return_value=object())
        page._on_program_settings_save_finished = Mock()
        page._on_program_settings_save_failed = Mock()
        page._bind_program_settings_save_worker = Mock()
        return page, save_runtime

    def test_program_settings_save_keeps_pending_actions_for_different_settings(self) -> None:
        page, save_runtime = self._make_page(running=True)

        _Page._request_program_settings_save(page, "auto_dpi", True)
        _Page._request_program_settings_save(page, "hide_to_tray", False)

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(
            page._refresh_runtime.program_settings_save_pending,
            [
                ("auto_dpi", True),
                ("hide_to_tray", False),
            ],
        )

    def test_program_settings_save_replaces_pending_action_for_same_setting(self) -> None:
        page, save_runtime = self._make_page(running=True)

        _Page._request_program_settings_save(page, "hide_to_tray", True)
        _Page._request_program_settings_save(page, "hide_to_tray", False)

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(page._refresh_runtime.program_settings_save_pending, [("hide_to_tray", False)])

    def test_program_settings_save_queues_while_restart_is_scheduled(self) -> None:
        page, save_runtime = self._make_page(running=False)
        page._refresh_runtime.program_settings_save_start_scheduled = True

        _Page._request_program_settings_save(page, "hide_to_tray", True)

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(page._refresh_runtime.program_settings_save_pending, [("hide_to_tray", True)])

    def test_program_settings_finished_starts_next_pending_save(self) -> None:
        page, save_runtime = self._make_page(running=False)
        worker = object()
        page.create_program_settings_save_worker = Mock(return_value=worker)
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", True)]

        callbacks = []
        with patch(
            "presets.ui.control.control_page_shared.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            _Page._on_program_settings_save_worker_finished(page, object())

        page.create_program_settings_save_worker.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_program_settings_save_worker.assert_called_once_with(
            0,
            action="hide_to_tray",
            enabled=True,
        )
        self.assertEqual(save_runtime.started, [worker])
        self.assertEqual(page._refresh_runtime.program_settings_save_pending, [])

    def test_stale_program_settings_save_worker_finished_does_not_start_pending_save(self) -> None:
        page, save_runtime = self._make_page(running=False)
        save_runtime.request_id = 2
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", True)]

        with patch("presets.ui.control.control_page_shared.QTimer.singleShot") as single_shot:
            _Page._on_program_settings_save_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page.create_program_settings_save_worker.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(page._refresh_runtime.program_settings_save_pending, [("hide_to_tray", True)])

    def test_stale_program_settings_save_worker_object_does_not_start_pending_save(self) -> None:
        page, save_runtime = self._make_page(running=False)
        save_runtime.worker = object()
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", True)]

        with patch("presets.ui.control.control_page_shared.QTimer.singleShot") as single_shot:
            _Page._on_program_settings_save_worker_finished(page, object())

        single_shot.assert_not_called()
        page.create_program_settings_save_worker.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(page._refresh_runtime.program_settings_save_pending, [("hide_to_tray", True)])

    def test_program_settings_save_status_ignored_when_new_save_is_pending(self) -> None:
        from presets.ui.control.control_page_shared import ControlPageActionMixin

        page, save_runtime = self._make_page(running=False)
        save_runtime.is_current = Mock(return_value=True)
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", False)]
        page._set_status = Mock()

        ControlPageActionMixin._on_program_settings_save_status(page, 4, "hide_to_tray", "stale")

        page._set_status.assert_not_called()

    def test_program_settings_save_result_ignored_when_new_save_is_pending(self) -> None:
        from presets.ui.control.control_page_shared import ControlPageActionMixin

        page, save_runtime = self._make_page(running=False)
        save_runtime.is_current = Mock(return_value=True)
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", False)]
        page._remember_hide_to_tray_on_minimize_close = Mock()
        page._sync_program_settings = Mock()

        ControlPageActionMixin._on_program_settings_save_finished(page, 4, "hide_to_tray", True)

        page._remember_hide_to_tray_on_minimize_close.assert_not_called()
        page._sync_program_settings.assert_not_called()

    def test_program_settings_save_error_ignored_when_new_save_is_pending(self) -> None:
        from presets.ui.control.control_page_shared import ControlPageActionMixin

        page, save_runtime = self._make_page(running=False)
        save_runtime.is_current = Mock(return_value=True)
        page._refresh_runtime.program_settings_save_pending = [("hide_to_tray", False)]
        page._sync_program_settings = Mock()
        page.window = Mock(return_value=object())

        with patch("qfluentwidgets.InfoBar.warning") as warning_mock:
            ControlPageActionMixin._on_program_settings_save_failed(page, 4, "hide_to_tray", "stale error")

        warning_mock.assert_not_called()
        page._sync_program_settings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
