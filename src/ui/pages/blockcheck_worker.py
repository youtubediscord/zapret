"""Background worker for Blockcheck page."""

from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class BlockcheckWorker(QObject):
    """Worker that emits Qt signals from a background daemon thread."""

    target_started = pyqtSignal(str, int, int)
    test_result = pyqtSignal(object)
    target_complete = pyqtSignal(object)
    progress = pyqtSignal(int, int, str)
    phase_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, mode: str = "full", extra_domains: list[str] | None = None,
                 skip_preflight_failed: bool = False, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._extra_domains = extra_domains
        self._skip_preflight_failed = skip_preflight_failed
        self._runner = None
        self._cancelled = False
        self._bg_thread: threading.Thread | None = None

    def start(self):
        self._cancelled = False
        self._bg_thread = threading.Thread(
            target=self._run_in_thread, daemon=True, name="blockcheck-worker",
        )
        self._bg_thread.start()

    def _run_in_thread(self):
        try:
            from blockcheck.runner import BlockcheckRunner
            self._runner = BlockcheckRunner(
                mode=self._mode,
                callback=self,
                extra_domains=self._extra_domains,
                skip_preflight_failed=self._skip_preflight_failed,
            )
            report = self._runner.run()
            self.finished.emit(report)
        except Exception as e:
            logger.exception("BlockcheckWorker crashed")
            self.log_message.emit(f"ERROR: {e}")
            self.finished.emit(None)

    def stop(self):
        self._cancelled = True
        if self._runner:
            self._runner.cancel()

    @property
    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()

    def on_target_started(self, name, index, total):
        self.target_started.emit(name, index, total)

    def on_test_result(self, result):
        self.test_result.emit(result)

    def on_target_complete(self, result):
        self.target_complete.emit(result)

    def on_progress(self, current, total, message):
        self.progress.emit(current, total, message)

    def on_phase_change(self, phase):
        self.phase_changed.emit(phase)

    def on_log(self, message):
        self.log_message.emit(message)

    def is_cancelled(self):
        return self._cancelled
