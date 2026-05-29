from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class BlobsLoadWorker(QThread):
    loaded = pyqtSignal(int, dict, bool)
    failed = pyqtSignal(int, str, bool)

    def __init__(self, request_id: int, *, reload: bool = False, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._reload = bool(reload)

    def run(self) -> None:
        import blobs.public as blobs_public

        try:
            if self._reload:
                blobs_info = blobs_public.reload_blobs()
            else:
                blobs_info = blobs_public.get_blobs_info()
        except Exception as exc:
            log(f"BlobsLoadWorker: не удалось загрузить blobs: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc), self._reload)
            return
        self.loaded.emit(self._request_id, dict(blobs_info or {}), self._reload)


class BlobActionWorker(QThread):
    completed = pyqtSignal(int, str, bool, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        name: str = "",
        blob_type: str = "",
        value: str = "",
        description: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._name = str(name or "").strip()
        self._blob_type = str(blob_type or "").strip()
        self._value = str(value or "")
        self._description = str(description or "")

    def run(self) -> None:
        context = {
            "name": self._name,
            "type": self._blob_type,
            "value": self._value,
            "description": self._description,
        }
        try:
            import blobs.public as blobs_public

            if self._action == "save":
                result = bool(
                    blobs_public.save_user_blob(
                        self._name,
                        self._blob_type,
                        self._value,
                        self._description,
                    )
                )
            elif self._action == "delete":
                result = bool(blobs_public.delete_user_blob(self._name))
            else:
                raise ValueError(f"Неизвестное действие blob: {self._action}")
        except Exception as exc:
            log(f"BlobActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class BlobOpenActionWorker(QThread):
    completed = pyqtSignal(int, str)
    failed = pyqtSignal(int, str, str)

    def __init__(self, request_id: int, *, action: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()

    def run(self) -> None:
        try:
            import blobs.public as blobs_public

            if self._action == "bin_folder":
                blobs_public.open_bin_folder()
            elif self._action == "blobs_json":
                blobs_public.open_blobs_json()
            else:
                raise ValueError(f"Неизвестное действие открытия blob: {self._action}")
        except Exception as exc:
            log(f"BlobOpenActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        self.completed.emit(self._request_id, self._action)


__all__ = ["BlobActionWorker", "BlobOpenActionWorker", "BlobsLoadWorker"]
