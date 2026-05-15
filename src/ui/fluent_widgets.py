# ui/fluent_widgets.py
"""
Общие fluent-виджеты и маленькие помощники для страниц.

Страницы импортируют отсюда только готовые UI-кирпичики:
SettingsCard, ActionButton, SettingsRow, PulsingDot и похожие элементы.
"""
from PyQt6.QtCore import Qt, QSize, QEvent, QTimer, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QPushButton,
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QTransform
import qtawesome as qta

from ui.theme import get_cached_qta_pixmap, get_themed_qta_icon, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding

try:
    from qfluentwidgets import (
        CardWidget, SimpleCardWidget, HeaderCardWidget, PrimaryPushButton, PushButton,
        TransparentPushButton, BodyLabel, StrongBodyLabel, CaptionLabel,
        SubtitleLabel, TitleLabel, IndeterminateProgressBar, FluentIcon,
        ProgressBar, InfoBar, InfoBarPosition, SwitchButton, isDarkTheme, themeColor,
        LineEdit, ComboBox, CheckBox, SettingCard as FluentSettingCard,
        ToolTipFilter, ToolTipPosition, FlowLayout,
    )
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    HeaderCardWidget = QFrame  # type: ignore[assignment,misc]
    SimpleCardWidget = QFrame  # type: ignore[assignment,misc]
    FluentSettingCard = QFrame  # type: ignore[assignment,misc]
    ToolTipFilter = None    # type: ignore[assignment,misc]
    ToolTipPosition = None  # type: ignore[assignment,misc]
    FlowLayout = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Re-export native qfluentwidgets inputs so pages can import from one place
# ---------------------------------------------------------------------------
if not HAS_FLUENT:
    # Минимальные Qt-замены для среды разработки без qfluentwidgets.
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
    """Контейнер для строк настроек в общем стиле страниц."""

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


def refresh_setting_card_group_height(group):
    """Явно пересчитывает высоту Fluent `SettingCardGroup`.

    Важно: функция не ставит eventFilter и не слушает `LayoutRequest`.
    Вызывайте её только после реального изменения структуры группы:
    вставили виджет, добавили карточку, скрыли/показали дополнительную строку.
    """

    if group is None or not hasattr(group, "vBoxLayout"):
        return group

    layout = getattr(group, "vBoxLayout", None)
    if layout is None:
        return group

    try:
        layout.invalidate()
        layout.activate()
    except Exception:
        pass

    height = 0
    try:
        width = max(1, int(group.width() or 0), int(layout.sizeHint().width() or 0))
    except Exception:
        width = 1

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
        return group

    try:
        if int(group.minimumHeight()) == height and int(group.maximumHeight()) == height:
            return group
    except Exception:
        pass

    try:
        group.setFixedHeight(height)
        group.updateGeometry()
    except Exception:
        pass
    return group


def enable_setting_card_group_auto_height(group):
    """Включает явный пересчёт высоты SettingCardGroup после изменения строк."""

    return refresh_setting_card_group_height(group)


def insert_widget_into_setting_card_group(group, index: int, widget) -> None:
    """Вставляет дополнительный виджет в Fluent-группу и сразу чинит пересчёт высоты."""

    if group is None or widget is None:
        return
    layout = getattr(group, "vBoxLayout", None)
    if layout is None:
        return
    layout.insertWidget(int(index), widget)
    refresh_setting_card_group_height(group)


class QuickActionsBar(SimpleCardWidget if HAS_FLUENT else QFrame):
    """Компактная fluent-панель быстрых действий без описаний.

    Это канонический паттерн для случаев, когда на странице нужны именно
    короткие действия-кнопки, а не большие строки настроек с заголовком
    и поясняющим текстом.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if HAS_FLUENT and FlowLayout is not None:
            layout = FlowLayout(self, needAni=False, isTight=True)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setHorizontalSpacing(8)
            layout.setVerticalSpacing(8)
        else:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(8)

        self.actions_layout = layout

    def add_button(self, button: QWidget) -> QWidget:
        if button is None:
            return button
        try:
            button.setFixedHeight(32)
        except Exception:
            pass
        try:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.actions_layout.addWidget(button)
        return button

    def add_buttons(self, buttons) -> None:
        for button in buttons or ():
            self.add_button(button)


class SemanticNotice(QWidget):
    """Небольшое theme-aware предупреждение/подсказка внутри fluent-групп."""

    def __init__(self, text: str = "", *, tone: str = "warning", parent=None):
        super().__init__(parent)
        self._tone = str(tone or "warning").strip().lower() or "warning"
        self._text = str(text or "")
        self._icon_label = QLabel(self)
        self._text_label = CaptionLabel(self) if HAS_FLUENT else QLabel(self)
        self._text_label.setWordWrap(True)
        self._text_label.setText(self._text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._text_label, 1)

        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme_refresh)

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text or "")
        self._text_label.setText(self._text)

    def text(self) -> str:
        return self._text

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        try:
            from ui.theme_semantic import get_semantic_palette

            palette = get_semantic_palette(getattr(tokens, "theme_name", None))
            if self._tone == "warning":
                fg = palette.warning_soft
                bg = palette.warning_soft_bg
                icon_color = palette.warning
                border = "rgba(255, 152, 0, 0.30)"
            elif self._tone == "error":
                fg = palette.error
                bg = palette.error_soft_bg
                icon_color = palette.error
                border = palette.error_soft_border
            else:
                fg = palette.info
                bg = "rgba(95, 205, 254, 0.12)"
                icon_color = palette.info
                border = "rgba(95, 205, 254, 0.26)"
        except Exception:
            fg = "#ff9800"
            bg = "rgba(255, 152, 0, 0.12)"
            icon_color = "#ff9800"
            border = "rgba(255, 152, 0, 0.30)"

        try:
            self._icon_label.setPixmap(
                get_cached_qta_pixmap("fa5s.exclamation-triangle", color=icon_color, size=14)
            )
        except Exception:
            pass

        self._text_label.setStyleSheet(
            f"color: {fg}; background: transparent;"
        )
        self.setStyleSheet(
            f"SemanticNotice {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )


def style_semantic_caption_label(label, *, tone: str = "error") -> None:
    """Красит обычный CaptionLabel в semantic-цвет и следит за сменой темы."""

    if label is None:
        return

    resolved_tone = str(tone or "error").strip().lower() or "error"

    def _apply(tokens=None, force: bool = False) -> None:
        _ = force
        try:
            from ui.theme_semantic import get_semantic_palette

            palette = get_semantic_palette(getattr(tokens, "theme_name", None))
            if resolved_tone == "warning":
                color = palette.warning_soft
            elif resolved_tone == "info":
                color = palette.info
            else:
                color = palette.error
        except Exception:
            if resolved_tone == "warning":
                color = "#ff9800"
            elif resolved_tone == "info":
                color = "#5fcdfE"
            else:
                color = "#cf1010"

        try:
            label.setStyleSheet(f"color: {color}; background: transparent;")
        except Exception:
            pass

    _apply()
    try:
        label._semantic_caption_theme_refresh = ThemeRefreshBinding(label, _apply)  # type: ignore[attr-defined]
    except Exception:
        pass


def build_premium_badge(text: str, parent=None) -> QLabel:
    """Создаёт единый бейдж Premium без копирования inline-стилей по страницам."""

    badge = QLabel(str(text or ""), parent)
    badge.setStyleSheet(
        "color: #b45309; "
        "font-size: 10px; "
        "font-weight: bold; "
        "background: rgba(255, 193, 7, 0.15); "
        "padding: 2px 6px; "
        "border-radius: 4px;"
    )
    return badge


def build_advanced_settings_section(
    *,
    title: str,
    warning_text: str,
    parent,
    toggle_rows=None,
    action_rows=None,
):
    """Собирает единый блок «Дополнительные настройки» для fluent/fallback UI."""

    toggle_rows = [row for row in (toggle_rows or ()) if row is not None]
    action_rows = [row for row in (action_rows or ()) if row is not None]

    warning = SemanticNotice(warning_text, tone="warning", parent=parent)

    if HAS_FLUENT:
        try:
            from qfluentwidgets import SettingCardGroup
        except Exception:
            SettingCardGroup = None  # type: ignore[assignment]
    else:
        SettingCardGroup = None  # type: ignore[assignment]

    if SettingCardGroup is not None:
        group = SettingCardGroup(title, parent)
        insert_widget_into_setting_card_group(group, 1, warning)
        for row in toggle_rows:
            group.addSettingCard(row)
        for row in action_rows:
            group.addSettingCard(row)
        enable_setting_card_group_auto_height(group)
        return group, warning

    group = SettingsCard(title, parent)
    layout = QVBoxLayout()
    layout.setSpacing(6)
    layout.addWidget(warning)
    for row in toggle_rows:
        layout.addWidget(row)
    for row in action_rows:
        layout.addWidget(row)
    group.add_layout(layout)
    return group, warning


# ---------------------------------------------------------------------------
# ActionButton — non-accent PushButton (use PrimaryActionButton for accent)
# ---------------------------------------------------------------------------


def _set_qta_button_icon(button, icon_name: str | None, *, color: str, size: int = 16) -> None:
    if not icon_name:
        return
    try:
        pixmap = get_cached_qta_pixmap(icon_name, color=color, size=size)
        if pixmap.isNull():
            button.setIcon(get_themed_qta_icon(icon_name, color=color))
            return
        button.setIcon(QIcon(pixmap))
    except Exception:
        try:
            button.setIcon(get_themed_qta_icon(icon_name, color=color))
        except Exception:
            pass

class ActionButton(PushButton if HAS_FLUENT else QPushButton):
    """Non-accent action button using qfluentwidgets PushButton.

    For accent (primary) buttons, use PrimaryActionButton instead.
    Note: PushButton.__init__ takes (parent=None) only — text is set via setText().
    Subclasses (StopButton etc.) rely on this being a real class.
    """

    def __init__(self, text: str, icon_name: str | None = None, parent=None):
        super().__init__(parent)
        self.setText(text)
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
                tokens = get_theme_tokens()
                _color = tokens.icon_fg
                if _color == self._last_icon_color:
                    return
                _set_qta_button_icon(self, self._icon_name, color=_color, size=16)
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
            source = get_cached_qta_pixmap(self._icon_name, color=color, size=max(icon_w, icon_h))
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
                _set_qta_button_icon(self, icon_name, color="#ffffff", size=16)
            except Exception:
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
                icon = get_themed_qta_icon(icon_name, color=themeColor().name())
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
            self._icon_label.setPixmap(get_cached_qta_pixmap(self._icon_name, color=color, size=20))
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
