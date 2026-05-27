from __future__ import annotations

from settings.mode import EXE_NAME_WINWS1, ZAPRET2_MODE
from presets.ui.control import control_runtime
from presets.ui.control.control_runtime import ControlStatusPlan, ControlStopButtonPlan
from presets.ui.control.additional_settings_runtime import (
    build_additional_settings_state,
    create_refresh_runtime,
    save_discord_restart_setting,
)
from profile.ui_mode import (
    PROFILE_UI_MODE_DEFAULT,
    load_current_profile_ui_mode,
    normalize_profile_ui_mode,
    save_current_profile_ui_mode,
)
from app.ui_texts import tr as tr_catalog


class ProfileUiModeLabelPlan:
    def __init__(self, *, mode: str, label_text: str):
        self.mode = mode
        self.label_text = label_text


class ProfileUiModeChangePlan:
    def __init__(self, *, should_apply: bool, refresh_strategy_after: bool, refresh_mode_label_after: bool):
        self.should_apply = bool(should_apply)
        self.refresh_strategy_after = bool(refresh_strategy_after)
        self.refresh_mode_label_after = bool(refresh_mode_label_after)


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

def save_wssize_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    _ = runtime_feature
    try:
        profile_feature.set_wssize_enabled(
            bool(enabled),
            launch_method=ZAPRET2_MODE,
        )
    except Exception:
        pass

def save_debug_log_enabled(enabled: bool, *, profile_feature, runtime_feature) -> None:
    _ = runtime_feature
    try:
        profile_feature.set_debug_log_enabled(
            bool(enabled),
            launch_method=ZAPRET2_MODE,
        )
    except Exception:
        pass

def build_stop_button_plan(*, language: str) -> ControlStopButtonPlan:
    try:
        from settings.mode import exe_name_for_launch_method
        from ui.workflows.common import get_current_launch_method

        from app.ui_texts import tr as tr_catalog

        method = get_current_launch_method(default="")
        exe_name = exe_name_for_launch_method(method)
        template = tr_catalog(
            "page.winws2_control.button.stop_only_template",
            language=language,
            default="Остановить только {exe_name}",
        )
        return ControlStopButtonPlan(text=template.format(exe_name=exe_name))
    except Exception:
        from app.ui_texts import tr as tr_catalog

        return ControlStopButtonPlan(
            text=tr_catalog(
                "page.winws2_control.button.stop_only_winws",
                language=language,
                default=f"Остановить только {EXE_NAME_WINWS1}",
            )
        )

def build_status_plan(*, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
    from app.ui_texts import tr as tr_catalog

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
