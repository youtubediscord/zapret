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
        self.assertIn("UDP-порты", dialog.portsEdit.accessibleDescription())
        self.assertEqual(dialog.yesButton.accessibleName(), "Добавить пользовательский profile")
        self.assertEqual(
            dialog.yesButton.property("screenReaderStateText"),
            "Добавить пользовательский profile",
        )
        self.assertIn("Создаёт profile", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить создание пользовательского profile")
        self.assertEqual(
            dialog.cancelButton.property("screenReaderStateText"),
            "Отменить создание пользовательского profile",
        )

    def test_save_mode_buttons_have_screen_reader_state_text(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, button_text="Сохранить")
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.yesButton.accessibleName(), "Сохранить пользовательский profile")
        self.assertEqual(
            dialog.yesButton.property("screenReaderStateText"),
            "Сохранить пользовательский profile",
        )
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить изменение пользовательского profile")
        self.assertEqual(
            dialog.cancelButton.property("screenReaderStateText"),
            "Отменить изменение пользовательского profile",
        )

    def test_input_clear_buttons_do_not_take_tab_focus(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, name="YouTube", ports="80,443")
        self.addCleanup(dialog.deleteLater)
        dialog.show()
        self.app.processEvents()

        for line_edit in (dialog.nameEdit, dialog.portsEdit):
            with self.subTest(name=line_edit.accessibleName()):
                buttons = [
                    child
                    for child in line_edit.findChildren(object)
                    if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
                    and hasattr(child, "setFocusPolicy")
                ]
                self.assertTrue(buttons)
                self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

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

    def test_ports_hint_updates_for_selected_protocol(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        parent.resize(640, 480)
        parent.show()

        dialog = CreateUserProfileDialog(parent, protocol="tcp")
        self.addCleanup(dialog.deleteLater)

        self.assertGreaterEqual(dialog.widget.minimumWidth(), 520)
        self.assertEqual(dialog.portsLabel.text(), "TCP-порты")
        self.assertIn("443-65535", dialog.portsEdit.placeholderText())
        self.assertIn("80,443-65535", dialog.portsEdit.placeholderText())
        self.assertIn("список через запятую", dialog.portsHintLabel.text())
        self.assertNotIn("порт прокси", dialog.portsHintLabel.text())
        self.assertIn("TCP", dialog.portsEdit.accessibleDescription())

        dialog.protocolCombo.setCurrentIndex(1)

        self.assertEqual(dialog.portsLabel.text(), "UDP-порты")
        self.assertIn("UDP-порты", dialog.portsEdit.placeholderText())
        self.assertIn("UDP", dialog.portsHintLabel.text())
        self.assertIn("UDP", dialog.portsEdit.accessibleDescription())

        dialog.protocolCombo.setCurrentIndex(2)

        self.assertEqual(dialog.portsLabel.text(), "L7")
        self.assertIn("stun,discord", dialog.portsEdit.placeholderText())
        self.assertIn("stun,discord", dialog.portsHintLabel.text())
        self.assertIn("L7", dialog.portsEdit.accessibleDescription())

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
