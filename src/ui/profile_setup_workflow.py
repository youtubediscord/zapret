from __future__ import annotations

from log.log import log

from ui.navigation_pages import resolve_preset_setup_page_for_method
from ui.window_adapter import get_loaded_page
from ui.workflows.mode import open_profile_setup_for_method


def open_profile_setup_with_logging(
    window,
    method: str,
    profile_key: str,
    *,
    error_prefix: str,
) -> bool:
    try:
        return bool(open_profile_setup_for_method(window, method, profile_key, allow_internal=True))
    except Exception as e:
        log(f"{error_prefix}: {e}", "ERROR")
        return False


def on_open_profile_setup(window, method: str, profile_key: str) -> None:
    open_profile_setup_with_logging(
        window,
        method,
        profile_key,
        error_prefix="Error opening profile setup",
    )


def on_profile_setup_changed(window, method: str, profile_key: str, change_kind: str) -> bool:
    preset_setup_page = resolve_preset_setup_page_for_method(method)
    if preset_setup_page is None:
        return False
    page = get_loaded_page(window, preset_setup_page)
    if page is None:
        return False
    log(f"Profile setup changed: {profile_key} = {change_kind}", "INFO")
    try:
        page.apply_profile_setup_change(profile_key, change_kind)
        return True
    except Exception:
        return False
