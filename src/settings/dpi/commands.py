from __future__ import annotations

from dataclasses import dataclass

from log.log import log
from settings.mode import is_orchestra_launch_method, is_preset_launch_method, normalize_launch_method



@dataclass(slots=True)
class DpiOrchestraSettingsState:
    strict_detection: bool
    debug_file: bool
    auto_restart_discord: bool
    discord_fails: int
    lock_successes: int
    unlock_fails: int


@dataclass(slots=True)
class DpiVisibilityState:
    show_orchestra_settings: bool


@dataclass(slots=True)
class DpiInitialState:
    launch_method: str
    visibility: DpiVisibilityState

def load_initial_state() -> DpiInitialState:
    launch_method = get_launch_method()
    return DpiInitialState(
        launch_method=launch_method,
        visibility=describe_visibility(launch_method),
    )

def get_launch_method() -> str:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    return normalize_launch_method(get_strategy_launch_method())


def get_profile_ui_mode() -> str:
    from settings.dpi.strategy_settings import get_profile_ui_mode as _get_profile_ui_mode
    from settings.mode import normalize_profile_ui_mode

    return normalize_profile_ui_mode(_get_profile_ui_mode())


def set_profile_ui_mode(mode: str) -> str:
    from settings.dpi.strategy_settings import set_profile_ui_mode as _set_profile_ui_mode
    from settings.mode import normalize_profile_ui_mode

    normalized = normalize_profile_ui_mode(mode)
    _set_profile_ui_mode(normalized)
    return normalized


def describe_visibility(method: str) -> DpiVisibilityState:
    method = normalize_launch_method(method, default="")
    return DpiVisibilityState(
        show_orchestra_settings=bool(is_orchestra_launch_method(method)),
    )

def _orchestra_reg_path() -> str:
    return "orchestra.settings"

def load_orchestra_settings() -> DpiOrchestraSettingsState:
    from settings.store import (
        get_orchestra_auto_restart_on_discord_fail,
        get_orchestra_discord_fails_for_restart,
        get_orchestra_keep_debug_file,
        get_orchestra_lock_successes,
        get_orchestra_strict_detection,
        get_orchestra_unlock_fails,
    )

    return DpiOrchestraSettingsState(
        strict_detection=bool(get_orchestra_strict_detection()),
        debug_file=bool(get_orchestra_keep_debug_file()),
        auto_restart_discord=bool(get_orchestra_auto_restart_on_discord_fail()),
        discord_fails=int(get_orchestra_discord_fails_for_restart()),
        lock_successes=int(get_orchestra_lock_successes()),
        unlock_fails=int(get_orchestra_unlock_fails()),
    )

def apply_launch_method(method: str) -> str:
    from settings.dpi.strategy_settings import get_strategy_launch_method, set_strategy_launch_method

    previous_method = normalize_launch_method(get_strategy_launch_method())
    next_method = normalize_launch_method(method)

    set_strategy_launch_method(next_method)

    if is_preset_launch_method(previous_method) or is_preset_launch_method(next_method):
        if previous_method != next_method:
            log(f"Смена метода {previous_method} -> {next_method}", "INFO")

    return next_method

def set_orchestra_setting(key: str, value, *, runner=None) -> None:
    normalized_key = str(key or "").strip().lower()

    if normalized_key == "strict_detection":
        from settings.store import set_orchestra_strict_detection

        set_orchestra_strict_detection(bool(value))
        if runner:
            runner.set_strict_detection(bool(value))
        return

    if normalized_key == "debug_file":
        from settings.store import set_orchestra_keep_debug_file

        set_orchestra_keep_debug_file(bool(value))
        return

    if normalized_key == "auto_restart_discord":
        from settings.store import set_orchestra_auto_restart_on_discord_fail

        set_orchestra_auto_restart_on_discord_fail(bool(value))
        if runner:
            runner.auto_restart_on_discord_fail = bool(value)
        return

    if normalized_key == "discord_fails":
        from settings.store import set_orchestra_discord_fails_for_restart

        set_orchestra_discord_fails_for_restart(int(value))
        if runner:
            runner.discord_fails_for_restart = int(value)
        return

    if normalized_key == "lock_successes":
        from settings.store import set_orchestra_lock_successes

        set_orchestra_lock_successes(int(value))
        if runner:
            runner.lock_successes_threshold = int(value)
        return

    if normalized_key == "unlock_fails":
        from settings.store import set_orchestra_unlock_fails

        set_orchestra_unlock_fails(int(value))
        if runner:
            runner.unlock_fails_threshold = int(value)
        return
