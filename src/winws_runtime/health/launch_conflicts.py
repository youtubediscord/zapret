from __future__ import annotations

import os
import time
from typing import Dict, List

from log.log import log
from winws_runtime.runtime.system_ops import (
    _KNOWN_WINDIVERT_SERVICES,
    kill_process_by_pid_runtime,
)
from utils.windows_process_probe import (
    iter_process_module_paths_winapi,
    iter_process_records_winapi,
)


CONFLICTING_PROCESSES = {
    "ProcessHacker.exe": {
        "name": "Process Hacker",
        "reason": "Перехватывает системные вызовы и может блокировать WinDivert",
        "solution": "Закройте Process Hacker и повторите запуск Zapret",
    },
    "procexp.exe": {
        "name": "Process Explorer",
        "reason": "Может конфликтовать с WinDivert",
        "solution": "Закройте Process Explorer и повторите запуск Zapret",
    },
    "procexp64.exe": {
        "name": "Process Explorer (64-bit)",
        "reason": "Может конфликтовать с WinDivert",
        "solution": "Закройте Process Explorer и повторите запуск Zapret",
    },
    "GoodbyeDPI.exe": {
        "name": "GoodbyeDPI",
        "reason": "Конфликт с другим DPI-bypass инструментом",
        "solution": "Используйте только один DPI-bypass инструмент",
    },
    "SpoofDPI.exe": {
        "name": "SpoofDPI",
        "reason": "Конфликт с другим DPI-bypass инструментом",
        "solution": "Используйте только один DPI-bypass инструмент",
    },
}

_CONFLICTING_PROCESS_BY_NAME = {
    str(exe_name or "").strip().lower(): dict(info or {})
    for exe_name, info in CONFLICTING_PROCESSES.items()
}

# Папки нашей собственной установки: процессы и драйверы из них — не конфликт.
# Раннеры регистрируют сюда свой work_dir при инициализации.
_OWN_WINDIVERT_DIRS: set[str] = set()

_SERVICES_REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Services"


def register_own_windivert_dirs(*dirs: str) -> None:
    """Регистрирует папки нашей установки, чтобы не считать себя конфликтом."""
    for directory in dirs:
        normalized = _normalize_dir(directory)
        if normalized:
            _OWN_WINDIVERT_DIRS.add(normalized)


def _normalize_dir(directory: str) -> str:
    text = str(directory or "").strip()
    if not text:
        return ""
    # Пути из реестра/снимков всегда с "\"; на тестовых POSIX-системах
    # os.path с ними не работает, поэтому приводим разделитель явно.
    return os.path.normpath(text.replace("\\", os.sep)).lower()


def _is_own_path(path: str) -> bool:
    normalized = _normalize_dir(path)
    if not normalized:
        return False
    for own_dir in _OWN_WINDIVERT_DIRS:
        if normalized == own_dir or normalized.startswith(own_dir + os.sep):
            return True
    return False


def _is_windivert_module_name(module_path: str) -> bool:
    base_name = str(module_path or "").replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    return base_name.startswith("windivert") and base_name.endswith(".dll")


def _normalize_service_image_path(image_path: str) -> str:
    """Приводит ImagePath службы к обычному пути файла драйвера."""
    driver_path = str(image_path or "").strip().strip('"')
    if driver_path.startswith("\\??\\"):
        driver_path = driver_path[4:]
    return driver_path


def find_windivert_holder_processes() -> List[Dict[str, str]]:
    """Ищет чужие процессы с загруженной windivert*.dll.

    Любой процесс не из нашей папки, который держит WinDivert.dll, — почти
    наверняка программа, конфликтующая за драйвер (другой форк zapret,
    GoodbyeDPI и т.п.). Сканирование модулей всех процессов не бесплатно,
    поэтому вызывать только из веток обработки ошибок запуска.
    """
    holders: list[dict] = []
    own_pid = os.getpid()
    try:
        for pid, proc_name in iter_process_records_winapi():
            if int(pid) <= 4 or int(pid) == own_pid:
                continue
            module_paths = iter_process_module_paths_winapi(int(pid))
            if not module_paths:
                continue

            windivert_dlls = [path for path in module_paths if _is_windivert_module_name(path)]
            if not windivert_dlls:
                continue

            exe_path = module_paths[0]
            if _is_own_path(exe_path):
                continue

            holders.append(
                {
                    "name": str(proc_name or "").strip() or os.path.basename(exe_path),
                    "exe": exe_path,
                    "windivert_dll": windivert_dlls[0],
                    "pid": int(pid),
                }
            )
            log(
                f"Обнаружен чужой процесс с WinDivert.dll: {proc_name} (PID {pid}, {exe_path})",
                "WARNING",
            )
    except Exception as e:
        log(f"Ошибка поиска процессов с WinDivert.dll: {e}", "DEBUG")

    return holders


def find_foreign_windivert_service_paths() -> List[str]:
    """Ищет службы WinDivert*, чей драйвер лежит не в нашей папке.

    Работает даже если чужой процесс уже завершился, а его драйвер остался
    зарегистрирован: ImagePath службы называет папку программы-владельца.
    """
    try:
        import winreg
    except Exception:
        return []

    foreign_paths: list[str] = []
    for service_name in _KNOWN_WINDIVERT_SERVICES:
        try:
            key_path = f"{_SERVICES_REGISTRY_KEY}\\{service_name}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as service_key:
                image_path, _ = winreg.QueryValueEx(service_key, "ImagePath")
        except Exception:
            continue

        driver_path = _normalize_service_image_path(image_path)
        if not driver_path or _is_own_path(driver_path):
            continue

        if driver_path not in foreign_paths:
            foreign_paths.append(driver_path)
            log(
                f"Служба {service_name} указывает на чужой драйвер WinDivert: {driver_path}",
                "WARNING",
            )

    return foreign_paths


def build_windivert_conflict_hint() -> str | None:
    """Однострочная подсказка о найденном виновнике для текста ошибки."""
    try:
        holders = find_windivert_holder_processes()
    except Exception:
        holders = []
    if holders:
        first = holders[0]
        return (
            f"Возможный конфликт: {first['name']} (PID {first['pid']}, {first['exe']}) "
            "держит WinDivert — закройте эту программу"
        )

    try:
        foreign_paths = find_foreign_windivert_service_paths()
    except Exception:
        foreign_paths = []
    if foreign_paths:
        return (
            f"Драйвер WinDivert установлен другой программой: {foreign_paths[0]} — "
            "закройте её или выполните очистку драйвера"
        )

    return None


def check_conflicting_processes() -> List[Dict[str, str]]:
    """Ищет программы, которые могут мешать WinDivert."""
    found_conflicts: list[dict] = []
    try:
        for pid, proc_name in iter_process_records_winapi():
            normalized = str(proc_name or "").strip().lower()
            info = _CONFLICTING_PROCESS_BY_NAME.get(normalized)
            if not info:
                continue

            found_conflicts.append(
                {
                    "exe": normalized,
                    "name": info.get("name", normalized),
                    "reason": info.get("reason", ""),
                    "solution": info.get("solution", ""),
                    "pid": int(pid),
                }
            )
            log(
                f"Обнаружен конфликтующий процесс: {info.get('name', normalized)} ({normalized}, PID: {pid})",
                "WARNING",
            )
    except Exception as e:
        log(f"Ошибка WinAPI-проверки конфликтующих процессов: {e}", "DEBUG")

    return found_conflicts


def build_launch_conflict_advice() -> tuple[str, str] | None:
    """Возвращает подсказку только после неудачного запуска Zapret."""
    conflicting = check_conflicting_processes()
    if not conflicting:
        return _build_dynamic_conflict_advice()

    names = ", ".join(
        str(item.get("name") or item.get("exe") or "неизвестная программа")
        for item in conflicting
    )
    solutions = []
    for item in conflicting:
        solution = str(item.get("solution") or "").strip()
        if solution and solution not in solutions:
            solutions.append(solution)

    cause = f"{names}, похоже, помешал запуску Zapret: WinDivert не смог открыться"
    solution = "\n".join(solutions) or "Закройте конфликтующую программу и повторите запуск Zapret"
    return cause, solution


def _build_dynamic_conflict_advice() -> tuple[str, str] | None:
    """Подсказка по программам вне чёрного списка: кто реально держит WinDivert."""
    holders = find_windivert_holder_processes()
    if holders:
        names = ", ".join(f"{h['name']} (PID {h['pid']}, {h['exe']})" for h in holders)
        return (
            f"WinDivert занят другой программой: {names}",
            "Закройте эту программу и повторите запуск Zapret",
        )

    foreign_paths = find_foreign_windivert_service_paths()
    if foreign_paths:
        return (
            f"Драйвер WinDivert установлен другой программой: {foreign_paths[0]}",
            "Закройте ту программу (или удалите её драйвер) и повторите запуск Zapret",
        )

    return None


def try_kill_conflicting_processes(auto_kill: bool = False) -> bool:
    """Пытается закрыть конфликтующие процессы."""
    conflicting = check_conflicting_processes()

    if not conflicting:
        return True

    if not auto_kill:
        log(f"Обнаружено конфликтующих процессов: {len(conflicting)}", "WARNING")
        return False

    log("Попытка закрыть конфликтующие процессы...", "INFO")

    success_count = 0
    for conflict in conflicting:
        try:
            pid = int(conflict.get("pid") or 0)
            if pid <= 0:
                log(f"У конфликтующего процесса {conflict['name']} нет корректного PID", "ERROR")
                continue

            if kill_process_by_pid_runtime(pid, wait_timeout_ms=5000):
                log(f"Процесс {conflict['name']} (PID {pid}) закрыт через WinAPI", "SUCCESS")
                success_count += 1
            else:
                log(f"Не удалось закрыть {conflict['name']} (PID {pid}) через WinAPI", "ERROR")
        except Exception as e:
            log(f"Ошибка при закрытии {conflict['name']}: {e}", "ERROR")

    if success_count == len(conflicting):
        log(f"Все конфликтующие процессы ({success_count}) закрыты", "SUCCESS")
        time.sleep(1)
        return True

    log(f"Закрыто {success_count}/{len(conflicting)} конфликтующих процессов", "WARNING")
    return False


def get_conflicting_processes_report() -> str:
    """Готовит текстовый отчёт для логов."""
    conflicting = check_conflicting_processes()

    if not conflicting:
        return ""

    lines = ["ОБНАРУЖЕНЫ КОНФЛИКТУЮЩИЕ ПРОГРАММЫ:", ""]

    for i, conflict in enumerate(conflicting, 1):
        pid_info = f" (PID: {conflict['pid']})" if conflict.get("pid") else ""
        lines.append(f"{i}. {conflict['name']}{pid_info}")
        lines.append(f"   Файл: {conflict['exe']}")
        lines.append(f"   Проблема: {conflict['reason']}")
        lines.append(f"   Решение: {conflict['solution']}")
        lines.append("")

    lines.append("Закройте эти программы, если запуск Zapret завершился ошибкой.")
    return "\n".join(lines)
