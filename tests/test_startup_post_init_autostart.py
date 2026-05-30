from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class StartupPostInitAutostartTests(unittest.TestCase):
    def test_post_init_defers_launch_method_read_until_autostart_callback(self) -> None:
        from main import startup_coordinator
        from main.startup_coordinator import StartupCoordinator

        class Runtime:
            def __init__(self) -> None:
                self.autostart_calls: list[str | None] = []

            def start_autostart(self, launch_method: str | None = None) -> None:
                self.autostart_calls.append(launch_method)

        runtime = Runtime()
        window_shell = SimpleNamespace(
            start_in_tray=False,
            set_status=Mock(),
            mark_startup_core_ready=Mock(),
            mark_startup_post_init_done=Mock(),
            init_theme_manager=Mock(),
        )
        coordinator = StartupCoordinator(
            runtime_feature=runtime,
            tray_feature=SimpleNamespace(init=Mock(), is_initialized=Mock(return_value=False)),
            window_shell=window_shell,
            log_startup_metric=Mock(),
        )
        scheduled: list[tuple[int, object]] = []

        with (
            patch.object(
                startup_coordinator.QTimer,
                "singleShot",
                side_effect=lambda delay_ms, callback: scheduled.append((int(delay_ms), callback)),
            ),
            patch(
                "settings.dpi.strategy_settings.get_strategy_launch_method",
                side_effect=AssertionError("method must not be read in quick post-init"),
            ),
        ):
            coordinator._post_init_tasks()

        self.assertEqual(runtime.autostart_calls, [])
        self.assertEqual(len(scheduled), 1)
        window_shell.mark_startup_post_init_done.assert_called_once_with("post_init_scheduled:auto")

        with patch("settings.dpi.strategy_settings.get_strategy_launch_method", return_value="zapret1_mode"):
            _delay_ms, callback = scheduled.pop(0)
            callback()

        self.assertEqual(runtime.autostart_calls, ["zapret1_mode"])


if __name__ == "__main__":
    unittest.main()
