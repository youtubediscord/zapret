from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProfileSetupLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, load_profile, profile_key: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()

    def run(self) -> None:
        try:
            payload = self._load_profile(self._profile_key)
        except Exception as exc:
            log(f"ProfileSetupLoadWorker: не удалось загрузить profile setup: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, payload)


class ProfileListFileLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        load_state,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_state = load_state
        self._profile_key = str(profile_key or "").strip()
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()

    def run(self) -> None:
        try:
            state = self._load_state(
                self._profile_key,
                filter_kind=self._filter_kind,
                filter_value=self._filter_value,
            )
        except Exception as exc:
            log(f"ProfileListFileLoadWorker: не удалось загрузить файл списка profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


class ProfileListFileValidationWorker(QThread):
    validated = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, validate_text, *, kind: str, text: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._validate_text = validate_text
        self._kind = str(kind or "").strip()
        self._text = str(text or "")

    def run(self) -> None:
        try:
            invalid_lines = self._validate_text(
                kind=self._kind,
                text=self._text,
            )
        except Exception as exc:
            log(f"ProfileListFileValidationWorker: не удалось проверить файл списка profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.validated.emit(self._request_id, self._kind, self._text, tuple(invalid_lines or ()))


class ProfileListFileSaveWorker(QThread):
    saved = pyqtSignal(int, object, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, save_text, load_profile, profile_key: str, text: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._save_text = save_text
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()
        self._text = str(text or "")

    def run(self) -> None:
        try:
            state = self._save_text(
                profile_key=self._profile_key,
                text=self._text,
            )
            payload = self._load_profile(self._profile_key)
        except Exception as exc:
            log(f"ProfileListFileSaveWorker: не удалось сохранить файл списка profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, state, payload)


class ProfileSettingsSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        controller,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()
        self._in_range = str(in_range or "").strip()
        self._out_range = str(out_range or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._controller.save_winws2_settings(
                profile_key=self._profile_key,
                filter_kind=self._filter_kind,
                filter_value=self._filter_value,
                in_range=self._in_range,
                out_range=self._out_range,
            )
            payload = self._controller.load(str(profile_key or self._profile_key))
        except Exception as exc:
            log(f"ProfileSettingsSaveWorker: не удалось сохранить настройки profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, str(profile_key or ""), payload)


class ProfileRawTextSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, profile_key: str, raw_text: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._raw_text = str(raw_text or "")

    def run(self) -> None:
        try:
            profile_key = self._controller.save_raw_profile_text(
                profile_key=self._profile_key,
                raw_text=self._raw_text,
            )
            payload = self._controller.load(str(profile_key or self._profile_key))
        except Exception as exc:
            log(f"ProfileRawTextSaveWorker: не удалось сохранить сырой текст profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, str(profile_key or ""), payload)


class ProfileEnabledSaveWorker(QThread):
    saved = pyqtSignal(int, str, bool, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        controller,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._enabled = bool(enabled)
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._controller.set_enabled(
                profile_key=self._profile_key,
                enabled=self._enabled,
                filter_kind=self._filter_kind,
                filter_value=self._filter_value,
            )
        except Exception as exc:
            log(f"ProfileEnabledSaveWorker: не удалось изменить состояние profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        payload = None
        clean_profile_key = str(profile_key or "").strip()
        if clean_profile_key:
            try:
                payload = self._controller.load(clean_profile_key)
            except Exception as exc:
                log(f"ProfileEnabledSaveWorker: не удалось обновить payload profile: {exc}", "DEBUG")
        self.saved.emit(self._request_id, clean_profile_key, self._enabled, payload)


class ProfilePresetProfileActionWorker(QThread):
    finished_action = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        profile_service,
        *,
        action: str,
        profile_key: str,
        enabled: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._service = profile_service
        self._action = str(action or "").strip()
        self._target_profile_key = str(profile_key or "").strip()
        self._enabled = enabled

    def run(self) -> None:
        try:
            if self._action == "set_enabled":
                result = self._service.set_profile_enabled(
                    self._target_profile_key,
                    bool(self._enabled),
                )
                if result and str(result or "").strip() != self._target_profile_key:
                    item = _profile_item_by_key(self._service, str(result or ""))
                    if item is not None:
                        result = {"profile_key": str(result or "").strip(), "profile_item": item}
            elif self._action == "duplicate":
                result = self._service.duplicate_profile(self._target_profile_key)
                item = _profile_item_by_key(self._service, str(result or ""))
                if item is not None:
                    result = {"profile_key": str(result or "").strip(), "profile_item": item}
            elif self._action == "delete":
                result = bool(self._service.delete_profile(self._target_profile_key))
            else:
                raise ValueError(f"Неизвестное действие profile: {self._action}")
        except Exception as exc:
            log(f"ProfilePresetProfileActionWorker: не удалось выполнить действие profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.finished_action.emit(self._request_id, self._action, self._target_profile_key, result)


class ProfilePresetProfileMoveWorker(QThread):
    moved = pyqtSignal(int, str, str, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        profile_service,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._service = profile_service
        self._action = str(action or "").strip()
        self._source_profile_key = str(source_profile_key or "").strip()
        self._destination_profile_key = str(destination_profile_key or "").strip()
        self._destination_group_key = str(destination_group_key or "").strip()

    def run(self) -> None:
        try:
            if self._action == "before":
                result = self._service.move_profile_before(
                    self._source_profile_key,
                    self._destination_profile_key,
                    destination_folder_key=self._destination_group_key,
                )
            elif self._action == "after":
                result = self._service.move_profile_after(
                    self._source_profile_key,
                    self._destination_profile_key,
                    destination_folder_key=self._destination_group_key,
                )
            elif self._action == "end":
                result = self._service.move_profile_to_end(self._source_profile_key)
            elif self._action == "folder":
                result = self._service.move_profile_to_folder(
                    self._source_profile_key,
                    self._destination_group_key,
                )
            else:
                raise ValueError(f"Неизвестное перемещение profile: {self._action}")
        except Exception as exc:
            log(f"ProfilePresetProfileMoveWorker: не удалось переместить profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.moved.emit(
            self._request_id,
            self._action,
            self._source_profile_key,
            self._destination_profile_key,
            self._destination_group_key,
            result,
        )


class ProfileUserProfileCreateWorker(QThread):
    created = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        profile,
        launch_method: str,
        *,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile = profile
        self._launch_method = str(launch_method or "").strip()
        self._name = str(name or "").strip()
        self._protocol = str(protocol or "").strip()
        self._ports = str(ports or "").strip()

    def run(self) -> None:
        try:
            profile_id = self._profile.create_user_profile(
                name=self._name,
                protocol=self._protocol,
                ports=self._ports,
            )
            created_item = self._created_profile_item(str(profile_id or ""))
        except Exception as exc:
            log(f"ProfileUserProfileCreateWorker: не удалось создать пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.created.emit(self._request_id, str(profile_id or ""), created_item)

    def _created_profile_item(self, profile_id: str):
        items = _user_profile_items(self._profile, self._launch_method, profile_id)
        return items[0] if items else None


class ProfileUserProfileUpdateWorker(QThread):
    updated = pyqtSignal(int, str, int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        controller,
        launch_method: str,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._launch_method = str(launch_method or "").strip()
        self._profile_id = str(profile_id or "").strip()
        self._name = str(name or "").strip()
        self._protocol = str(protocol or "").strip()
        self._ports = str(ports or "").strip()

    def run(self) -> None:
        try:
            changed = self._controller.update_user_profile(
                profile_id=self._profile_id,
                name=self._name,
                protocol=self._protocol,
                ports=self._ports,
            )
            updated_items = _user_profile_items(self._controller, self._launch_method, self._profile_id)
        except Exception as exc:
            log(f"ProfileUserProfileUpdateWorker: не удалось изменить пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.updated.emit(self._request_id, self._profile_id, int(changed or 0), updated_items)


class ProfileUserProfileDeleteWorker(QThread):
    deleted = pyqtSignal(int, str, int)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, *, profile_id: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_id = str(profile_id or "").strip()

    def run(self) -> None:
        try:
            changed = self._controller.delete_user_profile(profile_id=self._profile_id)
        except Exception as exc:
            log(f"ProfileUserProfileDeleteWorker: не удалось удалить пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.deleted.emit(self._request_id, self._profile_id, int(changed or 0))


def _user_profile_items(profile, launch_method: str, profile_id: str) -> tuple[object, ...]:
    clean_profile_id = str(profile_id or "").strip()
    if not clean_profile_id:
        return ()
    try:
        payload = profile.list_profiles(str(launch_method or "").strip())
    except Exception:
        return ()
    return tuple(
        item for item in tuple(getattr(payload, "items", ()) or ())
        if str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id
    )


def _profile_item_by_key(profile, profile_key: str, launch_method: str = ""):
    clean_key = str(profile_key or "").strip()
    if not clean_key:
        return None
    try:
        clean_method = str(launch_method or "").strip()
        payload = profile.list_profiles(clean_method) if clean_method else profile.list_profiles()
    except Exception:
        return None
    try:
        items = tuple(getattr(payload, "items", ()) or ())
    except Exception:
        return None
    for item in items:
        if str(getattr(item, "key", "") or "").strip() == clean_key:
            return item
    return None


class ProfileFolderActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        *,
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
        self._action = str(action or "").strip()
        self._folder_key = str(folder_key or "").strip()
        self._name = str(name or "").strip()
        self._direction = int(direction or 0)
        self._collapsed = bool(collapsed)
        self._context_extra = dict(context_extra or {})

    def run(self) -> None:
        from profile.folders import (
            create_profile_folder,
            delete_profile_folder,
            load_profile_folder_state,
            move_profile_folder_by_step,
            rename_profile_folder,
            reset_profile_folders,
            set_profile_folder_collapsed,
        )

        context = {
            "folder_key": self._folder_key,
            "name": self._name,
            "direction": self._direction,
            "collapsed": self._collapsed,
        }
        context.update(self._context_extra)
        try:
            if self._action == "load_state":
                result = load_profile_folder_state()
            elif self._action == "create":
                result = create_profile_folder(self._name)
            elif self._action == "rename":
                result = rename_profile_folder(self._folder_key, self._name)
            elif self._action == "delete":
                result = delete_profile_folder(self._folder_key)
            elif self._action == "move_step":
                result = move_profile_folder_by_step(self._folder_key, self._direction)
            elif self._action == "set_collapsed":
                result = set_profile_folder_collapsed(self._folder_key, self._collapsed)
            elif self._action == "reset":
                result = reset_profile_folders()
            else:
                raise ValueError(f"Неизвестное действие папки profile: {self._action}")
        except Exception as exc:
            log(f"ProfileFolderActionWorker: не удалось выполнить действие папки profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        if self._action != "load_state" and bool(result):
            try:
                context["folder_state"] = load_profile_folder_state()
            except Exception as exc:
                log(f"ProfileFolderActionWorker: не удалось обновить состояние папок profile: {exc}", "DEBUG")
        self.completed.emit(self._request_id, self._action, result, context)


class ProfileStrategyApplyWorker(QThread):
    applied = pyqtSignal(int, str, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, profile_key: str, strategy_id: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._strategy_id = str(strategy_id or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._controller.apply_strategy(
                profile_key=self._profile_key,
                strategy_id=self._strategy_id,
            )
        except Exception as exc:
            log(f"ProfileStrategyApplyWorker: не удалось применить готовую стратегию: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        if not profile_key:
            self.failed.emit(self._request_id, "Стратегия не применена")
            return
        payload = None
        try:
            payload = self._controller.load(str(profile_key))
        except Exception as exc:
            log(f"ProfileStrategyApplyWorker: не удалось загрузить обновлённый profile payload: {exc}", "DEBUG")
        self.applied.emit(self._request_id, self._profile_key, str(profile_key), self._strategy_id, payload)


class ProfileStrategyFeedbackSaveWorker(QThread):
    saved = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        controller,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._strategy_id = str(strategy_id or "").strip()
        self._rating = rating
        self._favorite = favorite

    def run(self) -> None:
        try:
            state = self._controller.set_strategy_feedback(
                profile_key=self._profile_key,
                rating=self._rating,
                favorite=self._favorite,
            )
        except Exception as exc:
            log(f"ProfileStrategyFeedbackSaveWorker: не удалось сохранить оценку стратегии: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, self._profile_key, self._strategy_id, state)
