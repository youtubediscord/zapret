from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class StatusMessageContractTests(unittest.TestCase):
    def test_ui_state_store_remembers_last_status_message(self) -> None:
        from app.state_store import MainWindowStateStore

        store = MainWindowStateStore()
        changes: list[tuple[str, frozenset[str]]] = []
        store.subscribe(
            lambda state, fields: changes.append((state.last_status_message, fields)),
            fields={"last_status_message"},
        )

        self.assertTrue(store.set_last_status_message("Проверка обновлений..."))

        self.assertEqual(store.snapshot().last_status_message, "Проверка обновлений...")
        self.assertEqual(changes, [("Проверка обновлений...", frozenset({"last_status_message"}))])

    def test_window_set_status_sends_text_to_bound_status_message_sink(self) -> None:
        from main.window_actions import WindowActionsMixin

        class Window(WindowActionsMixin):
            pass

        window = Window()
        messages: list[str] = []
        window.bind_status_message_sink(messages.append)

        with patch("main.window_actions.log"):
            window.set_status("Блокировка MAX включена")

        self.assertEqual(messages, ["Блокировка MAX включена"])

    def test_window_open_folder_runs_through_worker(self) -> None:
        import inspect

        from main.window_actions import WindowActionsMixin
        from main import window_action_workers

        open_source = "\n".join(
            (
                inspect.getsource(WindowActionsMixin.bind_open_folder_worker_factory),
                inspect.getsource(WindowActionsMixin.open_folder),
                inspect.getsource(WindowActionsMixin.create_open_folder_worker),
                inspect.getsource(WindowActionsMixin._start_open_folder_worker),
            )
        )
        worker_source = inspect.getsource(window_action_workers.WindowOpenFolderWorker.run)
        worker_init_params = inspect.signature(
            window_action_workers.WindowOpenFolderWorker.__init__
        ).parameters

        self.assertIn("create_open_folder_worker", open_source)
        self.assertIn("_open_folder_worker_factory", open_source)
        self.assertIn("OneShotWorkerRuntime", inspect.getsource(WindowActionsMixin._open_folder_runtime))
        self.assertIn("start_qthread_worker", open_source)
        self.assertNotIn("from main.commands import open_program_folder", open_source)
        self.assertNotIn("from main.window_action_workers import WindowOpenFolderWorker", open_source)
        self.assertNotIn("worker.start()", open_source)
        self.assertNotIn("worker.deleteLater()", open_source)
        self.assertNotIn("run_hidden(", open_source)
        self.assertIn("open_program_folder", worker_init_params)
        self.assertIn("self._open_program_folder", worker_source)
        self.assertNotIn("run_hidden", worker_source)
        self.assertNotIn("explorer.exe", worker_source)

    def test_window_open_folder_uses_shared_latest_worker_state(self) -> None:
        import inspect

        from main.window_actions import WindowActionsMixin
        from ui.latest_value_worker_state import LatestValueWorkerState

        class Window(WindowActionsMixin):
            pass

        window = Window()
        window._open_folder_runtime_instance = SimpleNamespace(is_running=Mock(return_value=False))

        open_source = inspect.getsource(WindowActionsMixin.open_folder)
        schedule_source = inspect.getsource(WindowActionsMixin._schedule_open_folder_worker_start)
        run_source = inspect.getsource(WindowActionsMixin._run_scheduled_open_folder_worker_start)

        self.assertIsInstance(window._open_folder_state_obj(), LatestValueWorkerState)
        self.assertIn("_open_folder_state_obj()", open_source)
        self.assertIn("_open_folder_state_obj()", schedule_source)
        self.assertIn("_open_folder_state_obj()", run_source)
        self.assertNotIn("getattr(self, \"_open_folder_start_scheduled\"", open_source)

    def test_window_open_folder_pending_restarts_after_event_loop_turn(self) -> None:
        import main.window_actions as window_actions

        from main.window_actions import WindowActionsMixin

        class Window(WindowActionsMixin):
            pass

        window = Window()
        window._open_folder_pending = True
        window._open_folder_start_scheduled = False
        window._open_folder_runtime_worker = None
        window._start_open_folder_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(window_actions, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            window._on_open_folder_worker_finished(object())

        window._start_open_folder_worker.assert_not_called()

        single_shot.call_args.args[1]()

        window._start_open_folder_worker.assert_called_once_with()

    def test_stale_window_open_folder_finish_does_not_restart_pending_open(self) -> None:
        import main.window_actions as window_actions

        from main.window_actions import WindowActionsMixin

        class Window(WindowActionsMixin):
            pass

        current_worker = object()
        window = Window()
        window._open_folder_pending = True
        window._open_folder_start_scheduled = False
        window._open_folder_runtime_worker = current_worker
        window._start_open_folder_worker = Mock()
        single_shot = Mock()

        with patch.object(window_actions, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            window._on_open_folder_worker_finished(object())

        single_shot.assert_not_called()
        window._start_open_folder_worker.assert_not_called()
        self.assertTrue(window._open_folder_pending)
        self.assertIs(window._open_folder_runtime_worker, current_worker)


if __name__ == "__main__":
    unittest.main()
