from __future__ import annotations

import ast
import gc
import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from ui.close_dialog import CloseDialog
from ui.fluent_dialog import MessageBox


ROOT = Path(__file__).resolve().parents[1]


class _EventFilterTrackingParent(QWidget):
    def installEventFilter(self, event_filter) -> None:  # noqa: N802
        self.__dict__.setdefault("installed_filters", []).append(event_filter)
        super().installEventFilter(event_filter)

    def removeEventFilter(self, event_filter) -> None:  # noqa: N802
        self.__dict__.setdefault("removed_filters", []).append(event_filter)
        super().removeEventFilter(event_filter)


class FluentDialogLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _parent(self) -> _EventFilterTrackingParent:
        parent = _EventFilterTrackingParent()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)
        return parent

    def test_close_dialog_detaches_from_parent_event_filter_after_exec(self) -> None:
        parent = self._parent()
        dialog = CloseDialog(parent, launch_running=True)
        self.addCleanup(dialog.deleteLater)

        self.assertIn(dialog, parent.installed_filters)
        QTimer.singleShot(0, dialog.reject)
        self.assertEqual(dialog.exec(), 0)
        self.assertIn(dialog, parent.removed_filters)
        self.assertIsNone(dialog._mask_event_filter_host)

    def test_standard_message_box_uses_same_managed_lifecycle(self) -> None:
        parent = self._parent()
        dialog = MessageBox("Проверка", "Текст", parent)
        self.addCleanup(dialog.deleteLater)

        self.assertIn(dialog, parent.installed_filters)
        QTimer.singleShot(0, dialog.reject)
        self.assertEqual(dialog.exec(), 0)
        self.assertIn(dialog, parent.removed_filters)

    def test_closed_dialog_does_not_receive_later_parent_events(self) -> None:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)
        uncaught: list[BaseException] = []
        previous_excepthook = sys.excepthook
        sys.excepthook = lambda exc_type, exc, traceback: uncaught.append(exc)
        try:
            for width in (660, 680):
                dialog = CloseDialog(parent, launch_running=True)
                QTimer.singleShot(0, dialog.reject)
                self.assertEqual(dialog.exec(), 0)
                del dialog
                gc.collect()
                parent.resize(width, 480)
                self.app.processEvents()
        finally:
            sys.excepthook = previous_excepthook

        self.assertEqual(uncaught, [])

    def test_application_does_not_import_unmanaged_message_boxes(self) -> None:
        offenders: list[str] = []
        for path in (ROOT / "src").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module != "qfluentwidgets":
                    continue
                if any(alias.name in {"MessageBox", "MessageBoxBase"} for alias in node.names):
                    offenders.append(path.relative_to(ROOT).as_posix())

        self.assertEqual(offenders, ["src/ui/fluent_dialog.py"])


if __name__ == "__main__":
    unittest.main()
