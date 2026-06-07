from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class ProgramSettingsFastSnapshotTests(unittest.TestCase):
    def test_fast_snapshot_reads_only_settings_json_values(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        defender_cls = Mock()
        max_blocked = Mock(return_value=True)
        settings = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": True,
                "defender_disabled": True,
                "max_blocked": True,
            },
            "window": {
                "hide_to_tray_on_minimize_close": False,
            },
        }

        with (
            patch("settings.store.read_settings", return_value=settings) as read_settings,
            patch("windows_features.defender_manager.WindowsDefenderManager", defender_cls),
            patch("windows_features.max_blocker.is_max_blocked", max_blocked),
        ):
            snapshot = ProgramSettingsRuntimeService().read_snapshot()

        self.assertTrue(snapshot.auto_dpi_enabled)
        self.assertTrue(snapshot.gui_autostart_enabled)
        self.assertFalse(snapshot.hide_to_tray_on_minimize_close)
        self.assertTrue(snapshot.defender_disabled)
        self.assertTrue(snapshot.max_blocked)
        read_settings.assert_called_once_with()
        defender_cls.assert_not_called()
        max_blocked.assert_not_called()

    def test_windows_feature_snapshot_updates_only_heavy_values(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        service = ProgramSettingsRuntimeService()
        settings = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": False,
                "defender_disabled": False,
                "max_blocked": False,
            },
            "window": {
                "hide_to_tray_on_minimize_close": True,
            },
        }

        with (
            patch("settings.store.read_settings", return_value=settings),
        ):
            fast_snapshot = service.refresh_fast()

        with (
            patch("settings.store.get_dpi_autostart", side_effect=AssertionError("fast settings were reread")),
            patch(
                "settings.store.get_gui_autostart_enabled",
                side_effect=AssertionError("fast settings were reread"),
            ),
            patch(
                "settings.store.get_hide_to_tray_on_minimize_close",
                side_effect=AssertionError("fast settings were reread"),
            ),
            patch("windows_features.defender_manager.WindowsDefenderManager") as defender_cls,
            patch("windows_features.max_blocker.is_max_blocked", return_value=True),
        ):
            defender_cls.return_value.is_defender_disabled.return_value = True
            heavy_snapshot = service.refresh_system_status()

        self.assertTrue(fast_snapshot.auto_dpi_enabled)
        self.assertTrue(heavy_snapshot.auto_dpi_enabled)
        self.assertFalse(heavy_snapshot.gui_autostart_enabled)
        self.assertTrue(heavy_snapshot.hide_to_tray_on_minimize_close)
        self.assertTrue(heavy_snapshot.defender_disabled)
        self.assertTrue(heavy_snapshot.max_blocked)

    def test_system_status_refresh_does_not_restore_stale_fast_fields(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        service = ProgramSettingsRuntimeService()
        enabled_settings = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": True,
                "defender_disabled": False,
                "max_blocked": False,
            },
            "window": {"hide_to_tray_on_minimize_close": False},
        }
        disabled_settings = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": False,
                "defender_disabled": False,
                "max_blocked": False,
            },
            "window": {"hide_to_tray_on_minimize_close": False},
        }

        with patch("settings.store.read_settings", return_value=enabled_settings):
            service.refresh_fast()

        def disable_autostart_during_system_check() -> bool:
            with patch("settings.store.read_settings", return_value=disabled_settings):
                service.refresh_fast()
            return True

        with (
            patch.object(
                ProgramSettingsRuntimeService,
                "_read_defender_disabled",
                side_effect=disable_autostart_during_system_check,
            ),
            patch.object(ProgramSettingsRuntimeService, "_read_max_blocked", return_value=False),
        ):
            snapshot = service.refresh_system_status()

        self.assertFalse(snapshot.gui_autostart_enabled)
        self.assertTrue(snapshot.defender_disabled)

    def test_load_snapshot_refreshes_settings_json_instead_of_old_cached_snapshot(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        service = ProgramSettingsRuntimeService()
        with (
            patch(
                "settings.store.read_settings",
                side_effect=[
                    {
                        "program": {
                            "dpi_autostart": True,
                            "gui_autostart_enabled": False,
                            "defender_disabled": False,
                            "max_blocked": False,
                        },
                        "window": {"hide_to_tray_on_minimize_close": False},
                    },
                    {
                        "program": {
                            "dpi_autostart": True,
                            "gui_autostart_enabled": True,
                            "defender_disabled": False,
                            "max_blocked": False,
                        },
                        "window": {"hide_to_tray_on_minimize_close": False},
                    },
                ],
            ) as read_settings,
        ):
            first = service.load_snapshot()
            second = service.load_snapshot()

        self.assertFalse(first.gui_autostart_enabled)
        self.assertTrue(second.gui_autostart_enabled)
        self.assertEqual(read_settings.call_count, 2)

    def test_attach_program_settings_runtime_applies_ready_snapshot_immediately(self) -> None:
        from program_settings.runtime import attach_program_settings_runtime

        applied = []
        runtime_service = SimpleNamespace(
            subscribe=Mock(side_effect=lambda callback, emit_initial=False: callback("ready") or (lambda: None)),
        )

        attach_program_settings_runtime(
            SimpleNamespace(_program_settings_runtime_attached=False),
            runtime_service=runtime_service,
            apply_snapshot_fn=applied.append,
        )

        runtime_service.subscribe.assert_called_once()
        self.assertTrue(runtime_service.subscribe.call_args.kwargs["emit_initial"])
        self.assertEqual(applied, ["ready"])

    def test_load_program_settings_snapshot_refreshes_fast_settings_after_save(self) -> None:
        from program_settings.runtime import load_program_settings_snapshot

        runtime_service = SimpleNamespace(
            read_snapshot=Mock(return_value="stale"),
            refresh_fast=Mock(return_value="fresh"),
        )

        self.assertEqual(load_program_settings_snapshot(runtime_service), "fresh")
        runtime_service.refresh_fast.assert_called_once_with()
        runtime_service.read_snapshot.assert_not_called()

    def test_gui_autostart_is_not_window_level_ui_state(self) -> None:
        import app.state_store as state_store

        self.assertNotIn("autostart_enabled", state_store.AppUiState.__dataclass_fields__)
        self.assertFalse(hasattr(state_store.MainWindowStateStore, "set_autostart"))
        self.assertFalse(hasattr(state_store.AppRuntimeState, "is_autostart_enabled"))
        self.assertFalse(hasattr(state_store.AppRuntimeState, "set_autostart"))


if __name__ == "__main__":
    unittest.main()
