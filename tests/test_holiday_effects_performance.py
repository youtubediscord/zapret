from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from ui.holiday_effects import _Snowflake, SnowflakesOverlay


class HolidayEffectsPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_snowflake_motion_rect_covers_old_and_new_positions(self) -> None:
        host = QWidget()
        overlay = SnowflakesOverlay(host)
        flake = _Snowflake(40.0, 50.0)
        flake.size = 4.0

        self.assertTrue(hasattr(overlay, "_snowflake_paint_rect"))
        self.assertTrue(hasattr(overlay, "_snowflake_motion_rect"))

        old_rect = overlay._snowflake_paint_rect(flake)
        flake.x = 44.0
        flake.y = 57.0
        new_rect = overlay._snowflake_paint_rect(flake)

        dirty_rect = overlay._snowflake_motion_rect(flake, 40.0, 50.0)

        self.assertTrue(dirty_rect.contains(old_rect))
        self.assertTrue(dirty_rect.contains(new_rect))
        self.assertLess(dirty_rect.width(), overlay.width() or 640)


if __name__ == "__main__":
    unittest.main()
