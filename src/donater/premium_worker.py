from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class PremiumWorkerThread(QThread):
    """Simple background worker for Premium page tasks."""

    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, target, args=None):
        super().__init__()
        self.target = target
        self.args = args or ()

    def run(self):
        try:
            result = self.target(*self.args)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
