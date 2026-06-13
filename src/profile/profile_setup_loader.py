from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log
from profile.list_file_editor import count_profile_list_entries
from profile.setup_apply_signature import profile_setup_payload_apply_signature


def _profile_setup_load_result(payload, *, apply_result=None):
    return ProfileSetupLoadResult(payload=payload, apply_result=apply_result)


class ProfileSetupLoadResult:
    def __init__(self, *, payload, apply_signature=None, apply_result=None) -> None:
        self.payload = payload
        self.apply_result = apply_result
        self.apply_signature = (
            tuple(apply_signature)
            if apply_signature is not None
            else profile_setup_payload_apply_signature(payload)
        )


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
        self.loaded.emit(self._request_id, _profile_setup_load_result(payload))


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
            result = {
                "invalid_lines": tuple(invalid_lines or ()),
                "entries_count": count_profile_list_entries(self._text),
            }
        except Exception as exc:
            log(f"ProfileListFileValidationWorker: не удалось проверить файл списка profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.validated.emit(self._request_id, self._kind, self._text, result)


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
        self.saved.emit(self._request_id, state, _profile_setup_load_result(payload))


class ProfileSettingsSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        save_settings,
        load_profile,
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
        self._save_settings = save_settings
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()
        self._in_range = str(in_range or "").strip()
        self._out_range = str(out_range or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._save_settings(
                profile_key=self._profile_key,
                filter_kind=self._filter_kind,
                filter_value=self._filter_value,
                in_range=self._in_range,
                out_range=self._out_range,
            )
            payload = self._load_profile(str(profile_key or self._profile_key))
        except Exception as exc:
            log(f"ProfileSettingsSaveWorker: не удалось сохранить настройки profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, str(profile_key or ""), _profile_setup_load_result(payload))


class ProfileRawTextSaveWorker(QThread):
    saved = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, save_raw_text, load_profile, profile_key: str, raw_text: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._save_raw_text = save_raw_text
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()
        self._raw_text = str(raw_text or "")

    def run(self) -> None:
        try:
            profile_key = self._save_raw_text(
                profile_key=self._profile_key,
                raw_text=self._raw_text,
            )
            payload = self._load_profile(str(profile_key or self._profile_key))
        except Exception as exc:
            log(f"ProfileRawTextSaveWorker: не удалось сохранить сырой текст profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, str(profile_key or ""), _profile_setup_load_result(payload))


class ProfileEnabledSaveWorker(QThread):
    saved = pyqtSignal(int, str, bool, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        set_enabled,
        load_profile,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._set_enabled = set_enabled
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()
        self._enabled = bool(enabled)
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._set_enabled(
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
                payload = self._load_profile(clean_profile_key)
            except Exception as exc:
                log(f"ProfileEnabledSaveWorker: не удалось обновить payload profile: {exc}", "DEBUG")
        self.saved.emit(self._request_id, clean_profile_key, self._enabled, _profile_setup_load_result(payload))


class ProfilePresetProfileActionWorker(QThread):
    finished_action = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        set_profile_enabled,
        duplicate_profile,
        delete_profile,
        load_profile_item,
        *,
        action: str,
        profile_key: str,
        enabled: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._set_profile_enabled = set_profile_enabled
        self._duplicate_profile = duplicate_profile
        self._delete_profile = delete_profile
        self._load_profile_item = load_profile_item
        self._action = str(action or "").strip()
        self._target_profile_key = str(profile_key or "").strip()
        self._enabled = enabled

    def run(self) -> None:
        try:
            if self._action == "set_enabled":
                result = self._set_profile_enabled(
                    self._target_profile_key,
                    bool(self._enabled),
                )
                if result and str(result or "").strip() != self._target_profile_key:
                    item = self._load_profile_item(str(result or ""))
                    if item is not None:
                        result = {"profile_key": str(result or "").strip(), "profile_item": item}
            elif self._action == "duplicate":
                result = self._duplicate_profile(self._target_profile_key)
                item = self._load_profile_item(str(result or ""))
                if item is not None:
                    result = {"profile_key": str(result or "").strip(), "profile_item": item}
            elif self._action == "delete":
                result = bool(self._delete_profile(self._target_profile_key))
            else:
                raise ValueError(f"Неизвестное действие profile: {self._action}")
        except Exception as exc:
            log(f"ProfilePresetProfileActionWorker: не удалось выполнить действие profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.finished_action.emit(self._request_id, self._action, self._target_profile_key, result)


class ProfileItemRefreshWorker(QThread):
    refreshed = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        load_profile_item,
        *,
        old_profile_key: str,
        profile_key: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_profile_item = load_profile_item
        self._old_profile_key = str(old_profile_key or "").strip()
        self._profile_key = str(profile_key or "").strip()

    def run(self) -> None:
        try:
            item = self._load_profile_item(self._profile_key)
        except Exception as exc:
            log(f"ProfileItemRefreshWorker: не удалось загрузить profile item: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.refreshed.emit(self._request_id, self._old_profile_key, self._profile_key, item)


class ProfilePresetProfileMoveWorker(QThread):
    moved = pyqtSignal(int, str, str, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        move_profile_before,
        move_profile_after,
        move_profile_to_end,
        move_profile_to_folder,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._move_profile_before = move_profile_before
        self._move_profile_after = move_profile_after
        self._move_profile_to_end = move_profile_to_end
        self._move_profile_to_folder = move_profile_to_folder
        self._action = str(action or "").strip()
        self._source_profile_key = str(source_profile_key or "").strip()
        self._destination_profile_key = str(destination_profile_key or "").strip()
        self._destination_group_key = str(destination_group_key or "").strip()

    def run(self) -> None:
        try:
            if self._action == "before":
                result = self._move_profile_before(
                    self._source_profile_key,
                    self._destination_profile_key,
                    destination_folder_key=self._destination_group_key,
                )
            elif self._action == "after":
                result = self._move_profile_after(
                    self._source_profile_key,
                    self._destination_profile_key,
                    destination_folder_key=self._destination_group_key,
                )
            elif self._action == "end":
                result = self._move_profile_to_end(self._source_profile_key)
            elif self._action == "folder":
                result = self._move_profile_to_folder(
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
        create_user_profile,
        load_user_profile_items,
        *,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._create_user_profile = create_user_profile
        self._load_user_profile_items = load_user_profile_items
        self._name = str(name or "").strip()
        self._protocol = str(protocol or "").strip()
        self._ports = str(ports or "").strip()

    def run(self) -> None:
        try:
            profile_id = self._create_user_profile(
                name=self._name,
                protocol=self._protocol,
                ports=self._ports,
            )
            created_items = self._load_user_profile_items(str(profile_id or ""))
            created_item = created_items[0] if created_items else None
        except Exception as exc:
            log(f"ProfileUserProfileCreateWorker: не удалось создать пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.created.emit(self._request_id, str(profile_id or ""), created_item)

class ProfileUserProfileUpdateWorker(QThread):
    updated = pyqtSignal(int, str, int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        update_user_profile,
        load_user_profile_items,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._update_user_profile = update_user_profile
        self._load_user_profile_items = load_user_profile_items
        self._profile_id = str(profile_id or "").strip()
        self._name = str(name or "").strip()
        self._protocol = str(protocol or "").strip()
        self._ports = str(ports or "").strip()

    def run(self) -> None:
        try:
            changed = self._update_user_profile(
                profile_id=self._profile_id,
                name=self._name,
                protocol=self._protocol,
                ports=self._ports,
            )
            updated_items = self._load_user_profile_items(self._profile_id)
        except Exception as exc:
            log(f"ProfileUserProfileUpdateWorker: не удалось изменить пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.updated.emit(self._request_id, self._profile_id, int(changed or 0), updated_items)


class ProfileUserProfileDeleteWorker(QThread):
    deleted = pyqtSignal(int, str, int)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, delete_user_profile, *, profile_id: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._delete_user_profile = delete_user_profile
        self._profile_id = str(profile_id or "").strip()

    def run(self) -> None:
        try:
            changed = self._delete_user_profile(profile_id=self._profile_id)
        except Exception as exc:
            log(f"ProfileUserProfileDeleteWorker: не удалось удалить пользовательский profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.deleted.emit(self._request_id, self._profile_id, int(changed or 0))


def load_user_profile_items_from_payload(load_profiles, profile_id: str) -> tuple[object, ...]:
    clean_profile_id = str(profile_id or "").strip()
    if not clean_profile_id:
        return ()
    try:
        payload = load_profiles()
    except Exception:
        return ()
    return tuple(
        item for item in tuple(getattr(payload, "items", ()) or ())
        if str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id
    )


def load_profile_item_from_payload(load_profiles, profile_key: str):
    clean_key = str(profile_key or "").strip()
    if not clean_key:
        return None
    try:
        payload = load_profiles()
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
        load_profile_folder_state,
        create_profile_folder,
        rename_profile_folder,
        delete_profile_folder,
        move_profile_folder_by_step,
        set_profile_folder_collapsed,
        set_profile_folders_collapsed,
        reset_profile_folders,
        *,
        action: str,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        collapsed_by_key: dict[str, bool] | None = None,
        context_extra: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_profile_folder_state = load_profile_folder_state
        self._create_profile_folder = create_profile_folder
        self._rename_profile_folder = rename_profile_folder
        self._delete_profile_folder = delete_profile_folder
        self._move_profile_folder_by_step = move_profile_folder_by_step
        self._set_profile_folder_collapsed = set_profile_folder_collapsed
        self._set_profile_folders_collapsed = set_profile_folders_collapsed
        self._reset_profile_folders = reset_profile_folders
        self._action = str(action or "").strip()
        self._folder_key = str(folder_key or "").strip()
        self._name = str(name or "").strip()
        self._direction = int(direction or 0)
        self._collapsed = bool(collapsed)
        self._collapsed_by_key = {
            str(key or "").strip(): bool(value)
            for key, value in dict(collapsed_by_key or {}).items()
            if str(key or "").strip()
        }
        self._context_extra = dict(context_extra or {})

    def run(self) -> None:
        context = {
            "folder_key": self._folder_key,
            "name": self._name,
            "direction": self._direction,
            "collapsed": self._collapsed,
            "collapsed_by_key": dict(self._collapsed_by_key),
        }
        context.update(self._context_extra)
        try:
            if self._action == "load_state":
                result = self._load_profile_folder_state()
            elif self._action == "create":
                result = self._create_profile_folder(self._name)
            elif self._action == "rename":
                result = self._rename_profile_folder(self._folder_key, self._name)
            elif self._action == "delete":
                result = self._delete_profile_folder(self._folder_key)
            elif self._action == "move_step":
                result = self._move_profile_folder_by_step(self._folder_key, self._direction)
            elif self._action == "set_collapsed":
                result = self._set_profile_folder_collapsed(self._folder_key, self._collapsed)
            elif self._action == "set_collapsed_many":
                result = self._set_profile_folders_collapsed(self._collapsed_by_key)
            elif self._action == "reset":
                result = self._reset_profile_folders()
            else:
                raise ValueError(f"Неизвестное действие папки profile: {self._action}")
        except Exception as exc:
            log(f"ProfileFolderActionWorker: не удалось выполнить действие папки profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        if self._action != "load_state" and bool(result):
            try:
                context["folder_state"] = self._load_profile_folder_state()
            except Exception as exc:
                log(f"ProfileFolderActionWorker: не удалось обновить состояние папок profile: {exc}", "DEBUG")
        self.completed.emit(self._request_id, self._action, result, context)


class ProfileStrategyApplyWorker(QThread):
    applied = pyqtSignal(int, str, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        apply_strategy,
        load_profile,
        profile_key: str,
        strategy_id: str,
        strategy_branch_id: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._apply_strategy = apply_strategy
        self._load_profile = load_profile
        self._profile_key = str(profile_key or "").strip()
        self._strategy_id = str(strategy_id or "").strip()
        self._strategy_branch_id = str(strategy_branch_id or "").strip()

    def run(self) -> None:
        try:
            kwargs = {
                "profile_key": self._profile_key,
                "strategy_id": self._strategy_id,
            }
            if self._strategy_branch_id:
                kwargs["strategy_branch_id"] = self._strategy_branch_id
            result = self._apply_strategy(**kwargs)
        except Exception as exc:
            log(f"ProfileStrategyApplyWorker: не удалось применить готовую стратегию: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        profile_key = str(getattr(result, "profile_key", "") or "").strip()
        payload = None
        if profile_key:
            try:
                payload = self._load_profile(profile_key)
            except Exception as exc:
                log(f"ProfileStrategyApplyWorker: не удалось загрузить обновлённый profile payload: {exc}", "DEBUG")
        self.applied.emit(
            self._request_id,
            self._profile_key,
            profile_key,
            self._strategy_id,
            _profile_setup_load_result(payload, apply_result=result),
        )


class ProfileStrategyFeedbackSaveWorker(QThread):
    saved = pyqtSignal(int, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        save_feedback,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._save_feedback = save_feedback
        self._profile_key = str(profile_key or "").strip()
        self._strategy_id = str(strategy_id or "").strip()
        self._rating = rating
        self._favorite = favorite

    def run(self) -> None:
        try:
            state = self._save_feedback(
                profile_key=self._profile_key,
                rating=self._rating,
                favorite=self._favorite,
            )
        except Exception as exc:
            log(f"ProfileStrategyFeedbackSaveWorker: не удалось сохранить оценку стратегии: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.saved.emit(self._request_id, self._profile_key, self._strategy_id, state)
