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

        playlist_card = getattr(widgets, "youtube_playlist_card", None)
        self.assertIsNotNone(playlist_card)

        expected = {
            widgets.forum_card: ("Открыть сайт-форум для новичков", "Авторизация через Telegram-бота"),
            widgets.info_card: ("Открыть руководство и ответы", "Руководство и ответы на вопросы"),
            widgets.folder_card: ("Открыть папку с инструкциями", "Открыть локальную папку help"),
            widgets.android_card: ("Открыть инструкцию для Android", "Открыть инструкцию на сайте"),
            widgets.github_card: ("Открыть GitHub", "Исходный код и документация"),
            widgets.telegram_card: ("Открыть Telegram канал", "Новости и обновления"),
            widgets.youtube_card: ("Открыть курс и гайд по Zapret 2", "Видео по настройке и пониманию Zapret 2"),
            playlist_card: ("Открыть плейлист курса по Zapret 2", "Все видео курса одним списком"),
            widgets.mastodon_card: ("Открыть Mastodon профиль", "Новости в Fediverse"),
            widgets.bastyon_card: ("Открыть Bastyon профиль", "Новости в Bastyon"),
        }
        for card, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(card.accessibleName(), name)
                self.assertEqual(card.property("screenReaderStateText"), name)
                self.assertIn(description, card.accessibleDescription())
                button = getattr(card, "button", None)
                if button is not None:
                    self.assertEqual(button.accessibleName(), name)
                    self.assertEqual(button.property("screenReaderStateText"), name)
                    self.assertIn(description, button.accessibleDescription())

        self.assertEqual(
            bytes(widgets.youtube_card.linkButton.getUrl().toEncoded()).decode("ascii"),
            "https://www.youtube.com/@%D0%9F%D1%80%D0%B8%D0%B2%D0%B0%D1%82%D0%BD%D0%BE%D1%81%D1%82%D1%8C/videos",
        )
        self.assertEqual(
            playlist_card.linkButton.getUrl().toString(),
            "https://www.youtube.com/playlist?list=PLa6yzOvgEWW0F1PL0D8pOPI8lD_rfLL1s",
        )


if __name__ == "__main__":
    unittest.main()
