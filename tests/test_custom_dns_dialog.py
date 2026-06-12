from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, Qt
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

    def test_context_menu_dispatches_quick_actions_immediately(self) -> None:
        import dns.ui.custom_dns_dialog as custom_dns_dialog
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(
            parent,
            servers=[
                {"id": "cloudflare", "name": "Cloudflare", "ipv4": ["1.1.1.1", "1.0.0.1"], "ipv6": []},
            ],
        )
        dialog.serversList.setCurrentRow(0)
        created_actions: dict[str, _FakeAction] = {}

        def make_action(text: str, *, icon=None, parent=None):
            action = _FakeAction(text)
            created_actions[text] = action
            return action

        with (
            patch.object(custom_dns_dialog, "RoundMenu", _FakeMenu),
            patch.object(custom_dns_dialog, "make_menu_action", side_effect=make_action),
            patch.object(
                custom_dns_dialog,
                "exec_popup_menu",
                side_effect=lambda *_args, **_kwargs: created_actions["Создать копию"],
            ),
        ):
            dialog._show_servers_context_menu(QPoint(0, 0))

        self.assertEqual([server["name"] for server in dialog.servers()], ["Cloudflare", "Cloudflare копия"])
        self.assertEqual(dialog.serversList.count(), 2)

    def test_context_menu_is_bound_to_exact_list_row_viewport(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(
            parent,
            servers=[
                {"id": "cloudflare", "name": "Cloudflare", "ipv4": ["1.1.1.1"], "ipv6": []},
            ],
        )

        self.assertEqual(
            dialog.serversList.viewport().contextMenuPolicy(),
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

    def test_context_menu_copy_and_delete_actions_work_immediately(self) -> None:
        from dns.ui.custom_dns_dialog import CustomDnsDialog

        parent = QWidget()
        parent.resize(640, 480)
        dialog = CustomDnsDialog(
            parent,
            servers=[
                {"id": "cloudflare", "name": "Cloudflare", "ipv4": ["1.1.1.1", "1.0.0.1"], "ipv6": []},
            ],
        )
        dialog.serversList.setCurrentRow(0)

        self.assertTrue(dialog._copy_current_dns_to_clipboard())
        self.assertEqual(QApplication.clipboard().text(), "1.1.1.1, 1.0.0.1")

        self.assertTrue(dialog._delete_current_server())
        self.assertEqual(dialog.servers(), [])


class _FakeMenu:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self._actions = []
        self.view = _FakeMenuView()

    def addAction(self, action) -> None:  # noqa: N802
        self._actions.append(action)
        self.view.add_item()

    def addSeparator(self) -> None:  # noqa: N802
        self._actions.append(None)
        self.view.add_item()

    def actions(self):
        return list(self._actions)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMenuItem:
    def __init__(self) -> None:
        self._data = {}

    def setData(self, role, value) -> None:  # noqa: N802
        self._data[int(role)] = value


class _FakeMenuView:
    def __init__(self) -> None:
        self._items: list[_FakeMenuItem] = []

    def add_item(self) -> None:
        self._items.append(_FakeMenuItem())

    def count(self) -> int:
        return len(self._items)

    def item(self, row: int):
        return self._items[row] if 0 <= row < len(self._items) else None


if __name__ == "__main__":
    unittest.main()
