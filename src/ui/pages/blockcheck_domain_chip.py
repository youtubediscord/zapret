"""Domain chip widget for Blockcheck page."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout

from qfluentwidgets import CaptionLabel, PushButton, isDarkTheme


class DomainChip(QFrame):
    """Small removable domain tag."""

    removed = pyqtSignal(str)

    def __init__(self, domain: str, parent=None):
        super().__init__(parent)
        self._domain = domain
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)

        label = CaptionLabel(domain)
        layout.addWidget(label)

        close_btn = PushButton()
        close_btn.setText("\u2715")
        close_btn.setFixedSize(20, 20)
        try:
            close_btn.setFlat(True)
        except (AttributeError, TypeError):
            pass
        close_btn.clicked.connect(lambda: self.removed.emit(self._domain))
        layout.addWidget(close_btn)

        self._apply_chip_style()

    def _apply_chip_style(self):
        dark = isDarkTheme()
        bg = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.05)"
        border = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.08)"
        self.setStyleSheet(
            f"DomainChip {{ background: {bg}; border: 1px solid {border}; "
            f"border-radius: 14px; }}"
        )
