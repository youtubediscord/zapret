# ui/compat_widgets.py
"""
Compatibility widgets: re-exports old custom widgets or their qfluentwidgets replacements.
All pages should import SettingsCard, ActionButton, StatusIndicator, SettingsRow, PulsingDot
from here.

New in this version:
  - PrimaryActionButton  — proper PrimaryPushButton-based accent button
  - Re-exports: SwitchButton, LineEdit, ComboBox, CheckBox, IndeterminateProgressBar
  - InfoBarHelper        — one-liner InfoBar.success/warning/error/info
"""
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent, QTimer, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QPushButton,
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QTransform

try:
    from qfluentwidgets import (
        CardWidget, SimpleCardWidget, HeaderCardWidget, PrimaryPushButton, PushButton,
        TransparentPushButton, BodyLabel, StrongBodyLabel, CaptionLabel,
        SubtitleLabel, TitleLabel, IndeterminateProgressBar, FluentIcon,
        ProgressBar, InfoBar, InfoBarPosition, SwitchButton, isDarkTheme, themeColor,
        LineEdit, ComboBox, CheckBox, SettingCard as FluentSettingCard,
        ToolTipFilter, ToolTipPosition,
    )
    HAS_FLUENT = True
    _FluentPushButton = PushButton
except ImportError:
    HAS_FLUENT = False
    HeaderCardWidget = QFrame  # type: ignore[assignment,misc]
    FluentSettingCard = QFrame  # type: ignore[assignment,misc]
    ToolTipFilter = None    # type: ignore[assignment,misc]
    ToolTipPosition = None  # type: ignore[assignment,misc]
    _FluentPushButton = QPushButton  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Re-export native qfluentwidgets inputs so pages can import from one place
# ---------------------------------------------------------------------------
if not HAS_FLUENT:
    # Fallbacks when qfluentwidgets is not installed
    from PyQt6.QtWidgets import QLineEdit as LineEdit       # type: ignore[assignment]
    from PyQt6.QtWidgets import QComboBox as ComboBox       # type: ignore[assignment]
    from PyQt6.QtWidgets import QCheckBox as CheckBox       # type: ignore[assignment]
    SwitchButton = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# set_tooltip — installs qfluentwidgets ToolTipFilter + sets tooltip text
# ---------------------------------------------------------------------------

def set_tooltip(widget, text: str, *, position=None, delay: int = 300) -> None:
    """Set a Fluent-styled tooltip on *widget*.

    Installs ``ToolTipFilter`` exactly once per widget (safe to call multiple
    times — subsequent calls only update the text). Falls back to the native
    Qt tooltip when qfluentwidgets is not available.

    Args:
        widget:   Any QWidget.
        text:     Tooltip text (empty string hides the tooltip).
        position: ``ToolTipPosition`` value; defaults to ``TOP``.
        delay:    Hover-to-show delay in milliseconds (default 300).
    """
    widget.setToolTip(text)
    if ToolTipFilter is None:
        return
    # Install only once — skip if already done for this widget.
    if getattr(widget, "_fluent_tooltip_filter", None) is None:
        pos = position if position is not None else ToolTipPosition.TOP
        f = ToolTipFilter(widget, showDelay=delay, position=pos)
        widget.installEventFilter(f)
        widget._fluent_tooltip_filter = f  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SettingsCard — wraps qfluentwidgets CardWidget (or falls back to QFrame)
# ---------------------------------------------------------------------------

class SettingsCard(QWidget if HAS_FLUENT else QFrame):
    """Card container for settings rows, matching the old SettingsCard API."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title_label = None
        self._card_root = None
        self._header_label = None
        self._content_host = None

        if HAS_FLUENT:
            outer_layout = QVBoxLayout(self)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(0)

            if title:
                card_root = HeaderCardWidget(title, self)
                content_host = QWidget(card_root)
                content_layout = QVBoxLayout(content_host)
                content_layout.setContentsMargins(0, 0, 0, 0)
                content_layout.setSpacing(12)
                try:
                    card_root.viewLayout.addWidget(content_host)
                except Exception:
                    pass
                self._header_label = getattr(card_root, "headerLabel", None)
                self._title_label = self._header_label
                self.main_layout = content_layout
                self._content_host = content_host
            else:
                card_root = CardWidget(self)
                content_layout = QVBoxLayout(card_root)
                content_layout.setContentsMargins(16, 16, 16, 16)
                content_layout.setSpacing(12)
                self.main_layout = content_layout

            self._card_root = card_root
            outer_layout.addWidget(card_root)
        else:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(16, 16, 16, 16)
            self.main_layout.setSpacing(12)

            if title:
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
                self._title_label = title_lbl
                self.main_layout.addWidget(title_lbl)

    def add_widget(self, widget: QWidget):
        self.main_layout.addWidget(widget)

    def add_layout(self, layout):
        self.main_layout.addLayout(layout)

    def set_title(self, text: str) -> None:
        try:
            if HAS_FLUENT:
                if self._title_label is None:
                    title_lbl = StrongBodyLabel(text, self)
                    self._title_label = title_lbl
                    self.main_layout.insertWidget(0, title_lbl)
                else:
                    self._title_label.setText(text)
            else:
                if self._title_label is None:
                    title_lbl = QLabel(text)
                    title_lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
                    self._title_label = title_lbl
                    self.main_layout.insertWidget(0, title_lbl)
                else:
                    self._title_label.setText(text)
        except Exception:
            pass

    def setStyleSheet(self, style: str) -> None:  # noqa: N802
        if HAS_FLUENT and self._card_root is not None:
            self._card_root.setStyleSheet(style)
            return
        super().setStyleSheet(style)

    def styleSheet(self) -> str:  # noqa: N802
        if HAS_FLUENT and self._card_root is not None:
            try:
                return self._card_root.styleSheet()
            except Exception:
                return ""
        return super().styleSheet()


class _SettingCardGroupAutoSizer(QObject):
    """Принудительно пересчитывает высоту Fluent-группы после динамических изменений.

    В qfluentwidgets `SettingCardGroup.adjustSize()` учитывает только карточки внутри
    внутреннего `cardLayout`. Если мы вручную вставляем дополнительные виджеты в
    `vBoxLayout` группы, например предупреждающий текст или строку статуса, штатный
    расчёт высоты становится заниженным. В результате следующий блок страницы может
    стартовать слишком рано и визуально «налезать» на предыдущий.
    """

    _REFRESH_EVENTS = {
        QEvent.Type.Show,
        QEvent.Type.Hide,
        QEvent.Type.Resize,
        QEvent.Type.LayoutRequest,
        QEvent.Type.FontChange,
        QEvent.Type.StyleChange,
        QEvent.Type.ContentsRectChange,
    }

    def __init__(self, group: QWidget):
        super().__init__(group)
        self._group = group
        self._refresh_pending = False
        self._watched_widget_ids: set[int] = set()
        self._watch_widget(group)
        self._watch_layout_widgets()
        self.schedule_refresh()

    def _watch_widget(self, widget) -> None:
        if widget is None:
            return
        widget_id = id(widget)
        if widget_id in self._watched_widget_ids:
            return
        self._watched_widget_ids.add(widget_id)
        try:
            widget.installEventFilter(self)
        except Exception:
            pass

    def _watch_layout_widgets(self) -> None:
        layout = getattr(self._group, "vBoxLayout", None)
        if layout is None:
            return
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                self._watch_widget(widget)

    def schedule_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self.refresh_now)

    def refresh_now(self) -> None:
        self._refresh_pending = False
        group = self._group
        if group is None:
            return

        layout = getattr(group, "vBoxLayout", None)
        if layout is None:
            return

        self._watch_layout_widgets()

        try:
            layout.invalidate()
            layout.activate()
        except Exception:
            pass

        width_candidates = [
            int(getattr(group, "width", lambda: 0)() or 0),
        ]
        try:
            width_candidates.append(int(layout.sizeHint().width()))
        except Exception:
            pass
        try:
            width_candidates.append(int(group.sizeHint().width()))
        except Exception:
            pass
        width = max(1, *width_candidates)

        height = 0
        try:
            if layout.hasHeightForWidth():
                height = int(layout.totalHeightForWidth(width))
        except Exception:
            height = 0
        if height <= 0:
            try:
                height = int(layout.sizeHint().height())
            except Exception:
                height = 0
        if height <= 0:
            return

        try:
            group.setMinimumHeight(height)
        except Exception:
            pass
        try:
            if group.height() != height:
                group.resize(max(1, group.width()), height)
        except Exception:
            pass
        try:
            group.updateGeometry()
        except Exception:
            pass

        parent = None
        try:
            parent = group.parentWidget()
        except Exception:
            parent = None
        if parent is not None:
            try:
                parent.updateGeometry()
            except Exception:
                pass

    def eventFilter(self, obj, event):  # noqa: N802
        _ = obj
        try:
            if event.type() in self._REFRESH_EVENTS:
                self._watch_layout_widgets()
                self.schedule_refresh()
        except Exception:
            pass
        return super().eventFilter(obj, event)


def enable_setting_card_group_auto_height(group):
    """Включает авто-пересчёт высоты для Fluent `SettingCardGroup`.

    Функция безопасна и для обычных fallback-виджетов: если передан не Fluent-группа,
    она просто вернёт объект без изменений.
    """

    if group is None or not hasattr(group, "vBoxLayout"):
        return group

    helper = getattr(group, "_setting_group_auto_sizer", None)
    if helper is None:
        helper = _SettingCardGroupAutoSizer(group)
        try:
            group._setting_group_auto_sizer = helper  # type: ignore[attr-defined]
        except Exception:
            pass
    else:
        try:
            helper.schedule_refresh()
        except Exception:
            pass
    return group


def insert_widget_into_setting_card_group(group, index: int, widget) -> None:
    """Вставляет дополнительный виджет в Fluent-группу и сразу чинит пересчёт высоты."""

    if group is None or widget is None:
        return
    layout = getattr(group, "vBoxLayout", None)
    if layout is None:
        return
    layout.insertWidget(int(index), widget)
    helper = enable_setting_card_group_auto_height(group)
    try:
        helper = getattr(group, "_setting_group_auto_sizer", helper)
        if helper is not None:
            helper.schedule_refresh()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ActionButton — non-accent PushButton (use PrimaryActionButton for accent)
# ---------------------------------------------------------------------------

class ActionButton(PushButton if HAS_FLUENT else QPushButton):
    """Non-accent action button using qfluentwidgets PushButton.

    For accent (primary) buttons, use PrimaryActionButton instead.
    Note: PushButton.__init__ takes (parent=None) only — text is set via setText().
    Subclasses (StopButton etc.) rely on this being a real class.
    """

    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.accent = accent
        self._icon_name = icon_name
        self._theme_refresh_scheduled = False
        self._last_icon_color = None
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon_name:
            self.setIconSize(QSize(16, 16))
            # Avoid virtual dispatch to subclass _update_style() while base __init__ runs.
            ActionButton._update_style(self)

    def _update_style(self):
        """Update icon tint when theme changes."""
        if self._icon_name:
            try:
                import qtawesome as qta
                from qfluentwidgets import isDarkTheme as _idt
                _color = "#cccccc" if _idt() else "#555555"
                if _color == self._last_icon_color:
                    return
                self.setIcon(qta.icon(self._icon_name, color=_color))
                self._last_icon_color = _color
            except Exception:
                pass

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if not self._icon_name:
                    return super().changeEvent(event)
                if not self._theme_refresh_scheduled:
                    self._theme_refresh_scheduled = True
                    QTimer.singleShot(16, self._on_debounced_theme_change)
        except Exception:
            pass
        return super().changeEvent(event)

    def _on_debounced_theme_change(self) -> None:
        try:
            self._update_style()
        finally:
            self._theme_refresh_scheduled = False


# ---------------------------------------------------------------------------
# RefreshButton — ActionButton with WinUI-style spinning animation
# ---------------------------------------------------------------------------

class RefreshButton(ActionButton):
    """Refresh / reload button with WinUI-style icon spin during loading.

    Usage:
        btn = RefreshButton()          # default "Обновить" + sync icon
        btn = RefreshButton("Обновить статус")
        btn.set_loading(True)          # start spin, disable button
        btn.set_loading(False)         # stop spin, re-enable button
    """

    def __init__(self, text: str = "Обновить", icon_name: str = "fa5s.sync-alt", parent=None):
        self._loading = False
        self._spin_angle = 0.0
        self._spin_timer = None
        super().__init__(text, icon_name, parent=parent)
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(40)  # ~25 fps
        self._spin_timer.timeout.connect(self._spin_tick)

    def set_loading(self, loading: bool) -> None:
        """Start or stop the spinning loading animation."""
        if self._loading == loading:
            return
        self._loading = loading
        self.setEnabled(not loading)
        timer = self._spin_timer
        if loading:
            self._spin_angle = 0.0
            if timer is not None:
                timer.start()
        else:
            if timer is not None:
                timer.stop()
            self._set_icon_at(0.0)

    def _spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 12) % 360  # ~1 rotation/sec
        self._set_icon_at(self._spin_angle)

    def _set_icon_at(self, angle: float) -> None:
        if not self._icon_name:
            return
        try:
            import qtawesome as qta
            from qfluentwidgets import isDarkTheme as _idt
            color = "#cccccc" if _idt() else "#555555"

            size = self.iconSize()
            icon_w = max(16, int(size.width()) or 16)
            icon_h = max(16, int(size.height()) or 16)

            # Рисуем вращение внутри фиксированного холста одного размера,
            # чтобы иконка не "плавала" по вертикали из-за меняющегося bbox.
            source = qta.icon(self._icon_name, color=color).pixmap(icon_w, icon_h)
            rotated = source.transformed(QTransform().rotate(angle), Qt.TransformationMode.SmoothTransformation)

            canvas = QPixmap(icon_w, icon_h)
            canvas.fill(Qt.GlobalColor.transparent)

            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap((icon_w - rotated.width()) // 2, (icon_h - rotated.height()) // 2, rotated)
            painter.end()

            self.setIcon(QIcon(canvas))
        except Exception:
            timer = getattr(self, "_spin_timer", None)
            if timer is not None:
                timer.stop()

    def _update_style(self) -> None:
        """Update icon tint when theme changes (only when not spinning)."""
        if not getattr(self, "_loading", False):
            self._set_icon_at(0.0)


# ---------------------------------------------------------------------------
# PrimaryActionButton — accent PrimaryPushButton (start/confirm actions)
# ---------------------------------------------------------------------------

class PrimaryActionButton(PrimaryPushButton if HAS_FLUENT else QPushButton):
    """Accent action button using qfluentwidgets PrimaryPushButton.

    Use this for primary / confirm actions (e.g. «Запустить», «Применить»).
    PrimaryPushButton.__init__ takes (parent=None) only — text is set via setText().
    """

    def __init__(self, text: str, icon_name: str | None = None, parent=None):
        super().__init__(parent)
        self.setText(text)
        self._icon_name = icon_name
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon_name:
            self.setIconSize(QSize(16, 16))
            try:
                import qtawesome as qta
                self.setIcon(qta.icon(icon_name, color="#ffffff"))
            except Exception:
                pass

    def _update_style(self):
        """No-op: qfluentwidgets handles styling."""
        pass


# ---------------------------------------------------------------------------
# SettingsRow — icon + title/description left, control right
# ---------------------------------------------------------------------------

class SettingsRow(FluentSettingCard if HAS_FLUENT else QWidget):
    """Settings row (icon + text on the left, control widget on the right)."""

    def __init__(self, icon_name: str, title: str, description: str = "", parent=None):
        self._icon_name = icon_name
        self._icon_label = None
        self._title_label = None
        self._desc_label = None
        if HAS_FLUENT:
            try:
                import qtawesome as qta
                icon = qta.icon(icon_name, color=themeColor().name())
            except Exception:
                icon = QIcon()
            super().__init__(icon, title, description or None, parent)
            self._icon_label = getattr(self, "iconLabel", None)
            self._title_label = getattr(self, "titleLabel", None)
            self._desc_label = getattr(self, "contentLabel", None)
            try:
                self.setIconSize(20, 20)
            except Exception:
                pass
            self.control_container = QHBoxLayout()
            self.control_container.setSpacing(8)
            try:
                stretch_index = max(0, self.hBoxLayout.count() - 1)
                self.hBoxLayout.insertSpacing(stretch_index, 16)
                self.hBoxLayout.insertLayout(stretch_index, self.control_container)
            except Exception:
                self.hBoxLayout.addLayout(self.control_container)
        else:
            super().__init__(parent)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 4, 0, 4)
            layout.setSpacing(12)

            # Icon
            icon_label = QLabel()
            self._icon_label = icon_label
            self._refresh_icon()
            icon_label.setFixedSize(24, 24)
            layout.addWidget(icon_label)

            # Text
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 13px; font-weight: 500;")
            self._title_label = title_label
            text_layout.addWidget(title_label)

            if description:
                desc_label = QLabel(description)
                desc_label.setStyleSheet("font-size: 11px;")
                desc_label.setWordWrap(True)
                self._desc_label = desc_label
                text_layout.addWidget(desc_label)

            layout.addLayout(text_layout, 1)

            # Control container (populated externally via set_control)
            self.control_container = QHBoxLayout()
            self.control_container.setSpacing(8)
            layout.addLayout(self.control_container)

    def _refresh_icon(self) -> None:
        if self._icon_label is None:
            return
        try:
            import qtawesome as qta
            color = themeColor().name() if HAS_FLUENT else "#5fcffe"
            self._icon_label.setPixmap(qta.icon(self._icon_name, color=color).pixmap(20, 20))
        except Exception:
            pass

    def set_control(self, widget: QWidget):
        """Adds a control widget on the right side."""
        self.control_container.addWidget(widget)

    def set_title(self, text: str) -> None:
        try:
            if HAS_FLUENT:
                self.setTitle(text)
            elif self._title_label is not None:
                self._title_label.setText(text)
        except Exception:
            pass

    def set_description(self, text: str) -> None:
        try:
            if HAS_FLUENT:
                self.setContent(text)
            elif self._desc_label is not None:
                self._desc_label.setText(text)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PulsingDot — animated status indicator dot with glow effect
# ---------------------------------------------------------------------------

class PulsingDot(QWidget):
    """Pulsing dot indicator — QTimer at 100 ms (10 FPS).

    QPropertyAnimation was intentionally avoided: it runs at the display
    refresh rate (~60 FPS), tripling paint calls vs a fixed interval timer.
    Lifecycle: timer stops when the widget is hidden and resumes on show,
    so there is zero CPU cost while the user is on a different page.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#aeb5c1")
        self._pulse_phase = 0.0
        self._is_pulsing = False

        self.setFixedSize(28, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.setInterval(100)         # 10 FPS — smooth enough, half the CPU vs 50 ms
        self._timer.timeout.connect(self._tick)

    # --- Public API -------------------------------------------------------

    def set_color(self, color: str) -> None:
        c = QColor(color)
        if c.isValid():
            self._color = c
        self.update()

    def start_pulse(self) -> None:
        if not self._is_pulsing:
            self._is_pulsing = True
            self._pulse_phase = 0.0
            if self.isVisible():
                self._timer.start()

    def stop_pulse(self) -> None:
        self._is_pulsing = False
        self._timer.stop()
        self._pulse_phase = 0.0
        self.update()

    # --- Lifecycle: stop timer when hidden, restart when shown -----------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._is_pulsing and not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()   # zero CPU while page is not visible

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            window = self.window()
            if window and window.isMinimized():
                self._timer.stop()
            elif self._is_pulsing and not self._timer.isActive():
                self._timer.start()

    # --- Animation tick ---------------------------------------------------

    def _tick(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.08) % 1.0  # ~0.8 cycles/sec at 10 FPS
        self.update()

    # --- Paint ------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        base_r = 5

        # Pulsing rings (two offset by 0.5 phase for continuous ripple)
        if self._is_pulsing:
            for phase_offset in (0.0, 0.5):
                phase = (self._pulse_phase + phase_offset) % 1.0
                opacity = max(0.0, 0.5 * (1.0 - phase))
                radius = base_r + 10 * phase
                c = QColor(self._color)
                c.setAlphaF(opacity)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c)
                r = int(radius)
                painter.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)

        # Static outer glow
        glow = QColor(self._color)
        glow.setAlphaF(0.3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            int(cx - base_r - 2), int(cy - base_r - 2),
            (base_r + 2) * 2, (base_r + 2) * 2,
        )

        # Main dot
        painter.setBrush(self._color)
        painter.drawEllipse(int(cx - base_r), int(cy - base_r), base_r * 2, base_r * 2)

        # Highlight
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawEllipse(int(cx - 2), int(cy - 3), 3, 3)


# ---------------------------------------------------------------------------
# StatusIndicator — PulsingDot + label, theme-aware status colors
# ---------------------------------------------------------------------------

class StatusIndicator(QWidget):
    """Status indicator (pulsing dot + text) with theme-aware colors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_status = "neutral"
        self._theme_refresh_scheduled = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.dot = PulsingDot()
        layout.addWidget(self.dot)

        if HAS_FLUENT:
            self.text = BodyLabel("...")
        else:
            self.text = QLabel("...")
            self.text.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.text)
        layout.addStretch()

    def set_status(self, text: str, status: str = "neutral"):
        """Sets status. status: 'running', 'success', 'stopped', 'warning', 'neutral'"""
        self.text.setText(text)
        self._current_status = status

        colors = self._get_status_colors()
        color = colors.get(status, colors["neutral"])
        self.dot.set_color(color)

        if status == "running":
            self.dot.start_pulse()
        else:
            self.dot.stop_pulse()

    def _get_status_colors(self) -> dict[str, str]:
        """Returns status->color mapping using semantic palette if available."""
        try:
            from ui.theme_semantic import get_semantic_palette
            palette = get_semantic_palette()
            return {
                "running": palette.success,
                "success": palette.success,
                "stopped": palette.error,
                "warning": palette.warning,
                "neutral": themeColor().name() if HAS_FLUENT else "#5fcffe",
            }
        except Exception:
            return {
                "running": "#52c477",
                "success": "#52c477",
                "stopped": "#e05454",
                "warning": "#e0a854",
                "neutral": "#5fcffe",
            }

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if not self._theme_refresh_scheduled:
                    self._theme_refresh_scheduled = True
                    QTimer.singleShot(0, self._on_debounced_theme_change)
        except Exception:
            pass
        return super().changeEvent(event)

    def _on_debounced_theme_change(self) -> None:
        self._theme_refresh_scheduled = False
        self.set_status(self.text.text(), self._current_status)


# ---------------------------------------------------------------------------
# InfoBarHelper — one-liner InfoBar notifications
# ---------------------------------------------------------------------------

class InfoBarHelper:
    """Convenience wrapper for qfluentwidgets InfoBar notifications."""

    @staticmethod
    def success(parent: QWidget, title: str, content: str = "", duration: int = 3000):
        if HAS_FLUENT:
            InfoBar.success(title, content, duration=duration,
                            position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def warning(parent: QWidget, title: str, content: str = "", duration: int = 4000):
        if HAS_FLUENT:
            InfoBar.warning(title, content, duration=duration,
                            position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def error(parent: QWidget, title: str, content: str = "", duration: int = 5000):
        if HAS_FLUENT:
            InfoBar.error(title, content, duration=duration,
                          position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def info(parent: QWidget, title: str, content: str = "", duration: int = 3000):
        if HAS_FLUENT:
            InfoBar.info(title, content, duration=duration,
                         position=InfoBarPosition.TOP_RIGHT, parent=parent)


class ResetActionButton(_FluentPushButton):
    """Кнопка с подтверждением через MessageBox."""

    reset_confirmed = pyqtSignal()

    def __init__(self, text: str = "Сбросить", confirm_text: str = "Подтвердить?", parent=None):
        super().__init__(parent)
        self._default_text = text
        self._confirm_text = confirm_text
        self.setText(text)
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        try:
            from qfluentwidgets import MessageBox

            box = MessageBox(self._default_text, self._confirm_text, self.window())
            if box.exec():
                self.reset_confirmed.emit()
        except Exception:
            self.reset_confirmed.emit()
