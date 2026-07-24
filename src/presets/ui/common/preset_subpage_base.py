from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog

from ui.pages.base_page import BasePage
from ui.fluent_widgets import style_semantic_caption_label
from ui.theme import get_themed_qta_icon
from ui.accessibility import (
    remove_line_edit_buttons_from_tab_order,
    set_breadcrumb_accessibility,
    set_control_accessibility,
    set_state_text,
)
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.queued_worker_state import QueuedWorkerState
from ui.popup_menu import exec_popup_menu
from presets.ui.common.raw_preset_text_editor import RawPresetTextEditor
from presets.ui.common.preset_status_bar import (
    PresetStatusBar,
    build_runtime_preset_status_plan,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    BreadcrumbBar,
    CaptionLabel,
    FluentIcon,
    InfoBar,
    LineEdit,
    PushButton,
    RoundMenu,
    SimpleCardWidget,
    StrongBodyLabel,
    TransparentToolButton,
)
from ui.fluent_dialog import MessageBox, MessageBoxBase


EXTERNAL_RAW_PRESET_RELOAD_COALESCE_MS = 150


def _fluent_icon(name: str):
    if name == "STOP":
        return get_themed_qta_icon("fa5s.stop")
    return getattr(FluentIcon, name, None)


def _make_menu_action(text: str, *, icon=None, parent=None):
    if icon is not None:
        try:
            return Action(icon, text, parent)
        except TypeError:
            pass
    try:
        action = Action(text, parent)
    except TypeError:
        action = Action(text)
    try:
        if icon is not None:
            action.setIcon(icon)
    except Exception:
        pass
    return action


def _set_raw_preset_menu_item_accessibility(menu, *, text: str, disabled: bool = False) -> None:
    menu_view = getattr(menu, "view", None)
    if menu_view is None:
        return
    try:
        item = menu_view.item(menu_view.count() - 1)
    except Exception:
        item = None
    if item is None:
        return
    accessible_text = f"Действие preset: {str(text or '').strip()}"
    if disabled:
        accessible_text = f"{accessible_text}, недоступно"
    try:
        item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
    except Exception:
        pass


@dataclass(frozen=True, slots=True)
class RuntimeToggleButtonPlan:
    text: str
    icon_name: str
    should_stop: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class RawPresetRuntimeActions:
    start: Callable[..., object]
    stop: Callable[..., object]
    is_available: Callable[[], object]


def build_runtime_toggle_button_plan(
    *,
    launch_phase: str,
    launch_running: bool,
    launch_busy: bool,
) -> RuntimeToggleButtonPlan:
    phase = str(launch_phase or "").strip().lower()
    should_stop = bool(launch_running) or phase in {"running", "stopping"}
    transition = phase in {"autostart_pending", "starting", "stopping"} or bool(launch_busy)
    if should_stop:
        return RuntimeToggleButtonPlan(
            text="Остановить",
            icon_name="STOP",
            should_stop=True,
            enabled=not transition,
        )
    return RuntimeToggleButtonPlan(
        text="Запустить",
        icon_name="PLAY",
        should_stop=False,
        enabled=not transition,
    )


def apply_runtime_toggle_button_plan(
    button,
    plan: RuntimeToggleButtonPlan,
    *,
    runtime_available: bool,
    icon_factory=_fluent_icon,
) -> bool:
    enabled = bool(plan.enabled and runtime_available)
    visual_key = (plan.text, plan.icon_name, bool(plan.should_stop))
    plan_key = (*visual_key, enabled)
    if getattr(button, "_last_runtime_toggle_button_plan_key", None) == plan_key:
        return plan.should_stop
    setattr(button, "_last_runtime_toggle_button_plan_key", plan_key)
    if getattr(button, "_last_runtime_toggle_button_visual_key", None) != visual_key:
        setattr(button, "_last_runtime_toggle_button_visual_key", visual_key)
        button.setText(plan.text)
        button.setIcon(icon_factory(plan.icon_name))
    if getattr(button, "_last_runtime_toggle_button_enabled", None) != enabled:
        setattr(button, "_last_runtime_toggle_button_enabled", enabled)
        button.setEnabled(enabled)
    _set_runtime_toggle_accessibility(button, plan, runtime_available=runtime_available)
    return plan.should_stop


def _set_runtime_toggle_accessibility(button, plan: RuntimeToggleButtonPlan, *, runtime_available: bool) -> None:
    action = "Остановить" if plan.should_stop else "Запустить"
    name = f"{action} пресет"
    if runtime_available:
        description = (
            "Останавливает запущенный Zapret с этим пресетом."
            if plan.should_stop
            else "Запускает Zapret с открытым пресетом."
        )
    else:
        description = "Управление Zapret сейчас недоступно."
    set_control_accessibility(
        button,
        name=name,
        description=description,
    )
    set_state_text(button, name)


def set_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.text()) == value:
            return False
    except Exception:
        pass
    widget.setText(value)
    return True


def set_visible_if_changed(widget, visible: bool) -> bool:
    value = bool(visible)
    try:
        if bool(widget.isVisible()) == value:
            return False
    except Exception:
        pass
    widget.setVisible(value)
    return True


def set_enabled_if_changed(widget, enabled: bool) -> bool:
    value = bool(enabled)
    try:
        if bool(widget.isEnabled()) == value:
            return False
    except Exception:
        pass
    widget.setEnabled(value)
    return True


class _RenameDialog(MessageBoxBase):
    def __init__(self, current_name: str, existing_names: list[str], parent=None):
        if parent is not None and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._current_name = str(current_name or "")
        self._existing_names = [n for n in existing_names if n != self._current_name]

        self.titleLabel = StrongBodyLabel("Переименовать", self.widget)
        self.subtitleLabel = BodyLabel(
            "Имя пресета отображается в списке и используется для переключения.",
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(self._current_name)
        self.nameEdit.selectAll()
        self.nameEdit.setClearButtonEnabled(True)
        remove_line_edit_buttons_from_tab_order(self.nameEdit)

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText("Переименовать")
        self.cancelButton.setText("Отмена")
        self.widget.setMinimumWidth(420)
        self._install_accessibility()

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self._show_warning("Введите название.")
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.nameEdit,
            name="Новое название открытого пресета",
            description=f"Текущее имя: {self._current_name}. Введите новое имя для открытого пресета.",
        )
        set_control_accessibility(
            self.yesButton,
            name="Переименовать открытый пресет",
            description="Меняет имя открытого пресета.",
        )
        set_control_accessibility(
            self.cancelButton,
            name="Отменить переименование открытого пресета",
            description="Закрывает окно без изменения имени.",
        )

    def _show_warning(self, text: str) -> None:
        self.warningLabel.setText(text)
        set_state_text(self.warningLabel, f"Ошибка: {text}")


class PresetRawEditorPage(BasePage):
    def __init__(
        self,
        parent=None,
        *,
        create_raw_preset_load_worker,
        create_raw_preset_save_worker,
        create_raw_preset_activate_worker,
        create_raw_preset_action_worker,
        launch_method: str,
        title: str,
        open_back,
        open_root,
        runtime_actions: RawPresetRuntimeActions | None,
        ui_state_store,
    ):
        self._launch_method = str(launch_method or "").strip()
        self._title = str(title or "").strip() or "Пресет"
        super().__init__(self._title, "", parent)
        self._open_back_callback = open_back
        self._open_root_callback = open_root
        self._runtime_actions = runtime_actions
        self._preset_name = ""
        self._preset_file_name = ""
        self._preset_path: Path | None = None
        self._preset_origin = "user"
        self._preset_can_reset_to_builtin = False
        self._active_preset_file_name = ""
        self._active_preset_name = ""
        self._raw_editor_text_snapshot: str | None = None
        self._raw_preset_content_loaded_once = False
        self._raw_preset_content_dirty = True
        self._ignore_next_raw_preset_content_revision = False
        self._raw_editor_text_cache_update_suspended = False
        self._raw_editor_show_scheduled = False
        self._is_loading = False
        self._raw_load_runtime = OneShotWorkerRuntime()
        self._raw_load_request_id = 0
        self._raw_load_runtime_request_id = 0
        self._raw_load_state = LatestValueWorkerState(
            self._raw_load_runtime,
            empty_value=False,
        )
        self._raw_text_apply_scheduled = False
        self._pending_raw_text_apply = None
        self._raw_save_runtime = OneShotWorkerRuntime()
        self._raw_save_request_id = 0
        self._raw_preset_save_state = LatestValueWorkerState(
            self._raw_save_runtime,
            empty_value=None,
        )
        self._after_raw_preset_save = None
        self._raw_save_succeeded = True
        self._raw_activate_runtime = OneShotWorkerRuntime()
        self._raw_activate_request_id = 0
        self._raw_preset_activation_state = LatestValueWorkerState(
            self._raw_activate_runtime,
            empty_value="",
        )
        self._raw_action_runtime = OneShotWorkerRuntime()
        self._raw_action_request_id = 0
        self._raw_preset_write_state = QueuedWorkerState[dict[str, object]](object())
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._footer_status = "neutral"
        self._footer_text = ""
        self._content_publish_pending = False
        self._app_event_filter_installed = False
        self._runtime_toggle_should_stop = False
        self._create_raw_preset_load_worker_fn = create_raw_preset_load_worker
        self._create_raw_preset_save_worker_fn = create_raw_preset_save_worker
        self._create_raw_preset_activate_worker_fn = create_raw_preset_activate_worker
        self._create_raw_preset_action_worker_fn = create_raw_preset_action_worker
        self._raw_text_editor = RawPresetTextEditor(
            self,
            request_save=lambda *, publish_content_changed=False: self._save_file(
                publish_content_changed=bool(publish_content_changed),
            ),
            set_footer=self._set_footer,
            cleanup_in_progress=lambda: bool(self.__dict__.get("_cleanup_in_progress", False))
            or bool(self.__dict__.get("_is_loading", False)),
        )
        self._sync_raw_text_editor_state_from_legacy()
        self.searchInput = self._raw_text_editor.search_input
        self.editor = self._raw_text_editor.editor
        self._save_timer = self._raw_text_editor.save_timer
        self._commit_timer = self._raw_text_editor.commit_timer

        self._build_ui()
        self.editor.installEventFilter(self)
        self.searchInput.installEventFilter(self)
        try:
            self.editor.viewport().installEventFilter(self)
        except Exception:
            pass
        # App-wide фильтр (коммит правок по клику вне редактора) ставится только
        # пока страница видима — см. on_page_activated/on_page_hidden.
        self.bind_ui_state_store(ui_state_store)

    def _raw_worker_runtime(self, attr: str) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            setattr(self, attr, runtime)
        return runtime

    _RAW_TEXT_STATE_LEGACY_KEYS = (
        ("_raw_editor_text_snapshot", "text_snapshot", None),
        ("_raw_preset_content_loaded_once", "content_loaded_once", False),
        ("_raw_preset_content_dirty", "content_dirty", True),
        ("_raw_editor_text_cache_update_suspended", "cache_update_suspended", False),
        ("_raw_editor_show_scheduled", "show_scheduled", False),
        ("_content_publish_pending", "content_publish_pending", False),
    )

    def _sync_raw_text_editor_state_from_legacy(self) -> None:
        """Переносит состояние в редактор и удаляет legacy-копии.

        После этого единственный владелец состояния текста — RawPresetTextEditor;
        properties ниже только делегируют (dict-ветка остаётся для окна до
        создания редактора и для тестов, конструирующих страницу через __new__).
        """
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is None:
            return
        for legacy_key, editor_attr, default in self._RAW_TEXT_STATE_LEGACY_KEYS:
            if legacy_key in self.__dict__:
                value = self.__dict__.pop(legacy_key)
            else:
                value = default
            if editor_attr == "text_snapshot":
                setattr(text_editor, editor_attr, None if value is None else str(value))
            else:
                setattr(text_editor, editor_attr, bool(value))

    def _raw_text_state_get(self, legacy_key: str, editor_attr: str, default):
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            return getattr(text_editor, editor_attr)
        return self.__dict__.get(legacy_key, default)

    def _raw_text_state_set(self, legacy_key: str, editor_attr: str, value) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            setattr(text_editor, editor_attr, value)
            return
        self.__dict__[legacy_key] = value

    @property
    def _raw_editor_text_snapshot(self):
        return self._raw_text_state_get("_raw_editor_text_snapshot", "text_snapshot", None)

    @_raw_editor_text_snapshot.setter
    def _raw_editor_text_snapshot(self, value) -> None:
        self._raw_text_state_set(
            "_raw_editor_text_snapshot",
            "text_snapshot",
            None if value is None else str(value),
        )

    @property
    def _raw_preset_content_loaded_once(self) -> bool:
        return bool(self._raw_text_state_get("_raw_preset_content_loaded_once", "content_loaded_once", False))

    @_raw_preset_content_loaded_once.setter
    def _raw_preset_content_loaded_once(self, value: bool) -> None:
        self._raw_text_state_set("_raw_preset_content_loaded_once", "content_loaded_once", bool(value))

    @property
    def _raw_preset_content_dirty(self) -> bool:
        return bool(self._raw_text_state_get("_raw_preset_content_dirty", "content_dirty", True))

    @_raw_preset_content_dirty.setter
    def _raw_preset_content_dirty(self, value: bool) -> None:
        self._raw_text_state_set("_raw_preset_content_dirty", "content_dirty", bool(value))

    @property
    def _raw_editor_text_cache_update_suspended(self) -> bool:
        return bool(
            self._raw_text_state_get("_raw_editor_text_cache_update_suspended", "cache_update_suspended", False)
        )

    @_raw_editor_text_cache_update_suspended.setter
    def _raw_editor_text_cache_update_suspended(self, value: bool) -> None:
        self._raw_text_state_set("_raw_editor_text_cache_update_suspended", "cache_update_suspended", bool(value))

    @property
    def _raw_editor_show_scheduled(self) -> bool:
        return bool(self._raw_text_state_get("_raw_editor_show_scheduled", "show_scheduled", False))

    @_raw_editor_show_scheduled.setter
    def _raw_editor_show_scheduled(self, value: bool) -> None:
        self._raw_text_state_set("_raw_editor_show_scheduled", "show_scheduled", bool(value))

    @property
    def _content_publish_pending(self) -> bool:
        return bool(self._raw_text_state_get("_content_publish_pending", "content_publish_pending", False))

    @_content_publish_pending.setter
    def _content_publish_pending(self, value: bool) -> None:
        self._raw_text_state_set("_content_publish_pending", "content_publish_pending", bool(value))

    def _raw_worker_runtime_is_running(self, attr: str) -> bool:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            return False
        return bool(runtime.is_running())

    def _accept_current_raw_write_worker_finished(self, request_attr: str, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            return int(request_id) == int(self.__dict__.get(request_attr, 0) or 0)
        except (TypeError, ValueError):
            return False

    def _raw_preset_write_is_running(self) -> bool:
        if self._raw_preset_write_state_obj().start_scheduled:
            return True
        if self._raw_preset_save_state_obj().start_scheduled:
            return True
        if self._raw_preset_activation_state_obj().start_scheduled:
            return True
        for attr in ("_raw_save_runtime", "_raw_activate_runtime", "_raw_action_runtime"):
            runtime = self.__dict__.get(attr)
            if runtime is not None and runtime.is_running():
                return True
        return False

    def _queue_raw_preset_write_operation(self, operation: dict[str, object]) -> None:
        pending = self._raw_preset_write_state_obj().pending
        queued = dict(operation)
        if pending and pending[-1] == queued:
            return
        if (
            pending
            and queued.get("kind") != "action"
            and pending[-1].get("kind") == queued.get("kind")
        ):
            pending[-1] = queued
            return
        pending.append(queued)

    def _start_next_raw_preset_write_operation(self) -> bool:
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._raw_preset_write_is_running():
            return False
        state = self._raw_preset_write_state_obj()
        if not state.has_pending():
            return False
        operation = dict(state.pop_next() or {})
        return self._run_raw_preset_write_operation(operation)

    def _run_raw_preset_write_operation(self, operation: dict[str, object] | None) -> bool:
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._raw_preset_write_is_running():
            self._queue_raw_preset_write_operation(dict(operation or {}))
            return False
        operation = dict(operation or {})
        kind = str(operation.get("kind") or "")
        if kind == "activate":
            self._raw_preset_activation_state_obj().pending = ""
            self._start_preset_activation_worker(str(operation.get("file_name") or ""))
            return True
        if kind == "save":
            self._start_raw_preset_save_worker(
                file_name=str(operation.get("file_name") or ""),
                source_text=operation.get("source_text"),
                publish_content_changed=bool(operation.get("publish_content_changed")),
            )
            return True
        if kind == "action":
            action = str(operation.get("action") or "")
            payload = operation.get("payload")
            self._start_raw_preset_action_worker(
                action,
                **(dict(payload) if isinstance(payload, dict) else {}),
            )
            return True
        return bool(self._start_next_raw_preset_write_operation())

    def _queue_raw_preset_write_operation_from_dict(self, operation: dict[str, object]) -> bool:
        self._queue_raw_preset_write_operation(dict(operation or {}))
        return True

    def _schedule_next_raw_preset_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        accepted = False

        def _is_current_worker_finish(_runtime, finished_worker) -> bool:
            nonlocal accepted
            accepted = self._accept_current_raw_write_worker_finished(request_attr, finished_worker)
            return accepted

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        operation = self._raw_preset_write_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=_is_current_worker_finish,
            single_shot=_single_shot,
            start=lambda pending: self._run_raw_preset_write_operation(dict(pending or {})),
            queue_item=self._queue_raw_preset_write_operation_from_dict,
            is_cleanup_in_progress=lambda: bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        return accepted, operation is not None

    def _schedule_next_raw_preset_write_operation_start(self) -> bool:
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._raw_preset_write_is_running():
            return True
        state = self._raw_preset_write_state_obj()
        if not state.has_pending():
            return False
        if state.start_scheduled:
            return True
        state.start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_raw_preset_write_operation_start)
        except Exception:
            self._run_scheduled_raw_preset_write_operation_start()
        return True

    def _run_scheduled_raw_preset_write_operation_start(self) -> None:
        self._raw_preset_write_state_obj().start_scheduled = False
        self._start_next_raw_preset_write_operation()

    def _raw_preset_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        state = self.__dict__.get("_raw_preset_write_state")
        if state is None:
            pending = self.__dict__.pop("_pending_raw_preset_write_operations", None)
            start_scheduled = bool(self.__dict__.pop("_raw_preset_write_operation_start_scheduled", False))
            state = QueuedWorkerState[dict[str, object]](object())
            state.pending = list(pending or [])
            state.start_scheduled = start_scheduled
            self.__dict__["_raw_preset_write_state"] = state
        return state

    @property
    def _pending_raw_preset_write_operations(self):
        return self._raw_preset_write_state_obj().pending

    @_pending_raw_preset_write_operations.setter
    def _pending_raw_preset_write_operations(self, value) -> None:
        self._raw_preset_write_state_obj().pending = list(value or [])

    @property
    def _raw_preset_write_operation_start_scheduled(self) -> bool:
        return bool(self._raw_preset_write_state_obj().start_scheduled)

    @_raw_preset_write_operation_start_scheduled.setter
    def _raw_preset_write_operation_start_scheduled(self, value: bool) -> None:
        self._raw_preset_write_state_obj().start_scheduled = bool(value)

    def _default_title(self) -> str:
        return self._title

    def on_page_activated(self) -> None:
        self._install_app_event_filter()
        if self._raw_preset_content_loaded_once:
            self._schedule_raw_editor_show_after_page_switch()

    def on_page_hidden(self) -> None:
        self._commit_pending_content_change()
        self._remove_app_event_filter()
        self._hide_raw_editor_for_next_switch()

    def _install_app_event_filter(self) -> None:
        if bool(self.__dict__.get("_app_event_filter_installed", False)):
            return
        app = QApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._app_event_filter_installed = True

    def _remove_app_event_filter(self) -> None:
        if not bool(self.__dict__.get("_app_event_filter_installed", False)):
            return
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        self._app_event_filter_installed = False

    def _hide_raw_editor_for_next_switch(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.hide_for_next_switch()
            return
        editor = self.__dict__.get("editor")
        if editor is None:
            return
        try:
            editor.setVisible(False)
        except Exception:
            pass
        self._raw_editor_show_scheduled = False

    def _schedule_raw_editor_show_after_page_switch(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.schedule_show_after_page_switch()
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("editor") is None:
            return
        if self._raw_editor_show_scheduled:
            return
        self._raw_editor_show_scheduled = True
        try:
            QTimer.singleShot(0, self._show_raw_editor_after_page_switch)
        except Exception:
            self._show_raw_editor_after_page_switch()

    def _show_raw_editor_after_page_switch(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.show_after_page_switch()
            return
        self._raw_editor_show_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        editor = self.__dict__.get("editor")
        if editor is None:
            return
        try:
            editor.setVisible(True)
        except Exception:
            pass

    def _preset_launch_method(self) -> str | None:
        return self._launch_method


    def _preset_folder_scope_key(self) -> str | None:
        from settings.mode import (
            PRESETS_SCOPE_WINWS1,
            PRESETS_SCOPE_WINWS2,
            is_zapret1_launch_method,
            is_zapret2_launch_method,
        )

        method = self._preset_launch_method()
        if is_zapret2_launch_method(method):
            return PRESETS_SCOPE_WINWS2
        if is_zapret1_launch_method(method):
            return PRESETS_SCOPE_WINWS1
        return None

    def _breadcrumb_root_text(self) -> str:
        return "Управление"

    def _breadcrumb_parent_text(self) -> str:
        return "Мои пресеты"

    def _breadcrumb_current_text(self) -> str:
        return self._preset_name or self._default_title()

    def _rebuild_breadcrumb(self) -> None:
        breadcrumb = getattr(self, "_breadcrumb", None)
        if breadcrumb is None:
            return
        breadcrumb_key = (
            self._breadcrumb_root_text(),
            self._breadcrumb_parent_text(),
            self._breadcrumb_current_text(),
        )
        # Совпадения ключа недостаточно: клик по крошке заставляет BreadcrumbBar
        # физически удалить элементы правее выбранного, а ключ при этом не
        # меняется — без проверки count() крошки пропадали бы навсегда.
        try:
            breadcrumb_count = int(breadcrumb.count())
        except Exception:
            breadcrumb_count = 0
        if (
            self.__dict__.get("_last_breadcrumb_key") == breadcrumb_key
            and breadcrumb_count == len(breadcrumb_key)
        ):
            return
        try:
            breadcrumb.blockSignals(True)
            breadcrumb.clear()
            breadcrumb.addItem("root", breadcrumb_key[0])
            breadcrumb.addItem("list", breadcrumb_key[1])
            breadcrumb.addItem("raw_preset", breadcrumb_key[2])
            set_breadcrumb_accessibility(breadcrumb, breadcrumb_key)
            self.__dict__["_last_breadcrumb_key"] = breadcrumb_key
        finally:
            try:
                breadcrumb.blockSignals(False)
            except Exception:
                pass

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "root":
            self._open_root_callback()
        elif key == "list":
            self._open_back_callback()

    def _show_success(self, text: str) -> None:
        if InfoBar is not None:
            try:
                InfoBar.success(title="Успех", content=text, parent=self.window())
                return
            except Exception:
                pass

    def _show_error(self, text: str) -> None:
        if InfoBar is not None:
            try:
                InfoBar.error(title="Ошибка", content=text, parent=self.window())
                return
            except Exception:
                pass

    def _is_current_builtin(self) -> bool:
        try:
            return str(self._preset_origin or "").strip().lower() == "builtin"
        except Exception:
            return False

    def _can_reset_current_to_builtin(self) -> bool:
        return bool(
            not self._is_current_builtin()
            and self.__dict__.get("_preset_can_reset_to_builtin", False)
        )

    def _build_ui(self) -> None:
        try:
            self.title_label.hide()
        except Exception:
            pass
        try:
            if self.subtitle_label is not None:
                self.subtitle_label.hide()
        except Exception:
            pass

        self._breadcrumb = None
        top_row = QWidget(self)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        self._breadcrumb = BreadcrumbBar(self)
        self._rebuild_breadcrumb()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        top_layout.addWidget(self._breadcrumb, 1)
        top_layout.addStretch(1)

        self.menuButton = TransparentToolButton(_fluent_icon("MENU"), self)
        menu_button_name = "Открыть меню действий пресета"
        set_control_accessibility(
            self.menuButton,
            name=menu_button_name,
            description="Открывает действия для пресета: переименовать, дублировать, экспортировать или удалить.",
        )
        set_state_text(self.menuButton, menu_button_name)
        self.menuButton.clicked.connect(self._open_menu)
        top_layout.addWidget(self.menuButton, 0)
        self.add_widget(top_row)

        self.summaryCard = SimpleCardWidget(self)
        summary_layout = QVBoxLayout(self.summaryCard)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(8)

        self.statusLabel = StrongBodyLabel("Пресет", self.summaryCard)
        self.metaLabel = CaptionLabel("", self.summaryCard)
        self.metaLabel.setWordWrap(True)
        self.pathLabel = CaptionLabel("", self.summaryCard)
        self.pathLabel.setWordWrap(True)

        summary_layout.addWidget(self.statusLabel)
        summary_layout.addWidget(self.metaLabel)
        summary_layout.addWidget(self.pathLabel)
        self.add_widget(self.summaryCard)

        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.activateButton = PushButton("Сделать активным", self)
        self.activateButton.setIcon(_fluent_icon("ACCEPT"))
        activate_button_name = "Сделать пресет активным"
        set_control_accessibility(
            self.activateButton,
            name=activate_button_name,
            description="Делает этот пресет выбранным для запуска.",
        )
        set_state_text(self.activateButton, activate_button_name)
        self.activateButton.clicked.connect(self._activate_preset)
        actions_layout.addWidget(self.activateButton)

        self.openExternalButton = PushButton("Открыть в редакторе", self)
        self.openExternalButton.setIcon(_fluent_icon("FOLDER"))
        open_external_button_name = "Открыть пресет в редакторе"
        set_control_accessibility(
            self.openExternalButton,
            name=open_external_button_name,
            description="Открывает файл пресета во внешнем текстовом редакторе.",
        )
        set_state_text(self.openExternalButton, open_external_button_name)
        self.openExternalButton.clicked.connect(self._open_external)
        actions_layout.addWidget(self.openExternalButton)

        self.runtimeToggleButton = PushButton("Запустить", self)
        self.runtimeToggleButton.setIcon(_fluent_icon("PLAY"))
        _set_runtime_toggle_accessibility(
            self.runtimeToggleButton,
            RuntimeToggleButtonPlan(
                text="Запустить",
                icon_name="PLAY",
                should_stop=False,
                enabled=True,
            ),
            runtime_available=self._runtime_actions is not None,
        )
        self.runtimeToggleButton.clicked.connect(self._toggle_runtime)
        actions_layout.addWidget(self.runtimeToggleButton)

        actions_layout.addStretch(1)
        actions_layout.addWidget(self.searchInput, 1)
        self.add_widget(actions)

        self.add_widget(self.editor, 1)

        self.footerStatusBar = PresetStatusBar(self)
        self.footerLabel = self.footerStatusBar.text_label
        self.add_widget(self.footerStatusBar)

    def set_preset_file_name(self, file_name: str) -> None:
        if not self._run_after_raw_preset_save(lambda: self.set_preset_file_name(file_name)):
            return
        next_file_name = str(file_name or "").strip()
        if self._can_reuse_loaded_raw_preset(next_file_name):
            self._refresh_header()
            return
        self._preset_file_name = next_file_name
        self._preset_name = Path(self._preset_file_name).stem if self._preset_file_name else ""
        self._preset_path = None
        self._preset_origin = "user"
        self._raw_editor_text_snapshot = None
        self._raw_preset_content_dirty = True
        self._load_file()
        self._refresh_header()

    def _can_reuse_loaded_raw_preset(self, file_name: str) -> bool:
        current = str(self.__dict__.get("_preset_file_name", "") or "").strip().lower()
        requested = str(file_name or "").strip().lower()
        if not current or not requested or current != requested:
            return False
        if not self._raw_preset_content_loaded_once:
            return False
        return not self._raw_preset_content_dirty

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "open_raw_preset":
            self.set_preset_file_name(str((payload or {}).get("preset_name") or ""))
            return True
        return False

    def _flush_pending_save(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._save_timer.isActive():
            self._save_timer.stop()
        if self._content_publish_pending:
            self._save_file()

    def _run_after_raw_preset_save(self, callback) -> bool:
        if self._cleanup_in_progress:
            return False
        if self._raw_worker_runtime_is_running("_raw_save_runtime"):
            self._after_raw_preset_save = callback
            return False
        if self._pending_raw_preset_save is not None:
            self._after_raw_preset_save = callback
            return False
        if self._save_timer.isActive() or self._content_publish_pending:
            self._after_raw_preset_save = callback
            self._save_timer.stop()
            self._save_file()
            return False
        return True

    def _refresh_header(self) -> None:
        self._rebuild_breadcrumb()
        active_name = self._current_selected_name()
        active_file_name = self._current_selected_file_name()
        is_active = False
        if self._preset_file_name:
            is_active = active_file_name.lower() == self._preset_file_name.lower()
        elif self._preset_name:
            is_active = active_name.lower() == self._preset_name.lower()
        origin = str(self._preset_origin or "user").strip().lower() or "user"

        if is_active and origin == "builtin":
            status = "Активный встроенный пресет"
        elif is_active and origin == "imported":
            status = "Активный импортированный пресет"
        elif is_active:
            status = "Активный пресет"
        elif origin == "builtin":
            status = "Встроенный пресет"
        elif origin == "imported":
            status = "Импортированный пресет"
        else:
            status = "Пользовательский пресет"
        set_text_if_changed(self.statusLabel, status)
        set_visible_if_changed(self.activateButton, not is_active)
        set_text_if_changed(self.metaLabel, f"Имя: {self._preset_name}")
        set_text_if_changed(self.pathLabel, str(self._preset_path or ""))

    def _load_file(self) -> None:
        self._request_raw_preset_text()

    def create_raw_preset_load_worker(self, request_id: int, file_name: str, parent=None):
        return self._create_raw_preset_load_worker_fn(
            request_id,
            launch_method=self._launch_method,
            file_name=file_name,
            parent=parent,
        )

    def create_raw_preset_save_worker(
        self,
        request_id: int,
        *,
        file_name: str,
        source_text: str,
        publish_content_changed: bool,
        parent=None,
    ):
        return self._create_raw_preset_save_worker_fn(
            request_id,
            launch_method=self._launch_method,
            file_name=file_name,
            source_text=source_text,
            publish_content_changed=publish_content_changed,
            parent=parent,
        )

    def create_raw_preset_activate_worker(self, request_id: int, file_name: str, parent=None):
        return self._create_raw_preset_activate_worker_fn(
            request_id,
            launch_method=self._launch_method,
            file_name=file_name,
            parent=parent,
        )

    def create_raw_preset_action_worker(self, request_id: int, *, action: str, payload: dict | None = None, parent=None):
        return self._create_raw_preset_action_worker_fn(
            request_id,
            launch_method=self._launch_method,
            action=action,
            payload=payload,
            parent=parent,
        )

    def _request_raw_preset_text(self, *, reason: str = "normal") -> None:
        runtime = self._raw_worker_runtime("_raw_load_runtime")
        state = self._raw_load_state_obj()
        self.__dict__["_raw_load_request_reason"] = str(reason or "normal").strip() or "normal"
        if state.is_busy():
            self._raw_load_request_id += 1
            state.pending = True
            self._is_loading = True
            self._set_footer("Загрузка...")
            return
        self._raw_load_request_id += 1
        request_id = self._raw_load_request_id
        self._is_loading = True
        self._set_footer("Загрузка...")
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_raw_preset_load_worker(
                request_id,
                self._preset_file_name,
                self,
            ),
            on_loaded=self._on_raw_preset_text_loaded,
            on_failed=self._on_raw_preset_text_failed,
            on_finished=self._on_raw_preset_worker_finished,
        )
        self._raw_load_runtime_request_id = request_id

    def _on_raw_preset_text_loaded(self, request_id: int, result) -> None:
        if request_id != self._raw_load_request_id:
            return
        self.__dict__["_pending_raw_text_apply_reason"] = self.__dict__.get(
            "_raw_load_request_reason",
            "normal",
        )
        self._schedule_raw_preset_text_apply(result)

    def _schedule_raw_preset_text_apply(self, result) -> None:
        self._pending_raw_text_apply = result
        if self.__dict__.get("_raw_text_apply_scheduled", False):
            return
        self._raw_text_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_raw_preset_text_apply)
        except Exception:
            self._run_scheduled_raw_preset_text_apply()

    def _run_scheduled_raw_preset_text_apply(self) -> None:
        result = self.__dict__.get("_pending_raw_text_apply")
        self._pending_raw_text_apply = None
        self._raw_text_apply_scheduled = False
        if result is None or self.__dict__.get("_cleanup_in_progress", False):
            return
        load_state = self._raw_load_state_obj()
        if load_state.has_pending() or load_state.start_scheduled:
            return
        if getattr(result, "file_name", ""):
            self._preset_file_name = str(result.file_name or "").strip()
        if getattr(result, "display_name", ""):
            self._preset_name = str(result.display_name or "").strip()
        self._preset_path = getattr(result, "path", None)
        self._preset_origin = str(getattr(result, "origin", "") or "user").strip().lower() or "user"
        self._preset_can_reset_to_builtin = bool(getattr(result, "can_reset_to_builtin", False))
        self._apply_raw_preset_active_state(
            getattr(result, "active_file_name", ""),
            getattr(result, "active_name", ""),
        )
        load_reason = str(self.__dict__.pop("_pending_raw_text_apply_reason", "") or "").strip()
        if (
            load_reason == "external"
            and self.__dict__.get("_raw_text_editor") is not None
            and self._raw_text_editor.has_local_unpublished_changes()
        ):
            self._raw_text_editor.report_external_update_skipped()
            self._is_loading = False
            self._refresh_header()
            return
        self._apply_raw_editor_text(result.text)
        self._raw_preset_content_loaded_once = True
        self._raw_preset_content_dirty = False
        self._set_footer(result.footer_text)
        self._is_loading = False
        self._refresh_header()
        self._schedule_raw_editor_show_after_page_switch()

    def _apply_raw_editor_text(self, text: str) -> bool:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            return bool(text_editor.apply_loaded_text(text))
        value = str(text or "")
        if self._current_raw_editor_text() == value:
            return False
        editor = self.__dict__.get("editor")
        if editor is not None and callable(getattr(editor, "setPlainText", None)):
            try:
                editor.setPlainText(value)
            except Exception:
                pass
        self._raw_editor_text_snapshot = value
        return True

    def _apply_raw_preset_active_state(self, file_name: str, name: str = "") -> None:
        active_file_name = str(file_name or "").strip()
        self._active_preset_file_name = active_file_name
        self._active_preset_name = str(name or "").strip() or (Path(active_file_name).stem if active_file_name else "")

    def _on_raw_preset_text_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_load_request_id:
            return
        load_state = self._raw_load_state_obj()
        if load_state.has_pending() or load_state.start_scheduled:
            return
        self._raw_preset_content_dirty = True
        self._set_footer(f"Ошибка загрузки: {error}")
        self._is_loading = False

    def _on_raw_preset_worker_finished(self, _worker) -> None:
        state = self._raw_load_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=lambda _runtime, worker: self._accept_current_raw_preset_load_finished(worker),
            single_shot=_single_shot,
            run_scheduled=self._run_scheduled_raw_preset_load_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _accept_current_raw_preset_load_finished(self, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            current_request_id = int(self.__dict__.get("_raw_load_runtime_request_id", 0) or 0)
            if int(request_id) != current_request_id:
                return False
        except (TypeError, ValueError):
            return False
        self._raw_load_runtime_request_id = 0
        return True

    def _schedule_pending_raw_preset_load_start(self) -> None:
        state = self._raw_load_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            self._run_scheduled_raw_preset_load_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_raw_preset_load_start(self) -> None:
        pending = self._raw_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        if not pending:
            return
        self._request_raw_preset_text()

    def _raw_load_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_raw_load_state")
        runtime = self.__dict__.get("_raw_load_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_raw_load_pending", False))
            start_scheduled = bool(self.__dict__.pop("_raw_load_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_raw_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _raw_load_pending(self) -> bool:
        return bool(self._raw_load_state_obj().pending)

    @_raw_load_pending.setter
    def _raw_load_pending(self, value: bool) -> None:
        self._raw_load_state_obj().pending = bool(value)

    @property
    def _raw_load_start_scheduled(self) -> bool:
        return bool(self._raw_load_state_obj().start_scheduled)

    @_raw_load_start_scheduled.setter
    def _raw_load_start_scheduled(self, value: bool) -> None:
        self._raw_load_state_obj().start_scheduled = bool(value)

    def _search_preset_text(self, text: str) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.search_text(text)

    def _on_text_changed(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.on_text_changed()
            return
        # Правка инвалидирует мемо: текст перечитывается из документа целиком
        # при следующем обращении (_current_raw_editor_text).
        self._raw_editor_text_snapshot = None
        if self._cleanup_in_progress or self._is_loading:
            return
        self._raw_preset_content_dirty = True
        self._content_publish_pending = True
        self._save_timer.stop()
        self._commit_timer.stop()
        self._save_timer.start(900)
        self._set_footer("Изменения...")

    def _current_raw_editor_text(self) -> str:
        """Текущий текст raw-редактора пресета.

        Документ QPlainTextEdit — единственный источник правды; снапшот — только
        мемоизация с инвалидацией по textChanged. Инкрементального патчинга по
        contentsChange здесь быть не должно: Qt учитывает финальный разделитель
        блока в charsAdded/charsRemoved, и позиционная математика молча теряла
        вставленный из буфера текст."""
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            return text_editor.current_text()
        snapshot = self._raw_editor_text_snapshot
        if snapshot is not None:
            return str(snapshot or "")
        editor = self.__dict__.get("editor")
        if editor is None:
            return ""
        try:
            text = str(editor.toPlainText() or "")
        except Exception:
            return ""
        self._raw_editor_text_snapshot = text
        return text

    def _save_file(self, *, publish_content_changed: bool = False) -> bool:
        if self._cleanup_in_progress:
            return False
        if self._preset_path is None:
            return False
        return self._request_raw_preset_save(
            file_name=self._preset_file_name,
            source_text=None,
            publish_content_changed=publish_content_changed,
        )

    def _request_raw_preset_save(
        self,
        *,
        file_name: str,
        source_text: str | None,
        publish_content_changed: bool = False,
    ) -> bool:
        runtime = self._raw_worker_runtime("_raw_save_runtime")
        state = self._raw_preset_save_state_obj()
        if state.is_busy():
            pending = state.pending if state.has_pending() else None
            state.pending = (
                str(file_name or "").strip(),
                None if source_text is None else str(source_text or ""),
                bool(publish_content_changed or (pending[2] if pending else False)),
            )
            return True
        if self._raw_preset_write_is_running():
            self._queue_raw_preset_write_operation(
                {
                    "kind": "save",
                    "file_name": str(file_name or "").strip(),
                    "source_text": None if source_text is None else str(source_text or ""),
                    "publish_content_changed": bool(publish_content_changed),
                }
            )
            return True
        self._start_raw_preset_save_worker(
            file_name=file_name,
            source_text=source_text,
            publish_content_changed=publish_content_changed,
        )
        return True

    def _start_raw_preset_save_worker(
        self,
        *,
        file_name: str,
        source_text: str | None,
        publish_content_changed: bool,
    ) -> None:
        runtime = self._raw_worker_runtime("_raw_save_runtime")
        self._raw_save_request_id += 1
        request_id = self._raw_save_request_id
        source_text = self._resolve_raw_preset_save_text(source_text)
        self._raw_save_succeeded = False
        self._set_footer("Сохранение...")
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_raw_preset_save_worker(
                request_id,
                file_name=str(file_name or "").strip(),
                source_text=str(source_text or ""),
                publish_content_changed=bool(publish_content_changed),
                parent=self,
            ),
            on_loaded=self._on_raw_preset_save_finished,
            on_failed=self._on_raw_preset_save_failed,
            on_finished=self._on_raw_preset_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _resolve_raw_preset_save_text(self, source_text) -> str:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            return text_editor.resolve_save_text(source_text)
        if source_text is not None:
            return str(source_text or "")
        return self._current_raw_editor_text()

    def _on_raw_preset_save_finished(
        self,
        request_id: int,
        requested_file_name: str,
        result,
        publish_content_changed: bool,
    ) -> None:
        if request_id != self._raw_save_request_id:
            return
        if self._raw_preset_save_state_obj().has_pending():
            return
        current_file_name = str(self._preset_file_name or "").strip().lower()
        saved_file_name = str(requested_file_name or "").strip().lower()
        if current_file_name and saved_file_name and current_file_name != saved_file_name:
            return
        updated = result.updated
        self._raw_save_succeeded = True
        self._preset_name = updated.name
        self._preset_file_name = updated.file_name
        self._preset_path = result.path
        self._preset_origin = str(getattr(updated, "kind", "") or self._preset_origin or "user").strip().lower() or "user"
        self._preset_can_reset_to_builtin = bool(getattr(result, "can_reset_to_builtin", False))
        self._raw_preset_content_loaded_once = True
        self._raw_preset_content_dirty = False
        if publish_content_changed:
            self._ignore_next_raw_preset_content_revision = True
        if publish_content_changed:
            self._content_publish_pending = False
        self._set_footer(result.footer_text)

    def _on_raw_preset_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_save_request_id:
            return
        if self._raw_preset_save_state_obj().has_pending():
            return
        self._raw_save_succeeded = False
        self._set_footer(f"Ошибка сохранения: {error}")
        self._show_error(str(error))

    def _on_raw_preset_save_worker_finished(self, worker) -> None:
        if not self._accept_current_raw_write_worker_finished("_raw_save_request_id", worker):
            return
        save_state = self._raw_preset_save_state_obj()
        pending = save_state.pending
        save_state.pending = None
        if pending and not self._cleanup_in_progress:
            self._schedule_raw_preset_save_worker_start(
                str(pending[0] or ""),
                None if pending[1] is None else str(pending[1] or ""),
                bool(pending[2]),
            )
            return
        callback = self._after_raw_preset_save
        self._after_raw_preset_save = None
        if callback is not None and self._raw_save_succeeded and not self._cleanup_in_progress:
            callback()
            if self._raw_preset_write_is_running():
                return
        self._schedule_next_raw_preset_write_operation_after_finish("_raw_save_request_id", worker)

    def _schedule_raw_preset_save_worker_start(
        self,
        file_name: str,
        source_text: str | None,
        publish_content_changed: bool,
    ) -> None:
        state = self._raw_preset_save_state_obj()
        pending = state.pending if state.has_pending() else None
        state.pending = (
            str(file_name or "").strip(),
            None if source_text is None else str(source_text or ""),
            bool(publish_content_changed or (pending[2] if pending else False)),
        )

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            self._run_scheduled_raw_preset_save_worker_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_raw_preset_save_worker_start(self) -> None:
        pending = self._raw_preset_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        if pending is None:
            return
        file_name, source_text, publish_content_changed = pending
        self._start_raw_preset_save_worker(
            file_name=str(file_name or ""),
            source_text=None if source_text is None else str(source_text or ""),
            publish_content_changed=bool(publish_content_changed),
        )

    def _raw_preset_save_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_raw_preset_save_state")
        runtime = self.__dict__.get("_raw_save_runtime")
        if state is None:
            pending = self.__dict__.pop("_pending_raw_preset_save", None)
            start_scheduled = bool(self.__dict__.pop("_raw_preset_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_raw_preset_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_raw_preset_save(self):
        return self._raw_preset_save_state_obj().pending

    @_pending_raw_preset_save.setter
    def _pending_raw_preset_save(self, value) -> None:
        self._raw_preset_save_state_obj().pending = value

    @property
    def _raw_preset_save_start_scheduled(self) -> bool:
        return bool(self._raw_preset_save_state_obj().start_scheduled)

    @_raw_preset_save_start_scheduled.setter
    def _raw_preset_save_start_scheduled(self, value: bool) -> None:
        self._raw_preset_save_state_obj().start_scheduled = bool(value)

    def _commit_pending_content_change(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.commit_pending_content_change()
            return
        if self._cleanup_in_progress or not self._content_publish_pending:
            return
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._save_file(publish_content_changed=True)

    def _schedule_pending_content_commit(self) -> None:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            text_editor.schedule_pending_content_commit()
            return
        if self._cleanup_in_progress or not self._content_publish_pending:
            return
        self._commit_timer.start(0)

    def _is_editor_object(self, obj) -> bool:
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None:
            return bool(text_editor.is_editor_object(obj))
        return False

    def eventFilter(self, obj, event):
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None and text_editor.handle_event(obj, event):
            return True
        return super().eventFilter(obj, event)

    def bind_ui_state_store(self, store) -> None:
        if self._ui_state_store is store:
            return
        unsubscribe = self._ui_state_unsubscribe
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_store = store
        self._ui_state_unsubscribe = None
        try:
            self._ui_state_unsubscribe = store.subscribe(
                self._on_ui_state_changed,
                fields={
                    "launch_method",
                    "launch_phase",
                    "launch_running",
                    "launch_busy",
                    "launch_busy_text",
                    "last_status_message",
                    "active_preset_revision",
                    "preset_content_revision",
                    "preset_structure_revision",
                },
                emit_initial=True,
            )
        except Exception:
            self._render_footer_status(None)

    def _set_footer(self, text: str) -> None:
        self._footer_status, self._footer_text = self._footer_status_from_text(text)
        self._render_footer_status()

    def _footer_status_from_text(self, text: str) -> tuple[str, str]:
        value = str(text or "").strip()
        if value.startswith("Загрузка"):
            return "loading", ""
        if value == "Загружено":
            return "loaded", ""
        if value.startswith("Применяем"):
            return "applying", ""
        if value.startswith("Пресет примен"):
            return "applied", ""
        if value.startswith("Пресет выбран"):
            return "selected_stopped", ""
        if value.startswith("Изменения"):
            return "dirty", ""
        if value.startswith("Сохранено"):
            return "saved", "Изменения сохранены"
        if value.startswith("Ошибка"):
            return "error", value
        return "neutral", value

    def _on_ui_state_changed(self, state, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        runtime_toggle_changed = (
            not changed
            or bool(changed & {"launch_phase", "launch_running", "launch_busy"})
        )
        footer_status_changed = (
            not changed
            or bool(changed & {
                "launch_method",
                "launch_busy",
                "launch_busy_text",
                "last_status_message",
                "active_preset_revision",
            })
        )
        if runtime_toggle_changed:
            self._render_runtime_toggle(state)
        if footer_status_changed:
            self._render_footer_status(state)
        content_revision_changed = bool(changed & {"preset_content_revision"})
        if content_revision_changed and bool(self.__dict__.get("_ignore_next_raw_preset_content_revision", False)):
            self._ignore_next_raw_preset_content_revision = False
            content_revision_changed = False
        if content_revision_changed or bool(changed & {"preset_structure_revision"}):
            self._raw_preset_content_dirty = True
        if content_revision_changed:
            self._handle_external_raw_preset_content_changed()

    def _handle_external_raw_preset_content_changed(self) -> None:
        # Коалесинг: серия внешних bump-ов в пределах окна даёт одну перезагрузку.
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_external_raw_reload_scheduled", False):
            return
        self._external_raw_reload_scheduled = True
        try:
            QTimer.singleShot(
                EXTERNAL_RAW_PRESET_RELOAD_COALESCE_MS,
                self._run_scheduled_external_raw_preset_reload,
            )
        except Exception:
            self._external_raw_reload_scheduled = False
            self._run_external_raw_preset_reload_now()

    def _run_scheduled_external_raw_preset_reload(self) -> None:
        self._external_raw_reload_scheduled = False
        self._run_external_raw_preset_reload_now()

    def _run_external_raw_preset_reload_now(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not str(self.__dict__.get("_preset_file_name", "") or "").strip():
            return
        if not self._raw_preset_content_loaded_once:
            return
        text_editor = self.__dict__.get("_raw_text_editor")
        if text_editor is not None and text_editor.has_local_unpublished_changes():
            text_editor.report_external_update_skipped()
            return
        self._request_raw_preset_text(reason="external")

    def _render_runtime_toggle(self, state=None) -> None:
        button = getattr(self, "runtimeToggleButton", None)
        if button is None:
            return
        store = self._ui_state_store
        if state is None and store is not None:
            try:
                state = store.snapshot()
            except Exception:
                state = None
        launch_phase = str(getattr(state, "launch_phase", "") or "") if state is not None else ""
        launch_running = bool(getattr(state, "launch_running", False)) if state is not None else False
        launch_busy = bool(getattr(state, "launch_busy", False)) if state is not None else False
        plan = build_runtime_toggle_button_plan(
            launch_phase=launch_phase,
            launch_running=launch_running,
            launch_busy=launch_busy,
        )
        self._runtime_toggle_should_stop = apply_runtime_toggle_button_plan(
            button,
            plan,
            runtime_available=self._runtime_actions is not None,
        )

    def _toggle_runtime(self) -> None:
        runtime = self._runtime_actions
        if runtime is None:
            self._show_error("Управление Zapret сейчас недоступно.")
            return
        self._commit_pending_content_change()
        try:
            if bool(getattr(self, "_runtime_toggle_should_stop", False)):
                runtime.stop()
            else:
                if not runtime.is_available():
                    self._show_error("Запуск ещё готовится. Попробуйте ещё раз через пару секунд.")
                    return
                runtime.start(launch_method=self._launch_method)
        except Exception as e:
            self._show_error(str(e))

    def _render_footer_status(self, state=None) -> None:
        store = self._ui_state_store
        if state is None and store is not None:
            try:
                state = store.snapshot()
            except Exception:
                state = None

        runtime_method = getattr(state, "launch_method", "") if state is not None else ""
        launch_busy = bool(getattr(state, "launch_busy", False)) if state is not None else False
        launch_busy_text = str(getattr(state, "launch_busy_text", "") or "") if state is not None else ""
        last_status_message = str(getattr(state, "last_status_message", "") or "") if state is not None else ""

        base_status = self._footer_status
        base_text = self._footer_text
        if self._is_current_selected_file() and state is not None:
            plan = build_runtime_preset_status_plan(
                base_status=base_status,
                launch_method=self._launch_method,
                runtime_launch_method=runtime_method,
                launch_busy=launch_busy,
                launch_busy_text=launch_busy_text,
                last_status_message=last_status_message,
                base_text=base_text,
            )
        else:
            from presets.ui.common.preset_status_bar import build_preset_status_plan

            plan = build_preset_status_plan(
                base_status,
                launch_method=self._launch_method,
                text=base_text,
            )
        self.footerStatusBar.set_plan(plan)

    def _is_current_selected_file(self) -> bool:
        try:
            current = self._current_selected_file_name().strip().lower()
            own = str(self._preset_file_name or "").strip().lower()
            return bool(current and own and current == own)
        except Exception:
            return False

    def _is_redundant_active_preset_activation(self) -> bool:
        if not self._is_current_selected_file():
            return False
        if self._content_publish_pending:
            return False
        if self._raw_preset_save_state_obj().has_pending():
            return False
        try:
            if self._save_timer.isActive():
                return False
        except Exception:
            pass
        return True

    def _activate_preset(self) -> None:
        if not self._run_after_raw_preset_save(self._activate_preset):
            return
        if not self._preset_file_name:
            self._show_error(f"Не удалось активировать пресет «{self._preset_name}»")
            return
        if self._is_redundant_active_preset_activation():
            return
        self._set_footer(self._activation_footer_text())
        self._request_preset_activation()

    def _request_preset_activation(self) -> None:
        file_name = str(self._preset_file_name or "").strip()
        if not file_name:
            return
        state = self._raw_preset_activation_state_obj()
        if state.start_scheduled:
            state.pending = file_name
            return
        if self._raw_preset_write_is_running():
            state.pending = file_name
            self._queue_raw_preset_write_operation({"kind": "activate", "file_name": file_name})
            return
        self._start_preset_activation_worker(file_name)

    def _start_preset_activation_worker(self, file_name: str) -> None:
        runtime = self._raw_worker_runtime("_raw_activate_runtime")
        self._raw_activate_request_id += 1
        request_id = self._raw_activate_request_id
        if self.activateButton is not None:
            set_enabled_if_changed(self.activateButton, False)
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_raw_preset_activate_worker(
                request_id,
                str(file_name or "").strip(),
                self,
            ),
            on_loaded=self._on_preset_activation_finished,
            on_failed=self._on_preset_activation_failed,
            on_finished=self._on_preset_activation_worker_finished,
            loaded_signal_name="activated",
        )

    def _on_preset_activation_finished(self, request_id: int, activated: bool) -> None:
        if request_id != self._raw_activate_request_id:
            return
        if self._raw_preset_activation_state_obj().has_pending():
            return
        if activated:
            self._apply_raw_preset_active_state(self._preset_file_name, self._preset_name)
            self._refresh_header()
            self._set_footer(self._activation_footer_text())
            self._show_success(f"Пресет «{self._preset_name}» активирован")
            return
        self._show_error(f"Не удалось активировать пресет «{self._preset_name}»")

    def _on_preset_activation_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_activate_request_id:
            return
        if self._raw_preset_activation_state_obj().has_pending():
            return
        self._show_error(str(error))

    def _on_preset_activation_worker_finished(self, worker) -> None:
        accepted, scheduled = self._schedule_next_raw_preset_write_operation_after_finish(
            "_raw_activate_request_id",
            worker,
        )
        if not accepted and getattr(worker, "_request_id", None) is not None:
            return
        if scheduled:
            return
        state = self._raw_preset_activation_state_obj()
        pending = str(state.pending or "").strip()
        state.pending = ""
        if pending and not bool(self.__dict__.get("_cleanup_in_progress", False)):
            self._schedule_preset_activation_worker_start(pending)
            return
        if self.activateButton is not None:
            set_enabled_if_changed(self.activateButton, True)

    def _schedule_preset_activation_worker_start(self, file_name: str) -> None:
        state = self._raw_preset_activation_state_obj()
        state.pending = str(file_name or "").strip()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            self._run_scheduled_preset_activation_worker_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_preset_activation_worker_start(self) -> None:
        pending = self._raw_preset_activation_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        pending = str(pending or "").strip()
        if not pending:
            return
        self._start_preset_activation_worker(pending)

    def _raw_preset_activation_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_raw_preset_activation_state")
        runtime = self.__dict__.get("_raw_activate_runtime")
        if state is None:
            pending = str(self.__dict__.pop("_pending_raw_preset_activation", "") or "").strip()
            start_scheduled = bool(self.__dict__.pop("_raw_preset_activation_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value="",
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_raw_preset_activation_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_raw_preset_activation(self) -> str:
        return str(self._raw_preset_activation_state_obj().pending or "")

    @_pending_raw_preset_activation.setter
    def _pending_raw_preset_activation(self, value: str) -> None:
        self._raw_preset_activation_state_obj().pending = str(value or "").strip()

    @property
    def _raw_preset_activation_start_scheduled(self) -> bool:
        return bool(self._raw_preset_activation_state_obj().start_scheduled)

    @_raw_preset_activation_start_scheduled.setter
    def _raw_preset_activation_start_scheduled(self, value: bool) -> None:
        self._raw_preset_activation_state_obj().start_scheduled = bool(value)

    def _request_raw_preset_action(self, action: str, **payload) -> None:
        if self._raw_preset_write_is_running():
            self._queue_raw_preset_write_operation(
                {
                    "kind": "action",
                    "action": str(action or ""),
                    "payload": dict(payload or {}),
                }
            )
            return
        self._start_raw_preset_action_worker(action, **payload)

    def _start_raw_preset_action_worker(self, action: str, **payload) -> None:
        runtime = self._raw_worker_runtime("_raw_action_runtime")
        self._raw_action_request_id += 1
        request_id = self._raw_action_request_id
        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_raw_preset_action_worker(
                request_id,
                action=action,
                payload=payload,
                parent=self,
            ),
            on_loaded=self._on_raw_preset_action_finished,
            on_failed=self._on_raw_preset_action_failed,
            on_finished=self._on_raw_preset_action_worker_finished,
            loaded_signal_name="completed",
        )

    def _on_raw_preset_action_finished(self, request_id: int, action: str, result, payload) -> None:
        if request_id != self._raw_action_request_id:
            return
        if self._raw_preset_write_state_obj().has_pending():
            return
        if action == "rename":
            updated, path, load_result = result
            self._notify_preset_structure_changed()
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(updated, "kind", "") or "user").strip().lower() or "user"
            self._preset_can_reset_to_builtin = False
            self._apply_raw_preset_action_result(load_result)
            self._refresh_header()
            self._show_success(f"Пресет переименован: {payload.get('new_name') or updated.name}")
        elif action == "duplicate":
            duplicated, path, load_result = result
            self._notify_preset_structure_changed()
            self._preset_name = duplicated.name
            self._preset_file_name = duplicated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(duplicated, "kind", "") or "user").strip().lower() or "user"
            self._preset_can_reset_to_builtin = False
            self._apply_raw_preset_action_result(load_result)
            self._refresh_header()
            self._show_success(f"Создан дубликат: {payload.get('new_name') or duplicated.name}")
        elif action == "export":
            self._show_success(f"Пресет экспортирован: {result}")
        elif action == "reset":
            updated, path, load_result = result
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(updated, "kind", "") or "builtin").strip().lower() or "builtin"
            self._preset_can_reset_to_builtin = False
            self._apply_raw_preset_action_result(load_result)
            self._refresh_header()
            self._show_success(f"Восстановлен встроенный пресет «{self._preset_name}»")
        elif action == "delete":
            name = str(payload.get("display_name") or self._preset_name or "").strip()
            self._notify_preset_structure_changed()
            self._open_back_callback()
            self._show_success(f"Пресет «{name}» удалён")

    def _apply_raw_preset_action_result(self, load_result) -> None:
        """Применяет содержимое, прочитанное action-worker-ом в его же потоке.

        Диск после действия не перечитывается отдельным load-worker-ом; полный
        перезапрос остаётся только страховкой на случай, если worker не смог
        прочитать итоговый файл.
        """
        if load_result is None:
            self._load_file()
            return
        self.__dict__["_pending_raw_text_apply_reason"] = "action"
        self._pending_raw_text_apply = load_result
        self._raw_text_apply_scheduled = False
        self._run_scheduled_raw_preset_text_apply()

    def _on_raw_preset_action_failed(self, request_id: int, _action: str, error: str, _payload) -> None:
        if request_id != self._raw_action_request_id:
            return
        if self._raw_preset_write_state_obj().has_pending():
            return
        self._show_error(str(error))

    def _on_raw_preset_action_worker_finished(self, worker) -> None:
        _accepted, scheduled = self._schedule_next_raw_preset_write_operation_after_finish(
            "_raw_action_request_id",
            worker,
        )
        if scheduled:
            return

    def _activation_footer_text(self) -> str:
        try:
            store = self._ui_state_store
            state = store.snapshot() if store is not None else None
            runtime_method = str(getattr(state, "launch_method", "") or "").strip().lower()
            if bool(getattr(state, "launch_running", False)) and runtime_method == self._launch_method:
                return "Применяем пресет..."
        except Exception:
            pass
        return "Пресет выбран"

    def _open_external(self) -> None:
        try:
            if not self._run_after_raw_preset_save(self._open_external):
                return
            if self._preset_path is None:
                return
            self._request_raw_preset_action("open", path=self._preset_path)
        except Exception as e:
            self._show_error(str(e))

    def _open_menu(self) -> None:
        if RoundMenu is not None and Action is not None:
            menu = RoundMenu(parent=self)
            action_map: dict[object, str] = {}
            duplicate_action = _make_menu_action("Дублировать", icon=_fluent_icon("COPY"), parent=menu)
            export_action = _make_menu_action("Экспорт", icon=_fluent_icon("SHARE"), parent=menu)
            action_map[duplicate_action] = "duplicate"
            action_map[export_action] = "export"
            reset_action = None
            rename_action = None
            delete_action = None
            if not self._is_current_builtin():
                rename_action = _make_menu_action("Переименовать", icon=_fluent_icon("RENAME"), parent=menu)
                delete_action = _make_menu_action("Удалить", icon=_fluent_icon("DELETE"), parent=menu)
                if self._can_reset_current_to_builtin():
                    reset_action = _make_menu_action("Вернуть встроенный", icon=_fluent_icon("SYNC"), parent=menu)
                if self._is_current_selected_file() and hasattr(delete_action, "setEnabled"):
                    delete_action.setEnabled(False)
                action_map[rename_action] = "rename"
                if reset_action is not None:
                    action_map[reset_action] = "reset"
                action_map[delete_action] = "delete"
            if rename_action is not None:
                menu.addAction(rename_action)
                _set_raw_preset_menu_item_accessibility(menu, text="Переименовать")
            menu.addAction(duplicate_action)
            _set_raw_preset_menu_item_accessibility(menu, text="Дублировать")
            menu.addAction(export_action)
            _set_raw_preset_menu_item_accessibility(menu, text="Экспорт")
            if reset_action is not None:
                menu.addAction(reset_action)
                _set_raw_preset_menu_item_accessibility(menu, text="Вернуть встроенный")
            if delete_action is not None:
                menu.addAction(delete_action)
                _set_raw_preset_menu_item_accessibility(
                    menu,
                    text="Удалить",
                    disabled=self._is_current_selected_file(),
                )
            chosen = exec_popup_menu(
                menu,
                self.menuButton.mapToGlobal(self.menuButton.rect().bottomLeft()),
                owner=self,
                capture_action=True,
            )
            command = action_map.get(chosen, "")
            if command == "rename":
                self._rename_preset()
            elif command == "delete":
                self._delete_preset()
            elif command == "duplicate":
                self._duplicate_preset()
            elif command == "export":
                self._export_preset()
            elif command == "reset":
                self._reset_preset()

    def _rename_preset(self) -> None:
        if self._is_current_builtin():
            self._show_error("Встроенный пресет нельзя переименовать. Создайте копию и работайте уже с ней.")
            return
        if not self._run_after_raw_preset_save(self._rename_preset):
            return
        dialog = _RenameDialog(self._preset_name, [], self.window())
        if not dialog.exec():
            return
        new_name = dialog.nameEdit.text().strip()
        if not new_name or new_name == self._preset_name:
            return
        self._request_raw_preset_action(
            "rename",
            file_name=self._preset_file_name,
            new_name=new_name,
        )

    def _duplicate_preset(self) -> None:
        if not self._run_after_raw_preset_save(self._duplicate_preset):
            return
        new_name = f"{self._preset_name} (копия)"
        self._request_raw_preset_action(
            "duplicate",
            file_name=self._preset_file_name,
            new_name=new_name,
        )

    def _export_preset(self) -> None:
        if not self._run_after_raw_preset_save(self._export_preset):
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать пресет",
            f"{self._preset_name}.txt",
            "Файлы пресетов (*.txt);;Все файлы (*.*)",
        )
        if not file_path:
            return
        self._request_raw_preset_action(
            "export",
            file_name=self._preset_file_name,
            target_path=file_path,
        )

    def _reset_preset(self) -> None:
        if not self._run_after_raw_preset_save(self._reset_preset):
            return
        if MessageBox is not None:
            body = (
                f"Будет удалён ваш изменённый файл пресета «{self._preset_name}».\n"
                "После этого снова появится встроенный пресет с тем же именем файла.\n"
                "Изменения в этом файле будут потеряны."
            )
            box = MessageBox(
                "Вернуть встроенный пресет?",
                body,
                self.window(),
            )
            box.yesButton.setText("Вернуть встроенный")
            box.cancelButton.setText("Отмена")
            set_message_box_button_accessibility(
                box,
                yes_name="Вернуть встроенный пресет",
                yes_description=body,
                cancel_name="Отменить возврат встроенного пресета",
                cancel_description="Закрывает диалог без возврата встроенного пресета.",
            )
            if not box.exec():
                return
        self._request_raw_preset_action(
            "reset",
            file_name=self._preset_file_name,
        )

    def _delete_preset(self) -> None:
        if self._is_current_builtin():
            self._show_error("Встроенный пресет нельзя удалить.")
            return
        if not self._run_after_raw_preset_save(self._delete_preset):
            return
        if MessageBox is not None:
            body = (
                f"Пользовательский пресет «{self._preset_name}» будет удалён.\n"
                "Изменения в нём будут потеряны."
            )
            box = MessageBox(
                "Удалить пресет?",
                body,
                self.window(),
            )
            box.yesButton.setText("Удалить")
            box.cancelButton.setText("Отмена")
            set_message_box_button_accessibility(
                box,
                yes_name="Удалить пользовательский пресет",
                yes_description=body,
                cancel_name="Отменить удаление пользовательского пресета",
                cancel_description="Закрывает диалог без удаления пользовательского пресета.",
            )
            if not box.exec():
                return
        self._request_raw_preset_action(
            "delete",
            file_name=self._preset_file_name,
            display_name=self._preset_name,
        )

    def _current_selected_name(self) -> str:
        return str(self.__dict__.get("_active_preset_name", "") or "").strip()

    def _current_selected_file_name(self) -> str:
        return str(self.__dict__.get("_active_preset_file_name", "") or "").strip()

    def _notify_preset_structure_changed(self) -> None:
        store = self._ui_state_store
        if store is None:
            return
        try:
            store.bump_preset_structure_revision()
        except Exception:
            pass

    def _stop_raw_worker_runtimes(self) -> None:
        for attr, warning_prefix, blocking in (
            ("_raw_load_runtime", "raw preset load worker", False),
            ("_raw_save_runtime", "raw preset save worker", False),
            ("_raw_activate_runtime", "raw preset activate worker", False),
            ("_raw_action_runtime", "raw preset action worker", False),
        ):
            runtime = self.__dict__.get(attr)
            if runtime is None:
                continue
            runtime.stop(blocking=blocking, warning_prefix=warning_prefix)
            runtime.cancel()

    def cleanup(self) -> None:
        try:
            self._commit_pending_content_change()
        except Exception:
            pass
        self._cleanup_in_progress = True
        self._raw_load_state_obj().reset()
        self._pending_raw_text_apply = None
        self._raw_text_apply_scheduled = False
        self._raw_editor_show_scheduled = False
        self._raw_preset_write_state_obj().reset()
        self._raw_preset_save_state_obj().reset()
        self._raw_preset_activation_state_obj().reset()
        self._raw_load_runtime_request_id = 0
        self._stop_raw_worker_runtimes()
        unsubscribe = self._ui_state_unsubscribe
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        try:
            self._save_timer.stop()
        except Exception:
            pass
        try:
            self._commit_timer.stop()
        except Exception:
            pass
        try:
            app = QApplication.instance()
            if app is not None and self._app_event_filter_installed:
                app.removeEventFilter(self)
        except Exception:
            pass
        try:
            text_editor = self.__dict__.get("_raw_text_editor")
            if text_editor is not None:
                text_editor.cleanup()
        except Exception:
            pass
        self._ui_state_store = None
