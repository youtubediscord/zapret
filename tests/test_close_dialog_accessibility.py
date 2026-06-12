import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from ui.close_dialog import CloseDialog


class CloseDialogAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _parent(self) -> QWidget:
        parent = QWidget()
        parent.resize(640, 480)
        parent.show()
        self.addCleanup(parent.deleteLater)
        return parent

    def test_close_actions_are_named_for_screen_reader_when_dpi_is_running(self) -> None:
        dialog = CloseDialog(self._parent(), launch_running=True)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.bodyLabel.accessibleName(), "Описание закрытия: DPI запущен")
        self.assertEqual(dialog.bodyLabel.property("screenReaderStateText"), "Описание закрытия: DPI запущен")
        self.assertIn("продолжит работать", dialog.bodyLabel.accessibleDescription())
        self.assertEqual(dialog.trayButton.accessibleName(), "Свернуть ZapretGUI в трей")
        self.assertEqual(dialog.trayButton.property("screenReaderStateText"), "Свернуть ZapretGUI в трей")
        self.assertIn("оставляет окно доступным из трея", dialog.trayButton.accessibleDescription())
        self.assertEqual(dialog.guiOnlyButton.accessibleName(), "Закрыть только окно ZapretGUI")
        self.assertEqual(dialog.guiOnlyButton.property("screenReaderStateText"), "Закрыть только окно ZapretGUI")
        self.assertIn("DPI продолжит работать", dialog.guiOnlyButton.accessibleDescription())
        self.assertEqual(dialog.stopDpiButton.accessibleName(), "Закрыть ZapretGUI и остановить DPI")
        self.assertEqual(dialog.stopDpiButton.property("screenReaderStateText"), "Закрыть ZapretGUI и остановить DPI")
        self.assertIn("остановит DPI", dialog.stopDpiButton.accessibleDescription())
        self.assertEqual(dialog.cancelLinkButton.accessibleName(), "Отменить закрытие ZapretGUI")
        self.assertEqual(dialog.cancelLinkButton.property("screenReaderStateText"), "Отменить закрытие ZapretGUI")

    def test_unavailable_stop_action_has_text_state_for_screen_reader(self) -> None:
        dialog = CloseDialog(self._parent(), launch_running=False)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.bodyLabel.accessibleName(), "Описание закрытия: DPI не запущен")
        self.assertEqual(dialog.bodyLabel.property("screenReaderStateText"), "Описание закрытия: DPI не запущен")
        self.assertEqual(dialog.trayButton.property("screenReaderStateText"), "Свернуть ZapretGUI в трей")
        self.assertEqual(dialog.guiOnlyButton.property("screenReaderStateText"), "Закрыть только окно ZapretGUI")
        self.assertEqual(dialog.stopDpiButton.accessibleName(), "Закрыть ZapretGUI и остановить DPI, недоступно")
        self.assertEqual(
            dialog.stopDpiButton.property("screenReaderStateText"),
            "Закрыть ZapretGUI и остановить DPI, недоступно",
        )
        self.assertEqual(dialog.cancelLinkButton.property("screenReaderStateText"), "Отменить закрытие ZapretGUI")
        self.assertIn("DPI сейчас не запущен", dialog.stopDpiButton.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
