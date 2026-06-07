from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _Signal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class _FakeThread:
    instances = []

    def __init__(self) -> None:
        self.started = _Signal()
        self.finished = _Signal()
        self.quit_called = False
        self.wait_called = False
        self.delete_later_called = False
        _FakeThread.instances.append(self)

    def start(self) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True

    def wait(self, *_args) -> bool:
        self.wait_called = True
        return True

    def deleteLater(self) -> None:
        self.delete_later_called = True


class _FakeWorker:
    def __init__(self) -> None:
        self.finished = _Signal()
        self.moved_to_thread = None
        self.delete_later_called = False

    def moveToThread(self, thread) -> None:
        self.moved_to_thread = thread

    def run(self) -> None:
        pass

    def deleteLater(self) -> None:
        self.delete_later_called = True


class WinwsRuntimeThreadRuntimeTests(unittest.TestCase):
    def test_worker_thread_cleanup_does_not_wait_in_finish_slot(self) -> None:
        from winws_runtime.runtime.thread_runtime import start_worker_thread

        owner = SimpleNamespace()
        worker = _FakeWorker()
        _FakeThread.instances = []

        with patch("winws_runtime.runtime.thread_runtime.QThread", _FakeThread):
            thread = start_worker_thread(
                owner,
                thread_attr="_thread",
                worker_attr="_worker",
                worker=worker,
            )

        worker.finished.emit(True, "")

        self.assertTrue(thread.quit_called)
        self.assertFalse(thread.wait_called)
        self.assertIsNone(owner._thread)
        self.assertIsNone(owner._worker)


if __name__ == "__main__":
    unittest.main()
