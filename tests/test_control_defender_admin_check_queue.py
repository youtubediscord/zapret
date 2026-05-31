from __future__ import annotations

import unittest
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

    def test_defender_admin_check_keeps_latest_request_while_restart_is_scheduled(self) -> None:
        page = _Page()
        page._defender_admin_check_runtime = _Runtime(running=False)
        page._defender_admin_check_pending = True
        page._defender_admin_check_start_scheduled = True
        page.create_program_settings_admin_check_worker = Mock()

        page._request_defender_admin_check(False)

        page.create_program_settings_admin_check_worker.assert_not_called()
        self.assertFalse(page._defender_admin_check_pending)


if __name__ == "__main__":
    unittest.main()
