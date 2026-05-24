from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog

from ui.pages.base_page import BasePage
from ui.fluent_widgets import style_semantic_caption_label
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
        ui_state_store,
    ):
        self._launch_method = str(launch_method or "").strip()
        self._title = str(title or "").strip() or "Пресет"
        super().__init__(self._title, "", parent)
        self._open_back_callback = open_back
        self._open_root_callback = open_root
        self._preset_name = ""
        self._preset_file_name = ""
        self._preset_path: Path | None = None
        self._is_loading = False
        self._raw_load_request_id = 0
        self._raw_load_worker = None
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._footer_status = "neutral"
        self._footer_text = ""
        self._content_publish_pending = False
        self._app_event_filter_installed = False

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

    def _get_preset_path(self, name: str) -> Path:
        return self._controller.source_path(str(name or "").strip())

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
        try:
            breadcrumb.blockSignals(True)
            breadcrumb.clear()
            breadcrumb.addItem("root", self._breadcrumb_root_text())
            breadcrumb.addItem("list", self._breadcrumb_parent_text())
            breadcrumb.addItem("raw_preset", self._breadcrumb_current_text())
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
            if not self._preset_file_name:
                return False
            return self._controller.is_builtin(self._preset_file_name)
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
        actions_layout.addStretch(1)
        self.add_widget(actions)

        self.editor = PlainTextEdit(self)
        apply_editor_smooth_scroll_preference(self.editor)
        self.editor.textChanged.connect(self._on_text_changed)
        self.add_widget(self.editor, 1)

        self.footerStatusBar = PresetStatusBar(self)
        self.footerLabel = self.footerStatusBar.text_label
        self.add_widget(self.footerStatusBar)

    def set_preset_file_name(self, file_name: str) -> None:
        self._flush_pending_save()
        self._preset_file_name = str(file_name or "").strip()
        self._preset_name = Path(self._preset_file_name).stem if self._preset_file_name else ""
        if self._preset_file_name:
            try:
                manifest = self._controller.manifest(self._preset_file_name)
                if manifest is not None:
                    self._preset_name = manifest.name
                    self._preset_file_name = manifest.file_name
                self._preset_path = self._controller.source_path(self._preset_file_name)
            except Exception:
                self._preset_path = self._get_preset_path(self._preset_name)
        else:
            self._preset_path = self._get_preset_path(self._preset_name)
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
            self._save_file()

    def _refresh_header(self) -> None:
        self._rebuild_breadcrumb()
        active_name = self._current_selected_name()
        active_file_name = self._current_selected_file_name()
        is_active = False
        if self._preset_file_name:
            is_active = active_file_name.lower() == self._preset_file_name.lower()
        elif self._preset_name:
            is_active = active_name.lower() == self._preset_name.lower()
        origin = "builtin" if self._is_current_builtin() else "user"
        if self._preset_file_name:
            try:
                manifest = self._controller.manifest(self._preset_file_name)
                if manifest is not None:
                    kind = str(manifest.kind or "").strip().lower()
                    if kind in {"builtin", "imported", "user"}:
                        origin = kind
            except Exception:
                pass

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
        self.statusLabel.setText(status)
        self.activateButton.setVisible(not is_active)
        self.metaLabel.setText(f"Имя: {self._preset_name}")
        self.pathLabel.setText(str(self._preset_path or ""))

    def _load_file(self) -> None:
        self._request_raw_preset_text()

    def _request_raw_preset_text(self) -> None:
        self._raw_load_request_id += 1
        request_id = self._raw_load_request_id
        self._is_loading = True
        self._set_footer("Загрузка...")
        worker = self._controller.create_load_worker(request_id, self._preset_path, self)
        self._raw_load_worker = worker
        worker.loaded.connect(self._on_raw_preset_text_loaded)
        worker.failed.connect(self._on_raw_preset_text_failed)
        worker.finished.connect(lambda w=worker: self._on_raw_preset_worker_finished(w))
        worker.start()

    def _on_raw_preset_text_loaded(self, request_id: int, result) -> None:
        if request_id != self._raw_load_request_id:
            return
        self.editor.setPlainText(result.text)
        self._set_footer(result.footer_text)
        self._is_loading = False

    def _on_raw_preset_text_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_load_request_id:
            return
        self._set_footer(f"Ошибка загрузки: {error}")
        self._is_loading = False

    def _on_raw_preset_worker_finished(self, worker) -> None:
        if self._raw_load_worker is worker:
            self._raw_load_worker = None
        worker.deleteLater()

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

    def _save_file(self, *, publish_content_changed: bool = False) -> None:
        if self._cleanup_in_progress:
            return
        if self._preset_path is None:
            return
        try:
            result = self._controller.save_text(
                file_name=self._preset_file_name,
                source_text=self.editor.toPlainText(),
                publish_content_changed=publish_content_changed,
            )
            updated = result.updated
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = result.path
            if publish_content_changed:
                self._content_publish_pending = False
            self._set_footer(result.footer_text)
        except Exception as e:
            self._set_footer(f"Ошибка сохранения: {e}")
            self._show_error(str(e))

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
        self._render_footer_status(state)

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

    def _activate_preset(self) -> None:
        self._flush_pending_save()
        try:
            if self._activate_selected_preset():
                self._refresh_header()
                self._set_footer(self._activation_footer_text())
                self._show_success(f"Пресет «{self._preset_name}» активирован")
            else:
                self._show_error(f"Не удалось активировать пресет «{self._preset_name}»")
        except Exception as e:
            self._show_error(str(e))

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
            self._flush_pending_save()
            if self._preset_path is None:
                return
            self._controller.open_source_file(self._preset_path)
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
        self._flush_pending_save()
        dialog = _RenameDialog(self._preset_name, [], self.window())
        if not dialog.exec():
            return
        new_name = dialog.nameEdit.text().strip()
        if not new_name or new_name == self._preset_name:
            return
        try:
            updated = self._controller.rename(
                file_name=self._preset_file_name,
                new_name=new_name,
            )
            self._notify_preset_structure_changed()
            self.set_preset_file_name(updated.file_name)
            self._show_success(f"Пресет переименован: {new_name}")
        except Exception as e:
            self._show_error(str(e))

    def _duplicate_preset(self) -> None:
        self._flush_pending_save()
        try:
            new_name = f"{self._preset_name} (копия)"
            duplicated = self._controller.duplicate(
                file_name=self._preset_file_name,
                new_name=new_name,
            )
            self._notify_preset_structure_changed()
            self.set_preset_file_name(duplicated.file_name)
            self._show_success(f"Создан дубликат: {new_name}")
        except Exception as e:
            self._show_error(str(e))

    def _export_preset(self) -> None:
        self._flush_pending_save()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать пресет",
            f"{self._preset_name}.txt",
            "Файлы пресетов (*.txt);;Все файлы (*.*)",
        )
        if not file_path:
            return
        try:
            self._controller.export(
                file_name=self._preset_file_name,
                target_path=file_path,
            )
            self._show_success(f"Пресет экспортирован: {file_path}")
        except Exception as e:
            self._show_error(str(e))

    def _reset_preset(self) -> None:
        self._flush_pending_save()
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
        try:
            updated = self._controller.reset_to_builtin(
                file_name=self._preset_file_name,
            )
            self._preset_name = updated.name
            self._preset_file_name = updated.file_name
            self._preset_path = self._controller.source_path(self._preset_file_name)
            self._load_file()
            self._refresh_header()
            self._show_success(f"Восстановлен встроенный пресет «{self._preset_name}»")
        except Exception as e:
            self._show_error(str(e))

    def _delete_preset(self) -> None:
        if self._is_current_builtin():
            self._show_error("Встроенный пресет нельзя удалить.")
            return
        self._flush_pending_save()
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
        try:
            name = self._preset_name
            self._controller.delete(
                file_name=self._preset_file_name,
            )
            self._notify_preset_structure_changed()
            self._open_back_callback()
            self._show_success(f"Пресет «{name}» удалён")
        except Exception as e:
            self._show_error(str(e))

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

    def _activate_selected_preset(self) -> bool:
        try:
            return self._controller.activate(
                file_name=self._preset_file_name,
            )
        except Exception:
            return False

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
