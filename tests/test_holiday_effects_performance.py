from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from app.state_store import AppUiState, MainWindowStateStore
from main.window_state_actions import WindowStateActions
from ui.holiday_effects import _Snowflake, GarlandOverlay, HolidayEffectsManager, SnowflakesOverlay
from ui.window_appearance_state import apply_garland_enabled, apply_snowflakes_enabled, on_animations_changed


class _CountingSnowflakesOverlay(SnowflakesOverlay):
    def __init__(self, parent: QWidget):
        self.raise_count = 0
        super().__init__(parent)

    def raise_(self) -> None:
        self.raise_count += 1
        super().raise_()


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

    def test_snowflake_pixmap_is_reused_for_same_visual_bucket(self) -> None:
        host = QWidget()
        overlay = SnowflakesOverlay(host)
        flake = _Snowflake(40.0, 50.0)
        flake.size = 3.1
        flake.opacity = 0.31

        first = overlay._snowflake_pixmap(flake, 1.0)
        second = overlay._snowflake_pixmap(flake, 1.0)

        self.assertFalse(first.isNull())
        self.assertEqual(first.cacheKey(), second.cacheKey())
        self.assertEqual(len(overlay._flake_pixmap_cache), 1)

    def test_snowflake_density_stays_bounded_on_large_windows(self) -> None:
        host = QWidget()
        overlay = SnowflakesOverlay(host)

        self.assertLessEqual(overlay._max_flake_count(1920, 1080), 150)
        self.assertLessEqual(overlay._initial_flake_count(1920, 1080), 70)

    def test_holiday_effects_do_not_pause_for_ui_work(self) -> None:
        self.assertFalse(hasattr(SnowflakesOverlay, "suspend_for_ui_work"))
        self.assertFalse(hasattr(GarlandOverlay, "suspend_for_ui_work"))

    def test_snowflake_animation_does_not_raise_overlay_every_frame(self) -> None:
        host = QWidget()
        host.resize(640, 480)
        overlay = _CountingSnowflakesOverlay(host)
        overlay.set_enabled(True)
        overlay.raise_count = 0

        overlay._animate()

        self.assertEqual(overlay.raise_count, 0)

    def test_holiday_manager_pauses_and_resumes_timers_without_disabling_effects(self) -> None:
        host = QWidget()
        host.resize(640, 480)
        manager = HolidayEffectsManager(host)

        manager.set_garland_enabled(True)
        manager.set_snowflakes_enabled(True)

        self.assertTrue(manager._garland._timer.isActive())
        self.assertTrue(manager._snowflakes._animate_timer.isActive())
        self.assertTrue(manager._snowflakes._spawn_timer.isActive())

        manager.set_animation_active(False)

        self.assertTrue(manager._garland.is_enabled())
        self.assertTrue(manager._snowflakes.is_enabled())
        self.assertFalse(manager._garland._timer.isActive())
        self.assertFalse(manager._snowflakes._animate_timer.isActive())
        self.assertFalse(manager._snowflakes._spawn_timer.isActive())

        manager.set_animation_active(True)

        self.assertTrue(manager._garland._timer.isActive())
        self.assertTrue(manager._snowflakes._animate_timer.isActive())
        self.assertTrue(manager._snowflakes._spawn_timer.isActive())

    def test_disabling_holiday_effects_does_not_create_overlay_manager(self) -> None:
        host = QWidget()
        host.visual_state = SimpleNamespace(holiday_effects=None)

        apply_garland_enabled(host, False)
        apply_snowflakes_enabled(host, False)

        self.assertIsNone(host.visual_state.holiday_effects)

    def test_animation_master_disables_existing_holiday_overlays(self) -> None:
        effects = SimpleNamespace(
            set_garland_enabled=Mock(),
            set_snowflakes_enabled=Mock(),
            set_animation_active=Mock(),
        )
        host = QWidget()
        host.visual_state = SimpleNamespace(holiday_effects=effects)

        with patch("ui.window_appearance_state.apply_window_animation_policy"):
            on_animations_changed(host, False)

        effects.set_garland_enabled.assert_called_once_with(False)
        effects.set_snowflakes_enabled.assert_called_once_with(False)
        effects.set_animation_active.assert_called_once_with(False)

    def test_window_actions_keep_holiday_overlays_off_when_animation_master_is_off(self) -> None:
        effects = SimpleNamespace(set_snowflakes_enabled=Mock())
        host = QWidget()
        host.visual_state = SimpleNamespace(holiday_effects=effects)
        store = MainWindowStateStore(AppUiState(garland_enabled=True, snowflakes_enabled=True))
        actions = WindowStateActions(host, store)

        with patch("main.window_state_actions._holiday_effects_allowed", return_value=False):
            actions.set_snowflakes_enabled(True)

        snapshot = store.snapshot()
        self.assertFalse(snapshot.garland_enabled)
        self.assertFalse(snapshot.snowflakes_enabled)
        effects.set_snowflakes_enabled.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
