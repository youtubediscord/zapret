from __future__ import annotations

import unittest


class _Widget:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.accessible_name = ""
        self.accessible_description = ""
        self.tooltip = ""
        self.properties: dict[str, object] = {}
        self.property_calls: list[tuple[str, object]] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def accessibleName(self) -> str:  # noqa: N802
        return self.accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self.accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self.accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self.accessible_description = str(text)

    def toolTip(self) -> str:  # noqa: N802
        return self.tooltip

    def setToolTip(self, text: str) -> None:  # noqa: N802
        self.tooltip = str(text)

    def property(self, name: str):  # noqa: A003
        return self.properties.get(str(name))

    def setProperty(self, name: str, value) -> None:  # noqa: N802
        self.property_calls.append((str(name), value))
        self.properties[str(name)] = value


class AccessibilityHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_set_accessible_name_uses_widget_text_by_default(self) -> None:
        from ui.accessibility import set_accessible_name

        widget = _Widget("Запустить")

        changed = set_accessible_name(widget)

        self.assertTrue(changed)
        self.assertEqual(widget.accessible_name, "Запустить")

    def test_set_accessible_description_skips_duplicate_value(self) -> None:
        from ui.accessibility import set_accessible_description

        widget = _Widget()
        widget.accessible_description = "Открывает папку с логами"

        changed = set_accessible_description(widget, "Открывает папку с логами")

        self.assertFalse(changed)
        self.assertEqual(widget.accessible_description, "Открывает папку с логами")

    def test_set_control_accessibility_sets_name_and_description(self) -> None:
        from ui.accessibility import set_control_accessibility

        widget = _Widget("Остановить")

        set_control_accessibility(
            widget,
            name="Остановить Zapret",
            description="Останавливает запущенный процесс обхода блокировок.",
        )

        self.assertEqual(widget.accessible_name, "Остановить Zapret")
        self.assertEqual(widget.accessible_description, "Останавливает запущенный процесс обхода блокировок.")

    def test_set_control_accessibility_enables_enter_for_push_button(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from qfluentwidgets import PushButton

        from ui.accessibility import set_control_accessibility

        button = PushButton("Открыть")
        self.addCleanup(button.deleteLater)
        clicked: list[bool] = []
        button.clicked.connect(lambda: clicked.append(True))

        set_control_accessibility(button, name="Открыть логи")
        button.show()
        self._app.processEvents()
        button.setFocus()
        self._app.processEvents()
        QTest.keyClick(button, Qt.Key.Key_Return)
        self._app.processEvents()

        self.assertEqual(clicked, [True])

    def test_set_control_accessibility_enables_tab_and_enter_for_clickable_widget(self) -> None:
        from PyQt6.QtCore import QEvent, Qt, pyqtSignal
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QWidget

        from ui.accessibility import set_control_accessibility

        class ClickablePanel(QWidget):
            clicked = pyqtSignal()

        panel = ClickablePanel()
        self.addCleanup(panel.deleteLater)
        panel.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        clicked: list[bool] = []
        panel.clicked.connect(lambda: clicked.append(True))

        set_control_accessibility(panel, name="Открыть раздел: Логи")
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        panel.keyPressEvent(event)

        self.assertEqual(panel.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertTrue(event.isAccepted())
        self.assertEqual(clicked, [True])

    def test_set_control_accessibility_names_spinbox_inner_field_and_skips_buttons(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import SpinBox

        from ui.accessibility import set_control_accessibility

        spinbox = SpinBox()
        self.addCleanup(spinbox.deleteLater)

        set_control_accessibility(
            spinbox,
            name="Номер стратегии, выбрано: 3",
            description="Стрелками вверх и вниз можно изменить номер стратегии.",
        )

        line_edit = spinbox.findChild(object, "qt_spinbox_lineedit")
        buttons = [
            child
            for child in spinbox.findChildren(object)
            if type(child).__name__ == "SpinButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertIsNotNone(line_edit)
        self.assertEqual(line_edit.accessibleName(), "Номер стратегии, выбрано: 3")
        self.assertIn("Стрелками вверх и вниз", line_edit.accessibleDescription())
        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_control_accessibility_skips_line_edit_clear_button_in_tab_order(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import LineEdit

        from ui.accessibility import set_control_accessibility

        line_edit = LineEdit()
        self.addCleanup(line_edit.deleteLater)

        set_control_accessibility(line_edit, name="Домен для белого списка")

        buttons = [
            child
            for child in line_edit.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_control_accessibility_skips_plain_text_edit_scrollbar_arrows(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import PlainTextEdit

        from ui.accessibility import set_control_accessibility

        text_edit = PlainTextEdit()
        self.addCleanup(text_edit.deleteLater)

        set_control_accessibility(text_edit, name="История рейтингов стратегий")

        buttons = [
            child
            for child in text_edit.findChildren(object)
            if type(child).__name__ == "ArrowButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_state_text_marks_text_status_for_screen_reader(self) -> None:
        from ui.accessibility import set_state_text

        widget = _Widget()

        set_state_text(widget, "Запущено")

        self.assertEqual(widget.accessible_name, "Запущено")
        self.assertEqual(widget.properties["screenReaderStateText"], "Запущено")

    def test_set_state_text_skips_line_edit_clear_button_in_tab_order(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import LineEdit

        from ui.accessibility import set_state_text

        line_edit = LineEdit()
        self.addCleanup(line_edit.deleteLater)

        set_state_text(line_edit, "Код привязки Premium: пока не создан")

        buttons = [
            child
            for child in line_edit.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_state_text_skips_plain_text_edit_scrollbar_arrows(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import PlainTextEdit

        from ui.accessibility import set_state_text

        text_edit = PlainTextEdit()
        self.addCleanup(text_edit.deleteLater)

        set_state_text(text_edit, "Лог обучения Оркестратора: пока нет записей обучения")

        buttons = [
            child
            for child in text_edit.findChildren(object)
            if type(child).__name__ == "ArrowButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_state_text_skips_duplicate_property_write(self) -> None:
        from ui.accessibility import set_state_text

        widget = _Widget()
        widget.accessible_name = "Запущено"
        widget.properties["screenReaderStateText"] = "Запущено"

        set_state_text(widget, "Запущено")

        self.assertEqual(widget.property_calls, [])

    def test_set_item_accessible_text_sets_item_roles(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidgetItem

        from ui.accessibility import set_item_accessible_text

        item = QTableWidgetItem("OK")

        set_item_accessible_text(item, "Статус: OK", description="Проверка прошла успешно")

        self.assertEqual(item.data(Qt.ItemDataRole.AccessibleTextRole), "Статус: OK")
        self.assertEqual(item.data(Qt.ItemDataRole.AccessibleDescriptionRole), "Проверка прошла успешно")

    def test_remove_line_edit_buttons_from_tab_order_skips_qfluent_search_buttons(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import SearchLineEdit

        from ui.accessibility import remove_line_edit_buttons_from_tab_order

        search = SearchLineEdit()
        self.addCleanup(search.deleteLater)
        search.setClearButtonEnabled(True)
        search.setText("profile")
        search.show()
        self._app.processEvents()

        buttons = [
            child
            for child in search.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]
        self.assertTrue(buttons)

        remove_line_edit_buttons_from_tab_order(search)

        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_remove_line_edit_buttons_from_tab_order_handles_buttons_created_after_text_change(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import SearchLineEdit

        from ui.accessibility import remove_line_edit_buttons_from_tab_order

        search = SearchLineEdit()
        self.addCleanup(search.deleteLater)
        search.setClearButtonEnabled(True)

        remove_line_edit_buttons_from_tab_order(search)
        search.setText("profile")
        self._app.processEvents()

        buttons = [
            child
            for child in search.findChildren(object)
            if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
            and hasattr(child, "setFocusPolicy")
        ]

        self.assertTrue(buttons)
        self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_set_segmented_items_accessibility_marks_selected_item(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from ui.segmented_accessibility import set_segmented_items_accessibility

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        widget = SegmentedWidget()
        widget.addItem("first", "Первый")
        widget.addItem("second", "Второй")
        widget.setCurrentItem("second")

        set_segmented_items_accessibility(widget, name="Раздел")

        self.assertEqual(widget.items["first"].accessibleName(), "Раздел: Первый, не выбрано")
        self.assertEqual(widget.items["second"].accessibleName(), "Раздел: Второй, выбрано")

    def test_set_segmented_items_accessibility_accepts_accessible_labels(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from ui.segmented_accessibility import set_segmented_items_accessibility

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        widget = SegmentedWidget()
        widget.addItem("about", "О ПРОГРАММЕ")
        widget.addItem("support", "ПОДДЕРЖКА")
        widget.setCurrentItem("about")

        set_segmented_items_accessibility(
            widget,
            name="Вкладки",
            labels={
                "about": "О программе",
                "support": "Поддержка",
            },
        )

        self.assertEqual(widget.items["about"].accessibleName(), "Вкладки: О программе, выбрано")
        self.assertEqual(widget.items["support"].accessibleName(), "Вкладки: Поддержка, не выбрано")

    def test_set_segmented_items_accessibility_enables_keyboard_selection(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from ui.segmented_accessibility import set_segmented_items_accessibility

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        selected: list[str] = []
        widget = SegmentedWidget()
        widget.addItem("first", "Первый", lambda: selected.append("first"))
        widget.addItem("second", "Второй", lambda: selected.append("second"))
        widget.setCurrentItem("first")

        set_segmented_items_accessibility(widget, name="Раздел")

        right_event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Right), Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget.items["first"], right_event)

        self.assertTrue(right_event.isAccepted())
        self.assertEqual(widget.currentRouteKey(), "second")
        self.assertEqual(selected, ["second"])

        enter_event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget.items["second"], enter_event)

        self.assertTrue(enter_event.isAccepted())
        self.assertEqual(selected, ["second", "second"])

    def test_segmented_keyboard_selection_refreshes_spoken_selected_state(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from ui.segmented_accessibility import set_segmented_items_accessibility

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        widget = SegmentedWidget()
        widget.addItem("first", "Первый")
        widget.addItem("second", "Второй")
        widget.setCurrentItem("first")

        set_segmented_items_accessibility(widget, name="Раздел")

        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Right), Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget.items["first"], event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(widget.currentRouteKey(), "second")
        self.assertEqual(widget.items["first"].accessibleName(), "Раздел: Первый, не выбрано")
        self.assertEqual(widget.items["second"].accessibleName(), "Раздел: Второй, выбрано")

    def test_segmented_widget_itself_reads_current_selection(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from ui.segmented_accessibility import set_segmented_items_accessibility

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        widget = SegmentedWidget()
        widget.addItem("first", "Первый")
        widget.addItem("second", "Второй")
        widget.setCurrentItem("second")

        set_segmented_items_accessibility(widget, name="Раздел")

        self.assertEqual(widget.accessibleName(), "Раздел, выбрано: Второй")
        self.assertEqual(widget.property("screenReaderStateText"), "Раздел, выбрано: Второй")
        self.assertIn("стрелками", widget.accessibleDescription())
        self.assertIn("Enter или Пробел", widget.accessibleDescription())

    def test_combo_items_accessibility_updates_after_selection_change(self) -> None:
        from PyQt6.QtCore import Qt
        from qfluentwidgets import ComboBox

        from ui.combo_accessibility import set_combo_items_accessibility

        combo = ComboBox()
        self.addCleanup(combo.deleteLater)
        combo.addItem("Авто")
        combo.addItem("Ручной")

        set_combo_items_accessibility(combo, name="Режим запуска")

        combo.setCurrentIndex(1)
        menu = combo._create_accessible_combo_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим запуска: Авто, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим запуска: Ручной, выбран",
        )

    def test_set_tooltip_also_sets_accessible_description(self) -> None:
        from unittest.mock import patch

        from ui.fluent_widgets import set_tooltip

        widget = _Widget()
        widget.installEventFilter = lambda _filter: None

        with patch("ui.fluent_widgets.ToolTipFilter", return_value=object()):
            set_tooltip(widget, "Открывает папку с логами.")

        self.assertEqual(widget.tooltip, "Открывает папку с логами.")
        self.assertEqual(widget.accessible_description, "Открывает папку с логами.")

    def test_set_tooltip_sets_accessible_name_for_icon_only_controls(self) -> None:
        from unittest.mock import patch

        from ui.fluent_widgets import set_tooltip

        widget = _Widget("")
        widget.installEventFilter = lambda _filter: None

        with patch("ui.fluent_widgets.ToolTipFilter", return_value=object()):
            set_tooltip(widget, "Создать новый preset")

        self.assertEqual(widget.accessible_name, "Создать новый preset")


if __name__ == "__main__":
    unittest.main()
