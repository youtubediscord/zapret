from PyQt6.QtCore import QTimer

from log.log import log
from settings.mode import ALL_LAUNCH_METHODS, exe_name_for_launch_method, is_preset_launch_method


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

    if _reuse_running_expected_process(runtime_feature, resolved_method):
        return

    log(f"Автозапуск передан в единый DPI runtime-путь: {resolved_method}", "INFO")
    runtime_feature.objects.launch_runtime.start_dpi_async(
        selected_mode=None,
        launch_method=resolved_method,
        _startup_autostart=True,
    )
    _schedule_autostart_launch_summary_refresh(
        runtime_feature=runtime_feature,
        ui_state=ui_state,
        launch_method=resolved_method,
    )


def _mark_runtime_stopped(runtime_feature) -> None:
    runtime_feature.objects.runtime_service.mark_stopped(clear_error=True)


def _mark_runtime_failed(runtime_feature, message: str) -> None:
    runtime_feature.objects.runtime_service.mark_start_failed(str(message or "").strip())


def _reuse_running_expected_process(runtime_feature, launch_method: str) -> bool:
    if not is_preset_launch_method(launch_method):
        return False
    try:
        runtime_api = getattr(runtime_feature.objects, "launch_runtime_api", None)
        if runtime_api is None or not runtime_api.is_expected_running(silent=True):
            return False
        expected_process = exe_name_for_launch_method(launch_method).strip().lower()
        runtime_feature.objects.runtime_service.bootstrap_probe(
            True,
            launch_method=launch_method,
            expected_process=expected_process,
        )
        log(f"Автозапуск DPI: {expected_process or launch_method} уже работает, повторный старт не нужен", "INFO")
        return True
    except Exception as e:
        log(f"Не удалось подхватить уже запущенный DPI при автозапуске: {e}", "DEBUG")
        return False


def _schedule_autostart_launch_summary_refresh(*, runtime_feature, ui_state, launch_method: str) -> None:
    QTimer.singleShot(
        0,
        lambda: _refresh_autostart_launch_summary(
            runtime_feature=runtime_feature,
            ui_state=ui_state,
            launch_method=launch_method,
        ),
    )


def _refresh_autostart_launch_summary(*, runtime_feature, ui_state, launch_method: str) -> None:
    try:
        runtime_feature.dependencies.presets_feature.refresh_launch_summary_in_store(
            method=launch_method,
            profile_feature=runtime_feature.dependencies.profile_feature,
            ui_state_store=ui_state,
        )
    except Exception as e:
        log(f"Не удалось обновить стартовое отображение для {launch_method}: {e}", "DEBUG")
