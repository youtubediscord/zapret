from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication


class _AccessibleLabel:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.accessible_name = ""
        self.properties: dict[str, object] = {}

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self.properties[name] = value


class AutostartAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _send_key(self, widget, key: Qt.Key) -> None:
        event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, event)

    def test_option_card_has_screen_reader_text_and_keyboard_activation(self) -> None:
        from autostart.ui.page import AutostartOptionCard

        card = AutostartOptionCard(
            "fa5s.desktop",
            "Автозапуск программы Zapret",
            "Запускает главное окно программы при входе в Windows.",
        )
        clicked = Mock()
        card.clicked.connect(clicked)

        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIn("Автозапуск программы Zapret", card.accessibleName())
        self.assertIn("не включено", card.accessibleName())
        self.assertIn("Запускает главное окно", card.accessibleDescription())

        self._send_key(card, Qt.Key.Key_Return)

        clicked.assert_called_once()

    def test_option_card_announces_active_state_and_ignores_keyboard_activation(self) -> None:
        from autostart.ui.page import AutostartOptionCard

        card = AutostartOptionCard(
            "fa5s.desktop",
            "Автозапуск программы Zapret",
            "Запускает главное окно программы при входе в Windows.",
        )
        clicked = Mock()
        card.clicked.connect(clicked)

        card.set_disabled(True, is_active=True)
        self.assertIn("включено", card.accessibleName())

        self._send_key(card, Qt.Key.Key_Space)

        clicked.assert_not_called()

    def test_mode_card_has_screen_reader_text_and_keyboard_activation(self) -> None:
        from autostart.ui.page import ClickableModeCard

        card = ClickableModeCard()
        clicked = Mock()
        card.clicked.connect(clicked)

        card.set_mode_accessibility(mode="Профили (Zapret 2)", strategy="TLS fake")

        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIn("Текущий режим: Профили (Zapret 2)", card.accessibleName())
        self.assertIn("Стратегия: TLS fake", card.accessibleName())

        self._send_key(card, Qt.Key.Key_Enter)

        clicked.assert_called_once()

    def test_status_update_writes_screen_reader_state_text(self) -> None:
        from autostart.ui.page import AutostartPage

        page = AutostartPage.__new__(AutostartPage)
        page.strategy_name = "TLS fake"
        page._ui_language = "ru"
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.status_label = _AccessibleLabel()
        page.status_desc = _AccessibleLabel()
        page.current_strategy_label = _AccessibleLabel("TLS fake")
        page.status_icon = Mock()
        page.disable_btn = Mock()
        page.gui_option = Mock()
        page._update_mode = Mock()

        AutostartPage.update_status(page, True, "TLS fake")

        self.assertEqual(page.status_label.accessible_name, "Автозапуск включён")
        self.assertEqual(page.status_label.properties["screenReaderStateText"], "Автозапуск включён")
        self.assertEqual(
            page.current_strategy_label.properties["screenReaderStateText"],
            "Текущая стратегия: TLS fake",
        )


if __name__ == "__main__":
    unittest.main()
