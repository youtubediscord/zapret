from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from log.log import log
from profile.match_filters import filter_values
from profile.editable_settings import normalize_filter_value
from profile.key_resolution import profile_reference_key
from profile.profile_setup_loader import profile_save_result_keys
from profile.setup_match_text import build_profile_setup_match_tab_text
from profile.ui.profile_setup_controls import (
    range_expression_from_controls,
    set_combo_by_data,
    set_range_controls,
    sync_range_value_enabled,
)
from profile.strategy_state import ProfileStrategyState
from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController
from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController
from profile.ui.profile_setup_payload_controller import ProfileSetupPayloadController
from profile.ui.profile_strategy_controller import ProfileStrategyController
from profile.ui.profile_user_profile_controller import ProfileUserProfileController
from profile.ui.profile_strategy_list_widget import (
    CompactDisplayComboBox,
    ProfileStrategyListDelegate,
    ProfileStrategyListView,
    ProfileStrategyListWidget,
    ProfileStrategySearchLineEdit,
    _current_strategy_branch_id,
    _current_strategy_id,
    _join_accessible_options,
    _payload_with_strategy_branch,
    _set_strategy_clear_feedback_button_state,
    _set_strategy_favorite_button_state,
    _set_strategy_feedback_button_state,
    _strategy_branch_label,
    _strategy_branch_summary_name,
    _sync_combo_items_accessibility,
    _sync_strategy_branch_combo_items_accessibility,
    _update_strategy_branch_combo_in_place,
)
from profile.ui.user_profile_dialog import CreateUserProfileDialog
from qfluentwidgets import (
    BodyLabel,
    BreadcrumbBar,
    CaptionLabel,
    CheckBox,
    ComboBox,
    InfoBar,
    LineEdit,
    MessageBox,
    PlainTextEdit,
    FluentIcon,
    SegmentedWidget,
    PushButton,
)
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_preset_launch_method, is_zapret2_launch_method
from ui.pages.base_page import BasePage
from ui.accessibility import (
    remove_line_edit_buttons_from_tab_order,
    set_breadcrumb_accessibility,
    set_control_accessibility,
    set_state_text,
)
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState
from ui.segmented_accessibility import set_segmented_items_accessibility
from app.ui_texts import tr as tr_catalog
from ui.theme import get_theme_tokens


_PROFILE_SETUP_CLEANUP_RUNTIMES = (
    ("_setup_load_runtime", "profile setup load worker", False),
    ("_list_file_load_runtime", "profile list file load worker", False),
    ("_list_file_validation_runtime", "profile list file validation worker", False),
    ("_list_file_save_runtime", "profile list file save worker", True),
    ("_settings_save_runtime", "profile settings save worker", True),
    ("_raw_profile_save_runtime", "profile raw text save worker", True),
    ("_enabled_save_runtime", "profile enabled save worker", True),
    ("_user_profile_update_runtime", "profile user update worker", True),
    ("_user_profile_delete_runtime", "profile user delete worker", True),
    ("_strategy_apply_runtime", "profile strategy apply worker", True),
    ("_strategy_feedback_save_runtime", "profile strategy feedback save worker", True),
)


def set_widget_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.text()) == value:
            return False
    except Exception:
        pass
    widget.setText(value)
    return True


def set_widget_checked_if_changed(widget, checked: bool) -> bool:
    value = bool(checked)
    try:
        if bool(widget.isChecked()) == value:
            return False
    except Exception:
        pass
    widget.setChecked(value)
    return True


def set_widget_enabled_if_changed(widget, enabled: bool) -> bool:
    value = bool(enabled)
    try:
        if bool(widget.isEnabled()) == value:
            return False
    except Exception:
        pass
    widget.setEnabled(value)
    return True


def set_widget_visible_if_changed(widget, visible: bool) -> bool:
    value = bool(visible)
    try:
        if bool(widget.isVisible()) == value:
            return False
    except Exception:
        pass
    widget.setVisible(value)
    return True


def set_widget_property_if_changed(widget, name: str, value) -> bool:
    key = str(name or "")
    try:
        if widget.property(key) == value:
            return False
    except Exception:
        pass
    widget.setProperty(key, value)
    return True


def set_profile_list_status_text(label, text: str) -> bool:
    changed = set_widget_text_if_changed(label, text)
    set_state_text(label, f"Статус списка profile: {text}")
    return changed


def set_profile_list_error_text(label, text: str) -> bool:
    changed = set_widget_text_if_changed(label, text)
    value = " ".join(str(text or "").strip().split())
    if value:
        set_state_text(label, f"Ошибка списка profile: {value}")
    return changed


def set_widget_style_sheet_if_changed(widget, style: str) -> bool:
    value = str(style or "")
    try:
        if str(widget.styleSheet()) == value:
            return False
    except Exception:
        pass
    widget.setStyleSheet(value)
    return True


def set_read_only_if_changed(widget, read_only: bool) -> bool:
    value = bool(read_only)
    try:
        if bool(widget.isReadOnly()) == value:
            return False
    except Exception:
        pass
    widget.setReadOnly(value)
    return True


def set_placeholder_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.placeholderText()) == value:
            return False
    except Exception:
        pass
    widget.setPlaceholderText(value)
    return True


def set_current_index_if_changed(widget, index: int) -> bool:
    value = int(index)
    try:
        if int(widget.currentIndex()) == value:
            return False
    except Exception:
        pass
    widget.setCurrentIndex(value)
    return True


def set_segmented_current_item_if_changed(widget, item_key: str) -> bool:
    value = str(item_key or "")
    try:
        if str(widget.currentItem()) == value:
            return False
    except Exception:
        pass
    widget.setCurrentItem(value)
    return True


def set_tab_item_text_if_changed(widget, item_key: str, text: str) -> bool:
    route_key = str(item_key or "")
    value = str(text or "")
    try:
        if str(widget.itemText(route_key)) == value:
            return False
    except Exception:
        pass
    widget.setItemText(route_key, value)
    return True


def _branch_raw_strategy_text(branch, strategy_args: str) -> str:
    lines = []
    in_range = str(getattr(branch, "in_range", "") or "x").strip() or "x"
    out_range = str(getattr(branch, "out_range", "") or "a").strip() or "a"
    payload = str(getattr(branch, "payload", "") or "all").strip() or "all"
    if in_range != "x":
        lines.append(f"--in-range={in_range}")
    if out_range != "a":
        lines.append(f"--out-range={out_range}")
    if payload != "all":
        lines.append(f"--payload={payload}")
    clean_strategy_args = str(strategy_args or "").strip()
    if clean_strategy_args:
        lines.append(clean_strategy_args)
    return "\n".join(lines).strip()


def _branch_match_tab_text(payload, branch, raw_strategy_text: str) -> str:
    return build_profile_setup_match_tab_text(
        match_summary=str(getattr(payload, "match_summary", "") or ""),
        strategy_id=str(getattr(branch, "strategy_id", "") or ""),
        strategy_name=str(getattr(branch, "strategy_name", "") or ""),
        raw_strategy_text=raw_strategy_text,
    )


def _profile_editor_tab_title(payload) -> str:
    item = getattr(payload, "item", None)
    match_lines = tuple(str(line or "").strip().lower() for line in getattr(item, "match_lines", ()) or ())
    if any(line.startswith(("--hostlist-exclude", "--ipset-exclude")) for line in match_lines):
        return "Исключения"

    display_name = str(getattr(item, "display_name", "") or "").casefold()
    if "исключения" in display_name:
        return "Исключения"

    return "Редактор"


def _profile_has_list_file_editor(payload) -> bool:
    item = getattr(payload, "item", None)
    match_lines = tuple(str(line or "").strip().lower() for line in getattr(item, "match_lines", ()) or ())
    return any(
        line.startswith(("--hostlist=", "--ipset=", "--hostlist-exclude=", "--ipset-exclude="))
        for line in match_lines
    )


def _profile_setup_payload_from_worker_result(result):
    return getattr(result, "payload", result)


def _profile_setup_apply_signature_from_worker_result(result):
    apply_signature = getattr(result, "apply_signature", None)
    return tuple(apply_signature) if apply_signature is not None else None


def _profile_setup_apply_result_from_worker_result(result):
    return getattr(result, "apply_result", None)


def _profile_setup_payload_and_apply_signature(result):
    return (
        _profile_setup_payload_from_worker_result(result),
        _profile_setup_apply_signature_from_worker_result(result),
    )


def _non_negative_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def _list_file_save_request(
    profile_key: str,
    text: str,
    *,
    filter_kind: str = "",
    filter_value: str = "",
) -> dict[str, str]:
    return {
        "profile_key": str(profile_key or "").strip(),
        "text": str(text or ""),
        "filter_kind": str(filter_kind or "").strip(),
        "filter_value": str(filter_value or "").strip(),
    }


def _normalized_list_file_save_request(value) -> dict[str, str]:
    if isinstance(value, dict):
        return _list_file_save_request(
            str(value.get("profile_key") or ""),
            str(value.get("text") or ""),
            filter_kind=str(value.get("filter_kind") or ""),
            filter_value=str(value.get("filter_value") or ""),
        )
    if isinstance(value, tuple):
        parts = tuple(value)
        return _list_file_save_request(
            str(parts[0] if len(parts) > 0 else ""),
            str(parts[1] if len(parts) > 1 else ""),
            filter_kind=str(parts[2] if len(parts) > 2 else ""),
            filter_value=str(parts[3] if len(parts) > 3 else ""),
        )
    return _list_file_save_request("", "")


def _worker_pending_property(state_obj_name: str, *, cast=None):
    """Thin-property поверх pending state-объекта подсистемы.

    Имена и get/set-семантика сохранены для BEH-тестов (стабы присваивают
    эти атрибуты напрямую); компактизация по образцу фазы A (DRY, AC1)."""

    def _get(self):
        value = getattr(self, state_obj_name)().pending
        return cast(value) if cast is not None else value

    def _set(self, value) -> None:
        getattr(self, state_obj_name)().pending = cast(value) if cast is not None else value

    return property(_get, _set)


def _worker_start_scheduled_property(state_obj_name: str):
    """Thin-property поверх start_scheduled state-объекта подсистемы."""

    def _get(self) -> bool:
        return bool(getattr(self, state_obj_name)().start_scheduled)

    def _set(self, value) -> None:
        getattr(self, state_obj_name)().start_scheduled = bool(value)

    return property(_get, _set)


class ProfileSetupPageBase(BasePage):
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"

    def __init__(
        self,
        parent=None,
        *,
        create_profile_setup_load_worker,
        create_profile_list_file_load_worker,
        create_profile_list_file_save_worker,
        create_profile_list_file_validation_worker,
        create_profile_settings_save_worker,
        create_profile_raw_text_save_worker,
        create_profile_enabled_save_worker,
        create_profile_user_update_worker,
        create_profile_user_delete_worker,
        create_profile_strategy_apply_worker,
        create_profile_strategy_feedback_save_worker,
        open_profiles,
        open_root,
        on_profile_changed,
    ):
        super().__init__(
            title="",
            parent=parent,
            title_key=self.title_key_name,
        )
        self._create_profile_setup_load_worker_fn = create_profile_setup_load_worker
        self._create_profile_list_file_load_worker_fn = create_profile_list_file_load_worker
        self._create_profile_list_file_save_worker_fn = create_profile_list_file_save_worker
        self._create_profile_list_file_validation_worker_fn = create_profile_list_file_validation_worker
        self._create_profile_settings_save_worker_fn = create_profile_settings_save_worker
        self._create_profile_raw_text_save_worker_fn = create_profile_raw_text_save_worker
        self._create_profile_enabled_save_worker_fn = create_profile_enabled_save_worker
        self._create_profile_user_update_worker_fn = create_profile_user_update_worker
        self._create_profile_user_delete_worker_fn = create_profile_user_delete_worker
        self._create_profile_strategy_apply_worker_fn = create_profile_strategy_apply_worker
        self._create_profile_strategy_feedback_save_worker_fn = create_profile_strategy_feedback_save_worker
        self._open_profiles = open_profiles
        self._open_root = open_root
        self._on_profile_changed_callback = on_profile_changed
        self._profile_key = ""
        self._loading = False
        self._setup_load_runtime = OneShotWorkerRuntime()
        self._setup_load_request_id = 0
        self._setup_load_runtime_request_id = 0
        self._setup_load_state = LatestValueWorkerState(
            self._setup_load_runtime,
            empty_value=False,
        )
        self._list_file_load_runtime = OneShotWorkerRuntime()
        self._list_file_load_request_id = 0
        self._list_file_load_state = LatestValueWorkerState(
            self._list_file_load_runtime,
            empty_value=False,
        )
        self._list_file_state_apply_scheduled = False
        self._pending_list_file_state_apply = None
        self._list_file_save_runtime = OneShotWorkerRuntime()
        self._list_file_save_request_id = 0
        self._list_file_save_state = LatestValueWorkerState(
            self._list_file_save_runtime,
            empty_value=None,
        )
        self._list_file_validation_runtime = OneShotWorkerRuntime()
        self._list_file_validation_request_id = 0
        self._list_file_validation_state = LatestValueWorkerState(
            self._list_file_validation_runtime,
            empty_value=None,
        )
        self._settings_save_runtime = OneShotWorkerRuntime()
        self._settings_save_request_id = 0
        self._settings_save_state = LatestValueWorkerState(
            self._settings_save_runtime,
            empty_value=None,
        )
        self._raw_profile_save_runtime = OneShotWorkerRuntime()
        self._raw_profile_save_request_id = 0
        self._raw_profile_save_state = LatestValueWorkerState(
            self._raw_profile_save_runtime,
            empty_value=None,
        )
        self._enabled_save_runtime = OneShotWorkerRuntime()
        self._enabled_save_request_id = 0
        self._enabled_save_runtime_enabled: bool | None = None
        self._enabled_save_state = LatestValueWorkerState(
            self._enabled_save_runtime,
            empty_value=None,
        )
        self._user_profile_update_runtime = OneShotWorkerRuntime()
        self._user_profile_update_request_id = 0
        self._user_profile_delete_runtime = OneShotWorkerRuntime()
        self._user_profile_delete_request_id = 0
        self._user_profile_write_state = QueuedWorkerState[dict[str, str]](
            self._user_profile_update_runtime,
        )
        self._strategy_apply_runtime = OneShotWorkerRuntime()
        self._strategy_apply_request_id = 0
        self._strategy_apply_runtime_strategy_id = ""
        self._strategy_apply_runtime_branch_id = ""
        self._strategy_apply_state = LatestValueWorkerState(
            self._strategy_apply_runtime,
            empty_value=None,
        )
        self._scheduled_profile_setup_write_operation = None
        self._profile_setup_write_state = QueuedWorkerState[dict[str, object]](
            self._settings_save_runtime,
        )
        self._strategy_feedback_save_runtime = OneShotWorkerRuntime()
        self._strategy_feedback_save_request_id = 0
        self._strategy_feedback_save_state = LatestValueWorkerState(
            self._strategy_feedback_save_runtime,
            empty_value=None,
        )
        self._payload = None
        self._profile_setup_payload_apply_scheduled = False
        self._pending_profile_setup_payload_apply = None
        self._strategy_stack = None
        self._strategy_tabs = None
        self._strategy_list = None
        self._strategy_branch_bar = None
        self._strategy_branch_combo = None
        self._strategy_tab = None
        self._list_file_editor_placeholder = None
        self._match_tab_placeholder = None
        self._editor_tab_available = True
        self._editor_tab_built = False
        self._match_tab_built = False
        self._list_file_dirty = True
        self._match_text = None
        self._match_text_snapshot = ""
        self._settings_container = None
        self._work_button = None
        self._notwork_button = None
        self._favorite_button = None
        self._clear_feedback_button = None
        self._update_user_profile_button = None
        self._delete_user_profile_button = None
        self._raw_profile_text = None
        self._raw_profile_text_cache: str | None = None
        self._raw_profile_save_button = None
        self._list_file_title = None
        self._list_file_base_title = None
        self._list_file_base_text = None
        self._list_file_user_title = None
        self._list_file_text = None
        self._list_file_editor_tab = None
        self._list_file_error_label = None
        self._list_file_status_label = None
        self._list_file_save_button = None
        self._list_file_kind = ""
        self._list_file_base_text_snapshot = ""
        self._list_file_text_snapshot = ""
        self._list_file_server_text_snapshot = None
        self._list_file_text_dirty = True
        self._list_file_validation_has_error = False
        self._list_file_user_entries_count = 0
        self._list_file_base_entries_count = 0
        self._list_file_normal_style = ""
        self._list_file_error_style = ""
        self._list_file_validation_timer = QTimer(self)
        self._list_file_validation_timer.setSingleShot(True)
        self._list_file_validation_timer.timeout.connect(self._run_scheduled_list_file_validation)
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(350)
        self._settings_save_timer.timeout.connect(self._autosave_editable_settings)
        self._list_file_editor_controller = ProfileListFileEditorController(self)
        self._save_controller = ProfileSetupSaveController(self)
        self._payload_controller = ProfileSetupPayloadController(self)
        self._strategy_controller = ProfileStrategyController(self)
        self._user_profile_controller = ProfileUserProfileController(self)
        self._build_content()

    def _worker_runtime(self, attr: str) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            setattr(self, attr, runtime)
        return runtime

    def _list_file_editor_controller_obj(self) -> ProfileListFileEditorController:
        # Контроллер создаётся эагерно в __init__; ленивая ветка нужна только
        # duck-typed стабам из тестов (__new__ без __init__).
        controller = self.__dict__.get("_list_file_editor_controller")
        if controller is None:
            controller = ProfileListFileEditorController(self)
            self.__dict__["_list_file_editor_controller"] = controller
        return controller

    def _save_controller_obj(self) -> ProfileSetupSaveController:
        # Контроллер создаётся эагерно в __init__; ленивая ветка нужна только
        # duck-typed стабам из тестов (__new__ без __init__).
        controller = self.__dict__.get("_save_controller")
        if controller is None:
            controller = ProfileSetupSaveController(self)
            self.__dict__["_save_controller"] = controller
        return controller

    def _payload_controller_obj(self) -> ProfileSetupPayloadController:
        # Контроллер создаётся эагерно в __init__; ленивая ветка нужна только
        # duck-typed стабам из тестов (__new__ без __init__).
        controller = self.__dict__.get("_payload_controller")
        if controller is None:
            controller = ProfileSetupPayloadController(self)
            self.__dict__["_payload_controller"] = controller
        return controller

    def _strategy_controller_obj(self) -> ProfileStrategyController:
        # Контроллер создаётся эагерно в __init__; ленивая ветка нужна только
        # duck-typed стабам из тестов (__new__ без __init__).
        controller = self.__dict__.get("_strategy_controller")
        if controller is None:
            controller = ProfileStrategyController(self)
            self.__dict__["_strategy_controller"] = controller
        return controller

    def _user_profile_controller_obj(self) -> ProfileUserProfileController:
        # Контроллер создаётся эагерно в __init__; ленивая ветка нужна только
        # duck-typed стабам из тестов (__new__ без __init__).
        controller = self.__dict__.get("_user_profile_controller")
        if controller is None:
            controller = ProfileUserProfileController(self)
            self.__dict__["_user_profile_controller"] = controller
        return controller

    def _accept_current_profile_setup_worker_finished(self, request_attr: str, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is not None:
            try:
                return int(request_id) == int(self.__dict__.get(request_attr, 0) or 0)
            except (TypeError, ValueError):
                return False

        worker_attr = str(request_attr or "").removesuffix("_request_id") + "_runtime_worker"
        missing = object()
        current_worker = self.__dict__.get(worker_attr, missing)
        if current_worker is missing:
            if str(request_attr or "") in {
                "_user_profile_update_request_id",
                "_user_profile_delete_request_id",
            }:
                return True
            try:
                return int(self.__dict__.get(request_attr, 0) or 0) <= 0
            except (TypeError, ValueError):
                return True
        if worker is not current_worker:
            return False
        setattr(self, worker_attr, None)
        return True

    def _profile_setup_write_is_running(self) -> bool:
        return self._save_controller_obj()._profile_setup_write_is_running()

    @staticmethod
    def _profile_setup_write_operations_collide(previous: dict, queued: dict) -> bool:
        return ProfileSetupSaveController._profile_setup_write_operations_collide(previous, queued)

    def _queue_profile_setup_write_operation(self, operation: dict[str, object]) -> None:
        return self._save_controller_obj()._queue_profile_setup_write_operation(operation)

    def _start_next_profile_setup_write_operation(self) -> bool:
        return self._save_controller_obj()._start_next_profile_setup_write_operation()

    def _schedule_next_profile_setup_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        return self._save_controller_obj()._schedule_next_profile_setup_write_operation_after_finish(request_attr, worker)

    def _schedule_profile_setup_write_operation_start(self, operation: dict[str, object]) -> None:
        return self._save_controller_obj()._schedule_profile_setup_write_operation_start(operation)

    def _run_profile_setup_write_operation(self, operation: dict[str, object] | None = None) -> bool:
        return self._save_controller_obj()._run_profile_setup_write_operation(operation)

    def _profile_setup_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        return self._save_controller_obj()._profile_setup_write_state_obj()

    @property
    def _pending_profile_setup_write_operations(self) -> list[dict[str, object]]:
        return self._profile_setup_write_state_obj().pending

    @_pending_profile_setup_write_operations.setter
    def _pending_profile_setup_write_operations(self, value: list[dict[str, object]]) -> None:
        self._profile_setup_write_state_obj().pending = [
            dict(operation or {})
            for operation in list(value or [])
        ]

    _profile_setup_write_operation_start_scheduled = _worker_start_scheduled_property("_profile_setup_write_state_obj")

    def _build_content(self) -> None:
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._breadcrumb = BreadcrumbBar()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        # stretch > 0 обязателен: у BreadcrumbBar нет sizeHint, без доли
        # свободной ширины он получает ~0 px и прячет все элементы в элайд-меню.
        header_layout.addWidget(self._breadcrumb, 1, Qt.AlignmentFlag.AlignVCenter)
        self._summary = BodyLabel("")
        self._summary.setWordWrap(True)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self._summary, 1)

        self._enabled_checkbox = CheckBox("Включён")
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        self._enabled_checkbox.stateChanged.connect(self._update_profile_setup_accessibility)
        header_layout.addWidget(self._enabled_checkbox, 0, Qt.AlignmentFlag.AlignRight)
        self._update_user_profile_button = PushButton("Изменить", icon=FluentIcon.EDIT)
        set_control_accessibility(
            self._update_user_profile_button,
            name="Изменить пользовательский profile",
            description="Открывает изменение пользовательского profile и обновляет связанные preset-ы.",
        )
        set_state_text(self._update_user_profile_button, "Изменить пользовательский profile")
        self._update_user_profile_button.clicked.connect(self._on_update_user_profile_clicked)
        self._update_user_profile_button.hide()
        header_layout.addWidget(self._update_user_profile_button, 0, Qt.AlignmentFlag.AlignRight)
        self._delete_user_profile_button = PushButton("Удалить", icon=FluentIcon.DELETE)
        set_control_accessibility(
            self._delete_user_profile_button,
            name="Удалить пользовательский profile",
            description="Удаляет пользовательский profile, его списки и связанные записи из preset-ов.",
        )
        set_state_text(self._delete_user_profile_button, "Удалить пользовательский profile")
        self._delete_user_profile_button.clicked.connect(self._on_delete_user_profile_clicked)
        self._delete_user_profile_button.hide()
        header_layout.addWidget(self._delete_user_profile_button, 0, Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(header)

        self._settings_container = QWidget(self)
        self._settings_container.setMinimumWidth(0)
        self._settings_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout = QHBoxLayout(self._settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(10)

        self._filter_combo = CompactDisplayComboBox()
        self._filter_combo.setMinimumWidth(120)
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.hostlist", language=self._ui_language, default="Hostlist"), userData="hostlist")
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.ipset", language=self._ui_language, default="IPset"), userData="ipset")
        settings_layout.addWidget(self._filter_combo)

        self._filter_value = LineEdit()
        self._filter_value.setMinimumWidth(0)
        self._filter_value.setPlaceholderText("lists/example.txt")
        set_control_accessibility(
            self._filter_value,
            name="Файл списка profile",
            description="Путь к hostlist или ipset файлу для текущего profile.",
        )
        remove_line_edit_buttons_from_tab_order(self._filter_value)
        settings_layout.addWidget(self._filter_value, 1)

        self._in_range_mode = CompactDisplayComboBox()
        self._in_range_mode.setMinimumWidth(82)
        self._fill_range_combo(self._in_range_mode)
        self._in_range_label = BodyLabel("--in-range")
        settings_layout.addWidget(self._in_range_label)
        settings_layout.addWidget(self._in_range_mode)

        self._in_range_value = LineEdit()
        self._in_range_value.setMinimumWidth(72)
        self._in_range_value.setPlaceholderText("8")
        set_control_accessibility(
            self._in_range_value,
            name="Значение in-range",
            description="Число или выражение для --in-range.",
        )
        remove_line_edit_buttons_from_tab_order(self._in_range_value)
        settings_layout.addWidget(self._in_range_value)

        self._out_range_mode = CompactDisplayComboBox()
        self._out_range_mode.setMinimumWidth(82)
        self._fill_range_combo(self._out_range_mode)
        self._out_range_label = BodyLabel("--out-range")
        settings_layout.addWidget(self._out_range_label)
        settings_layout.addWidget(self._out_range_mode)

        self._out_range_value = LineEdit()
        self._out_range_value.setMinimumWidth(72)
        self._out_range_value.setPlaceholderText("8")
        set_control_accessibility(
            self._out_range_value,
            name="Значение out-range",
            description="Число или выражение для --out-range.",
        )
        remove_line_edit_buttons_from_tab_order(self._out_range_value)
        settings_layout.addWidget(self._out_range_value)

        self._in_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._in_range_mode, self._in_range_value)
        )
        self._in_range_mode.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._out_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._out_range_mode, self._out_range_value)
        )
        self._out_range_mode.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._filter_combo.currentIndexChanged.connect(lambda _index: self._on_filter_kind_changed())
        self._filter_combo.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._filter_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._filter_value.editingFinished.connect(self._on_filter_value_editing_finished)
        self._in_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._out_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())

        self.layout.addWidget(self._settings_container)
        self._install_profile_tooltips()
        self._update_profile_setup_accessibility()

        self._strategy_stack = QStackedWidget(self)
        self._strategy_tabs = SegmentedWidget()
        self._strategy_tabs.addItem("strategies", "Готовые стратегии", lambda: self._switch_strategy_tab(0))
        self._strategy_tabs.addItem("editor", "Редактор", lambda: self._switch_strategy_tab(1))
        self._strategy_tabs.addItem("match", "Когда применяется", lambda: self._switch_strategy_tab(2))
        set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        self._sync_editor_tab_label(None)
        self._strategy_tabs.currentItemChanged.connect(self._update_strategy_tabs_accessibility)
        self.layout.addWidget(self._strategy_tabs)

        self._strategy_branch_bar = QWidget(self)
        branch_layout = QHBoxLayout(self._strategy_branch_bar)
        branch_layout.setContentsMargins(0, 0, 0, 0)
        branch_layout.setSpacing(8)
        branch_layout.addWidget(BodyLabel("Ветка"))
        self._strategy_branch_combo = CompactDisplayComboBox()
        self._strategy_branch_combo.setMinimumWidth(260)
        self._strategy_branch_combo.currentIndexChanged.connect(self._on_strategy_branch_changed)
        self._strategy_branch_combo.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        branch_layout.addWidget(self._strategy_branch_combo, 1)
        self._strategy_branch_bar.hide()
        self.layout.addWidget(self._strategy_branch_bar)

        self._strategy_list = ProfileStrategyListWidget(self)
        self._strategy_list.strategy_activated.connect(self._on_strategy_list_activated)
        self._strategy_stack.addWidget(self._strategy_list)

        self._list_file_editor_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._list_file_editor_placeholder)

        self._match_tab_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._match_tab_placeholder)

        self.layout.addWidget(self._strategy_stack, 1)
        QWidget.setTabOrder(self._strategy_tabs, self._strategy_list._search)
        QWidget.setTabOrder(self._strategy_list._search, self._strategy_list._list)
        self._update_profile_setup_accessibility()

    def _update_combo_accessibility(self, combo, *, name: str, description: str) -> None:
        if combo is None:
            return
        current_text = getattr(combo, "currentText", None)
        if not callable(current_text):
            return
        selected = str(current_text() or "").strip()
        if selected:
            accessible_name = f"{name}, выбрано: {selected}"
        else:
            accessible_name = f"{name}, не выбрано"
        set_state_text(combo, accessible_name)
        set_control_accessibility(
            combo,
            name=accessible_name,
            description=description,
        )
        _sync_combo_items_accessibility(combo, name=name)

    def _update_profile_setup_accessibility(self, *_args) -> None:
        checkbox = self.__dict__.get("_enabled_checkbox")
        if checkbox is not None:
            state = "включено" if checkbox.isChecked() else "выключено"
            state_text = f"Profile, {state}"
            set_control_accessibility(
                checkbox,
                name=state_text,
                description="Включает или отключает этот profile в текущем preset.",
            )
            set_state_text(checkbox, state_text)
        self._update_combo_accessibility(
            self.__dict__.get("_filter_combo"),
            name="Тип списка profile",
            description="Выберите hostlist для доменов или ipset для IP-адресов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_in_range_mode"),
            name="Режим in-range",
            description="Выберите режим --in-range для входящих пакетов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_out_range_mode"),
            name="Режим out-range",
            description="Выберите режим --out-range для исходящих пакетов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_strategy_branch_combo"),
            name="Ветка готовой стратегии",
            description="Выберите ветку готовой стратегии для этого profile.",
        )
        _sync_strategy_branch_combo_items_accessibility(self.__dict__.get("_strategy_branch_combo"))
        self._update_strategy_tabs_accessibility()

    def _strategy_tab_accessible_labels(self) -> dict[str, str]:
        labels = {
            "strategies": "Готовые стратегии",
            "match": "Когда применяется",
        }
        if bool(getattr(self, "_editor_tab_available", False)):
            labels["editor"] = _profile_editor_tab_title(getattr(self, "_payload", None))
        return labels

    def _update_strategy_tabs_accessibility(self, current: object | None = None) -> None:
        tabs = self.__dict__.get("_strategy_tabs")
        if tabs is None:
            return
        key = str(current or "").strip()
        if not key:
            try:
                key = str(tabs.currentRouteKey() or "").strip()
            except Exception:
                key = ""
        labels = self._strategy_tab_accessible_labels()
        label = labels.get(key) or labels.get("strategies") or "Готовые стратегии"
        state = f"Разделы profile, выбрано: {label}"
        ordered_keys = ["strategies", "editor", "match"]
        options = _join_accessible_options([labels[key] for key in ordered_keys if key in labels])
        description = f"Выберите раздел настройки profile: {options}." if options else "Выберите раздел настройки profile."
        set_state_text(tabs, state)
        set_control_accessibility(
            tabs,
            name=state,
            description=description,
        )
        set_segmented_items_accessibility(
            tabs,
            name="Разделы profile",
            labels=labels,
            item_tab_focus=False,
        )

    def _switch_strategy_tab(self, index: int) -> None:
        if index == 1 and not self._editor_tab_available:
            index = 0
            if self._strategy_tabs is not None:
                set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        if index == 1:
            self._ensure_editor_tab_built()
            self._request_list_file_editor_state()
        elif index == 2:
            self._ensure_match_tab_built()
            self._apply_match_tab_payload()
        set_current_index_if_changed(self._strategy_stack, index)
        if self._strategy_tabs is not None:
            key = "editor" if index == 1 else "match" if index == 2 else "strategies"
            self._update_strategy_tabs_accessibility(key)

    def _ensure_editor_tab_built(self) -> None:
        if self._editor_tab_built:
            return
        self._editor_tab_built = True
        editor_tab = self._list_file_editor_placeholder
        self._list_file_editor_tab = editor_tab
        editor_layout = QVBoxLayout(editor_tab)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)

        self._list_file_title = BodyLabel("Файл списка")
        editor_layout.addWidget(self._list_file_title)

        self._list_file_base_title = CaptionLabel("База")
        self._list_file_base_title.setWordWrap(True)
        editor_layout.addWidget(self._list_file_base_title)

        self._list_file_base_text = PlainTextEdit()
        self._list_file_base_text.setReadOnly(True)
        self._list_file_base_text.setMinimumHeight(180)
        self._list_file_base_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        set_tooltip(
            self._list_file_base_text,
            "Системная часть списка. Она обновляется программой и показана только для просмотра.",
        )
        set_control_accessibility(
            self._list_file_base_text,
            name="Базовая часть списка profile",
            description="Системная часть списка. Она обновляется программой и доступна только для чтения.",
        )
        set_state_text(self._list_file_base_text, "Базовая часть списка profile")
        editor_layout.addWidget(self._list_file_base_text, 1)

        self._list_file_user_title = CaptionLabel("Ваши записи")
        self._list_file_user_title.setWordWrap(True)
        editor_layout.addWidget(self._list_file_user_title)

        self._list_file_text = PlainTextEdit()
        self._list_file_text.setMinimumHeight(320)
        self._list_file_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_file_text.textChanged.connect(self._on_list_file_text_changed)
        set_tooltip(
            self._list_file_text,
            "Пользовательская часть списка. Сохраняется в lists/user и добавляется к базе.",
        )
        set_control_accessibility(
            self._list_file_text,
            name="Ваши записи списка profile",
            description="Пользовательская часть списка. Эти строки можно редактировать и сохранить.",
        )
        set_state_text(self._list_file_text, "Ваши записи списка profile")
        editor_layout.addWidget(self._list_file_text, 1)

        self._list_file_error_label = CaptionLabel("")
        self._list_file_error_label.setWordWrap(True)
        self._list_file_error_label.hide()
        editor_layout.addWidget(self._list_file_error_label)

        editor_actions = QWidget(editor_tab)
        editor_actions_layout = QHBoxLayout(editor_actions)
        editor_actions_layout.setContentsMargins(0, 0, 0, 0)
        editor_actions_layout.setSpacing(12)
        # Кнопки «Сохранить» больше нет: валидный текст сохраняется сам
        # (_maybe_autosave_list_file), статус показывает результат.
        self._list_file_save_button = None
        self._list_file_status_label = CaptionLabel("Загрузка файла списка...")
        set_state_text(self._list_file_status_label, "Статус списка profile: Загрузка файла списка...")
        self._list_file_status_label.setWordWrap(True)
        editor_actions_layout.addWidget(self._list_file_status_label, 1)
        editor_layout.addWidget(editor_actions)
        self._refresh_list_file_editor_style(has_error=False)

    def _ensure_match_tab_built(self) -> None:
        if self._match_tab_built:
            return
        self._match_tab_built = True
        match_tab = self._match_tab_placeholder
        match_layout = QVBoxLayout(match_tab)
        match_layout.setContentsMargins(0, 0, 0, 0)
        match_layout.setSpacing(10)
        match_layout.addWidget(BodyLabel("Условия и готовая стратегия"))
        self._match_text = PlainTextEdit()
        self._match_text.setReadOnly(True)
        self._match_text.setMinimumHeight(280)
        set_tooltip(
            self._match_text,
            "Подробности текущего profile: условия применения и выбранная готовая стратегия.",
        )
        set_control_accessibility(
            self._match_text,
            name="Условия применения profile",
            description="Здесь показаны условия применения profile и выбранная готовая стратегия.",
        )
        set_state_text(self._match_text, "Условия применения profile")
        match_layout.addWidget(self._match_text, 1)

        match_layout.addWidget(BodyLabel("Текст profile в текущем preset"))
        self._raw_profile_text = PlainTextEdit()
        self._raw_profile_text.setMinimumHeight(150)
        self._raw_profile_text.setMaximumHeight(220)
        set_tooltip(
            self._raw_profile_text,
            "Сырой текст profile. Сохраняется только в текущий preset и не меняет пользовательский шаблон.",
        )
        set_control_accessibility(
            self._raw_profile_text,
            name="Текст profile в текущем preset",
            description="Сырой текст profile. Сохраняется только в текущий preset.",
        )
        set_state_text(self._raw_profile_text, "Текст profile в текущем preset")
        self._raw_profile_text.textChanged.connect(self._on_raw_profile_text_changed)
        match_layout.addWidget(self._raw_profile_text)

        raw_actions = QWidget(match_tab)
        raw_actions_layout = QHBoxLayout(raw_actions)
        raw_actions_layout.setContentsMargins(0, 0, 0, 0)
        raw_actions_layout.setSpacing(12)
        self._raw_profile_save_button = PushButton("Сохранить текст profile", icon=FluentIcon.SAVE)
        self._raw_profile_save_button.clicked.connect(self._on_raw_profile_save_clicked)
        set_tooltip(
            self._raw_profile_save_button,
            "Проверяет текст как один profile и записывает его в текущий preset.",
        )
        set_control_accessibility(
            self._raw_profile_save_button,
            name="Сохранить текст profile",
            description="Проверяет текст как один profile и записывает его в текущий preset.",
        )
        set_state_text(self._raw_profile_save_button, "Сохранить текст profile")
        raw_actions_layout.addWidget(self._raw_profile_save_button)
        raw_actions_layout.addStretch(1)
        match_layout.addWidget(raw_actions)

        feedback_actions = QWidget(match_tab)
        feedback_actions_layout = QHBoxLayout(feedback_actions)
        feedback_actions_layout.setContentsMargins(0, 0, 0, 0)
        feedback_actions_layout.setSpacing(12)

        self._work_button = PushButton("Работает", icon=FluentIcon.ACCEPT)
        set_tooltip(self._work_button, "Пометить текущую готовую стратегию как рабочую для этого profile.")
        set_control_accessibility(
            self._work_button,
            name="Отметить стратегию как рабочую",
            description="Помечает текущую готовую стратегию как рабочую для этого profile.",
        )
        self._work_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="work"))
        feedback_actions_layout.addWidget(self._work_button)

        self._notwork_button = PushButton("Не работает", icon=FluentIcon.CLOSE)
        set_tooltip(self._notwork_button, "Пометить текущую готовую стратегию как нерабочую для этого profile.")
        set_control_accessibility(
            self._notwork_button,
            name="Отметить стратегию как нерабочую",
            description="Помечает текущую готовую стратегию как нерабочую для этого profile.",
        )
        self._notwork_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="notwork"))
        feedback_actions_layout.addWidget(self._notwork_button)

        self._favorite_button = PushButton("В избранное", icon=FluentIcon.HEART)
        set_tooltip(self._favorite_button, "Добавить текущую готовую стратегию в избранное или убрать её оттуда.")
        set_control_accessibility(
            self._favorite_button,
            name="Добавить стратегию в избранное",
            description="Добавляет текущую готовую стратегию в избранное или убирает её оттуда.",
        )
        self._favorite_button.clicked.connect(self._toggle_current_strategy_favorite)
        feedback_actions_layout.addWidget(self._favorite_button)

        self._clear_feedback_button = PushButton("Убрать оценку", icon=FluentIcon.RETURN)
        set_tooltip(self._clear_feedback_button, "Очистить вашу оценку для текущей готовой стратегии.")
        set_control_accessibility(
            self._clear_feedback_button,
            name="Убрать оценку стратегии",
            description="Очищает вашу оценку для текущей готовой стратегии.",
        )
        self._clear_feedback_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating=""))
        feedback_actions_layout.addWidget(self._clear_feedback_button)
        feedback_actions_layout.addStretch(1)
        match_layout.addWidget(feedback_actions)
        self._apply_match_tab_payload()

    def _apply_match_tab_payload(self) -> None:
        payload = self._payload
        if payload is None or not self._match_tab_built:
            return
        item = payload.item
        if self._match_text is not None:
            match_text = str(getattr(payload, "match_tab_text", "") or "")
            if self.__dict__.get("_match_text_snapshot") != match_text:
                self._match_text.setPlainText(match_text)
                self._match_text_snapshot = match_text
        if self._raw_profile_text is not None:
            self._set_raw_profile_text_from_payload(str(getattr(payload, "raw_profile_text", "") or ""))
            raw_editable = bool(getattr(item, "in_preset", False))
            set_read_only_if_changed(self._raw_profile_text, not raw_editable)
        if self._raw_profile_save_button is not None:
            set_widget_enabled_if_changed(self._raw_profile_save_button, bool(getattr(item, "in_preset", False)))
        self._apply_feedback_buttons(payload)

    def _set_raw_profile_text_from_payload(self, text: str) -> None:
        value = str(text or "")
        editor = self.__dict__.get("_raw_profile_text")
        if editor is None:
            self._raw_profile_text_cache = value
            return
        if self._current_raw_profile_text() == value:
            return
        editor.setPlainText(value)
        self._raw_profile_text_cache = value

    def _on_raw_profile_text_changed(self) -> None:
        # \u041f\u0440\u0430\u0432\u043a\u0430 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0438\u0440\u0443\u0435\u0442 \u043c\u0435\u043c\u043e: \u0442\u0435\u043a\u0441\u0442 \u043f\u0435\u0440\u0435\u0447\u0438\u0442\u0430\u0435\u0442\u0441\u044f \u0438\u0437
        # \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430 \u043f\u0440\u0438 \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0435\u043c \u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u0438 (_current_raw_profile_text).
        self._raw_profile_text_cache = None

    def _current_raw_profile_text(self) -> str:
        """\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0435\u043a\u0441\u0442 raw-\u0440\u0435\u0434\u0430\u043a\u0442\u043e\u0440\u0430 profile.

        \u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 QPlainTextEdit \u2014 \u0435\u0434\u0438\u043d\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u043f\u0440\u0430\u0432\u0434\u044b; \u043a\u044d\u0448 \u2014 \u0442\u043e\u043b\u044c\u043a\u043e
        \u043c\u0435\u043c\u043e\u0438\u0437\u0430\u0446\u0438\u044f \u0441 \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u0435\u0439 \u043f\u043e textChanged. \u0418\u043d\u043a\u0440\u0435\u043c\u0435\u043d\u0442\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u0430\u0442\u0447\u0438\u043d\u0433\u0430 \u043f\u043e
        contentsChange \u0437\u0434\u0435\u0441\u044c \u0431\u044b\u0442\u044c \u043d\u0435 \u0434\u043e\u043b\u0436\u043d\u043e: Qt \u0443\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442 \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 \u0440\u0430\u0437\u0434\u0435\u043b\u0438\u0442\u0435\u043b\u044c
        \u0431\u043b\u043e\u043a\u0430 \u0432 charsAdded/charsRemoved, \u0438 \u043f\u043e\u0437\u0438\u0446\u0438\u043e\u043d\u043d\u0430\u044f \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u043a\u0430 \u043c\u043e\u043b\u0447\u0430 \u0442\u0435\u0440\u044f\u043b\u0430
        \u0432\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043d\u044b\u0439 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430 \u0442\u0435\u043a\u0441\u0442."""
        cached = self.__dict__.get("_raw_profile_text_cache")
        if cached is not None:
            return str(cached or "")
        editor = self.__dict__.get("_raw_profile_text")
        if editor is None:
            return ""
        try:
            text = str(editor.toPlainText() or "")
        except Exception:
            return ""
        self._raw_profile_text_cache = text
        return text

    def _request_list_file_editor_state(self) -> None:
        return self._list_file_editor_controller_obj()._request_list_file_editor_state()

    def _on_list_file_editor_state_loaded(self, request_id: int, result) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_editor_state_loaded(request_id, result)

    def _list_file_load_result_is_current(self, result) -> bool:
        # Результат — эхо ПОСЛЕДНЕГО запроса (контекст редактирования меняется
        # только через _request_list_file_editor_state: каждая мутация комбо,
        # поля значения и payload планирует перезагрузку). Сверять его с
        # текущими виджетами по именам файлов нельзя: сервис легитимно ремапит
        # пару при kind-switch превью (netrogat.txt → ipset-ru/dns/exclude),
        # и сравнение имён не сходилось бы никогда — вечная «Загрузка...».
        return self._list_file_editor_controller_obj()._list_file_load_result_is_current(result)

    def _schedule_list_file_editor_state_apply(self, state) -> None:
        return self._list_file_editor_controller_obj()._schedule_list_file_editor_state_apply(state)

    def _run_scheduled_list_file_editor_state_apply(self) -> None:
        return self._list_file_editor_controller_obj()._run_scheduled_list_file_editor_state_apply()

    def _on_list_file_editor_state_failed(self, request_id: int, error: str) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_editor_state_failed(request_id, error)

    def _on_list_file_worker_finished(self, _worker) -> None:
        self._list_file_load_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=lambda _runtime, worker: self._accept_current_profile_setup_worker_finished(
                "_list_file_load_request_id",
                worker,
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_list_file_load_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _schedule_pending_list_file_load_start(self) -> None:
        return self._list_file_editor_controller_obj()._schedule_pending_list_file_load_start()

    def _run_scheduled_list_file_load_start(self) -> None:
        return self._list_file_editor_controller_obj()._run_scheduled_list_file_load_start()

    def _list_file_load_state_obj(self) -> LatestValueWorkerState:
        return self._list_file_editor_controller_obj()._list_file_load_state_obj()

    _pending_list_file_load = _worker_pending_property("_list_file_load_state_obj", cast=bool)

    _list_file_load_start_scheduled = _worker_start_scheduled_property("_list_file_load_state_obj")

    def _fill_range_combo(self, combo: CompactDisplayComboBox) -> None:
        combo.addItem("a — всегда", userData="a", compactText="a")
        combo.addItem("x — никогда", userData="x", compactText="x")
        combo.addItem("n — номер пакета", userData="n", compactText="n")
        combo.addItem("d — пакет с данными", userData="d", compactText="d")
        combo.addItem("своё выражение", userData="custom", compactText="своё")

    def _range_mode_description(self, mode: str) -> str:
        descriptions = {
            "a": "a — всегда. Этот range не ограничивает пакеты.",
            "x": "x — никогда. Следующие --lua-desync не будут применяться для этого направления.",
            "n": "n — номер пакета в соединении. Например, n8 означает восьмой пакет.",
            "d": "d — номер пакета с данными. Служебные пакеты без данных не считаются.",
            "custom": "своё выражение — ручной range winws2, например s1<d1 или -d8.",
        }
        return descriptions.get(str(mode or "").strip(), "Неизвестный режим range.")

    def _update_range_tooltips(self, combo: ComboBox, value_edit: LineEdit, *, option_name: str, direction: str) -> None:
        mode = str(combo.itemData(combo.currentIndex()) or "").strip()
        mode_description = self._range_mode_description(mode)
        set_tooltip(
            combo,
            f"{option_name} для {direction} пакетов.\n{mode_description}",
        )
        set_tooltip(
            value_edit,
            f"Значение для {option_name}.\n{mode_description}\n"
            "Поле активно для n, d и своего выражения.",
        )

    def _update_all_range_tooltips(self) -> None:
        self._update_range_tooltips(
            self._in_range_mode,
            self._in_range_value,
            option_name="--in-range",
            direction="входящих",
        )
        self._update_range_tooltips(
            self._out_range_mode,
            self._out_range_value,
            option_name="--out-range",
            direction="исходящих",
        )

    def _install_profile_tooltips(self) -> None:
        range_hint = (
            "Диапазон задаёт, на каких пакетах будут работать следующие --lua-desync внутри этого profile.\n"
            "a — всегда, x — никогда, n — номер пакета, d — номер пакета с данными, своё — ручное выражение winws2."
        )
        set_tooltip(
            self._breadcrumb,
            "Хлебные крошки: показывают путь до текущего profile и позволяют вернуться к списку profile или управлению.",
        )
        set_tooltip(
            self._summary,
            "Краткое условие profile: протокол, порты и тип фильтра. По этой строке видно, когда этот profile применяется.",
        )
        set_tooltip(
            self._enabled_checkbox,
            "Включает или выключает этот profile в текущем preset. Если выключить, profile останется в preset, но не будет применяться.",
        )
        set_tooltip(
            self._update_user_profile_button,
            "Изменяет пользовательский profile и обновляет все preset-ы, где есть profile с таким же именем.",
        )
        set_tooltip(
            self._delete_user_profile_button,
            "Удаляет пользовательский profile, его файлы списков и связанные profile-ы из preset-ов.",
        )
        set_tooltip(
            self._filter_combo,
            "Тип фильтра profile. Hostlist — список доменов, ipset — список IP-адресов или подсетей.",
        )
        set_tooltip(
            self._filter_value,
            "Файл списка для текущего profile. Обычно это путь вида lists/youtube.txt или lists/ipset-youtube.txt.",
        )
        set_tooltip(
            self._in_range_label,
            "--in-range — диапазон для входящих пакетов. " + range_hint,
        )
        set_tooltip(
            self._in_range_mode,
            "Режим --in-range. Откройте меню, чтобы увидеть расшифровку a, x, n, d и своего выражения.",
        )
        set_tooltip(
            self._in_range_value,
            "Число или ручная часть --in-range. Поле активно, когда выбран режим n, d или своё выражение.",
        )
        set_tooltip(
            self._out_range_label,
            "--out-range — диапазон для исходящих пакетов. " + range_hint,
        )
        set_tooltip(
            self._out_range_mode,
            "Режим --out-range. Откройте меню, чтобы увидеть расшифровку a, x, n, d и своего выражения.",
        )
        set_tooltip(
            self._out_range_value,
            "Число или ручная часть --out-range. Поле активно, когда выбран режим n, d или своё выражение.",
        )

    def _rebuild_breadcrumb(self) -> None:
        self._breadcrumb.blockSignals(True)
        try:
            breadcrumb_key = (
                tr_catalog(self.control_key, language=self._ui_language, default="Управление"),
                tr_catalog(self.profiles_key, language=self._ui_language, default=self.profiles_default),
                str(getattr(getattr(self._payload, "item", None), "display_name", "") or "Профиль"),
            )
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", breadcrumb_key[0])
            self._breadcrumb.addItem("profiles", breadcrumb_key[1])
            self._breadcrumb.addItem("profile", breadcrumb_key[2])
            set_breadcrumb_accessibility(self._breadcrumb, breadcrumb_key)
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        # Клик по крошке уже удалил из BreadcrumbBar элементы правее выбранного —
        # восстанавливаем полный путь до навигации, иначе при возврате на эту же
        # страницу крошки остаются обрезанными.
        self._rebuild_breadcrumb()
        if key == "control":
            self._open_root()
        elif key == "profiles":
            self._open_profiles()

    def _on_update_user_profile_clicked(self) -> None:
        if self._payload is None:
            return
        profile_id = _user_profile_id_from_payload(self._profile_key, self._payload)
        if not profile_id:
            return
        item = self._payload.item
        protocol, ports = _protocol_and_ports_from_match_lines(tuple(getattr(item, "match_lines", ()) or ()))
        dialog = CreateUserProfileDialog(
            self,
            title="Изменить profile",
            subtitle="Изменяет пользовательский profile и обновляет все preset-ы, где есть profile с таким же именем.",
            button_text="Сохранить",
            name=str(getattr(item, "display_name", "") or ""),
            protocol=protocol,
            ports=ports,
        )
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_update(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _on_delete_user_profile_clicked(self) -> None:
        profile_id = _user_profile_id_from_payload(self._profile_key, self._payload)
        if not profile_id:
            return
        body = (
            "Пользовательский profile будет удалён из библиотеки, его файлы списков будут удалены, "
            "а profile-ы с таким же именем будут убраны из preset-ов."
        )
        dialog = MessageBox(
            "Удалить profile",
            body,
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        set_message_box_button_accessibility(
            dialog,
            yes_name="Удалить пользовательский profile",
            yes_description=body,
            cancel_name="Отменить удаление пользовательского profile",
            cancel_description="Закрывает диалог без удаления пользовательского profile.",
        )
        if not dialog.exec():
            return
        self._request_user_profile_delete(profile_id)

    def _set_user_profile_buttons_enabled(self, enabled: bool) -> None:
        if self._update_user_profile_button is not None:
            set_widget_enabled_if_changed(self._update_user_profile_button, enabled)
        if self._delete_user_profile_button is not None:
            set_widget_enabled_if_changed(self._delete_user_profile_button, enabled)

    def _current_user_profile_id(self) -> str:
        return _user_profile_id_from_payload(self._profile_key, self._payload)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        return self._user_profile_controller_obj()._request_user_profile_update(profile_id, name=name, protocol=protocol, ports=ports)

    def _user_profile_write_operation_running(self) -> bool:
        return self._user_profile_controller_obj()._user_profile_write_operation_running()

    def _queue_user_profile_write_operation(
        self,
        action: str,
        *,
        profile_id: str,
        name: str = "",
        protocol: str = "",
        ports: str = "",
    ) -> None:
        return self._user_profile_controller_obj()._queue_user_profile_write_operation(action, profile_id=profile_id, name=name, protocol=protocol, ports=ports)

    def _pop_next_pending_user_profile_write_operation(self) -> dict[str, str] | None:
        return self._user_profile_controller_obj()._pop_next_pending_user_profile_write_operation()

    def _has_pending_user_profile_write_operation(self) -> bool:
        return self._user_profile_controller_obj()._has_pending_user_profile_write_operation()

    def _schedule_next_pending_user_profile_write_operation_start(self) -> bool:
        return self._user_profile_controller_obj()._schedule_next_pending_user_profile_write_operation_start()

    def _run_scheduled_user_profile_write_operation_start(self) -> None:
        return self._user_profile_controller_obj()._run_scheduled_user_profile_write_operation_start()

    def _user_profile_write_state_obj(self) -> QueuedWorkerState[dict[str, str]]:
        return self._user_profile_controller_obj()._user_profile_write_state_obj()

    @property
    def _pending_user_profile_operations(self) -> list[dict[str, str]]:
        return self._user_profile_write_state_obj().pending

    @_pending_user_profile_operations.setter
    def _pending_user_profile_operations(self, value: list[dict[str, str]]) -> None:
        self._user_profile_write_state_obj().pending = [
            self._user_profile_write_operation_from_pending_operation(operation)
            for operation in list(value or [])
        ]

    @property
    def _pending_user_profile_updates(self) -> list[dict[str, str]]:
        return [
            {
                "profile_id": str(operation.get("profile_id") or ""),
                "name": str(operation.get("name") or ""),
                "protocol": str(operation.get("protocol") or ""),
                "ports": str(operation.get("ports") or ""),
            }
            for operation in self._user_profile_write_state_obj().pending
            if str(operation.get("action") or "") == "update"
        ]

    @_pending_user_profile_updates.setter
    def _pending_user_profile_updates(self, value: list[dict[str, str]]) -> None:
        pending_operations = self._user_profile_write_state_obj().pending
        pending_operations[:] = [
            operation for operation in pending_operations if str(operation.get("action") or "") != "update"
        ]
        pending_operations.extend(
            self._user_profile_write_operation_from_update(update)
            for update in list(value or [])
        )

    @property
    def _pending_user_profile_deletes(self) -> list[str]:
        return [
            str(operation.get("profile_id") or "")
            for operation in self._user_profile_write_state_obj().pending
            if str(operation.get("action") or "") == "delete"
        ]

    @_pending_user_profile_deletes.setter
    def _pending_user_profile_deletes(self, value: list[str]) -> None:
        pending_operations = self._user_profile_write_state_obj().pending
        pending_operations[:] = [
            operation for operation in pending_operations if str(operation.get("action") or "") != "delete"
        ]
        pending_operations.extend(
            self._user_profile_write_operation_from_delete(profile_id)
            for profile_id in list(value or [])
        )

    _user_profile_write_operation_start_scheduled = _worker_start_scheduled_property("_user_profile_write_state_obj")

    @staticmethod
    def _user_profile_write_operation_from_pending_operation(operation) -> dict[str, str]:
        return ProfileUserProfileController._user_profile_write_operation_from_pending_operation(operation)

    @staticmethod
    def _user_profile_write_operation_from_update(update) -> dict[str, str]:
        return ProfileUserProfileController._user_profile_write_operation_from_update(update)

    @staticmethod
    def _user_profile_write_operation_from_delete(profile_id) -> dict[str, str]:
        return ProfileUserProfileController._user_profile_write_operation_from_delete(profile_id)

    def _start_next_pending_user_profile_write_operation(self) -> bool:
        return self._user_profile_controller_obj()._start_next_pending_user_profile_write_operation()

    def _run_user_profile_write_operation(self, pending: dict[str, str] | None) -> bool:
        return self._user_profile_controller_obj()._run_user_profile_write_operation(pending)

    def _queue_user_profile_write_operation_from_dict(self, operation: dict[str, str]) -> bool:
        return self._user_profile_controller_obj()._queue_user_profile_write_operation_from_dict(operation)

    def _schedule_next_user_profile_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        return self._user_profile_controller_obj()._schedule_next_user_profile_write_operation_after_finish(request_attr, worker)

    def _start_user_profile_update_worker(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        return self._user_profile_controller_obj()._start_user_profile_update_worker(profile_id, name=name, protocol=protocol, ports=ports)

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        _profile_items=(),
    ) -> None:
        return self._user_profile_controller_obj()._on_user_profile_update_finished(request_id, profile_id, changed, _profile_items)

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        return self._user_profile_controller_obj()._on_user_profile_update_failed(request_id, error)

    def _on_user_profile_update_worker_finished(self, _worker) -> None:
        return self._user_profile_controller_obj()._on_user_profile_update_worker_finished(_worker)

    def _apply_user_profile_update_locally(self, updated_item) -> bool:
        payload = self._payload
        if payload is None or updated_item is None:
            return False
        try:
            self._payload = replace(payload, item=updated_item)
        except Exception:
            return False
        self._schedule_profile_setup_payload_apply(self._payload)
        return True

    def _request_user_profile_delete(self, profile_id: str) -> None:
        return self._user_profile_controller_obj()._request_user_profile_delete(profile_id)

    def _start_user_profile_delete_worker(self, profile_id: str) -> None:
        return self._user_profile_controller_obj()._start_user_profile_delete_worker(profile_id)

    def _on_user_profile_delete_finished(self, request_id: int, profile_id: str, changed: int) -> None:
        return self._user_profile_controller_obj()._on_user_profile_delete_finished(request_id, profile_id, changed)

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        return self._user_profile_controller_obj()._on_user_profile_delete_failed(request_id, error)

    def _on_user_profile_delete_worker_finished(self, _worker) -> None:
        return self._user_profile_controller_obj()._on_user_profile_delete_worker_finished(_worker)

    def show_profile(self, profile_key: str) -> None:
        next_key = str(profile_key or "").strip()
        current_key = str(self._profile_key or "").strip()
        if next_key and next_key == current_key and self._payload is not None:
            return
        if next_key != current_key:
            self._flush_list_file_autosave_before_switch(current_key)
            self._payload = None
            self._pending_profile_setup_payload_apply = None
            self._profile_setup_payload_apply_scheduled = False
            self._pending_list_file_state_apply = None
            self._last_profile_setup_payload_apply_signature = None
            self._list_file_state_apply_scheduled = False
            self._list_file_dirty = True
            # Новый профиль — прежние правки редактора списка не его: baseline
            # в «незнание», чтобы первое состояние применилось. Снапшот НЕ
            # трогаем: он обязан зеркалить редактор для инкрементальных патчей.
            self._list_file_server_text_snapshot = None
        self._profile_key = next_key
        self.reload_current_profile()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "open_profile":
            self.show_profile(str((payload or {}).get("profile_key") or ""))
            return True
        return False

    def reload_current_profile(self) -> None:
        self._request_profile_setup_payload()

    def _profile_result_reference(self, payload, profile_key: str) -> str:
        """Единая валюта ссылок страницы: стабильная ссылка из payload-элемента,
        и только при её отсутствии — ключ из результата операции. Позиционный
        "profile:N" в self._profile_key протухает при сдвиге соседей."""
        item = getattr(payload, "item", None) if payload is not None else None
        reference = profile_reference_key(item) if item is not None else ""
        return reference or str(profile_key or "").strip()

    def _emit_profile_changed(
        self,
        profile_key: str,
        change_kind: str,
        profile_item=None,
        *,
        old_profile_key: str = "",
    ) -> None:
        """Уведомляет страницу preset о правке profile. Пара old→new нужна
        списку для точечной замены строки, когда правка имени/match-строк
        сменила persistent_key; при old == new ведём себя как раньше."""
        clean_key = str(profile_key or "").strip()
        old_key = str(old_profile_key or "").strip()
        if old_key and old_key != clean_key:
            self._on_profile_changed_callback(clean_key, change_kind, profile_item, old_profile_key=old_key)
            return
        if profile_item is not None:
            self._on_profile_changed_callback(clean_key, change_kind, profile_item)
            return
        self._on_profile_changed_callback(clean_key, change_kind)

    def create_profile_setup_load_worker(self, request_id: int, profile_key: str, parent=None):
        return self._create_profile_setup_load_worker_fn(request_id, self.launch_method, profile_key=profile_key, parent=parent)

    def create_profile_list_file_load_worker(
        self,
        request_id: int,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        return self._create_profile_list_file_load_worker_fn(request_id, self.launch_method, profile_key=profile_key, filter_kind=filter_kind, filter_value=filter_value, parent=parent)

    def create_profile_list_file_save_worker(
        self,
        request_id: int,
        profile_key: str,
        text: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        return self._create_profile_list_file_save_worker_fn(request_id, self.launch_method, profile_key=profile_key, text=text, filter_kind=filter_kind, filter_value=filter_value, parent=parent)

    def create_profile_list_file_validation_worker(self, request_id: int, *, kind: str, text: str, parent=None):
        return self._create_profile_list_file_validation_worker_fn(request_id, self.launch_method, kind=kind, text=text, parent=parent)

    def create_profile_settings_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
        parent=None,
    ):
        return self._create_profile_settings_save_worker_fn(request_id, self.launch_method, profile_key=profile_key, filter_kind=filter_kind, filter_value=filter_value, in_range=in_range, out_range=out_range, parent=parent)

    def create_profile_raw_text_save_worker(self, request_id: int, profile_key: str, raw_text: str, parent=None):
        return self._create_profile_raw_text_save_worker_fn(request_id, self.launch_method, profile_key=profile_key, raw_text=raw_text, parent=parent)

    def create_profile_enabled_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        return self._create_profile_enabled_save_worker_fn(request_id, self.launch_method, profile_key=profile_key, enabled=enabled, filter_kind=filter_kind, filter_value=filter_value, parent=parent)

    def create_profile_user_update_worker(
        self,
        request_id: int,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        return self._create_profile_user_update_worker_fn(request_id, self.launch_method, profile_id=profile_id, name=name, protocol=protocol, ports=ports, parent=parent)

    def create_profile_user_delete_worker(self, request_id: int, *, profile_id: str, parent=None):
        return self._create_profile_user_delete_worker_fn(request_id, self.launch_method, profile_id=profile_id, parent=parent)

    def create_profile_strategy_apply_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        strategy_id: str,
        strategy_branch_id: str = "",
        parent=None,
    ):
        return self._create_profile_strategy_apply_worker_fn(request_id, self.launch_method, profile_key=profile_key, strategy_id=strategy_id, strategy_branch_id=strategy_branch_id, parent=parent)

    def create_profile_strategy_feedback_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        return self._create_profile_strategy_feedback_save_worker_fn(request_id, self.launch_method, profile_key=profile_key, strategy_id=strategy_id, rating=rating, favorite=favorite, parent=parent)

    def _request_profile_setup_payload(self) -> None:
        return self._payload_controller_obj()._request_profile_setup_payload()

    def _start_profile_setup_load_worker(self) -> None:
        return self._payload_controller_obj()._start_profile_setup_load_worker()

    def _on_profile_setup_payload_loaded(self, request_id: int, payload) -> None:
        return self._payload_controller_obj()._on_profile_setup_payload_loaded(request_id, payload)

    def _schedule_profile_setup_payload_apply(self, payload, *, apply_signature=None) -> None:
        return self._payload_controller_obj()._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)

    def _run_scheduled_profile_setup_payload_apply(self) -> None:
        return self._payload_controller_obj()._run_scheduled_profile_setup_payload_apply()

    def _on_profile_setup_payload_failed(self, request_id: int, error: str) -> None:
        return self._payload_controller_obj()._on_profile_setup_payload_failed(request_id, error)

    def _on_profile_setup_worker_finished(self, _worker) -> None:
        self._setup_load_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=lambda _runtime, worker: self._accept_current_profile_setup_load_worker_finished(
                worker,
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_profile_setup_load_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _accept_current_profile_setup_load_worker_finished(self, worker) -> bool:
        return self._payload_controller_obj()._accept_current_profile_setup_load_worker_finished(worker)

    def _schedule_profile_setup_load_start(self) -> None:
        return self._payload_controller_obj()._schedule_profile_setup_load_start()

    def _run_scheduled_profile_setup_load_start(self) -> None:
        return self._payload_controller_obj()._run_scheduled_profile_setup_load_start()

    def _setup_load_state_obj(self) -> LatestValueWorkerState:
        return self._payload_controller_obj()._setup_load_state_obj()

    _setup_load_dirty = _worker_pending_property("_setup_load_state_obj", cast=bool)

    _setup_load_start_scheduled = _worker_start_scheduled_property("_setup_load_state_obj")

    def _restore_loaded_payload_header(self, payload) -> None:
        item = getattr(payload, "item", None)
        set_widget_text_if_changed(self._summary, getattr(payload, "match_summary", "") or "")
        if item is not None:
            set_widget_checked_if_changed(self._enabled_checkbox, bool(getattr(item, "enabled", False)))
            set_widget_enabled_if_changed(self._enabled_checkbox, True)

    def _apply_payload(self, payload) -> None:
        self._loading = True
        try:
            item = payload.item
            set_widget_text_if_changed(self._summary, payload.match_summary)
            set_widget_checked_if_changed(self._enabled_checkbox, bool(item.enabled))
            set_widget_enabled_if_changed(self._enabled_checkbox, True)
            user_profile_visible = bool(_user_profile_id_from_payload(self._profile_key, payload))
            if self._update_user_profile_button is not None:
                set_widget_visible_if_changed(self._update_user_profile_button, user_profile_visible)
            if self._delete_user_profile_button is not None:
                set_widget_visible_if_changed(self._delete_user_profile_button, user_profile_visible)
            self._apply_editable_settings(payload)
            self._set_list_file_editor_available(_profile_has_list_file_editor(payload))
            self._sync_editor_tab_label(payload)
            self._apply_strategy_branch_selector(payload)

            self._strategy_list.set_rows(
                entries=payload.strategy_entries,
                states=payload.strategy_states,
                current_strategy_id=_current_strategy_id(payload) or "none",
            )
            set_widget_enabled_if_changed(self._strategy_list, not (item.in_preset and not item.enabled))
            self._list_file_dirty = True
            if self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
                self._request_list_file_editor_state()
            if self._match_tab_built:
                self._apply_match_tab_payload()
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

    def _apply_strategy_branch_selector(self, payload) -> None:
        combo = self._strategy_branch_combo
        bar = self._strategy_branch_bar
        if combo is None or bar is None:
            return
        branches = tuple(getattr(payload, "strategy_branches", ()) or ())
        visible = len(branches) > 1
        set_widget_visible_if_changed(bar, visible)
        if not visible:
            return

        current_id = _current_strategy_branch_id(payload) or str(getattr(branches[0], "branch_id", "") or "")
        branch_rows: list[tuple[str, str]] = []
        selected_index = 0
        for index, branch in enumerate(branches):
            branch_id = str(getattr(branch, "branch_id", "") or "").strip()
            branch_rows.append((branch_id, _strategy_branch_label(branch)))
            if branch_id == current_id:
                selected_index = index
        combo.blockSignals(True)
        try:
            if not _update_strategy_branch_combo_in_place(combo, branch_rows, selected_index):
                combo.clear()
                for branch_id, label in branch_rows:
                    combo.addItem(label, userData=branch_id)
                combo.setCurrentIndex(selected_index)
            _sync_strategy_branch_combo_items_accessibility(combo)
        finally:
            combo.blockSignals(False)
        self._update_profile_setup_accessibility()

    def _on_strategy_branch_changed(self, _index: int) -> None:
        if self._loading or self._payload is None or self._strategy_branch_combo is None:
            return
        branch_id = str(self._strategy_branch_combo.itemData(self._strategy_branch_combo.currentIndex()) or "").strip()
        if not branch_id:
            return
        branches = tuple(getattr(self._payload, "strategy_branches", ()) or ())
        branch = next((item for item in branches if str(getattr(item, "branch_id", "") or "").strip() == branch_id), None)
        if branch is None:
            return
        self._payload = _payload_with_strategy_branch(self._payload, branch_id)
        self._loading = True
        try:
            self._apply_editable_settings(self._payload)
        finally:
            self._loading = False
        self._strategy_list.set_current_strategy_id(str(getattr(branch, "strategy_id", "") or "none").strip() or "none")
        self._apply_feedback_buttons(self._payload)
        if self._match_tab_built:
            self._apply_match_tab_payload()

    def _set_list_file_editor_available(self, available: bool) -> None:
        if self._strategy_tabs is None or self._strategy_stack is None:
            self._editor_tab_available = available
            return
        if available == self._editor_tab_available:
            return

        self._editor_tab_available = available
        if available:
            editor_title = _profile_editor_tab_title(self._payload)
            self._strategy_tabs.insertItem(1, "editor", editor_title, lambda: self._switch_strategy_tab(1))
            self._update_strategy_tabs_accessibility()
            return

        if self._strategy_stack.currentIndex() == 1:
            set_current_index_if_changed(self._strategy_stack, 0)
            set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        self._strategy_tabs.removeWidget("editor")
        self._update_strategy_tabs_accessibility()

    def _sync_editor_tab_label(self, payload) -> None:
        editor_title = _profile_editor_tab_title(payload)
        if self._strategy_tabs is not None and self._editor_tab_available:
            set_tab_item_text_if_changed(self._strategy_tabs, "editor", editor_title)
            set_tooltip(
                self._strategy_tabs,
                f"Готовые стратегии меняют строки --lua-desync. «{editor_title}» меняет файл hostlist/ipset. «Когда применяется» показывает условия profile и итоговый текст. Ctrl+F — поиск по готовым стратегиям.",
            )
            self._update_strategy_tabs_accessibility()

    def _apply_list_file_editor_state(self, state) -> None:
        kind = str(getattr(state, "kind", "") or "").strip().lower()
        display_path = str(getattr(state, "display_path", "") or "").strip()
        text = str(getattr(state, "text", "") or "")
        base_text = str(getattr(state, "base_text", "") or "")
        user_text = str(getattr(state, "user_text", text) or "")
        base_display_path = str(getattr(state, "base_display_path", "") or "").strip()
        user_display_path = str(getattr(state, "user_display_path", display_path) or "").strip()
        editable = bool(getattr(state, "editable", False))
        error_text = str(getattr(state, "error_text", "") or "").strip()
        invalid_lines = tuple(getattr(state, "invalid_lines", ()) or ())
        self._list_file_kind = kind
        visible_user_text = user_text if editable else text
        base_text_changed = self.__dict__.get("_list_file_base_text_snapshot", "") != base_text
        current_user_text = self._current_list_file_text()
        user_text_changed = current_user_text != visible_user_text
        # «Есть несохранённые правки» — производное состояние: текст редактора
        # отличается от последнего подтверждённого сервером. Флаг здесь не
        # годится: его сбрасывал цикл валидации, и поздний ответ воркера
        # затирал набранные домены — они «не сохранялись».
        server_snapshot = self.__dict__.get("_list_file_server_text_snapshot")
        # None — «сервер неизвестен» (первая загрузка, смена профиля или типа
        # фильтра): пришедшее состояние применяется безусловно.
        has_unsaved_edits = (
            isinstance(server_snapshot, str)
            and current_user_text != server_snapshot
        )
        # Удерживать пользовательский текст можно только против состояния ТОГО
        # ЖЕ файла: state другого файла (смена типа/значения фильтра) обязан
        # примениться, иначе текст «переедет» в чужой список при автосейве.
        incoming_identity = (kind, display_path)
        same_file = self.__dict__.get("_list_file_applied_identity") == incoming_identity
        keep_user_edits = user_text_changed and has_unsaved_edits and same_file
        self._list_file_applied_identity = incoming_identity
        if editable and display_path:
            # Актуализируем целевую пару автосейва по фактически показанному
            # файлу — поле значения фильтра могло уже указывать на другой.
            self._list_file_editor_filter = (kind, display_path)
        self._list_file_base_entries_count = (
            _non_negative_int(getattr(state, "base_entries_count", 0))
            if editable
            else 0
        )
        self._list_file_user_entries_count = _non_negative_int(
            getattr(state, "user_entries_count", 0)
        )

        title = "Файл списка"
        if display_path:
            title = f"{display_path} ({'IPset' if kind == 'ipset' else 'Hostlist'})"
        if self._list_file_title is not None:
            set_widget_text_if_changed(self._list_file_title, title)
        if self._list_file_base_title is not None:
            set_widget_visible_if_changed(self._list_file_base_title, editable)
            set_widget_text_if_changed(
                self._list_file_base_title,
                f"База: {base_display_path}" if base_display_path else "База"
            )
        if self._list_file_base_text is not None:
            set_widget_visible_if_changed(self._list_file_base_text, editable)
            self._list_file_base_text.blockSignals(True)
            try:
                if base_text_changed:
                    self._list_file_base_text.setPlainText(base_text)
                if kind == "ipset":
                    set_placeholder_text_if_changed(self._list_file_base_text, "В базе пока нет IP или подсетей.")
                else:
                    set_placeholder_text_if_changed(self._list_file_base_text, "В базе пока нет доменов.")
            finally:
                self._list_file_base_text.blockSignals(False)
        self._list_file_base_text_snapshot = base_text
        if self._list_file_user_title is not None:
            set_widget_visible_if_changed(self._list_file_user_title, editable)
            set_widget_text_if_changed(
                self._list_file_user_title,
                f"Ваши записи: {user_display_path}" if user_display_path else "Ваши записи"
            )
        if self._list_file_text is not None:
            self._list_file_text.blockSignals(True)
            try:
                if user_text_changed and not keep_user_edits:
                    self._list_file_text.setPlainText(visible_user_text)
                set_read_only_if_changed(self._list_file_text, not editable)
                if kind == "ipset":
                    set_placeholder_text_if_changed(self._list_file_text, "IP или подсети по одному на строку:\n1.2.3.4\n10.0.0.0/8")
                else:
                    set_placeholder_text_if_changed(self._list_file_text, "Домены по одному на строку:\nexample.com\nsub.example.org")
            finally:
                self._list_file_text.blockSignals(False)
        # Что сервер знает — фиксируем всегда; текст пользователя — только
        # когда его правки не старше пришедшего состояния.
        self._list_file_server_text_snapshot = visible_user_text
        if not keep_user_edits:
            self._list_file_text_snapshot = visible_user_text
            self._list_file_text_dirty = False
        if self._list_file_save_button is not None:
            set_widget_enabled_if_changed(self._list_file_save_button, editable and not invalid_lines)
        if self._list_file_status_label is not None:
            if editable:
                base_count = self._list_file_base_entries_count
                user_count = self._list_file_user_entries_count
                set_profile_list_status_text(
                    self._list_file_status_label,
                    f"Записей всего: {base_count + user_count} • ваших: {user_count}"
                )
            else:
                set_profile_list_status_text(
                    self._list_file_status_label,
                    error_text or "Файл списка недоступен для редактирования.",
                )
        self._list_file_validation_has_error = bool(invalid_lines)
        self._render_list_file_validation(invalid_lines, fallback_error=error_text if not editable else "")

    def _on_list_file_text_changed(self) -> None:
        if self._loading or self._list_file_text is None:
            return
        self._list_file_text_dirty = True
        save_button = self.__dict__.get("_list_file_save_button")
        if save_button is not None:
            set_widget_enabled_if_changed(save_button, False)
        timer = self.__dict__.get("_list_file_validation_timer")
        if timer is not None:
            try:
                timer.start(180)
            except TypeError:
                timer.start()
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Проверка списка...")
        if timer is not None:
            return
        self._run_scheduled_list_file_validation()

    def _current_list_file_text(self) -> str:
        """\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0435\u043a\u0441\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u0441\u043a\u043e\u0433\u043e \u0440\u0435\u0434\u0430\u043a\u0442\u043e\u0440\u0430 \u0441\u043f\u0438\u0441\u043a\u0430.

        \u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 QPlainTextEdit \u2014 \u0435\u0434\u0438\u043d\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u043f\u0440\u0430\u0432\u0434\u044b; \u0441\u043d\u0430\u043f\u0448\u043e\u0442 \u2014 \u0442\u043e\u043b\u044c\u043a\u043e
        \u043c\u0435\u043c\u043e\u0438\u0437\u0430\u0446\u0438\u044f \u0441 \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u0435\u0439 \u043f\u043e textChanged (_list_file_text_dirty).
        \u0418\u043d\u043a\u0440\u0435\u043c\u0435\u043d\u0442\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u0430\u0442\u0447\u0438\u043d\u0433\u0430 \u043f\u043e contentsChange \u0437\u0434\u0435\u0441\u044c \u0431\u044b\u0442\u044c \u043d\u0435 \u0434\u043e\u043b\u0436\u043d\u043e: Qt
        \u0443\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442 \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 \u0440\u0430\u0437\u0434\u0435\u043b\u0438\u0442\u0435\u043b\u044c \u0431\u043b\u043e\u043a\u0430 \u0432 charsAdded/charsRemoved, \u0438
        \u043f\u043e\u0437\u0438\u0446\u0438\u043e\u043d\u043d\u0430\u044f \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u043a\u0430 \u043c\u043e\u043b\u0447\u0430 \u0442\u0435\u0440\u044f\u043b\u0430 \u0432\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043d\u044b\u0439 \u0438\u0437 \u0431\u0443\u0444\u0435\u0440\u0430 \u0442\u0435\u043a\u0441\u0442 \u2014
        \u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f \u0440\u0443\u0433\u0430\u043b\u0430\u0441\u044c \u043d\u0430 \u0444\u0430\u043d\u0442\u043e\u043c\u043d\u044b\u0435 \u0441\u0442\u0440\u043e\u043a\u0438, \u0430 \u0430\u0432\u0442\u043e\u0441\u0435\u0439\u0432 \u043f\u0438\u0441\u0430\u043b \u0431\u0438\u0442\u044b\u0439 \u0441\u043d\u0430\u043f\u0448\u043e\u0442."""
        snapshot = str(self.__dict__.get("_list_file_text_snapshot", "") or "")
        if not bool(self.__dict__.get("_list_file_text_dirty", True)):
            return snapshot
        editor = self.__dict__.get("_list_file_text")
        if editor is None:
            return snapshot
        try:
            text = str(editor.toPlainText() or "")
        except Exception:
            return snapshot
        self._list_file_text_snapshot = text
        self._list_file_text_dirty = False
        return text

    def _run_scheduled_list_file_validation(self) -> None:
        return self._list_file_editor_controller_obj()._run_scheduled_list_file_validation()

    def _request_list_file_validation(self, request: dict) -> None:
        return self._list_file_editor_controller_obj()._request_list_file_validation(request)

    def _resolve_list_file_validation_request(self, request: dict) -> dict[str, str]:
        return self._list_file_editor_controller_obj()._resolve_list_file_validation_request(request)

    def _start_list_file_validation_worker(self, request: dict) -> None:
        return self._list_file_editor_controller_obj()._start_list_file_validation_worker(request)

    def _on_list_file_validation_finished(
        self,
        request_id: int,
        kind: str,
        text: str,
        invalid_lines,
    ) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_validation_finished(request_id, kind, text, invalid_lines)

    def _unsaved_list_file_text(self) -> str | None:
        return self._list_file_editor_controller_obj()._unsaved_list_file_text()

    def _list_file_target_filter(self) -> tuple[str, str]:
        return self._list_file_editor_controller_obj()._list_file_target_filter()

    def _maybe_autosave_list_file(self) -> None:
        return self._list_file_editor_controller_obj()._maybe_autosave_list_file()

    def _flush_list_file_autosave_before_switch(self, previous_key: str) -> None:
        return self._list_file_editor_controller_obj()._flush_list_file_autosave_before_switch(previous_key)

    def _on_list_file_validation_failed(self, request_id: int, error: str) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_validation_failed(request_id, error)

    def _on_list_file_validation_worker_finished(self, _worker) -> None:
        self._list_file_validation_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=lambda _runtime, worker: self._accept_current_profile_setup_worker_finished(
                "_list_file_validation_request_id",
                worker,
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_list_file_validation_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _schedule_pending_list_file_validation_start(self) -> None:
        return self._list_file_editor_controller_obj()._schedule_pending_list_file_validation_start()

    def _run_scheduled_list_file_validation_start(self) -> None:
        return self._list_file_editor_controller_obj()._run_scheduled_list_file_validation_start()

    def _list_file_validation_state_obj(self) -> LatestValueWorkerState:
        return self._list_file_editor_controller_obj()._list_file_validation_state_obj()

    _pending_list_file_validation = _worker_pending_property("_list_file_validation_state_obj")

    _list_file_validation_start_scheduled = _worker_start_scheduled_property("_list_file_validation_state_obj")

    def _on_list_file_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._list_file_text is None:
            return
        self._request_list_file_save(
            self._profile_key,
            self._current_list_file_text(),
            filter_kind=self._current_filter_kind(),
            filter_value=self._current_filter_value(),
        )

    def _request_list_file_save(
        self,
        profile_key: str,
        text: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> None:
        return self._list_file_editor_controller_obj()._request_list_file_save(profile_key, text, filter_kind=filter_kind, filter_value=filter_value)

    def _start_list_file_save_worker(
        self,
        profile_key: str,
        text: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> None:
        return self._list_file_editor_controller_obj()._start_list_file_save_worker(profile_key, text, filter_kind=filter_kind, filter_value=filter_value)

    def _on_list_file_save_finished(self, request_id: int, state, payload=None) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_save_finished(request_id, state, payload)

    def _on_list_file_save_failed(self, request_id: int, error: str) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_save_failed(request_id, error)

    def _on_list_file_save_worker_finished(self, worker) -> None:
        return self._list_file_editor_controller_obj()._on_list_file_save_worker_finished(worker)

    def _schedule_pending_list_file_save_start(
        self,
        profile_key: str | None = None,
        text: str | None = None,
        *,
        filter_kind: str | None = None,
        filter_value: str | None = None,
    ) -> None:
        return self._list_file_editor_controller_obj()._schedule_pending_list_file_save_start(profile_key, text, filter_kind=filter_kind, filter_value=filter_value)

    def _run_scheduled_list_file_save_start(self) -> None:
        return self._list_file_editor_controller_obj()._run_scheduled_list_file_save_start()

    def _list_file_save_state_obj(self) -> LatestValueWorkerState:
        return self._list_file_editor_controller_obj()._list_file_save_state_obj()

    _pending_list_file_save = _worker_pending_property("_list_file_save_state_obj")

    _scheduled_list_file_save = _worker_pending_property("_list_file_save_state_obj")

    _list_file_save_start_scheduled = _worker_start_scheduled_property("_list_file_save_state_obj")

    def _render_list_file_validation(
        self,
        invalid_lines: tuple[tuple[int, str], ...],
        *,
        fallback_error: str = "",
    ) -> None:
        has_error = bool(invalid_lines or fallback_error)
        self._refresh_list_file_editor_style(has_error=has_error)
        if self._list_file_error_label is None:
            return
        if invalid_lines:
            lines = [
                f"Строка {line}: {value}"
                for line, value in invalid_lines[:5]
            ]
            if len(invalid_lines) > 5:
                lines.append(f"И ещё ошибок: {len(invalid_lines) - 5}")
            set_profile_list_error_text(self._list_file_error_label, "Неверные строки:\n" + "\n".join(lines))
            set_widget_visible_if_changed(self._list_file_error_label, True)
            return
        if fallback_error:
            set_profile_list_error_text(self._list_file_error_label, fallback_error)
            set_widget_visible_if_changed(self._list_file_error_label, True)
            return
        set_widget_text_if_changed(self._list_file_error_label, "")
        set_widget_visible_if_changed(self._list_file_error_label, False)

    def _refresh_list_file_editor_style(self, *, has_error: bool) -> None:
        if self._list_file_text is None:
            return
        tokens = get_theme_tokens()
        error_color = "#ff6b6b"
        normal_style = f"""
            QPlainTextEdit {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:hover {{
                background: {tokens.surface_bg_hover};
                border: 1px solid {tokens.surface_border_hover};
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {tokens.accent_hex};
            }}
        """
        error_style = f"""
            QPlainTextEdit {{
                background: rgba(255, 100, 100, 0.06);
                border: 1px solid {error_color};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {error_color};
            }}
        """
        if self._list_file_base_text is not None:
            set_widget_style_sheet_if_changed(self._list_file_base_text, normal_style)
        set_widget_style_sheet_if_changed(self._list_file_text, error_style if has_error else normal_style)
        if self._list_file_error_label is not None:
            set_widget_style_sheet_if_changed(
                self._list_file_error_label,
                f"color: {error_color}; background: transparent;",
            )
        if self._list_file_status_label is not None:
            set_widget_style_sheet_if_changed(
                self._list_file_status_label,
                f"color: {tokens.fg_faint}; background: transparent;",
            )

    def _apply_feedback_buttons(self, payload) -> None:
        item = payload.item
        state = payload.current_strategy_state
        editable = bool(
            item.in_preset
            and item.enabled
            and item.strategy_id not in {"", "none", "custom"}
        )
        for button in (self._work_button, self._notwork_button, self._favorite_button, self._clear_feedback_button):
            if button is not None:
                set_widget_enabled_if_changed(button, editable)
        if self._favorite_button is not None:
            favorite_text = "Убрать из избранного" if state.favorite else "В избранное"
            favorite_action_name = (
                "Убрать стратегию из избранного"
                if state.favorite
                else "Добавить стратегию в избранное"
            )
            set_widget_text_if_changed(self._favorite_button, favorite_text)
            set_control_accessibility(
                self._favorite_button,
                name=favorite_action_name,
                description="Добавляет текущую готовую стратегию в избранное или убирает её оттуда.",
            )
            _set_strategy_favorite_button_state(
                self._favorite_button,
                action_name=favorite_action_name,
                favorite=state.favorite,
            )
        if self._work_button is not None:
            work_selected = state.rating == "work"
            set_widget_property_if_changed(self._work_button, "selected", work_selected)
            _set_strategy_feedback_button_state(
                self._work_button,
                action_name="Отметить стратегию как рабочую",
                selected=work_selected,
            )
        if self._notwork_button is not None:
            notwork_selected = state.rating == "notwork"
            set_widget_property_if_changed(self._notwork_button, "selected", notwork_selected)
            _set_strategy_feedback_button_state(
                self._notwork_button,
                action_name="Отметить стратегию как нерабочую",
                selected=notwork_selected,
            )
        if self._clear_feedback_button is not None:
            _set_strategy_clear_feedback_button_state(
                self._clear_feedback_button,
                rating=state.rating,
            )

    def _apply_editable_settings(self, payload) -> None:
        is_preset_mode = is_preset_launch_method(self.launch_method)
        is_winws2 = is_zapret2_launch_method(self.launch_method)
        if not is_preset_mode:
            if self._settings_container is not None:
                set_widget_visible_if_changed(self._settings_container, False)
            return

        filter_enabled = bool(getattr(payload, "editable_filter_enabled", True))
        available_kinds = tuple(getattr(payload, "editable_filter_kinds", ()) or ())
        filter_switchable = filter_enabled and len({kind for kind in available_kinds if kind in {"hostlist", "ipset"}}) > 1
        if self._settings_container is not None:
            set_widget_visible_if_changed(self._settings_container, is_winws2 or filter_switchable)
        self._rebuild_filter_kind_combo(
            available_kinds,
            str(getattr(payload, "editable_filter_kind", "") or "hostlist"),
        )
        set_combo_by_data(self._filter_combo, getattr(payload, "editable_filter_kind", "") or "hostlist")
        set_widget_text_if_changed(self._filter_value, str(getattr(payload, "editable_filter_value", "") or ""))
        set_widget_visible_if_changed(self._filter_combo, filter_switchable)
        set_widget_visible_if_changed(self._filter_value, filter_switchable)
        for widget in (
            self._in_range_label,
            self._in_range_mode,
            self._in_range_value,
            self._out_range_label,
            self._out_range_mode,
            self._out_range_value,
        ):
            if widget is not None:
                set_widget_visible_if_changed(widget, is_winws2)
        set_range_controls(self._in_range_mode, self._in_range_value, getattr(payload, "in_range", "") or "x")
        set_range_controls(self._out_range_mode, self._out_range_value, getattr(payload, "out_range", "") or "a")
        self._update_all_range_tooltips()
        self._update_profile_setup_accessibility()

    def _rebuild_filter_kind_combo(self, available_kinds: tuple[str, ...], current_kind: str) -> None:
        labels = {
            "hostlist": tr_catalog("page.winws2_profile_setup.filter.hostlist", language=self._ui_language, default="Hostlist"),
            "ipset": tr_catalog("page.winws2_profile_setup.filter.ipset", language=self._ui_language, default="IPset"),
        }
        kinds: list[str] = []
        for kind in (*available_kinds, current_kind):
            normalized = str(kind or "").strip().lower()
            if normalized in labels and normalized not in kinds:
                kinds.append(normalized)
        if not kinds:
            kinds = ["hostlist"]

        current_items = [
            str(self._filter_combo.itemData(index) or "").strip().lower()
            for index in range(self._filter_combo.count())
        ]
        if current_items == kinds:
            return

        self._filter_combo.blockSignals(True)
        try:
            self._filter_combo.clear()
            for kind in kinds:
                self._filter_combo.addItem(labels[kind], userData=kind)
        finally:
            self._filter_combo.blockSignals(False)

    def _on_range_mode_changed(self, combo: ComboBox, value_edit: LineEdit) -> None:
        sync_range_value_enabled(combo, value_edit)
        if combo is self._in_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--in-range", direction="входящих")
        elif combo is self._out_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--out-range", direction="исходящих")
        self._schedule_settings_autosave()

    def _on_filter_kind_changed(self) -> None:
        # Несохранённые правки принадлежат ПРЕЖНЕМУ файлу: дописываем их туда
        # (тип — из отображённого состояния, значение поля — до синхронизации)
        # и сбрасываем baseline, чтобы состояние нового типа применилось.
        self._flush_list_file_autosave_before_filter_switch()
        self._sync_filter_value_for_kind()
        if self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
            self._request_list_file_editor_state()
        self._schedule_settings_autosave()

    def _on_filter_value_editing_finished(self) -> None:
        # Правка пути в поле — такая же мутация контекста редактора, как смена
        # типа: без перезагрузки последний загруженный результат навсегда
        # остался бы про другой файл.
        if self._loading:
            return
        current_pair = (self._current_filter_kind(), self._current_filter_value())
        if current_pair == tuple(self._list_file_target_filter()):
            return
        self._flush_list_file_autosave_before_filter_switch()
        if self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
            self._request_list_file_editor_state()

    def _flush_list_file_autosave_before_filter_switch(self) -> None:
        if bool(self.__dict__.get("_list_file_validation_has_error", False)):
            self._list_file_server_text_snapshot = None
            return
        snapshot = self._unsaved_list_file_text()
        self._list_file_server_text_snapshot = None
        if snapshot is None or not str(self.__dict__.get("_profile_key", "") or ""):
            return
        # Пара, под которую редактор был загружен, — не текущие значения
        # виджетов: они уже могли смениться.
        target_kind, target_value = self._list_file_target_filter()
        self._request_list_file_save(
            self._profile_key,
            snapshot,
            filter_kind=target_kind,
            filter_value=target_value,
        )

    def _current_filter_kind(self) -> str:
        return str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist")

    def _current_filter_value(self) -> str:
        return self._filter_value.text().strip()

    def _profile_is_only_template(self) -> bool:
        item = getattr(self._payload, "item", None)
        return item is not None and not bool(getattr(item, "in_preset", False))

    def _sync_filter_value_for_kind(self) -> None:
        if self._loading or not is_preset_launch_method(self.launch_method):
            return
        filter_kind = self._current_filter_kind()
        filter_role = str(getattr(self._payload, "editable_filter_role", "") or "primary")
        normalized = normalize_filter_value(self._filter_value.text(), filter_kind, filter_role=filter_role)
        if normalized and normalized != self._filter_value.text().strip():
            self._filter_value.setText(normalized)

    def _schedule_settings_autosave(self) -> None:
        return self._save_controller_obj()._schedule_settings_autosave()

    def _autosave_editable_settings(self) -> None:
        return self._save_controller_obj()._autosave_editable_settings()

    def _request_settings_save(self, request: dict) -> None:
        return self._save_controller_obj()._request_settings_save(request)

    def _start_settings_save_worker(self, request: dict) -> None:
        return self._save_controller_obj()._start_settings_save_worker(request)

    def _on_settings_save_finished(self, request_id: int, saved_keys, payload=None) -> None:
        return self._save_controller_obj()._on_settings_save_finished(request_id, saved_keys, payload)

    def _on_settings_save_failed(self, request_id: int, error: str) -> None:
        return self._save_controller_obj()._on_settings_save_failed(request_id, error)

    def _on_settings_save_worker_finished(self, worker) -> None:
        return self._save_controller_obj()._on_settings_save_worker_finished(worker)

    def _settings_save_state_obj(self) -> LatestValueWorkerState:
        return self._save_controller_obj()._settings_save_state_obj()

    _pending_settings_save = _worker_pending_property("_settings_save_state_obj")

    def _on_raw_profile_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._raw_profile_text is None:
            return
        self._request_raw_profile_save(self._profile_key, None)

    def _resolve_raw_profile_save_text(self, raw_text) -> str:
        return self._save_controller_obj()._resolve_raw_profile_save_text(raw_text)

    def _request_raw_profile_save(self, profile_key: str, raw_text: str | None) -> None:
        return self._save_controller_obj()._request_raw_profile_save(profile_key, raw_text)

    def _start_raw_profile_save_worker(self, profile_key: str, raw_text: str | None) -> None:
        return self._save_controller_obj()._start_raw_profile_save_worker(profile_key, raw_text)

    def _on_raw_profile_save_finished(self, request_id: int, saved_keys, payload=None) -> None:
        return self._save_controller_obj()._on_raw_profile_save_finished(request_id, saved_keys, payload)

    def _on_raw_profile_save_failed(self, request_id: int, error: str) -> None:
        return self._save_controller_obj()._on_raw_profile_save_failed(request_id, error)

    def _on_raw_profile_save_worker_finished(self, worker) -> None:
        return self._save_controller_obj()._on_raw_profile_save_worker_finished(worker)

    def _raw_profile_save_state_obj(self) -> LatestValueWorkerState:
        return self._save_controller_obj()._raw_profile_save_state_obj()

    _pending_raw_profile_save = _worker_pending_property("_raw_profile_save_state_obj")

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        runtime = self._worker_runtime("_enabled_save_runtime")
        worker_state = self._enabled_save_state_obj()
        item = getattr(self.__dict__.get("_payload"), "item", None)
        if not runtime.is_running() and item is not None and bool(getattr(item, "enabled", False)) == enabled:
            return
        if worker_state.is_busy():
            if self.__dict__.get("_enabled_save_runtime_enabled") != enabled:
                worker_state.pending = enabled
            return
        if self._profile_setup_write_is_running():
            if self.__dict__.get("_enabled_save_runtime_enabled") != enabled:
                worker_state.pending = enabled
                self._queue_profile_setup_write_operation({"kind": "enabled_save", "enabled": enabled})
            return
        self._start_enabled_save_worker(enabled)

    def _start_enabled_save_worker(self, enabled: bool) -> None:
        return self._save_controller_obj()._start_enabled_save_worker(enabled)

    def _on_enabled_save_finished(self, request_id: int, profile_key: str, enabled: bool, payload=None) -> None:
        return self._save_controller_obj()._on_enabled_save_finished(request_id, profile_key, enabled, payload)

    def _apply_enabled_locally(self, enabled: bool):
        payload = self._payload
        if payload is None:
            return None
        item = getattr(payload, "item", None)
        if item is None:
            return None
        updated_item = replace(item, enabled=bool(enabled))
        self._payload = replace(payload, item=updated_item)
        checkbox = self._enabled_checkbox
        if checkbox is not None:
            self._loading = True
            try:
                set_widget_checked_if_changed(checkbox, bool(enabled))
                set_widget_enabled_if_changed(checkbox, True)
            finally:
                self._loading = False
        return updated_item

    def _on_enabled_save_failed(self, request_id: int, error: str) -> None:
        return self._save_controller_obj()._on_enabled_save_failed(request_id, error)

    def _on_enabled_save_worker_finished(self, worker) -> None:
        return self._save_controller_obj()._on_enabled_save_worker_finished(worker)

    def _schedule_enabled_save_worker_start(self) -> None:
        return self._save_controller_obj()._schedule_enabled_save_worker_start()

    def _run_scheduled_enabled_save_worker_start(self) -> None:
        return self._save_controller_obj()._run_scheduled_enabled_save_worker_start()

    def _enabled_save_state_obj(self) -> LatestValueWorkerState:
        return self._save_controller_obj()._enabled_save_state_obj()

    _pending_enabled_save = _worker_pending_property("_enabled_save_state_obj")

    _enabled_save_start_scheduled = _worker_start_scheduled_property("_enabled_save_state_obj")

    def _on_strategy_list_activated(self, strategy_id: str) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        if bool(getattr(item, "in_preset", False)) and not bool(getattr(item, "enabled", False)):
            return
        if strategy_id == _current_strategy_id(self._payload):
            return
        self._apply_strategy_locally(strategy_id)
        self._request_strategy_apply(strategy_id)

    def _request_strategy_apply(self, strategy_id: str) -> None:
        return self._strategy_controller_obj()._request_strategy_apply(strategy_id)

    def _start_strategy_apply_worker(self, strategy_id: str, *, strategy_branch_id: str = "") -> None:
        return self._strategy_controller_obj()._start_strategy_apply_worker(strategy_id, strategy_branch_id=strategy_branch_id)

    def _on_strategy_apply_finished(
        self,
        request_id: int,
        requested_profile_key: str,
        profile_key: str,
        strategy_id: str,
        payload=None,
    ) -> None:
        return self._strategy_controller_obj()._on_strategy_apply_finished(request_id, requested_profile_key, profile_key, strategy_id, payload)

    def _on_strategy_apply_failed(self, request_id: int, error: str) -> None:
        return self._strategy_controller_obj()._on_strategy_apply_failed(request_id, error)

    def _on_strategy_apply_worker_finished(self, worker) -> None:
        return self._strategy_controller_obj()._on_strategy_apply_worker_finished(worker)

    def _strategy_apply_state_obj(self) -> LatestValueWorkerState:
        return self._strategy_controller_obj()._strategy_apply_state_obj()

    _pending_strategy_apply = _worker_pending_property("_strategy_apply_state_obj")

    def _apply_strategy_locally(self, strategy_id: str) -> bool:
        payload = self._payload
        if payload is None:
            return False
        item = getattr(payload, "item", None)
        if item is None or not bool(getattr(item, "in_preset", False)):
            return False
        entry = (getattr(payload, "strategy_entries", {}) or {}).get(strategy_id)
        if entry is None:
            return False

        state = (getattr(payload, "strategy_states", {}) or {}).get(strategy_id, ProfileStrategyState())
        branches = tuple(getattr(payload, "strategy_branches", ()) or ())
        current_branch_id = _current_strategy_branch_id(payload)
        if branches and current_branch_id:
            entry_args = str(getattr(entry, "args", "") or "").strip()
            updated_branch_items = []
            for branch in branches:
                if str(getattr(branch, "branch_id", "") or "").strip() != current_branch_id:
                    updated_branch_items.append(branch)
                    continue
                raw_strategy_text = _branch_raw_strategy_text(branch, entry_args)
                updated_branch = replace(
                    branch,
                    strategy_id=strategy_id,
                    strategy_name=str(getattr(entry, "name", "") or strategy_id),
                    raw_strategy_text=raw_strategy_text,
                )
                updated_branch_items.append(
                    replace(
                        updated_branch,
                        match_tab_text=_branch_match_tab_text(payload, updated_branch, raw_strategy_text),
                    )
                )
            updated_branches = tuple(updated_branch_items)
            selected_branch = next(
                (
                    branch
                    for branch in updated_branches
                    if str(getattr(branch, "branch_id", "") or "").strip() == current_branch_id
                ),
                None,
            )
            next_raw_strategy_text = str(getattr(selected_branch, "raw_strategy_text", "") or entry_args)
            next_strategy_name = str(getattr(entry, "name", "") or strategy_id)
            if len(updated_branches) <= 1:
                updated_item = replace(
                    item,
                    strategy_id=strategy_id,
                    strategy_name=next_strategy_name,
                    enabled=True,
                    rating=str(getattr(state, "rating", "") or ""),
                    favorite=bool(getattr(state, "favorite", False)),
                    strategy_branches=updated_branches,
                )
            else:
                updated_item = replace(
                    item,
                    strategy_id="custom",
                    strategy_name=_strategy_branch_summary_name(updated_branches),
                    enabled=True,
                    rating="",
                    favorite=False,
                    strategy_branches=updated_branches,
                )
            self._payload = replace(
                payload,
                item=updated_item,
                strategy_branches=updated_branches,
                raw_strategy_text=next_raw_strategy_text,
                match_tab_text=str(getattr(selected_branch, "match_tab_text", "") or ""),
                current_strategy_state=state,
            )
            self._strategy_list.set_current_strategy_id(strategy_id)
            self._apply_strategy_branch_selector(self._payload)
            self._apply_feedback_buttons(self._payload)
            if self._match_tab_built:
                self._apply_match_tab_payload()
            return True

        updated_item = replace(
            item,
            strategy_id=strategy_id,
            strategy_name=str(getattr(entry, "name", "") or strategy_id),
            enabled=True,
            rating=str(getattr(state, "rating", "") or ""),
            favorite=bool(getattr(state, "favorite", False)),
        )
        self._payload = replace(
            payload,
            item=updated_item,
            raw_strategy_text=str(getattr(entry, "args", "") or ""),
            match_tab_text=build_profile_setup_match_tab_text(
                match_summary=str(getattr(payload, "match_summary", "") or ""),
                strategy_id=strategy_id,
                strategy_name=str(getattr(entry, "name", "") or strategy_id),
                raw_strategy_text=str(getattr(entry, "args", "") or ""),
            ),
            current_strategy_state=state,
        )
        self._strategy_list.set_current_strategy_id(strategy_id)
        self._apply_feedback_buttons(self._payload)
        if self._match_tab_built:
            self._apply_match_tab_payload()
        return True

    def _set_current_strategy_feedback(self, *, rating: str) -> None:
        if self._loading or not self._profile_key:
            return
        next_rating = str(rating or "").strip()
        state = getattr(getattr(self, "_payload", None), "current_strategy_state", None)
        current_rating = str(getattr(state, "rating", "") or "").strip()
        if next_rating == current_rating:
            return
        self._request_strategy_feedback_save({"rating": next_rating, "favorite": None})

    def _toggle_current_strategy_favorite(self) -> None:
        if self._loading or not self._profile_key or self._payload is None:
            return
        current = bool(self._payload.current_strategy_state.favorite)
        self._request_strategy_feedback_save({"rating": None, "favorite": not current})

    def _request_strategy_feedback_save(self, request: dict) -> None:
        return self._strategy_controller_obj()._request_strategy_feedback_save(request)

    def _merge_pending_strategy_feedback_save(self, request: dict) -> None:
        return self._strategy_controller_obj()._merge_pending_strategy_feedback_save(request)

    def _start_strategy_feedback_save_worker(self, request: dict) -> None:
        return self._strategy_controller_obj()._start_strategy_feedback_save_worker(request)

    def _on_strategy_feedback_save_finished(
        self,
        request_id: int,
        profile_key: str,
        strategy_id: str,
        state,
    ) -> None:
        return self._strategy_controller_obj()._on_strategy_feedback_save_finished(request_id, profile_key, strategy_id, state)

    def _on_strategy_feedback_save_failed(self, request_id: int, error: str) -> None:
        return self._strategy_controller_obj()._on_strategy_feedback_save_failed(request_id, error)

    def _on_strategy_feedback_save_worker_finished(self, worker) -> None:
        return self._strategy_controller_obj()._on_strategy_feedback_save_worker_finished(worker)

    def _schedule_strategy_feedback_save_worker_start(self) -> None:
        return self._strategy_controller_obj()._schedule_strategy_feedback_save_worker_start()

    def _run_scheduled_strategy_feedback_save_worker_start(self) -> None:
        return self._strategy_controller_obj()._run_scheduled_strategy_feedback_save_worker_start()

    def _strategy_feedback_save_state_obj(self) -> LatestValueWorkerState:
        return self._strategy_controller_obj()._strategy_feedback_save_state_obj()

    _pending_strategy_feedback_save = _worker_pending_property("_strategy_feedback_save_state_obj")

    _strategy_feedback_save_start_scheduled = _worker_start_scheduled_property("_strategy_feedback_save_state_obj")

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        timer = self.__dict__.get("_settings_save_timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        timer = self.__dict__.get("_list_file_validation_timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        for attr in (
            "_pending_list_file_load",
            "_pending_list_file_state_apply",
            "_pending_list_file_save",
            "_scheduled_list_file_save",
            "_pending_list_file_validation",
            "_pending_settings_save",
            "_pending_raw_profile_save",
            "_pending_enabled_save",
            "_pending_strategy_apply",
            "_pending_strategy_feedback_save",
            "_scheduled_profile_setup_write_operation",
            "_pending_profile_setup_payload_apply",
        ):
            setattr(self, attr, None)
        self._list_file_state_apply_scheduled = False
        self._setup_load_state_obj().reset()
        self._list_file_load_state_obj().reset()
        self._list_file_validation_state_obj().reset()
        self._list_file_save_state_obj().reset()
        self._settings_save_state_obj().reset()
        self._raw_profile_save_state_obj().reset()
        self._enabled_save_state_obj().reset()
        self._strategy_apply_state_obj().reset()
        self._strategy_feedback_save_state_obj().reset()
        self._user_profile_write_state_obj().reset()
        self._profile_setup_write_state_obj().reset()
        self._profile_setup_payload_apply_scheduled = False
        for attr in (
            "_setup_load_request_id",
            "_list_file_load_request_id",
            "_list_file_save_request_id",
            "_list_file_validation_request_id",
            "_settings_save_request_id",
            "_raw_profile_save_request_id",
            "_enabled_save_request_id",
            "_user_profile_update_request_id",
            "_user_profile_delete_request_id",
            "_strategy_apply_request_id",
            "_strategy_feedback_save_request_id",
        ):
            setattr(self, attr, int(getattr(self, attr, 0) or 0) + 1)
        for attr, warning_prefix, blocking in _PROFILE_SETUP_CLEANUP_RUNTIMES:
            runtime = self.__dict__.get(attr)
            if runtime is None:
                continue
            runtime.stop(blocking=blocking, log_fn=log, warning_prefix=warning_prefix)
            runtime.cancel()
        self._strategy_apply_runtime_strategy_id = ""
        self._enabled_save_runtime_enabled = None
        self._setup_load_runtime_request_id = 0
        try:
            super().cleanup()
        except Exception:
            pass

    def _apply_strategy_feedback_locally(self, state) -> bool:
        if self._payload is None or state is None:
            return False
        item = getattr(self._payload, "item", None)
        if item is None:
            return False
        strategy_id = _current_strategy_id(self._payload)
        if not strategy_id or strategy_id in {"none", "custom"}:
            return False
        next_state = state if isinstance(state, ProfileStrategyState) else ProfileStrategyState()
        strategy_states = dict(getattr(self._payload, "strategy_states", {}) or {})
        strategy_states[strategy_id] = next_state
        updated_item = replace(
            item,
            rating=str(getattr(next_state, "rating", "") or ""),
            favorite=bool(getattr(next_state, "favorite", False)),
        )
        self._payload = replace(
            self._payload,
            item=updated_item,
            strategy_states=strategy_states,
            current_strategy_state=next_state,
        )
        if self._strategy_list is not None:
            self._strategy_list.set_rows(
                entries=getattr(self._payload, "strategy_entries", {}) or {},
                states=strategy_states,
                current_strategy_id=strategy_id,
            )
        self._apply_feedback_buttons(self._payload)
        return True


class Zapret2ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"


class Zapret1ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET1_MODE
    title_key_name = "page.winws1_profile_setup.title"
    control_key = "page.winws1_profile_setup.breadcrumb.control"
    profiles_key = "page.winws1_pages.title"
    profiles_default = "Настройка пресета"


def _protocol_and_ports_from_match_lines(match_lines: tuple[str, ...]) -> tuple[str, str]:
    for protocol, option_name in (("tcp", "--filter-tcp"), ("udp", "--filter-udp"), ("l7", "--filter-l7")):
        values = filter_values(match_lines, option_name)
        if values:
            return protocol, values[0]
    return "tcp", ""


def _user_profile_id_from_payload(profile_key: str, payload) -> str:
    item = getattr(payload, "item", None)
    profile_id = str(getattr(item, "user_profile_id", "") or "").strip()
    if profile_id:
        return profile_id
    key = str(profile_key or "").strip()
    if key.startswith("template:user:"):
        return key.split("template:user:", 1)[1].strip()
    return ""


def _updated_user_profile_item(profile_id: str, profile_key: str, profile_items):
    clean_profile_id = str(profile_id or "").strip()
    clean_profile_key = str(profile_key or "").strip()
    candidates = tuple(profile_items or ())
    for item in candidates:
        if clean_profile_key and str(getattr(item, "key", "") or "").strip() == clean_profile_key:
            return item
    for item in candidates:
        if clean_profile_id and str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id:
            return item
    return None
