from __future__ import annotations

import os
from dataclasses import dataclass

from config.config import MAIN_DIRECTORY
from settings.mode import EXE_NAME_WINWS1
from utils.windows_process_probe import iter_process_names_winapi, iter_uninstall_display_names


KASPERSKY_PROCESS_NAMES = frozenset(
    {
        "avp.exe",
        "kavfs.exe",
        "klnagent.exe",
        "ksde.exe",
        "kavfswp.exe",
        "kavfswh.exe",
        "kavfsslp.exe",
    }
)


@dataclass(frozen=True)
class KasperskyLaunchAdvice:
    cause: str
    solution: str


def detect_kaspersky_antivirus() -> bool:
    """Возвращает True, если в системе найден Kaspersky."""
    try:
        for process_name in iter_process_names_winapi():
            if str(process_name or "").strip().casefold() in KASPERSKY_PROCESS_NAMES:
                return True

        for product_name in iter_uninstall_display_names():
            normalized = str(product_name or "").casefold()
            if "kaspersky" in normalized or "каспер" in normalized:
                return True
    except Exception:
        return False

    return False


def build_kaspersky_launch_advice(*, exe_name: str = EXE_NAME_WINWS1) -> KasperskyLaunchAdvice | None:
    """Строит подсказку только для случая, когда запуск Zapret уже сорвался."""
    if not detect_kaspersky_antivirus():
        return None

    app_folder = os.path.abspath(MAIN_DIRECTORY)
    executable = str(exe_name or EXE_NAME_WINWS1).strip() or EXE_NAME_WINWS1
    return KasperskyLaunchAdvice(
        cause=f"Kaspersky, похоже, помешал запуску Zapret: {executable} не получил доступ к WinDivert",
        solution=(
            "Добавьте папку программы и файлы WinDivert в исключения Kaspersky, "
            f"затем повторите запуск. Папка программы: {app_folder}"
        ),
    )
