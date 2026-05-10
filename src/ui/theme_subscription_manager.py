# ui/theme_subscription_manager.py
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget

from log.log import log
from ui.window_ui_session import get_window_ui_session


class ThemeSubscriptionManager:
    """
    Миксин для отображения Premium-статуса в верхней панели окна.

    Базовый системный заголовок окна ставит ZapretFluentWindow при создании.
    Этот миксин не пересобирает заголовок целиком, а обновляет только отдельную
    Premium-метку, чтобы основной текст окна не прыгал при получении подписки.
    """

    def update_subscription_title_badge(
        self: QWidget,
        is_premium: bool = False,
        days_remaining: Optional[int] = None,
        source: str = "api",
    ) -> None:
        """Добавляет или скрывает отдельную Premium-метку в верхней панели."""
        if not is_premium:
            badge = getattr(self, "_subscription_title_badge", None)
            if badge is None:
                return
            if badge.isVisible():
                badge.hide()
                log(f"Premium-метка скрыта (source: {source})", "DEBUG")
            return

        badge = self._ensure_subscription_title_badge()
        if badge is None:
            log(f"Premium-метка не обновлена: titleBar недоступен (source: {source})", "WARNING")
            return

        badge_text = self._subscription_title_badge_text(days_remaining, source)
        if badge.text() != badge_text:
            badge.setText(badge_text)
            badge.adjustSize()
            log(f"Premium-метка обновлена: {badge_text} (source: {source})", "DEBUG")

        if not badge.isVisible():
            badge.show()
            log(f"Premium-метка показана (source: {source})", "DEBUG")

    def _subscription_title_badge_text(
        self: QWidget,
        days_remaining: Optional[int],
        source: str,
    ) -> str:
        if source == "offline":
            return "[PREMIUM - offline]"

        if days_remaining is None:
            return "[PREMIUM]"

        try:
            days = int(days_remaining)
        except (TypeError, ValueError):
            return "[PREMIUM]"

        if days > 0:
            return f"[PREMIUM - {days} дн.]"
        if days == 0:
            return "[PREMIUM - истекает сегодня]"
        return "[PREMIUM - истёк]"

    def _ensure_subscription_title_badge(self: QWidget) -> QLabel | None:
        badge = getattr(self, "_subscription_title_badge", None)
        if badge is not None:
            return badge

        title_bar = getattr(self, "titleBar", None)
        if title_bar is None:
            return None

        layout = getattr(title_bar, "hBoxLayout", None)
        if layout is None:
            return None

        badge = QLabel("", title_bar)
        badge.setObjectName("premiumTitleBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(22)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        badge.setStyleSheet(
            "color: #b45309; "
            "font-size: 10px; "
            "font-weight: 600; "
            "background: rgba(255, 193, 7, 0.16); "
            "padding: 2px 8px; "
            "border-radius: 4px;"
        )

        insert_index = self._subscription_title_badge_insert_index(layout)
        layout.insertWidget(insert_index, badge, 0, Qt.AlignmentFlag.AlignVCenter)
        badge.hide()
        self._subscription_title_badge = badge
        return badge

    def _subscription_title_badge_insert_index(self: QWidget, layout) -> int:
        title_bar = getattr(self, "titleBar", None)
        title_label = getattr(title_bar, "titleLabel", None) if title_bar is not None else None
        if title_label is not None:
            title_index = layout.indexOf(title_label)
            if title_index >= 0:
                return title_index + 1

        session = get_window_ui_session(self)
        search_widget = None if session is None else session.sidebar_search_nav_widget
        if search_widget is not None:
            search_index = layout.indexOf(search_widget)
            if search_index >= 0:
                return search_index

        return max(0, layout.count() - 1)
