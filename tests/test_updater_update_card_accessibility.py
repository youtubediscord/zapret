from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from updater.ui.update_card import UpdateStatusCard


class UpdaterUpdateCardAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_update_status_card_has_initial_screen_reader_text(self) -> None:
        card = UpdateStatusCard(language="ru")

        self.assertEqual(
            card.accessibleName(),
            "Проверка обновлений. Нажмите для проверки доступных обновлений",
        )
        self.assertIn("текущий статус", card.accessibleDescription().lower())
        self.assertEqual(card.check_btn.accessibleName(), "Проверить обновления")
        self.assertEqual(
            card.check_btn.property("screenReaderStateText"),
            "Проверить обновления",
        )
        self.assertIn("запускает проверку", card.check_btn.accessibleDescription().lower())

    def test_update_status_card_text_labels_are_named_for_screen_reader(self) -> None:
        card = UpdateStatusCard(language="ru")

        self.assertEqual(card.title_label.accessibleName(), "Заголовок проверки обновлений: Проверка обновлений")
        self.assertEqual(
            card.subtitle_label.accessibleName(),
            "Описание проверки обновлений: Нажмите для проверки доступных обновлений",
        )

    def test_update_status_card_reports_checking_state(self) -> None:
        card = UpdateStatusCard(language="ru")

        card.start_checking()

        self.assertEqual(
            card.accessibleName(),
            "Проверка обновлений... Подождите, идёт проверка серверов",
        )
        self.assertEqual(
            card.property("screenReaderStateText"),
            "Проверка обновлений... Подождите, идёт проверка серверов",
        )
        self.assertEqual(card.check_btn.accessibleName(), "Проверка обновлений выполняется")
        self.assertEqual(
            card.check_btn.property("screenReaderStateText"),
            "Проверка обновлений выполняется",
        )
        self.assertIn("дождитесь завершения", card.check_btn.accessibleDescription().lower())

    def test_disabled_update_check_button_reports_unavailable_state(self) -> None:
        card = UpdateStatusCard(language="ru")

        card.set_check_enabled(False)

        self.assertFalse(card.check_btn.isEnabled())
        self.assertEqual(card.check_btn.accessibleName(), "Проверить обновления, недоступно")
        self.assertEqual(
            card.check_btn.property("screenReaderStateText"),
            "Проверить обновления, недоступно",
        )
        self.assertIn("сейчас недоступна", card.check_btn.accessibleDescription().lower())

        card.set_check_enabled(True)

        self.assertTrue(card.check_btn.isEnabled())
        self.assertEqual(card.check_btn.accessibleName(), "Проверить обновления")
        self.assertEqual(
            card.check_btn.property("screenReaderStateText"),
            "Проверить обновления",
        )


if __name__ == "__main__":
    unittest.main()
