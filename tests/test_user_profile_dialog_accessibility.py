import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from profile.ui.user_profile_dialog import CreateUserProfileDialog


class UserProfileDialogAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_controls_are_named_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, protocol="udp")
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.nameEdit.accessibleName(), "Название пользовательского profile")
        self.assertIn("Например YouTube или Discord", dialog.nameEdit.accessibleDescription())
        self.assertEqual(dialog.protocolCombo.accessibleName(), "Тип пользовательского profile, выбрано: UDP")
        self.assertEqual(
            dialog.protocolCombo.property("screenReaderStateText"),
            "Тип пользовательского profile, выбрано: UDP",
        )
        self.assertIn("TCP, UDP или L7", dialog.protocolCombo.accessibleDescription())
        self.assertEqual(dialog.portsEdit.accessibleName(), "Порты или L7 для пользовательского profile")
        self.assertIn("Например 80,443 или stun,discord", dialog.portsEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Добавить пользовательский profile")
        self.assertIn("Создаёт profile", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить создание пользовательского profile")

    def test_protocol_accessible_name_updates_after_keyboard_selection(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, protocol="tcp")
        self.addCleanup(dialog.deleteLater)

        dialog.protocolCombo.setCurrentIndex(2)

        self.assertEqual(dialog.protocolCombo.accessibleName(), "Тип пользовательского profile, выбрано: L7")
        self.assertEqual(
            dialog.protocolCombo.property("screenReaderStateText"),
            "Тип пользовательского profile, выбрано: L7",
        )

    def test_protocol_combo_menu_items_are_named_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, protocol="udp")
        self.addCleanup(dialog.deleteLater)
        create_menu = getattr(dialog.protocolCombo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Тип пользовательского profile: TCP, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Тип пользовательского profile: UDP, выбран",
        )

    def test_validation_warning_has_text_state_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog.validate())

        self.assertEqual(dialog.warningLabel.accessibleName(), "Ошибка: Введите название profile.")
        self.assertEqual(dialog.warningLabel.property("screenReaderStateText"), "Ошибка: Введите название profile.")


if __name__ == "__main__":
    unittest.main()
