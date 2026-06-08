from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class WindowGeometryWorkerTests(unittest.TestCase):
    def test_geometry_save_loaded_callback_accepts_runtime_request_id(self) -> None:
        import ui.window_geometry_runtime as runtime

        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._cleanup_in_progress = False
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=7)
        geometry_runtime._last_persisted_maximized = None
        geometry_runtime._pending_window_maximized_state = None
        geometry_runtime._last_persisted_geometry = None
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=7)

        runtime.WindowGeometryRuntime._on_geometry_save_finished(
            geometry_runtime,
            7,
            (10, 20, 800, 600),
            True,
        )

        self.assertEqual(geometry_runtime._last_persisted_geometry, (10, 20, 800, 600))
        self.assertTrue(geometry_runtime._last_persisted_maximized)
        self.assertTrue(geometry_runtime._pending_window_maximized_state)

    def test_stale_geometry_save_loaded_callback_is_ignored(self) -> None:
        import ui.window_geometry_runtime as runtime

        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._last_persisted_maximized = False
        geometry_runtime._pending_window_maximized_state = False
        geometry_runtime._last_persisted_geometry = (1, 2, 300, 200)
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=8)

        runtime.WindowGeometryRuntime._on_geometry_save_finished(
            geometry_runtime,
            7,
            (10, 20, 800, 600),
            True,
        )

        self.assertEqual(geometry_runtime._last_persisted_geometry, (1, 2, 300, 200))
        self.assertFalse(geometry_runtime._last_persisted_maximized)
        self.assertFalse(geometry_runtime._pending_window_maximized_state)

    def test_regular_window_geometry_saves_run_through_worker(self) -> None:
        import main.window_lifecycle_setup as lifecycle_setup
        from app.feature_facades.window_geometry import WindowGeometryFeature
        import ui.window_geometry_runtime as runtime
        import app.window_geometry_workers as worker_module

        self.assertTrue(hasattr(worker_module, "WindowGeometrySaveWorker"))

        worker_init_source = inspect.getsource(worker_module.WindowGeometrySaveWorker.__init__)
        worker_source = inspect.getsource(worker_module.WindowGeometrySaveWorker.run)
        feature_source = inspect.getsource(WindowGeometryFeature)
        lifecycle_source = inspect.getsource(lifecycle_setup.attach_window_lifecycle)
        runtime_source = inspect.getsource(runtime.WindowGeometryRuntime)
        persist_source = inspect.getsource(runtime.WindowGeometryRuntime._persist_geometry_now)
        max_source = inspect.getsource(runtime.WindowGeometryRuntime._persist_window_maximized_state_now)
        sync_source = inspect.getsource(runtime.WindowGeometryRuntime._persist_geometry_sync)
        request_source = inspect.getsource(runtime.WindowGeometryRuntime._request_geometry_save)
        start_source = inspect.getsource(runtime.WindowGeometryRuntime._start_geometry_save_worker)

        self.assertIn("set_window_geometry=self.set_window_geometry", feature_source)
        self.assertIn("get_window_geometry=self.get_window_geometry", feature_source)
        self.assertIn("features.window_geometry.create_geometry_save_worker", lifecycle_source)
        self.assertIn("request_id", worker_init_source)
        self.assertIn("self._request_id", worker_init_source)
        self.assertIn("create_geometry_save_worker", runtime_source)
        self.assertIn("_geometry_save_runtime = OneShotWorkerRuntime()", runtime_source)
        self.assertNotIn("ui.window_geometry_worker", runtime_source)
        self.assertNotIn("settings_store", worker_source)
        self.assertIn("_persist_geometry_sync", persist_source)
        self.assertIn("_request_geometry_save", persist_source)
        self.assertIn("_request_geometry_save", max_source)
        self.assertIn("_stop_geometry_save_worker_for_sync", sync_source)
        self.assertIn("_geometry_save_state_obj", request_source)
        self.assertIn("_geometry_save_runtime", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertNotIn("worker.start()", start_source)
        self.assertNotIn("worker.deleteLater()", runtime_source)
        self.assertNotIn("self.store.save_geometry", persist_source)
        self.assertNotIn("self.store.save_maximized", max_source)

    def test_geometry_save_pending_uses_shared_latest_worker_state(self) -> None:
        import ui.window_geometry_runtime as runtime

        runtime_source = inspect.getsource(runtime.WindowGeometryRuntime)
        init_source = inspect.getsource(runtime.WindowGeometryRuntime.__init__)

        self.assertIn("LatestValueWorkerState", runtime_source)
        self.assertIn("_geometry_save_state_obj", runtime_source)
        self.assertNotIn(
            "self._geometry_save_pending: tuple[tuple[int, int, int, int] | None, bool] | None = None",
            init_source,
        )
        self.assertNotIn("self._geometry_save_start_scheduled = False", init_source)

    def test_pending_geometry_save_restarts_after_event_loop_turn(self) -> None:
        import ui.window_geometry_runtime as runtime

        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._cleanup_in_progress = False
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=1)
        geometry_runtime._geometry_save_pending = ((10, 20, 800, 600), True)
        geometry_runtime._start_geometry_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(runtime, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            runtime.WindowGeometryRuntime._on_geometry_save_worker_finished(
                geometry_runtime,
                object(),
            )

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        geometry_runtime._start_geometry_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        geometry_runtime._start_geometry_save_worker.assert_called_once_with(((10, 20, 800, 600), True))

    def test_stale_geometry_save_worker_finished_does_not_restart_pending_save(self) -> None:
        import ui.window_geometry_runtime as runtime

        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._cleanup_in_progress = False
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=2)
        geometry_runtime._geometry_save_pending = ((10, 20, 800, 600), True)
        geometry_runtime._start_geometry_save_worker = Mock()
        single_shot = Mock()

        with patch.object(runtime, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            runtime.WindowGeometryRuntime._on_geometry_save_worker_finished(
                geometry_runtime,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        geometry_runtime._start_geometry_save_worker.assert_not_called()
        self.assertEqual(geometry_runtime._geometry_save_pending, ((10, 20, 800, 600), True))

    def test_stale_geometry_save_worker_object_finished_does_not_restart_pending_save(self) -> None:
        import ui.window_geometry_runtime as runtime

        old_worker = object()
        current_worker = object()
        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._cleanup_in_progress = False
        geometry_runtime._geometry_save_runtime = SimpleNamespace(request_id=2, worker=current_worker)
        geometry_runtime._geometry_save_pending = ((10, 20, 800, 600), True)
        geometry_runtime._start_geometry_save_worker = Mock()
        single_shot = Mock()

        with patch.object(runtime, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            runtime.WindowGeometryRuntime._on_geometry_save_worker_finished(
                geometry_runtime,
                old_worker,
            )

        single_shot.assert_not_called()
        geometry_runtime._start_geometry_save_worker.assert_not_called()
        self.assertEqual(geometry_runtime._geometry_save_pending, ((10, 20, 800, 600), True))

    def test_force_sync_geometry_save_does_not_wait_for_worker(self) -> None:
        import ui.window_geometry_runtime as runtime

        worker_runtime = SimpleNamespace(stop=Mock(), cancel=Mock())
        geometry_runtime = runtime.WindowGeometryRuntime.__new__(runtime.WindowGeometryRuntime)
        geometry_runtime._geometry_save_pending = ((10, 20, 800, 600), False)
        geometry_runtime._geometry_save_start_scheduled = True
        geometry_runtime._geometry_save_runtime = worker_runtime

        runtime.WindowGeometryRuntime._stop_geometry_save_worker_for_sync(geometry_runtime)

        self.assertIsNone(geometry_runtime._geometry_save_pending)
        self.assertFalse(geometry_runtime._geometry_save_start_scheduled)
        worker_runtime.stop.assert_called_once_with(
            blocking=False,
            wait_timeout_ms=1000,
            log_fn=runtime.log,
            warning_prefix="window geometry save worker",
        )
        worker_runtime.cancel.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
