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
        self.assertIn("state.is_busy()", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertNotIn("worker.start()", start_source)
        self.assertNotIn("self._worker", class_source)
        self.assertNotIn("worker.deleteLater()", finish_source)
        self.assertIn("_summary_runtime.stop", cleanup_source)
        self.assertIn("_summary_runtime.cancel", cleanup_source)

    def test_summary_worker_warms_profile_list_before_resolving_summary(self) -> None:
        from presets.display_state import ProfileStrategyDisplayState
        from presets.display_state_refresh import PresetProfileStrategySummaryWorker
        from settings.mode import ZAPRET2_MODE

        events: list[str] = []
        profile_feature = SimpleNamespace(
            warm_profile_list=Mock(side_effect=lambda _method: events.append("warm")),
            get_profile_strategy_display_state=Mock(
                side_effect=lambda _method, max_items=2: (
                    events.append("summary") or ProfileStrategyDisplayState(summary="OVH UDP", active_count=1)
                )
            ),
        )
        worker = PresetProfileStrategySummaryWorker(
            1,
            method=ZAPRET2_MODE,
            profile_feature=profile_feature,
        )

        worker.run()

        self.assertEqual(events, ["warm", "summary"])
        profile_feature.warm_profile_list.assert_called_once_with(ZAPRET2_MODE)

    def test_strategy_only_summary_worker_skips_profile_list_warmup(self) -> None:
        from presets.display_state import ProfileStrategyDisplayState
        from presets.display_state_refresh import PresetProfileStrategySummaryWorker
        from settings.mode import ZAPRET2_MODE

        events: list[str] = []
        profile_feature = SimpleNamespace(
            warm_profile_list=Mock(side_effect=lambda _method: events.append("warm")),
            get_profile_strategy_display_state=Mock(
                side_effect=lambda _method, max_items=2: (
                    events.append("summary") or ProfileStrategyDisplayState(summary="OVH UDP", active_count=1)
                )
            ),
        )
        worker = PresetProfileStrategySummaryWorker(
            1,
            method=ZAPRET2_MODE,
            profile_feature=profile_feature,
            refresh_reason="strategy_only",
        )

        worker.run()

        self.assertEqual(events, ["summary"])
        profile_feature.warm_profile_list.assert_not_called()

    def test_summary_refresh_queue_lives_in_latest_worker_state(self) -> None:
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._summary_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.__init__)
        request_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.request_refresh)
        start_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._start_worker)
        loaded_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._on_summary_loaded)
        failed_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._on_summary_failed)
        finished_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._on_worker_finished)
        run_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime._run_scheduled_refresh_start)
        cleanup_source = inspect.getsource(PresetProfileStrategySummaryRefreshRuntime.cleanup)

        self.assertIsInstance(
            PresetProfileStrategySummaryRefreshRuntime._summary_state_obj(runtime),
            LatestValueWorkerState,
        )
        self.assertIn("_summary_state = LatestValueWorkerState", init_source)
        self.assertIn("_summary_state_obj()", request_source)
        self.assertIn("_summary_state_obj()", start_source)
        self.assertIn("state_obj.has_pending()", loaded_source)
        self.assertIn("state.has_pending()", failed_source)
        self.assertIn("state.has_pending()", finished_source)
        self.assertIn("state.start_scheduled", run_source)
        self.assertIn("_summary_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending = False", init_source)
        self.assertNotIn("self._start_scheduled = False", init_source)

    def test_cleanup_does_not_wait_for_summary_refresh_worker(self) -> None:
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._pending = True
        runtime._start_scheduled = True
        runtime._summary_runtime = SimpleNamespace(stop=Mock(), cancel=Mock())

        runtime.cleanup()

        self.assertFalse(runtime._pending)
        self.assertFalse(runtime._start_scheduled)
        runtime._summary_runtime.stop.assert_called_once_with(
            blocking=False,
            log_fn=__import__("presets.display_state_refresh", fromlist=["log"]).log,
            warning_prefix="preset summary refresh worker",
        )
        runtime._summary_runtime.cancel.assert_called_once_with()

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

    def test_summary_result_is_ignored_when_new_refresh_is_pending(self) -> None:
        import presets.display_state as display_state
        from presets.display_state import ProfileStrategyDisplayState
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._summary_runtime = Mock()
        runtime._summary_runtime.is_current.return_value = True
        runtime._pending = True
        runtime._state_store = Mock()
        state = ProfileStrategyDisplayState(summary="old summary", active_count=1)

        with patch.object(display_state, "publish_profile_strategy_summary_in_store") as publish:
            PresetProfileStrategySummaryRefreshRuntime._on_summary_loaded(runtime, 2, state)

        publish.assert_not_called()

    def test_summary_error_is_ignored_when_new_refresh_is_pending(self) -> None:
        import presets.display_state_refresh as display_state_refresh
        from presets.display_state_refresh import PresetProfileStrategySummaryRefreshRuntime

        runtime = PresetProfileStrategySummaryRefreshRuntime.__new__(
            PresetProfileStrategySummaryRefreshRuntime
        )
        runtime._summary_runtime = Mock()
        runtime._summary_runtime.is_current.return_value = True
        runtime._pending = True

        with patch.object(display_state_refresh, "log") as log_mock:
            PresetProfileStrategySummaryRefreshRuntime._on_summary_failed(runtime, 2, "old error")

        log_mock.assert_not_called()

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
