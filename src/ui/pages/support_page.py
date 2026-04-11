# ui/pages/support_page.py
"""Страница Поддержка - GitHub Discussions и каналы сообщества"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtWidgets import QLabel

try:
    from qfluentwidgets import (
        InfoBar,
        PushSettingCard,
        PrimaryPushSettingCard,
        SettingCardGroup,
    )
except ImportError:
    StrongBodyLabel = QLabel
    CaptionLabel = QLabel
    InfoBar = None
    PushSettingCard = None  # type: ignore[assignment]
    PrimaryPushSettingCard = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]

from ui.about_page_controller import AboutPageController
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens

from .base_page import BasePage


class SupportPage(BasePage):
    """Страница поддержки с одним основным маршрутом через GitHub Discussions."""

    def __init__(self, parent=None):
        super().__init__(
            "Поддержка",
            "GitHub Discussions и каналы сообщества",
            parent,
            title_key="page.support.title",
            subtitle_key="page.support.subtitle",
        )

        self._support_card = None
        self._support_group = None

        self._tg_card = None
        self._dc_card = None
        self._community_group = None
        self._build_ui()
        self._apply_page_theme(force=True)

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self) -> None:
        if SettingCardGroup is None or PushSettingCard is None or PrimaryPushSettingCard is None:
            raise RuntimeError("Stock qfluentwidgets setting cards недоступны для страницы поддержки")

        tokens = get_theme_tokens()

        self._support_group = SettingCardGroup(
            self._tr("page.support.section.discussions", "GitHub Discussions"),
            self.content,
        )
        self._support_card = PrimaryPushSettingCard(
            self._tr("page.support.discussions.button", "Открыть"),
            qta.icon("fa5b.github", color=tokens.accent_hex),
            self._tr("page.support.discussions.title", "GitHub Discussions")
        ,
            self._tr(
                "page.support.discussions.description",
                "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
            ),
        )
        self._support_card.clicked.connect(self._open_support_discussions)
        self._support_group.addSettingCard(self._support_card)
        self.add_widget(self._support_group)

        self.add_spacing(16)

        self._community_group = SettingCardGroup(
            self._tr("page.support.section.community", "Каналы сообщества"),
            self.content,
        )

        self._tg_card = PushSettingCard(
            self._tr("page.support.channel.open", "Открыть"),
            qta.icon("fa5b.telegram", color="#229ED9"),
            self._tr("page.support.channel.telegram.title", "Telegram"),
            self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом"),
        )
        self._tg_card.clicked.connect(self._open_telegram_support)

        self._dc_card = PushSettingCard(
            self._tr("page.support.channel.open", "Открыть"),
            qta.icon("fa5b.discord", color="#5865F2"),
            self._tr("page.support.channel.discord.title", "Discord"),
            self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение"),
        )
        self._dc_card.clicked.connect(self._open_discord)

        self._community_group.addSettingCards([self._tg_card, self._dc_card])
        self.add_widget(self._community_group)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._support_card is not None:
            try:
                self._support_card.iconLabel.setIcon(qta.icon("fa5b.github", color=tokens.accent_hex))
            except Exception:
                pass
        if self._tg_card is not None:
            try:
                self._tg_card.iconLabel.setIcon(qta.icon("fa5b.telegram", color="#229ED9"))
            except Exception:
                pass
        if self._dc_card is not None:
            try:
                self._dc_card.iconLabel.setIcon(qta.icon("fa5b.discord", color="#5865F2"))
            except Exception:
                pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._support_group is not None:
            try:
                self._support_group.titleLabel.setText(
                    self._tr("page.support.section.discussions", "GitHub Discussions")
                )
            except Exception:
                pass
        if self._support_card is not None:
            try:
                self._support_card.setTitle(
                    self._tr("page.support.discussions.title", "GitHub Discussions")
                )
                self._support_card.setContent(
                    self._tr(
                        "page.support.discussions.description",
                        "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
                    )
                )
                self._support_card.button.setText(
                    self._tr("page.support.discussions.button", "Открыть")
                )
            except Exception:
                pass

        if self._community_group is not None:
            try:
                self._community_group.titleLabel.setText(
                    self._tr("page.support.section.community", "Каналы сообщества")
                )
            except Exception:
                pass
        if self._tg_card is not None:
            try:
                self._tg_card.setTitle(self._tr("page.support.channel.telegram.title", "Telegram"))
                self._tg_card.setContent(
                    self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом")
                )
                self._tg_card.button.setText(self._tr("page.support.channel.open", "Открыть"))
            except Exception:
                pass
        if self._dc_card is not None:
            try:
                self._dc_card.setTitle(self._tr("page.support.channel.discord.title", "Discord"))
                self._dc_card.setContent(
                    self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение")
                )
                self._dc_card.button.setText(self._tr("page.support.channel.open", "Открыть"))
            except Exception:
                pass

    def _open_support_discussions(self) -> None:
        result = AboutPageController.open_support_discussions()
        if (not result.ok) and InfoBar is not None:
            InfoBar.warning(
                title=self._tr("page.support.error.title", "Ошибка"),
                content=self._tr(
                    "page.support.error.open_discussions",
                    "Не удалось открыть GitHub Discussions:\n{error}",
                ).format(error=result.message),
                parent=self.window(),
            )

    def _open_telegram_support(self) -> None:
        result = AboutPageController.open_telegram("zaprethelp")
        if (not result.ok) and InfoBar is not None:
            InfoBar.warning(
                title=self._tr("page.support.error.title", "Ошибка"),
                content=self._tr(
                    "page.support.error.open_telegram",
                    "Не удалось открыть Telegram:\n{error}",
                ).format(error=result.message),
                parent=self.window(),
            )

    def _open_discord(self) -> None:
        result = AboutPageController.open_discord("https://discord.gg/kkcBDG2uws")
        if (not result.ok) and InfoBar is not None:
            InfoBar.warning(
                title=self._tr("page.support.error.title", "Ошибка"),
                content=self._tr(
                    "page.support.error.open_discord",
                    "Не удалось открыть Discord:\n{error}",
                ).format(error=result.message),
                parent=self.window(),
            )
