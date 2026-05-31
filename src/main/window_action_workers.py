from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class WindowOpenFolderWorker(QThread):
    completed = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, *, open_program_folder, parent=None):
        super().__init__(parent)
        self._open_program_folder = open_program_folder

    def run(self) -> None:
        try:
            self._open_program_folder()
        except Exception as exc:
            log(f"WindowOpenFolderWorker: не удалось открыть папку программы: {exc}", "ERROR")
            self.failed.emit(str(exc))
            return
        self.completed.emit()


__all__ = ["WindowOpenFolderWorker"]
