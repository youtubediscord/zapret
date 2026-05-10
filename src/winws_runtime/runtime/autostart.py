from log.log import log
from presets.public import get_launch_snapshot
from settings.mode import ALL_LAUNCH_METHODS, is_orchestra_launch_method, is_preset_launch_method
from ui.window_adapter import update_window_current_strategy_display


def start_dpi_autostart(app, launch_method: str | None = None) -> None:
    """Запускает DPI autostart через общий runtime controller."""
    if bool(getattr(app, "_dpi_autostart_initiated", False)):
        log("Автозапуск DPI уже выполнен", "DEBUG")
        return

    app._dpi_autostart_initiated = True

    from program_settings.public import is_auto_dpi_enabled

    if not is_auto_dpi_enabled():
        log("Автозапуск DPI отключён", "INFO")
        _mark_runtime_stopped(app)
        return

    from settings.dpi.strategy_settings import get_strategy_launch_method

    resolved_method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
    if resolved_method not in ALL_LAUNCH_METHODS:
        log(f"Автозапуск не поддерживается для метода: {resolved_method or 'unknown'}", "WARNING")
        _mark_runtime_stopped(app)
        return

    startup_snapshot = _resolve_startup_snapshot(app, resolved_method)
    display_name = _resolve_startup_display_name(
        app,
        resolved_method,
        startup_snapshot=startup_snapshot,
    )
    if display_name:
        update_window_current_strategy_display(app, display_name)

    log(f"Автозапуск передан в единый DPI controller pipeline: {resolved_method}", "INFO")
    app.launch_controller.start_dpi_async(
        selected_mode=startup_snapshot.to_selected_mode() if startup_snapshot is not None else None,
        launch_method=resolved_method,
        _startup_autostart=True,
    )


def _mark_runtime_stopped(app) -> None:
    runtime_service = getattr(app, "launch_runtime_service", None)
    if runtime_service is None:
        return
    runtime_service.mark_stopped(clear_error=True)


def _resolve_startup_snapshot(app, launch_method: str):
    method = str(launch_method or "").strip().lower()
    try:
        if is_preset_launch_method(method):
            return get_launch_snapshot(
                method,
                app_context=app.app_context,
                require_filters=True,
            )
    except Exception as e:
        log(f"Не удалось подготовить стартовый пресет для {method}: {e}", "DEBUG")

    return None


def _resolve_startup_display_name(app, launch_method: str, *, startup_snapshot=None) -> str:
    method = str(launch_method or "").strip().lower()
    try:
        if is_preset_launch_method(method):
            snapshot = startup_snapshot or _resolve_startup_snapshot(app, method)
            if snapshot is not None:
                return str(snapshot.display_name or "").strip() or "Пресет"

        if is_orchestra_launch_method(method):
            return "Оркестр"
    except Exception as e:
        log(f"Не удалось определить стартовое имя стратегии для {method}: {e}", "DEBUG")

    return ""
