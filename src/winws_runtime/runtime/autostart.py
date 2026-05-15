from log.log import log
from settings.mode import ALL_LAUNCH_METHODS, is_preset_launch_method


def start_dpi_autostart(
    startup_state,
    *,
    runtime_feature,
    ui_state,
    launch_method: str | None = None,
) -> None:
    """Запускает DPI autostart через общий runtime-путь."""
    if bool(startup_state.dpi_autostart_initiated):
        log("Автозапуск DPI уже выполнен", "DEBUG")
        return

    startup_state.dpi_autostart_initiated = True

    from program_settings.public import is_auto_dpi_enabled

    if not is_auto_dpi_enabled():
        log("Автозапуск DPI отключён", "INFO")
        _mark_runtime_stopped(runtime_feature)
        return

    from settings.dpi.strategy_settings import get_strategy_launch_method

    resolved_method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
    if resolved_method not in ALL_LAUNCH_METHODS:
        log(f"Автозапуск не поддерживается для метода: {resolved_method or 'unknown'}", "WARNING")
        _mark_runtime_stopped(runtime_feature)
        return

    startup_snapshot = _resolve_startup_snapshot(runtime_feature, resolved_method)
    _refresh_autostart_launch_summary(
        runtime_feature=runtime_feature,
        ui_state=ui_state,
        launch_method=resolved_method,
    )

    log(f"Автозапуск передан в единый DPI runtime-путь: {resolved_method}", "INFO")
    runtime_feature.objects.launch_runtime.start_dpi_async(
        selected_mode=startup_snapshot.to_selected_mode() if startup_snapshot is not None else None,
        launch_method=resolved_method,
        _startup_autostart=True,
    )


def _mark_runtime_stopped(runtime_feature) -> None:
    runtime_feature.objects.runtime_service.mark_stopped(clear_error=True)


def _resolve_startup_snapshot(runtime_feature, launch_method: str):
    method = str(launch_method or "").strip().lower()
    try:
        if is_preset_launch_method(method):
            return runtime_feature.dependencies.presets_feature.get_launch_snapshot(
                method,
                require_filters=True,
            )
    except Exception as e:
        log(f"Не удалось подготовить стартовый пресет для {method}: {e}", "DEBUG")

    return None


def _refresh_autostart_launch_summary(*, runtime_feature, ui_state, launch_method: str) -> None:
    try:
        runtime_feature.dependencies.presets_feature.refresh_launch_summary_in_store(
            method=launch_method,
            profile_feature=runtime_feature.dependencies.profile_feature,
            ui_state_store=ui_state,
        )
    except Exception as e:
        log(f"Не удалось обновить стартовое отображение для {launch_method}: {e}", "DEBUG")
