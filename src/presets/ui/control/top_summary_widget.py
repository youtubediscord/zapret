from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import CaptionLabel, FlowLayout, StrongBodyLabel, SubtitleLabel

from app.text_catalog import tr as tr_catalog
from presets.ui.control.top_summary_plan import build_premium_summary, build_profiles_value


class ControlTopSummaryItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, *, prominent: bool = False, clickable: bool = False, parent=None):
        super().__init__(parent)
        self._clickable = bool(clickable)
        self._caption_label = CaptionLabel(self)
        self._value_label = SubtitleLabel(self) if prominent else StrongBodyLabel(self)
        self._details_label = CaptionLabel(self)
        self._details_label.setWordWrap(True)
        self._details_label.setVisible(False)

        if self._clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._caption_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._details_label)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def set_texts(self, *, caption: str, value: str, details: str = "") -> None:
        self._caption_label.setText(str(caption or ""))
        self._caption_label.setVisible(bool(str(caption or "").strip()))
        self._value_label.setText(str(value or ""))
        self._details_label.setText(str(details or ""))
        self._details_label.setVisible(bool(str(details or "").strip()))

    def mousePressEvent(self, event):  # noqa: N802
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ControlTopSummaryWidget(QWidget):
    presetClicked = pyqtSignal()
    profilesClicked = pyqtSignal()
    premiumClicked = pyqtSignal()

    def __init__(self, *, language: str, mode_value: str, parent=None):
        super().__init__(parent)
        self._language = str(language or "ru")
        self._mode_value = str(mode_value or "")
        self._preset_value = ""
        self._profile_count: int | None = None
        self._is_premium = False
        self._premium_days: int | None = None

        self.preset_item = ControlTopSummaryItem(prominent=True, clickable=True, parent=self)
        self.profiles_item = ControlTopSummaryItem(clickable=True, parent=self)
        self.mode_item = ControlTopSummaryItem(parent=self)
        self.premium_item = ControlTopSummaryItem(clickable=True, parent=self)

        self.preset_item.clicked.connect(self.presetClicked.emit)
        self.profiles_item.clicked.connect(self.profilesClicked.emit)
        self.premium_item.clicked.connect(self.premiumClicked.emit)

        layout = FlowLayout(self, needAni=False, isTight=True)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setHorizontalSpacing(36)
        layout.setVerticalSpacing(14)
        layout.addWidget(self.preset_item)
        layout.addWidget(self.profiles_item)
        layout.addWidget(self.mode_item)
        layout.addWidget(self.premium_item)

        self.preset_item.setMinimumWidth(260)
        for item in (self.profiles_item, self.mode_item, self.premium_item):
            item.setMinimumWidth(120)

        self.retranslate()

    def set_language(self, language: str) -> None:
        self._language = str(language or "ru")
        self.retranslate()

    def set_preset(self, value: str) -> None:
        self._preset_value = str(value or "")
        self.retranslate()

    def set_profile_count(self, enabled_count: int | None) -> None:
        self._profile_count = enabled_count
        self.retranslate()

    def set_premium(self, *, is_premium: bool, days_remaining: int | None) -> None:
        self._is_premium = bool(is_premium)
        self._premium_days = days_remaining
        self.retranslate()

    def retranslate(self) -> None:
        language = self._language
        self.preset_item.set_texts(
            caption=tr_catalog("page.control.summary.preset.caption", language=language, default="Текущий preset"),
            value=self._preset_value
            or tr_catalog("page.winws2_control.preset.not_selected", language=language, default="Не выбран"),
        )
        self.profiles_item.set_texts(
            caption=tr_catalog("page.control.summary.profiles.caption", language=language, default="Профили"),
            value=build_profiles_value(self._profile_count, language=language),
        )
        self.mode_item.set_texts(
            caption=tr_catalog("page.control.summary.mode.caption", language=language, default="Текущий режим"),
            value=self._mode_value,
        )
        premium_title, premium_details = build_premium_summary(
            self._is_premium,
            self._premium_days,
            language=language,
        )
        self.premium_item.set_texts(caption="", value=premium_title, details=premium_details)
