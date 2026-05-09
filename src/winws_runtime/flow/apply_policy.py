from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from log.log import log


if TYPE_CHECKING:
    from main.window import LupiDPIApp


def _is_launch_running(app: "LupiDPIApp") -> bool:
    try:
        controller = getattr(app, "launch_controller", None)
        if controller is not None:
            return bool(controller.is_running())
    except Exception as e:
        log(f"Ошибка проверки состояния DPI: {e}", "DEBUG")
    return False


def _preset_filter_flags(launch_method: str) -> tuple[str, ...]:
    method = str(launch_method or "").strip().lower()
    if method == "zapret1_mode":
        return ("--wf-tcp=", "--wf-udp=")
    return ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part")


def _get_selected_presets_path(app: "LupiDPIApp", launch_method: str) -> Path | None:
    method = str(launch_method or "").strip().lower()
    if method not in {"zapret1_mode", "zapret2_mode"}:
        return None
    try:
        snapshot = app.app_context.preset_mode_coordinator.get_startup_snapshot(method, require_filters=False)
        return Path(snapshot.preset_path)
    except Exception:
        return None


def request_preset_runtime_content_apply(
    app: "LupiDPIApp",
    *,
    launch_method: str,
    reason: str,
    profile_key: str | None = None,
) -> bool:
    """Apply runtime reaction for edits to the currently selected preset mode."""
    method = str(launch_method or "").strip().lower()
    if method not in {"zapret1_mode", "zapret2_mode"}:
        log(f"Preset runtime apply skipped: unsupported method {method}", "DEBUG")
        return False

    if not hasattr(app, "launch_controller") or not app.launch_controller:
        log("Preset runtime apply skipped: launch_controller not found", "DEBUG")
        return False

    if not _is_launch_running(app):
        log(f"Preset runtime apply skipped: DPI not running ({method})", "DEBUG")
        return False

    preset_path = _get_selected_presets_path(app, method)
    if preset_path is None or not preset_path.exists():
        log(f"Preset runtime apply: active preset missing for {method}, stopping DPI", "WARNING")
        app.launch_controller.stop_dpi_async()
        return True

    try:
        content = preset_path.read_text(encoding="utf-8")
    except Exception as e:
        log(f"Preset runtime apply: failed to read preset for {method}: {e}", "ERROR")
        return False

    if not any(flag in content for flag in _preset_filter_flags(method)):
        log(f"Preset runtime apply: preset has no active filters for {method}, stopping DPI", "INFO")
        app.launch_controller.stop_dpi_async()
        return True

    profile_info = f" [{profile_key}]" if profile_key else ""
    log(
        f"Preset runtime apply{profile_info} ({method}, reason={reason}) - watcher-driven hot-reload should apply changes automatically",
        "INFO",
    )
    return True
