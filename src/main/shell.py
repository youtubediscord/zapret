from __future__ import annotations

import atexit
import ctypes
import os
import shutil
import subprocess
import sys
import time

from config.build_info import APP_VERSION

from log.log import log

from startup.admin_check import is_admin
from utils.subproc import run_hidden


def handle_update_mode(argv: list[str] | None = None) -> None:
    args = list(argv or sys.argv)
    if len(args) < 4:
        log("--update: недостаточно аргументов", "❌ ERROR")
        return

    old_exe, new_exe = args[2], args[3]

    for _ in range(10):
        if not os.path.exists(old_exe) or os.access(old_exe, os.W_OK):
            break
        time.sleep(0.5)

    try:
        shutil.copy2(new_exe, old_exe)
        run_hidden([old_exe])
        log("Файл обновления применён", "INFO")
    except Exception as exc:
        log(f"Ошибка в режиме --update: {exc}", "❌ ERROR")
    finally:
        try:
            os.remove(new_exe)
        except FileNotFoundError:
            pass


def shell_bootstrap(argv: list[str] | None = None) -> bool:
    args = list(argv or sys.argv)

    if "--version" in args:
        ctypes.windll.user32.MessageBoxW(None, APP_VERSION, "Zapret – версия", 0x40)
        sys.exit(0)

    if "--update" in args and len(args) > 3:
        handle_update_mode(args)
        sys.exit(0)

    start_in_tray = "--tray" in args

    if not is_admin():
        params = subprocess.list2cmdline(list(args[1:]))
        shell_exec_result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        if int(shell_exec_result) <= 32:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Не удалось запросить права администратора.",
                "Zapret",
                0x10,
            )
        sys.exit(0)

    from startup.single_instance import create_mutex, release_mutex
    from startup.ipc_manager import IPCManager

    mutex_handle, already_running = create_mutex("ZapretSingleInstance")
    if already_running:
        ipc = IPCManager()
        if ipc.send_show_command():
            log("Отправлена команда показать окно запущенному экземпляру", "INFO")
        else:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Экземпляр Zapret уже запущен, но не удалось показать окно!",
                "Zapret",
                0x40,
            )
        sys.exit(0)

    atexit.register(lambda: release_mutex(mutex_handle))
    return bool(start_in_tray)
