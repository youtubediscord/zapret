from __future__ import annotations

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QIcon
import qtawesome as qta

from ui.accessibility import set_control_accessibility, set_state_text
from ui.theme import (
    get_cached_qta_pixmap,
    get_card_gradient_qss,
    get_theme_tokens,
    get_themed_qta_icon,
    get_tinted_surface_gradient_qss,
    to_qcolor,
)
from ui.animation_policy import register_managed_animation, start_managed_animation
from ui.theme_refresh import ThemeRefreshBinding
from qfluentwidgets import (
    ComboBox,
    SpinBox,
    InfoBadge,
    InfoLevel as _InfoLevel,
    SettingCard as FluentSettingCard,
    SwitchSettingCard,
    SwitchButton,
    IndicatorPosition,
    StrongBodyLabel,
    BodyLabel as _BodyLabel,
    CaptionLabel as _CaptionLabel,
)

_HAS_INFO_BADGE = InfoBadge is not None and _InfoLevel is not None


def _should_use_info_badge(info_badge_cls=InfoBadge, info_level_cls=_InfoLevel) -> bool:
    return bool(_HAS_INFO_BADGE and info_badge_cls is not None and info_level_cls is not None)


def _build_theme_refresh_key(tokens) -> tuple[str, str, str]:
    return (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.font_family_qss))


class Win11ToggleRow(FluentSettingCard):
    """Строка с toggle switch в стиле Windows 11."""

    toggled = pyqtSignal(bool)

    def __init__(self, icon_name: str, title: str, description: str = "", icon_color: str = "", parent=None):
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._icon_label = None
        self._switch_button = None
        self._accessible_title = str(title or "")
        self._accessible_description = str(description or "")

        initial_tokens = get_theme_tokens()
        FluentSettingCard.__init__(
            self,
            self._build_icon(initial_tokens),
            title,
            description or None,
            parent=parent,
        )
        try:
            self.setIconSize(18, 18)
        except Exception:
            pass
        self._icon_label = getattr(self, "iconLabel", None)
        self._title_label = getattr(self, "titleLabel", None)
        self._desc_label = getattr(self, "contentLabel", None)

        self._switch_button = SwitchButton(self)

        if self._switch_button is not None:
            try:
                self.hBoxLayout.addWidget(self._switch_button, 0, Qt.AlignmentFlag.AlignRight)
                self.hBoxLayout.addSpacing(16)
            except Exception:
                pass

        if self._switch_button is not None:
            try:
                signal = getattr(self._switch_button, "toggled", None) or getattr(
                    self._switch_button,
                    "checkedChanged",
                    None,
                )
                if signal is not None:
                    signal.connect(self._on_switch_toggled)
            except Exception:
                pass
        self._update_toggle_accessibility()
        self._theme_refresh = ThemeRefreshBinding(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        icon_label = self._icon_label
        if icon_label is None:
            return
        try:
            icon_label.setIcon(self._build_icon(theme_tokens))
        except Exception:
            try:
                color = self._resolved_icon_color(theme_tokens)
                icon_label.setPixmap(get_cached_qta_pixmap(self._icon_name, color=color, size=18))
            except Exception:
                return

    def _build_icon(self, tokens=None) -> QIcon:
        theme_tokens = tokens or get_theme_tokens()
        try:
            return get_themed_qta_icon(self._icon_name, color=self._resolved_icon_color(theme_tokens))
        except Exception:
            return QIcon()

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._refresh_icon(tokens)

    def setChecked(self, checked: bool, block_signals: bool = False):
        toggle = getattr(self, "_switch_button", None)
        if toggle is None:
            return
        next_checked = bool(checked)
        try:
            if bool(toggle.isChecked()) == next_checked:
                return
        except Exception:
            pass
        if block_signals:
            toggle.blockSignals(True)
        toggle.setChecked(next_checked)
        if block_signals:
            toggle.blockSignals(False)
        self._update_toggle_accessibility()

    def isChecked(self) -> bool:
        toggle = getattr(self, "_switch_button", None)
        if toggle is None:
            return False
        return bool(toggle.isChecked())

    def set_texts(self, title: str, description: str = "") -> None:
        next_title = str(title or "")
        next_description = str(description or "")
        text_key = (next_title, next_description)
        try:
            title_label = getattr(self, "_title_label", None)
            desc_label = getattr(self, "_desc_label", None)
            current_title = str(title_label.text() if title_label is not None else "")
            current_description = str(desc_label.text() if desc_label is not None else "")
            if (current_title, current_description) == text_key:
                self._last_win11_toggle_texts_key = text_key
                return
        except Exception:
            if getattr(self, "_last_win11_toggle_texts_key", None) == text_key:
                return
        try:
            self.setTitle(next_title)
            self.setContent(next_description)
            self._accessible_title = next_title
            self._accessible_description = next_description
            self._last_win11_toggle_texts_key = text_key
            self._update_toggle_accessibility()
        except Exception:
            pass

    def _on_switch_toggled(self, checked: bool) -> None:
        self._update_toggle_accessibility()
        self.toggled.emit(bool(checked))

    def _update_toggle_accessibility(self) -> None:
        state = "включено" if self.isChecked() else "выключено"
        title = str(self.__dict__.get("_accessible_title", "") or "").strip()
        description = str(self.__dict__.get("_accessible_description", "") or "")
        name = f"{title}, {state}".strip(", ")
        set_control_accessibility(self, name=name, description=description)
        set_state_text(self, name)
        toggle = self.__dict__.get("_switch_button")
        if toggle is not None:
            set_control_accessibility(toggle, name=name, description=description)
            set_state_text(toggle, name)


class Win11RadioOption(QWidget):
    """Радио-опция в стиле Windows 11."""

    clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        description: str,
        icon_name: str | None = None,
        icon_color: str = "",
        recommended: bool = False,
        recommended_badge: str = "рекомендуется",
        parent=None,
    ):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._selected = False
        self._hover = False
        self._recommended = recommended
        self._accessible_title = str(title or "")
        self._accessible_description = str(description or "")
        self._recommended_badge_text = str(recommended_badge or "") if recommended else ""

        self._icon_name = icon_name
        self._icon_color = icon_color
        self._icon_label: QLabel | None = None
        self._badge_label = None
        self._title_label = None
        self._desc_label = None
        self._applying_theme_styles = False
        initial_tokens = get_theme_tokens()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.radio_circle = QWidget()
        self.radio_circle.setFixedSize(20, 20)
        layout.addWidget(self.radio_circle)

        if icon_name:
            self._icon_label = QLabel()
            self._icon_label.setFixedSize(28, 28)
            layout.addWidget(self._icon_label)
            self._refresh_icon(initial_tokens)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = StrongBodyLabel(title)
        self._title_label = title_label
        title_layout.addWidget(title_label)

        if recommended:
            if _should_use_info_badge():
                self._badge_label = InfoBadge(recommended_badge, level=_InfoLevel.ATTENTION)
            else:
                self._badge_label = QLabel(recommended_badge)
                self._badge_label.setStyleSheet(
                    "QLabel { background: #0078d4; color: #fff; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; }"
                )
            title_layout.addWidget(self._badge_label)

        title_layout.addStretch()
        text_layout.addLayout(title_layout)

        desc_label = _CaptionLabel(description)
        desc_label.setWordWrap(True)
        self._desc_label = desc_label
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self._update_style(initial_tokens)
        self._update_accessibility()
        self._theme_refresh = ThemeRefreshBinding(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        if self._icon_label is None or not self._icon_name:
            return
        theme_tokens = tokens or get_theme_tokens()
        try:
                self._icon_label.setPixmap(
                    get_cached_qta_pixmap(
                        self._icon_name,
                        color=self._resolved_icon_color(theme_tokens),
                        size=24,
                    )
                )
        except Exception:
            return

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._refresh_icon(tokens)
        self._update_style(tokens)

    def setSelected(self, selected: bool):
        selected = bool(selected)
        if self._selected == selected:
            self._update_accessibility()
            return
        self._selected = selected
        self._update_style()
        self._update_accessibility()

    def isSelected(self) -> bool:
        return self._selected

    def set_texts(self, title: str, description: str, recommended_badge: str | None = None) -> None:
        next_title = str(title or "")
        next_description = str(description or "")
        next_badge = None if recommended_badge is None else str(recommended_badge or "")
        text_key = (next_title, next_description, next_badge)
        try:
            title_label = getattr(self, "_title_label", None)
            desc_label = getattr(self, "_desc_label", None)
            badge_label = getattr(self, "_badge_label", None)
            current_title = str(title_label.text() if title_label is not None else "")
            current_description = str(desc_label.text() if desc_label is not None else "")
            current_badge = None
            if next_badge is not None and badge_label is not None and hasattr(badge_label, "text"):
                current_badge = str(badge_label.text())
            if (current_title, current_description, current_badge) == text_key:
                self._last_win11_radio_texts_key = text_key
                return
        except Exception:
            if getattr(self, "_last_win11_radio_texts_key", None) == text_key:
                return
        try:
            if self._title_label is not None:
                self._title_label.setText(next_title)
            if self._desc_label is not None:
                self._desc_label.setText(next_description)
            if next_badge is not None and self._badge_label is not None and hasattr(self._badge_label, "setText"):
                self._badge_label.setText(next_badge)
            self._accessible_title = next_title
            self._accessible_description = next_description
            if next_badge is not None:
                self._recommended_badge_text = next_badge if self._recommended else ""
            self._last_win11_radio_texts_key = text_key
            self._update_accessibility()
        except Exception:
            pass

    def _update_accessibility(self) -> None:
        state = "выбрано" if self._selected else "не выбрано"
        parts = [str(self._accessible_title or "").strip(), state]
        badge = str(getattr(self, "_recommended_badge_text", "") or "").strip()
        if badge:
            parts.append(badge)
        name = ", ".join(part for part in parts if part)
        set_control_accessibility(self, name=name, description=self._accessible_description)
        set_state_text(self, name)

    def _update_style(self, tokens=None):
        if self._applying_theme_styles:
            return

        self._applying_theme_styles = True
        try:
            theme_tokens = tokens or get_theme_tokens()

            if self._selected:
                selected_bg = theme_tokens.accent_soft_bg_hover if self._hover else theme_tokens.accent_soft_bg
                bg = get_tinted_surface_gradient_qss(
                    selected_bg,
                    theme_name=theme_tokens.theme_name,
                    hover=self._hover,
                )
                border_alpha = "0.68" if self._hover else "0.60"
                border = f"rgba({theme_tokens.accent_rgb_str}, {border_alpha})"
            elif self._hover:
                bg = get_card_gradient_qss(theme_tokens.theme_name, hover=True)
                border = theme_tokens.surface_border_hover
            else:
                bg = get_card_gradient_qss(theme_tokens.theme_name)
                border = theme_tokens.surface_border

            self.setStyleSheet(
                f"""
                Win11RadioOption {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 8px;
                }}
                """
            )
        finally:
            self._applying_theme_styles = False

        self.update()

    def enterEvent(self, event):
        self._hover = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        circle_x = 12 + 10
        circle_y = self.height() // 2

        tokens = get_theme_tokens()
        accent_r, accent_g, accent_b = tokens.accent_rgb
        selected_ring = QColor(accent_r, accent_g, accent_b, 245)
        selected_dot = QColor(accent_r, accent_g, accent_b, 255)
        unselected_ring = QColor(accent_r, accent_g, accent_b, 140 if tokens.is_light else 165)

        if not selected_ring.isValid():
            selected_ring = QColor(tokens.accent_hex)
            selected_ring.setAlpha(245)
        if not selected_dot.isValid():
            selected_dot = QColor(tokens.accent_hex)
            selected_dot.setAlpha(255)
        if not unselected_ring.isValid():
            unselected_ring = QColor(tokens.accent_hex)
            unselected_ring.setAlpha(140 if tokens.is_light else 165)

        ring_color = selected_ring if self._selected else unselected_ring
        pen = painter.pen()
        pen.setColor(ring_color)
        pen.setWidth(2 if self._selected else 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle_x - 8, circle_y - 8, 16, 16)

        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(selected_dot)
            painter.drawEllipse(circle_x - 4, circle_y - 4, 8, 8)

        painter.end()


class Win11NumberRow(FluentSettingCard):
    """Строка с числовым вводом в стиле Windows 11."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str = "",
        icon_color: str = "",
        min_val: int = 0,
        max_val: int = 999,
        default_val: int = 10,
        suffix: str = "",
        parent=None,
    ):
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._icon_label = None
        self._applying_theme_styles = False
        self._accessible_title = str(title or "")
        self._accessible_description = str(description or "")
        initial_tokens = get_theme_tokens()

        super().__init__(
            self._build_icon(initial_tokens),
            title,
            description or None,
            parent=parent,
        )
        self.setIconSize(18, 18)
        self._icon_label = getattr(self, "iconLabel", None)
        self._title_label = getattr(self, "titleLabel", None)
        self._desc_label = getattr(self, "contentLabel", None)
        layout = getattr(self, "hBoxLayout", None)

        self.spinbox = SpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinbox.setFixedWidth(160)
        self.spinbox.valueChanged.connect(self._on_spinbox_value_changed)
        layout.addWidget(self.spinbox)
        layout.addSpacing(16)
        self._update_number_accessibility()
        self._theme_refresh = ThemeRefreshBinding(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        icon_label = self._icon_label
        if icon_label is None:
            return
        try:
            icon_label.setIcon(self._build_icon(theme_tokens))
        except Exception:
            try:
                icon_label.setPixmap(
                    get_cached_qta_pixmap(
                        self._icon_name,
                        color=self._resolved_icon_color(theme_tokens),
                        size=18,
                    )
                )
            except Exception:
                return

    def _build_icon(self, tokens=None) -> QIcon:
        theme_tokens = tokens or get_theme_tokens()
        try:
            return get_themed_qta_icon(self._icon_name, color=self._resolved_icon_color(theme_tokens))
        except Exception:
            return QIcon()

    def _apply_theme_styles(self, tokens=None) -> None:
        return None

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._applying_theme_styles = True
        try:
            self._refresh_icon(tokens)
        finally:
            self._applying_theme_styles = False

    def setValue(self, value: int, block_signals: bool = False):
        next_value = int(value)
        try:
            if int(self.spinbox.value()) == next_value:
                return
        except Exception:
            pass
        if block_signals:
            self.spinbox.blockSignals(True)
        self.spinbox.setValue(next_value)
        if block_signals:
            self.spinbox.blockSignals(False)
        self._update_number_accessibility()

    def value(self) -> int:
        return self.spinbox.value()

    def set_texts(self, title: str, description: str = "") -> None:
        next_title = str(title or "")
        next_description = str(description or "")
        text_key = (next_title, next_description)
        try:
            title_label = getattr(self, "_title_label", None)
            desc_label = getattr(self, "_desc_label", None)
            current_title = str(title_label.text() if title_label is not None else "")
            current_description = str(desc_label.text() if desc_label is not None else "")
            if (current_title, current_description) == text_key:
                self._last_win11_number_texts_key = text_key
                return
        except Exception:
            if getattr(self, "_last_win11_number_texts_key", None) == text_key:
                return
        try:
            self.setTitle(next_title)
            self.setContent(next_description)
            self._accessible_title = next_title
            self._accessible_description = next_description
            self._last_win11_number_texts_key = text_key
            self._update_number_accessibility()
        except Exception:
            pass

    def _on_spinbox_value_changed(self, value: int) -> None:
        self._update_number_accessibility()
        self.valueChanged.emit(int(value))

    def _update_number_accessibility(self) -> None:
        title = str(self.__dict__.get("_accessible_title", "") or "").strip()
        description = str(self.__dict__.get("_accessible_description", "") or "")
        try:
            value = self.spinbox.value()
        except Exception:
            value = ""
        name = f"{title}, значение: {value}".strip(", ")
        set_control_accessibility(self, name=name, description=description)
        set_state_text(self, name)
        spinbox = self.__dict__.get("spinbox")
        if spinbox is not None:
            set_control_accessibility(spinbox, name=name, description=description)
            set_state_text(spinbox, name)


class Win11ComboRow(FluentSettingCard):
    """Строка с выпадающим списком в стиле Windows 11."""

    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str = "",
        icon_color: str = "",
        items: list | None = None,
        parent=None,
    ):
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._title_label = None
        self._desc_label = None
        self._icon_label = None
        self._applying_theme_styles = False
        self._accessible_title = str(title or "")
        self._accessible_description = str(description or "")
        initial_tokens = get_theme_tokens()

        super().__init__(
            self._build_icon(initial_tokens),
            title,
            description or None,
            parent=parent,
        )
        self.setIconSize(18, 18)
        self._icon_label = getattr(self, "iconLabel", None)
        self._title_label = getattr(self, "titleLabel", None)
        self._desc_label = getattr(self, "contentLabel", None)
        layout = getattr(self, "hBoxLayout", None)

        self.combo = ComboBox()
        self.combo.setFixedWidth(160)

        if items:
            for text, data in items:
                self.combo.addItem(text, userData=data)

        self.combo.currentIndexChanged.connect(self._on_combo_index_changed)
        self.combo.currentTextChanged.connect(self._on_combo_text_changed)
        layout.addWidget(self.combo)
        layout.addSpacing(16)
        self._update_combo_accessibility()
        self._theme_refresh = ThemeRefreshBinding(
            self,
            self._apply_theme_refresh,
            key_builder=_build_theme_refresh_key,
        )

    def _resolved_icon_color(self, tokens=None) -> str:
        theme_tokens = tokens or get_theme_tokens()
        c = str(self._icon_color or "").strip()
        if not c:
            return theme_tokens.accent_hex
        return c

    def _refresh_icon(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        icon_label = self._icon_label
        if icon_label is None:
            return
        try:
            icon_label.setIcon(self._build_icon(theme_tokens))
        except Exception:
            try:
                icon_label.setPixmap(
                    get_cached_qta_pixmap(
                        self._icon_name,
                        color=self._resolved_icon_color(theme_tokens),
                        size=18,
                    )
                )
            except Exception:
                return

    def _build_icon(self, tokens=None) -> QIcon:
        theme_tokens = tokens or get_theme_tokens()
        try:
            return get_themed_qta_icon(self._icon_name, color=self._resolved_icon_color(theme_tokens))
        except Exception:
            return QIcon()

    def _apply_theme_styles(self, tokens=None) -> None:
        return None

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._applying_theme_styles = True
        try:
            self._refresh_icon(tokens)
        finally:
            self._applying_theme_styles = False

    def setCurrentData(self, data, block_signals: bool = False):
        index = self.combo.findData(data)
        if index < 0:
            return
        try:
            if self.combo.currentIndex() == index:
                return
        except Exception:
            pass
        if block_signals:
            self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        if block_signals:
            self.combo.blockSignals(False)
        self._update_combo_accessibility()

    def currentData(self):
        return self.combo.currentData()

    def setCurrentIndex(self, index: int, block_signals: bool = False):
        next_index = int(index)
        try:
            if self.combo.currentIndex() == next_index:
                return
        except Exception:
            pass
        if block_signals:
            self.combo.blockSignals(True)
        self.combo.setCurrentIndex(next_index)
        if block_signals:
            self.combo.blockSignals(False)
        self._update_combo_accessibility()

    def currentIndex(self) -> int:
        return self.combo.currentIndex()

    def set_texts(self, title: str, description: str = "") -> None:
        next_title = str(title or "")
        next_description = str(description or "")
        text_key = (next_title, next_description)
        try:
            title_label = getattr(self, "_title_label", None)
            desc_label = getattr(self, "_desc_label", None)
            current_title = str(title_label.text() if title_label is not None else "")
            current_description = str(desc_label.text() if desc_label is not None else "")
            if (current_title, current_description) == text_key:
                self._last_win11_combo_texts_key = text_key
                return
        except Exception:
            if getattr(self, "_last_win11_combo_texts_key", None) == text_key:
                return
        try:
            self.setTitle(next_title)
            self.setContent(next_description)
            self._accessible_title = next_title
            self._accessible_description = next_description
            self._last_win11_combo_texts_key = text_key
            self._update_combo_accessibility()
        except Exception:
            pass

    def _on_combo_index_changed(self, index: int) -> None:
        self._update_combo_accessibility()
        self.currentIndexChanged.emit(int(index))

    def _on_combo_text_changed(self, text: str) -> None:
        self._update_combo_accessibility()
        self.currentTextChanged.emit(str(text))

    def _update_combo_accessibility(self) -> None:
        title = str(self.__dict__.get("_accessible_title", "") or "").strip()
        description = str(self.__dict__.get("_accessible_description", "") or "")
        try:
            text = self.combo.currentText()
        except Exception:
            text = ""
        name = f"{title}, выбрано: {text}".strip(", ")
        set_control_accessibility(self, name=name, description=description)
        set_state_text(self, name)
        combo = self.__dict__.get("combo")
        if combo is not None:
            set_control_accessibility(combo, name=name, description=description)
            set_state_text(combo, name)


__all__ = [
    "Win11ToggleRow",
    "Win11RadioOption",
    "Win11NumberRow",
    "Win11ComboRow",
]
