from __future__ import annotations

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


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

    def test_autostart_page_deps_pass_notify_callback(self) -> None:
        from app.page_names import PageName
        from ui.page_deps.system import build_autostart_page_kwargs

        notify = Mock()
        kwargs = build_autostart_page_kwargs(
            page_name=PageName.AUTOSTART,
            autostart_feature=object(),
            show_page=Mock(),
            notify=notify,
            ui_state_store=object(),
        )

        self.assertIs(kwargs["notify"], notify)

    def test_autostart_page_deps_composition_includes_notify_callback(self) -> None:
        from app.page_names import PageName
        from main.window_page_deps_setup import build_window_page_deps_sources
        from ui.page_composition import build_page_deps

        notify = Mock()
        sources = build_window_page_deps_sources(
            features=SimpleNamespace(
                autostart=object(),
                blobs=object(),
                blockcheck=object(),
                diagnostics=object(),
                dns=object(),
                dpi_settings=object(),
                external_actions=object(),
                hosts=object(),
                lists=object(),
                logs=object(),
                orchestra=object(),
                premium=object(),
                presets=object(),
                profile=object(),
                program_settings=object(),
                runtime=object(),
                telegram_proxy=object(),
                updater=object(),
            ),
            state=SimpleNamespace(ui=object()),
            page_actions=SimpleNamespace(
                after_launch_method_changed=Mock(),
                notify=notify,
                on_animations_changed=Mock(),
                on_background_preset_changed=Mock(),
                on_background_refresh_needed=Mock(),
                on_editor_smooth_scroll_changed=Mock(),
                on_mica_changed=Mock(),
                on_opacity_changed=Mock(),
                on_profile_setup_changed=Mock(),
                on_smooth_scroll_changed=Mock(),
                on_ui_language_changed=Mock(),
                open_connection_test=Mock(),
                open_folder=Mock(),
                open_preset_raw_editor=Mock(),
                open_profile_setup=Mock(),
                request_exit=Mock(),
                set_garland_enabled=Mock(),
                set_snowflakes_enabled=Mock(),
                set_status=Mock(),
                show_active_mode_control_page=Mock(),
                show_page=Mock(),
            ),
        )

        kwargs = build_page_deps(sources, PageName.AUTOSTART)

        self.assertIs(kwargs["notify"], notify)

    def test_autostart_error_notification_payload_is_user_readable(self) -> None:
        from autostart.ui.notifications import build_autostart_error_notification

        payload = build_autostart_error_notification("COM raw details")

        self.assertEqual(payload["level"], "error")
        self.assertEqual(payload["title"], "Автозапуск не включён")
        self.assertIn("COM raw details", payload["content"])
        self.assertEqual(payload["source"], "autostart.gui")
        self.assertEqual(payload["queue"], "immediate")


if __name__ == "__main__":
    unittest.main()
