from __future__ import annotations

from settings.mode import EXE_NAME_WINWS1, ZAPRET2_MODE
from presets.ui.control import control_runtime
from presets.ui.control.control_runtime import ControlStatusPlan, ControlStopButtonPlan
from profile.ui_mode import (
    PROFILE_UI_MODE_DEFAULT,
    load_current_profile_ui_mode,
    normalize_profile_ui_mode,
    save_current_profile_ui_mode,
)
from app.text_catalog import tr as tr_catalog


class ProfileAdvancedSettingsApplyPlan:
    def __init__(self, *, discord_restart: bool, wssize_enabled: bool, debug_log_enabled: bool):
        self.discord_restart = bool(discord_restart)
        self.wssize_enabled = bool(wssize_enabled)
        self.debug_log_enabled = bool(debug_log_enabled)


class ProfileUiModeLabelPlan:
    def __init__(self, *, mode: str, label_text: str):
        self.mode = mode
        self.label_text = label_text


class ProfileUiModeChangePlan:
    def __init__(self, *, should_apply: bool, refresh_strategy_after: bool, refresh_mode_label_after: bool):
        self.should_apply = bool(should_apply)
        self.refresh_strategy_after = bool(refresh_strategy_after)
        self.refresh_mode_label_after = bool(refresh_mode_label_after)


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.advanced_settings_worker = None
        self.advanced_settings_request_id = 0
        self.advanced_settings_dirty = True

    def has_pending_refresh(self) -> bool:
        return bool(self.advanced_settings_dirty)

    def mark_presets_dirty(self) -> None:
        self.advanced_settings_dirty = True

    def mark_advanced_settings_applied(self) -> None:
        self.advanced_settings_dirty = False
        self.advanced_settings_worker = None

    def mark_advanced_settings_written(self) -> None:
        self.advanced_settings_request_id += 1
        self.advanced_settings_dirty = False
        self.advanced_settings_worker = None

    def next_advanced_settings_request_id(self) -> int:
        self.advanced_settings_request_id += 1
        return self.advanced_settings_request_id

    def accept_advanced_settings_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.advanced_settings_request_id):
            return False
        self.mark_advanced_settings_applied()
        return True

def create_refresh_runtime() -> ModeControlRefreshRuntime:
    return ModeControlRefreshRuntime()

def load_advanced_settings_state(*, profile_feature) -> dict:
    try:
        return profile_feature.get_advanced_settings_state(ZAPRET2_MODE) or {}
    except Exception:
        return {}

def create_advanced_settings_worker(request_id: int, profile_feature, parent=None):
    return profile_feature.create_advanced_settings_load_worker(request_id, parent)

def build_advanced_settings_apply_plan(state: dict | None) -> ProfileAdvancedSettingsApplyPlan:
    state = state if isinstance(state, dict) else {}
    return ProfileAdvancedSettingsApplyPlan(
        discord_restart=bool(state.get("discord_restart", True)),
        wssize_enabled=bool(state.get("wssize_enabled", False)),
        debug_log_enabled=bool(state.get("debug_log_enabled", False)),
    )

def get_profile_ui_mode_setting() -> str:
    _ = load_current_profile_ui_mode
    return PROFILE_UI_MODE_DEFAULT

def build_profile_ui_mode_label_plan(*, language: str) -> ProfileUiModeLabelPlan:
    mode = PROFILE_UI_MODE_DEFAULT
    key = "page.winws2_control.mode.basic"
    default = "Basic"
    return ProfileUiModeLabelPlan(
        mode=mode,
        label_text=tr_catalog(key, language=language, default=default),
    )

def build_profile_ui_mode_change_plan(*, wanted_mode: str, current_mode: str) -> ProfileUiModeChangePlan:
    _ = (wanted_mode, current_mode, normalize_profile_ui_mode)
    return ProfileUiModeChangePlan(
        should_apply=False,
        refresh_strategy_after=False,
        refresh_mode_label_after=True,
    )

def apply_profile_ui_mode_change(*, wanted_mode: str, reload_host) -> None:
    _ = (wanted_mode, reload_host)

    save_current_profile_ui_mode(PROFILE_UI_MODE_DEFAULT)

def save_discord_restart_setting(enabled: bool) -> None:
    try:
        from discord.discord_restart import set_discord_restart_setting

        set_discord_restart_setting(bool(enabled))
    except Exception:
        pass

def save_wssize_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    try:
        profile_feature.set_wssize_enabled(
            bool(enabled),
            launch_method=ZAPRET2_MODE,
        )
        runtime_feature.apply_preset_content(launch_method=ZAPRET2_MODE, reason="profile_wssize_changed")
    except Exception:
        pass

def save_debug_log_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    try:
        profile_feature.set_debug_log_enabled(
            bool(enabled),
            launch_method=ZAPRET2_MODE,
        )
        runtime_feature.apply_preset_content(launch_method=ZAPRET2_MODE, reason="profile_debug_log_changed")
    except Exception:
        pass

def build_stop_button_plan(*, language: str) -> ControlStopButtonPlan:
    try:
        from settings.mode import exe_name_for_launch_method
        from ui.workflows.common import get_current_launch_method

        from app.text_catalog import tr as tr_catalog

        method = get_current_launch_method(default="")
        exe_name = exe_name_for_launch_method(method)
        template = tr_catalog(
            "page.winws2_control.button.stop_only_template",
            language=language,
            default="Остановить только {exe_name}",
        )
        return ControlStopButtonPlan(text=template.format(exe_name=exe_name))
    except Exception:
        from app.text_catalog import tr as tr_catalog

        return ControlStopButtonPlan(
            text=tr_catalog(
                "page.winws2_control.button.stop_only_winws",
                language=language,
                default=f"Остановить только {EXE_NAME_WINWS1}",
            )
        )

def build_status_plan(*, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
    from app.text_catalog import tr as tr_catalog

    phase = str(state or "").strip().lower()
    if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
        phase = "running" if bool(state) else "stopped"

    if phase == "running":
        return ControlStatusPlan(
            phase=phase,
            title=tr_catalog("page.winws2_control.status.running", language=language, default="Zapret работает"),
            description=tr_catalog("page.winws2_control.status.bypass_active", language=language, default="Обход блокировок активен"),
            dot_color="#6ccb5f",
            pulsing=False,
            show_start=False,
            show_stop_only=True,
            show_stop_and_exit=True,
        )
    if phase == "autostart_pending":
        return ControlStatusPlan(
            phase=phase,
            title="Автозапуск Zapret запланирован",
            description="Подготавливаем стартовый запуск выбранного пресета",
            dot_color="#f5a623",
            pulsing=True,
            show_start=False,
            show_stop_only=False,
            show_stop_and_exit=False,
        )
    if phase == "starting":
        return ControlStatusPlan(
            phase=phase,
            title="Zapret запускается",
            description="Ждём подтверждение процесса winws",
            dot_color="#f5a623",
            pulsing=True,
            show_start=False,
            show_stop_only=False,
            show_stop_and_exit=False,
        )
    if phase == "stopping":
        return ControlStatusPlan(
            phase=phase,
            title="Zapret останавливается",
            description="Завершаем процесс и освобождаем WinDivert",
            dot_color="#f5a623",
            pulsing=True,
            show_start=False,
            show_stop_only=False,
            show_stop_and_exit=False,
        )
    if phase == "failed":
        return ControlStatusPlan(
            phase=phase,
            title="Ошибка запуска Zapret",
            description=control_runtime.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
            dot_color="#ff6b6b",
            pulsing=False,
            show_start=True,
            show_stop_only=False,
            show_stop_and_exit=False,
        )
    return ControlStatusPlan(
        phase="stopped",
        title=tr_catalog("page.winws2_control.status.stopped", language=language, default="Zapret остановлен"),
        description=tr_catalog("page.winws2_control.status.press_start", language=language, default="Нажмите «Запустить» для активации"),
        dot_color="#ff6b6b",
        pulsing=False,
        show_start=True,
        show_stop_only=False,
        show_stop_and_exit=False,
    )
