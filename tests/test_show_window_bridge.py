from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtCore import QCoreApplication

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class ShowWindowBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_show_request_prefers_tray_manager(self) -> None:
        from startup.show_window_bridge import ShowWindowBridge

        tray_manager = Mock()
        window = SimpleNamespace(
            visual_state=SimpleNamespace(tray_manager=tray_manager),
        )
        bridge = ShowWindowBridge(window)

        with patch("ui.window_adapter.show_window") as show_window:
            bridge._handle_show_window()

        tray_manager.show_window.assert_called_once_with()
        show_window.assert_not_called()

    def test_show_request_uses_common_window_adapter_without_tray_manager(self) -> None:
        from startup.show_window_bridge import ShowWindowBridge

        window = SimpleNamespace(
            visual_state=SimpleNamespace(tray_manager=None),
            showNormal=Mock(),
            activateWindow=Mock(),
            raise_=Mock(),
        )
        bridge = ShowWindowBridge(window)

        with patch("ui.window_adapter.show_window") as show_window:
            bridge._handle_show_window()

        show_window.assert_called_once_with(window)
        window.showNormal.assert_not_called()
        window.activateWindow.assert_not_called()
        window.raise_.assert_not_called()

    def test_signal_emission_reaches_handler(self) -> None:
        from startup.show_window_bridge import ShowWindowBridge

        tray_manager = Mock()
        window = SimpleNamespace(
            visual_state=SimpleNamespace(tray_manager=tray_manager),
        )
        bridge = ShowWindowBridge(window)
        bridge.show_requested.connect(bridge._handle_show_window)

        bridge.show_requested.emit()

        tray_manager.show_window.assert_called_once_with()

    def test_start_wires_watcher_to_signal(self) -> None:
        from startup.show_window_bridge import ShowWindowBridge

        tray_manager = Mock()
        window = SimpleNamespace(visual_state=SimpleNamespace(tray_manager=tray_manager))
        bridge = ShowWindowBridge(window)

        with patch(
            "startup.show_window_bridge.start_show_event_watcher",
            return_value=Mock(),
        ) as start_watcher:
            self.assertTrue(bridge.start())

        start_watcher.assert_called_once()
        # Переданный наблюдателю callback должен доводить сигнал до обработчика
        (watcher_callback,) = start_watcher.call_args.args
        watcher_callback()
        tray_manager.show_window.assert_called_once_with()

    def test_start_reports_failure_when_watcher_not_started(self) -> None:
        from startup.show_window_bridge import ShowWindowBridge

        window = SimpleNamespace(visual_state=SimpleNamespace(tray_manager=Mock()))
        bridge = ShowWindowBridge(window)

        with patch(
            "startup.show_window_bridge.start_show_event_watcher",
            return_value=None,
        ):
            self.assertFalse(bridge.start())


if __name__ == "__main__":
    unittest.main()
