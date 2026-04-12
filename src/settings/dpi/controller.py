from __future__ import annotations

from dataclasses import dataclass

from log import log


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
        from config import REGISTRY_PATH

        return f"{REGISTRY_PATH}\\Orchestra"

    @classmethod
    def load_orchestra_settings(cls) -> DpiOrchestraSettingsState:
        from config.reg import reg

        path = cls._orchestra_reg_path()
        strict_detection = reg(path, "StrictDetection")
        debug_file = reg(path, "KeepDebugFile")
        auto_restart = reg(path, "AutoRestartOnDiscordFail")
        discord_fails = reg(path, "DiscordFailsForRestart")
        lock_successes = reg(path, "LockSuccesses")
        unlock_fails = reg(path, "UnlockFails")

        return DpiOrchestraSettingsState(
            strict_detection=bool(True if strict_detection is None else strict_detection),
            debug_file=bool(debug_file),
            auto_restart_discord=bool(True if auto_restart is None else auto_restart),
            discord_fails=int(discord_fails if discord_fails is not None else 3),
            lock_successes=int(lock_successes if lock_successes is not None else 3),
            unlock_fails=int(unlock_fails if unlock_fails is not None else 3),
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
        from config.reg import reg

        path = cls._orchestra_reg_path()
        normalized_key = str(key or "").strip().lower()

        if normalized_key == "strict_detection":
            reg(path, "StrictDetection", 1 if bool(value) else 0)
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.set_strict_detection(bool(value))
            return

        if normalized_key == "debug_file":
            reg(path, "KeepDebugFile", 1 if bool(value) else 0)
            return

        if normalized_key == "auto_restart_discord":
            reg(path, "AutoRestartOnDiscordFail", 1 if bool(value) else 0)
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.auto_restart_on_discord_fail = bool(value)
            return

        if normalized_key == "discord_fails":
            reg(path, "DiscordFailsForRestart", int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.discord_fails_for_restart = int(value)
            return

        if normalized_key == "lock_successes":
            reg(path, "LockSuccesses", int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.lock_successes_threshold = int(value)
            return

        if normalized_key == "unlock_fails":
            reg(path, "UnlockFails", int(value))
            runner = getattr(app, "orchestra_runner", None) if app is not None else None
            if runner:
                runner.unlock_fails_threshold = int(value)
            return
