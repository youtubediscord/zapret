# winws_runtime/health/winws_exit_diagnosis.py
"""Диагностика кодов завершения winws/winws2 (WinDivert exit-code diagnostics).

Handler-функции берут базовые тексты причин/решений из единой таблицы
``winws_runtime.health.windivert_diagnostics.WINDIVERT_ERROR_TABLE`` и
дополняют их динамическими probe-уточнениями (BFE, Secure Boot, файлы
драйвера, антивирус, сетевые адаптеры).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from winws_runtime.health.antivirus_detection import (  # noqa: F401 (реэкспорт для фасада)
    _detect_active_antivirus,
    _find_known_antivirus_name,
    _is_windows_defender_active,
)
from winws_runtime.health.windivert_diagnostics import (
    WINDIVERT_ERROR_TABLE,
    _ERROR_ACCESS_DENIED,
    _ERROR_BAD_PATHNAME,
    _ERROR_DRIVER_BLOCKED,
    _ERROR_DRIVER_FAILED_PRIOR_UNLOAD,
    _ERROR_GEN_FAILURE,
    _ERROR_INVALID_IMAGE_HASH,
    _ERROR_INVALID_PARAMETER,
    _ERROR_NOT_ENOUGH_MEMORY,
    _ERROR_PROCESS_ABORTED,
    _ERROR_SERVICE_DEPENDENCY_FAIL,
    _ERROR_SERVICE_DISABLED,
    _ERROR_SERVICE_DOES_NOT_EXIST,
    _WINDIVERT_DRIVER_SERVICE_NAMES,
)


@dataclass
class WinDivertDiagnosis:
    """Structured result of WinDivert error diagnosis."""
    cause: str                        # Human-readable cause
    solution: str                     # What the user should do
    auto_fix: Optional[str] = None   # Action ID: "enable_adapters", "enable_bfe", "enable_driver", None
    severity: str = "critical"        # "critical" | "warning"
    exit_code: int = 0                # Original exit code
    win32_error: Optional[int] = None # Mapped Win32 error (may differ from exit_code)


def _diagnosis_from_table(code: int, *, severity: str = "critical") -> WinDivertDiagnosis:
    """Базовый диагноз из единой таблицы кодов (без динамических уточнений)."""
    record = WINDIVERT_ERROR_TABLE[code]
    return WinDivertDiagnosis(
        cause=record.cause,
        solution=record.solution,
        auto_fix=record.auto_fix_action,
        severity=severity,
    )


# stderr patterns → Win32 error mapping (for when exit code is truncated)
_STDERR_TO_WIN32: List[Tuple[str, int]] = [
    ("the service cannot be started", _ERROR_SERVICE_DISABLED),
    ("service is disabled", _ERROR_SERVICE_DISABLED),
    ("no enabled devices", _ERROR_SERVICE_DISABLED),
    ("access is denied", _ERROR_ACCESS_DENIED),
    ("access denied", _ERROR_ACCESS_DENIED),
    ("hash for file is not valid", _ERROR_INVALID_IMAGE_HASH),
    ("invalid image hash", _ERROR_INVALID_IMAGE_HASH),
    ("disable secure boot", _ERROR_INVALID_IMAGE_HASH),
    ("driver blocked", _ERROR_DRIVER_BLOCKED),
    ("blocked from loading", _ERROR_DRIVER_BLOCKED),
    ("driver failed prior unload", _ERROR_DRIVER_FAILED_PRIOR_UNLOAD),
    ("bad pathname", _ERROR_BAD_PATHNAME),
    ("service does not exist", _ERROR_SERVICE_DOES_NOT_EXIST),
    ("dependency service", _ERROR_SERVICE_DEPENDENCY_FAIL),
    ("process terminated unexpectedly", _ERROR_PROCESS_ABORTED),
    ("not enough memory", _ERROR_NOT_ENOUGH_MEMORY),
    ("insufficient resources", _ERROR_NOT_ENOUGH_MEMORY),
    ("parameter is incorrect", _ERROR_INVALID_PARAMETER),
    ("a device attached to the system is not functioning", _ERROR_GEN_FAILURE),
]


def diagnose_winws_exit(exit_code: int, stderr: str = "") -> Optional[WinDivertDiagnosis]:
    """Diagnose winws2 exit code + stderr and return structured result.

    The exit code of winws2 equals the raw Win32 GetLastError() value after
    WinDivertOpen() fails.  However, the exit code may be truncated to 8 bits
    in some scenarios (e.g. 1058 → 34).  Therefore stderr text is parsed first
    as the primary signal, and exit_code is used as fallback.

    Returns None if exit_code is 0 (success) or diagnosis is not applicable.
    """
    if exit_code == 0:
        return None

    stderr_lower = (stderr or "").lower()

    # 1. Resolve the real Win32 error from stderr text (more reliable)
    win32_error = exit_code
    for pattern, code in _STDERR_TO_WIN32:
        if pattern in stderr_lower:
            win32_error = code
            break

    # Winws2 can return the raw Win32 error truncated to one byte.
    # ERROR_SERVICE_DISABLED 1058 becomes process exit code 34, often without
    # stderr in GUI launch mode. Treat that as the same driver-service failure.
    if win32_error == 34 and not stderr_lower.strip():
        win32_error = _ERROR_SERVICE_DISABLED

    # 2. Dispatch to specific handlers
    handler = _EXIT_CODE_HANDLERS.get(win32_error)
    if handler:
        diag = handler(exit_code, stderr)
        diag.exit_code = exit_code
        diag.win32_error = win32_error
        return diag

    # 3. Fallback: generic WinDivert error
    if "windivert" in stderr_lower or "error opening filter" in stderr_lower:
        first_line = _extract_relevant_error_line(stderr)[:200]
        return WinDivertDiagnosis(
            cause=f"Ошибка WinDivert (код {exit_code})",
            solution=first_line or "Перезагрузите компьютер и попробуйте снова",
            severity="critical",
            exit_code=exit_code,
            win32_error=win32_error,
        )

    return None


def _extract_relevant_error_line(stderr: str) -> str:
    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    for line in reversed(lines):
        lower = line.lower()
        if "windivert:" in lower or "error opening filter" in lower:
            return line
    for line in reversed(lines):
        lower = line.lower()
        if "error" in lower or "ошибка" in lower:
            return line
    return lines[0] if lines else ""


# ---------------------------------------------------------------------------
#  Per-error-code handlers
# ---------------------------------------------------------------------------

def _handle_service_disabled(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    """ERROR_SERVICE_DISABLED (1058) — the most common WinDivert error."""
    # Run sub-checks to narrow down the cause
    cause, solution, auto_fix = _probe_service_disabled_cause()
    return WinDivertDiagnosis(
        cause=cause, solution=solution, auto_fix=auto_fix, severity="critical",
    )


def _handle_invalid_image_hash(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    secure_boot = _check_secure_boot()
    if secure_boot:
        return WinDivertDiagnosis(
            cause="Secure Boot блокирует загрузку драйвера WinDivert",
            solution="Отключите Secure Boot в BIOS/UEFI настройках",
            severity="critical",
        )
    return _diagnosis_from_table(_ERROR_INVALID_IMAGE_HASH)


def _handle_access_denied(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return WinDivertDiagnosis(
                cause="Программа запущена без прав администратора",
                solution="Запустите программу от имени администратора",
                severity="critical",
            )
    except Exception:
        pass
    try:
        from winws_runtime.health.launch_conflicts import build_launch_conflict_advice

        conflict_advice = build_launch_conflict_advice()
        if conflict_advice is not None:
            cause, solution = conflict_advice
            return WinDivertDiagnosis(
                cause=cause,
                solution=solution,
                severity="critical",
            )
    except Exception:
        pass
    return _diagnosis_from_table(_ERROR_ACCESS_DENIED)


def _handle_driver_blocked(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return _diagnosis_from_table(_ERROR_DRIVER_BLOCKED)


def _handle_driver_prior_unload(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return _diagnosis_from_table(_ERROR_DRIVER_FAILED_PRIOR_UNLOAD)


def _handle_service_not_exist(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    # Check if WinDivert files exist
    missing = _check_windivert_files()
    if missing:
        return WinDivertDiagnosis(
            cause=f"Отсутствуют файлы WinDivert: {', '.join(missing)}",
            solution="Переустановите программу или восстановите файлы из архива",
            severity="critical",
        )
    return _diagnosis_from_table(_ERROR_SERVICE_DOES_NOT_EXIST)


def _handle_dependency_fail(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    bfe_ok = _check_bfe_service()
    if not bfe_ok:
        return WinDivertDiagnosis(
            cause="Служба Base Filtering Engine (BFE) не запущена",
            solution="Включите BFE: sc config BFE start= auto && net start BFE",
            auto_fix="enable_bfe",
            severity="critical",
        )
    return _diagnosis_from_table(_ERROR_SERVICE_DEPENDENCY_FAIL)


def _handle_not_enough_memory(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return _diagnosis_from_table(_ERROR_NOT_ENOUGH_MEMORY, severity="warning")


def _handle_gen_failure(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    adapters_ok = _check_network_adapters()
    if not adapters_ok:
        return WinDivertDiagnosis(
            cause="Все сетевые адаптеры отключены",
            solution="Включите хотя бы один сетевой адаптер",
            auto_fix="enable_adapters",
            severity="critical",
        )
    return _diagnosis_from_table(_ERROR_GEN_FAILURE)


def _handle_invalid_parameter(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    import re
    stderr_lower = (stderr or "").lower()

    if "incompatible nfqws2_compat_ver" in stderr_lower:
        return WinDivertDiagnosis(
            cause="winws2.exe и Lua-скрипты от разных версий",
            solution="Обновите папку lua вместе с winws2.exe или переустановите программу",
            severity="critical",
        )

    if "windivert" in stderr_lower and "error opening filter" in stderr_lower:
        if "the service cannot be started" in stderr_lower or "service is disabled" in stderr_lower:
            return _handle_service_disabled(exit_code, stderr)
        return WinDivertDiagnosis(
            cause="WinDivert не смог открыть фильтр",
            solution=_extract_relevant_error_line(stderr) or "Проверьте состояние драйвера WinDivert",
            severity="critical",
        )

    # Lua desync function not found — lua-init auto-fix didn't help,
    # meaning the .lua file itself is missing from disk.
    m = re.search(r"desync function '([^']+)' does not exist", stderr or "")
    if m:
        func_name = m.group(1)
        return WinDivertDiagnosis(
            cause=f"Lua-функция '{func_name}' не найдена — файл .lua отсутствует на диске",
            solution="Переустановите программу — файлы в папке lua/ повреждены или удалены",
            severity="critical",
        )

    # Lua script syntax/runtime error
    if "lua" in stderr_lower and ("error" in stderr_lower or "syntax" in stderr_lower):
        return WinDivertDiagnosis(
            cause="Ошибка в Lua-скрипте",
            solution="Переустановите программу или проверьте файлы в папке lua/",
            severity="critical",
        )

    return _diagnosis_from_table(_ERROR_INVALID_PARAMETER, severity="warning")


def _handle_bad_pathname(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    missing = _check_windivert_files()
    diagnosis = _diagnosis_from_table(_ERROR_BAD_PATHNAME)
    if missing:
        diagnosis.cause += f": {', '.join(missing)}"
    return diagnosis


def _handle_process_aborted(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return _diagnosis_from_table(_ERROR_PROCESS_ABORTED)


# Handler dispatch table
_EXIT_CODE_HANDLERS = {
    _ERROR_SERVICE_DISABLED: _handle_service_disabled,
    _ERROR_INVALID_IMAGE_HASH: _handle_invalid_image_hash,
    _ERROR_ACCESS_DENIED: _handle_access_denied,
    _ERROR_DRIVER_BLOCKED: _handle_driver_blocked,
    _ERROR_DRIVER_FAILED_PRIOR_UNLOAD: _handle_driver_prior_unload,
    _ERROR_SERVICE_DOES_NOT_EXIST: _handle_service_not_exist,
    _ERROR_SERVICE_DEPENDENCY_FAIL: _handle_dependency_fail,
    _ERROR_NOT_ENOUGH_MEMORY: _handle_not_enough_memory,
    _ERROR_GEN_FAILURE: _handle_gen_failure,
    _ERROR_INVALID_PARAMETER: _handle_invalid_parameter,
    _ERROR_BAD_PATHNAME: _handle_bad_pathname,
    _ERROR_PROCESS_ABORTED: _handle_process_aborted,
}


# ---------------------------------------------------------------------------
#  System probe helpers
# ---------------------------------------------------------------------------

def _probe_service_disabled_cause() -> Tuple[str, str, Optional[str]]:
    """Narrow down why 'service cannot be started' (1058).

    Returns (cause, solution, auto_fix_action).
    """
    # Check 1: WinDivert files missing (AV quarantine)
    missing = _check_windivert_files()
    if missing:
        return (
            f"Файлы WinDivert отсутствуют (возможно удалены антивирусом): {', '.join(missing)}",
            "Добавьте папку программы в исключения антивируса и переустановите",
            None,
        )

    # Check 2: BFE service
    if not _check_bfe_service():
        return (
            "Служба Base Filtering Engine (BFE) отключена — WinDivert зависит от неё",
            "Включите BFE: sc config BFE start= auto && net start BFE",
            "enable_bfe",
        )

    # Check 3: WinDivert/Monkey service explicitly disabled
    disabled_driver = _find_disabled_windivert_driver_service()
    if disabled_driver:
        return (
            f"Служба драйвера WinDivert ({disabled_driver}) отключена в системе",
            "Выполните аварийную очистку драйвера и повторите запуск",
            "cleanup_driver",
        )

    # Check 4: Driver installed but not yet ready after cleanup/restart.
    try:
        from winws_runtime.runtime.system_ops import probe_windivert_state_runtime

        probe = probe_windivert_state_runtime()
        probe_code_suffix = (
            f" (код {int(probe.error_code)})" if probe.error_code is not None else ""
        )
        if probe.installed and not probe.ready:
            return (
                f"WinDivert ещё не готов после предыдущего запуска или очистки{probe_code_suffix}",
                "Подождите пару секунд и попробуйте снова. Если повторяется — перезапустите программу или ПК",
                None,
            )
        if not probe.installed and not probe.ready:
            return (
                f"WinDivert ещё не установился или не готов к открытию фильтра{probe_code_suffix}",
                "Подождите пару секунд и попробуйте снова. Если повторяется — перезапустите программу или проверьте файлы WinDivert",
                None,
            )
    except Exception:
        pass

    # Check 5: Kaspersky after a real WinDivert start failure.
    try:
        from winws_runtime.health.launch_conflicts import build_launch_conflict_advice

        conflict_advice = build_launch_conflict_advice()
        if conflict_advice is not None:
            cause, solution = conflict_advice
            return cause, solution, None
    except Exception:
        pass

    # Check 6: Antivirus
    av = _detect_active_antivirus()
    if av:
        return (
            f"Антивирус ({av}) может блокировать загрузку драйвера WinDivert",
            "Добавьте папку программы в исключения антивируса",
            None,
        )

    # Check 7: Network adapters. This check must be late because Win32 1058
    # is a generic service-disabled error and otherwise easily turns into a
    # ложный диагноз про адаптеры.
    if not _check_network_adapters():
        return (
            "Не найден ни один активный сетевой адаптер — WinDivert не к чему привязаться",
            "Включите хотя бы один сетевой адаптер в системе и повторите запуск",
            "enable_adapters",
        )

    # Fallback: базовый текст 1058 из единой таблицы.
    record = WINDIVERT_ERROR_TABLE[_ERROR_SERVICE_DISABLED]
    return (record.cause, record.solution, record.auto_fix_action)


def _check_network_adapters() -> bool:
    """Return True if at least one network adapter is enabled/up."""
    try:
        from dns.public import get_adapters_info_native

        adapters = get_adapters_info_native()
        for adapter in adapters:
            adapter_type = int(adapter.get("type") or 0)
            if adapter_type == 24:  # MIB_IF_TYPE_LOOPBACK
                continue
            if adapter.get("index") or adapter.get("adapter_name") or adapter.get("name"):
                return True
        return False
    except Exception:
        return True  # assume OK on failure


def _check_windivert_files() -> List[str]:
    """Return list of missing critical WinDivert files."""
    import os
    try:
        from config.config import WINDIVERT_FOLDER

    except ImportError:
        return []

    required = ["WinDivert.dll", "WinDivert64.sys"]
    missing = []
    for f in required:
        if not os.path.exists(os.path.join(WINDIVERT_FOLDER, f)):
            missing.append(f)
    return missing


def _check_bfe_service() -> bool:
    """Return True if Base Filtering Engine service is running."""
    try:
        from startup.bfe_util import is_service_running

        return bool(is_service_running("BFE"))
    except Exception:
        return True  # assume OK


def _check_secure_boot() -> bool:
    """Return True if Secure Boot is ENABLED (via registry)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\SecureBoot\State",
        )
        val, _ = winreg.QueryValueEx(key, "UEFISecureBootEnabled")
        winreg.CloseKey(key)
        return val == 1
    except Exception:
        return False  # key doesn't exist = Secure Boot not available


def _find_disabled_windivert_driver_service() -> Optional[str]:
    """Return disabled WinDivert-compatible service name, if present."""
    try:
        import winreg

        for service_name in _WINDIVERT_DRIVER_SERVICE_NAMES:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    fr"SYSTEM\CurrentControlSet\Services\{service_name}",
                    0,
                    winreg.KEY_READ,
                ) as key:
                    start_value, _ = winreg.QueryValueEx(key, "Start")
                    if int(start_value) == 4:
                        return service_name
            except FileNotFoundError:
                continue
        return None
    except Exception:
        return None


def _check_windivert_driver_disabled() -> bool:
    """Return True if any WinDivert-compatible service start type is DISABLED."""
    return _find_disabled_windivert_driver_service() is not None
