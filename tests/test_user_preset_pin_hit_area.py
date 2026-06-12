from __future__ import annotations

import unittest

from PyQt6.QtCore import QPoint, QRect

from ui.presets_menu.delegate import PresetListDelegate


class UserPresetPinHitAreaTests(unittest.TestCase):
    def test_pin_action_uses_button_sized_hit_area(self) -> None:
        delegate = PresetListDelegate.__new__(PresetListDelegate)
        row_rect = QRect(0, 0, 320, 44)
        visual_pin_rect = PresetListDelegate._pin_rect(delegate, row_rect, "preset", 0)

        self.assertIsNotNone(visual_pin_rect)
        click_near_visible_pin = QPoint(visual_pin_rect.right() + 6, visual_pin_rect.center().y())

        action = PresetListDelegate._action_at(
            delegate,
            row_rect,
            "preset",
            False,
            False,
            0,
            click_near_visible_pin,
        )

        self.assertEqual(action, "pin")


if __name__ == "__main__":
    unittest.main()
