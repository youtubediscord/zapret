"""Диалоги для создания и переименования пресетов Zapret 2 Direct."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QPushButton

from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, SubtitleLabel
except ImportError:
    from PyQt6.QtWidgets import QDialog as MessageBoxBase, QLineEdit as LineEdit

    BodyLabel = QLabel
    CaptionLabel = QLabel
    SubtitleLabel = QLabel


def _tr_dialog(language: str, key: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


class PresetNameDialog(MessageBoxBase):
    """Модальный диалог для создания и переименования пресета."""

    def __init__(self, mode: str, old_name: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._mode = mode  # "create" | "rename"
        self._ui_language = language

        title_text = (
            _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.create.title", "Создать пресет")
            if mode == "create"
            else _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.rename.title", "Переименовать пресет")
        )
        self.titleLabel = SubtitleLabel(title_text, self.widget)

        if mode == "rename" and old_name:
            from_label = CaptionLabel(
                _tr_dialog(
                    self._ui_language,
                    "page.z2_strategy_detail.preset_dialog.rename.current_name",
                    "Текущее имя: {name}",
                    name=old_name,
                ),
                self.widget,
            )
            self.viewLayout.addWidget(self.titleLabel)
            self.viewLayout.addWidget(from_label)
        else:
            self.viewLayout.addWidget(self.titleLabel)

        name_label = BodyLabel(
            _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.name_label", "Название"),
            self.widget,
        )
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setPlaceholderText(
            _tr_dialog(
                self._ui_language,
                "page.z2_strategy_detail.preset_dialog.name_placeholder",
                "Введите название пресета...",
            )
        )
        if mode == "rename" and old_name:
            self.name_edit.setText(old_name)
        self.name_edit.returnPressed.connect(self._validate_and_accept)

        self._error_label = CaptionLabel("", self.widget)
        try:
            from qfluentwidgets import isDarkTheme as _is_dark_theme

            error_color = "#ff6b6b" if _is_dark_theme() else "#dc2626"
        except Exception:
            error_color = "#dc2626"
        self._error_label.setStyleSheet(f"color: {error_color};")
        self._error_label.hide()

        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addWidget(self._error_label)

        self.yesButton.setText(
            _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.create", "Создать")
            if mode == "create"
            else _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.rename", "Переименовать")
        )
        self.cancelButton.setText(
            _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.cancel", "Отмена")
        )
        self.widget.setMinimumWidth(360)

    def _validate_and_accept(self) -> None:
        if self.validate():
            self.accept()

    def validate(self) -> bool:
        name = self.name_edit.text().strip()
        if not name:
            self._error_label.setText(
                _tr_dialog(self._ui_language, "page.z2_strategy_detail.preset_dialog.error.empty", "Введите название пресета")
            )
            self._error_label.show()
            return False
        self._error_label.hide()
        return True

    def get_name(self) -> str:
        return self.name_edit.text().strip()
