from __future__ import annotations

import atexit
import sys

from log.log import log

from config.build_info import APP_VERSION

from startup.ipc_manager import IPCManager

from main.application_post_startup import build_application_post_startup_deps
from main.post_startup import install_post_startup_tasks
from main.qt_runtime import application_bootstrap
from main.runtime_state import is_qt_event_diagnostic_enabled
from main.shell import shell_bootstrap


def _configure_window_appearance(window, appearance_actions) -> None:
    try:
        from settings.appearance import load_background_preset
        from ui.theme import apply_window_background

        background_preset = load_background_preset().preset
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
        from settings.appearance import load_window_opacity

        opacity = load_window_opacity().value
        if opacity != 100:
            appearance_actions.set_window_opacity(opacity)
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
    if is_qt_event_diagnostic_enabled():
        try:
            from main.qt_event_diagnostics import install_qt_event_diagnostic

            install_qt_event_diagnostic(app)
        except Exception as exc:
            log(f"Не удалось включить Qt event diagnostic: {exc}", "WARNING")

    from main.application_controller import ApplicationController
    from main.window import LupiDPIApp

    application_controller = ApplicationController(
        window_cls=LupiDPIApp,
        start_in_tray=start_in_tray,
    )
    window = application_controller.create_window()
    from main.windows_session_shutdown import connect_windows_session_shutdown

    connect_windows_session_shutdown(app, window)
    _configure_window_appearance(window, application_controller.window_state_actions)

    ipc_manager = IPCManager()
    ipc_manager.start_server(window)
    atexit.register(ipc_manager.stop)

    if start_in_tray:
        log("Запуск приложения скрыто в трее", "TRAY")

    install_post_startup_tasks(
        build_application_post_startup_deps(
            window=window,
            app_runtime=application_controller.app_runtime,
        )
    )
    sys.exit(app.exec())
