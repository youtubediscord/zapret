from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from ui.pages.about_page_kvn_build import build_about_page_kvn_content
from ui.theme import get_theme_tokens


class AboutKvnAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_kvn_link_cards_have_screen_reader_text(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)

        widgets = build_about_page_kvn_content(
            layout,
            tokens=get_theme_tokens(),
            content_parent=parent,
            on_open_kvn_channel=lambda: None,
            on_open_kvn_bot=lambda: None,
            on_open_kvn_bypass=lambda: None,
            on_open_kvn_github=lambda: None,
        )

        self.assertEqual(widgets.features_group.accessibleName(), "Раздел Zapret KVN: Возможности")
        self.assertEqual(
            widgets.features_group.property("screenReaderStateText"),
            "Раздел Zapret KVN: Возможности",
        )
        self.assertEqual(widgets.links_group.accessibleName(), "Раздел Zapret KVN: Ссылки")
        self.assertEqual(
            widgets.links_group.property("screenReaderStateText"),
            "Раздел Zapret KVN: Ссылки",
        )

        expected = {
            widgets.tg_card: ("Открыть канал Zapret KVN", "Новости и обновления"),
            widgets.bot_card: ("Купить подписку Zapret KVN", "Оформление через Telegram-бота"),
            widgets.bypass_card: ("Открыть канал BypassBlock", "Второй канал с новостями"),
            widgets.gh_card: ("Открыть исходный код Zapret KVN", "GitHub репозиторий Zapret KVN"),
        }
        for card, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(card.accessibleName(), name)
                self.assertEqual(card.property("screenReaderStateText"), name)
                self.assertIn(description, card.accessibleDescription())
                self.assertEqual(card.button.accessibleName(), name)
                self.assertEqual(card.button.property("screenReaderStateText"), name)
                self.assertIn(description, card.button.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
