from __future__ import annotations

import atexit
import sys

from log.log import log

from config.build_info import APP_VERSION

from startup.ipc_manager import IPCManager

from main.post_startup import install_post_startup_tasks
from main.qt_runtime import application_bootstrap
from main.shell import shell_bootstrap


def _configure_window_appearance(window) -> None:
    try:
        from settings.store import get_background_preset
        from ui.theme import apply_window_background

        background_preset = get_background_preset()
        apply_window_background(window, preset=background_preset)
    except Exception:
        pass

    try:
        from qfluentwidgets.common.config import qconfig
        from ui.theme import apply_window_background

        qconfig.themeChanged.connect(lambda _: apply_window_background(window))
    except Exception:
        pass

    try:
        from settings.store import get_window_opacity

        opacity = get_window_opacity()
        if opacity != 100:
            window.set_window_opacity(opacity)
    except Exception:
        pass


def main() -> None:
    log("=== ЗАПУСК ПРИЛОЖЕНИЯ ===", "🔹 main")
    log(APP_VERSION, "🔹 main")

    try:
        from settings.store import materialize_settings_file

        materialize_settings_file()
    except Exception as exc:
        log(f"Не удалось подготовить settings.json: {exc}", "WARNING")

    start_in_tray = shell_bootstrap()
    app = application_bootstrap()

    from main.window import window_bootstrap

    _app_context, window = window_bootstrap(start_in_tray=start_in_tray)
    _configure_window_appearance(window)

    ipc_manager = IPCManager()
    ipc_manager.start_server(window)
    atexit.register(ipc_manager.stop)

    if start_in_tray:
        log("Запуск приложения скрыто в трее", "TRAY")

    install_post_startup_tasks(window)
    sys.exit(app.exec())
