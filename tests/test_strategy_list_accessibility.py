from __future__ import annotations

import inspect
import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from profile.ui.profile_setup_page import ProfileStrategyListWidget


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

    def test_strategy_search_explains_keyboard_path_to_results(self) -> None:
        widget = ProfileStrategyListWidget()
        self.addCleanup(widget.deleteLater)

        self.assertEqual(widget._search.accessibleName(), "Поиск готовых стратегий")
        description = widget._search.accessibleDescription()
        self.assertIn("перейдите в список клавишей Tab", description)
        self.assertIn("выберите стратегию стрелками", description)
        self.assertIn("нажмите Enter", description)

    def test_strategy_summary_reads_visible_count(self) -> None:
        widget = ProfileStrategyListWidget()
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


if __name__ == "__main__":
    unittest.main()
