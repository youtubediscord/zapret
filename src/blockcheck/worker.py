"""Background worker for Blockcheck page."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class BlockcheckWorker(QObject):
    """Worker that runs BlockCheck in a QThread owned by shared runtime."""

    run_log_started = pyqtSignal(object)
    test_result = pyqtSignal(object)
    target_complete = pyqtSignal(object)
    phase_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(
        self,
        mode: str = "full",
        extra_domains: list[str] | None = None,
        skip_preflight_failed: bool = False,
        *,
        start_run_log: Callable[[str, list[str]], object],
        append_run_log: Callable[[str | None, str], None],
        close_run_log: Callable[[str | None], None],
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._extra_domains = extra_domains
        self._skip_preflight_failed = skip_preflight_failed
        self._start_run_log = start_run_log
        self._append_run_log_action = append_run_log
        self._close_run_log_action = close_run_log
        self._runner = None
        self._cancelled = False
        self._run_log_file = None
        self._running = False

    def run(self):
        self._cancelled = False
        self._running = True
        report = None
        try:
            from blockcheck.runner import BlockcheckRunner

            log_state = self._start_run_log(self._mode, list(self._extra_domains or []))
            self._run_log_file = log_state.path
            self.run_log_started.emit(log_state.path)
            if not log_state.created:
                logger.warning("Failed to create blockcheck run log")

            self._runner = BlockcheckRunner(
                mode=self._mode,
                callback=self,
                extra_domains=self._extra_domains,
                skip_preflight_failed=self._skip_preflight_failed,
            )
            report = self._runner.run()
            if report is not None and not getattr(report, "cancelled", False):
                elapsed = getattr(report, "elapsed_seconds", 0.0)
                self._append_run_log(f"\nCompleted in {elapsed:.1f}s")
        except Exception as e:
            logger.exception("BlockcheckWorker crashed")
            self._append_run_log(f"ERROR: {e}")
            self.log_message.emit(f"ERROR: {e}")
        finally:
            try:
                self._close_run_log_action(self._run_log_file)
            except Exception:
                pass
            self._running = False
        self.finished.emit(report)

    def stop(self):
        self._cancelled = True
        if self._runner:
            self._runner.cancel()

    @property
    def is_running(self) -> bool:
        return bool(self._running)

    def on_target_started(self, name, index, total):
        _ = (name, index, total)

    def on_test_result(self, result):
        self.test_result.emit(result)

    def on_target_complete(self, result):
        self.target_complete.emit(result)

    def on_progress(self, current, total, message):
        _ = (current, total, message)

    def on_phase_change(self, phase):
        self._append_run_log(f"[PHASE] {phase}")
        self.phase_changed.emit(phase)

    def on_log(self, message):
        self._append_run_log(message)
        self.log_message.emit(message)

    def is_cancelled(self):
        return self._cancelled

    def _append_run_log(self, message: str) -> None:
        try:
            self._append_run_log_action(self._run_log_file, message)
        except Exception:
            pass
