from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ExternalOpenUrlWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, url: str, open_url_fn=None, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._url = str(url or "").strip()
        self._open_url_fn = open_url_fn

    def run(self) -> None:
        import app.external_commands as external_commands

        try:
            result = external_commands.open_url(self._url, open_url_fn=self._open_url_fn)
        except Exception as exc:
            log(f"ExternalOpenUrlWorker: не удалось открыть ссылку: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


__all__ = ["ExternalOpenUrlWorker"]
