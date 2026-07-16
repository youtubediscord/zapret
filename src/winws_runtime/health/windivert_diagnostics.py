# winws_runtime/health/windivert_diagnostics.py
"""Единый центр диагностики WinDivert.

Здесь живут:
- канонические определения Win32-кодов ошибок WinDivert (единственная точка
  определения числовых литералов, остальные модули импортируют имена);
- декларативная таблица код → (короткая подсказка ru, причина, решение,
  auto_fix action, transient-флаг);
- ``describe_windivert_error`` — пользовательский текст с номером кода;
- pre-spawn readiness gate (перенесён из runner_base) с one-shot
  recovery-циклом и подсказкой о конфликте WinDivert.

Модуль намеренно не импортирует ``winws_runtime.runtime.system_ops`` на
уровне модуля: system_ops сам импортирует отсюда канонический код 1072,
поэтому все обращения к runtime-функциям выполняются лениво.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from log.log import log


# --- Канонические Win32-коды ошибок WinDivert (единственная точка определения) ---
_ERROR_ACCESS_DENIED = 5
_ERROR_NOT_ENOUGH_MEMORY = 8
_ERROR_GEN_FAILURE = 31
_ERROR_INVALID_PARAMETER = 87
_ERROR_BAD_PATHNAME = 161
_ERROR_INVALID_IMAGE_HASH = 577
_ERROR_DRIVER_FAILED_PRIOR_UNLOAD = 654
_ERROR_SERVICE_DISABLED = 1058
_ERROR_SERVICE_DOES_NOT_EXIST = 1060
_ERROR_PROCESS_ABORTED = 1067
_ERROR_SERVICE_DEPENDENCY_FAIL = 1068
_ERROR_SERVICE_MARKED_FOR_DELETE = 1072
_ERROR_DRIVER_BLOCKED = 1275
# EPT_S_NOT_REGISTERED: плавающая гонка SCM сразу после stop/cleanup.
_ERROR_EPT_S_NOT_REGISTERED = 1753

# Имена служб драйвера WinDivert/Monkey (используются диагностикой и auto-fix).
_WINDIVERT_DRIVER_SERVICE_NAMES = ("WinDivert", "windivert", "WinDivert14", "WinDivert64", "Monkey")

# Параметры pre-spawn readiness probe (перенесены из runner_base).
_WINDIVERT_PRESPAWN_WAIT_SECONDS = 3.0
_WINDIVERT_READINESS_POLL_INTERVAL_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class WinDivertErrorRecord:
    """Декларативное описание одного Win32-кода ошибки WinDivert."""

    code: int
    short_hint_ru: str          # короткая подсказка для pre-spawn readiness текста
    cause: str                  # базовая причина (для diagnose_winws_exit fallback)
    solution: str               # базовое решение
    auto_fix_action: Optional[str] = None  # безопасное авто-действие или None
    transient: bool = False     # входит ли код в transient-набор readiness recovery


WINDIVERT_ERROR_TABLE: dict[int, WinDivertErrorRecord] = {
    record.code: record
    for record in (
        WinDivertErrorRecord(
            code=_ERROR_ACCESS_DENIED,
            short_hint_ru=(
                "нет доступа к драйверу WinDivert — возможно, блокирует антивирус "
                "или не хватает прав администратора"
            ),
            cause="Отказано в доступе к WinDivert",
            solution="Проверьте антивирус и запустите от имени администратора",
            transient=True,
        ),
        WinDivertErrorRecord(
            code=_ERROR_NOT_ENOUGH_MEMORY,
            short_hint_ru="недостаточно системной памяти для WinDivert",
            cause="Недостаточно системной памяти для WinDivert",
            solution="Закройте лишние программы и перезагрузите компьютер",
        ),
        WinDivertErrorRecord(
            code=_ERROR_GEN_FAILURE,
            short_hint_ru="общая ошибка устройства — проверьте сетевые адаптеры",
            cause="Общая ошибка устройства",
            solution="Перезагрузите компьютер и проверьте сетевые адаптеры",
        ),
        WinDivertErrorRecord(
            code=_ERROR_INVALID_PARAMETER,
            short_hint_ru="неверные параметры фильтра или Lua-скрипта",
            cause="Ошибка в параметрах фильтра или Lua-скрипта",
            solution="Проверьте настройки стратегии — возможно повреждён пресет",
        ),
        WinDivertErrorRecord(
            code=_ERROR_BAD_PATHNAME,
            short_hint_ru="не найден файл драйвера WinDivert",
            cause="Не найден файл драйвера WinDivert",
            solution="Переустановите программу или проверьте антивирус",
        ),
        WinDivertErrorRecord(
            code=_ERROR_INVALID_IMAGE_HASH,
            short_hint_ru=(
                "Windows отклонила подпись драйвера WinDivert "
                "(Secure Boot / политика подписи драйверов)"
            ),
            cause="Подпись драйвера WinDivert не прошла проверку",
            solution="Отключите Secure Boot или включите тестовый режим: bcdedit /set testsigning on",
        ),
        WinDivertErrorRecord(
            code=_ERROR_DRIVER_FAILED_PRIOR_UNLOAD,
            short_hint_ru="старая версия драйвера WinDivert всё ещё загружена в память",
            cause="Старая версия драйвера WinDivert всё ещё загружена в память",
            solution="Перезагрузите компьютер для выгрузки старого драйвера",
        ),
        WinDivertErrorRecord(
            code=_ERROR_SERVICE_DISABLED,
            short_hint_ru="служба WinDivert отключена в системе",
            cause="WinDivert не может запустить службу драйвера",
            solution="Перезагрузите компьютер. Если не помогает — проверьте Secure Boot и антивирус",
            transient=True,
        ),
        WinDivertErrorRecord(
            code=_ERROR_SERVICE_DOES_NOT_EXIST,
            short_hint_ru="драйвер WinDivert не установлен",
            cause="Служба WinDivert не найдена в системе",
            solution="Переустановите программу",
            transient=True,
        ),
        WinDivertErrorRecord(
            code=_ERROR_PROCESS_ABORTED,
            short_hint_ru="драйвер WinDivert аварийно завершился",
            cause="Драйвер WinDivert аварийно завершился при запуске",
            solution="Переустановите программу и перезагрузите компьютер",
        ),
        WinDivertErrorRecord(
            code=_ERROR_SERVICE_DEPENDENCY_FAIL,
            short_hint_ru="не запущена зависимая служба (Base Filtering Engine)",
            cause="Зависимая служба Windows Filtering Platform не запущена",
            solution="Перезагрузите компьютер",
        ),
        WinDivertErrorRecord(
            code=_ERROR_SERVICE_MARKED_FOR_DELETE,
            short_hint_ru=(
                "служба WinDivert помечена на удаление — подождите несколько секунд "
                "или перезагрузите ПК"
            ),
            cause="Служба WinDivert помечена на удаление",
            solution="Подождите несколько секунд и повторите запуск, либо перезагрузите компьютер",
            transient=True,
        ),
        WinDivertErrorRecord(
            code=_ERROR_DRIVER_BLOCKED,
            short_hint_ru="драйвер WinDivert заблокирован системой (Memory Integrity / HVCI)",
            cause="Политика безопасности Windows блокирует загрузку драйвера",
            solution="Проверьте настройки Device Guard / WDAC или отключите Secure Boot",
        ),
        WinDivertErrorRecord(
            code=_ERROR_EPT_S_NOT_REGISTERED,
            # Пустая подсказка: для 1753 сохраняем прежний общий readiness-текст.
            short_hint_ru="",
            cause="Служба WinDivert ещё не зарегистрирована в системе (временная гонка SCM)",
            solution="Подождите пару секунд и повторите запуск",
            transient=True,
        ),
    )
}

# Transient-набор pre-spawn readiness recovery: {5, 1058, 1060, 1753, 1072}.
TRANSIENT_WINDIVERT_READINESS_CODES = frozenset(
    record.code for record in WINDIVERT_ERROR_TABLE.values() if record.transient
)


def describe_windivert_error(code: int, stage: str = "exit", *, probe_stage: str = "") -> str:
    """Пользовательский текст (ru) для Win32-кода ошибки WinDivert.

    Всегда содержит десятичный номер кода.

    Args:
        code: Win32-код ошибки.
        stage: "readiness" — текст для pre-spawn readiness провала,
               "exit" — текст для диагностики кода завершения winws.
        probe_stage: стадия readiness probe (например "network_open") для
                     уточнения общего readiness-текста.
    """
    error_code = int(code)
    record = WINDIVERT_ERROR_TABLE.get(error_code)

    if stage == "readiness":
        if record is not None and record.short_hint_ru:
            return f"WinDivert не готов: {record.short_hint_ru} (код {error_code})"
        stage_text = str(probe_stage or "")
        stage_suffix = f", стадия {stage_text}" if stage_text else ""
        return f"WinDivert ещё не готов к открытию фильтра (код {error_code}{stage_suffix})"

    if record is not None:
        return f"{record.cause} (код {error_code}). {record.solution}"
    return f"Ошибка WinDivert (код {error_code})"


# ---------------------------------------------------------------------------
#  Pre-spawn readiness gate (перенесён из runner_base)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WinDivertReadinessResult:
    """Итог pre-spawn readiness gate WinDivert."""

    ready: bool
    probe: object | None = None          # WinDivertRuntimeProbeResult или None
    error_code: int | None = None
    description: str = ""                # человеко-читаемое описание провала
    conflict_hint: str = ""              # подсказка о найденном конфликте, если есть


def describe_windivert_conflict_hint() -> str:
    """Ищет программу, реально держащую WinDivert, только в ветке ошибки."""
    try:
        from winws_runtime.health.launch_conflicts import build_windivert_conflict_hint

        return str(build_windivert_conflict_hint() or "")
    except Exception:
        return ""


def describe_windivert_readiness_probe_result(probe) -> str:
    """Точное описание провала pre-spawn readiness probe WinDivert."""
    if probe is None or getattr(probe, "error_code", None) is None:
        return "WinDivert ещё не готов к открытию фильтра"

    error_code = int(probe.error_code or 0)
    probe_stage = str(getattr(probe, "stage", "") or "")
    return describe_windivert_error(error_code, "readiness", probe_stage=probe_stage)


def describe_windivert_readiness_failure(probe) -> str:
    """Описание провала readiness probe с подсказкой о конфликте WinDivert."""
    base_message = describe_windivert_readiness_probe_result(probe)
    conflict_hint = describe_windivert_conflict_hint()
    if conflict_hint:
        return f"{base_message}. {conflict_hint}"
    return base_message


def retry_windivert_spawn_readiness_after_recovery(
    probe,
    *,
    aggressive_cleanup: Optional[Callable[[], None]] = None,
    wait_after_cleanup: Optional[Callable[[], None]] = None,
):
    """Один recovery-цикл для pre-spawn readiness.

    Нужен для плавающих случаев, когда stop/cleanup уже завершён, но
    WinDivert ещё не готов открыть NETWORK layer. Не бесконечный retry:
    делаем один контролируемый цикл и возвращаем итоговый probe.
    """
    if probe.ready or int(probe.error_code or 0) not in TRANSIENT_WINDIVERT_READINESS_CODES:
        return probe

    log(
        "WinDivert pre-spawn readiness transient failure, performing one recovery cycle",
        "WARNING",
    )
    try:
        if callable(aggressive_cleanup):
            aggressive_cleanup()
        if callable(wait_after_cleanup):
            wait_after_cleanup()
        from winws_runtime.runtime.system_ops import wait_for_windivert_spawn_ready_runtime

        return wait_for_windivert_spawn_ready_runtime(
            max_wait_seconds=_WINDIVERT_PRESPAWN_WAIT_SECONDS,
            poll_interval=_WINDIVERT_READINESS_POLL_INTERVAL_SECONDS,
        )
    except Exception:
        return probe


def ensure_windivert_ready_before_spawn(
    *,
    max_wait_seconds: float = _WINDIVERT_PRESPAWN_WAIT_SECONDS,
    poll_interval: float = _WINDIVERT_READINESS_POLL_INTERVAL_SECONDS,
    aggressive_cleanup: Optional[Callable[[], None]] = None,
    wait_after_cleanup: Optional[Callable[[], None]] = None,
) -> WinDivertReadinessResult:
    """Проверяет готовность WinDivert прямо перед новым spawn.

    Возвращает объект-результат: флаг готовности, код ошибки,
    человеко-читаемое описание и подсказку о конфликте (если найдена).
    Callbacks очистки передаёт runner: сам цикл recovery остаётся здесь.
    """
    try:
        from winws_runtime.runtime.system_ops import wait_for_windivert_spawn_ready_runtime

        probe = wait_for_windivert_spawn_ready_runtime(
            max_wait_seconds=max_wait_seconds,
            poll_interval=poll_interval,
        )
    except Exception:
        return WinDivertReadinessResult(ready=True)

    if probe.ready:
        return WinDivertReadinessResult(ready=True, probe=probe)

    recovery_probe = retry_windivert_spawn_readiness_after_recovery(
        probe,
        aggressive_cleanup=aggressive_cleanup,
        wait_after_cleanup=wait_after_cleanup,
    )
    if recovery_probe.ready:
        return WinDivertReadinessResult(ready=True, probe=recovery_probe)

    log(
        "WinDivert pre-spawn readiness check failed: "
        f"installed={recovery_probe.installed}, error={recovery_probe.error_code}, "
        f"stage={recovery_probe.stage}",
        "WARNING",
    )
    conflict_hint = describe_windivert_conflict_hint()
    base_message = describe_windivert_readiness_probe_result(recovery_probe)
    description = f"{base_message}. {conflict_hint}" if conflict_hint else base_message
    error_code = int(recovery_probe.error_code) if recovery_probe.error_code is not None else None
    return WinDivertReadinessResult(
        ready=False,
        probe=recovery_probe,
        error_code=error_code,
        description=description,
        conflict_hint=conflict_hint,
    )
