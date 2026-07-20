"""
Автозапуск GUI через Планировщик задач Windows (COM API Schedule.Service).

Zapret.exe собран с manifest requireAdministrator, поэтому ярлык в папке
автозагрузки Windows молча игнорирует на системах с включённым UAC
(показать запрос elevation на этапе входа система не может). Задача
планировщика с RunLevel=Highest запускается с правами администратора
без UAC-запроса и работает независимо от состояния UAC.

ВАЖНО: задача регистрируется с LogonType=INTERACTIVE_TOKEN от имени
текущего пользователя, НЕ от SYSTEM. Запуск от SYSTEM ломает GUI-приложение:
процесс попадает в неинтерактивный контекст (session 0), окно и трей не
отображаются, а winws2 наследует SYSTEM-окружение без профиля пользователя.
INTERACTIVE_TOKEN + RunLevel=Highest даёт тот же контекст, что и ручной
запуск exe с подтверждением UAC: интерактивная сессия пользователя,
его профиль, но полный админский токен.
"""

from __future__ import annotations

import ntpath
import os

from config.runtime_layout import RUNTIME_DIR_NAME, RUNTIME_EXE_NAME
from log.log import log


AUTOSTART_TASK_NAME = "ZapretGUI Autostart"
AUTOSTART_TASK_ARGS = "--tray"
_TASK_FOLDER = "\\"

# Константы Task Scheduler 2.0 COM API
TASK_TRIGGER_LOGON = 9
TASK_ACTION_EXEC = 0
TASK_RUNLEVEL_HIGHEST = 1
TASK_LOGON_INTERACTIVE_TOKEN = 3
TASK_CREATE_OR_UPDATE = 6
TASK_INSTANCES_IGNORE_NEW = 2


def _co_initialize() -> bool:
    try:
        import pythoncom

        pythoncom.CoInitialize()
        return True
    except Exception:
        return False


def _co_uninitialize(initialized: bool) -> None:
    if not initialized:
        return
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except Exception:
        pass


def _connect_scheduler():
    import win32com.client

    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    return scheduler


def _current_user_id() -> str:
    user = os.environ.get("USERNAME", "").strip()
    if not user:
        return ""
    domain = os.environ.get("USERDOMAIN", "").strip()
    return f"{domain}\\{user}" if domain else user


def _canonical_app_working_directory(exe_path: str) -> str:
    """Возвращает корень установки только для канонического runtime exe."""
    normalized = ntpath.normpath(str(exe_path or "").strip())
    runtime_dir = ntpath.dirname(normalized)
    app_root = ntpath.dirname(runtime_dir)
    if (
        ntpath.basename(normalized).casefold() != RUNTIME_EXE_NAME.casefold()
        or ntpath.basename(runtime_dir).casefold() != RUNTIME_DIR_NAME.casefold()
        or not app_root
    ):
        raise ValueError(
            "Автозапуск разрешён только для установленного "
            f"{RUNTIME_DIR_NAME}\\{RUNTIME_EXE_NAME}: {exe_path}"
        )
    return app_root


def _register_autostart_task(exe_path: str, task_name: str) -> None:
    """Вся COM-работа в отдельной функции: её локальные COM-объекты
    освобождаются до CoUninitialize в вызывающем коде."""
    working_directory = _canonical_app_working_directory(exe_path)
    scheduler = _connect_scheduler()
    folder = scheduler.GetFolder(_TASK_FOLDER)
    task_def = scheduler.NewTask(0)

    task_def.RegistrationInfo.Author = "ZapretGUI"
    task_def.RegistrationInfo.Description = (
        "Автозапуск ZapretGUI в трее при входе в Windows"
    )

    trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)
    user_id = _current_user_id()
    if user_id:
        trigger.UserId = user_id
    # Небольшая пауза, чтобы рабочий стол и область уведомлений успели подняться
    trigger.Delay = "PT3S"

    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.Path = exe_path
    action.Arguments = AUTOSTART_TASK_ARGS
    action.WorkingDirectory = working_directory

    principal = task_def.Principal
    principal.RunLevel = TASK_RUNLEVEL_HIGHEST
    principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN

    settings = task_def.Settings
    settings.Enabled = True
    settings.StartWhenAvailable = True
    # Дефолты планировщика рассчитаны на batch-задачи и ломают GUI-приложение:
    # запрет старта на батарее, остановка при переходе на батарею и
    # принудительное завершение через 72 часа.
    settings.DisallowStartIfOnBatteries = False
    settings.StopIfGoingOnBatteries = False
    settings.ExecutionTimeLimit = "PT0S"
    settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    # Дефолтный приоритет задач планировщика — below normal (7)
    settings.Priority = 5

    folder.RegisterTaskDefinition(
        task_name,
        task_def,
        TASK_CREATE_OR_UPDATE,
        None,
        None,
        TASK_LOGON_INTERACTIVE_TOKEN,
    )


def create_or_update_autostart_task(
    exe_path: str,
    *,
    task_name: str = AUTOSTART_TASK_NAME,
) -> bool:
    """Регистрирует (или перезаписывает) задачу автозапуска для текущего пользователя."""
    exe_path = str(exe_path or "").strip()
    if not exe_path:
        log("Autostart task create failed: empty exe path", "ERROR")
        return False

    com_ready = _co_initialize()
    try:
        try:
            _register_autostart_task(exe_path, task_name)
            return True
        except Exception as exc:
            log(f"Autostart task create failed: {exc}", "WARNING")
            return False
    finally:
        _co_uninitialize(com_ready)


def _read_autostart_task_action(task_name: str) -> tuple[str, str] | None:
    folder = _connect_scheduler().GetFolder(_TASK_FOLDER)
    task = folder.GetTask(task_name)
    for action in task.Definition.Actions:
        if int(getattr(action, "Type", TASK_ACTION_EXEC)) == TASK_ACTION_EXEC:
            return (
                str(getattr(action, "Path", "") or ""),
                str(getattr(action, "Arguments", "") or ""),
            )
    return None


def get_autostart_task_action(
    *,
    task_name: str = AUTOSTART_TASK_NAME,
) -> tuple[str, str] | None:
    """Возвращает (path, arguments) exec-действия задачи или None, если задачи нет."""
    com_ready = _co_initialize()
    try:
        try:
            return _read_autostart_task_action(task_name)
        except Exception:
            return None
    finally:
        _co_uninitialize(com_ready)


def autostart_task_exists(*, task_name: str = AUTOSTART_TASK_NAME) -> bool:
    return get_autostart_task_action(task_name=task_name) is not None


def _delete_task(task_name: str) -> None:
    folder = _connect_scheduler().GetFolder(_TASK_FOLDER)
    folder.DeleteTask(task_name, 0)


def delete_autostart_task(*, task_name: str = AUTOSTART_TASK_NAME) -> bool:
    """Удаляет задачу автозапуска. False — если задачи не было или удалить не удалось."""
    com_ready = _co_initialize()
    try:
        try:
            _delete_task(task_name)
            return True
        except Exception as exc:
            log(f"Autostart task delete skipped: {exc}", "DEBUG")
            return False
    finally:
        _co_uninitialize(com_ready)
