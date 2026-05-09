from __future__ import annotations

from typing import TYPE_CHECKING

from log.log import log


if TYPE_CHECKING:
    from main.window import LupiDPIApp


def request_selected_source_preset_apply(
    app: "LupiDPIApp",
    *,
    launch_method: str,
    reason: str,
    preset_file_name: str = "",
) -> bool:
    """Применяет выбранный source preset к уже запущенному DPI."""
    method = str(launch_method or "").strip().lower()
    selected_preset = str(preset_file_name or "").strip()

    if not hasattr(app, "launch_controller") or not app.launch_controller:
        log("Применение выбранного source preset пропущено: launch_controller не найден", "DEBUG")
        return False

    try:
        controller = getattr(app, "launch_controller", None)
        if controller is None:
            log("Применение выбранного source preset пропущено: launch_controller не найден", "DEBUG")
            return False
        if not controller.is_running():
            runtime_service = getattr(app, "launch_runtime_service", None)
            phase = ""
            running = False
            if runtime_service is not None:
                try:
                    snapshot = runtime_service.snapshot()
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

    if method in {"zapret1_mode", "zapret2_mode"}:
        log(
            f"Применение выбранного source preset ({method}, reason={reason}{preset_info}) -> preset mode switch pipeline",
            "INFO",
        )
        app.launch_controller.switch_presets_async(method)
        return True

    log(
        f"Применение выбранного source preset ({method or 'unknown'}, reason={reason}{preset_info}) -> restart pipeline",
        "INFO",
    )
    app.launch_controller.restart_dpi_async()
    return True
