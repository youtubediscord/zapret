from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.pages.base_page import BasePage


class BasePageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_page_scrollbar_arrow_buttons_do_not_take_tab_focus(self) -> None:
        page = BasePage("Тестовая страница")
        self.addCleanup(page.deleteLater)

        buttons = [
            child
            for child in page.findChildren(object)
            if type(child).__name__ == "ArrowButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_page_titles_expose_screen_reader_state_text(self) -> None:
        page = BasePage("Тестовая страница", "Описание тестовой страницы")
        self.addCleanup(page.deleteLater)

        section = page.add_section_title("Основные настройки", return_widget=True)

        self.assertEqual(
            page.title_label.property("screenReaderStateText"),
            "Заголовок страницы: Тестовая страница",
        )
        self.assertEqual(
            page.subtitle_label.property("screenReaderStateText"),
            "Описание страницы: Описание тестовой страницы",
        )
        self.assertEqual(
            section.property("screenReaderStateText"),
            "Раздел страницы: Основные настройки",
        )

    def test_page_title_screen_reader_text_updates_with_language(self) -> None:
        def _tr(key: str, *, language: str, default: str) -> str:
            texts = {
                ("test.title", "ru"): "Русский заголовок",
                ("test.title", "en"): "English title",
                ("test.subtitle", "ru"): "Русское описание",
                ("test.subtitle", "en"): "English description",
                ("test.section", "ru"): "Русский раздел",
                ("test.section", "en"): "English section",
            }
            return texts.get((key, language), default)

        with patch("ui.pages.base_page.tr_catalog", side_effect=_tr):
            page = BasePage(
                "Запасной заголовок",
                "Запасное описание",
                title_key="test.title",
                subtitle_key="test.subtitle",
            )
            self.addCleanup(page.deleteLater)
            section = page.add_section_title(
                "Запасной раздел",
                return_widget=True,
                text_key="test.section",
            )

            page.set_ui_language("en")

        self.assertEqual(
            page.title_label.property("screenReaderStateText"),
            "Заголовок страницы: English title",
        )
        self.assertEqual(
            page.subtitle_label.property("screenReaderStateText"),
            "Описание страницы: English description",
        )
        self.assertEqual(
            section.property("screenReaderStateText"),
            "Раздел страницы: English section",
        )


if __name__ == "__main__":
    unittest.main()
