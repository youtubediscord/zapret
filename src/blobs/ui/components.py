"""Компоненты страницы BlobsPage."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QFileDialog, QSizePolicy
)

from ui.compat_widgets import set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        LineEdit, ComboBox, MessageBox,
        MessageBoxBase, SubtitleLabel, BodyLabel, CaptionLabel,
        TransparentToolButton,
    )
except ImportError:
    from PyQt6.QtWidgets import (
        QLineEdit as LineEdit, QComboBox as ComboBox,
        QDialog as MessageBoxBase, QPushButton as TransparentToolButton,
    )
    MessageBox = None
    SubtitleLabel = QLabel
    BodyLabel = QLabel
    CaptionLabel = QLabel


class BlobItemWidget(QFrame):
    """Виджет одного блоба в списке."""

    deleted = pyqtSignal(str)

    def __init__(self, name: str, info: dict, parent=None, language: str = "ru"):
        super().__init__(parent)
        self.blob_name = name
        self.blob_info = info
        self._ui_language = language

        self._tokens = get_theme_tokens()
        self._current_qss = ""

        self._icon_label = None
        self._name_label = None
        self._user_badge = None
        self._desc_label = None
        self._value_label = None
        self._status_label = None
        self._delete_btn = None

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._icon_label = QLabel()
        layout.addWidget(self._icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)

        self._name_label = QLabel(self.blob_name)
        name_layout.addWidget(self._name_label)

        if self.blob_info.get("is_user"):
            self._user_badge = QLabel(self._tr("page.blobs.item.user_badge", "пользовательский"))
            self._user_badge.setStyleSheet("""
                QLabel {
                    color: #ffc107;
                    font-size: 10px;
                    background: rgba(255, 193, 7, 0.15);
                    padding: 2px 6px;
                    border-radius: 3px;
                }
            """)
            name_layout.addWidget(self._user_badge)

        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        desc = self.blob_info.get("description", "")
        if desc:
            self._desc_label = QLabel(desc)
            self._desc_label.setWordWrap(True)
            info_layout.addWidget(self._desc_label)

        value = self.blob_info.get("value", "")
        if value:
            if value.startswith("@"):
                display_value = os.path.basename(value[1:])
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value

            self._value_label = QLabel(display_value)
            info_layout.addWidget(self._value_label)

        layout.addLayout(info_layout, 1)

        if self.blob_info.get("type") == "file":
            if self.blob_info.get("exists", True):
                self._status_label = QLabel("✓")
                self._status_label.setStyleSheet("color: #6ccb5f; font-size: 14px;")
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_found", "Файл найден"))
            else:
                self._status_label = QLabel("✗")
                self._status_label.setStyleSheet("color: #ff6b6b; font-size: 14px;")
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_missing", "Файл не найден"))
            layout.addWidget(self._status_label)

        if self.blob_info.get("is_user"):
            self._delete_btn = TransparentToolButton()
            self._delete_btn.setIcon(get_themed_qta_icon('fa5s.trash-alt', color='#ff6b6b'))
            self._delete_btn.setFixedSize(28, 28)
            self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._delete_btn.clicked.connect(self._on_delete)
            layout.addWidget(self._delete_btn)

        self._apply_theme()

    def refresh_theme(self) -> None:
        self._tokens = get_theme_tokens()
        self._apply_theme()

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        if self._user_badge is not None:
            self._user_badge.setText(self._tr("page.blobs.item.user_badge", "пользовательский"))
        if self._status_label is not None:
            if self.blob_info.get("exists", True):
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_found", "Файл найден"))
            else:
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_missing", "Файл не найден"))

    def _apply_theme(self) -> None:
        tokens = self._tokens or get_theme_tokens("Темная синяя")

        qss = f"""
            BlobItemWidget {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
                padding: 8px;
            }}
            BlobItemWidget:hover {{
                background: {tokens.surface_bg_hover};
                border: 1px solid {tokens.surface_border_hover};
            }}
        """
        if qss != self._current_qss:
            self._current_qss = qss
            self.setStyleSheet(qss)

        if self._name_label is not None:
            self._name_label.setStyleSheet(
                f"color: {tokens.fg}; font-size: 13px; font-weight: 600;"
            )
        if self._desc_label is not None:
            self._desc_label.setStyleSheet(
                f"color: {tokens.fg_muted}; font-size: 11px;"
            )
        if self._value_label is not None:
            self._value_label.setStyleSheet(
                f"color: {tokens.fg_faint}; font-size: 10px; font-family: Consolas;"
            )

        if self._icon_label is not None:
            if self.blob_info.get("type") == "hex":
                icon_name = "fa5s.hashtag"
                icon_color = "#ffc107"
            else:
                icon_name = "fa5s.file"
                icon_color = tokens.accent_hex
            try:
                self._icon_label.setPixmap(get_cached_qta_pixmap(icon_name, color=icon_color, size=16))
            except Exception:
                self._icon_label.setPixmap(get_cached_qta_pixmap("fa5s.file", color=tokens.accent_hex, size=16))

    def _on_delete(self):
        box = MessageBox(
            self._tr("page.blobs.dialog.delete.title", "Удаление блоба"),
            self._tr("page.blobs.dialog.delete.body", "Удалить пользовательский блоб '{name}'?", name=self.blob_name),
            self.window(),
        )
        if box.exec():
            self.deleted.emit(self.blob_name)


class AddBlobDialog(MessageBoxBase):
    """Диалог добавления нового блоба."""

    def __init__(self, parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            text = tr_catalog(key, language=self._ui_language, default=default)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        self._tr = _tr

        self.titleLabel = SubtitleLabel(self._tr("page.blobs.dialog.add.title", "Добавить блоб"), self.widget)

        name_label = BodyLabel(self._tr("page.blobs.dialog.add.name", "Имя"), self.widget)
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.name.placeholder", "Латиница, цифры, подчеркивания"))

        type_label = BodyLabel(self._tr("page.blobs.dialog.add.type", "Тип"), self.widget)
        self.type_combo = ComboBox(self.widget)
        self.type_combo.addItem(self._tr("page.blobs.dialog.add.type.file", "Файл (.bin)"), userData="file")
        self.type_combo.addItem(self._tr("page.blobs.dialog.add.type.hex", "Hex значение"), userData="hex")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        value_label = BodyLabel(self._tr("page.blobs.dialog.add.value", "Значение"), self.widget)
        self._value_container = QWidget(self.widget)
        value_layout = QHBoxLayout(self._value_container)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(6)
        self.value_edit = LineEdit(self._value_container)
        self.value_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.value.path_placeholder", "Путь к файлу"))
        value_layout.addWidget(self.value_edit, 1)
        self.browse_btn = TransparentToolButton(self._value_container)
        self.browse_btn.setIcon(get_themed_qta_icon("fa5s.folder-open", color="#888"))
        self.browse_btn.setFixedSize(32, 32)
        set_tooltip(self.browse_btn, self._tr("page.blobs.dialog.add.browse.tooltip", "Выбрать файл"))
        self.browse_btn.clicked.connect(self._browse_file)
        value_layout.addWidget(self.browse_btn)

        desc_label = BodyLabel(self._tr("page.blobs.dialog.add.description", "Описание (опционально)"), self.widget)
        self.desc_edit = LineEdit(self.widget)
        self.desc_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.description.placeholder", "Краткое описание блоба"))

        self._error_label = CaptionLabel("", self.widget)
        try:
            from qfluentwidgets import isDarkTheme as _idt
            _err_clr = "#ff6b6b" if _idt() else "#dc2626"
        except Exception:
            _err_clr = "#dc2626"
        self._error_label.setStyleSheet(f"color: {_err_clr};")
        self._error_label.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addWidget(type_label)
        self.viewLayout.addWidget(self.type_combo)
        self.viewLayout.addWidget(value_label)
        self.viewLayout.addWidget(self._value_container)
        self.viewLayout.addWidget(desc_label)
        self.viewLayout.addWidget(self.desc_edit)
        self.viewLayout.addWidget(self._error_label)

        self.yesButton.setText(self._tr("page.blobs.dialog.add.button.add", "Добавить"))
        self.cancelButton.setText(self._tr("page.blobs.dialog.add.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(400)

    def _on_type_changed(self, index):
        blob_type = self.type_combo.currentData()
        self.browse_btn.setVisible(blob_type == "file")
        if blob_type == "hex":
            self.value_edit.setPlaceholderText(
                self._tr("page.blobs.dialog.add.value.hex_placeholder", "Hex значение (например: 0x0E0E0F0E)")
            )
        else:
            self.value_edit.setPlaceholderText(
                self._tr("page.blobs.dialog.add.value.path_placeholder_bin", "Путь к .bin файлу")
            )

    def _browse_file(self):
        from config.config import BIN_FOLDER


        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("page.blobs.dialog.add.browse.title", "Выберите файл блоба"),
            BIN_FOLDER,
            "Binary files (*.bin);;All files (*.*)",
        )
        if file_path:
            if file_path.startswith(BIN_FOLDER):
                file_path = os.path.relpath(file_path, BIN_FOLDER)
            self.value_edit.setText(file_path)

    def validate(self) -> bool:
        import re

        name = self.name_edit.text().strip()
        value = self.value_edit.text().strip()

        if not name:
            self._show_error(self._tr("page.blobs.dialog.add.error.name_required", "Введите имя блоба"))
            return False

        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            self._show_error(
                self._tr(
                    "page.blobs.dialog.add.error.name_invalid",
                    "Имя должно начинаться с буквы и содержать только латиницу, цифры и подчеркивания",
                )
            )
            return False

        if not value:
            self._show_error(self._tr("page.blobs.dialog.add.error.value_required", "Введите значение блоба"))
            return False

        blob_type = self.type_combo.currentData()
        if blob_type == "hex" and not value.startswith("0x"):
            self._show_error(self._tr("page.blobs.dialog.add.error.hex_prefix", "Hex значение должно начинаться с 0x"))
            return False

        return True

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentData(),
            "value": self.value_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
        }
