from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtGui import QTextCursor, QTextDocument
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog

from ui.pages.base_page import BasePage
from ui.fluent_widgets import set_tooltip, style_semantic_caption_label
from ui.accessibility import set_control_accessibility, set_state_text
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.queued_worker_state import QueuedWorkerState
from ui.popup_menu import exec_popup_menu
from ui.smooth_scroll import apply_editor_smooth_scroll_preference
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
    MessageBox,
    MessageBoxBase,
    PlainTextEdit,
    PushButton,
    RoundMenu,
    SearchLineEdit,
    SimpleCardWidget,
    StrongBodyLabel,
    TransparentToolButton,
)


def _fluent_icon(name: str):
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
            icon_name="CANCEL",
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
        name=f"{action} пресет",
        description=description,
    )


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
        self._active_preset_file_name = ""
        self._active_preset_name = ""
        self._raw_editor_text_snapshot: str | None = None
        self._raw_editor_text_cache_update_suspended = False
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
        self._raw_save_runtime_worker = None
        self._raw_preset_save_state = LatestValueWorkerState(
            self._raw_save_runtime,
            empty_value=None,
        )
        self._after_raw_preset_save = None
        self._raw_save_succeeded = True
        self._raw_activate_runtime = OneShotWorkerRuntime()
        self._raw_activate_request_id = 0
        self._raw_activate_runtime_worker = None
        self._raw_preset_activation_state = LatestValueWorkerState(
            self._raw_activate_runtime,
            empty_value="",
        )
        self._raw_action_runtime = OneShotWorkerRuntime()
        self._raw_action_request_id = 0
        self._raw_action_runtime_worker = None
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
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_file)
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.timeout.connect(self._commit_pending_content_change)

        self._build_ui()
        self.editor.installEventFilter(self)
        try:
            self.editor.viewport().installEventFilter(self)
        except Exception:
            pass
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_event_filter_installed = True
        self.bind_ui_state_store(ui_state_store)

    def _raw_worker_runtime(self, attr: str) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            setattr(self, attr, runtime)
        return runtime

    def _raw_worker_runtime_is_running(self, attr: str) -> bool:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            return False
        return bool(runtime.is_running())

    def _accept_current_raw_write_worker_finished(self, attr: str, worker) -> bool:
        missing = object()
        current_worker = self.__dict__.get(attr, missing)
        if current_worker is missing:
            setattr(self, attr, None)
            return True
        if worker is not current_worker:
            return False
        setattr(self, attr, None)
        return True

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

    def on_page_hidden(self) -> None:
        self._commit_pending_content_change()

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
        if self.__dict__.get("_last_breadcrumb_key") == breadcrumb_key:
            return
        try:
            breadcrumb.blockSignals(True)
            breadcrumb.clear()
            breadcrumb.addItem("root", breadcrumb_key[0])
            breadcrumb.addItem("list", breadcrumb_key[1])
            breadcrumb.addItem("raw_preset", breadcrumb_key[2])
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
        set_control_accessibility(
            self.menuButton,
            name="Открыть меню действий пресета",
            description="Открывает действия для пресета: переименовать, дублировать, экспортировать или удалить.",
        )
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
        set_control_accessibility(
            self.activateButton,
            name="Сделать пресет активным",
            description="Делает этот пресет выбранным для запуска.",
        )
        self.activateButton.clicked.connect(self._activate_preset)
        actions_layout.addWidget(self.activateButton)

        self.openExternalButton = PushButton("Открыть в редакторе", self)
        self.openExternalButton.setIcon(_fluent_icon("FOLDER"))
        set_control_accessibility(
            self.openExternalButton,
            name="Открыть пресет в редакторе",
            description="Открывает файл пресета во внешнем текстовом редакторе.",
        )
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
        self.searchInput = SearchLineEdit(self)
        self.searchInput.setPlaceholderText("Поиск по тексту пресета")
        set_tooltip(self.searchInput, "Найти строку в тексте открытого пресета.")
        set_control_accessibility(
            self.searchInput,
            name="Поиск по тексту пресета",
            description="Введите текст, чтобы найти строку внутри открытого пресета.",
        )
        self.searchInput.setClearButtonEnabled(True)
        self.searchInput.setFixedHeight(34)
        self.searchInput.setMinimumWidth(220)
        self.searchInput.setMaximumWidth(300)
        self.searchInput.setProperty("noDrag", True)
        self.searchInput.textChanged.connect(self._search_preset_text)
        actions_layout.addWidget(self.searchInput, 0)
        self.add_widget(actions)

        self.editor = PlainTextEdit(self)
        set_control_accessibility(
            self.editor,
            name="Текст открытого пресета",
            description="Здесь можно читать и редактировать содержимое открытого пресета.",
        )
        apply_editor_smooth_scroll_preference(self.editor)
        self.editor.document().contentsChange.connect(self._on_raw_editor_contents_changed)
        self.editor.textChanged.connect(self._on_text_changed)
        self.add_widget(self.editor, 1)

        self.footerStatusBar = PresetStatusBar(self)
        self.footerLabel = self.footerStatusBar.text_label
        self.add_widget(self.footerStatusBar)

    def set_preset_file_name(self, file_name: str) -> None:
        if not self._run_after_raw_preset_save(lambda: self.set_preset_file_name(file_name)):
            return
        self._preset_file_name = str(file_name or "").strip()
        self._preset_name = Path(self._preset_file_name).stem if self._preset_file_name else ""
        self._preset_path = None
        self._preset_origin = "user"
        self._raw_editor_text_snapshot = None
        self._load_file()
        self._refresh_header()

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

    def _request_raw_preset_text(self) -> None:
        runtime = self._raw_worker_runtime("_raw_load_runtime")
        state = self._raw_load_state_obj()
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
        self._apply_raw_preset_active_state(
            getattr(result, "active_file_name", ""),
            getattr(result, "active_name", ""),
        )
        self._apply_raw_editor_text(result.text)
        self._set_footer(result.footer_text)
        self._is_loading = False
        self._refresh_header()

    def _apply_raw_editor_text(self, text: str) -> None:
        value = str(text or "")
        if self.__dict__.get("_raw_editor_text_snapshot") == value:
            return
        self._raw_editor_text_cache_update_suspended = True
        try:
            self.editor.setPlainText(value)
        finally:
            self._raw_editor_text_cache_update_suspended = False
        self._raw_editor_text_snapshot = value

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
        editor = getattr(self, "editor", None)
        if editor is None:
            return
        query = str(text or "")
        cursor = editor.textCursor()
        if not query.strip():
            cursor.clearSelection()
            editor.setTextCursor(cursor)
            return

        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        editor.find(query, QTextDocument.FindFlag(0))

    def _on_text_changed(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._is_loading:
            return
        self._content_publish_pending = True
        self._save_timer.stop()
        self._commit_timer.stop()
        self._save_timer.start(900)
        self._set_footer("Изменения...")

    def _on_raw_editor_contents_changed(self, position: int, chars_removed: int, chars_added: int) -> None:
        if self._cleanup_in_progress or self._is_loading:
            return
        if bool(self.__dict__.get("_raw_editor_text_cache_update_suspended", False)):
            return
        current = str(self.__dict__.get("_raw_editor_text_snapshot") or "")
        start = max(0, min(int(position or 0), len(current)))
        removed = max(0, int(chars_removed or 0))
        inserted = self._raw_editor_inserted_text(start, max(0, int(chars_added or 0)))
        self._raw_editor_text_snapshot = f"{current[:start]}{inserted}{current[start + removed:]}"

    def _raw_editor_inserted_text(self, position: int, chars_added: int) -> str:
        if chars_added <= 0:
            return ""
        editor = self.__dict__.get("editor")
        if editor is None:
            return ""
        try:
            document = editor.document()
            cursor = QTextCursor(document)
            cursor.setPosition(max(0, int(position or 0)))
            cursor.setPosition(max(0, int(position or 0)) + int(chars_added or 0), QTextCursor.MoveMode.KeepAnchor)
            return str(cursor.selectedText() or "").replace("\u2029", "\n")
        except Exception:
            return ""

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
        _request_id, worker = runtime.start_qthread_worker(
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
        self._raw_save_runtime_worker = worker

    def _resolve_raw_preset_save_text(self, source_text) -> str:
        if source_text is not None:
            text = str(source_text or "")
        else:
            snapshot = self.__dict__.get("_raw_editor_text_snapshot")
            if snapshot is not None:
                return str(snapshot or "")
            text = ""
        self._raw_editor_text_snapshot = text
        return text

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
        if not self._accept_current_raw_write_worker_finished("_raw_save_runtime_worker", worker):
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
        self._schedule_next_raw_preset_write_operation_start()

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
        if self._cleanup_in_progress or not self._content_publish_pending:
            return
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._save_file(publish_content_changed=True)

    def _schedule_pending_content_commit(self) -> None:
        if self._cleanup_in_progress or not self._content_publish_pending:
            return
        self._commit_timer.start(0)

    def _is_editor_object(self, obj) -> bool:
        editor = getattr(self, "editor", None)
        if editor is None or obj is None:
            return False
        current = obj
        while current is not None:
            if current is editor:
                return True
            try:
                current = current.parent()
            except Exception:
                return False
        return False

    def eventFilter(self, obj, event):
        event_type = event.type()
        if event_type in {QEvent.Type.FocusOut, QEvent.Type.Leave} and self._is_editor_object(obj):
            self._schedule_pending_content_commit()
        elif event_type == QEvent.Type.MouseButtonPress and not self._is_editor_object(obj):
            self._schedule_pending_content_commit()
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
        if bool(self.__dict__.get("_content_publish_pending", False)):
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
        _request_id, worker = runtime.start_qthread_worker(
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
        self._raw_activate_runtime_worker = worker

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
        if not self._accept_current_raw_write_worker_finished("_raw_activate_runtime_worker", worker):
            return
        if self._schedule_next_raw_preset_write_operation_start():
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
        _request_id, worker = runtime.start_qthread_worker(
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
        self._raw_action_runtime_worker = worker

    def _on_raw_preset_action_finished(self, request_id: int, action: str, result, payload) -> None:
        if request_id != self._raw_action_request_id:
            return
        if self._raw_preset_write_state_obj().has_pending():
            return
        if action == "rename":
            updated, path = result
            self._notify_preset_structure_changed()
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(updated, "kind", "") or "user").strip().lower() or "user"
            self._load_file()
            self._refresh_header()
            self._show_success(f"Пресет переименован: {payload.get('new_name') or updated.name}")
        elif action == "duplicate":
            duplicated, path = result
            self._notify_preset_structure_changed()
            self._preset_name = duplicated.name
            self._preset_file_name = duplicated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(duplicated, "kind", "") or "user").strip().lower() or "user"
            self._load_file()
            self._refresh_header()
            self._show_success(f"Создан дубликат: {payload.get('new_name') or duplicated.name}")
        elif action == "export":
            self._show_success(f"Пресет экспортирован: {result}")
        elif action == "reset":
            updated, path = result
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = path
            self._preset_origin = str(getattr(updated, "kind", "") or "builtin").strip().lower() or "builtin"
            self._load_file()
            self._refresh_header()
            self._show_success(f"Восстановлен встроенный пресет «{self._preset_name}»")
        elif action == "delete":
            name = str(payload.get("display_name") or self._preset_name or "").strip()
            self._notify_preset_structure_changed()
            self._open_back_callback()
            self._show_success(f"Пресет «{name}» удалён")

    def _on_raw_preset_action_failed(self, request_id: int, _action: str, error: str, _payload) -> None:
        if request_id != self._raw_action_request_id:
            return
        if self._raw_preset_write_state_obj().has_pending():
            return
        self._show_error(str(error))

    def _on_raw_preset_action_worker_finished(self, worker) -> None:
        if not self._accept_current_raw_write_worker_finished("_raw_action_runtime_worker", worker):
            return
        if self._schedule_next_raw_preset_write_operation_start():
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
            duplicate_action = _make_menu_action("Дублировать", icon=_fluent_icon("COPY"), parent=menu)
            export_action = _make_menu_action("Экспорт", icon=_fluent_icon("SHARE"), parent=menu)
            reset_action = _make_menu_action("Вернуть встроенный", icon=_fluent_icon("SYNC"), parent=menu)
            rename_action = None
            delete_action = None
            if not self._is_current_builtin():
                rename_action = _make_menu_action("Переименовать", icon=_fluent_icon("RENAME"), parent=menu)
                delete_action = _make_menu_action("Удалить", icon=_fluent_icon("DELETE"), parent=menu)
                if self._is_current_selected_file() and hasattr(delete_action, "setEnabled"):
                    delete_action.setEnabled(False)
                rename_action.triggered.connect(self._rename_preset)
                delete_action.triggered.connect(self._delete_preset)
            duplicate_action.triggered.connect(self._duplicate_preset)
            export_action.triggered.connect(self._export_preset)
            reset_action.triggered.connect(self._reset_preset)
            if rename_action is not None:
                menu.addAction(rename_action)
            menu.addAction(duplicate_action)
            menu.addAction(export_action)
            menu.addAction(reset_action)
            if delete_action is not None:
                menu.addAction(delete_action)
            exec_popup_menu(
                menu,
                self.menuButton.mapToGlobal(self.menuButton.rect().bottomLeft()),
                owner=self,
            )

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
            box = MessageBox(
                "Вернуть встроенный пресет?",
                f"Будет удалён ваш изменённый файл пресета «{self._preset_name}».\n"
                "После этого снова появится встроенный пресет с тем же именем файла.\n"
                "Изменения в этом файле будут потеряны.",
                self.window(),
            )
            box.yesButton.setText("Вернуть встроенный")
            box.cancelButton.setText("Отмена")
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
            box = MessageBox(
                "Удалить пресет?",
                f"Пользовательский пресет «{self._preset_name}» будет удалён.\n"
                "Изменения в нём будут потеряны.",
                self.window(),
            )
            box.yesButton.setText("Удалить")
            box.cancelButton.setText("Отмена")
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
        self._raw_preset_write_state_obj().reset()
        self._raw_preset_save_state_obj().reset()
        self._raw_preset_activation_state_obj().reset()
        self._raw_load_runtime_request_id = 0
        self._raw_save_runtime_worker = None
        self._raw_activate_runtime_worker = None
        self._raw_action_runtime_worker = None
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
        self._ui_state_store = None
