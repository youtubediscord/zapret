# ui/pages/support_page.py
"""Страница Поддержка - GitHub Discussions и каналы сообщества"""

from __future__ import annotations

import webbrowser

import qtawesome as qta
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

try:
    from qfluentwidgets import StrongBodyLabel, CaptionLabel, InfoBar
except ImportError:
    StrongBodyLabel = QLabel
    CaptionLabel = QLabel
    InfoBar = None

from config.urls import SUPPORT_DISCUSSIONS_URL
from log import log
from ui.compat_widgets import ActionButton, SettingsCard, SettingsRow
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

        self._support_icon_label: QLabel | None = None
        self._support_title_label: QLabel | None = None
        self._support_desc_label: QLabel | None = None
        self._support_button: ActionButton | None = None

        self._tg_row: SettingsRow | None = None
        self._tg_btn: ActionButton | None = None
        self._dc_row: SettingsRow | None = None
        self._dc_btn: ActionButton | None = None

        self.enable_deferred_ui_build()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self) -> None:
        tokens = get_theme_tokens()

        self.add_section_title(text_key="page.support.section.discussions")

        support_card = SettingsCard()
        support_layout = QHBoxLayout()
        support_layout.setSpacing(16)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(36, 36))
        icon_label.setFixedSize(44, 44)
        self._support_icon_label = icon_label
        support_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self._support_title_label = StrongBodyLabel(
            self._tr("page.support.discussions.title", "GitHub Discussions")
        )
        self._support_title_label.setProperty("tone", "primary")
        text_layout.addWidget(self._support_title_label)

        self._support_desc_label = CaptionLabel(
            self._tr(
                "page.support.discussions.description",
                "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
            )
        )
        self._support_desc_label.setWordWrap(True)
        self._support_desc_label.setProperty("tone", "muted")
        text_layout.addWidget(self._support_desc_label)

        support_layout.addLayout(text_layout, 1)

        self._support_button = ActionButton(
            self._tr("page.support.discussions.button", "Открыть"),
            "fa5s.external-link-alt",
            accent=True,
        )
        self._support_button.setProperty("noDrag", True)
        self._support_button.setFixedHeight(36)
        self._support_button.clicked.connect(self._open_support_discussions)
        support_layout.addWidget(self._support_button)

        support_card.add_layout(support_layout)
        self.add_widget(support_card)

        self.add_spacing(16)

        self.add_section_title(text_key="page.support.section.community")
        channels_card = SettingsCard()

        self._tg_row = SettingsRow(
            "fa5b.telegram",
            self._tr("page.support.channel.telegram.title", "Telegram"),
            self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом"),
        )
        self._tg_btn = ActionButton(
            self._tr("page.support.channel.open", "Открыть"),
            "fa5s.external-link-alt",
            accent=False,
        )
        self._tg_btn.setProperty("noDrag", True)
        self._tg_btn.clicked.connect(self._open_telegram_support)
        self._tg_row.set_control(self._tg_btn)
        channels_card.add_widget(self._tg_row)

        self._dc_row = SettingsRow(
            "fa5b.discord",
            self._tr("page.support.channel.discord.title", "Discord"),
            self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение"),
        )
        self._dc_btn = ActionButton(
            self._tr("page.support.channel.open", "Открыть"),
            "fa5s.external-link-alt",
            accent=False,
        )
        self._dc_btn.setProperty("noDrag", True)
        self._dc_btn.clicked.connect(self._open_discord)
        self._dc_row.set_control(self._dc_btn)
        channels_card.add_widget(self._dc_row)

        self.add_widget(channels_card)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._support_icon_label is not None:
            try:
                self._support_icon_label.setPixmap(
                    qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(36, 36)
                )
            except Exception:
                pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._support_title_label is not None:
            self._support_title_label.setText(
                self._tr("page.support.discussions.title", "GitHub Discussions")
            )
        if self._support_desc_label is not None:
            self._support_desc_label.setText(
                self._tr(
                    "page.support.discussions.description",
                    "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
                )
            )
        if self._support_button is not None:
            self._support_button.setText(self._tr("page.support.discussions.button", "Открыть"))

        if self._tg_row is not None:
            self._tg_row.set_title(self._tr("page.support.channel.telegram.title", "Telegram"))
            self._tg_row.set_description(
                self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом")
            )
        if self._tg_btn is not None:
            self._tg_btn.setText(self._tr("page.support.channel.open", "Открыть"))

        if self._dc_row is not None:
            self._dc_row.set_title(self._tr("page.support.channel.discord.title", "Discord"))
            self._dc_row.set_description(
                self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение")
            )
        if self._dc_btn is not None:
            self._dc_btn.setText(self._tr("page.support.channel.open", "Открыть"))

    def _open_support_discussions(self) -> None:
        try:
            webbrowser.open(SUPPORT_DISCUSSIONS_URL)
            log(f"Открыта поддержка GitHub Discussions: {SUPPORT_DISCUSSIONS_URL}", "INFO")
        except Exception as e:
            if InfoBar is not None:
                InfoBar.warning(
                    title=self._tr("page.support.error.title", "Ошибка"),
                    content=self._tr(
                        "page.support.error.open_discussions",
                        "Не удалось открыть GitHub Discussions:\n{error}",
                    ).format(error=e),
                    parent=self.window(),
                )

    def _open_telegram_support(self) -> None:
        try:
            from config.telegram_links import open_telegram_link

            open_telegram_link("zaprethelp")
            log("Открыт Telegram: zaprethelp", "INFO")
        except Exception as e:
            if InfoBar is not None:
                InfoBar.warning(
                    title=self._tr("page.support.error.title", "Ошибка"),
                    content=self._tr(
                        "page.support.error.open_telegram",
                        "Не удалось открыть Telegram:\n{error}",
                    ).format(error=e),
                    parent=self.window(),
                )

    def _open_discord(self) -> None:
        try:
            url = "https://discord.gg/kkcBDG2uws"
            webbrowser.open(url)
            log(f"Открыт Discord: {url}", "INFO")
        except Exception as e:
            if InfoBar is not None:
                InfoBar.warning(
                    title=self._tr("page.support.error.title", "Ошибка"),
                    content=self._tr(
                        "page.support.error.open_discord",
                        "Не удалось открыть Discord:\n{error}",
                    ).format(error=e),
                    parent=self.window(),
                )
