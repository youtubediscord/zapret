"""Диалоги для создания и переименования пресетов Zapret 2 mode."""

from __future__ import annotations

from app.ui_texts import tr as tr_catalog
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, SubtitleLabel
from ui.fluent_dialog import MessageBoxBase
from ui.accessibility import set_control_accessibility, set_state_text


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
            _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.create.title", "Создать пресет")
            if mode == "create"
            else _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.rename.title", "Переименовать пресет")
        )
        self.titleLabel = SubtitleLabel(title_text, self.widget)
        title_description = "Диалог создания preset." if mode == "create" else "Диалог переименования preset."
        set_control_accessibility(
            self.titleLabel,
            name=f"Диалог: {title_text}",
            description=title_description,
        )
        self.current_name_label = None

        if mode == "rename" and old_name:
            from_label = CaptionLabel(
                _tr_dialog(
                    self._ui_language,
                    "page.winws2_profile_setup.preset_dialog.rename.current_name",
                    "Текущее имя: {name}",
                    name=old_name,
                ),
                self.widget,
            )
            self.current_name_label = from_label
            set_control_accessibility(
                from_label,
                name=f"Текущее имя preset: {old_name}",
                description="Это старое имя preset перед переименованием.",
            )
            self.viewLayout.addWidget(self.titleLabel)
            self.viewLayout.addWidget(from_label)
        else:
            self.viewLayout.addWidget(self.titleLabel)

        name_label = BodyLabel(
            _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.name_label", "Название"),
            self.widget,
        )
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setPlaceholderText(
            _tr_dialog(
                self._ui_language,
                "page.winws2_profile_setup.preset_dialog.name_placeholder",
                "Введите название пресета...",
            )
        )
        if mode == "rename" and old_name:
            self.name_edit.setText(old_name)
        if mode == "rename":
            description = (
                f"Текущее имя: {old_name}. Введите новое название preset."
                if old_name
                else "Введите новое название preset."
            )
            set_control_accessibility(
                self.name_edit,
                name="Новое название preset",
                description=description,
            )
        else:
            set_control_accessibility(
                self.name_edit,
                name="Название нового preset",
                description="Введите название для нового preset.",
            )
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
            _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.button.create", "Создать")
            if mode == "create"
            else _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.button.rename", "Переименовать")
        )
        self.cancelButton.setText(
            _tr_dialog(self._ui_language, "page.winws2_profile_setup.preset_dialog.button.cancel", "Отмена")
        )
        if mode == "rename":
            set_state_text(self.yesButton, "Переименовать preset")
            set_control_accessibility(
                self.yesButton,
                name="Переименовать preset",
                description="Меняет имя preset.",
            )
            set_state_text(self.cancelButton, "Отменить переименование preset")
            set_control_accessibility(
                self.cancelButton,
                name="Отменить переименование preset",
                description="Закрывает диалог без переименования preset.",
            )
        else:
            set_state_text(self.yesButton, "Создать preset")
            set_control_accessibility(
                self.yesButton,
                name="Создать preset",
                description="Создаёт новый preset.",
            )
            set_state_text(self.cancelButton, "Отменить создание preset")
            set_control_accessibility(
                self.cancelButton,
                name="Отменить создание preset",
                description="Закрывает диалог без создания preset.",
            )
        self.widget.setMinimumWidth(360)

    def _validate_and_accept(self) -> None:
        if self.validate():
            self.accept()

    def validate(self) -> bool:
        name = self.name_edit.text().strip()
        if not name:
            error_text = _tr_dialog(
                self._ui_language,
                "page.winws2_profile_setup.preset_dialog.error.empty",
                "Введите название пресета",
            )
            self._error_label.setText(error_text)
            set_state_text(self._error_label, f"Ошибка: {error_text}")
            self._error_label.show()
            return False
        self._error_label.hide()
        return True

    def get_name(self) -> str:
        return self.name_edit.text().strip()
