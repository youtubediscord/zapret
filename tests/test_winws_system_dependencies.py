from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class WinwsSystemDependencyTests(unittest.TestCase):
    def test_winws1_dry_run_reports_trimmed_windows_when_wlanapi_is_missing(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            exe = root / "exe" / "winws.exe"
            exe.parent.mkdir(parents=True, exist_ok=True)
            exe.write_text("", encoding="utf-8")

            config_path = root / "tmp" / "winws1_at_config" / "selected.txt"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("--wf-tcp=443\n", encoding="utf-8")

            runner = object.__new__(Winws1StrategyRunner)
            runner.winws_exe = str(exe)
            runner.work_dir = str(root)
            runner._state_lock = threading.RLock()
            runner._prepared_preset_cache = {}
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()

            artifact = SimpleNamespace(
                validation_ok=True,
                validation_report="",
                preset_path=str(root / "selected.txt"),
                launch_args=(f"@{config_path}",),
            )

            with (
                patch(
                    "winws_runtime.runners.runner_base.StrategyRunnerBase._get_missing_windows_system_dependencies",
                    return_value=("wlanapi.dll",),
                ),
                patch("winws_runtime.runners.runner_base.should_offer_windows_server_wlanapi_install", return_value=False),
                patch("winws_runtime.runners.zapret1_runner.subprocess.run") as run_mock,
            ):
                ok = runner._run_preset_dry_run_locked(artifact)

        self.assertFalse(ok)
        run_mock.assert_not_called()
        message = runner._set_last_error.call_args.args[0]
        self.assertIn("Windows урезана", message)
        self.assertIn("wlanapi.dll", message)
        self.assertIn("winws.exe", message)

    def test_winws2_dry_run_does_not_require_wlanapi(self) -> None:
        from winws_runtime.runners.preset_runner_support import PreparedPresetArtifact
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runner = object.__new__(Winws2StrategyRunner)
            runner.winws_exe = "winws2.exe"
            runner.work_dir = str(root)
            runner._last_spawn_exit_code = None
            runner._last_spawn_stderr = ""
            runner._set_last_error = Mock()
            runner._create_startup_info = Mock(return_value=None)

            artifact = PreparedPresetArtifact(
                preset_path=str(root / "selected.txt"),
                cache_key=None,
                normalized_text="--wf-tcp-out=443\n",
                launch_args=("@original.txt",),
                validation_ok=True,
                validation_report="",
            )

            with (
                patch(
                    "winws_runtime.runners.runner_base.StrategyRunnerBase._get_missing_windows_system_dependencies",
                    return_value=("wlanapi.dll",),
                ),
                patch("winws_runtime.runners.runner_base.should_offer_windows_server_wlanapi_install", return_value=False),
                patch("winws_runtime.runners.zapret2_runner.subprocess.run") as run_mock,
            ):
                run_mock.return_value = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
                ok = runner._run_preset_dry_run_locked(
                    artifact,
                    "Preset",
                    preset_switch=False,
                    notify_failure=True,
                )

        self.assertTrue(ok)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0][0], "winws2.exe")
        runner._set_last_error.assert_not_called()

    def test_windows_server_missing_wlanapi_message_has_install_marker(self) -> None:
        from winws_runtime.health.windows_system_dependencies import WINDOWS_SERVER_WLANAPI_MARKER
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        runner = object.__new__(Winws1StrategyRunner)
        runner.winws_exe = "winws.exe"

        with patch("winws_runtime.runners.runner_base.should_offer_windows_server_wlanapi_install", return_value=True):
            message = runner._format_missing_windows_system_dependency_error(("wlanapi.dll",))

        self.assertTrue(message.startswith(WINDOWS_SERVER_WLANAPI_MARKER))
        self.assertIn("wlanapi.dll", message)
        self.assertIn("winws.exe", message)

    def test_runtime_bridge_shows_windows_server_install_buttons(self) -> None:
        from ui.runtime_ui_bridge import RuntimeUiBridge
        from winws_runtime.health.windows_system_dependencies import WINDOWS_SERVER_WLANAPI_MARKER

        payloads: list[dict] = []
        bridge = RuntimeUiBridge(
            notify=payloads.append,
            set_status=lambda _text: None,
            mark_content_changed=lambda: None,
        )

        bridge.show_launch_error(f"{WINDOWS_SERVER_WLANAPI_MARKER} не найден wlanapi.dll")

        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload["level"], "warning")
        self.assertEqual(payload["title"], "Windows Server обнаружена")
        self.assertEqual(payload["duration"], -1)
        self.assertEqual(
            [button["kind"] for button in payload["buttons"]],
            ["install_windows_server_wlanapi", "dismiss"],
        )
        self.assertEqual([button["text"] for button in payload["buttons"]], ["Установить", "Нет"])
        self.assertNotIn(WINDOWS_SERVER_WLANAPI_MARKER, payload["content"])


if __name__ == "__main__":
    unittest.main()
