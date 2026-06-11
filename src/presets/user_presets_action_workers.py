from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class UserPresetActivateWorker(QThread):
    activated = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, activate_preset, *, file_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._activate_preset = activate_preset
        self._file_name = str(file_name or "").strip()
        self._display_name = str(display_name or self._file_name).strip()

    def run(self) -> None:
        try:
            result = self._activate_preset(
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
        duplicate_preset,
        reset_preset_to_builtin,
        delete_preset,
        export_preset,
        *,
        action: str,
        file_name: str,
        display_name: str,
        file_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._duplicate_preset = duplicate_preset
        self._reset_preset_to_builtin = reset_preset_to_builtin
        self._delete_preset = delete_preset
        self._export_preset = export_preset
        self._action = str(action or "").strip()
        self._file_name = str(file_name or "").strip()
        self._display_name = str(display_name or self._file_name).strip()
        self._file_path = str(file_path or "").strip()

    def run(self) -> None:
        try:
            if self._action == "duplicate":
                result = self._duplicate_preset(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "reset":
                result = self._reset_preset_to_builtin(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "delete":
                result = self._delete_preset(
                    file_name=self._file_name,
                    display_name=self._display_name,
                )
            elif self._action == "export":
                result = self._export_preset(
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
        import_preset_from_file,
        reset_all_presets,
        *,
        action: str,
        file_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._import_preset_from_file = import_preset_from_file
        self._reset_all_presets = reset_all_presets
        self._action = str(action or "").strip()
        self._file_path = str(file_path or "").strip()

    def run(self) -> None:
        context = {"file_path": self._file_path}
        try:
            if self._action == "import":
                result = self._import_preset_from_file(file_path=self._file_path)
            elif self._action == "reset_all":
                result = self._reset_all_presets()
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
        create_preset,
        rename_preset,
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
        self._create_preset = create_preset
        self._rename_preset = rename_preset
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
                result = self._create_preset(
                    name=self._name,
                    from_current=self._from_current,
                )
            elif self._action == "rename":
                result = self._rename_preset(
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


class UserPresetOpenFolderWorker(QThread):
    completed = pyqtSignal(int)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, open_folder, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._open_folder = open_folder

    def run(self) -> None:
        try:
            self._open_folder()
        except Exception as exc:
            log(f"UserPresetOpenFolderWorker: не удалось открыть папку preset: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id)


class UserPresetLinkActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(self, request_id: int, open_presets_info, open_new_configs_post, *, action: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._open_presets_info = open_presets_info
        self._open_new_configs_post = open_new_configs_post
        self._action = str(action or "").strip()

    def run(self) -> None:
        context = {"action": self._action}
        try:
            if self._action == "info":
                result = self._open_presets_info()
            elif self._action == "new_configs":
                result = self._open_new_configs_post()
            else:
                raise ValueError(f"Неизвестное действие ссылки preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetLinkActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class UserPresetStorageActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        toggle_preset_pin,
        set_preset_rating,
        move_preset_by_step,
        move_preset_on_drop,
        load_folder_state,
        *,
        action: str,
        name: str = "",
        display_name: str = "",
        rating: int = 0,
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
        self._toggle_preset_pin = toggle_preset_pin
        self._set_preset_rating = set_preset_rating
        self._move_preset_by_step = move_preset_by_step
        self._move_preset_on_drop = move_preset_on_drop
        self._load_folder_state = load_folder_state
        self._action = str(action or "").strip()
        self._name = str(name or "").strip()
        self._display_name = str(display_name or self._name).strip()
        self._rating = int(rating or 0)
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
            "rating": self._rating,
            "direction": self._direction,
            "source_kind": self._source_kind,
            "source_id": self._source_id,
            "destination_kind": self._destination_kind,
            "destination_id": self._destination_id,
            "destination_folder_key": self._destination_folder_key,
        }
        try:
            if self._action == "pin":
                result = self._toggle_preset_pin(
                    self._name,
                    display_name=self._display_name,
                )
            elif self._action == "rating":
                result = self._set_preset_rating(
                    self._name,
                    self._rating,
                    display_name=self._display_name,
                )
            elif self._action == "move_step":
                result = self._move_preset_by_step(
                    self._name,
                    self._direction,
                    cached_metadata=self._cached_metadata,
                )
                if isinstance(result, dict):
                    for key in ("destination_kind", "destination_id", "destination_folder_key"):
                        if str(result.get(key) or "").strip():
                            context[key] = str(result.get(key) or "").strip()
                    result = bool(result.get("ok", True))
            elif self._action == "drop":
                result = self._move_preset_on_drop(
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
        if self._load_folder_state is not None and (self._action == "pin" or bool(result)):
            try:
                context["folder_state"] = self._load_folder_state()
            except Exception as exc:
                log(f"UserPresetStorageActionWorker: не удалось обновить состояние папок preset: {exc}", "DEBUG")
        self.completed.emit(self._request_id, self._action, result, context)


class UserPresetFolderActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        load_preset_folder_state,
        create_preset_folder,
        rename_preset_folder,
        delete_preset_folder,
        move_preset_folder_by_step,
        set_preset_folder_collapsed,
        reset_preset_folders,
        *,
        scope_key: str,
        action: str,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        context_extra: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_preset_folder_state = load_preset_folder_state
        self._create_preset_folder = create_preset_folder
        self._rename_preset_folder = rename_preset_folder
        self._delete_preset_folder = delete_preset_folder
        self._move_preset_folder_by_step = move_preset_folder_by_step
        self._set_preset_folder_collapsed = set_preset_folder_collapsed
        self._reset_preset_folders = reset_preset_folders
        self._scope_key = str(scope_key or "").strip()
        self._action = str(action or "").strip()
        self._folder_key = str(folder_key or "").strip()
        self._name = str(name or "").strip()
        self._direction = int(direction or 0)
        self._collapsed = bool(collapsed)
        self._context_extra = dict(context_extra or {})

    def run(self) -> None:
        context = {
            "scope_key": self._scope_key,
            "folder_key": self._folder_key,
            "name": self._name,
            "direction": self._direction,
            "collapsed": self._collapsed,
        }
        context.update(self._context_extra)
        try:
            if self._action == "load_state":
                result = self._load_preset_folder_state(self._scope_key)
            elif self._action == "create":
                result = self._create_preset_folder(self._scope_key, self._name)
            elif self._action == "rename":
                result = self._rename_preset_folder(self._scope_key, self._folder_key, self._name)
            elif self._action == "delete":
                result = self._delete_preset_folder(self._scope_key, self._folder_key)
            elif self._action in {"move", "move_step"}:
                result = self._move_preset_folder_by_step(self._scope_key, self._folder_key, self._direction)
            elif self._action == "set_collapsed":
                result = self._set_preset_folder_collapsed(self._scope_key, self._folder_key, self._collapsed)
            elif self._action == "toggle_collapsed":
                state = self._load_preset_folder_state(self._scope_key)
                folder = state.get("folders", {}).get(self._folder_key) if isinstance(state, dict) else None
                if not isinstance(folder, dict) and self._folder_key != "pinned":
                    result = False
                else:
                    collapsed = not bool(folder.get("collapsed", False)) if isinstance(folder, dict) else True
                    context["collapsed"] = collapsed
                    result = self._set_preset_folder_collapsed(self._scope_key, self._folder_key, collapsed)
            elif self._action == "reset":
                result = self._reset_preset_folders(self._scope_key)
            else:
                raise ValueError(f"Неизвестное действие папки preset: {self._action}")
        except Exception as exc:
            log(f"UserPresetFolderActionWorker: действие {self._action} не выполнено: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        if self._action != "load_state" and bool(result):
            try:
                context["folder_state"] = self._load_preset_folder_state(self._scope_key)
            except Exception as exc:
                log(f"UserPresetFolderActionWorker: не удалось обновить состояние папок preset: {exc}", "DEBUG")
        self.completed.emit(self._request_id, self._action, result, context)


__all__ = [
    "UserPresetActivateWorker",
    "UserPresetBulkActionWorker",
    "UserPresetEditActionWorker",
    "UserPresetFolderActionWorker",
    "UserPresetItemActionWorker",
    "UserPresetLinkActionWorker",
    "UserPresetOpenFolderWorker",
    "UserPresetStorageActionWorker",
]
