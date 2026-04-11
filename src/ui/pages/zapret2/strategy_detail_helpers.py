"""Вспомогательные UI- и args-хелперы для страницы деталей стратегии Z2."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

try:
    from qfluentwidgets import TogglePushButton
except ImportError:
    TogglePushButton = QPushButton


def extract_desync_technique_from_arg(line: str) -> str | None:
    """Извлекает имя desync-техники из одной строки аргумента."""
    source = (line or "").strip()
    match = re.match(r"^--(?:lua-desync|dpi-desync)=([a-zA-Z0-9_-]+)", source)
    if not match:
        return None
    return match.group(1).strip().lower() or None


def map_desync_technique_to_tcp_phase(technique: str) -> str | None:
    """Сопоставляет desync-технику одной из внутренних TCP phase вкладок."""
    normalized = (technique or "").strip().lower()
    if not normalized:
        return None
    if normalized == "pass":
        return "multisplit"
    if normalized == "fake":
        return "fake"
    if normalized in ("multisplit", "fakedsplit", "hostfakesplit"):
        return "multisplit"
    if normalized in ("multidisorder", "fakeddisorder"):
        return "multidisorder"
    if normalized == "multidisorder_legacy":
        return "multidisorder_legacy"
    if normalized == "tcpseg":
        return "tcpseg"
    if normalized == "oob":
        return "oob"
    return "other"


def normalize_args_text(text: str) -> str:
    """Нормализует текст args для точного сравнения без потери порядка строк."""
    if not text:
        return ""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    return "\n".join(lines).strip()


class TTLButtonSelector(QWidget):
    """Селектор числового значения через компактный ряд кнопок."""

    value_changed = pyqtSignal(int)

    def __init__(self, values: list[int], labels: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._values = values
        self._labels = labels or [str(value) for value in values]
        self._current_value = values[0]
        self._buttons: list[tuple[object, int]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for value, label in zip(self._values, self._labels):
            button = TogglePushButton(self)
            button.setText(label)
            button.setFixedSize(36, 24)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, current_value=value: self._select(current_value))
            self._buttons.append((button, value))
            layout.addWidget(button)

        layout.addStretch()
        self._sync_checked_states()

    def _select(self, value: int) -> None:
        if value != self._current_value:
            self._current_value = value
            self._sync_checked_states()
            self.value_changed.emit(value)

    def _sync_checked_states(self) -> None:
        for button, value in self._buttons:
            button.setChecked(value == self._current_value)

    def setValue(self, value: int, block_signals: bool = False) -> None:
        if value in self._values:
            if block_signals:
                self.blockSignals(True)
            self._current_value = value
            self._sync_checked_states()
            if block_signals:
                self.blockSignals(False)

    def value(self) -> int:
        return self._current_value
