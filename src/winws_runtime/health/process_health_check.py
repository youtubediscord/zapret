# winws_runtime/health/process_health_check.py
"""Фасад health-проверок winws (обратная совместимость импортов).

Реализация распилена по подмодулям:
- ``windivert_diagnostics`` — единая таблица Win32-кодов, describe-функции,
  pre-spawn readiness gate;
- ``winws_exit_diagnosis`` — диагностика кодов завершения winws/winws2;
- ``windivert_auto_fix`` — безопасные auto-fix действия;
- ``startup_error_diagnosis`` — диагностика исключений при запуске;
- ``process_monitor`` — мониторинг здоровья процесса и типовые причины падений;
- ``antivirus_detection`` — обнаружение активного антивируса.

Этот модуль реэкспортирует все прежние публичные имена (и приватные
helper-функции, которые исторически использовались напрямую), чтобы старые
импорты ``winws_runtime.health.process_health_check`` продолжали работать.
"""

from winws_runtime.health.windivert_diagnostics import (  # noqa: F401
    WINDIVERT_ERROR_TABLE,
    WinDivertErrorRecord,
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
    _ERROR_SERVICE_MARKED_FOR_DELETE,
    _WINDIVERT_DRIVER_SERVICE_NAMES,
    describe_windivert_error,
)
from winws_runtime.health.antivirus_detection import (  # noqa: F401
    _ANTIVIRUS_PROCESS_MARKERS,
    _ANTIVIRUS_PRODUCT_MARKERS,
    _detect_active_antivirus,
    _find_known_antivirus_name,
    _is_windows_defender_active,
)
from winws_runtime.health.winws_exit_diagnosis import (  # noqa: F401
    WinDivertDiagnosis,
    _EXIT_CODE_HANDLERS,
    _STDERR_TO_WIN32,
    _check_bfe_service,
    _check_network_adapters,
    _check_secure_boot,
    _check_windivert_driver_disabled,
    _check_windivert_files,
    _extract_relevant_error_line,
    _find_disabled_windivert_driver_service,
    _probe_service_disabled_cause,
    diagnose_winws_exit,
    format_winws_exit_diagnosis,
)
from winws_runtime.health.windivert_auto_fix import (  # noqa: F401
    _fix_cleanup_driver,
    _fix_enable_adapters,
    _fix_enable_bfe,
    _fix_enable_driver,
    execute_windivert_auto_fix,
)
from winws_runtime.health.startup_error_diagnosis import (  # noqa: F401
    _check_antivirus_blocking,
    _check_file_locked,
    _check_winws_already_running,
    diagnose_startup_error,
)
from winws_runtime.health.process_monitor import (  # noqa: F401
    _check_process_running,
    _find_process_pid_by_name_winapi,
    _get_crash_details,
    analyze_strategy_complexity,
    check_common_crash_causes,
    check_process_health,
    get_last_crash_info,
    validate_command_line_length,
)

__all__ = [
    "WINDIVERT_ERROR_TABLE",
    "WinDivertErrorRecord",
    "WinDivertDiagnosis",
    "analyze_strategy_complexity",
    "check_common_crash_causes",
    "check_process_health",
    "describe_windivert_error",
    "diagnose_startup_error",
    "diagnose_winws_exit",
    "format_winws_exit_diagnosis",
    "execute_windivert_auto_fix",
    "get_last_crash_info",
    "validate_command_line_length",
]
