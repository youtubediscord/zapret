from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


class _Signal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self) -> None:
        for callback in list(self._callbacks):
            callback()


class _FakeProcessMonitor:
    instances = []

    def __init__(self, *, interval_ms: int) -> None:
        self.interval_ms = interval_ms
        self.processDetailsChanged = _Signal()
        self.finished = _Signal()
        self.stop = Mock()
        self.start = Mock()
        _FakeProcessMonitor.instances.append(self)


class ProcessMonitorNonblockingTests(unittest.TestCase):
    def test_process_monitor_stop_does_not_wait_for_sleeping_thread(self) -> None:
        from winws_runtime.monitoring.process_monitor import ProcessMonitorThread

        monitor = ProcessMonitorThread(interval_ms=2000)
        monitor.wait = Mock(return_value=True)
        monitor.quit = Mock()

        monitor.stop()

        self.assertFalse(monitor._running)
        monitor.quit.assert_called_once()
        monitor.wait.assert_not_called()

    def test_reinitializing_process_monitor_keeps_old_thread_until_finished(self) -> None:
        from winws_runtime.monitoring import process_monitor_manager

        _FakeProcessMonitor.instances = []
        manager = process_monitor_manager.ProcessMonitorManager(observe_process_details=lambda _details: None)

        with patch(
            "winws_runtime.monitoring.process_monitor.ProcessMonitorThread",
            _FakeProcessMonitor,
        ):
            manager.initialize_process_monitor()
            first = manager.process_monitor
            manager.initialize_process_monitor()

        self.assertIsNot(first, manager.process_monitor)
        first.stop.assert_called_once()
        self.assertIn(first, manager._retired_process_monitors)

        first.finished.emit()

        self.assertNotIn(first, manager._retired_process_monitors)


if __name__ == "__main__":
    unittest.main()
