from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

import startup.single_instance as single_instance


class ShowEventTests(unittest.TestCase):
    def setUp(self) -> None:
        single_instance._show_event_handle = None

    def tearDown(self) -> None:
        single_instance._show_event_handle = None

    def test_create_show_event_stores_handle_and_is_idempotent(self) -> None:
        kernel32 = Mock()
        kernel32.CreateEventW.return_value = 42

        with patch.object(single_instance, "_kernel32", return_value=kernel32):
            self.assertEqual(single_instance.create_show_event(), 42)
            self.assertEqual(single_instance.create_show_event(), 42)

        kernel32.CreateEventW.assert_called_once_with(
            None, False, False, single_instance.SHOW_EVENT_NAME
        )
        self.assertEqual(single_instance._show_event_handle, 42)

    def test_create_show_event_returns_none_on_failure(self) -> None:
        kernel32 = Mock()
        kernel32.CreateEventW.return_value = 0

        with patch.object(single_instance, "_kernel32", return_value=kernel32):
            self.assertIsNone(single_instance.create_show_event())

        self.assertIsNone(single_instance._show_event_handle)

    def test_signal_show_event_returns_false_when_event_missing(self) -> None:
        kernel32 = Mock()
        kernel32.OpenEventW.return_value = 0

        with patch.object(single_instance, "_kernel32", return_value=kernel32):
            self.assertFalse(single_instance.signal_show_event())

        kernel32.SetEvent.assert_not_called()

    def test_signal_show_event_sets_and_closes_handle(self) -> None:
        kernel32 = Mock()
        kernel32.OpenEventW.return_value = 5
        kernel32.SetEvent.return_value = 1

        with patch.object(single_instance, "_kernel32", return_value=kernel32):
            self.assertTrue(single_instance.signal_show_event())

        kernel32.OpenEventW.assert_called_once_with(
            single_instance.EVENT_MODIFY_STATE, False, single_instance.SHOW_EVENT_NAME
        )
        kernel32.SetEvent.assert_called_once_with(5)
        kernel32.CloseHandle.assert_called_once_with(5)

    def test_signal_show_event_closes_handle_even_when_set_fails(self) -> None:
        kernel32 = Mock()
        kernel32.OpenEventW.return_value = 5
        kernel32.SetEvent.return_value = 0

        with patch.object(single_instance, "_kernel32", return_value=kernel32):
            self.assertFalse(single_instance.signal_show_event())

        kernel32.CloseHandle.assert_called_once_with(5)


class ShowEventWatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        single_instance._show_event_handle = None

    def tearDown(self) -> None:
        single_instance._show_event_handle = None

    def test_watcher_invokes_callback_per_signal_and_stops_on_failure(self) -> None:
        results = iter(
            [
                single_instance.WAIT_OBJECT_0,
                single_instance.WAIT_OBJECT_0,
                0xFFFFFFFF,  # WAIT_FAILED
            ]
        )
        received: list[str] = []

        thread = single_instance.start_show_event_watcher(
            lambda: received.append("show"),
            wait_fn=lambda: next(results),
        )
        self.assertIsNotNone(thread)
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(received, ["show", "show"])

    def test_watcher_stops_on_abandoned_wait(self) -> None:
        WAIT_ABANDONED = 0x80
        thread = single_instance.start_show_event_watcher(
            lambda: self.fail("callback не должен вызываться"),
            wait_fn=lambda: WAIT_ABANDONED,
        )
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_watcher_requires_created_event(self) -> None:
        self.assertIsNone(single_instance.start_show_event_watcher(lambda: None))


class ShellSecondInstanceTests(unittest.TestCase):
    """Ветка already_running в shell_bootstrap: MessageBox показывается только
    при ручном запуске с недоставленным сигналом."""

    def _run_bootstrap(self, argv: list[str], *, signal_delivered: bool):
        from main import shell

        fake_ctypes = Mock()
        with (
            patch.object(shell, "is_admin", return_value=True),
            patch.object(shell, "ctypes", fake_ctypes),
            patch("startup.single_instance.create_mutex", return_value=(1, True)),
            patch(
                "startup.single_instance.signal_show_event",
                return_value=signal_delivered,
            ),
        ):
            with self.assertRaises(SystemExit) as ctx:
                shell.shell_bootstrap(argv)

        self.assertEqual(ctx.exception.code, 0)
        return fake_ctypes.windll.user32.MessageBoxW

    def test_no_messagebox_when_signal_delivered(self) -> None:
        message_box = self._run_bootstrap(["zapret.exe"], signal_delivered=True)
        message_box.assert_not_called()

    def test_no_messagebox_for_tray_launch_even_without_signal(self) -> None:
        message_box = self._run_bootstrap(
            ["zapret.exe", "--tray"], signal_delivered=False
        )
        message_box.assert_not_called()

    def test_messagebox_for_manual_launch_without_signal(self) -> None:
        message_box = self._run_bootstrap(["zapret.exe"], signal_delivered=False)
        message_box.assert_called_once()

    def test_first_instance_creates_show_event_right_after_mutex(self) -> None:
        from main import shell

        calls: list[str] = []
        with (
            patch.object(shell, "is_admin", return_value=True),
            patch.object(shell, "ctypes", Mock()),
            patch(
                "startup.single_instance.create_mutex",
                side_effect=lambda name: calls.append("mutex") or (1, False),
            ),
            patch(
                "startup.single_instance.create_show_event",
                side_effect=lambda: calls.append("event") or 42,
            ),
            patch.object(shell, "atexit", Mock()),
        ):
            start_in_tray = shell.shell_bootstrap(["zapret.exe", "--tray"])

        self.assertTrue(start_in_tray)
        self.assertEqual(calls, ["mutex", "event"])


if __name__ == "__main__":
    unittest.main()
