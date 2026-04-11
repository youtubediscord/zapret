from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class ControlProgramSettingsPlan:
    auto_dpi_enabled: bool
    defender_disabled: bool
    max_blocked: bool


@dataclass(slots=True)
class ControlAutoDpiPlan:
    enabled: bool
    message: str
    title: str


@dataclass(slots=True)
class ControlStopButtonPlan:
    text: str


@dataclass(slots=True)
class ControlRuntimeState:
    phase: str
    last_error: str


@dataclass(slots=True)
class ControlStatusPlan:
    phase: str
    title: str
    description: str
    dot_color: str
    pulsing: bool
    show_start: bool
    show_stop_only: bool
    show_stop_and_exit: bool


@dataclass(slots=True)
class ControlStrategyDisplayPlan:
    title: str
    description: str
    tooltip: str


@dataclass(slots=True)
class ControlConfirmationDialogPlan:
    title: str
    content: str
    revert_checked: bool


@dataclass(slots=True)
class ControlToggleActionStartPlan:
    blocked: bool
    blocked_title: str
    blocked_content: str
    blocked_revert_checked: bool | None
    confirmations: tuple[ControlConfirmationDialogPlan, ...]
    start_status: str


@dataclass(slots=True)
class ControlActionResultPlan:
    level: str
    title: str
    content: str
    revert_checked: bool | None
    final_status: str


class ControlPageController:
    @staticmethod
    def load_program_settings() -> ControlProgramSettingsPlan:
        auto_dpi_enabled = False
        defender_disabled = False
        max_blocked = False

        try:
            from config import get_dpi_autostart

            auto_dpi_enabled = bool(get_dpi_autostart())
        except Exception:
            pass

        try:
            from altmenu.defender_manager import WindowsDefenderManager

            defender_disabled = bool(WindowsDefenderManager().is_defender_disabled())
        except Exception:
            pass

        try:
            from altmenu.max_blocker import is_max_blocked

            max_blocked = bool(is_max_blocked())
        except Exception:
            pass

        return ControlProgramSettingsPlan(
            auto_dpi_enabled=auto_dpi_enabled,
            defender_disabled=defender_disabled,
            max_blocked=max_blocked,
        )

    @staticmethod
    def save_auto_dpi(enabled: bool) -> ControlAutoDpiPlan:
        try:
            from config import set_dpi_autostart

            set_dpi_autostart(bool(enabled))
        except Exception:
            pass

        message = (
            "DPI будет включаться автоматически при старте программы"
            if enabled
            else "Автозагрузка DPI отключена"
        )
        return ControlAutoDpiPlan(
            enabled=bool(enabled),
            message=message,
            title="Автозагрузка DPI",
        )

    @staticmethod
    def reset_startup_cache() -> tuple[bool, str]:
        try:
            from startup.check_cache import startup_cache
            from log import log

            startup_cache.invalidate_cache()
            log("Кэш проверок запуска очищен пользователем", "INFO")
            return True, "Кэш проверок запуска очищен"
        except Exception as e:
            try:
                from log import log

                log(f"Ошибка очистки кэша: {e}", "❌ ERROR")
            except Exception:
                pass
            return False, str(e)

    @staticmethod
    def build_stop_button_plan(*, language: str) -> ControlStopButtonPlan:
        try:
            from strategy_menu import get_strategy_launch_method
            from config import get_winws_exe_for_method
            from ui.text_catalog import tr as tr_catalog

            method = get_strategy_launch_method()
            exe_name = os.path.basename(get_winws_exe_for_method(method)) or "winws.exe"
            template = tr_catalog(
                "page.control.button.stop_only_template",
                language=language,
                default="Остановить только {exe_name}",
            )
            return ControlStopButtonPlan(text=template.format(exe_name=exe_name))
        except Exception:
            from ui.text_catalog import tr as tr_catalog

            return ControlStopButtonPlan(
                text=tr_catalog(
                    "page.control.button.stop_only_winws",
                    language=language,
                    default="Остановить только winws.exe",
                )
            )

    @staticmethod
    def resolve_runtime_state(*, snapshot_state=None, last_known_dpi_running: bool = False) -> ControlRuntimeState:
        if snapshot_state is not None:
            try:
                phase = str(snapshot_state.dpi_phase or "").strip().lower() or ("running" if snapshot_state.dpi_running else "stopped")
                return ControlRuntimeState(
                    phase=phase,
                    last_error=str(snapshot_state.dpi_last_error or "").strip(),
                )
            except Exception:
                pass

        return ControlRuntimeState(
            phase="running" if bool(last_known_dpi_running) else "stopped",
            last_error="",
        )

    @staticmethod
    def short_dpi_error(last_error: str) -> str:
        text = str(last_error or "").strip()
        if not text:
            return ""
        first_line = text.splitlines()[0].strip()
        if len(first_line) <= 160:
            return first_line
        return first_line[:157] + "..."

    @staticmethod
    def build_strategy_display_plan(*, name: str, language: str, window=None) -> ControlStrategyDisplayPlan:
        from ui.text_catalog import tr as tr_catalog

        not_selected = tr_catalog(
            "page.control.strategy.not_selected",
            language=language,
            default="Не выбрана",
        )
        active_description = tr_catalog(
            "page.control.strategy.active",
            language=language,
            default="Активная стратегия обхода",
        )
        select_hint = tr_catalog(
            "page.control.strategy.select_hint",
            language=language,
            default="Выберите стратегию в разделе «Стратегии»",
        )

        display_name = str(name or "").strip()
        tooltip = ""

        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
            if method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                from ui.main_window_display import get_direct_strategy_summary

                summary = get_direct_strategy_summary(window, max_items=2)
                display_name = summary or not_selected

                if method in ("direct_zapret2", "direct_zapret1"):
                    from core.presets.direct_facade import DirectPresetFacade

                    selections = DirectPresetFacade.from_launch_method(method).get_strategy_selections() or {}
                else:
                    from preset_orchestra_zapret2 import PresetManager

                    selections = PresetManager().get_strategy_selections() or {}

                active_count = sum(
                    1 for strategy_id in selections.values() if (strategy_id or "none") != "none"
                )
                if active_count > 0 and summary:
                    tooltip = summary.replace(" • ", "\n").replace(" +", "\n+")
        except Exception:
            pass

        if display_name and display_name not in ("Автостарт DPI отключен", not_selected):
            return ControlStrategyDisplayPlan(
                title=display_name,
                description=active_description,
                tooltip=tooltip,
            )

        return ControlStrategyDisplayPlan(
            title=not_selected,
            description=select_hint,
            tooltip="",
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
                title=tr_catalog("page.control.status.running", language=language, default="Zapret работает"),
                description=tr_catalog("page.control.status.bypass_active", language=language, default="Обход блокировок активен"),
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
                description="Ждём завершения стартовой инициализации перед запуском",
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
            title=tr_catalog("page.control.status.stopped", language=language, default="Zapret остановлен"),
            description=tr_catalog("page.control.status.press_start", language=language, default="Нажмите «Запустить» для активации"),
            dot_color="#ff6b6b",
            pulsing=False,
            show_start=True,
            show_stop_only=False,
            show_stop_and_exit=False,
        )

    @staticmethod
    def is_user_admin() -> bool:
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

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
                            "page.control.dialog.defender_disable.title",
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
                        "page.control.dialog.defender_enable.title",
                        language=language,
                        default="Включение Windows Defender",
                    ),
                    content=(
                        "Включить Windows Defender обратно?\n\n"
                        "Это восстановит защиту вашего компьютера."
                    ),
                    revert_checked=True,
                ),
            ),
            start_status="Включение Windows Defender...",
        )

    @staticmethod
    def run_defender_toggle(*, disable: bool, status_callback: Callable[[str], None] | None = None) -> ControlActionResultPlan:
        try:
            from altmenu.defender_manager import WindowsDefenderManager, set_defender_disabled

            manager = WindowsDefenderManager(status_callback=status_callback)

            if disable:
                success, count = manager.disable_defender()
                if success:
                    set_defender_disabled(True)
                    return ControlActionResultPlan(
                        level="success",
                        title="Windows Defender отключен",
                        content=(
                            "Windows Defender успешно отключен. "
                            f"Применено {count} настроек. Может потребоваться перезагрузка."
                        ),
                        revert_checked=None,
                        final_status="Готово",
                    )
                return ControlActionResultPlan(
                    level="error",
                    title="Ошибка",
                    content=(
                        "Не удалось отключить Windows Defender. "
                        "Возможно, некоторые настройки заблокированы системой."
                    ),
                    revert_checked=False,
                    final_status="Готово",
                )

            success, _count = manager.enable_defender()
            if success:
                set_defender_disabled(False)
                return ControlActionResultPlan(
                    level="success",
                    title="Windows Defender включен",
                    content=(
                        "Windows Defender успешно включен. "
                        "Защита вашего компьютера восстановлена."
                    ),
                    revert_checked=None,
                    final_status="Готово",
                )
            return ControlActionResultPlan(
                level="warning",
                title="Частичный успех",
                content=(
                    "Windows Defender включен частично. "
                    "Некоторые настройки могут потребовать ручного исправления."
                ),
                revert_checked=None,
                final_status="Готово",
            )
        except Exception as e:
            return ControlActionResultPlan(
                level="error",
                title="Ошибка",
                content=f"Произошла ошибка при изменении настроек Windows Defender: {e}",
                revert_checked=None,
                final_status="",
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
                            "page.control.dialog.max_block_enable.title",
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
                        "page.control.dialog.max_block_disable.title",
                        language=language,
                        default="Отключение блокировки MAX",
                    ),
                    content=(
                        "Отключить блокировку программы MAX?\n\n"
                        "Это удалит все созданные блокировки и правила."
                    ),
                    revert_checked=True,
                ),
            ),
            start_status="",
        )

    @staticmethod
    def run_max_block_toggle(*, enable: bool, status_callback: Callable[[str], None] | None = None) -> ControlActionResultPlan:
        try:
            from altmenu.max_blocker import MaxBlockerManager

            manager = MaxBlockerManager(status_callback=status_callback)

            if enable:
                success, message = manager.enable_blocking()
                if success:
                    return ControlActionResultPlan(
                        level="success",
                        title="Блокировка включена",
                        content=message,
                        revert_checked=None,
                        final_status="Готово",
                    )
                return ControlActionResultPlan(
                    level="warning",
                    title="Ошибка",
                    content=f"Не удалось полностью включить блокировку: {message}",
                    revert_checked=False,
                    final_status="Готово",
                )

            success, message = manager.disable_blocking()
            if success:
                return ControlActionResultPlan(
                    level="success",
                    title="Блокировка отключена",
                    content=message,
                    revert_checked=None,
                    final_status="Готово",
                )
            return ControlActionResultPlan(
                level="warning",
                title="Ошибка",
                content=f"Не удалось полностью отключить блокировку: {message}",
                revert_checked=None,
                final_status="Готово",
            )
        except Exception as e:
            return ControlActionResultPlan(
                level="error",
                title="Ошибка",
                content=f"Ошибка при переключении блокировки MAX: {e}",
                revert_checked=None,
                final_status="",
            )
