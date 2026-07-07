from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TrayMenuContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_tray_launch_state_reads_runtime_snapshot_contract(self) -> None:
        from app.feature_facades.tray import TrayFeature

        runtime_feature = SimpleNamespace(
            snapshot=Mock(return_value=SimpleNamespace(running=True, phase="running"))
        )
        feature = TrayFeature(
            _deps=SimpleNamespace(),
            _runtime_feature=runtime_feature,
            _telegram_proxy_feature=SimpleNamespace(),
        )

        self.assertEqual(feature.launch_state(), (True, "running"))

    def test_legacy_right_click_callback_opens_context_menu_at_cursor(self) -> None:
        import tray

        tray.WM_CONTEXTMENU = 0x007B
        tray.WM_RBUTTONUP = 0x0205
        tray.WM_LBUTTONUP = 0x0202
        tray.WM_LBUTTONDBLCLK = 0x0203
        tray.NIN_SELECT = 0x0400
        tray.NIN_KEYSELECT = 0x0401

        manager = tray.SystemTrayManager.__new__(tray.SystemTrayManager)
        manager.show_context_menu = Mock()
        manager._schedule_visibility_toggle = Mock()

        with patch.object(tray.QTimer, "singleShot", side_effect=lambda _ms, callback: callback()):
            tray.SystemTrayManager._handle_native_callback(manager, tray.WM_RBUTTONUP, anchor_x=1, anchor_y=0)

        manager.show_context_menu.assert_called_once_with(anchor_x=None, anchor_y=None)
        manager._schedule_visibility_toggle.assert_not_called()

    def test_round_tray_menu_uses_global_hairline_fix(self) -> None:
        import tray
        from qfluentwidgets import Action, RoundMenu
        from ui.popup_menu_style import install_global_round_menu_hairline_fix

        manager = tray.SystemTrayManager.__new__(tray.SystemTrayManager)
        with patch("ui.popup_menu_style._is_windows_11_or_newer", return_value=True):
            install_global_round_menu_hairline_fix()
            menu = RoundMenu(parent=None)
        self.addCleanup(menu.deleteLater)
        menu.addAction(Action("Скрыть в трей", menu))
        before = menu.styleSheet()

        tray.SystemTrayManager._apply_menu_style(manager, menu)

        self.assertEqual(menu.styleSheet(), before)
        self.assertIn("MenuActionListWidget", menu.styleSheet())
        self.assertIn("border-color", menu.styleSheet())
        self.assertIn("zapretgui-round-menu-hairline-begin", menu.styleSheet())
        self.assertNotIn("border-left", menu.styleSheet())

    def test_native_tray_winapi_calls_have_pointer_safe_ctypes_signatures(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src" / "tray.py").read_text(encoding="utf-8")

        required_signatures = [
            "kernel32.GetModuleHandleW.restype",
            "user32.RegisterClassExW.argtypes",
            "user32.RegisterClassExW.restype",
            "user32.UnregisterClassW.argtypes",
            "user32.UnregisterClassW.restype",
            "user32.CreateWindowExW.argtypes",
            "user32.CreateWindowExW.restype",
            "user32.DestroyWindow.argtypes",
            "user32.DestroyWindow.restype",
            "user32.LoadImageW.argtypes",
            "user32.LoadImageW.restype",
            "user32.LoadIconW.argtypes",
            "user32.LoadIconW.restype",
            "user32.DestroyIcon.argtypes",
            "user32.DestroyIcon.restype",
            "shell32.Shell_NotifyIconW.argtypes",
            "shell32.Shell_NotifyIconW.restype",
        ]

        missing = [signature for signature in required_signatures if signature not in source]

        self.assertEqual(missing, [])

    def test_native_tray_message_window_unregisters_class_on_destroy(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src" / "tray.py").read_text(encoding="utf-8")

        self.assertIn("user32.UnregisterClassW(self.owner._class_name, instance)", source)

    def test_native_tray_class_name_is_unique_per_manager_instance(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src" / "tray.py").read_text(encoding="utf-8")

        self.assertIn('self._class_name = f"Zapret2TrayWindow_{os.getpid()}_{id(self):x}"', source)


if __name__ == "__main__":
    unittest.main()
