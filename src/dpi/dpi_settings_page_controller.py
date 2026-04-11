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
    show_advanced: bool
    show_discord_restart: bool
    show_orchestra_settings: bool


@dataclass(slots=True)
class DpiSettingsState:
    launch_method: str
    discord_restart_enabled: bool
    orchestra: DpiOrchestraSettingsState
    wssize_enabled: bool
    debug_log_enabled: bool
    visibility: DpiVisibilityState


class DpiSettingsPageController:
    @staticmethod
    def get_launch_method() -> str:
        from strategy_menu import get_strategy_launch_method

        return str(get_strategy_launch_method() or "").strip().lower()

    @staticmethod
    def get_discord_restart_enabled() -> bool:
        from discord.discord_restart import get_discord_restart_setting

        return bool(get_discord_restart_setting(default=True))

    @staticmethod
    def set_discord_restart_enabled(enabled: bool) -> None:
        from discord.discord_restart import set_discord_restart_setting

        set_discord_restart_setting(bool(enabled))

    @staticmethod
    def describe_visibility(method: str) -> DpiVisibilityState:
        method = str(method or "").strip().lower()
        is_direct_mode = method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
        is_zapret_mode = method in ("direct_zapret2", "direct_zapret1")
        return DpiVisibilityState(
            show_advanced=bool(is_direct_mode and method != "direct_zapret2"),
            show_discord_restart=bool(is_zapret_mode and method != "direct_zapret2"),
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

    @classmethod
    def get_filter_state(cls, kind: str, method: str | None = None) -> bool:
        facade = cls._get_direct_toggle_facade(method)
        if facade is not None:
            if kind == "wssize":
                return bool(facade.get_wssize_enabled())
            return bool(facade.get_debug_log_enabled())

        if kind == "wssize":
            from strategy_menu import get_wssize_enabled

            return bool(get_wssize_enabled())

        from strategy_menu import get_debug_log_enabled

        return bool(get_debug_log_enabled())

    @classmethod
    def set_filter_state(cls, kind: str, value: bool, method: str | None = None) -> bool:
        facade = cls._get_direct_toggle_facade(method)
        if facade is not None:
            if kind == "wssize":
                return bool(facade.set_wssize_enabled(bool(value)))
            return bool(facade.set_debug_log_enabled(bool(value)))

        if kind == "wssize":
            from strategy_menu import set_wssize_enabled

            return bool(set_wssize_enabled(bool(value)))

        from strategy_menu import set_debug_log_enabled

        return bool(set_debug_log_enabled(bool(value)))

    @classmethod
    def load_state(cls) -> DpiSettingsState:
        launch_method = cls.get_launch_method()
        return DpiSettingsState(
            launch_method=launch_method,
            discord_restart_enabled=cls.get_discord_restart_enabled(),
            orchestra=cls.load_orchestra_settings(),
            wssize_enabled=cls.get_filter_state("wssize", launch_method),
            debug_log_enabled=cls.get_filter_state("debug", launch_method),
            visibility=cls.describe_visibility(launch_method),
        )

    @staticmethod
    def apply_launch_method(method: str) -> str:
        from core.services import reset_cached_services
        from strategy_menu import get_strategy_launch_method, set_strategy_launch_method

        previous_method = str(get_strategy_launch_method() or "").strip().lower()
        next_method = str(method or "").strip().lower()

        if next_method == "direct_zapret2_orchestra":
            from preset_orchestra_zapret2 import ensure_default_preset_exists

            ensure_default_preset_exists()

        set_strategy_launch_method(next_method)

        direct_methods = ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1")
        if previous_method in direct_methods or next_method in direct_methods:
            if previous_method != next_method:
                log(f"Смена метода {previous_method} -> {next_method}, сброс direct-кэша...", "INFO")
                reset_cached_services()

        registry_driven_methods = {"direct_zapret2_orchestra", "orchestra"}
        if (
            previous_method != next_method
            and (previous_method in registry_driven_methods or next_method in registry_driven_methods)
        ):
            try:
                from preset_orchestra_zapret2.catalog import invalidate_categories_cache

                invalidate_categories_cache()
            except Exception:
                pass

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

    @classmethod
    def _get_direct_toggle_facade(cls, method: str | None = None):
        try:
            resolved_method = str(method or cls.get_launch_method()).strip().lower()
            if resolved_method in ("direct_zapret2", "direct_zapret1"):
                from core.presets.direct_facade import DirectPresetFacade

                return DirectPresetFacade.from_launch_method(resolved_method)
        except Exception:
            pass
        return None
