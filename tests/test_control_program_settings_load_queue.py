from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from presets.ui.control.control_page_shared import ControlPageActionMixin
from ui.latest_value_worker_state import LatestValueWorkerState


class _LoadRuntime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started = 0

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, **_kwargs) -> None:
        self.started += 1


class _Page(ControlPageActionMixin):
    create_program_settings_load_worker = Mock()
    _on_program_settings_load_finished = Mock()
    _on_program_settings_load_failed = Mock()


class ControlProgramSettingsLoadQueueTests(unittest.TestCase):
    def _make_page(self, *, running: bool):
        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

        load_runtime = _LoadRuntime(running=running)
        page = _Page()
        page._cleanup_in_progress = False
        page._refresh_runtime = ModeControlRefreshRuntime()
        page._refresh_runtime.program_settings_load_runtime = load_runtime
        page._refresh_runtime.program_settings_load_state.runtime = load_runtime
        page.create_program_settings_load_worker = Mock(return_value=object())
        return page, load_runtime

    def test_program_settings_load_queue_uses_shared_latest_worker_state(self) -> None:
        import inspect

        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

        runtime = ModeControlRefreshRuntime()
        runtime_source = inspect.getsource(ModeControlRefreshRuntime.__init__)

        self.assertIsInstance(runtime.program_settings_load_state, LatestValueWorkerState)
        self.assertNotIn("self.program_settings_load_pending = False", runtime_source)
        self.assertNotIn("self.program_settings_load_start_scheduled = False", runtime_source)

    def test_program_settings_load_marks_pending_while_worker_runs(self) -> None:
        page, load_runtime = self._make_page(running=True)

        page._request_program_settings_load()

        self.assertTrue(page._refresh_runtime.program_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)

    def test_program_settings_load_worker_finished_restarts_pending_load_later(self) -> None:
        page, load_runtime = self._make_page(running=False)
        page._refresh_runtime.program_settings_load_pending = True
        callbacks = []

        with patch(
            "presets.ui.control.control_page_shared.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            page._on_program_settings_load_worker_finished(object())

        self.assertFalse(page._refresh_runtime.program_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(load_runtime.started, 1)

    def test_stale_program_settings_load_worker_finished_does_not_restart_pending_load(self) -> None:
        page, load_runtime = self._make_page(running=False)
        load_runtime.request_id = 2
        page._refresh_runtime.program_settings_load_pending = True

        with patch("presets.ui.control.control_page_shared.QTimer.singleShot") as single_shot:
            page._on_program_settings_load_worker_finished(SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        self.assertEqual(load_runtime.started, 0)
        self.assertTrue(page._refresh_runtime.program_settings_load_pending)

    def test_stale_program_settings_load_worker_object_does_not_restart_pending_load(self) -> None:
        page, load_runtime = self._make_page(running=False)
        load_runtime.worker = object()
        page._refresh_runtime.program_settings_load_pending = True

        with patch("presets.ui.control.control_page_shared.QTimer.singleShot") as single_shot:
            page._on_program_settings_load_worker_finished(object())

        single_shot.assert_not_called()
        self.assertEqual(load_runtime.started, 0)
        self.assertTrue(page._refresh_runtime.program_settings_load_pending)

    def test_program_settings_load_waits_while_restart_is_scheduled(self) -> None:
        page, load_runtime = self._make_page(running=False)
        page._refresh_runtime.program_settings_load_pending = True
        callbacks = []

        with patch(
            "presets.ui.control.control_page_shared.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            page._on_program_settings_load_worker_finished(object())

        self.assertTrue(page._refresh_runtime.program_settings_load_start_scheduled)

        page._request_program_settings_load()

        self.assertEqual(load_runtime.started, 0)
        self.assertTrue(page._refresh_runtime.program_settings_load_pending)
        self.assertEqual(len(callbacks), 1)

    def test_program_settings_load_result_ignored_when_new_load_is_pending(self) -> None:
        page, load_runtime = self._make_page(running=False)
        load_runtime.is_current = Mock(return_value=True)
        page._refresh_runtime.program_settings_load_pending = True
        page._publish_program_settings_snapshot = Mock()
        page._apply_program_settings_snapshot = Mock()
        snapshot = object()

        ControlPageActionMixin._on_program_settings_load_finished(page, 4, snapshot)

        page._publish_program_settings_snapshot.assert_not_called()
        page._apply_program_settings_snapshot.assert_not_called()

    def test_program_settings_load_error_ignored_when_new_load_is_pending(self) -> None:
        page, load_runtime = self._make_page(running=False)
        load_runtime.is_current = Mock(return_value=True)
        page._refresh_runtime.program_settings_load_pending = True

        with patch("log.log.log") as log_mock:
            ControlPageActionMixin._on_program_settings_load_failed(page, 4, "stale error")

        log_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
