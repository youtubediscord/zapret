from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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
                inspect.getsource(WindowActionsMixin.open_folder),
                inspect.getsource(WindowActionsMixin._start_open_folder_worker),
            )
        )
        worker_source = inspect.getsource(window_action_workers.WindowOpenFolderWorker.run)
        worker_init_params = inspect.signature(
            window_action_workers.WindowOpenFolderWorker.__init__
        ).parameters

        self.assertIn("create_open_folder_worker", open_source)
        self.assertIn("OneShotWorkerRuntime", inspect.getsource(WindowActionsMixin._open_folder_runtime))
        self.assertIn("start_qthread_worker", open_source)
        self.assertNotIn("worker.start()", open_source)
        self.assertNotIn("worker.deleteLater()", open_source)
        self.assertNotIn("run_hidden(", open_source)
        self.assertIn("open_program_folder", worker_init_params)
        self.assertIn("self._open_program_folder", worker_source)
        self.assertNotIn("run_hidden", worker_source)
        self.assertNotIn("explorer.exe", worker_source)


if __name__ == "__main__":
    unittest.main()
