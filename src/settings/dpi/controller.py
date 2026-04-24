from __future__ import annotations

from dataclasses import dataclass

from log.log import log



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


class DpiSettingsPageController:
    @classmethod
    def load_initial_state(cls) -> DpiInitialState:
        launch_method = cls.get_launch_method()
        return DpiInitialState(
            launch_method=launch_method,
            visibility=cls.describe_visibility(launch_method),
        )

    @staticmethod
    def get_launch_method() -> str:
        from settings.dpi.strategy_settings import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()

    @staticmethod
    def describe_visibility(method: str) -> DpiVisibilityState:
        method = str(method or "").strip().lower()
        return DpiVisibilityState(
            show_orchestra_settings=bool(method == "orchestra"),
        )

    @staticmethod
    def _orchestra_reg_path() -> str:
        return "orchestra.settings"

    @classmethod
    def load_orchestra_settings(cls) -> DpiOrchestraSettingsState:
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

    @staticmethod
    def apply_launch_method(method: str) -> str:
        from settings.dpi.strategy_settings import get_strategy_launch_method, set_strategy_launch_method

        previous_method = str(get_strategy_launch_method() or "").strip().lower()
        next_method = str(method or "").strip().lower()

        set_strategy_launch_method(next_method)

        direct_methods = ("direct_zapret2", "direct_zapret1")
        if previous_method in direct_methods or next_method in direct_methods:
            if previous_method != next_method:
                log(f"Смена метода {previous_method} -> {next_method}", "INFO")

        return next_method

    @classmethod
    def set_orchestra_setting(cls, key: str, value, *, app=None) -> None:
        normalized_key = str(key or "").strip().lower()

        if normalized_key == "strict_detection":
            from settings.store import set_orchestra_strict_detection

            set_orchestra_strict_detection(bool(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
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
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.auto_restart_on_discord_fail = bool(value)
            return

        if normalized_key == "discord_fails":
            from settings.store import set_orchestra_discord_fails_for_restart

            set_orchestra_discord_fails_for_restart(int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.discord_fails_for_restart = int(value)
            return

        if normalized_key == "lock_successes":
            from settings.store import set_orchestra_lock_successes

            set_orchestra_lock_successes(int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.lock_successes_threshold = int(value)
            return

        if normalized_key == "unlock_fails":
            from settings.store import set_orchestra_unlock_fails

            set_orchestra_unlock_fails(int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.unlock_fails_threshold = int(value)
            return
