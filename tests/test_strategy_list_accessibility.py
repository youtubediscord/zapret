from __future__ import annotations

import inspect
import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QListWidgetItem

from profile.ui.profile_setup_page import ProfileStrategyListWidget


def _make_sync_strategy_list() -> ProfileStrategyListWidget:
    widget = ProfileStrategyListWidget()
    widget._strategy_filter_runtime = None
    return widget


class StrategyListAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_strategy_list_is_keyboard_focusable_and_named(self) -> None:
        source = inspect.getsource(ProfileStrategyListWidget.__init__)

        self.assertIn("Qt.FocusPolicy.StrongFocus", source)
        self.assertNotIn("Qt.FocusPolicy.NoFocus", source)
        self.assertIn('set_control_accessibility(self._search, name="Поиск готовых стратегий"', source)
        self.assertIn("set_control_accessibility(", source)
        self.assertIn('name="Список готовых стратегий"', source)
        self.assertIn("стрелками вверх и вниз", source)

    def test_strategy_widget_forwards_keyboard_focus_to_list(self) -> None:
        widget = ProfileStrategyListWidget()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertIs(widget.focusProxy(), widget._list)

    def test_strategy_search_explains_keyboard_path_to_results(self) -> None:
        widget = ProfileStrategyListWidget()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget._search.accessibleName(), "Поиск готовых стратегий")
        description = widget._search.accessibleDescription()
        self.assertIn("перейдите в список клавишей Tab", description)
        self.assertIn("выберите стратегию стрелками", description)
        self.assertIn("нажмите Enter или Пробел", description)

    def test_strategy_list_explains_enter_or_space_activation(self) -> None:
        widget = ProfileStrategyListWidget()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget._list.accessibleName(), "Список готовых стратегий: список пока загружается")
        description = widget._list.accessibleDescription()
        self.assertIn("выберите готовую стратегию стрелками", description.lower())
        self.assertIn("нажмите Enter или Пробел", description)

    def test_strategy_list_exposes_initial_loading_state(self) -> None:
        widget = ProfileStrategyListWidget()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget._list.accessibleName(), "Список готовых стратегий: список пока загружается")
        self.assertEqual(
            widget._list.property("screenReaderStateText"),
            "Список готовых стратегий: список пока загружается",
        )

    def test_strategy_summary_reads_visible_count(self) -> None:
        widget = _make_sync_strategy_list()
        self.addCleanup(widget.deleteLater)

        widget.set_rows(
            entries={
                "alpha": SimpleNamespace(name="Alpha", args="--alpha"),
                "beta": SimpleNamespace(name="Beta", args="--beta"),
            },
            states={},
            current_strategy_id="none",
        )

        self.assertEqual(widget._summary.text(), "2 из 2")
        self.assertEqual(
            widget._summary.property("screenReaderStateText"),
            "Показано готовых стратегий: 2 из 2",
        )

        widget._search.setText("Alpha")

        self.assertEqual(widget._summary.text(), "1 из 2")
        self.assertEqual(
            widget._summary.property("screenReaderStateText"),
            "Показано готовых стратегий: 1 из 2",
        )

    def test_strategy_list_updates_screen_reader_text_when_current_row_changes(self) -> None:
        widget = _make_sync_strategy_list()
        self.addCleanup(widget.deleteLater)

        visual = SimpleNamespace(label="Fake", description="Подмена TLS", icon_name="", color="")
        widget.set_rows(
            entries={
                "alpha": SimpleNamespace(name="Alpha", args="--alpha", visual=visual),
                "beta": SimpleNamespace(name="Beta", args="--beta", visual=visual),
            },
            states={},
            current_strategy_id="beta",
        )

        self.assertEqual(
            widget._list.property("screenReaderStateText"),
            "Готовая стратегия: Beta, выбрана, Fake, Подмена TLS. "
            "Нажмите Enter или Пробел, чтобы выбрать стратегию.",
        )

        widget._list.setCurrentRow(0)

        self.assertEqual(
            widget._list.property("screenReaderStateText"),
            "Готовая стратегия: Alpha, не выбрана, Fake, Подмена TLS. "
            "Нажмите Enter или Пробел, чтобы выбрать стратегию.",
        )

    def test_strategy_list_view_activates_current_row_from_keyboard(self) -> None:
        from profile.ui.profile_setup_page import ProfileStrategyListView

        view = ProfileStrategyListView()
        self.addCleanup(view.deleteLater)
        item = QListWidgetItem("TLS fake")
        view.addItem(item)
        view.setCurrentItem(item)
        activated: list[str] = []
        view.itemActivated.connect(lambda current: activated.append(current.text()))

        event = QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Return), Qt.KeyboardModifier.NoModifier)

        view.keyPressEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(activated, ["TLS fake"])


if __name__ == "__main__":
    unittest.main()
