from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, HyperlinkCard, PushSettingCard, SettingCardGroup

from ui.pages.about_page_help_build import build_about_page_help_content
from ui.theme import get_theme_tokens


class AboutHelpAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_help_cards_have_screen_reader_text(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)

        widgets = build_about_page_help_content(
            layout,
            tr_fn=lambda _key, default: default,
            tokens=get_theme_tokens(),
            content_parent=parent,
            make_section_label=lambda text: QWidget(),
            hyperlink_card_cls=HyperlinkCard,
            push_setting_card_cls=PushSettingCard,
            setting_card_group_cls=SettingCardGroup,
            fluent_icon=FluentIcon,
            on_open_forum=lambda: None,
            on_open_help_folder=lambda: None,
            on_open_telegram_news=lambda: None,
        )

        expected = {
            widgets.forum_card: ("Открыть сайт-форум для новичков", "Авторизация через Telegram-бота"),
            widgets.info_card: ("Открыть руководство и ответы", "Руководство и ответы на вопросы"),
            widgets.folder_card: ("Открыть папку с инструкциями", "Открыть локальную папку help"),
            widgets.android_card: ("Открыть инструкцию для Android", "Открыть инструкцию на сайте"),
            widgets.github_card: ("Открыть GitHub", "Исходный код и документация"),
            widgets.telegram_card: ("Открыть Telegram канал", "Новости и обновления"),
            widgets.youtube_card: ("Открыть YouTube канал", "Видео и обновления"),
            widgets.mastodon_card: ("Открыть Mastodon профиль", "Новости в Fediverse"),
            widgets.bastyon_card: ("Открыть Bastyon профиль", "Новости в Bastyon"),
        }
        for card, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(card.accessibleName(), name)
                self.assertIn(description, card.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
