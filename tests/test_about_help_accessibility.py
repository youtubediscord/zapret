from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
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

        self.assertFalse(hasattr(widgets, "youtube_card"))
        self.assertFalse(hasattr(widgets, "youtube_playlist_card"))

        self.assertEqual(widgets.docs_group.accessibleName(), "Раздел справки: Документация")
        self.assertEqual(
            widgets.docs_group.property("screenReaderStateText"),
            "Раздел справки: Документация",
        )
        self.assertEqual(widgets.news_group.accessibleName(), "Раздел справки: Новости")
        self.assertEqual(
            widgets.news_group.property("screenReaderStateText"),
            "Раздел справки: Новости",
        )

        expected = {
            widgets.forum_card: ("Открыть вики-сайт", "Документация и инструкции"),
            widgets.info_card: ("Открыть руководство и ответы", "Руководство и ответы на вопросы"),
            widgets.folder_card: ("Открыть папку с инструкциями", "Открыть локальную папку help"),
            widgets.android_card: ("Открыть инструкцию для Android", "Открыть инструкцию на сайте"),
            widgets.github_card: ("Открыть GitHub", "Исходный код и документация"),
            widgets.telegram_card: ("Открыть Telegram канал", "Новости и обновления"),
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
                link_button = getattr(card, "linkButton", None)
                if link_button is not None:
                    self.assertEqual(link_button.accessibleName(), name)
                    self.assertEqual(link_button.property("screenReaderStateText"), name)
                    self.assertIn(description, link_button.accessibleDescription())

    def test_hyperlink_cards_can_be_opened_from_keyboard(self) -> None:
        from ui.pages.about_page_help_accessibility import set_help_card_accessibility

        card = HyperlinkCard(
            "https://example.com/help",
            "Открыть",
            FluentIcon.LINK,
            "Тестовая ссылка",
            "Описание ссылки",
        )
        self.addCleanup(card.deleteLater)
        set_help_card_accessibility(
            card,
            action_name="Открыть тестовую ссылку",
            description="Открывает тестовую ссылку.",
        )
        opened: list[bool] = []
        card.linkButton.clicked.connect(lambda: opened.append(True))

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        with patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=True):
            card.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(opened, [True])


if __name__ == "__main__":
    unittest.main()
