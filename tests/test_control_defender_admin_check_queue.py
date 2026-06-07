from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from presets.ui.control.windows_features.runtime import ControlPageWindowsFeatureMixin


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


class _Page(ControlPageWindowsFeatureMixin):
    create_program_settings_admin_check_worker = Mock()


class ControlDefenderAdminCheckQueueTests(unittest.TestCase):
    def test_defender_admin_check_keeps_latest_pending_request(self) -> None:
        page = _Page()
        page._defender_admin_check_runtime = _Runtime(running=True)
        page._defender_admin_check_pending = None
        page.create_program_settings_admin_check_worker = Mock()

        page._request_defender_admin_check(True)
        page._request_defender_admin_check(False)

        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertFalse(page._defender_admin_check_pending)

    def test_defender_toggle_ignores_program_settings_snapshot_apply(self) -> None:
        page = _Page()
        page._program_settings_snapshot_apply_in_progress = True
        page._request_defender_admin_check = Mock()

        page._on_defender_toggled(True)

        page._request_defender_admin_check.assert_not_called()

    def test_defender_admin_check_worker_finished_restarts_pending_check_later(self) -> None:
        worker = object()
        page = _Page()
        page._cleanup_in_progress = False
        page._defender_admin_check_runtime = _Runtime(running=False)
        page._defender_admin_check_pending = True
        page.create_program_settings_admin_check_worker = Mock(return_value=worker)
        callbacks = []

        with patch(
            "presets.ui.control.windows_features.runtime.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            page._on_defender_admin_check_worker_finished(object())

        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertEqual(page._defender_admin_check_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_program_settings_admin_check_worker.assert_called_once_with(0)
        self.assertEqual(page._defender_admin_check_runtime.started, [worker])

    def test_stale_defender_admin_check_worker_finished_does_not_restart_pending_check(self) -> None:
        page = _Page()
        page._cleanup_in_progress = False
        page._defender_admin_check_runtime = _Runtime(running=False)
        page._defender_admin_check_runtime.request_id = 2
        page._defender_admin_check_pending = True
        page.create_program_settings_admin_check_worker = Mock()

        with patch("presets.ui.control.windows_features.runtime.QTimer.singleShot") as single_shot:
            page._on_defender_admin_check_worker_finished(SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertTrue(page._defender_admin_check_pending)

    def test_stale_defender_admin_check_worker_object_finished_does_not_restart_pending_check(self) -> None:
        old_worker = object()
        current_worker = object()
        page = _Page()
        page._cleanup_in_progress = False
        page._defender_admin_check_runtime = _Runtime(running=False)
        page._defender_admin_check_runtime.request_id = 2
        page._defender_admin_check_runtime.worker = current_worker
        page._defender_admin_check_pending = True
        page.create_program_settings_admin_check_worker = Mock()

        with patch("presets.ui.control.windows_features.runtime.QTimer.singleShot") as single_shot:
            page._on_defender_admin_check_worker_finished(old_worker)

        single_shot.assert_not_called()
        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertTrue(page._defender_admin_check_pending)

    def test_defender_admin_check_keeps_latest_request_while_restart_is_scheduled(self) -> None:
        page = _Page()
        page._defender_admin_check_runtime = _Runtime(running=False)
        page._defender_admin_check_pending = True
        page._defender_admin_check_start_scheduled = True
        page.create_program_settings_admin_check_worker = Mock()

        page._request_defender_admin_check(False)

        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertFalse(page._defender_admin_check_pending)

    def test_defender_admin_check_result_ignored_when_new_check_is_pending(self) -> None:
        page = _Page()
        page._defender_admin_check_pending = False
        page._defender_admin_check_runtime = Mock()
        page._defender_admin_check_runtime.is_current.return_value = True
        page._continue_defender_toggle = Mock()

        page._on_defender_admin_check_finished(3, True, disable=True)

        page._continue_defender_toggle.assert_not_called()

    def test_defender_admin_check_error_ignored_when_new_check_is_pending(self) -> None:
        page = _Page()
        page._defender_admin_check_pending = False
        page._defender_admin_check_runtime = Mock()
        page._defender_admin_check_runtime.is_current.return_value = True
        page._continue_defender_toggle = Mock()

        page._on_defender_admin_check_failed(3, "old admin check failed", disable=True)

        page._continue_defender_toggle.assert_not_called()

    def test_stop_defender_admin_check_worker_does_not_block_gui(self) -> None:
        runtime = Mock()
        page = _Page()
        page._defender_admin_check_runtime = runtime
        page._defender_admin_check_pending = True
        page._defender_admin_check_start_scheduled = True

        page._stop_defender_admin_check_worker()

        self.assertIsNone(page._defender_admin_check_pending)
        self.assertFalse(page._defender_admin_check_start_scheduled)
        runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Defender admin check worker",
        )
        runtime.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
