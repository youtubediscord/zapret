# winws_runtime/runners/spawn_failure.py
"""Unified classification of winws/winws2 spawn failures.

Single source of truth for "what kind of failure is this and is a retry
worth it". Runners and their retry orchestration consult this module instead
of keeping their own scattered exit-code/stderr predicates. Classification is
pure with respect to retry budget: retry counters stay in the callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from winws_runtime.health.windivert_diagnostics import (
    _ERROR_DRIVER_BLOCKED,
    _ERROR_DRIVER_FAILED_PRIOR_UNLOAD,
    _ERROR_INVALID_IMAGE_HASH,
    _ERROR_SERVICE_DEPENDENCY_FAIL,
    _ERROR_SERVICE_DISABLED,
    _ERROR_SERVICE_DOES_NOT_EXIST,
)


# STATUS_DLL_INIT_FAILED: Windows killed the process before main() because one
# of its DLLs failed to initialize. For winws this is a transient race right
# after another winws/WinDivert instance exited, not a persistent breakage.
STATUS_DLL_INIT_FAILED = 0xC0000142

# ERROR_INVALID_BLOCK — stale WinDivert state from a previous instance.
_WINDIVERT_CONFLICT_EXIT_CODES = frozenset({9})

_WINDIVERT_CONFLICT_SIGNATURES = (
    "guid or luid already exists",
    "object with that guid",
    "already running with the same filter",
)

# Errors that require user action (Secure Boot, AV, disabled service, ...)
# and must not be retried. Codes 577, 1058, 1060, 1068, 1275, 654.
_WINDIVERT_SYSTEM_EXIT_CODES = frozenset({
    _ERROR_INVALID_IMAGE_HASH,
    _ERROR_SERVICE_DISABLED,
    _ERROR_SERVICE_DOES_NOT_EXIST,
    _ERROR_SERVICE_DEPENDENCY_FAIL,
    _ERROR_DRIVER_BLOCKED,
    _ERROR_DRIVER_FAILED_PRIOR_UNLOAD,
})

_WINDIVERT_SYSTEM_SIGNATURES = (
    "the service cannot be started",
    "service is disabled",
    "invalid image hash",
    "driver blocked",
    "disable secure boot",
    "driver failed prior unload",
)

# diagnose_winws_exit() causes that mark a 1058 as a real system problem
# rather than a residual stop/start race.
_HARD_1058_CAUSE_MARKERS = (
    "base filtering engine",
    "служба windivert отключена",
    "отсутствуют файлы windivert",
    "secure boot",
    "подпись драйвера",
    "политика безопасности",
)


class SpawnFailureKind(Enum):
    TRANSIENT_DLL_INIT = "transient_dll_init"
    WINDIVERT_CONFLICT = "windivert_conflict"
    WINDIVERT_SERVICE_TRANSIENT = "windivert_service_transient"
    WINDIVERT_SYSTEM = "windivert_system"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpawnFailureClassification:
    kind: SpawnFailureKind
    retryable: bool
    needs_aggressive_cleanup: bool
    user_message: Optional[str]
    # Raw predicate flags. A failure can match several categories at once
    # (e.g. 1058 is a system code AND may be a transient service race);
    # retry orchestration checks these in its own historical order.
    is_transient_dll_init: bool
    is_conflict: bool
    is_system: bool
    is_service_transient: bool


def _normalize_exit_code(exit_code) -> int:
    try:
        return int(exit_code)
    except Exception:
        return -1


def _is_soft_windivert_1058(exit_code: int, stderr: str) -> bool:
    """True when a 1058-family failure looks like a residual stop/start race.

    WinDivert code 1058/34 sometimes surfaces right after stop/start even
    though BFE, the service, and the driver are all healthy. Those cases are
    worth one retry through a heavier cleanup. When diagnosis points at a real
    system cause (BFE off, driver files missing, service disabled, Secure
    Boot / driver signature / security policy) a retry cannot help.
    """
    from winws_runtime.health.process_health_check import diagnose_winws_exit

    try:
        diag = diagnose_winws_exit(exit_code, stderr)
    except Exception:
        diag = None

    win32_error = int(getattr(diag, "win32_error", exit_code) or exit_code)
    if win32_error != _ERROR_SERVICE_DISABLED:
        return False

    cause = str(getattr(diag, "cause", "") or "").strip().lower()
    return not any(marker in cause for marker in _HARD_1058_CAUSE_MARKERS)


def classify_spawn_failure(exit_code, stderr: str = "") -> SpawnFailureClassification:
    code = _normalize_exit_code(exit_code)
    stderr_text = str(stderr or "")
    stderr_lower = stderr_text.lower()

    is_transient_dll_init = code == STATUS_DLL_INIT_FAILED
    is_conflict = code in _WINDIVERT_CONFLICT_EXIT_CODES or any(
        sig in stderr_lower for sig in _WINDIVERT_CONFLICT_SIGNATURES
    )
    is_system = code in _WINDIVERT_SYSTEM_EXIT_CODES or any(
        sig in stderr_lower for sig in _WINDIVERT_SYSTEM_SIGNATURES
    )
    is_service_transient = _is_soft_windivert_1058(code, stderr_text)

    if is_transient_dll_init:
        kind = SpawnFailureKind.TRANSIENT_DLL_INIT
    elif is_service_transient:
        kind = SpawnFailureKind.WINDIVERT_SERVICE_TRANSIENT
    elif is_system:
        kind = SpawnFailureKind.WINDIVERT_SYSTEM
    elif is_conflict:
        kind = SpawnFailureKind.WINDIVERT_CONFLICT
    else:
        kind = SpawnFailureKind.UNKNOWN

    retryable = kind in (
        SpawnFailureKind.TRANSIENT_DLL_INIT,
        SpawnFailureKind.WINDIVERT_SERVICE_TRANSIENT,
        SpawnFailureKind.WINDIVERT_CONFLICT,
    )

    return SpawnFailureClassification(
        kind=kind,
        retryable=retryable,
        needs_aggressive_cleanup=retryable,
        user_message=None,
        is_transient_dll_init=is_transient_dll_init,
        is_conflict=is_conflict,
        is_system=is_system,
        is_service_transient=is_service_transient,
    )
