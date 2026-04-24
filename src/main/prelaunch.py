from __future__ import annotations

import os
import sys

from config.config import MAIN_DIRECTORY
from main.runtime_state import is_startup_debug_enabled


_PRELAUNCH_DONE = False


def _set_workdir_to_app() -> None:
    """Устанавливает рабочую директорию в папку exe/скрипта."""
    try:
        app_dir = os.path.abspath(MAIN_DIRECTORY)

        os.chdir(app_dir)

        if is_startup_debug_enabled():
            debug_info = f"""
=== ZAPRET STARTUP DEBUG ===
Compiled mode: {'__compiled__' in globals()}
Frozen mode: {getattr(sys, 'frozen', False)}
sys.executable: {sys.executable}
sys.argv[0]: {sys.argv[0]}
Working directory: {app_dir}
Directory exists: {os.path.exists(app_dir)}
Directory contents: {os.listdir(app_dir) if os.path.exists(app_dir) else 'N/A'}
========================
"""
            with open("zapret_startup.log", "w", encoding="utf-8") as handle:
                handle.write(debug_info)
    except Exception as exc:
        with open("zapret_startup_error.log", "w", encoding="utf-8") as handle:
            handle.write(f"Error setting workdir: {exc}\n")
            import traceback

            handle.write(traceback.format_exc())


def _require_frozen() -> None:
    is_frozen = getattr(sys, "frozen", False) or ("__compiled__" in globals())
    if is_frozen:
        return

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            "Запустите программу через Zapret.exe\n\nЗапуск напрямую из исходников не поддерживается.",
            "Zapret — Ошибка запуска",
            0x10,
        )
    except Exception:
        print("ERROR: Запуск из исходников не поддерживается. Используйте Zapret.exe")
    sys.exit(1)


def _install_crash_handler() -> None:
    from log.crash_handler import install_crash_handler

    if os.environ.get("ZAPRET_DISABLE_CRASH_HANDLER") != "1":
        install_crash_handler()


def _preload_slow_modules() -> None:
    import threading

    def _preload() -> None:
        try:
            import jinja2
            import requests
            import psutil
            import json
            import winreg
        except Exception:
            pass

    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()


def prepare_prelaunch() -> None:
    global _PRELAUNCH_DONE
    if _PRELAUNCH_DONE:
        return

    _set_workdir_to_app()
    _require_frozen()
    _install_crash_handler()
    _preload_slow_modules()
    _PRELAUNCH_DONE = True
