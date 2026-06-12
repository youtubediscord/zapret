from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import QApplication, QWidget


class CustomDnsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_adds_edits_and_deletes_custom_dns_entries(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        dialog.nameEdit.setText("Мой DNS")
        dialog.primaryEdit.setText("8.8.8.8")
        dialog.secondaryEdit.setText("1.1.1.1")

        self.assertTrue(dialog.save_current())
        self.assertEqual(len(dialog.servers()), 1)
        self.assertEqual(dialog.servers()[0]["name"], "Мой DNS")
        self.assertEqual(dialog.servers()[0]["ipv4"], ["8.8.8.8", "1.1.1.1"])

        dialog.nameEdit.setText("Рабочий DNS")
        dialog.primaryEdit.setText("9.9.9.9")
        dialog.secondaryEdit.setText("")

        self.assertTrue(dialog.save_current())
        self.assertEqual(dialog.servers()[0]["name"], "Рабочий DNS")
        self.assertEqual(dialog.servers()[0]["ipv4"], ["9.9.9.9"])

        self.assertTrue(dialog.delete_current())
        self.assertEqual(dialog.servers(), [])

    def test_dialog_requires_name_and_primary_dns(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        self.assertFalse(dialog.save_current())
        self.assertIn("название", dialog.warningLabel.text().lower())

        dialog.nameEdit.setText("Мой DNS")

        self.assertFalse(dialog.save_current())
        self.assertIn("основной DNS", dialog.warningLabel.text())

    def test_empty_custom_dns_list_does_not_show_blank_panel(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        self.assertTrue(dialog.serversList.isHidden())

        dialog.nameEdit.setText("Мой DNS")
        dialog.primaryEdit.setText("8.8.8.8")

        self.assertTrue(dialog.save_current())
        self.assertFalse(dialog.serversList.isHidden())

    def test_done_saves_typed_custom_dns_before_closing(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        dialog.nameEdit.setText("Мой DNS")
        dialog.primaryEdit.setText("8.8.8.8")

        self.assertTrue(dialog.validate())
        self.assertEqual(
            [(server["name"], server["ipv4"]) for server in dialog.servers()],
            [("Мой DNS", ["8.8.8.8"])],
        )

    def test_primary_action_adds_new_dns_and_requires_fields(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        self.assertEqual(dialog.yesButton.text(), "Добавить")
        self.assertFalse(dialog.validate())
        self.assertIn("название", dialog.warningLabel.text().lower())

    def test_existing_dns_shows_save_and_delete_actions(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(
            parent,
            servers=[
                {"id": "cloudflare", "name": "Cloudflare", "ipv4": ["1.1.1.1"], "ipv6": []},
            ],
        )

        self.assertEqual(dialog.yesButton.text(), "Добавить")
        self.assertTrue(dialog.deleteButton.isHidden())

        dialog.serversList.setCurrentRow(0)

        self.assertEqual(dialog.yesButton.text(), "Сохранить")
        self.assertFalse(dialog.deleteButton.isHidden())

    def test_dialog_has_no_separate_add_button(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        self.assertFalse(hasattr(dialog, "saveButton"))

    def test_dialog_rejects_invalid_ipv4_addresses(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(parent, servers=[])

        dialog.nameEdit.setText("Мой DNS")
        dialog.primaryEdit.setText("bad")

        self.assertFalse(dialog.save_current())
        self.assertIn("IPv4", dialog.warningLabel.text())

        dialog.primaryEdit.setText("8.8.8.8")
        dialog.secondaryEdit.setText("bad")

        self.assertFalse(dialog.save_current())
        self.assertIn("IPv4", dialog.warningLabel.text())

    def test_dialog_dns_list_reads_current_row_and_accepts_keyboard_selection(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(
            parent,
            servers=[
                {"id": "cloudflare", "name": "Cloudflare", "ipv4": ["1.1.1.1", "1.0.0.1"], "ipv6": []},
            ],
        )

        self.assertIsNone(dialog.serversList.currentItem())

        QApplication.sendEvent(
            dialog.serversList,
            QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason),
        )

        self.assertEqual(dialog.serversList.currentRow(), 0)
        self.assertEqual(
            dialog.serversList.property("screenReaderStateText"),
            "Список своих DNS: Cloudflare, DNS 1.1.1.1, 1.0.0.1. "
            "Нажмите Enter или Пробел, чтобы выбрать DNS для изменения.",
        )

        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(dialog.serversList, event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(dialog.nameEdit.text(), "Cloudflare")


if __name__ == "__main__":
    unittest.main()
