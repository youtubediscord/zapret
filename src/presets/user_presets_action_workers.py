from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class UserPresetActivateWorker(QThread):
    activated = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, actions_api, *, file_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self.actions_api = actions_api
        self._file_name = str(file_name or "").strip()
        self._display_name = str(display_name or self._file_name).strip()

    def run(self) -> None:
        try:
            result = self.actions_api.activate_preset(
                file_name=self._file_name,
                display_name=self._display_name,
            )
        except Exception as exc:
            log(f"UserPresetActivateWorker: не удалось активировать preset: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.activated.emit(self._request_id, result)


class UserPresetItemActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        actions_api,
        *,
        action: str,
        file_name: str,
        display_name: str,
        file_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self.actions_api = actions_api
        self._action = str(action or "").strip()
        self._file_name = str(file_name or "").strip()
        self._display_name = str(display_name or self._file_name).strip()
        self._file_path = str(file_path or "").strip()

    def run(self) -> None:
        try:
            if self._action == "duplicate":
                result = self.actions_api.duplicate_preset(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "reset":
                result = self.actions_api.reset_preset_to_builtin(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "delete":
                result = self.actions_api.delete_preset(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "export":
                result = self.actions_api.export_preset(
                    file_name=self._file_name,
                    file_path=self._file_path,
                    display_name=self._display_name,
                )
            else:
                raise ValueError(f"Неизвестное действие preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetItemActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc))
            return
        context = {
            "file_name": self._file_name,
            "display_name": self._display_name,
            "file_path": self._file_path,
        }
        self.completed.emit(self._request_id, self._action, result, context)


class UserPresetBulkActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        actions_api,
        *,
        action: str,
        file_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self.actions_api = actions_api
        self._action = str(action or "").strip()
        self._file_path = str(file_path or "").strip()

    def run(self) -> None:
        context = {"file_path": self._file_path}
        try:
            if self._action == "import":
                result = self.actions_api.import_preset_from_file(file_path=self._file_path)
            elif self._action == "reset_all":
                result = self.actions_api.reset_all_presets()
            else:
                raise ValueError(f"Неизвестное массовое действие preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetBulkActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class UserPresetEditActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        actions_api,
        *,
        action: str,
        name: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self.actions_api = actions_api
        self._action = str(action or "").strip()
        self._name = str(name or "").strip()
        self._current_name = str(current_name or "").strip()
        self._new_name = str(new_name or "").strip()
        self._from_current = bool(from_current)

    def run(self) -> None:
        context = {
            "name": self._name,
            "current_name": self._current_name,
            "new_name": self._new_name,
            "from_current": self._from_current,
        }
        try:
            if self._action == "create":
                result = self.actions_api.create_preset(
                    name=self._name,
                    from_current=self._from_current,
                )
            elif self._action == "rename":
                result = self.actions_api.rename_preset(
                    current_name=self._current_name,
                    new_name=self._new_name,
                )
            else:
                raise ValueError(f"Неизвестное действие редактирования preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetEditActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class UserPresetStorageActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        storage_api,
        *,
        action: str,
        name: str = "",
        display_name: str = "",
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self.storage_api = storage_api
        self._action = str(action or "").strip()
        self._name = str(name or "").strip()
        self._display_name = str(display_name or self._name).strip()
        self._direction = int(direction or 0)
        self._cached_metadata = cached_metadata
        self._source_kind = str(source_kind or "").strip()
        self._source_id = str(source_id or "").strip()
        self._destination_kind = str(destination_kind or "").strip()
        self._destination_id = str(destination_id or "").strip()
        self._destination_folder_key = str(destination_folder_key or "").strip()

    def run(self) -> None:
        context = {
            "name": self._name,
            "display_name": self._display_name,
            "direction": self._direction,
            "source_kind": self._source_kind,
            "source_id": self._source_id,
            "destination_kind": self._destination_kind,
            "destination_id": self._destination_id,
            "destination_folder_key": self._destination_folder_key,
        }
        storage_api = self.storage_api
        try:
            if self._action == "pin":
                result = storage_api.toggle_preset_pin(
                    self._name,
                    display_name=self._display_name,
                )
            elif self._action == "move_step":
                result = storage_api.move_preset_by_step(
                    self._name,
                    self._direction,
                    cached_metadata=self._cached_metadata,
                )
            elif self._action == "drop":
                result = storage_api.move_preset_on_drop(
                    source_kind=self._source_kind,
                    source_id=self._source_id,
                    destination_kind=self._destination_kind,
                    destination_id=self._destination_id,
                    destination_folder_key=self._destination_folder_key,
                )
            else:
                raise ValueError(f"Неизвестное действие списка preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetStorageActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


__all__ = [
    "UserPresetActivateWorker",
    "UserPresetBulkActionWorker",
    "UserPresetEditActionWorker",
    "UserPresetItemActionWorker",
    "UserPresetStorageActionWorker",
]
