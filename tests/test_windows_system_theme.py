from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


class WindowsSystemThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_reads_windows_apps_theme_from_personalize_registry_value(self) -> None:
        import ui.windows_system_theme as system_theme

        fake_winreg = SimpleNamespace(HKEY_CURRENT_USER=object())
        with (
            patch.object(system_theme.sys, "platform", "win32"),
            patch.dict(sys.modules, {"winreg": fake_winreg}),
        ):
            self.assertEqual(
                system_theme.read_windows_apps_theme(read_dword=lambda *_args: 0),
                "dark",
            )
            self.assertEqual(
                system_theme.read_windows_apps_theme(read_dword=lambda *_args: 1),
                "light",
            )

    def test_ignores_non_windows_apps_theme(self) -> None:
        import ui.windows_system_theme as system_theme

        with patch.object(system_theme.sys, "platform", "linux"):
            self.assertIsNone(system_theme.read_windows_apps_theme(read_dword=lambda *_args: 1))

    def test_detects_native_windows_theme_messages(self) -> None:
        import ui.windows_system_theme as system_theme

        self.assertTrue(system_theme.is_windows_theme_change_message(system_theme.WM_SETTINGCHANGE))
        self.assertTrue(system_theme.is_windows_theme_change_message(system_theme.WM_DWMCOLORIZATIONCOLORCHANGED))
        self.assertFalse(system_theme.is_windows_theme_change_message(0x0200))

    def test_apply_theme_skips_when_display_mode_is_not_auto(self) -> None:
        import ui.windows_system_theme as system_theme

        set_theme = Mock()

        applied = system_theme.apply_windows_system_theme_if_auto(
            object(),
            display_mode_loader=lambda: "dark",
            system_theme_reader=lambda: "light",
            set_theme_func=set_theme,
            theme_enum=SimpleNamespace(DARK="dark-theme", LIGHT="light-theme"),
            is_dark_theme_func=lambda: True,
            background_applier=Mock(),
            refresh_flusher=Mock(return_value=0),
        )

        self.assertFalse(applied)
        set_theme.assert_not_called()

    def test_apply_theme_uses_system_value_when_display_mode_is_auto(self) -> None:
        import ui.windows_system_theme as system_theme

        window = SimpleNamespace(update=Mock())
        set_theme = Mock()
        background_applier = Mock()
        refresh_flusher = Mock(return_value=3)

        applied = system_theme.apply_windows_system_theme_if_auto(
            window,
            display_mode_loader=lambda: "system",
            system_theme_reader=lambda: "light",
            set_theme_func=set_theme,
            theme_enum=SimpleNamespace(DARK="dark-theme", LIGHT="light-theme"),
            is_dark_theme_func=lambda: True,
            background_applier=background_applier,
            refresh_flusher=refresh_flusher,
        )

        self.assertTrue(applied)
        set_theme.assert_called_once_with("light-theme")
        background_applier.assert_called_once_with(window)
        refresh_flusher.assert_called_once_with(window)
        window.update.assert_called_once()

    def test_apply_theme_skips_repaint_when_qfluent_theme_already_matches(self) -> None:
        import ui.windows_system_theme as system_theme

        set_theme = Mock()
        background_applier = Mock()
        refresh_flusher = Mock(return_value=0)

        applied = system_theme.apply_windows_system_theme_if_auto(
            object(),
            display_mode_loader=lambda: "system",
            system_theme_reader=lambda: "dark",
            set_theme_func=set_theme,
            theme_enum=SimpleNamespace(DARK="dark-theme", LIGHT="light-theme"),
            is_dark_theme_func=lambda: True,
            background_applier=background_applier,
            refresh_flusher=refresh_flusher,
        )

        self.assertFalse(applied)
        set_theme.assert_not_called()
        background_applier.assert_not_called()
        refresh_flusher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
