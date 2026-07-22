from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class _FakeComObject:
    """Пустышка с динамическими атрибутами для узлов COM-задачи."""

    def __init__(self):
        object.__setattr__(self, "attrs", {})

    def __setattr__(self, name, value):
        self.attrs[name] = value

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, "attrs")[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _FakeComCollection:
    def __init__(self):
        self.created: list[tuple[int, _FakeComObject]] = []

    def Create(self, item_type: int):
        item = _FakeComObject()
        self.created.append((int(item_type), item))
        return item


class _FakeTaskDefinition:
    def __init__(self):
        self.RegistrationInfo = _FakeComObject()
        self.Triggers = _FakeComCollection()
        self.Actions = _FakeComCollection()
        self.Principal = _FakeComObject()
        self.Settings = _FakeComObject()


class _FakeTaskFolder:
    def __init__(self):
        self.registered: list[tuple] = []
        self.deleted: list[str] = []
        self.tasks: dict[str, object] = {}

    def RegisterTaskDefinition(self, name, definition, flags, user, password, logon_type):
        self.registered.append((name, definition, flags, user, password, logon_type))

    def GetTask(self, name):
        try:
            return self.tasks[name]
        except KeyError as exc:
            raise OSError(f"task not found: {name}") from exc

    def DeleteTask(self, name, flags):
        if name not in self.tasks:
            raise OSError(f"task not found: {name}")
        del self.tasks[name]
        self.deleted.append(name)


class _FakeScheduler:
    def __init__(self):
        self.folder = _FakeTaskFolder()
        self.task_definitions: list[_FakeTaskDefinition] = []

    def Connect(self):
        pass

    def GetFolder(self, path: str):
        return self.folder

    def NewTask(self, flags: int):
        definition = _FakeTaskDefinition()
        self.task_definitions.append(definition)
        return definition


class _FakeToggle:
    def __init__(self, checked: bool = False):
        self._checked = bool(checked)
        self.set_calls: list[tuple[bool, bool]] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool, block_signals: bool = False):  # noqa: N802
        self.set_calls.append((bool(checked), bool(block_signals)))
        self._checked = bool(checked)


class GuiAutostartContractTests(unittest.TestCase):
    def test_registers_elevated_logon_task_in_scheduler(self) -> None:
        from autostart import scheduled_task_api

        scheduler = _FakeScheduler()
        exe_path = r"C:\Program Files\Zapret\_internal\Zapret.exe"

        with patch.object(
            scheduled_task_api,
            "_connect_scheduler",
            return_value=scheduler,
        ):
            result = scheduled_task_api.create_or_update_autostart_task(exe_path)

        self.assertTrue(result)

        definition = scheduler.task_definitions[0]

        # Триггер: вход текущего пользователя в систему
        (trigger_type, trigger), = definition.Triggers.created
        self.assertEqual(trigger_type, scheduled_task_api.TASK_TRIGGER_LOGON)

        # Действие: запуск exe в трее
        (action_type, action), = definition.Actions.created
        self.assertEqual(action_type, scheduled_task_api.TASK_ACTION_EXEC)
        self.assertEqual(action.Path, exe_path)
        self.assertEqual(action.Arguments, "--tray")
        self.assertEqual(action.WorkingDirectory, r"C:\Program Files\Zapret")

        # Ключ решения: запуск с наивысшими правами без UAC-запроса.
        # Ярлык автозагрузки для requireAdministrator-exe Windows молча игнорирует.
        self.assertEqual(
            definition.Principal.RunLevel,
            scheduled_task_api.TASK_RUNLEVEL_HIGHEST,
        )
        self.assertEqual(
            definition.Principal.LogonType,
            scheduled_task_api.TASK_LOGON_INTERACTIVE_TOKEN,
        )

        # Дефолты планировщика ломают GUI: батарея и лимит времени выполнения
        self.assertFalse(definition.Settings.DisallowStartIfOnBatteries)
        self.assertFalse(definition.Settings.StopIfGoingOnBatteries)
        self.assertEqual(definition.Settings.ExecutionTimeLimit, "PT0S")

        (name, registered_def, flags, _user, _password, logon_type), = scheduler.folder.registered
        self.assertEqual(name, scheduled_task_api.AUTOSTART_TASK_NAME)
        self.assertIs(registered_def, definition)
        self.assertEqual(flags, scheduled_task_api.TASK_CREATE_OR_UPDATE)
        self.assertEqual(logon_type, scheduled_task_api.TASK_LOGON_INTERACTIVE_TOKEN)

    def test_rejects_flat_or_source_autostart_target(self) -> None:
        from autostart import scheduled_task_api

        with patch.object(scheduled_task_api, "_connect_scheduler") as connect_scheduler:
            result = scheduled_task_api.create_or_update_autostart_task(
                r"C:\Program Files\Zapret\Zapret.exe"
            )

        self.assertFalse(result)
        connect_scheduler.assert_not_called()

    def test_enable_gui_autostart_creates_task_and_removes_legacy_shortcut(self) -> None:
        from autostart.public import enable_gui_autostart
        from config.runtime_layout import APPLICATION_PATHS

        with (
            patch("autostart.startup_shortcut_api.delete_startup_shortcut", return_value=True) as delete_shortcut,
            patch("autostart.scheduled_task_api.create_or_update_autostart_task", return_value=True) as create_task,
        ):
            result = enable_gui_autostart()

        self.assertTrue(result.success)
        delete_shortcut.assert_called_once()
        create_task.assert_called_once_with(str(APPLICATION_PATHS.executable))

    def test_enable_gui_autostart_returns_readable_error_message(self) -> None:
        from autostart.public import enable_gui_autostart

        with (
            patch("autostart.startup_shortcut_api.delete_startup_shortcut", return_value=False),
            patch("autostart.scheduled_task_api.create_or_update_autostart_task", return_value=False),
        ):
            result = enable_gui_autostart()

        self.assertFalse(result.success)
        self.assertFalse(result.restart_requested)
        self.assertIn("Не удалось включить автозапуск", result.message)

    def test_disable_gui_autostart_removes_task_and_legacy_shortcut(self) -> None:
        from autostart.public import disable_gui_autostart

        with (
            patch("autostart.scheduled_task_api.delete_autostart_task", return_value=True),
            patch("autostart.startup_shortcut_api.delete_startup_shortcut", return_value=True),
        ):
            result = disable_gui_autostart()

        self.assertTrue(result.success)
        self.assertEqual(result.removed_count, 2)

    def test_migration_is_noop_when_autostart_disabled(self) -> None:
        from autostart.public import ensure_gui_autostart_migrated

        with (
            patch("settings.store.get_gui_autostart_enabled", return_value=False),
            patch("autostart.scheduled_task_api.create_or_update_autostart_task") as create_task,
        ):
            migrated = ensure_gui_autostart_migrated()

        self.assertFalse(migrated)
        create_task.assert_not_called()

    def test_migration_is_noop_when_task_matches_and_no_shortcut(self) -> None:
        from autostart.public import ensure_gui_autostart_migrated
        from config.runtime_layout import APPLICATION_PATHS

        shortcut_path = Path(r"C:\nonexistent\ZapretGUI.lnk")
        task_path = str(APPLICATION_PATHS.executable).swapcase()
        with (
            patch("settings.store.get_gui_autostart_enabled", return_value=True),
            patch(
                "autostart.scheduled_task_api.get_autostart_task_action",
                return_value=(task_path, "--tray"),
            ),
            patch(
                "autostart.startup_shortcut_api.get_startup_shortcut_path",
                return_value=shortcut_path,
            ),
            patch("autostart.scheduled_task_api.create_or_update_autostart_task") as create_task,
        ):
            migrated = ensure_gui_autostart_migrated()

        self.assertFalse(migrated)
        create_task.assert_not_called()

    def test_migration_replaces_legacy_shortcut_with_task(self) -> None:
        from autostart.public import ensure_gui_autostart_migrated
        from config.runtime_layout import APPLICATION_PATHS

        with tempfile.TemporaryDirectory() as tmp_dir:
            legacy_shortcut = Path(tmp_dir) / "ZapretGUI.lnk"
            legacy_shortcut.write_bytes(b"legacy")

            with (
                patch("settings.store.get_gui_autostart_enabled", return_value=True),
                patch("autostart.scheduled_task_api.get_autostart_task_action", return_value=None),
                patch(
                    "autostart.startup_shortcut_api.get_startup_shortcut_path",
                    return_value=legacy_shortcut,
                ),
                patch(
                    "autostart.scheduled_task_api.create_or_update_autostart_task",
                    return_value=True,
                ) as create_task,
            ):
                migrated = ensure_gui_autostart_migrated()

            self.assertTrue(migrated)
            create_task.assert_called_once_with(str(APPLICATION_PATHS.executable))
            self.assertFalse(legacy_shortcut.exists())

    def test_migration_replaces_task_with_wrong_arguments(self) -> None:
        from autostart.public import ensure_gui_autostart_migrated
        from config.runtime_layout import APPLICATION_PATHS

        shortcut_path = Path(r"C:\nonexistent\ZapretGUI.lnk")
        with (
            patch("settings.store.get_gui_autostart_enabled", return_value=True),
            patch(
                "autostart.scheduled_task_api.get_autostart_task_action",
                return_value=(str(APPLICATION_PATHS.executable), ""),
            ),
            patch(
                "autostart.startup_shortcut_api.get_startup_shortcut_path",
                return_value=shortcut_path,
            ),
            patch(
                "autostart.scheduled_task_api.create_or_update_autostart_task",
                return_value=True,
            ) as create_task,
            patch("autostart.startup_shortcut_api.delete_startup_shortcut"),
        ):
            migrated = ensure_gui_autostart_migrated()

        self.assertTrue(migrated)
        create_task.assert_called_once_with(str(APPLICATION_PATHS.executable))

    def test_autostart_error_notification_payload_is_user_readable(self) -> None:
        from autostart.ui.notifications import build_autostart_error_notification

        payload = build_autostart_error_notification("COM raw details")

        self.assertEqual(payload["level"], "error")
        self.assertEqual(payload["title"], "Автозапуск не включён")
        self.assertIn("COM raw details", payload["content"])
        self.assertEqual(payload["source"], "autostart.gui")
        self.assertEqual(payload["queue"], "immediate")

    def test_gui_autostart_lives_in_program_settings_snapshot(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

        settings = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": True,
                "defender_disabled": False,
                "max_blocked": False,
                "russian_state_media_blocked": False,
            },
            "window": {
                "tray_close_mode": "normal",
            },
        }
        with (
            patch("settings.store.read_settings", return_value=settings),
            patch("windows_features.defender_manager.WindowsDefenderManager") as defender_cls,
            patch("windows_features.max_blocker.is_max_blocked", return_value=False),
        ):
            defender_cls.return_value.is_defender_disabled.return_value = False
            snapshot = ProgramSettingsRuntimeService().read_snapshot()

        self.assertTrue(snapshot.gui_autostart_enabled)
        self.assertEqual(snapshot.revision[1], True)

    def test_gui_autostart_toggle_uses_program_settings_action(self) -> None:
        from autostart.public import GuiAutostartResult
        from program_settings.commands import set_gui_autostart_enabled

        with (
            patch("autostart.public.enable_gui_autostart", return_value=GuiAutostartResult(success=True)) as enable,
            patch("autostart.public.save_gui_autostart_enabled", return_value=True) as save,
        ):
            result = set_gui_autostart_enabled(True)

        enable.assert_called_once()
        save.assert_called_once_with(True)
        self.assertEqual(result.level, "success")
        self.assertIsNone(result.revert_checked)

    def test_gui_autostart_snapshot_sync_blocks_toggle_signal(self) -> None:
        from core.runtime.program_settings_runtime_service import ProgramSettingsSnapshot
        from presets.ui.control.control_page_runtime_shared import apply_program_settings_toggles

        toggle = _FakeToggle(False)
        snapshot = ProgramSettingsSnapshot(
            revision=(False, True, "normal", False, False, False),
            auto_dpi_enabled=False,
            gui_autostart_enabled=True,
            tray_close_mode="normal",
            defender_disabled=False,
            max_blocked=False,
            russian_state_media_blocked=False,
        )

        apply_program_settings_toggles(snapshot, gui_autostart_toggle=toggle)

        self.assertEqual(toggle.set_calls, [(True, True)])

    def test_gui_autostart_toggle_is_top_program_settings_row_for_both_modes(self) -> None:
        import inspect

        import presets.ui.control.zapret1.sections_build as winws1_sections
        import presets.ui.control.zapret2.sections_build as winws2_sections

        for source in (
            inspect.getsource(winws1_sections.build_winws1_pages_settings_sections),
            inspect.getsource(winws2_sections.build_winws2_pages_settings_sections),
        ):
            self.assertIn("gui_autostart_toggle", source)
            self.assertLess(
                source.index("program_settings_card.addSettingCard(gui_autostart_toggle)"),
                source.index("program_settings_card.addSettingCard(auto_dpi_toggle)"),
            )

    def test_autostart_is_no_longer_registered_as_standalone_page(self) -> None:
        import ui.pages as pages
        from app.page_names import PageName
        from app.search_index import SEARCH_ENTRIES
        from ui.navigation.schema import PAGE_ROUTE_SPECS
        from ui.page_composition import PAGE_DEPS_BUILDERS

        self.assertFalse(hasattr(PageName, "AUTOSTART"))
        self.assertNotIn("AutostartPage", pages.__all__)
        self.assertFalse(
            any(entry.entry_id.startswith("autostart.") for entry in SEARCH_ENTRIES)
        )
        self.assertFalse(
            any(
                str(getattr(page_name, "name", "")) == "AUTOSTART"
                for page_name in (*PAGE_ROUTE_SPECS.keys(), *PAGE_DEPS_BUILDERS.keys())
            )
        )


if __name__ == "__main__":
    unittest.main()
