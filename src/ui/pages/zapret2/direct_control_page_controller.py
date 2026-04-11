from __future__ import annotations

import os
import re

from PyQt6.QtCore import QThread, pyqtSignal

from ui.control_page_controller import (
    ControlActionResultPlan,
    ControlAutoDpiPlan,
    ControlConfirmationDialogPlan,
    ControlPageController,
    ControlProgramSettingsPlan,
    ControlStatusPlan,
    ControlStopButtonPlan,
    ControlToggleActionStartPlan,
)
from ui.text_catalog import tr as tr_catalog


class AdvancedSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        state: dict = {}
        try:
            from core.presets.direct_facade import DirectPresetFacade

            state = DirectPresetFacade.from_launch_method("direct_zapret2").get_advanced_settings_state() or {}
        except Exception:
            state = {}
        self.loaded.emit(self._request_id, state)


class DirectPresetSummaryLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        self.loaded.emit(self._request_id, load_direct_zapret2_preset_summary_payload())


def load_direct_zapret2_preset_summary_payload() -> dict:
    try:
        from core.services import get_direct_ui_snapshot_service

        return get_direct_ui_snapshot_service().load_preset_summary_payload("direct_zapret2")
    except Exception:
        return {
            "active_preset_name": "",
            "active_lists": [],
        }


_HOSTLIST_DISPLAY_RE = re.compile(r"--(?:hostlist|hostlist-exclude)=([^\s]+)")


class DirectAdvancedSettingsApplyPlan:
    def __init__(self, *, discord_restart: bool, wssize_enabled: bool, debug_log_enabled: bool):
        self.discord_restart = bool(discord_restart)
        self.wssize_enabled = bool(wssize_enabled)
        self.debug_log_enabled = bool(debug_log_enabled)


class DirectPresetSummaryPlan:
    def __init__(self, *, preset_name_text: str, preset_name_tooltip: str, strategy_text: str, strategy_tooltip: str):
        self.preset_name_text = preset_name_text
        self.preset_name_tooltip = preset_name_tooltip
        self.strategy_text = strategy_text
        self.strategy_tooltip = strategy_tooltip


class DirectModeLabelPlan:
    def __init__(self, *, mode: str, label_text: str):
        self.mode = mode
        self.label_text = label_text


class DirectModeChangePlan:
    def __init__(self, *, should_apply: bool, refresh_strategy_after: bool, refresh_mode_label_after: bool):
        self.should_apply = bool(should_apply)
        self.refresh_strategy_after = bool(refresh_strategy_after)
        self.refresh_mode_label_after = bool(refresh_mode_label_after)


class DirectControlRefreshRuntime:
    def __init__(self) -> None:
        self.advanced_settings_worker = None
        self.advanced_settings_request_id = 0
        self.advanced_settings_dirty = True
        self.preset_summary_worker = None
        self.preset_summary_request_id = 0
        self.preset_summary_dirty = True

    def has_pending_refresh(self) -> bool:
        return bool(self.advanced_settings_dirty or self.preset_summary_dirty)

    def mark_presets_dirty(self) -> None:
        self.advanced_settings_dirty = True
        self.preset_summary_dirty = True

    def mark_advanced_settings_applied(self) -> None:
        self.advanced_settings_dirty = False
        self.advanced_settings_worker = None

    def mark_preset_summary_applied(self) -> None:
        self.preset_summary_dirty = False
        self.preset_summary_worker = None

    def mark_advanced_settings_written(self) -> None:
        self.advanced_settings_request_id += 1
        self.advanced_settings_dirty = False
        self.advanced_settings_worker = None

    def next_advanced_settings_request_id(self) -> int:
        self.advanced_settings_request_id += 1
        return self.advanced_settings_request_id

    def next_preset_summary_request_id(self) -> int:
        self.preset_summary_request_id += 1
        return self.preset_summary_request_id

    def accept_advanced_settings_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.advanced_settings_request_id):
            return False
        self.mark_advanced_settings_applied()
        return True

    def accept_preset_summary_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.preset_summary_request_id):
            return False
        self.mark_preset_summary_applied()
        return True


class Zapret2DirectControlPageController(ControlPageController):
    @staticmethod
    def create_refresh_runtime() -> DirectControlRefreshRuntime:
        return DirectControlRefreshRuntime()

    @staticmethod
    def load_advanced_settings_state() -> dict:
        try:
            from core.services import get_direct_ui_snapshot_service

            return get_direct_ui_snapshot_service().load_advanced_settings_state("direct_zapret2")
        except Exception:
            return {}

    @staticmethod
    def load_preset_summary_payload() -> dict:
        return load_direct_zapret2_preset_summary_payload()

    @staticmethod
    def create_advanced_settings_worker(request_id: int, parent=None) -> AdvancedSettingsLoadWorker:
        return AdvancedSettingsLoadWorker(request_id, parent)

    @staticmethod
    def create_preset_summary_worker(request_id: int, parent=None) -> DirectPresetSummaryLoadWorker:
        return DirectPresetSummaryLoadWorker(request_id, parent)

    @staticmethod
    def build_advanced_settings_apply_plan(state: dict | None) -> DirectAdvancedSettingsApplyPlan:
        state = state if isinstance(state, dict) else {}
        return DirectAdvancedSettingsApplyPlan(
            discord_restart=bool(state.get("discord_restart", True)),
            wssize_enabled=bool(state.get("wssize_enabled", False)),
            debug_log_enabled=bool(state.get("debug_log_enabled", False)),
        )

    @staticmethod
    def build_preset_summary_plan(payload: dict | None, *, language: str) -> DirectPresetSummaryPlan:
        payload = payload if isinstance(payload, dict) else {}
        active_preset_name = str(payload.get("active_preset_name") or "").strip()
        active_lists = list(payload.get("active_lists") or [])

        if active_preset_name:
            preset_name_text = active_preset_name
            preset_name_tooltip = active_preset_name
        else:
            preset_name_text = tr_catalog(
                "page.z2_control.preset.not_selected",
                language=language,
                default="Не выбран",
            )
            preset_name_tooltip = ""

        if active_lists:
            strategy_text = " • ".join(active_lists)
            strategy_tooltip = "\n".join(active_lists)
        else:
            strategy_text = tr_catalog(
                "page.z2_control.preset.no_active_lists",
                language=language,
                default="Нет активных листов",
            )
            strategy_tooltip = ""

        return DirectPresetSummaryPlan(
            preset_name_text=preset_name_text,
            preset_name_tooltip=preset_name_tooltip,
            strategy_text=strategy_text,
            strategy_tooltip=strategy_tooltip,
        )

    @staticmethod
    def get_direct_launch_mode_setting() -> str:
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode

            mode = (get_direct_zapret2_ui_mode() or "").strip().lower()
            if mode in ("basic", "advanced"):
                return mode
        except Exception:
            pass
        return "advanced"

    @staticmethod
    def build_direct_mode_label_plan(*, language: str) -> DirectModeLabelPlan:
        mode = Zapret2DirectControlPageController.get_direct_launch_mode_setting()
        key = "page.z2_control.mode.basic" if mode == "basic" else "page.z2_control.mode.advanced"
        default = "Basic" if mode == "basic" else "Advanced"
        return DirectModeLabelPlan(
            mode=mode,
            label_text=tr_catalog(key, language=language, default=default),
        )

    @staticmethod
    def build_direct_mode_change_plan(*, wanted_mode: str, current_mode: str) -> DirectModeChangePlan:
        wanted = str(wanted_mode or "").strip().lower()
        current = str(current_mode or "").strip().lower()
        if wanted not in ("basic", "advanced") or wanted == current:
            return DirectModeChangePlan(
                should_apply=False,
                refresh_strategy_after=False,
                refresh_mode_label_after=True,
            )
        return DirectModeChangePlan(
            should_apply=True,
            refresh_strategy_after=True,
            refresh_mode_label_after=True,
        )

    @staticmethod
    def apply_direct_mode_change(*, wanted_mode: str, parent_app) -> None:
        wanted = str(wanted_mode or "").strip().lower()
        if wanted not in ("basic", "advanced"):
            return

        try:
            from strategy_menu.ui_prefs_store import set_direct_zapret2_ui_mode

            set_direct_zapret2_ui_mode(wanted)
        except Exception:
            pass

        try:
            from dpi.direct_runtime_apply_policy import request_direct_runtime_content_apply
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method(
                "direct_zapret2",
                on_dpi_reload_needed=lambda: request_direct_runtime_content_apply(
                    parent_app,
                    launch_method="direct_zapret2",
                    reason="direct_launch_mode_changed",
                ),
            )
            selections = facade.get_strategy_selections() or {}
            facade.set_strategy_selections(selections, save_and_sync=True)
        except Exception:
            pass

    @staticmethod
    def save_discord_restart_setting(enabled: bool) -> None:
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
        except Exception:
            pass

    @staticmethod
    def save_wssize_enabled(enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_wssize_enabled(bool(enabled))
        except Exception:
            pass

    @staticmethod
    def save_debug_log_enabled(enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_debug_log_enabled(bool(enabled))
        except Exception:
            pass

    @staticmethod
    def build_stop_button_plan(*, language: str) -> ControlStopButtonPlan:
        try:
            from strategy_menu.launch_method_store import get_strategy_launch_method
            from config import get_winws_exe_for_method
            from ui.text_catalog import tr as tr_catalog

            method = get_strategy_launch_method()
            exe_name = os.path.basename(get_winws_exe_for_method(method)) or "winws.exe"
            template = tr_catalog(
                "page.z2_control.button.stop_only_template",
                language=language,
                default="Остановить только {exe_name}",
            )
            return ControlStopButtonPlan(text=template.format(exe_name=exe_name))
        except Exception:
            from ui.text_catalog import tr as tr_catalog

            return ControlStopButtonPlan(
                text=tr_catalog(
                    "page.z2_control.button.stop_only_winws",
                    language=language,
                    default="Остановить только winws.exe",
                )
            )

    @staticmethod
    def build_status_plan(*, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
        from ui.text_catalog import tr as tr_catalog

        phase = str(state or "").strip().lower()
        if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        if phase == "running":
            return ControlStatusPlan(
                phase=phase,
                title=tr_catalog("page.z2_control.status.running", language=language, default="Zapret работает"),
                description=tr_catalog("page.z2_control.status.bypass_active", language=language, default="Обход блокировок активен"),
                dot_color="#6ccb5f",
                pulsing=True,
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
                description=ControlPageController.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
                dot_color="#ff6b6b",
                pulsing=False,
                show_start=True,
                show_stop_only=False,
                show_stop_and_exit=False,
            )
        return ControlStatusPlan(
            phase="stopped",
            title=tr_catalog("page.z2_control.status.stopped", language=language, default="Zapret остановлен"),
            description=tr_catalog("page.z2_control.status.press_start", language=language, default="Нажмите «Запустить» для активации"),
            dot_color="#ff6b6b",
            pulsing=False,
            show_start=True,
            show_stop_only=False,
            show_stop_and_exit=False,
        )

    @staticmethod
    def build_defender_toggle_start_plan(*, disable: bool, language: str) -> ControlToggleActionStartPlan:
        from ui.text_catalog import tr as tr_catalog

        if not ControlPageController.is_user_admin():
            return ControlToggleActionStartPlan(
                blocked=True,
                blocked_title="Требуются права администратора",
                blocked_content=(
                    "Для управления Windows Defender требуются права администратора. "
                    "Перезапустите программу от имени администратора."
                ),
                blocked_revert_checked=not bool(disable),
                confirmations=(),
                start_status="",
            )

        if disable:
            return ControlToggleActionStartPlan(
                blocked=False,
                blocked_title="",
                blocked_content="",
                blocked_revert_checked=None,
                confirmations=(
                    ControlConfirmationDialogPlan(
                        title=tr_catalog(
                            "page.z2_control.dialog.defender_disable.title",
                            language=language,
                            default="⚠️ Отключение Windows Defender",
                        ),
                        content=(
                            "Вы собираетесь отключить встроенную антивирусную защиту Windows.\n\n"
                            "Что произойдёт:\n"
                            "• Защита в реальном времени будет отключена\n"
                            "• Облачная защита и SmartScreen будут отключены\n"
                            "• Автоматическая отправка образцов будет отключена\n"
                            "• Мониторинг поведения программ будет отключён\n\n"
                            "⚠️ Ваш компьютер станет уязвим для вирусов и вредоносного ПО.\n"
                            "Отключайте только если вы понимаете, что делаете.\n"
                            "Вы сможете включить Defender обратно в любой момент."
                        ),
                        revert_checked=False,
                    ),
                    ControlConfirmationDialogPlan(
                        title="Подтверждение",
                        content=(
                            "Вы уверены? Нажимая «ОК», вы подтверждаете, что:\n\n"
                            "• Вы самостоятельно приняли решение отключить Windows Defender\n"
                            "• Вы осознаёте риски работы без антивирусной защиты\n"
                            "• Вы знаете, что можете включить защиту обратно\n\n"
                            "Может потребоваться перезагрузка для полного применения."
                        ),
                        revert_checked=False,
                    ),
                ),
                start_status="Отключение Windows Defender...",
            )

        return ControlToggleActionStartPlan(
            blocked=False,
            blocked_title="",
            blocked_content="",
            blocked_revert_checked=None,
            confirmations=(
                ControlConfirmationDialogPlan(
                    title=tr_catalog(
                        "page.z2_control.dialog.defender_enable.title",
                        language=language,
                        default="Включение Windows Defender",
                    ),
                    content="Включить Windows Defender обратно?\n\nЭто восстановит защиту вашего компьютера.",
                    revert_checked=True,
                ),
            ),
            start_status="Включение Windows Defender...",
        )

    @staticmethod
    def build_max_block_toggle_start_plan(*, enable: bool, language: str) -> ControlToggleActionStartPlan:
        from ui.text_catalog import tr as tr_catalog

        if enable:
            return ControlToggleActionStartPlan(
                blocked=False,
                blocked_title="",
                blocked_content="",
                blocked_revert_checked=None,
                confirmations=(
                    ControlConfirmationDialogPlan(
                        title=tr_catalog(
                            "page.z2_control.dialog.max_block_enable.title",
                            language=language,
                            default="Блокировка MAX",
                        ),
                        content=(
                            "Включить блокировку установки и работы программы MAX?\n\n"
                            "• Заблокирует запуск max.exe, max.msi и других файлов MAX\n"
                            "• Добавит правила блокировки в Windows Firewall\n"
                            "• Заблокирует домены MAX в файле hosts"
                        ),
                        revert_checked=False,
                    ),
                ),
                start_status="",
            )

        return ControlToggleActionStartPlan(
            blocked=False,
            blocked_title="",
            blocked_content="",
            blocked_revert_checked=None,
            confirmations=(
                ControlConfirmationDialogPlan(
                    title=tr_catalog(
                        "page.z2_control.dialog.max_block_disable.title",
                        language=language,
                        default="Отключение блокировки MAX",
                    ),
                    content="Отключить блокировку программы MAX?\n\nЭто удалит все созданные блокировки и правила.",
                    revert_checked=True,
                ),
            ),
            start_status="",
        )

