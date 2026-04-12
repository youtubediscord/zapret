from __future__ import annotations

from typing import TYPE_CHECKING

from log import log

if TYPE_CHECKING:
    from main import LupiDPIApp


def request_runtime_preset_switch(
    app: "LupiDPIApp",
    *,
    launch_method: str,
    reason: str,
    preset_file_name: str = "",
) -> bool:
    """Apply runtime policy when the selected preset file itself changes."""
    method = str(launch_method or "").strip().lower()
    target_preset = str(preset_file_name or "").strip()

    if not hasattr(app, "launch_controller") or not app.launch_controller:
        log("Runtime preset switch skipped: launch_controller not found", "DEBUG")
        return False

    try:
        controller = getattr(app, "launch_controller", None)
        if controller is None:
            log("Runtime preset switch skipped: launch_controller not found", "DEBUG")
            return False
        if not controller.is_running():
            log(f"Runtime preset switch skipped: DPI not running ({method})", "DEBUG")
            return False
    except Exception as e:
        log(f"Runtime preset switch state check error: {e}", "DEBUG")
        return False

    preset_info = f", preset={target_preset}" if target_preset else ""

    if method in {"direct_zapret1", "direct_zapret2"}:
        log(
            f"Runtime preset switch ({method}, reason={reason}{preset_info}) -> direct preset switch pipeline",
            "INFO",
        )
        app.launch_controller.switch_direct_preset_async(method)
        return True

    log(
        f"Runtime preset switch ({method or 'unknown'}, reason={reason}{preset_info}) -> restart pipeline",
        "INFO",
    )
    app.launch_controller.restart_dpi_async()
    return True
