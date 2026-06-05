from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class PresetSummaryRefreshRuntimeTests(unittest.TestCase):
    def test_summary_refresh_uses_one_shot_worker_runtime(self) -> None:
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        init_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.__init__)
        request_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.request_refresh)
        start_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._start_worker)
        finish_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._on_worker_finished)
        cleanup_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.cleanup)
        class_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime)

        self.assertIn("OneShotWorkerRuntime", init_source)
        self.assertIn("_summary_runtime", class_source)
        self.assertIn("_summary_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertNotIn("worker.start()", start_source)
        self.assertNotIn("self._worker", class_source)
        self.assertNotIn("worker.deleteLater()", finish_source)
        self.assertIn("_summary_runtime.stop", cleanup_source)
        self.assertIn("_summary_runtime.cancel", cleanup_source)

    def test_pending_summary_refresh_restarts_after_event_loop_turn(self) -> None:
        import presets.display_state_refresh as display_state_refresh
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._pending = True
        runtime.request_refresh = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(display_state_refresh, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PresetProfileStrategySummaryRefreshRuntime._on_worker_finished(runtime, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        runtime.request_refresh.assert_not_called()

        single_shot.call_args.args[1]()

        runtime.request_refresh.assert_called_once_with()

    def test_stale_summary_worker_finish_does_not_restart_pending_refresh(self) -> None:
        import presets.display_state_refresh as display_state_refresh
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._summary_runtime = SimpleNamespace(request_id=2)
        runtime._pending = True
        runtime._start_scheduled = False
        runtime.request_refresh = Mock()
        single_shot = Mock()

        with patch.object(display_state_refresh, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PresetProfileStrategySummaryRefreshRuntime._on_worker_finished(
                runtime,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        runtime.request_refresh.assert_not_called()
        self.assertTrue(runtime._pending)
        self.assertFalse(runtime._start_scheduled)

    def test_stale_summary_worker_object_finish_does_not_restart_pending_refresh(self) -> None:
        import presets.display_state_refresh as display_state_refresh
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._summary_runtime = SimpleNamespace(worker=object())
        runtime._pending = True
        runtime._start_scheduled = False
        runtime.request_refresh = Mock()
        single_shot = Mock()

        with patch.object(display_state_refresh, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            PresetProfileStrategySummaryRefreshRuntime._on_worker_finished(runtime, object())

        single_shot.assert_not_called()
        runtime.request_refresh.assert_not_called()
        self.assertTrue(runtime._pending)
        self.assertFalse(runtime._start_scheduled)

    def test_window_close_cleans_up_summary_refresh_runtime(self) -> None:
        import main.application_lifecycle_port as lifecycle_port
        import main.window_lifecycle_cleanup as lifecycle_cleanup

        port_source = inspect.getsource(lifecycle_port.ApplicationLifecycleWindowPort.cleanup_threaded_pages)
        cleanup_source = inspect.getsource(lifecycle_cleanup.cleanup_session_runtimes_for_close)

        self.assertIn("cleanup_session_runtimes_for_close", port_source)
        self.assertIn("preset_summary_refresh_runtime", cleanup_source)
        self.assertIn("runtime.cleanup()", cleanup_source)


if __name__ == "__main__":
    unittest.main()
