from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QWidget
from qfluentwidgets import CaptionLabel, IndeterminateProgressBar, PrimaryPushButton, PushButton


class ControlAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_management_buttons_have_screen_reader_names_and_descriptions(self) -> None:
        from presets.ui.control.shared_builders import build_mode_management_section_common

        _card, start_btn, stop_btn, stop_exit_btn, _progress, _loading = build_mode_management_section_common(
            tr_fn=lambda _key, default: default,
            caption_label_cls=CaptionLabel,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            big_action_button_cls=PrimaryPushButton,
            stop_button_cls=PushButton,
            start_key="start",
            start_default="Запустить Zapret",
            stop_key="stop",
            stop_default="Остановить winws.exe",
            stop_exit_key="stop_exit",
            stop_exit_default="Остановить и закрыть",
            on_start=lambda: None,
            on_stop=lambda: None,
            on_stop_and_exit=lambda: None,
            parent=QWidget(),
        )

        self.assertEqual(start_btn.accessibleName(), "Запустить Zapret")
        self.assertIn("Запускает", start_btn.accessibleDescription())
        self.assertEqual(stop_btn.accessibleName(), "Остановить winws.exe")
        self.assertIn("Останавливает", stop_btn.accessibleDescription())
        self.assertEqual(stop_exit_btn.accessibleName(), "Остановить и закрыть")
        self.assertIn("закрывает программу", stop_exit_btn.accessibleDescription())

    def test_stop_button_uses_square_stop_icon(self) -> None:
        from presets.ui.control.shared_builders import build_mode_management_section_common

        with patch(
            "presets.ui.control.shared_builders.get_themed_qta_icon",
            return_value=QIcon(),
        ) as get_icon:
            build_mode_management_section_common(
                tr_fn=lambda _key, default: default,
                caption_label_cls=CaptionLabel,
                indeterminate_progress_bar_cls=IndeterminateProgressBar,
                big_action_button_cls=PrimaryPushButton,
                stop_button_cls=PushButton,
                start_key="start",
                start_default="Запустить Zapret",
                stop_key="stop",
                stop_default="Остановить winws.exe",
                stop_exit_key="stop_exit",
                stop_exit_default="Остановить и закрыть",
                on_start=lambda: None,
                on_stop=lambda: None,
                on_stop_and_exit=lambda: None,
                parent=QWidget(),
            )

        get_icon.assert_called_once_with("fa5s.stop")


if __name__ == "__main__":
    unittest.main()
