from __future__ import annotations

from log.log import log
from settings.mode import is_preset_launch_method, normalize_launch_method


def request_selected_source_preset_apply(
    *,
    runtime_feature,
    launch_method: str,
    reason: str,
    preset_file_name: str = "",
) -> bool:
    """Применяет выбранный source preset к уже запущенному DPI."""
    method = normalize_launch_method(launch_method, default="")
    selected_preset = str(preset_file_name or "").strip()

    launch_runtime = runtime_feature.objects.launch_runtime
    if launch_runtime is None:
        log("Применение выбранного source preset пропущено: launch_runtime не найден", "DEBUG")
        return False

    try:
        if not launch_runtime.is_running():
            phase = ""
            running = False
            try:
                snapshot = runtime_feature.objects.snapshot()
                phase = str(getattr(snapshot, "phase", "") or "").strip().lower()
                running = bool(getattr(snapshot, "running", False))
            except Exception:
                phase = ""
                running = False
            log(
                f"Применение выбранного source preset пропущено: DPI не запущен ({method}, phase={phase or 'unknown'}, running={running})",
                "WARNING",
            )
            return False
    except Exception as e:
        log(f"Ошибка проверки состояния перед применением выбранного source preset: {e}", "WARNING")
        return False

    preset_info = f", preset={selected_preset}" if selected_preset else ""

    if is_preset_launch_method(method):
        log(
            f"Применение выбранного source preset ({method}, reason={reason}{preset_info}) -> preset mode switch pipeline",
            "INFO",
        )
        launch_runtime.switch_presets_async(method)
        return True

    log(
        f"Применение выбранного source preset ({method or 'unknown'}, reason={reason}{preset_info}) -> restart pipeline",
        "INFO",
    )
    launch_runtime.restart_dpi_async()
    return True
