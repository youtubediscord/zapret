from __future__ import annotations

from log.log import log
from settings.mode import is_preset_launch_method, normalize_launch_method


PRESET_CONTENT_APPLY_DEBOUNCE_MS = 900


def _is_launch_running(runtime_feature) -> bool:
    try:
        launch_runtime = runtime_feature.objects.launch_runtime
        if launch_runtime is not None:
            return bool(launch_runtime.is_running())
    except Exception as e:
        log(f"Ошибка проверки состояния DPI: {e}", "DEBUG")
    return False


def request_preset_runtime_content_apply(
    *,
    runtime_feature,
    launch_method: str,
    reason: str,
    profile_key: str | None = None,
) -> bool:
    """Apply runtime reaction for edits to the currently selected preset mode."""
    method = normalize_launch_method(launch_method, default="")
    if not is_preset_launch_method(method):
        log(f"Preset runtime apply skipped: unsupported method {method}", "DEBUG")
        return False

    launch_runtime = runtime_feature.objects.launch_runtime
    if launch_runtime is None:
        log("Preset runtime apply skipped: launch_runtime not found", "DEBUG")
        return False

    if not _is_launch_running(runtime_feature):
        log(f"Preset runtime apply skipped: DPI not running ({method})", "DEBUG")
        return False

    profile_info = f" [{profile_key}]" if profile_key else ""
    log(
        f"Preset runtime apply{profile_info} ({method}, reason={reason}) -> preset mode switch pipeline",
        "INFO",
    )
    launch_runtime.switch_presets_async(method, delay_ms=PRESET_CONTENT_APPLY_DEBOUNCE_MS)
    return True
