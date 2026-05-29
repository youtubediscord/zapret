from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import CaptionLabel, FlowLayout, StrongBodyLabel, SubtitleLabel

from app.ui_texts import tr as tr_catalog
from presets.ui.control.top_summary_plan import build_premium_summary, build_profiles_value


class ControlTopSummaryItem(QWidget):
    clicked = pyqtSignal()

    def __init__(
        self,
        *,
        icon_name: str,
        prominent: bool = False,
        clickable: bool = False,
        initial_icon_delay_ms: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._icon_name = str(icon_name or "fa5s.circle")
        self._clickable = bool(clickable)
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(24, 24)
        self._caption_label = CaptionLabel(self)
        self._value_label = SubtitleLabel(self) if prominent else StrongBodyLabel(self)
        self._details_label = CaptionLabel(self)
        self._details_label.setWordWrap(True)
        self._details_label.setVisible(False)

        if self._clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self._caption_label)
        text_layout.addWidget(self._value_label)
        text_layout.addWidget(self._details_label)
        layout.addLayout(text_layout, 1)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._theme_refresh = None
        delay_ms = max(0, int(initial_icon_delay_ms or 0))
        self._schedule_icon_refresh(delay_ms)

    def _schedule_icon_refresh(self, delay_ms: int) -> None:
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._activate_theme_refresh)
        else:
            self._activate_theme_refresh()

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

    def _refresh_icon(self, tokens=None) -> None:
        from ui.theme import get_cached_qta_pixmap, get_theme_tokens

        theme_tokens = tokens or get_theme_tokens()
        self._icon_label.setPixmap(
            get_cached_qta_pixmap(self._icon_name, color=theme_tokens.accent_hex, size=22)
        )

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._refresh_icon(tokens)

    def _activate_theme_refresh(self) -> None:
        if self._theme_refresh is None:
            from ui.theme_refresh import ThemeRefreshBinding

            self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme_refresh)
        self._refresh_icon()


class ControlTopSummaryWidget(QWidget):
    presetClicked = pyqtSignal()
    profilesClicked = pyqtSignal()
    premiumClicked = pyqtSignal()

    def __init__(self, *, language: str, mode_value: str, initial_icon_delay_ms: int = 0, parent=None):
        super().__init__(parent)
        self._language = str(language or "ru")
        self._mode_value = str(mode_value or "")
        self._preset_value = ""
        self._profile_count: int | None = None
        self._is_premium = False
        self._premium_days: int | None = None

        self.preset_item = ControlTopSummaryItem(
            icon_name="fa5s.folder-open",
            prominent=True,
            clickable=True,
            initial_icon_delay_ms=initial_icon_delay_ms,
            parent=self,
        )
        self.profiles_item = ControlTopSummaryItem(
            icon_name="fa5s.list-ul",
            clickable=True,
            initial_icon_delay_ms=initial_icon_delay_ms,
            parent=self,
        )
        self.mode_item = ControlTopSummaryItem(
            icon_name="fa5s.shield-alt",
            initial_icon_delay_ms=initial_icon_delay_ms,
            parent=self,
        )
        self.premium_item = ControlTopSummaryItem(
            icon_name="fa5s.star",
            clickable=True,
            initial_icon_delay_ms=initial_icon_delay_ms,
            parent=self,
        )

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
