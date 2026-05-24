from __future__ import annotations


class ControlAdditionalSettingsState:
    def __init__(self, *, discord_restart: bool, wssize_enabled: bool, debug_log_enabled: bool):
        self.discord_restart = bool(discord_restart)
        self.wssize_enabled = bool(wssize_enabled)
        self.debug_log_enabled = bool(debug_log_enabled)


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.additional_settings_worker = None
        self.additional_settings_request_id = 0
        self.additional_settings_dirty = True

    def has_pending_refresh(self) -> bool:
        return bool(self.additional_settings_dirty)

    def mark_presets_dirty(self) -> None:
        self.additional_settings_dirty = True

    def mark_additional_settings_applied(self) -> None:
        self.additional_settings_dirty = False
        self.additional_settings_worker = None

    def mark_additional_settings_written(self) -> None:
        self.additional_settings_request_id += 1
        self.additional_settings_dirty = False
        self.additional_settings_worker = None

    def next_additional_settings_request_id(self) -> int:
        self.additional_settings_request_id += 1
        return self.additional_settings_request_id

    def accept_additional_settings_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.additional_settings_request_id):
            return False
        self.mark_additional_settings_applied()
        return True


def create_refresh_runtime() -> ModeControlRefreshRuntime:
    return ModeControlRefreshRuntime()


def create_additional_settings_worker(request_id: int, profile_feature, *, launch_method: str, parent=None):
    return profile_feature.create_additional_settings_load_worker(
        request_id,
        parent,
        launch_method=launch_method,
    )


def build_additional_settings_state(state: dict | None) -> ControlAdditionalSettingsState:
    state = state if isinstance(state, dict) else {}
    return ControlAdditionalSettingsState(
        discord_restart=bool(state.get("discord_restart", True)),
        wssize_enabled=bool(state.get("wssize_enabled", False)),
        debug_log_enabled=bool(state.get("debug_log_enabled", False)),
    )


def save_discord_restart_setting(enabled: bool) -> None:
    try:
        from discord.discord_restart import set_discord_restart_setting

        set_discord_restart_setting(bool(enabled))
    except Exception:
        pass
