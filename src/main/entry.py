from __future__ import annotations

import atexit
import sys
import time as _time

from PyQt6.QtCore import QTimer

from log.log import log

from config.build_info import APP_VERSION

from main.qt_runtime import application_bootstrap
from main.runtime_state import (
    is_qt_event_diagnostic_enabled,
    log_startup_metric as emit_startup_metric,
)
from main.shell import shell_bootstrap


def _create_ipc_manager():
    from startup.ipc_manager import IPCManager

    return IPCManager()


def _build_application_post_startup_deps(**kwargs):
    from main.application_post_startup import build_application_post_startup_deps

    return build_application_post_startup_deps(**kwargs)


def _install_post_startup_tasks(deps) -> None:
    from main.post_startup import install_post_startup_tasks

    install_post_startup_tasks(deps)


def _install_qt_scroll_style(app) -> None:
    try:
        from main.qt_runtime import _install_non_transient_scrollbars_style

        t_style = _time.perf_counter()
        _install_non_transient_scrollbars_style(app)
        emit_startup_metric(
            "StartupQtScrollStyle",
            f"{(_time.perf_counter() - t_style) * 1000:.0f}ms",
        )
    except Exception:
        pass


def _install_qt_scroll_style_after_interactive(window, app) -> None:
    installed = False

    def _install_once(*_args) -> None:
        nonlocal installed
        if installed:
            return
        installed = True
        QTimer.singleShot(0, lambda: _install_qt_scroll_style(app))

    try:
        if bool(window.startup_state.interactive_logged):
            _install_once()
            return
    except Exception:
        _install_once()
        return

    try:
        window.startup_interactive_ready.connect(_install_once)
    except Exception:
        _install_once()


def _install_post_startup_tasks_after_interactive(window, deps_or_factory) -> None:
    installed = False

    def _install_once(*_args) -> None:
        nonlocal installed
        if installed:
            return
        installed = True
        deps = deps_or_factory() if callable(deps_or_factory) else deps_or_factory
        QTimer.singleShot(0, lambda: _install_post_startup_tasks(deps))

    try:
        if bool(window.startup_state.interactive_logged):
            _install_once()
            return
    except Exception:
        _install_once()
        return

    try:
        window.startup_interactive_ready.connect(_install_once)
    except Exception:
        _install_once()


def _configure_window_appearance(window, appearance_actions) -> None:
    try:
        from settings.appearance import peek_warmed_background_preset
        from ui.theme import apply_window_background

        background_preset = peek_warmed_background_preset() or "standard"
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
        from settings.appearance import peek_warmed_window_opacity

        opacity = peek_warmed_window_opacity()
        if opacity is not None and opacity != 100:
            appearance_actions.set_window_opacity(opacity)
    except Exception:
        pass


def _finish_event_loop_bootstrap(*, app, window, application_controller, start_in_tray: bool) -> None:
    from main.windows_session_shutdown import connect_windows_session_shutdown

    connect_windows_session_shutdown(app, window)
    _configure_window_appearance(window, application_controller.window_state_actions)

    ipc_manager = _create_ipc_manager()
    ipc_manager.start_server(window)
    atexit.register(ipc_manager.stop)

    if start_in_tray:
        log("Запуск приложения скрыто в трее", "TRAY")

    _install_qt_scroll_style_after_interactive(window, app)
    _install_post_startup_tasks_after_interactive(
        window,
        lambda: _build_application_post_startup_deps(
            window=window,
            app_runtime=application_controller.app_runtime,
        ),
    )


def main() -> None:
    log("=== ЗАПУСК ПРИЛОЖЕНИЯ ===", "🔹 main")
    log(APP_VERSION, "🔹 main")

    try:
        t_settings = _time.perf_counter()
        from settings.store import materialize_settings_file

        materialize_settings_file()
        emit_startup_metric(
            "StartupSettingsMaterialize",
            f"{(_time.perf_counter() - t_settings) * 1000:.0f}ms",
        )
    except Exception as exc:
        log(f"Не удалось подготовить settings.json: {exc}", "WARNING")

    t_shell = _time.perf_counter()
    start_in_tray = shell_bootstrap()
    emit_startup_metric(
        "StartupShellBootstrap",
        f"{(_time.perf_counter() - t_shell) * 1000:.0f}ms",
    )
    t_app = _time.perf_counter()
    app = application_bootstrap()
    emit_startup_metric(
        "StartupApplicationBootstrap",
        f"{(_time.perf_counter() - t_app) * 1000:.0f}ms",
    )
    if is_qt_event_diagnostic_enabled():
        try:
            from main.qt_event_diagnostics import install_qt_event_diagnostic

            install_qt_event_diagnostic(app)
        except Exception as exc:
            log(f"Не удалось включить Qt event diagnostic: {exc}", "WARNING")

    t_controller_import = _time.perf_counter()
    from main.application_controller import ApplicationController
    emit_startup_metric(
        "StartupApplicationControllerImport",
        f"{(_time.perf_counter() - t_controller_import) * 1000:.0f}ms",
    )
    t_window_import = _time.perf_counter()
    from main.window import LupiDPIApp
    emit_startup_metric(
        "StartupWindowClassImport",
        f"{(_time.perf_counter() - t_window_import) * 1000:.0f}ms",
    )

    t_controller_init = _time.perf_counter()
    application_controller = ApplicationController(
        window_cls=LupiDPIApp,
        start_in_tray=start_in_tray,
    )
    emit_startup_metric(
        "StartupApplicationControllerInit",
        f"{(_time.perf_counter() - t_controller_init) * 1000:.0f}ms",
    )
    window = application_controller.create_window()
    QTimer.singleShot(
        0,
        lambda: _finish_event_loop_bootstrap(
            app=app,
            window=window,
            application_controller=application_controller,
            start_in_tray=bool(start_in_tray),
        ),
    )
    sys.exit(app.exec())
