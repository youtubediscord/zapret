from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QIcon, QKeyEvent, QPixmap
from PyQt6.QtWidgets import QApplication


class _TextLabel:
    def __init__(self, text: str) -> None:
        self._text = str(text)
        self.set_calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.set_calls.append(value)
        self._text = value


class _StyledTextLabel(_TextLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._style = ""
        self.style_calls: list[str] = []

    def styleSheet(self) -> str:  # noqa: N802
        return self._style

    def setStyleSheet(self, style: str) -> None:  # noqa: N802
        value = str(style)
        self.style_calls.append(value)
        self._style = value


class _SwitchButton:
    def __init__(self, checked: bool) -> None:
        self.checked = bool(checked)
        self.set_calls: list[bool] = []
        self.block_calls: list[bool] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self.checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        self.set_calls.append(bool(checked))
        self.checked = bool(checked)

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))


class _SpinBox:
    def __init__(self, value: int) -> None:
        self._value = int(value)
        self.set_calls: list[int] = []
        self.block_calls: list[bool] = []

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:  # noqa: N802
        next_value = int(value)
        self.set_calls.append(next_value)
        self._value = next_value

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))


class _ComboBox:
    def __init__(self, index: int = 0, data_by_index: dict[int, object] | None = None) -> None:
        self._index = int(index)
        self._data_by_index = dict(data_by_index or {})
        self.set_calls: list[int] = []
        self.block_calls: list[bool] = []

    def currentIndex(self) -> int:  # noqa: N802
        return self._index

    def currentData(self):
        return self._data_by_index.get(self._index)

    def findData(self, data) -> int:  # noqa: N802
        for index, value in self._data_by_index.items():
            if value == data:
                return index
        return -1

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        next_index = int(index)
        self.set_calls.append(next_index)
        self._index = next_index

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))


class Win11ToggleRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_set_checked_skips_duplicate_state(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        switch = _SwitchButton(True)
        row._switch_button = switch

        Win11ToggleRow.setChecked(row, True, block_signals=True)

        self.assertEqual(switch.set_calls, [])
        self.assertEqual(switch.block_calls, [])

    def test_set_checked_applies_changed_state_with_blocked_signals(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        switch = _SwitchButton(False)
        row._switch_button = switch

        Win11ToggleRow.setChecked(row, True, block_signals=True)

        self.assertEqual(switch.set_calls, [True])
        self.assertEqual(switch.block_calls, [True, False])
        self.assertTrue(switch.checked)

    def test_set_checked_does_not_emit_user_toggle_signal(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow("fa5s.shield-alt", "Отключить Windows Defender")
        events: list[bool] = []
        row.toggled.connect(events.append)

        row.setChecked(True)
        self._app.processEvents()

        self.assertTrue(row.isChecked())
        self.assertEqual(events, [])

    def test_switch_signal_still_emits_user_toggle_signal(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow("fa5s.shield-alt", "Отключить Windows Defender")
        events: list[bool] = []
        row.toggled.connect(events.append)

        row._on_switch_toggled(True)

        self.assertEqual(events, [True])

    def test_combo_row_menu_items_are_named_for_screen_reader(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow(
            "fa5s.sliders-h",
            "Режим запуска",
            "Выберите режим запуска DPI",
            items=[("Авто", "auto"), ("Ручной", "manual")],
        )
        self.addCleanup(row.deleteLater)
        create_menu = getattr(row.combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим запуска: Авто, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим запуска: Ручной, не выбран",
        )

    def test_toggle_row_has_screen_reader_text_for_switch_state(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow(
            "fa5s.bolt",
            "Автозапуск DPI",
            "Запускать DPI после старта программы",
        )

        self.assertEqual(row.accessibleName(), "Автозапуск DPI, выключено")
        self.assertEqual(row.property("screenReaderStateText"), "Автозапуск DPI, выключено")
        self.assertIn("Запускать DPI после старта программы", row.accessibleDescription())
        self.assertEqual(row._switch_button.accessibleName(), "Автозапуск DPI, выключено")

    def test_toggle_row_loads_icon_after_first_paint(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        scheduled: list[tuple[int, object]] = []
        icon = QIcon(QPixmap(1, 1))
        with patch(
            "ui.widgets.win11_controls.get_themed_qta_icon",
            return_value=icon,
        ) as get_icon, patch(
            "ui.widgets.win11_controls.QTimer.singleShot",
            side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        ):
            row = Win11ToggleRow(
                "fa5s.bolt",
                "Автозапуск DPI",
                "Запускать DPI после старта программы",
            )

            get_icon.assert_not_called()
            self.assertEqual(len(scheduled), 1)
            self.assertGreaterEqual(scheduled[0][0], 200)
            scheduled[0][1]()

        get_icon.assert_called_once_with("fa5s.bolt", color=row._resolved_icon_color())

    def test_toggle_row_updates_screen_reader_state_after_set_checked(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow(
            "fa5s.bolt",
            "Автозапуск DPI",
            "Запускать DPI после старта программы",
        )

        row.setChecked(True)

        self.assertEqual(row.accessibleName(), "Автозапуск DPI, включено")
        self.assertEqual(row.property("screenReaderStateText"), "Автозапуск DPI, включено")
        self.assertEqual(row._switch_button.accessibleName(), "Автозапуск DPI, включено")

    def test_set_texts_skips_duplicate_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        row._title_label = _TextLabel("Title")
        row._desc_label = _TextLabel("Description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ToggleRow.set_texts(row, "Title", "Description")

        self.assertEqual(title_calls, [])
        self.assertEqual(content_calls, [])

    def test_set_texts_applies_changed_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        row._title_label = _TextLabel("Old title")
        row._desc_label = _TextLabel("Old description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ToggleRow.set_texts(row, "Title", "Description")

        self.assertEqual(title_calls, ["Title"])
        self.assertEqual(content_calls, ["Description"])

    def test_toggle_row_theme_refresh_styles_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ToggleRow

        row = Win11ToggleRow.__new__(Win11ToggleRow)
        row._title_label = _StyledTextLabel("Автозапуск ZapretGUI")
        row._desc_label = _StyledTextLabel("Запускать программу в трее")
        row._icon_label = None
        tokens = SimpleNamespace(
            fg="rgba(255, 255, 255, 0.92)",
            fg_muted="rgba(255, 255, 255, 0.65)",
            font_family_qss="'Segoe UI Variable', 'Segoe UI'",
        )

        Win11ToggleRow._apply_theme_refresh(row, tokens=tokens)

        self.assertIn("rgba(255, 255, 255, 0.92)", row._title_label.styleSheet())
        self.assertIn("font-weight: 600", row._title_label.styleSheet())
        self.assertIn("rgba(255, 255, 255, 0.65)", row._desc_label.styleSheet())
        self.assertIn("'Segoe UI Variable', 'Segoe UI'", row._desc_label.styleSheet())

    def test_radio_option_set_texts_skips_duplicate_text(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        row = Win11RadioOption.__new__(Win11RadioOption)
        title_label = _TextLabel("Zapret 2")
        desc_label = _TextLabel("Preset mode")
        badge_label = _TextLabel("recommended")
        row._title_label = title_label
        row._desc_label = desc_label
        row._badge_label = badge_label

        Win11RadioOption.set_texts(row, "Zapret 2", "Preset mode", "recommended")

        self.assertEqual(title_label.set_calls, [])
        self.assertEqual(desc_label.set_calls, [])
        self.assertEqual(badge_label.set_calls, [])

    def test_radio_option_set_texts_applies_changed_text(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        row = Win11RadioOption.__new__(Win11RadioOption)
        title_label = _TextLabel("Old")
        desc_label = _TextLabel("Old description")
        badge_label = _TextLabel("old")
        row._title_label = title_label
        row._desc_label = desc_label
        row._badge_label = badge_label

        Win11RadioOption.set_texts(row, "Zapret 2", "Preset mode", "recommended")

        self.assertEqual(title_label.set_calls, ["Zapret 2"])
        self.assertEqual(desc_label.set_calls, ["Preset mode"])
        self.assertEqual(badge_label.set_calls, ["recommended"])

    def test_radio_option_has_screen_reader_text_and_keyboard_activation(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        option = Win11RadioOption(
            "Профили Zapret 2",
            "Запуск через готовые профили",
            recommended=True,
            recommended_badge="рекомендуется",
        )
        clicked = Mock()
        option.clicked.connect(clicked)

        self.assertEqual(option.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(
            option.accessibleName(),
            "Профили Zapret 2, не выбрано, рекомендуется",
        )
        self.assertIn("Запуск через готовые профили", option.accessibleDescription())

        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(option, event)

        clicked.assert_called_once()

    def test_radio_option_updates_screen_reader_state_after_selection_change(self) -> None:
        from ui.widgets.win11_controls import Win11RadioOption

        option = Win11RadioOption(
            "Профили Zapret 2",
            "Запуск через готовые профили",
        )

        option.setSelected(True)

        self.assertEqual(option.accessibleName(), "Профили Zapret 2, выбрано")
        self.assertEqual(option.property("screenReaderStateText"), "Профили Zapret 2, выбрано")

    def test_number_row_set_value_skips_duplicate_value(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow.__new__(Win11NumberRow)
        spinbox = _SpinBox(7)
        row.spinbox = spinbox

        Win11NumberRow.setValue(row, 7, block_signals=True)

        self.assertEqual(spinbox.set_calls, [])
        self.assertEqual(spinbox.block_calls, [])

    def test_number_row_set_value_applies_changed_value_with_blocked_signals(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow.__new__(Win11NumberRow)
        spinbox = _SpinBox(7)
        row.spinbox = spinbox

        Win11NumberRow.setValue(row, 8, block_signals=True)

        self.assertEqual(spinbox.set_calls, [8])
        self.assertEqual(spinbox.block_calls, [True, False])
        self.assertEqual(spinbox.value(), 8)

    def test_number_row_has_screen_reader_text_for_current_value(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow(
            "fa5s.redo",
            "Количество попыток",
            "Сколько раз повторять проверку",
            min_val=1,
            max_val=10,
            default_val=3,
        )

        self.assertEqual(row.accessibleName(), "Количество попыток, значение: 3")
        self.assertEqual(row.property("screenReaderStateText"), "Количество попыток, значение: 3")
        self.assertIn("Сколько раз повторять проверку", row.accessibleDescription())
        self.assertEqual(row.spinbox.accessibleName(), "Количество попыток, значение: 3")

    def test_number_row_updates_screen_reader_text_after_value_change(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow(
            "fa5s.redo",
            "Количество попыток",
            "Сколько раз повторять проверку",
            min_val=1,
            max_val=10,
            default_val=3,
        )

        row.setValue(5)

        self.assertEqual(row.accessibleName(), "Количество попыток, значение: 5")
        self.assertEqual(row.property("screenReaderStateText"), "Количество попыток, значение: 5")
        self.assertEqual(row.spinbox.accessibleName(), "Количество попыток, значение: 5")

    def test_number_row_set_texts_skips_duplicate_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow.__new__(Win11NumberRow)
        row._title_label = _TextLabel("Attempts")
        row._desc_label = _TextLabel("Retry count")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11NumberRow.set_texts(row, "Attempts", "Retry count")

        self.assertEqual(title_calls, [])
        self.assertEqual(content_calls, [])

    def test_number_row_set_texts_applies_changed_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow.__new__(Win11NumberRow)
        row._title_label = _TextLabel("Old")
        row._desc_label = _TextLabel("Old description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11NumberRow.set_texts(row, "Attempts", "Retry count")

        self.assertEqual(title_calls, ["Attempts"])
        self.assertEqual(content_calls, ["Retry count"])

    def test_number_row_theme_refresh_styles_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11NumberRow

        row = Win11NumberRow.__new__(Win11NumberRow)
        row._title_label = _StyledTextLabel("Количество попыток")
        row._desc_label = _StyledTextLabel("Сколько раз повторять проверку")
        row._icon_label = None
        tokens = SimpleNamespace(
            fg="rgba(255, 255, 255, 0.92)",
            fg_muted="rgba(255, 255, 255, 0.65)",
            font_family_qss="'Segoe UI Variable', 'Segoe UI'",
        )

        Win11NumberRow._apply_theme_refresh(row, tokens=tokens)

        self.assertIn("rgba(255, 255, 255, 0.92)", row._title_label.styleSheet())
        self.assertIn("font-weight: 600", row._title_label.styleSheet())
        self.assertIn("rgba(255, 255, 255, 0.65)", row._desc_label.styleSheet())

    def test_combo_row_set_current_index_skips_duplicate_index(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        combo = _ComboBox(index=2)
        row.combo = combo

        Win11ComboRow.setCurrentIndex(row, 2, block_signals=True)

        self.assertEqual(combo.set_calls, [])
        self.assertEqual(combo.block_calls, [])

    def test_combo_row_set_current_index_applies_changed_index_with_blocked_signals(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        combo = _ComboBox(index=1)
        row.combo = combo

        Win11ComboRow.setCurrentIndex(row, 2, block_signals=True)

        self.assertEqual(combo.set_calls, [2])
        self.assertEqual(combo.block_calls, [True, False])
        self.assertEqual(combo.currentIndex(), 2)

    def test_combo_row_set_current_data_skips_duplicate_data(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        combo = _ComboBox(index=1, data_by_index={0: "off", 1: "on"})
        row.combo = combo

        Win11ComboRow.setCurrentData(row, "on", block_signals=True)

        self.assertEqual(combo.set_calls, [])
        self.assertEqual(combo.block_calls, [])

    def test_combo_row_set_current_data_applies_changed_data_with_blocked_signals(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        combo = _ComboBox(index=0, data_by_index={0: "off", 1: "on"})
        row.combo = combo

        Win11ComboRow.setCurrentData(row, "on", block_signals=True)

        self.assertEqual(combo.set_calls, [1])
        self.assertEqual(combo.block_calls, [True, False])
        self.assertEqual(combo.currentData(), "on")

    def test_combo_row_has_screen_reader_text_for_current_choice(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow(
            "fa5s.list",
            "Режим запуска",
            "Выберите способ запуска",
            items=[("Zapret 1", "zapret1"), ("Zapret 2", "zapret2")],
        )

        self.assertEqual(row.accessibleName(), "Режим запуска, выбрано: Zapret 1")
        self.assertEqual(row.property("screenReaderStateText"), "Режим запуска, выбрано: Zapret 1")
        self.assertIn("Выберите способ запуска", row.accessibleDescription())
        self.assertEqual(row.combo.accessibleName(), "Режим запуска, выбрано: Zapret 1")

    def test_combo_row_updates_screen_reader_text_after_selection_change(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow(
            "fa5s.list",
            "Режим запуска",
            "Выберите способ запуска",
            items=[("Zapret 1", "zapret1"), ("Zapret 2", "zapret2")],
        )

        row.setCurrentIndex(1)

        self.assertEqual(row.accessibleName(), "Режим запуска, выбрано: Zapret 2")
        self.assertEqual(row.property("screenReaderStateText"), "Режим запуска, выбрано: Zapret 2")
        self.assertEqual(row.combo.accessibleName(), "Режим запуска, выбрано: Zapret 2")

    def test_combo_row_set_texts_skips_duplicate_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        row._title_label = _TextLabel("Preset")
        row._desc_label = _TextLabel("Select mode")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ComboRow.set_texts(row, "Preset", "Select mode")

        self.assertEqual(title_calls, [])
        self.assertEqual(content_calls, [])

    def test_combo_row_set_texts_applies_changed_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        row._title_label = _TextLabel("Old")
        row._desc_label = _TextLabel("Old description")
        title_calls: list[str] = []
        content_calls: list[str] = []

        def set_title(text: str) -> None:
            title_calls.append(str(text))

        def set_content(text: str) -> None:
            content_calls.append(str(text))

        row.setTitle = set_title
        row.setContent = set_content

        Win11ComboRow.set_texts(row, "Preset", "Select mode")

        self.assertEqual(title_calls, ["Preset"])
        self.assertEqual(content_calls, ["Select mode"])

    def test_combo_row_theme_refresh_styles_title_and_description(self) -> None:
        from ui.widgets.win11_controls import Win11ComboRow

        row = Win11ComboRow.__new__(Win11ComboRow)
        row._title_label = _StyledTextLabel("Режим")
        row._desc_label = _StyledTextLabel("Выберите вариант")
        row._icon_label = None
        tokens = SimpleNamespace(
            fg="rgba(255, 255, 255, 0.92)",
            fg_muted="rgba(255, 255, 255, 0.65)",
            font_family_qss="'Segoe UI Variable', 'Segoe UI'",
        )

        Win11ComboRow._apply_theme_refresh(row, tokens=tokens)

        self.assertIn("rgba(255, 255, 255, 0.92)", row._title_label.styleSheet())
        self.assertIn("font-weight: 600", row._title_label.styleSheet())
        self.assertIn("rgba(255, 255, 255, 0.65)", row._desc_label.styleSheet())


if __name__ == "__main__":
    unittest.main()
