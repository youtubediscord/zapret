from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


class TrayMenuContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
