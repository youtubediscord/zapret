from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication


class _Button:
    def __init__(self, checked: bool = False) -> None:
        self._checked = bool(checked)
        self.calls: list[bool] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        value = bool(checked)
        self.calls.append(value)
        self._checked = value


class ProfileTypeSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_set_button_checked_skips_duplicate_state(self) -> None:
        from profile.ui.widgets.profile_type_selector import set_button_checked_if_changed

        button = _Button(True)

        self.assertFalse(set_button_checked_if_changed(button, True))
        self.assertEqual(button.calls, [])

        self.assertTrue(set_button_checked_if_changed(button, False))
        self.assertEqual(button.calls, [False])

    def test_set_active_profile_types_skips_duplicate_button_states(self) -> None:
        from profile.ui.widgets.profile_type_selector import ProfileTypeSelector

        all_button = _Button(False)
        tcp_button = _Button(True)
        udp_button = _Button(False)
        selector = SimpleNamespace(
            _buttons={
                "all": all_button,
                "tcp": tcp_button,
                "udp": udp_button,
            },
            blockSignals=lambda _blocked: None,
            _has_other_selected=lambda: any(
                button.isChecked()
                for key, button in selector._buttons.items()
                if key != "all"
            ),
        )

        ProfileTypeSelector.set_active_profile_types(selector, {"tcp"})

        self.assertEqual(all_button.calls, [])
        self.assertEqual(tcp_button.calls, [])
        self.assertEqual(udp_button.calls, [])

    def test_profile_types_signal_skips_duplicate_state(self) -> None:
        from profile.ui.widgets.profile_type_selector import ProfileTypeSelector

        emitted: list[set[str]] = []
        selector = SimpleNamespace(
            get_active_profile_types=lambda: {"all"},
            profile_types_changed=SimpleNamespace(emit=emitted.append),
        )

        changed = ProfileTypeSelector._emit_profile_types_changed_if_needed(selector, {"all"})

        self.assertFalse(changed)
        self.assertEqual(emitted, [])

    def test_buttons_expose_selected_state_to_screen_reader(self) -> None:
        from profile.ui.widgets.profile_type_selector import ProfileTypeSelector

        selector = ProfileTypeSelector()
        self.addCleanup(selector.deleteLater)

        self.assertEqual(selector.accessibleName(), "Фильтр типов profile")
        self.assertIn("Выберите один или несколько типов", selector.accessibleDescription())
        self.assertEqual(selector._buttons["all"].accessibleName(), "Тип profile: Все, выбрано")
        self.assertEqual(selector._buttons["tcp"].accessibleName(), "Тип profile: TCP, не выбрано")
        self.assertIn("Фильтрует список profile", selector._buttons["tcp"].accessibleDescription())

        selector.set_active_profile_types({"tcp"})

        self.assertEqual(selector._buttons["all"].accessibleName(), "Тип profile: Все, не выбрано")
        self.assertEqual(selector._buttons["tcp"].accessibleName(), "Тип profile: TCP, выбрано")
        self.assertEqual(selector._buttons["tcp"].property("screenReaderStateText"), "Тип profile: TCP, выбрано")

    def test_profile_type_filter_explains_keyboard_navigation_to_screen_reader(self) -> None:
        from profile.ui.widgets.profile_type_selector import ProfileTypeSelector

        selector = ProfileTypeSelector()
        self.addCleanup(selector.deleteLater)

        self.assertIn("стрелками влево и вправо", selector.accessibleDescription().lower())
        self.assertIn("Enter или Пробел", selector._buttons["tcp"].accessibleDescription())

    def test_arrow_keys_move_focus_between_profile_type_buttons(self) -> None:
        from profile.ui.widgets.profile_type_selector import ProfileTypeSelector

        selector = ProfileTypeSelector()
        self.addCleanup(selector.deleteLater)
        selector.show()
        self._app.processEvents()

        selector._buttons["all"].setFocus()
        self._app.processEvents()

        QTest.keyClick(selector._buttons["all"], Qt.Key.Key_Right)
        self._app.processEvents()

        self.assertIs(self._app.focusWidget(), selector._buttons["tcp"])


if __name__ == "__main__":
    unittest.main()
