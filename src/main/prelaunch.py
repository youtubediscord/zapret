from __future__ import annotations

import os
import sys

from config.runtime_layout import APPLICATION_PATHS
from main.pyinstaller_archive_import_lock import install_pyinstaller_archive_import_lock
from main.runtime_state import is_startup_debug_enabled


_PRELAUNCH_DONE = False


def _set_workdir_to_app() -> None:
    """Устанавливает рабочую директорию в единый корень приложения."""
    try:
        app_dir = str(APPLICATION_PATHS.root)

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
            APPLICATION_PATHS.logs_dir.mkdir(parents=True, exist_ok=True)
            with open(APPLICATION_PATHS.logs_dir / "zapret_startup.log", "w", encoding="utf-8") as handle:
                handle.write(debug_info)
    except Exception as exc:
        try:
            APPLICATION_PATHS.logs_dir.mkdir(parents=True, exist_ok=True)
            with open(APPLICATION_PATHS.logs_dir / "zapret_startup_error.log", "w", encoding="utf-8") as handle:
                handle.write(f"Error setting workdir: {exc}\n")
                import traceback

                handle.write(traceback.format_exc())
        except OSError:
            pass


def _install_crash_handler() -> None:
    from log.crash_handler import install_crash_handler

    if os.environ.get("ZAPRET_DISABLE_CRASH_HANDLER") != "1":
        install_crash_handler()


def _preload_slow_modules() -> None:
    import threading

    def _preload() -> None:
        # qtawesome здесь НЕ греем: на этой фазе главный поток занят
        # импортами PyQt6/qfluentwidgets, и фоновый импорт qtawesome
        # отбирает у него GIL. Прогрев qtawesome стартует позже —
        # см. start_qtawesome_warmup() в main.entry.
        try:
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
    _install_crash_handler()
    install_pyinstaller_archive_import_lock()
    _preload_slow_modules()
    _PRELAUNCH_DONE = True
