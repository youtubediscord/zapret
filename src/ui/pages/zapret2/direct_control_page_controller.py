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
    payload: dict = {
        "active_preset_name": "",
        "active_lists": [],
    }
    try:
        from core.services import get_direct_flow_coordinator
        from core.presets.direct_facade import DirectPresetFacade

        preset = get_direct_flow_coordinator().get_selected_source_manifest("direct_zapret2")
        payload["active_preset_name"] = str(getattr(preset, "name", "") or "").strip()

        source_text = DirectPresetFacade.from_launch_method("direct_zapret2").read_selected_source_text()
        active_lists: list[str] = []
        seen_lists: set[str] = set()

        for raw in str(source_text or "").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for value in _HOSTLIST_DISPLAY_RE.findall(stripped):
                list_path = value.strip().strip('"').strip("'")
                if not list_path:
                    continue

                normalized = list_path.replace("\\", "/")
                list_name = normalized.rsplit("/", 1)[-1]
                if not list_name:
                    continue

                dedupe_key = list_name.lower()
                if dedupe_key in seen_lists:
                    continue
                seen_lists.add(dedupe_key)
                active_lists.append(list_name)

        payload["active_lists"] = active_lists
    except Exception:
        pass

    return payload


_HOSTLIST_DISPLAY_RE = re.compile(r"--(?:hostlist|hostlist-exclude)=([^\s]+)")


class Zapret2DirectControlPageController(ControlPageController):
    @staticmethod
    def create_advanced_settings_worker(request_id: int, parent=None) -> AdvancedSettingsLoadWorker:
        return AdvancedSettingsLoadWorker(request_id, parent)

    @staticmethod
    def create_preset_summary_worker(request_id: int, parent=None) -> DirectPresetSummaryLoadWorker:
        return DirectPresetSummaryLoadWorker(request_id, parent)

    @staticmethod
    def load_program_settings() -> ControlProgramSettingsPlan:
        return ControlPageController.load_program_settings()

    @staticmethod
    def save_auto_dpi(enabled: bool) -> ControlAutoDpiPlan:
        return ControlPageController.save_auto_dpi(enabled)

    @staticmethod
    def reset_startup_cache() -> tuple[bool, str]:
        return ControlPageController.reset_startup_cache()

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

    def build_status_plan(self, *, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
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
                description=self.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
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

    def build_defender_toggle_start_plan(self, *, disable: bool, language: str) -> ControlToggleActionStartPlan:
        from ui.text_catalog import tr as tr_catalog

        if not self.is_user_admin():
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
    def run_defender_toggle(*, disable: bool, status_callback=None) -> ControlActionResultPlan:
        return ControlPageController.run_defender_toggle(disable=disable, status_callback=status_callback)

    def build_max_block_toggle_start_plan(self, *, enable: bool, language: str) -> ControlToggleActionStartPlan:
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

    @staticmethod
    def run_max_block_toggle(*, enable: bool, status_callback=None) -> ControlActionResultPlan:
        return ControlPageController.run_max_block_toggle(enable=enable, status_callback=status_callback)
