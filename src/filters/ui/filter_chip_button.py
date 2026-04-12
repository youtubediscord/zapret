# filters/ui/filter_chip_button.py
"""
Chip-кнопки фильтрации стратегий — используют PillPushButton из qfluentwidgets.
Поддерживает множественный выбор (не exclusive).
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal

try:
    from qfluentwidgets import PillPushButton
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QPushButton as PillPushButton  # type: ignore[assignment]
    _HAS_FLUENT = False


class _FilterBtn(PillPushButton):
    """PillPushButton с привязанным filter_key."""

    def __init__(self, label: str, filter_key: str, parent=None):
        super().__init__(parent)
        self.setText(label)
        self._filter_key = filter_key
        self.setCheckable(True)

    @property
    def filter_key(self) -> str:
        return self._filter_key


class FilterButtonGroup(QWidget):
    """
    Группа pill-кнопок для фильтрации стратегий.

    Множественный выбор (не exclusive):
    - "Все" снимает остальные фильтры
    - Выбор других фильтров снимает "Все"
    - Можно комбинировать TCP + Discord и т.д.

    Signals:
        filters_changed(set): Эмитит set активных filter_key
    """

    filters_changed = pyqtSignal(set)

    FILTERS_CONFIG = [
        ("all",     "Все"),
        ("tcp",     "TCP"),
        ("udp",     "UDP"),
        ("discord", "Discord"),
        ("voice",   "Voice"),
        ("games",   "Games"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, _FilterBtn] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        for filter_key, label in self.FILTERS_CONFIG:
            btn = _FilterBtn(label, filter_key, self)
            btn.clicked.connect(self._on_button_clicked)
            self._buttons[filter_key] = btn
            layout.addWidget(btn)

            if filter_key == "all":
                btn.setChecked(True)

        layout.addStretch()

    def _on_button_clicked(self):
        sender = self.sender()
        if not isinstance(sender, _FilterBtn):
            return

        clicked_key = sender.filter_key
        is_checked = sender.isChecked()

        if clicked_key == "all":
            if is_checked:
                for key, btn in self._buttons.items():
                    if key != "all":
                        btn.setChecked(False)
            else:
                if not self._has_other_selected():
                    sender.setChecked(True)
        else:
            if is_checked:
                self._buttons["all"].setChecked(False)
            else:
                if not self._has_other_selected():
                    self._buttons["all"].setChecked(True)

        self.filters_changed.emit(self.get_active_filters())

    def _has_other_selected(self) -> bool:
        for key, btn in self._buttons.items():
            if key != "all" and btn.isChecked():
                return True
        return False

    def get_active_filters(self) -> set:
        return {key for key, btn in self._buttons.items() if btn.isChecked()}

    def set_active_filters(self, filters: set):
        self.blockSignals(True)
        for key, btn in self._buttons.items():
            btn.setChecked(key in filters)
        if not filters or not self._has_other_selected():
            self._buttons["all"].setChecked(True)
            for key, btn in self._buttons.items():
                if key != "all":
                    btn.setChecked(False)
        self.blockSignals(False)

    def reset(self):
        self.set_active_filters({"all"})
        self.filters_changed.emit({"all"})
