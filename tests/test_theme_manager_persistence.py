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


class ThemeManagerPersistenceTests(unittest.TestCase):
    def test_theme_persistence_runs_through_worker(self) -> None:
        from app.feature_facades.appearance import AppearanceFeature
        import settings.appearance_workers as appearance_workers
        import ui.theme as theme

        self.assertTrue(hasattr(appearance_workers, "ThemePersistWorker"))

        feature_source = inspect.getsource(AppearanceFeature)
        worker_source = inspect.getsource(appearance_workers.ThemePersistWorker.run)
        manager_init_source = inspect.getsource(theme.ThemeManager.__init__)
        apply_source = inspect.getsource(theme.ThemeManager._apply_css_only)
        request_source = inspect.getsource(theme.ThemeManager._request_theme_persist)
        start_source = inspect.getsource(theme.ThemeManager._start_theme_persist_worker)
        finished_source = inspect.getsource(theme.ThemeManager._on_theme_persist_finished)

        self.assertIn("create_theme_persist_worker", feature_source)
        self.assertIn("save_selected_theme=self.save_selected_theme", feature_source)
        self.assertIn("create_theme_persist_worker", manager_init_source)
        self.assertIn("_theme_persist_runtime = OneShotWorkerRuntime()", manager_init_source)
        self.assertIn("_create_theme_persist_worker", start_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertNotIn("ThemePersistWorker(", start_source)
        self.assertNotIn("worker.start()", start_source)
        self.assertNotIn("settings_store", worker_source)
        self.assertIn("_request_theme_persist", apply_source)
        self.assertNotIn("set_selected_theme(clean)", apply_source)
        self.assertIn("_theme_persist_pending", request_source)
        self.assertIn("_theme_persist_pending", finished_source)

    def test_pending_theme_persist_restarts_after_event_loop_turn(self) -> None:
        import ui.theme as theme

        worker = object()
        manager = theme.ThemeManager.__new__(theme.ThemeManager)
        manager._theme_persist_pending = "dark"
        manager._theme_persist_runtime_worker = worker
        manager._cleanup_in_progress = False
        manager._start_theme_persist_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(theme, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            theme.ThemeManager._on_theme_persist_finished(manager, worker)

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        manager._start_theme_persist_worker.assert_not_called()

        single_shot.call_args.args[1]()

        manager._start_theme_persist_worker.assert_called_once_with("dark")

    def test_stale_theme_persist_finish_does_not_restart_pending_persist(self) -> None:
        import ui.theme as theme

        manager = theme.ThemeManager.__new__(theme.ThemeManager)
        manager._theme_persist_pending = "dark"
        manager._theme_persist_runtime_worker = object()
        manager._cleanup_in_progress = False
        manager._schedule_theme_persist_worker_start = Mock()

        theme.ThemeManager._on_theme_persist_finished(manager, object())

        manager._schedule_theme_persist_worker_start.assert_not_called()
        self.assertEqual(manager._theme_persist_pending, "dark")

    def test_theme_build_runs_through_runtime(self) -> None:
        import ui.one_shot_worker_runtime as one_shot_runtime
        import ui.theme as theme

        manager_init_source = inspect.getsource(theme.ThemeManager.__init__)
        apply_source = inspect.getsource(theme.ThemeManager.apply_theme_async)
        cleanup_source = inspect.getsource(theme.ThemeManager.cleanup)
        runtime_source = inspect.getsource(one_shot_runtime.OneShotWorkerRuntime.start_qobject_worker)

        self.assertIn("OneShotWorkerRuntime", manager_init_source)
        self.assertIn("_active_theme_build_jobs", manager_init_source)
        self.assertIn("start_qobject_worker", apply_source)
        self.assertIn('failed_signal_name="error"', apply_source)
        self.assertIn("theme build worker", cleanup_source)
        self.assertNotIn("QThread", apply_source)
        self.assertNotIn("moveToThread", apply_source)
        self.assertNotIn("thread.start()", apply_source)
        self.assertIn("failed_signal.connect(thread.quit)", runtime_source)
        self.assertIn("failed_signal.connect(worker.deleteLater)", runtime_source)

    def test_cleanup_does_not_wait_for_theme_build_workers(self) -> None:
        import ui.theme as theme

        build_runtime = SimpleNamespace(stop=Mock(), cancel=Mock())
        persist_runtime = SimpleNamespace(stop=Mock(), cancel=Mock())
        manager = theme.ThemeManager.__new__(theme.ThemeManager)
        manager._cleanup_in_progress = False
        manager._active_theme_build_jobs = {1: build_runtime}
        manager._cleanup_theme_build_thread = Mock()
        manager._theme_persist_pending = "dark"
        manager._theme_persist_start_scheduled = True
        manager._theme_persist_runtime_worker = object()
        manager._theme_persist_runtime = persist_runtime

        theme.ThemeManager.cleanup(manager)

        self.assertTrue(manager._cleanup_in_progress)
        build_runtime.stop.assert_called_once_with(
            blocking=False,
            wait_timeout_ms=1000,
            log_fn=theme.log,
            warning_prefix="theme build worker",
        )
        build_runtime.cancel.assert_called_once_with()
        persist_runtime.stop.assert_called_once_with(
            blocking=False,
            wait_timeout_ms=1000,
            log_fn=theme.log,
            warning_prefix="theme persist worker",
        )
        persist_runtime.cancel.assert_called_once_with()
        self.assertIsNone(manager._theme_persist_pending)
        self.assertFalse(manager._theme_persist_start_scheduled)
        self.assertIsNone(manager._theme_persist_runtime_worker)


if __name__ == "__main__":
    unittest.main()
