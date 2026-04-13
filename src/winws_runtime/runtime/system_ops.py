from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass

from log.log import log


_KNOWN_WINDIVERT_DRIVERS = ("WinDivert", "WinDivert14", "WinDivert64", "Monkey")
_KNOWN_WINDIVERT_SERVICES = ("WinDivert", "WinDivert14", "WinDivert64", "windivert", "Monkey")
_SERVICE_STOPPED = 0x00000001
_SERVICE_STOP_PENDING = 0x00000003
_SERVICE_RUNNING = 0x00000004
_WINDIVERT_LAYER_NETWORK = 0
_WINDIVERT_LAYER_REFLECT = 4
_WINDIVERT_FLAG_SNIFF = 1
_WINDIVERT_FLAG_RECV_ONLY = 4
_WINDIVERT_FLAG_NO_INSTALL = 0x0010


@dataclass(frozen=True, slots=True)
class WinDivertRuntimeProbeResult:
    installed: bool
    ready: bool
    error_code: int | None = None
    stage: str = ""


def get_process_pids_by_name(process_name: str) -> list[int]:
    try:
        from utils.process_killer import get_process_pids

        return list(get_process_pids(process_name) or [])
    except Exception as e:
        log(f"Ошибка получения PID процесса {process_name}: {e}", "DEBUG")
        return []


def get_all_winws_process_pids() -> list[int]:
    return get_process_pids_by_name("winws.exe") + get_process_pids_by_name("winws2.exe")


def has_any_winws_process() -> bool:
    return bool(get_all_winws_process_pids())


def force_kill_all_winws_processes() -> bool:
    try:
        from utils.process_killer import kill_winws_force

        return bool(kill_winws_force())
    except Exception as e:
        log(f"Ошибка force kill winws: {e}", "DEBUG")
        return False


def kill_process_by_pid_runtime(pid: int, *, wait_timeout_ms: int = 3000) -> bool:
    try:
        from utils.process_killer import kill_process_by_pid_winapi

        return bool(kill_process_by_pid_winapi(int(pid), wait_timeout_ms=wait_timeout_ms))
    except Exception as e:
        log(f"Ошибка kill_process_by_pid для PID={pid}: {e}", "DEBUG")
        return False


def stop_all_winws_processes() -> bool:
    try:
        from utils.process_killer import kill_winws_all

        return bool(kill_winws_all())
    except Exception as e:
        log(f"Ошибка остановки всех winws процессов: {e}", "DEBUG")
        return False


def cleanup_windivert_services_runtime() -> bool:
    try:
        from utils.service_manager import cleanup_windivert_services

        return bool(cleanup_windivert_services())
    except Exception as e:
        log(f"Ошибка cleanup_windivert_services: {e}", "DEBUG")
        return False


def get_known_windivert_service_states_runtime() -> dict[str, int | None]:
    try:
        from utils.service_manager import get_service_state

        return {service_name: get_service_state(service_name) for service_name in _KNOWN_WINDIVERT_SERVICES}
    except Exception as e:
        log(f"Ошибка чтения состояний WinDivert service: {e}", "DEBUG")
        return {service_name: None for service_name in _KNOWN_WINDIVERT_SERVICES}


def _iter_windivert_dll_candidates_runtime() -> list[str]:
    candidates: list[str] = []
    try:
        from config.config import MAIN_DIRECTORY, EXE_FOLDER, BIN_FOLDER

        for base in (MAIN_DIRECTORY, EXE_FOLDER, BIN_FOLDER):
            base_path = str(base or "").strip()
            if not base_path:
                continue
            candidates.append(os.path.join(base_path, "WinDivert.dll"))
    except Exception:
        pass

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.normpath(str(candidate or "").strip()))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(candidate)
    return unique


def _load_windivert_dll_runtime():
    if not hasattr(ctypes, "WinDLL"):
        return None

    dll_path = ""
    for candidate in _iter_windivert_dll_candidates_runtime():
        if os.path.exists(candidate):
            dll_path = candidate
            break

    if not dll_path:
        return None

    try:
        return ctypes.WinDLL(dll_path, use_last_error=True)
    except Exception as e:
        log(f"Не удалось загрузить WinDivert.dll для readiness probe: {e}", "DEBUG")
        return None


def _probe_windivert_open_runtime(
    dll,
    *,
    filter_text: bytes,
    layer: int,
    flags: int,
) -> tuple[bool, int | None]:
    try:
        open_fn = dll.WinDivertOpen
        close_fn = dll.WinDivertClose
    except Exception:
        return True, None

    open_fn.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_short, ctypes.c_uint64]
    open_fn.restype = ctypes.c_void_p
    close_fn.argtypes = [ctypes.c_void_p]
    close_fn.restype = ctypes.c_bool

    ctypes.set_last_error(0)
    handle = open_fn(filter_text, layer, 0, flags)
    invalid_handle = ctypes.c_void_p(-1).value
    handle_value = ctypes.c_void_p(handle).value

    if handle_value in (None, invalid_handle):
        return False, int(ctypes.get_last_error() or 0)

    try:
        close_fn(handle)
    except Exception:
        pass
    return True, None


def probe_windivert_state_runtime() -> WinDivertRuntimeProbeResult:
    """Двухступенчатый probe состояния WinDivert.

    1. `NO_INSTALL + REFLECT`:
       проверяем, установлен ли драйвер вообще, без скрытой авто-установки.
    2. Обычный `NETWORK + SNIFF`:
       проверяем, готов ли драйвер реально открыть фильтр для нового запуска.
    """
    dll = _load_windivert_dll_runtime()
    if dll is None:
        return WinDivertRuntimeProbeResult(
            installed=True,
            ready=True,
            error_code=None,
            stage="dll_unavailable",
        )

    installed_ok, installed_error = _probe_windivert_open_runtime(
        dll,
        filter_text=b"true",
        layer=_WINDIVERT_LAYER_REFLECT,
        flags=_WINDIVERT_FLAG_SNIFF | _WINDIVERT_FLAG_RECV_ONLY | _WINDIVERT_FLAG_NO_INSTALL,
    )
    if not installed_ok:
        if int(installed_error or 0) == 1060:
            return WinDivertRuntimeProbeResult(
                installed=False,
                ready=False,
                error_code=1060,
                stage="reflect_no_install",
            )
        return WinDivertRuntimeProbeResult(
            installed=True,
            ready=False,
            error_code=installed_error,
            stage="reflect_no_install",
        )

    ready_ok, ready_error = _probe_windivert_open_runtime(
        dll,
        filter_text=b"true",
        layer=_WINDIVERT_LAYER_NETWORK,
        flags=_WINDIVERT_FLAG_SNIFF,
    )
    return WinDivertRuntimeProbeResult(
        installed=True,
        ready=bool(ready_ok),
        error_code=None if ready_ok else ready_error,
        stage="network_open",
    )


def unload_known_windivert_drivers_runtime() -> bool:
    ok = True
    try:
        from utils.service_manager import unload_driver

        for driver in _KNOWN_WINDIVERT_DRIVERS:
            try:
                unload_driver(driver)
            except Exception:
                ok = False
    except Exception as e:
        log(f"Ошибка выгрузки драйверов WinDivert: {e}", "DEBUG")
        return False
    return ok


def stop_and_delete_runtime_services(*, retry_count: int = 3) -> bool:
    ok = True
    try:
        from utils.service_manager import stop_and_delete_service

        for service_name in _KNOWN_WINDIVERT_SERVICES:
            try:
                ok = bool(stop_and_delete_service(service_name, retry_count=retry_count)) and ok
            except Exception:
                ok = False
    except Exception as e:
        log(f"Ошибка stop_and_delete runtime services: {e}", "DEBUG")
        return False
    return ok


def stop_and_delete_named_service(service_name: str, *, retry_count: int = 3) -> bool:
    try:
        from utils.service_manager import stop_and_delete_service

        return bool(stop_and_delete_service(service_name, retry_count=retry_count))
    except Exception as e:
        log(f"Ошибка stop_and_delete_service для {service_name}: {e}", "DEBUG")
        return False


def standard_windivert_cleanup_runtime(*, sleep_seconds: float = 0.8) -> bool:
    """Обычная cleanup-стадия перед новым стартом.

    Здесь нельзя агрессивно удалять WinDivert service из SCM на каждом
    обычном запуске. Для обычного restart/start достаточно:
    - добить старые winws-процессы;
    - попытаться выгрузить драйвер;
    - дать Windows время освободить filter handle.

    Удаление service-объектов оставляем только для аварийной aggressive cleanup.
    """
    log("Cleaning up previous winws processes...", "DEBUG")
    ok = True
    ok = force_kill_all_winws_processes() and ok
    ok = unload_known_windivert_drivers_runtime() and ok
    ok = wait_for_windivert_cleanup_settle_runtime(
        max_wait_seconds=max(float(sleep_seconds), 0.8),
        poll_interval=0.2,
        retry_cleanup=False,
    ) and ok
    return ok


def aggressive_windivert_cleanup_runtime() -> bool:
    log("Performing aggressive WinDivert cleanup via Win API...", "INFO")
    ok = True
    ok = force_kill_all_winws_processes() and ok
    time.sleep(0.3)
    ok = unload_known_windivert_drivers_runtime() and ok
    time.sleep(0.2)
    ok = stop_and_delete_runtime_services(retry_count=3) and ok
    time.sleep(0.3)
    ok = force_kill_all_winws_processes() and ok
    ok = wait_for_windivert_cleanup_settle_runtime(
        max_wait_seconds=5.0,
        poll_interval=0.25,
        retry_cleanup=True,
    ) and ok
    log("Aggressive cleanup completed", "INFO")
    return ok


def wait_for_windivert_cleanup_settle_runtime(
    *,
    max_wait_seconds: float = 4.0,
    poll_interval: float = 0.2,
    retry_cleanup: bool = False,
) -> bool:
    """Ждёт, пока WinDivert cleanup реально стабилизируется.

    Условия готовности:
    - нет процессов winws/winws2;
    - ни одна известная WinDivert-служба не находится в RUNNING/STOP_PENDING;
    - состояние подтверждено несколько раз подряд.
    """
    deadline = time.monotonic() + max(0.0, float(max_wait_seconds))
    interval = max(0.05, float(poll_interval))
    stable_checks = 0

    while time.monotonic() < deadline:
        process_pids = get_all_winws_process_pids()
        service_states = get_known_windivert_service_states_runtime()
        busy_services = {
            name: state
            for name, state in service_states.items()
            if state in (_SERVICE_RUNNING, _SERVICE_STOP_PENDING)
        }
        probe = probe_windivert_state_runtime()

        if not process_pids and not busy_services and probe.ready:
            stable_checks += 1
            if stable_checks >= 2:
                return True
        else:
            stable_checks = 0
            if retry_cleanup:
                if process_pids:
                    force_kill_all_winws_processes()
                if busy_services:
                    stop_and_delete_runtime_services(retry_count=1)
                unload_known_windivert_drivers_runtime()

        time.sleep(interval)

    process_pids = get_all_winws_process_pids()
    service_states = get_known_windivert_service_states_runtime()
    busy_services = {
        name: state
        for name, state in service_states.items()
        if state in (_SERVICE_RUNNING, _SERVICE_STOP_PENDING)
    }
    probe = probe_windivert_state_runtime()
    log(
        "WinDivert cleanup settle timeout: "
        f"pids={process_pids or []}, "
        f"busy_services={busy_services or {}}, "
        f"driver_installed={probe.installed}, "
        f"driver_ready={probe.ready}, "
        f"driver_error={probe.error_code}, "
        f"driver_stage={probe.stage}",
        "WARNING",
    )
    return False
