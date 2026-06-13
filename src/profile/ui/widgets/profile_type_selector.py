# profile/ui/widgets/profile_type_selector.py
"""
Кнопки выбора типа профиля/трафика в списке профилей.
Поддерживает множественный выбор (не exclusive).
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import PillPushButton

from ui.accessibility import set_accessible_description, set_control_accessibility, set_state_text


def set_button_checked_if_changed(button, checked: bool) -> bool:
    value = bool(checked)
    try:
        if bool(button.isChecked()) == value:
            return False
    except Exception:
        pass
    button.setChecked(value)
    return True


class _ProfileTypeButton(PillPushButton):
    """PillPushButton с привязанным ключом типа профиля."""

    def __init__(self, label: str, profile_type: str, parent=None):
        super().__init__(parent)
        self.setText(label)
        self._profile_type = profile_type
        self.setCheckable(True)

    @property
    def profile_type(self) -> str:
        return self._profile_type

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class ProfileTypeSelector(QWidget):
    """
    Группа кнопок для выбора типа профиля/трафика в списке профилей.

    Множественный выбор (не exclusive):
    - "Все" снимает остальные типы;
    - выбор других типов снимает "Все";
    - можно комбинировать TCP + Discord и т.д.

    Signals:
        profile_types_changed(set): Эмитит set активных типов профиля.
    """

    profile_types_changed = pyqtSignal(set)

    PROFILE_TYPES = [
        ("all",     "Все"),
        ("tcp",     "TCP"),
        ("udp",     "UDP"),
        ("discord", "Discord"),
        ("voice",   "Voice"),
        ("games",   "Games"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, _ProfileTypeButton] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)
        set_control_accessibility(
            self,
            name="Фильтр типов profile",
            description=(
                "Выберите один или несколько типов, чтобы отфильтровать список profile. "
                "Между типами можно ходить стрелками вверх и вниз или влево и вправо, "
                "Enter или Пробел меняет выбор."
            ),
        )

        for profile_type, label in self.PROFILE_TYPES:
            btn = _ProfileTypeButton(label, profile_type, self)
            btn.clicked.connect(self._on_button_clicked)
            self._buttons[profile_type] = btn
            layout.addWidget(btn)

            if profile_type == "all":
                btn.setChecked(True)

        layout.addStretch()
        self._refresh_accessibility()

    def _on_button_clicked(self):
        sender = self.sender()
        if not isinstance(sender, _ProfileTypeButton):
            return

        previous_types = self.get_active_profile_types()
        clicked_key = sender.profile_type
        is_checked = sender.isChecked()

        if clicked_key == "all":
            if is_checked:
                for key, btn in self._buttons.items():
                    if key != "all":
                        set_button_checked_if_changed(btn, False)
            else:
                if not self._has_other_selected():
                    set_button_checked_if_changed(sender, True)
        else:
            if is_checked:
                set_button_checked_if_changed(self._buttons["all"], False)
            else:
                if not self._has_other_selected():
                    set_button_checked_if_changed(self._buttons["all"], True)

        self._refresh_accessibility()
        self._emit_profile_types_changed_if_needed(previous_types)

    def _has_other_selected(self) -> bool:
        for key, btn in self._buttons.items():
            if key != "all" and btn.isChecked():
                return True
        return False

    def get_active_profile_types(self) -> set:
        return {key for key, btn in self._buttons.items() if btn.isChecked()}

    def _emit_profile_types_changed_if_needed(self, previous_types: set) -> bool:
        active_types = self.get_active_profile_types()
        if active_types == set(previous_types or set()):
            return False
        self.profile_types_changed.emit(active_types)
        return True

    def set_active_profile_types(self, profile_types: set):
        self.blockSignals(True)
        for key, btn in self._buttons.items():
            set_button_checked_if_changed(btn, key in profile_types)
        if not profile_types or not self._has_other_selected():
            set_button_checked_if_changed(self._buttons["all"], True)
            for key, btn in self._buttons.items():
                if key != "all":
                    set_button_checked_if_changed(btn, False)
        self.blockSignals(False)
        refresh_accessibility = getattr(self, "_refresh_accessibility", None)
        if callable(refresh_accessibility):
            refresh_accessibility()

    def _refresh_accessibility(self) -> None:
        for _key, btn in self._buttons.items():
            label = str(btn.text() or "").strip()
            state = "выбрано" if btn.isChecked() else "не выбрано"
            set_state_text(btn, f"Тип profile: {label}, {state}")
            set_accessible_description(
                btn,
                (
                    "Фильтрует список profile. Можно выбрать несколько типов. "
                    "Стрелками вверх, вниз, влево и вправо перейдите к соседнему типу, "
                    "Enter или Пробел меняет выбор."
                ),
            )

    def reset(self):
        previous_types = self.get_active_profile_types()
        self.set_active_profile_types({"all"})
        self._emit_profile_types_changed_if_needed(previous_types)
