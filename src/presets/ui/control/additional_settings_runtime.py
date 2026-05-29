from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log
from presets.ui.control.refresh_runtime_state import (
    ModeControlRefreshRuntime,
    create_refresh_runtime,
)

# Public class ModeControlRefreshRuntime is re-exported here; the small
# implementation lives in refresh_runtime_state to keep early page imports light.

class ControlAdditionalSettingsState:
    def __init__(self, *, discord_restart: bool, wssize_enabled: bool, debug_log_enabled: bool):
        self.discord_restart = bool(discord_restart)
        self.wssize_enabled = bool(wssize_enabled)
        self.debug_log_enabled = bool(debug_log_enabled)


class ControlTopSummaryState:
    def __init__(self, *, preset_text: str, preset_tooltip: str, profile_count: int | None):
        self.preset_text = str(preset_text or "")
        self.preset_tooltip = str(preset_tooltip or "")
        self.profile_count = profile_count


def create_additional_settings_worker(request_id: int, profile_feature, *, launch_method: str, parent=None):
    return profile_feature.create_additional_settings_load_worker(
        request_id,
        parent,
        launch_method=launch_method,
    )


class ControlTopSummaryWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        presets_feature,
        profile_feature,
        *,
        launch_method: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._presets_feature = presets_feature
        self._profile_feature = profile_feature
        self._launch_method = str(launch_method or "").strip()

    def run(self) -> None:
        try:
            preset_text = ""
            preset_tooltip = ""
            try:
                preset_display = self._presets_feature.get_selected_source_preset_display(
                    self._launch_method,
                )
                if preset_display:
                    preset_text = str(preset_display[0] or "")
                    preset_tooltip = str(preset_display[1] or "")
            except Exception as exc:
                log(f"ControlTopSummaryWorker: не удалось прочитать выбранный preset: {exc}", "DEBUG")

            profile_count = None
            try:
                count = self._profile_feature.get_enabled_profile_count_snapshot(
                    self._launch_method,
                )
                profile_count = int(count) if count is not None else None
            except Exception as exc:
                log(f"ControlTopSummaryWorker: не удалось прочитать количество profile: {exc}", "DEBUG")

            state = ControlTopSummaryState(
                preset_text=preset_text,
                preset_tooltip=preset_tooltip,
                profile_count=profile_count,
            )
        except Exception as exc:
            log(f"ControlTopSummaryWorker: не удалось загрузить сводку: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


def create_top_summary_worker(
    request_id: int,
    presets_feature,
    profile_feature,
    *,
    launch_method: str,
    parent=None,
):
    return ControlTopSummaryWorker(
        request_id,
        presets_feature,
        profile_feature,
        launch_method=launch_method,
        parent=parent,
    )


class AdditionalSettingsSaveWorker(QThread):
    saved = pyqtSignal(int, str, bool)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        profile_feature,
        *,
        launch_method: str,
        setting: str,
        enabled: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile_feature = profile_feature
        self._launch_method = str(launch_method or "").strip()
        self._setting = str(setting or "").strip()
        self._enabled = bool(enabled)

    def run(self) -> None:
        try:
            if self._setting == "discord_restart":
                from discord.discord_restart import set_discord_restart_setting

                set_discord_restart_setting(self._enabled)
            elif self._setting == "wssize":
                self._profile_feature.set_wssize_enabled(
                    self._enabled,
                    launch_method=self._launch_method,
                )
            elif self._setting == "debug_log":
                self._profile_feature.set_debug_log_enabled(
                    self._enabled,
                    launch_method=self._launch_method,
                )
            else:
                raise ValueError(f"Неизвестная дополнительная настройка: {self._setting}")
        except Exception as exc:
            log(f"AdditionalSettingsSaveWorker: не удалось сохранить настройку {self._setting}: {exc}", "ERROR")
            self.failed.emit(self._request_id, self._setting, str(exc))
            return
        self.saved.emit(self._request_id, self._setting, self._enabled)


def create_additional_settings_save_worker(
    request_id: int,
    profile_feature,
    *,
    launch_method: str,
    setting: str,
    enabled: bool,
    parent=None,
):
    return AdditionalSettingsSaveWorker(
        request_id,
        profile_feature,
        launch_method=launch_method,
        setting=setting,
        enabled=enabled,
        parent=parent,
    )


def build_additional_settings_state(state: dict | None) -> ControlAdditionalSettingsState:
    state = state if isinstance(state, dict) else {}
    return ControlAdditionalSettingsState(
        discord_restart=bool(state.get("discord_restart", True)),
        wssize_enabled=bool(state.get("wssize_enabled", False)),
        debug_log_enabled=bool(state.get("debug_log_enabled", False)),
    )
