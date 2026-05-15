from __future__ import annotations

from dataclasses import dataclass

from settings.mode import EXE_NAME_WINWS1


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


class ControlPresetNameRuntime:
    def __init__(self) -> None:
        self.preset_name_dirty = True

    def mark_dirty(self) -> None:
        self.preset_name_dirty = True

    def mark_applied(self) -> None:
        self.preset_name_dirty = False

    def should_refresh(self) -> bool:
        return bool(self.preset_name_dirty)

def create_preset_name_runtime() -> ControlPresetNameRuntime:
    return ControlPresetNameRuntime()

def build_stop_button_plan(*, language: str) -> ControlStopButtonPlan:
    try:
        from settings.mode import exe_name_for_launch_method
        from ui.workflows.common import get_current_launch_method

        from app.text_catalog import tr as tr_catalog

        method = get_current_launch_method(default="")
        exe_name = exe_name_for_launch_method(method)
        template = tr_catalog(
            "page.control.button.stop_only_template",
            language=language,
            default="Остановить только {exe_name}",
        )
        return ControlStopButtonPlan(text=template.format(exe_name=exe_name))
    except Exception:
        from app.text_catalog import tr as tr_catalog

        return ControlStopButtonPlan(
            text=tr_catalog(
                "page.control.button.stop_only_winws",
                language=language,
                default=f"Остановить только {EXE_NAME_WINWS1}",
            )
        )

def resolve_runtime_state(*, snapshot_state=None, last_known_dpi_running: bool = False) -> ControlRuntimeState:
    if snapshot_state is not None:
        try:
            phase = str(snapshot_state.launch_phase or "").strip().lower() or (
                "running" if snapshot_state.launch_running else "stopped"
            )
            return ControlRuntimeState(
                phase=phase,
                last_error=str(snapshot_state.launch_last_error or "").strip(),
            )
        except Exception:
            pass

    return ControlRuntimeState(
        phase="running" if bool(last_known_dpi_running) else "stopped",
        last_error="",
    )

def short_dpi_error(last_error: str) -> str:
    text = str(last_error or "").strip()
    if not text:
        return ""
    first_line = text.splitlines()[0].strip()
    if len(first_line) <= 160:
        return first_line
    return first_line[:157] + "..."

def build_status_plan(*, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
    from app.text_catalog import tr as tr_catalog

    phase = str(state or "").strip().lower()
    if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
        phase = "running" if bool(state) else "stopped"

    if phase == "running":
        return ControlStatusPlan(
            phase=phase,
            title=tr_catalog("page.control.status.running", language=language, default="Zapret работает"),
            description=tr_catalog("page.control.status.bypass_active", language=language, default="Обход блокировок активен"),
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
            description=short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
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

def build_defender_toggle_start_plan(*, disable: bool, language: str, is_admin: bool) -> ControlToggleActionStartPlan:
    from app.text_catalog import tr as tr_catalog

    if not is_admin:
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

def build_max_block_toggle_start_plan(*, enable: bool, language: str) -> ControlToggleActionStartPlan:
    from app.text_catalog import tr as tr_catalog

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
