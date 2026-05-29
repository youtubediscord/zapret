from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtGui import QTextCursor, QTextDocument
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog

from ui.pages.base_page import BasePage
from ui.fluent_widgets import set_tooltip, style_semantic_caption_label
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
from presets.raw_preset_editor_workflow import RawPresetEditorController


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
    plan_key = (plan.text, plan.icon_name, bool(plan.should_stop), enabled)
    if getattr(button, "_last_runtime_toggle_button_plan_key", None) == plan_key:
        return plan.should_stop
    setattr(button, "_last_runtime_toggle_button_plan_key", plan_key)
    button.setText(plan.text)
    button.setIcon(icon_factory(plan.icon_name))
    button.setEnabled(enabled)
    return plan.should_stop


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

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText("Введите название.")
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True


class PresetRawEditorPage(BasePage):
    def __init__(
        self,
        parent=None,
        *,
        presets_feature,
        launch_method: str,
        title: str,
        open_back,
        open_root,
        runtime_feature,
        ui_state_store,
    ):
        self._launch_method = str(launch_method or "").strip()
        self._title = str(title or "").strip() or "Пресет"
        super().__init__(self._title, "", parent)
        self._open_back_callback = open_back
        self._open_root_callback = open_root
        self._runtime_feature = runtime_feature
        self._preset_name = ""
        self._preset_file_name = ""
        self._preset_path: Path | None = None
        self._preset_origin = "user"
        self._is_loading = False
        self._raw_load_request_id = 0
        self._raw_load_worker = None
        self._raw_save_request_id = 0
        self._raw_save_worker = None
        self._pending_raw_preset_save: tuple[str, str, bool] | None = None
        self._after_raw_preset_save = None
        self._raw_save_succeeded = True
        self._raw_activate_request_id = 0
        self._raw_activate_worker = None
        self._raw_action_request_id = 0
        self._raw_action_worker = None
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._footer_status = "neutral"
        self._footer_text = ""
        self._content_publish_pending = False
        self._app_event_filter_installed = False
        self._runtime_toggle_should_stop = False

        self._controller = RawPresetEditorController(
            presets_feature=presets_feature,
            launch_method=self._launch_method,
        )
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
        self.activateButton.clicked.connect(self._activate_preset)
        actions_layout.addWidget(self.activateButton)

        self.openExternalButton = PushButton("Открыть в редакторе", self)
        self.openExternalButton.setIcon(_fluent_icon("FOLDER"))
        self.openExternalButton.clicked.connect(self._open_external)
        actions_layout.addWidget(self.openExternalButton)

        self.runtimeToggleButton = PushButton("Запустить", self)
        self.runtimeToggleButton.setIcon(_fluent_icon("PLAY"))
        self.runtimeToggleButton.clicked.connect(self._toggle_runtime)
        actions_layout.addWidget(self.runtimeToggleButton)

        actions_layout.addStretch(1)
        self.searchInput = SearchLineEdit(self)
        self.searchInput.setPlaceholderText("Поиск по тексту пресета")
        set_tooltip(self.searchInput, "Найти строку в тексте открытого пресета.")
        self.searchInput.setClearButtonEnabled(True)
        self.searchInput.setFixedHeight(34)
        self.searchInput.setMinimumWidth(220)
        self.searchInput.setMaximumWidth(300)
        self.searchInput.setProperty("noDrag", True)
        self.searchInput.textChanged.connect(self._search_preset_text)
        actions_layout.addWidget(self.searchInput, 0)
        self.add_widget(actions)

        self.editor = PlainTextEdit(self)
        apply_editor_smooth_scroll_preference(self.editor)
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
        worker = self._raw_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    self._after_raw_preset_save = callback
                    return False
            except Exception:
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

    def _request_raw_preset_text(self) -> None:
        self._raw_load_request_id += 1
        request_id = self._raw_load_request_id
        self._is_loading = True
        self._set_footer("Загрузка...")
        worker = self._controller.create_load_worker(request_id, self._preset_file_name, self)
        self._raw_load_worker = worker
        worker.loaded.connect(self._on_raw_preset_text_loaded)
        worker.failed.connect(self._on_raw_preset_text_failed)
        worker.finished.connect(lambda w=worker: self._on_raw_preset_worker_finished(w))
        worker.start()

    def _on_raw_preset_text_loaded(self, request_id: int, result) -> None:
        if request_id != self._raw_load_request_id:
            return
        if getattr(result, "file_name", ""):
            self._preset_file_name = str(result.file_name or "").strip()
        if getattr(result, "display_name", ""):
            self._preset_name = str(result.display_name or "").strip()
        self._preset_path = getattr(result, "path", None)
        self._preset_origin = str(getattr(result, "origin", "") or "user").strip().lower() or "user"
        self.editor.setPlainText(result.text)
        self._set_footer(result.footer_text)
        self._is_loading = False
        self._refresh_header()

    def _on_raw_preset_text_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_load_request_id:
            return
        self._set_footer(f"Ошибка загрузки: {error}")
        self._is_loading = False

    def _on_raw_preset_worker_finished(self, worker) -> None:
        if self._raw_load_worker is worker:
            self._raw_load_worker = None
        worker.deleteLater()

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

    def _save_file(self, *, publish_content_changed: bool = False) -> bool:
        if self._cleanup_in_progress:
            return False
        if self._preset_path is None:
            return False
        return self._request_raw_preset_save(
            file_name=self._preset_file_name,
            source_text=self.editor.toPlainText(),
            publish_content_changed=publish_content_changed,
        )

    def _request_raw_preset_save(
        self,
        *,
        file_name: str,
        source_text: str,
        publish_content_changed: bool = False,
    ) -> bool:
        worker = self._raw_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    pending = self._pending_raw_preset_save
                    self._pending_raw_preset_save = (
                        str(file_name or "").strip(),
                        str(source_text or ""),
                        bool(publish_content_changed or (pending[2] if pending else False)),
                    )
                    return True
            except Exception:
                return False
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
        source_text: str,
        publish_content_changed: bool,
    ) -> None:
        self._raw_save_request_id += 1
        request_id = self._raw_save_request_id
        self._raw_save_succeeded = False
        self._set_footer("Сохранение...")
        worker = self._controller.create_save_worker(
            request_id,
            file_name=str(file_name or "").strip(),
            source_text=str(source_text or ""),
            publish_content_changed=bool(publish_content_changed),
            parent=self,
        )
        self._raw_save_worker = worker
        worker.saved.connect(self._on_raw_preset_save_finished)
        worker.failed.connect(self._on_raw_preset_save_failed)
        worker.finished.connect(lambda w=worker: self._on_raw_preset_save_worker_finished(w))
        worker.start()

    def _on_raw_preset_save_finished(
        self,
        request_id: int,
        requested_file_name: str,
        result,
        publish_content_changed: bool,
    ) -> None:
        if request_id != self._raw_save_request_id:
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
        self._raw_save_succeeded = False
        self._set_footer(f"Ошибка сохранения: {error}")
        self._show_error(str(error))

    def _on_raw_preset_save_worker_finished(self, worker) -> None:
        if self._raw_save_worker is worker:
            self._raw_save_worker = None
        worker.deleteLater()
        pending = self._pending_raw_preset_save
        self._pending_raw_preset_save = None
        if pending and not self._cleanup_in_progress:
            self._start_raw_preset_save_worker(
                file_name=pending[0],
                source_text=pending[1],
                publish_content_changed=pending[2],
            )
            return
        callback = self._after_raw_preset_save
        self._after_raw_preset_save = None
        if callback is not None and self._raw_save_succeeded and not self._cleanup_in_progress:
            callback()

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

    def _on_ui_state_changed(self, state, _changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        self._render_runtime_toggle(state)
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
            runtime_available=self._runtime_feature is not None,
        )

    def _toggle_runtime(self) -> None:
        runtime = self._runtime_feature
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
        if self.__dict__.get("_pending_raw_preset_save") is not None:
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
        worker = self._raw_activate_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._raw_activate_request_id += 1
        request_id = self._raw_activate_request_id
        if self.activateButton is not None:
            self.activateButton.setEnabled(False)
        worker = self._controller.create_activate_worker(request_id, self._preset_file_name, self)
        self._raw_activate_worker = worker
        worker.activated.connect(self._on_preset_activation_finished)
        worker.failed.connect(self._on_preset_activation_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_activation_worker_finished(w))
        worker.start()

    def _on_preset_activation_finished(self, request_id: int, activated: bool) -> None:
        if request_id != self._raw_activate_request_id:
            return
        if activated:
            self._refresh_header()
            self._set_footer(self._activation_footer_text())
            self._show_success(f"Пресет «{self._preset_name}» активирован")
            return
        self._show_error(f"Не удалось активировать пресет «{self._preset_name}»")

    def _on_preset_activation_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_activate_request_id:
            return
        self._show_error(str(error))

    def _on_preset_activation_worker_finished(self, worker) -> None:
        if self._raw_activate_worker is worker:
            self._raw_activate_worker = None
        worker.deleteLater()
        if self.activateButton is not None:
            self.activateButton.setEnabled(True)

    def _request_raw_preset_action(self, action: str, **payload) -> None:
        worker = self._raw_action_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._raw_action_request_id += 1
        request_id = self._raw_action_request_id
        worker = self._controller.create_action_worker(
            request_id,
            action=action,
            payload=payload,
            parent=self,
        )
        self._raw_action_worker = worker
        worker.completed.connect(self._on_raw_preset_action_finished)
        worker.failed.connect(self._on_raw_preset_action_failed)
        worker.finished.connect(lambda w=worker: self._on_raw_preset_action_worker_finished(w))
        worker.start()

    def _on_raw_preset_action_finished(self, request_id: int, action: str, result, payload) -> None:
        if request_id != self._raw_action_request_id:
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
        self._show_error(str(error))

    def _on_raw_preset_action_worker_finished(self, worker) -> None:
        if self._raw_action_worker is worker:
            self._raw_action_worker = None
        worker.deleteLater()

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
        try:
            return self._controller.selected_name()
        except Exception:
            return ""

    def _current_selected_file_name(self) -> str:
        try:
            return self._controller.selected_file_name()
        except Exception:
            return ""

    def _notify_preset_structure_changed(self) -> None:
        store = self._ui_state_store
        if store is None:
            return
        try:
            store.bump_preset_structure_revision()
        except Exception:
            pass

    def cleanup(self) -> None:
        try:
            self._commit_pending_content_change()
        except Exception:
            pass
        self._cleanup_in_progress = True
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
