from __future__ import annotations

import getpass
import os
from contextlib import contextmanager
from typing import Iterator

from log.log import log


CANONICAL_TASK_NAME = "ZapretGUI_AutoStart"

_TASK_TRIGGER_LOGON = 9
_TASK_ACTION_EXEC = 0
_TASK_CREATE_OR_UPDATE = 6
_TASK_LOGON_INTERACTIVE_TOKEN = 3
_TASK_RUNLEVEL_HIGHEST = 1


def _import_scheduler_modules():
    import pythoncom
    import pywintypes
    import win32api
    import win32com.client
    import win32con

    return pythoncom, pywintypes, win32api, win32com.client, win32con


@contextmanager
def _open_scheduler_service() -> Iterator[tuple[object, object, object, object]]:
    pythoncom, pywintypes, win32api, win32_client, win32con = _import_scheduler_modules()
    pythoncom.CoInitialize()
    try:
        service = win32_client.Dispatch("Schedule.Service")
        service.Connect()
        yield service, pywintypes, win32api, win32con
    finally:
        pythoncom.CoUninitialize()


def _resolve_current_user_id(win32api, win32con) -> str:
    candidates: list[str] = []

    try:
        candidates.append(str(win32api.GetUserNameEx(win32con.NameSamCompatible) or "").strip())
    except Exception:
        pass

    try:
        candidates.append(str(win32api.GetUserName() or "").strip())
    except Exception:
        pass

    try:
        candidates.append(str(getpass.getuser() or "").strip())
    except Exception:
        pass

    for candidate in candidates:
        if candidate:
            return candidate
    return ""


def _get_root_folder(service):
    return service.GetFolder("\\")


def _try_get_task(root_folder, task_name: str, pywintypes):
    try:
        return root_folder.GetTask(task_name)
    except pywintypes.com_error:
        return None


def is_canonical_autostart_enabled() -> bool:
    """Проверяет наличие канонической задачи через Windows Task Scheduler COM API."""
    try:
        with _open_scheduler_service() as (service, pywintypes, _win32api, _win32con):
            root_folder = _get_root_folder(service)
            return _try_get_task(root_folder, CANONICAL_TASK_NAME, pywintypes) is not None
    except Exception as exc:
        log(f"Task Scheduler query failed: {exc}", "WARNING")
        return False


def delete_canonical_autostart_task() -> bool:
    """Удаляет каноническую задачу через Windows Task Scheduler COM API."""
    try:
        with _open_scheduler_service() as (service, pywintypes, _win32api, _win32con):
            root_folder = _get_root_folder(service)
            task = _try_get_task(root_folder, CANONICAL_TASK_NAME, pywintypes)
            if task is None:
                return False
            root_folder.DeleteTask(CANONICAL_TASK_NAME, 0)
            return True
    except Exception as exc:
        log(f"Task Scheduler delete failed: {exc}", "WARNING")
        return False


def register_canonical_autostart_task(exe_path: str) -> bool:
    """Создаёт или обновляет задачу автозапуска через Windows Task Scheduler COM API."""
    exe_path = str(exe_path or "").strip()
    if not exe_path:
        log("Task Scheduler register failed: empty exe path", "ERROR")
        return False

    try:
        with _open_scheduler_service() as (service, _pywintypes, win32api, win32con):
            root_folder = _get_root_folder(service)
            current_user_id = _resolve_current_user_id(win32api, win32con)

            task_definition = service.NewTask(0)

            registration_info = task_definition.RegistrationInfo
            registration_info.Author = "ZapretGUI"
            registration_info.Description = (
                "Автозапуск ZapretGUI в трее при входе пользователя в Windows"
            )

            settings = task_definition.Settings
            settings.Enabled = True
            settings.AllowDemandStart = True
            settings.StartWhenAvailable = False
            settings.Hidden = False
            settings.DisallowStartIfOnBatteries = False
            settings.StopIfGoingOnBatteries = False
            try:
                settings.ExecutionTimeLimit = "PT0S"
            except Exception:
                pass

            principal = task_definition.Principal
            if current_user_id:
                principal.UserId = current_user_id
            principal.LogonType = _TASK_LOGON_INTERACTIVE_TOKEN
            principal.RunLevel = _TASK_RUNLEVEL_HIGHEST

            trigger = task_definition.Triggers.Create(_TASK_TRIGGER_LOGON)
            trigger.Enabled = True
            if current_user_id:
                try:
                    trigger.UserId = current_user_id
                except Exception:
                    pass

            action = task_definition.Actions.Create(_TASK_ACTION_EXEC)
            action.Path = exe_path
            action.Arguments = "--tray"
            action.WorkingDirectory = os.path.dirname(exe_path) or exe_path

            root_folder.RegisterTaskDefinition(
                CANONICAL_TASK_NAME,
                task_definition,
                _TASK_CREATE_OR_UPDATE,
                current_user_id,
                "",
                _TASK_LOGON_INTERACTIVE_TOKEN,
            )
            return True
    except Exception as exc:
        log(f"Task Scheduler register failed: {exc}", "ERROR")
        return False
