from __future__ import annotations

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class _FakeCollection:
    def __init__(self, factory):
        self._factory = factory
        self.created = []

    def Create(self, item_type: int):
        item = self._factory()
        self.created.append((item_type, item))
        return item


class _FakeTaskDefinition:
    def __init__(self):
        self.RegistrationInfo = SimpleNamespace(Author="", Description="")
        self.Settings = SimpleNamespace()
        self.Principal = SimpleNamespace(
            UserId=None,
            GroupId=None,
            LogonType=None,
            RunLevel=None,
        )
        self.Triggers = _FakeCollection(lambda: SimpleNamespace(Enabled=False, UserId=None))
        self.Actions = _FakeCollection(
            lambda: SimpleNamespace(Path="", Arguments="", WorkingDirectory="")
        )


class _FakeRootFolder:
    def __init__(self):
        self.register_calls = []

    def RegisterTaskDefinition(self, *args):
        self.register_calls.append(args)
        return object()


class _FakeSchedulerService:
    def __init__(self):
        self.task_definition = _FakeTaskDefinition()
        self.root_folder = _FakeRootFolder()

    def NewTask(self, _flags: int):
        return self.task_definition

    def GetFolder(self, _path: str):
        return self.root_folder


class GuiAutostartContractTests(unittest.TestCase):
    def test_registers_admin_group_task_without_user_password_credentials(self) -> None:
        from autostart import task_scheduler_api

        service = _FakeSchedulerService()

        @contextmanager
        def fake_open_scheduler_service():
            yield service, SimpleNamespace(com_error=Exception), object(), object()

        exe_path = r"C:\Program Files\Zapret\Zapret.exe"

        with patch.object(
            task_scheduler_api,
            "_open_scheduler_service",
            side_effect=fake_open_scheduler_service,
        ):
            result = task_scheduler_api.register_canonical_autostart_task(exe_path)

        self.assertTrue(result)
        self.assertEqual(len(service.root_folder.register_calls), 1)

        register_args = service.root_folder.register_calls[0]
        self.assertEqual(register_args[0], task_scheduler_api.CANONICAL_TASK_NAME)
        self.assertIs(register_args[1], service.task_definition)
        self.assertEqual(register_args[2], task_scheduler_api._TASK_CREATE_OR_UPDATE)
        self.assertIsNone(register_args[3])
        self.assertIsNone(register_args[4])
        self.assertEqual(register_args[5], task_scheduler_api._TASK_LOGON_GROUP)

        principal = service.task_definition.Principal
        self.assertIsNone(principal.UserId)
        self.assertEqual(principal.GroupId, task_scheduler_api.ADMINISTRATORS_GROUP_SID)
        self.assertEqual(principal.LogonType, task_scheduler_api._TASK_LOGON_GROUP)
        self.assertEqual(principal.RunLevel, task_scheduler_api._TASK_RUNLEVEL_HIGHEST)

        trigger = service.task_definition.Triggers.created[0][1]
        self.assertTrue(trigger.Enabled)
        self.assertIsNone(trigger.UserId)

        action = service.task_definition.Actions.created[0][1]
        self.assertEqual(action.Path, exe_path)
        self.assertEqual(action.Arguments, "--tray")
        self.assertEqual(action.WorkingDirectory, r"C:\Program Files\Zapret")

    def test_enable_gui_autostart_returns_readable_error_message(self) -> None:
        from autostart.public import enable_gui_autostart

        with (
            patch("startup.admin_check.is_admin", return_value=True),
            patch("autostart.autostart_exe.setup_autostart_for_exe", return_value=False),
        ):
            result = enable_gui_autostart()

        self.assertFalse(result.success)
        self.assertFalse(result.restart_requested)
        self.assertIn("Не удалось включить автозапуск", result.message)

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

        with (
            patch("settings.store.get_dpi_autostart", return_value=True),
            patch("settings.store.get_gui_autostart_enabled", return_value=True),
            patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=False),
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
