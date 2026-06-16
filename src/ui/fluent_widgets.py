# ui/fluent_widgets.py
"""
Общие fluent-виджеты и маленькие помощники для страниц.

Страницы импортируют отсюда только готовые UI-кирпичики:
SettingsCard, SettingsRow, PulsingDot и похожие элементы.
"""
from PyQt6.QtCore import Qt, QSize, QTimer, QObject, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QTransform
import qtawesome as qta

from ui.theme import get_cached_qta_pixmap, get_themed_qta_icon, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding
from ui.pulsing_dot import PulsingDot
from ui.accessibility import (
    set_accessible_description,
    set_control_accessibility,
    set_state_text,
)
from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, CheckBox, ComboBox, FlowLayout,
    FluentIcon, HeaderCardWidget, IndeterminateProgressBar, InfoBar,
    InfoBarPosition, LineEdit, PrimaryPushButton, ProgressBar, PushButton,
    SettingCard as FluentSettingCard, SimpleCardWidget, StrongBodyLabel,
    SubtitleLabel, SwitchButton, TitleLabel, ToolTipFilter, ToolTipPosition,
    TransparentPushButton, isDarkTheme, themeColor,
)


# ---------------------------------------------------------------------------
# set_tooltip — installs qfluentwidgets ToolTipFilter + sets tooltip text
# ---------------------------------------------------------------------------

def set_tooltip(widget, text: str, *, position=None, delay: int = 300) -> None:
    """Set a Fluent-styled tooltip on *widget*.

    Installs ``ToolTipFilter`` exactly once per widget (safe to call multiple
    times — subsequent calls only update the text).

    Args:
        widget:   Any QWidget.
        text:     Tooltip text (empty string hides the tooltip).
        position: ``ToolTipPosition`` value; defaults to ``TOP``.
        delay:    Hover-to-show delay in milliseconds (default 300).
    """
    value = str(text or "")
    try:
        if str(widget.toolTip()) != value:
            widget.setToolTip(value)
    except Exception:
        widget.setToolTip(value)
    try:
        widget_text = str(widget.text() or "").strip()
    except Exception:
        widget_text = ""
    try:
        accessible_name = str(widget.accessibleName() or "").strip()
    except Exception:
        accessible_name = ""
    if accessible_name:
        screen_reader_name = accessible_name
    elif value and not widget_text:
        screen_reader_name = value
    else:
        screen_reader_name = None
    set_control_accessibility(
        widget,
        name=screen_reader_name,
        description=value,
    )
    # Install only once — skip if already done for this widget.
    if getattr(widget, "_fluent_tooltip_filter", None) is None:
        pos = position if position is not None else ToolTipPosition.TOP
        f = ToolTipFilter(widget, showDelay=delay, position=pos)
        widget.installEventFilter(f)
        widget._fluent_tooltip_filter = f  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SettingsCard — wraps qfluentwidgets CardWidget
# ---------------------------------------------------------------------------

class SettingsCard(QWidget):
    """Контейнер для строк настроек в общем стиле страниц."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title_label = None
        self._card_root = None
        self._header_label = None
        self._content_host = None

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
        self._sync_title_accessibility(title)

    def add_widget(self, widget: QWidget):
        self.main_layout.addWidget(widget)

    def add_layout(self, layout):
        self.main_layout.addLayout(layout)

    def set_title(self, text: str) -> None:
        try:
            if self._title_label is None:
                title_lbl = StrongBodyLabel(text, self)
                self._title_label = title_lbl
                self.main_layout.insertWidget(0, title_lbl)
            else:
                self._title_label.setText(text)
            self._sync_title_accessibility(text)
        except Exception:
            pass

    def _sync_title_accessibility(self, text: str) -> None:
        value = str(text or "").strip()
        if not value:
            return
        state_text = f"Раздел настроек: {value}"
        set_state_text(self, state_text)
        if self._card_root is not None:
            set_state_text(self._card_root, state_text)
        if self._title_label is not None:
            set_state_text(self._title_label, state_text)

    def setStyleSheet(self, style: str) -> None:  # noqa: N802
        if self._card_root is not None:
            self._card_root.setStyleSheet(style)
            return
        super().setStyleSheet(style)

    def styleSheet(self) -> str:  # noqa: N802
        if self._card_root is not None:
            try:
                return self._card_root.styleSheet()
            except Exception:
                return ""
        return super().styleSheet()


class _SettingCardGroupAutoHeightFilter(QObject):
    """Пересчитывает высоту группы после изменения её строк."""

    _EVENTS = {
        QEvent.Type.ChildAdded,
        QEvent.Type.ChildRemoved,
        QEvent.Type.Show,
    }

    def __init__(self, group):
        super().__init__(group)
        self._group = group
        self._pending = False

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._group and event.type() in self._EVENTS:
            self._schedule_refresh()
        return False

    def _schedule_refresh(self) -> None:
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        self._pending = False
        refresh_setting_card_group_height(self._group)


def refresh_setting_card_group_height(group):
    """Явно пересчитывает высоту Fluent `SettingCardGroup`.

    Вызывайте её после реального изменения структуры группы:
    вставили виджет, добавили карточку, скрыли/показали дополнительную строку.
    """

    if group is None or not hasattr(group, "vBoxLayout"):
        return group

    layout = getattr(group, "vBoxLayout", None)
    if layout is None:
        return group

    _refresh_setting_card_group_card_heights(group)

    try:
        layout.invalidate()
        layout.activate()
    except Exception:
        pass

    height = _setting_card_group_layout_height(group, layout)
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


def _setting_card_group_layout_height(group, layout) -> int:
    total = 0
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue

        widget = item.widget()
        if widget is not None:
            total += _preferred_visible_widget_height(widget)
            continue

        child_layout = item.layout()
        if child_layout is not None and child_layout is getattr(group, "cardLayout", None):
            total += _setting_card_group_cards_height(group)
            continue

        try:
            total += max(0, int(item.sizeHint().height()))
        except Exception:
            pass

    return total


def _preferred_visible_widget_height(widget) -> int:
    height_candidates: list[int] = []
    try:
        height_candidates.append(int(widget.minimumSizeHint().height()))
    except Exception:
        pass
    try:
        height_candidates.append(int(widget.minimumHeight()))
    except Exception:
        pass
    try:
        if int(widget.minimumHeight()) == int(widget.maximumHeight()):
            height_candidates.append(int(widget.height()))
    except Exception:
        pass
    return max((item for item in height_candidates if item > 0), default=0)


def _setting_card_group_cards_height(group) -> int:
    card_layout = getattr(group, "cardLayout", None)
    if card_layout is None:
        return 0

    widgets = getattr(card_layout, "_ExpandLayout__widgets", None)
    if not widgets:
        return 0

    spacing = 0
    try:
        spacing = int(card_layout.spacing())
    except Exception:
        pass

    total = 0
    visible_count = 0
    for widget in list(widgets):
        if widget is None:
            continue
        try:
            if widget.isHidden():
                continue
        except Exception:
            pass

        if visible_count:
            total += spacing
        total += _preferred_visible_widget_height(widget)
        visible_count += 1

    return total


def _refresh_setting_card_group_card_heights(group) -> None:
    card_layout = getattr(group, "cardLayout", None)
    if card_layout is None:
        return

    widgets = getattr(card_layout, "_ExpandLayout__widgets", None)
    if not widgets:
        return

    for widget in list(widgets):
        if widget is None:
            continue
        try:
            if widget.isHidden():
                continue
        except Exception:
            pass

        height_candidates: list[int] = []
        try:
            height_candidates.append(int(widget.minimumHeight()))
        except Exception:
            pass
        try:
            if int(widget.minimumHeight()) == int(widget.maximumHeight()):
                height_candidates.append(int(widget.height()))
        except Exception:
            pass
        try:
            height_candidates.append(int(widget.sizeHint().height()))
        except Exception:
            pass
        try:
            height_candidates.append(int(widget.minimumSizeHint().height()))
        except Exception:
            pass

        height = max((item for item in height_candidates if item > 0), default=0)
        if height <= 0:
            continue

        try:
            if int(widget.minimumHeight()) == height and int(widget.maximumHeight()) == height:
                continue
        except Exception:
            pass

        try:
            widget.setFixedHeight(height)
            widget.updateGeometry()
        except Exception:
            pass


def enable_setting_card_group_auto_height(group):
    """Включает явный пересчёт высоты SettingCardGroup после изменения строк."""

    if group is None:
        return group

    if getattr(group, "_setting_card_group_auto_height_filter", None) is None:
        refresh_filter = _SettingCardGroupAutoHeightFilter(group)
        group.installEventFilter(refresh_filter)
        group._setting_card_group_auto_height_filter = refresh_filter  # type: ignore[attr-defined]

    return refresh_setting_card_group_height(group)


def insert_widget_into_setting_card_group(group, index: int, widget) -> None:
    """Вставляет дополнительный виджет в Fluent-группу и сразу чинит пересчёт высоты."""

    if group is None or widget is None:
        return
    layout = getattr(group, "vBoxLayout", None)
    if layout is None:
        return
    layout.insertWidget(int(index), widget)
    enable_setting_card_group_auto_height(group)


class QuickActionsBar(SimpleCardWidget):
    """Компактная fluent-панель быстрых действий без описаний.

    Это канонический паттерн для случаев, когда на странице нужны именно
    короткие действия-кнопки, а не большие строки настроек с заголовком
    и поясняющим текстом.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = FlowLayout(self, needAni=False, isTight=True)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

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
        self._refresh_minimum_height()
        return button

    def add_buttons(self, buttons) -> None:
        for button in buttons or ():
            self.add_button(button)

    def sizeHint(self):  # noqa: N802
        return self._expanded_layout_hint(super().sizeHint())

    def minimumSizeHint(self):  # noqa: N802
        return self._expanded_layout_hint(super().minimumSizeHint())

    def _expanded_layout_hint(self, fallback: QSize) -> QSize:
        try:
            layout_hint = self.actions_layout.sizeHint()
            layout_minimum = self.actions_layout.minimumSize()
            width = max(int(fallback.width()), int(layout_hint.width()), int(layout_minimum.width()))
            height = max(int(fallback.height()), int(layout_hint.height()), int(layout_minimum.height()))
            return QSize(width, height)
        except Exception:
            return fallback

    def _refresh_minimum_height(self) -> None:
        try:
            minimum = int(self.actions_layout.minimumSize().height())
            if minimum > 0:
                self.setMinimumHeight(minimum)
        except Exception:
            pass


class SemanticNotice(QWidget):
    """Небольшое theme-aware предупреждение/подсказка внутри fluent-групп."""

    def __init__(self, text: str = "", *, tone: str = "warning", parent=None):
        super().__init__(parent)
        self._tone = str(tone or "warning").strip().lower() or "warning"
        self._text = str(text or "")
        self._icon_label = QLabel(self)
        self._text_label = CaptionLabel(self)
        self._text_label.setWordWrap(True)
        self._text_label.setText(self._text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._text_label, 1)

        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme_refresh)
        self._sync_accessibility()

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text or "")
        self._text_label.setText(self._text)
        self._sync_accessibility()

    def text(self) -> str:
        return self._text

    def _sync_accessibility(self) -> None:
        text = " ".join(str(self._text or "").strip().split())
        if not text:
            return
        prefix_by_tone = {
            "error": "Ошибка",
            "info": "Информация",
            "warning": "Предупреждение",
        }
        prefix = prefix_by_tone.get(str(self._tone or "").strip().lower(), "Предупреждение")
        state_text = f"{prefix}: {text}"
        set_state_text(self, state_text)
        set_state_text(self._text_label, state_text)

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

    badge_text = str(text or "")
    badge = QLabel(badge_text, parent)
    badge.setStyleSheet(
        "color: #b45309; "
        "font-size: 10px; "
        "font-weight: bold; "
        "background: rgba(255, 193, 7, 0.15); "
        "padding: 2px 6px; "
        "border-radius: 4px;"
    )
    clean_text = " ".join(badge_text.strip().split())
    if clean_text:
        set_state_text(badge, f"Метка Premium: {clean_text}")
    return badge


def build_additional_settings_section(
    *,
    title: str,
    warning_text: str,
    parent,
    toggle_rows=None,
    action_rows=None,
):
    """Собирает единый блок «Дополнительные настройки» для Fluent UI."""

    toggle_rows = [row for row in (toggle_rows or ()) if row is not None]
    action_rows = [row for row in (action_rows or ()) if row is not None]

    warning = SemanticNotice(warning_text, tone="warning", parent=parent)

    from qfluentwidgets import SettingCardGroup

    group = SettingCardGroup(title, parent)
    insert_widget_into_setting_card_group(group, 1, warning)
    for row in toggle_rows:
        group.addSettingCard(row)
    for row in action_rows:
        group.addSettingCard(row)
    enable_setting_card_group_auto_height(group)
    return group, warning


# ---------------------------------------------------------------------------
# RefreshButton — PushButton with WinUI-style spinning animation
# ---------------------------------------------------------------------------

class RefreshButton(PushButton):
    """Refresh / reload button with WinUI-style icon spin during loading.

    Usage:
        btn = RefreshButton()          # default "Обновить" + FluentIcon.SYNC
        btn = RefreshButton("Обновить статус")
        btn.set_loading(True)          # start spin, disable button
        btn.set_loading(False)         # stop spin, re-enable button
    """

    def __init__(self, text: str = "Обновить", icon=FluentIcon.SYNC, parent=None):
        self._loading = False
        self._spin_angle = 0.0
        self._spin_timer = None
        self._base_icon = icon
        PushButton.__init__(self, parent=parent)
        self.setText(text)
        self.setIcon(icon)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(40)  # ~25 fps
        self._spin_timer.timeout.connect(self._spin_tick)
        self._update_accessibility()

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
            self.setIcon(self._base_icon)
        self._update_accessibility()

    def _update_accessibility(self) -> None:
        base_text = " ".join(str(self.text() or "Обновить").strip().split()) or "Обновить"
        if self._loading:
            state_text = f"{base_text}, выполняется"
            description = "Обновление уже запущено, дождитесь завершения."
        else:
            state_text = base_text
            description = "Запускает обновление."
        set_control_accessibility(self, name=state_text, description=description)
        set_state_text(self, state_text)

    def _spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 12) % 360  # ~1 rotation/sec
        self._set_icon_at(self._spin_angle)

    def _set_icon_at(self, angle: float) -> None:
        try:
            size = self.iconSize()
            icon_w = max(16, int(size.width()) or 16)
            icon_h = max(16, int(size.height()) or 16)

            source = self.icon().pixmap(max(icon_w, icon_h), max(icon_w, icon_h))
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


# ---------------------------------------------------------------------------
# SettingsRow — icon + title/description left, control right
# ---------------------------------------------------------------------------

class SettingsRow(FluentSettingCard):
    """Settings row (icon + text on the left, control widget on the right)."""

    def __init__(self, icon_name: str, title: str, description: str = "", parent=None):
        self._icon_name = icon_name
        self._accessible_title = str(title or "")
        self._accessible_description = str(description or "")
        self._icon_label = None
        self._title_label = None
        self._desc_label = None
        try:
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
        self._sync_text_accessibility()

    def _refresh_icon(self) -> None:
        if self._icon_label is None:
            return
        try:
            color = themeColor().name()
            self._icon_label.setPixmap(get_cached_qta_pixmap(self._icon_name, color=color, size=20))
        except Exception:
            pass

    def set_control(self, widget: QWidget):
        """Adds a control widget on the right side."""
        self.control_container.addWidget(widget)

    def set_title(self, text: str) -> None:
        try:
            self.setTitle(text)
            self._accessible_title = str(text or "")
            self._sync_text_accessibility()
        except Exception:
            pass

    def set_description(self, text: str) -> None:
        try:
            self.setContent(text)
            self._accessible_description = str(text or "")
            self._sync_text_accessibility()
        except Exception:
            pass

    def _sync_text_accessibility(self) -> None:
        title = str(self._accessible_title or "").strip()
        description = str(self._accessible_description or "").strip()
        if not title and not description:
            return
        state_text = f"Настройка: {title}" if title else "Настройка"
        if description:
            state_text = f"{state_text}. {description}"
        set_state_text(self, state_text)
        if description:
            set_accessible_description(self, description)
        if self._title_label is not None and title:
            set_state_text(self._title_label, f"Настройка: {title}")
        if self._desc_label is not None and description:
            set_state_text(self._desc_label, f"Описание настройки: {description}")


# ---------------------------------------------------------------------------
# InfoBarHelper — one-liner InfoBar notifications
# ---------------------------------------------------------------------------

class InfoBarHelper:
    """Convenience wrapper for qfluentwidgets InfoBar notifications."""

    @staticmethod
    def success(parent: QWidget, title: str, content: str = "", duration: int = 3000):
        InfoBar.success(title, content, duration=duration,
                        position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def warning(parent: QWidget, title: str, content: str = "", duration: int = 4000):
        InfoBar.warning(title, content, duration=duration,
                        position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def error(parent: QWidget, title: str, content: str = "", duration: int = 5000):
        InfoBar.error(title, content, duration=duration,
                      position=InfoBarPosition.TOP_RIGHT, parent=parent)

    @staticmethod
    def info(parent: QWidget, title: str, content: str = "", duration: int = 3000):
        InfoBar.info(title, content, duration=duration,
                     position=InfoBarPosition.TOP_RIGHT, parent=parent)
