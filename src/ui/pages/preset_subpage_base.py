from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QFileDialog

from ui.pages.base_page import BasePage

try:
    from qfluentwidgets import (
        Action,
        BodyLabel,
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
        TransparentPushButton,
        TransparentToolButton,
    )
except ImportError:
    from PyQt6.QtWidgets import (
        QLabel as BodyLabel,
        QLabel as CaptionLabel,
        QLabel as StrongBodyLabel,
        QLineEdit as LineEdit,
        QPlainTextEdit as PlainTextEdit,
        QPushButton as PushButton,
        QPushButton as TransparentPushButton,
        QPushButton as TransparentToolButton,
        QFrame as SimpleCardWidget,
    )

    MessageBox = None
    MessageBoxBase = object
    RoundMenu = None
    Action = None
    FluentIcon = None
    InfoBar = None


def _fluent_icon(name: str):
    if FluentIcon is None:
        return None
    return getattr(FluentIcon, name, None)


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
        if name != self._current_name and name in self._existing_names:
            self.warningLabel.setText(f"Пресет «{name}» уже существует.")
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True


class PresetSubpageBase(BasePage):
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(self._default_title(), "", parent)
        self.parent_app = parent
        self._preset_name = ""
        self._preset_path: Path | None = None
        self._is_loading = False
        self._loaded_once = False
        self._manager = None
        self._direct_facade = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_file)

        self._build_ui()

    def _default_title(self) -> str:
        raise NotImplementedError

    def _create_manager(self):
        raise NotImplementedError

    def _get_manager_obj(self):
        if self._manager is None:
            self._manager = self._create_manager()
        return self._manager

    def _get_preset_path(self, name: str) -> Path:
        raise NotImplementedError

    def _direct_launch_method(self) -> str | None:
        return None

    def _get_direct_facade(self):
        method = self._direct_launch_method()
        if not method:
            return None
        if self._direct_facade is None:
            from core.presets.direct_facade import DirectPresetFacade

            self._direct_facade = DirectPresetFacade.from_launch_method(method)
        return self._direct_facade

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

    def _build_ui(self) -> None:
        top_row = QWidget(self)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        self.backButton = TransparentPushButton(self)
        self.backButton.setText("Назад к списку")
        self.backButton.setIcon(_fluent_icon("LEFT_ARROW"))
        self.backButton.clicked.connect(self.back_clicked.emit)
        top_layout.addWidget(self.backButton, 0)
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
        self.editor.textChanged.connect(self._on_text_changed)
        self.add_widget(self.editor, 1)

        self.footerLabel = CaptionLabel("", self)
        self.add_widget(self.footerLabel)

    def set_preset_name(self, name: str) -> None:
        self._flush_pending_save()
        self._preset_name = str(name or "").strip()
        facade = self._get_direct_facade()
        if facade is not None and self._preset_name:
            try:
                self._preset_path = facade.get_source_path(self._preset_name)
            except Exception:
                self._preset_path = self._get_preset_path(self._preset_name)
        else:
            self._preset_path = self._get_preset_path(self._preset_name)
        self._loaded_once = True
        self._load_file()
        self._refresh_header()

    def _flush_pending_save(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_file()

    def _refresh_header(self) -> None:
        self.title_label.setText(self._preset_name or self._default_title())
        active_name = self._current_selected_name()
        is_active = active_name.lower() == self._preset_name.lower() if self._preset_name else False
        status = "Активный пресет" if is_active else "Пользовательский пресет"
        self.statusLabel.setText(status)
        self.activateButton.setVisible(not is_active)
        self.metaLabel.setText(f"Имя: {self._preset_name}")
        self.pathLabel.setText(str(self._preset_path or ""))

    def _load_file(self) -> None:
        self._is_loading = True
        try:
            if self._preset_path is None or not self._preset_path.exists():
                self.editor.setPlainText("")
                self._set_footer("Файл не найден")
                return
            self.editor.setPlainText(self._preset_path.read_text(encoding="utf-8", errors="replace"))
            self._set_footer("Загружено")
        except Exception as e:
            self._set_footer(f"Ошибка загрузки: {e}")
        finally:
            self._is_loading = False

    def _on_text_changed(self) -> None:
        if self._is_loading:
            return
        self._save_timer.stop()
        self._save_timer.start(900)
        self._set_footer("Изменения...")

    def _save_file(self) -> None:
        if self._preset_path is None:
            return
        try:
            facade = self._get_direct_facade()
            used_facade = facade is not None
            if facade is not None:
                facade.save_source_text(self._preset_name, self.editor.toPlainText())
            else:
                self._preset_path.parent.mkdir(parents=True, exist_ok=True)
                self._preset_path.write_text(self.editor.toPlainText(), encoding="utf-8")
            active_name = self._current_selected_name()
            if active_name.lower() == self._preset_name.lower():
                if not used_facade:
                    self._refresh_selected_runtime()
                self._notify_preset_switched()
            self._notify_preset_saved(self._preset_name)
            self._set_footer(f"Сохранено {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            self._set_footer(f"Ошибка сохранения: {e}")
            self._show_error(str(e))

    def _set_footer(self, text: str) -> None:
        self.footerLabel.setText(text)

    def _activate_preset(self) -> None:
        self._flush_pending_save()
        try:
            if self._activate_selected_preset():
                self._refresh_header()
                self._show_success(f"Пресет «{self._preset_name}» активирован")
            else:
                self._show_error(f"Не удалось активировать пресет «{self._preset_name}»")
        except Exception as e:
            self._show_error(str(e))

    def _open_external(self) -> None:
        try:
            self._flush_pending_save()
            if self._preset_path is None:
                return
            if os.name == "nt":
                os.startfile(str(self._preset_path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(self._preset_path)])
        except Exception as e:
            self._show_error(str(e))

    def _open_menu(self) -> None:
        if RoundMenu is not None and Action is not None:
            menu = RoundMenu(parent=self)
            rename_action = Action(_fluent_icon("RENAME"), "Переименовать", menu)
            duplicate_action = Action(_fluent_icon("COPY"), "Дублировать", menu)
            export_action = Action(_fluent_icon("SHARE"), "Экспорт", menu)
            reset_action = Action(_fluent_icon("SYNC"), "Сбросить", menu)
            delete_action = Action(_fluent_icon("DELETE"), "Удалить", menu)
            rename_action.triggered.connect(self._rename_preset)
            duplicate_action.triggered.connect(self._duplicate_preset)
            export_action.triggered.connect(self._export_preset)
            reset_action.triggered.connect(self._reset_preset)
            delete_action.triggered.connect(self._delete_preset)
            menu.addAction(rename_action)
            menu.addAction(duplicate_action)
            menu.addAction(export_action)
            menu.addAction(reset_action)
            menu.addAction(delete_action)
            menu.exec(self.menuButton.mapToGlobal(self.menuButton.rect().bottomLeft()))

    def _rename_preset(self) -> None:
        self._flush_pending_save()
        facade = self._get_direct_facade()
        existing_names = facade.list_names() if facade is not None else self._get_manager_obj().list_presets()
        dialog = _RenameDialog(self._preset_name, existing_names, self.window())
        if not dialog.exec():
            return
        new_name = dialog.nameEdit.text().strip()
        if not new_name or new_name == self._preset_name:
            return
        try:
            facade = self._get_direct_facade()
            if facade is not None:
                facade.rename(self._preset_name, new_name)
                self._notify_presets_changed()
                self.set_preset_name(new_name)
                if facade.is_selected(new_name):
                    self._notify_preset_switched()
                self._show_success(f"Пресет переименован: {new_name}")
            elif self._get_manager_obj().rename_preset(self._preset_name, new_name):
                self.set_preset_name(new_name)
                self._show_success(f"Пресет переименован: {new_name}")
            else:
                self._show_error("Не удалось переименовать пресет")
        except Exception as e:
            self._show_error(str(e))

    def _duplicate_preset(self) -> None:
        self._flush_pending_save()
        try:
            counter = 1
            new_name = f"{self._preset_name} (копия)"
            while self._get_manager_obj().preset_exists(new_name):
                counter += 1
                new_name = f"{self._preset_name} (копия {counter})"
            facade = self._get_direct_facade()
            if facade is not None:
                facade.duplicate(self._preset_name, new_name)
                self._notify_presets_changed()
                self.set_preset_name(new_name)
                self._show_success(f"Создан дубликат: {new_name}")
            elif self._get_manager_obj().duplicate_preset(self._preset_name, new_name):
                self.set_preset_name(new_name)
                self._show_success(f"Создан дубликат: {new_name}")
            else:
                self._show_error("Не удалось дублировать пресет")
        except Exception as e:
            self._show_error(str(e))

    def _export_preset(self) -> None:
        self._flush_pending_save()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать пресет",
            f"{self._preset_name}.txt",
            "Preset files (*.txt);;All files (*.*)",
        )
        if not file_path:
            return
        try:
            facade = self._get_direct_facade()
            if facade is not None:
                facade.export_plain_text(self._preset_name, Path(file_path))
                self._show_success(f"Пресет экспортирован: {file_path}")
            elif self._get_manager_obj().export_preset(self._preset_name, Path(file_path)):
                self._show_success(f"Пресет экспортирован: {file_path}")
            else:
                self._show_error("Не удалось экспортировать пресет")
        except Exception as e:
            self._show_error(str(e))

    def _reset_preset(self) -> None:
        self._flush_pending_save()
        if MessageBox is not None:
            box = MessageBox(
                "Сбросить пресет?",
                f"Пресет «{self._preset_name}» будет перезаписан данными из шаблона.",
                self.window(),
            )
            box.yesButton.setText("Сбросить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        try:
            facade = self._get_direct_facade()
            if facade is not None:
                facade.reset_to_template(self._preset_name)
                self._load_file()
                self._refresh_header()
                self._notify_preset_saved(self._preset_name)
                if facade.is_selected(self._preset_name):
                    self._notify_preset_switched()
                self._show_success(f"Пресет «{self._preset_name}» сброшен")
            elif self._get_manager_obj().reset_preset_to_default_template(self._preset_name):
                self._load_file()
                self._refresh_header()
                self._show_success(f"Пресет «{self._preset_name}» сброшен")
            else:
                self._show_error("Не удалось сбросить пресет")
        except Exception as e:
            self._show_error(str(e))

    def _delete_preset(self) -> None:
        self._flush_pending_save()
        if MessageBox is not None:
            box = MessageBox(
                "Удалить пресет?",
                f"Пресет «{self._preset_name}» будет удалён.",
                self.window(),
            )
            box.yesButton.setText("Удалить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        try:
            name = self._preset_name
            facade = self._get_direct_facade()
            if facade is not None:
                facade.delete(name)
                self._notify_presets_changed()
                self.back_clicked.emit()
                self._show_success(f"Пресет «{name}» удалён")
            elif self._get_manager_obj().delete_preset(name):
                self.back_clicked.emit()
                self._show_success(f"Пресет «{name}» удалён")
            else:
                self._show_error("Не удалось удалить пресет")
        except Exception as e:
            self._show_error(str(e))

    def _current_selected_name(self) -> str:
        method = self._direct_launch_method()
        if method:
            try:
                from core.services import get_direct_flow_coordinator

                return (get_direct_flow_coordinator().get_selected_preset_name(method) or "").strip()
            except Exception:
                pass
        return (self._get_manager_obj().get_active_preset_name() or "").strip()

    def _refresh_selected_runtime(self) -> bool:
        method = self._direct_launch_method()
        if method:
            try:
                from core.services import get_direct_flow_coordinator

                get_direct_flow_coordinator().refresh_selected_runtime(method)
                return True
            except Exception:
                return False
        return bool(self._get_manager_obj().switch_preset(self._preset_name, reload_dpi=False))

    def _activate_selected_preset(self) -> bool:
        method = self._direct_launch_method()
        if method:
            try:
                from core.services import get_direct_flow_coordinator

                get_direct_flow_coordinator().select_preset(method, self._preset_name)
                self._notify_preset_switched()
                return True
            except Exception:
                return False
        return bool(self._get_manager_obj().switch_preset(self._preset_name, reload_dpi=False))

    def _notify_preset_switched(self) -> None:
        method = self._direct_launch_method()
        try:
            if method == "direct_zapret2":
                from preset_zapret2.preset_store import get_preset_store

                get_preset_store().notify_preset_switched(self._preset_name)
            elif method == "direct_zapret1":
                from preset_zapret1.preset_store import get_preset_store_v1

                get_preset_store_v1().notify_preset_switched(self._preset_name)
        except Exception:
            pass

    def _notify_preset_saved(self, name: str) -> None:
        method = self._direct_launch_method()
        try:
            if method == "direct_zapret2":
                from preset_zapret2.preset_store import get_preset_store

                get_preset_store().notify_preset_saved(name)
            elif method == "direct_zapret1":
                from preset_zapret1.preset_store import get_preset_store_v1

                get_preset_store_v1().notify_preset_saved(name)
            else:
                self._get_manager_obj().invalidate_preset_cache(name)
        except Exception:
            pass

    def _notify_presets_changed(self) -> None:
        method = self._direct_launch_method()
        try:
            if method == "direct_zapret2":
                from preset_zapret2.preset_store import get_preset_store

                get_preset_store().notify_presets_changed()
            elif method == "direct_zapret1":
                from preset_zapret1.preset_store import get_preset_store_v1

                get_preset_store_v1().notify_presets_changed()
            else:
                self._get_manager_obj().invalidate_preset_cache(None)
        except Exception:
            pass
