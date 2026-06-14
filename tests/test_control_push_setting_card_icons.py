from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, PushSettingCard

from presets.ui.control.shared_builders import ACTION_CARD_BUTTON_WIDTH, build_push_setting_card_common


class ControlPushSettingCardIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_fluent_icon_is_converted_for_push_setting_card_button(self) -> None:
        card = build_push_setting_card_common(
            push_setting_card_cls=PushSettingCard,
            button_text="Открыть",
            icon=QIcon(),
            title_text="Проверка",
            content_text="",
            on_click=lambda: None,
            button_icon_name=FluentIcon.LINK,
        )

        self.assertFalse(card.button.icon().isNull())

    def test_action_card_buttons_have_same_width_for_different_text(self) -> None:
        open_card = build_push_setting_card_common(
            push_setting_card_cls=PushSettingCard,
            button_text="Открыть",
            icon=QIcon(),
            title_text="Тест соединения",
            content_text="",
            on_click=lambda: None,
        )
        reset_card = build_push_setting_card_common(
            push_setting_card_cls=PushSettingCard,
            button_text="Сбросить",
            icon=QIcon(),
            title_text="Сбросить сеть Windows",
            content_text="",
            on_click=lambda: None,
        )

        self.assertEqual(open_card.button.width(), ACTION_CARD_BUTTON_WIDTH)
        self.assertEqual(reset_card.button.width(), ACTION_CARD_BUTTON_WIDTH)
        self.assertEqual(open_card.button.width(), reset_card.button.width())

    def test_themed_card_icon_is_loaded_after_first_paint(self) -> None:
        from presets.ui.control.shared_builders import build_deferred_themed_push_setting_card_common

        scheduled: list[tuple[int, object]] = []
        icon = QIcon(QPixmap(1, 1))
        with patch(
            "presets.ui.control.shared_builders.get_themed_qta_icon",
            return_value=icon,
        ) as get_icon, patch(
            "presets.ui.control.shared_builders.QTimer.singleShot",
            side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        ):
            card = build_deferred_themed_push_setting_card_common(
                push_setting_card_cls=PushSettingCard,
                button_text="Открыть",
                icon_name="fa5s.wifi",
                icon_color="#60cdff",
                title_text="Проверка",
                content_text="",
                on_click=lambda: None,
            )

            get_icon.assert_not_called()
            self.assertTrue(card.iconLabel.icon.isNull())
            self.assertEqual(len(scheduled), 1)
            self.assertGreaterEqual(scheduled[0][0], 200)
            scheduled[0][1]()

        get_icon.assert_called_once_with("fa5s.wifi", color="#60cdff")
        self.assertFalse(card.iconLabel.icon.isNull())


if __name__ == "__main__":
    unittest.main()
