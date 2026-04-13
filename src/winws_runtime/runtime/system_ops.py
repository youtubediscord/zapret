from __future__ import annotations

import time

from log.log import log


_KNOWN_WINDIVERT_DRIVERS = ("WinDivert", "WinDivert14", "WinDivert64", "Monkey")
_KNOWN_WINDIVERT_SERVICES = ("WinDivert", "WinDivert14", "WinDivert64", "windivert", "Monkey")


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


def standard_windivert_cleanup_runtime(*, sleep_seconds: float = 0.3) -> bool:
    log("Cleaning up previous winws processes...", "DEBUG")
    ok = True
    ok = force_kill_all_winws_processes() and ok
    ok = cleanup_windivert_services_runtime() and ok
    ok = unload_known_windivert_drivers_runtime() and ok
    time.sleep(max(0.0, float(sleep_seconds)))
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
    log("Aggressive cleanup completed", "INFO")
    return ok
