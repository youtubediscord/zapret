import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class StrategyScanWorker(QObject):
    """Bridge synchronous StrategyScanner execution to Qt signals."""

    strategy_started = pyqtSignal(str, int, int)
    strategy_result = pyqtSignal(object)
    scan_log = pyqtSignal(str)
    phase_changed = pyqtSignal(str)
    scan_finished = pyqtSignal(object)

    def __init__(
        self,
        target: str,
        mode: str = "quick",
        start_index: int = 0,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
        *,
        runtime_feature,
        parent=None,
    ):
        super().__init__(parent)
        self._target = target
        self._mode = mode
        self._scan_protocol = scan_protocol
        self._udp_games_scope = udp_games_scope
        self._runtime_feature = runtime_feature
        try:
            self._start_index = max(0, int(start_index))
        except Exception:
            self._start_index = 0
        self._scanner = None
        self._cancelled = False
        self._bg_thread: threading.Thread | None = None

    def start(self):
        self._cancelled = False
        self._bg_thread = threading.Thread(
            target=self._run_in_thread,
            daemon=True,
            name="strategy-scan-worker",
        )
        self._bg_thread.start()

    def _run_in_thread(self):
        try:
            from blockcheck.strategy_scanner import StrategyScanner

            self._scanner = StrategyScanner(
                target=self._target,
                mode=self._mode,
                start_index=self._start_index,
                callback=self,
                scan_protocol=self._scan_protocol,
                udp_games_scope=self._udp_games_scope,
                runtime_feature=self._runtime_feature,
            )
            report = self._scanner.run()
            self.scan_finished.emit(report)
        except Exception as e:
            logger.exception("StrategyScanWorker crashed")
            self.scan_log.emit(f"ERROR: {e}")
            self.scan_finished.emit(None)

    def stop(self):
        self._cancelled = True
        if self._scanner:
            self._scanner.cancel()

    @property
    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()

    def on_strategy_started(self, name, index, total):
        self.strategy_started.emit(name, index, total)

    def on_strategy_result(self, result):
        self.strategy_result.emit(result)

    def on_log(self, message):
        self.scan_log.emit(message)

    def on_phase(self, phase):
        self.phase_changed.emit(phase)

    def is_cancelled(self):
        return self._cancelled
