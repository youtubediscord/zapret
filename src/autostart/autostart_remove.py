from __future__ import annotations

import os
import time
import winreg
from pathlib import Path
from typing import Callable, Iterable

from config import APP_CORE_PATH, MAIN_DIRECTORY, REGISTRY_PATH
from log import log
from utils import get_system_exe, run_hidden


class AutoStartCleaner:
    """Удаляет канонический task и legacy-хвосты старой модели автозапуска."""

    CANONICAL_TASK_NAME = "ZapretGUI_AutoStart"
    LEGACY_STARTUP_SHORTCUTS: tuple[str, ...] = ("ZapretGUI.lnk", "ZapretStrategy.lnk")
    LEGACY_SCHEDULER_TASKS: tuple[str, ...] = (
        "ZapretStrategy",
        "ZapretCensorliber",
        "ZapretDirect_AutoStart",
        "ZapretDirect",
        "ZapretDirectBoot",
    )
    LEGACY_SERVICE_NAMES: tuple[str, ...] = (
        "ZapretCensorliber",
        "ZapretDirect",
        "ZapretDirectService",
    )
    LEGACY_FILES: tuple[str, ...] = (
        "zapret_autostart.bat",
        "zapret_direct.bat",
        "zapret_boot_task.xml",
        "zapret_logon_task.xml",
        "zapret_service.bat",
    )

    def __init__(
        self,
        *,
        service_names: Iterable[str] | None = None,
        status_cb: Callable[[str], None] | None = None,
    ):
        self.service_names = tuple(service_names) if service_names else self.LEGACY_SERVICE_NAMES
        self._status_cb = status_cb

    def _status(self, msg: str):
        if self._status_cb:
            self._status_cb(msg)

    def run(self, *, remove_canonical: bool = True, remove_legacy: bool = True) -> int:
        removed_count = 0

        if remove_canonical:
            removed_count += self._remove_scheduler_tasks((self.CANONICAL_TASK_NAME,))

        if remove_legacy:
            removed_count += self._remove_startup_shortcuts(self.LEGACY_STARTUP_SHORTCUTS)
            removed_count += self._remove_scheduler_tasks(self.LEGACY_SCHEDULER_TASKS)
            removed_count += self._remove_legacy_run_entry()
            removed_count += self._remove_autostart_registry_state_key()
            removed_count += self._remove_legacy_files()

            for svc_name in self.service_names:
                removed_count += self._remove_service(svc_name)

        if removed_count > 0:
            log(f"Удалено механизмов автозапуска: {removed_count}", "INFO")
        else:
            log("Механизмы автозапуска не найдены", "INFO")

        return removed_count

    def _remove_startup_shortcuts(self, shortcuts: Iterable[str]) -> int:
        removed = 0
        startup_dir = (
            Path(os.environ["APPDATA"])
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        for shortcut_name in shortcuts:
            path = startup_dir / shortcut_name
            if not path.exists():
                continue
            try:
                path.unlink()
                log(f"Legacy-ярлык автозапуска удалён: {path}", "INFO")
                removed += 1
            except Exception as exc:
                log(f"Не удалось удалить ярлык {path}: {exc}", "⚠ WARNING")
        return removed

    def _remove_scheduler_tasks(self, task_names: Iterable[str]) -> int:
        removed = 0
        schtasks = get_system_exe("schtasks.exe")
        for task_name in task_names:
            check = run_hidden(
                [schtasks, "/Query", "/TN", task_name],
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="ignore",
            )
            if check.returncode != 0:
                continue
            log(f"Найдена задача автозапуска {task_name}, удаляем", "INFO")
            delete = run_hidden(
                [schtasks, "/Delete", "/TN", task_name, "/F"],
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="ignore",
            )
            if delete.returncode == 0:
                removed += 1
            else:
                err = str(delete.stderr or delete.stdout or "").strip()
                log(f"Не удалось удалить задачу {task_name}: {err}", "⚠ WARNING")
        return removed

    @staticmethod
    def _remove_legacy_run_entry() -> int:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                try:
                    winreg.DeleteValue(key, "ZapretGUI")
                    log("Legacy-запись автозапуска в HKCU\\...\\Run удалена", "INFO")
                    return 1
                except FileNotFoundError:
                    return 0
        except Exception as exc:
            log(f"Ошибка удаления legacy-записи автозапуска: {exc}", "⚠ WARNING")
            return 0

    @staticmethod
    def _remove_autostart_registry_state_key() -> int:
        autostart_registry_path = rf"{REGISTRY_PATH}\Autostart"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart_registry_path, 0, winreg.KEY_WRITE) as key:
                removed_any = 0
                for value_name in ("AutostartEnabled", "AutostartMethod"):
                    try:
                        winreg.DeleteValue(key, value_name)
                        removed_any += 1
                    except FileNotFoundError:
                        continue

            if removed_any <= 0:
                return 0

            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, autostart_registry_path)
            except OSError:
                pass

            log("Старое registry-состояние автозапуска удалено", "INFO")
            return 1
        except FileNotFoundError:
            return 0
        except Exception as exc:
            log(f"Ошибка очистки registry-состояния автозапуска: {exc}", "⚠ WARNING")
            return 0

    @classmethod
    def _remove_legacy_files(cls) -> int:
        removed = 0
        search_roots: list[Path] = []
        for candidate in (Path.cwd(), Path(APP_CORE_PATH), Path(MAIN_DIRECTORY)):
            if candidate not in search_roots:
                search_roots.append(candidate)

        for filename in cls.LEGACY_FILES:
            for root in search_roots:
                path = root / filename
                if not path.exists():
                    continue
                try:
                    path.unlink()
                    removed += 1
                    log(f"Удалён legacy-файл автозапуска: {path}", "INFO")
                except Exception as exc:
                    log(f"Не удалось удалить файл {path}: {exc}", "⚠ WARNING")
        return removed

    def _remove_service(self, svc_name: str) -> int:
        sc_exe = get_system_exe("sc.exe")
        query = run_hidden(
            [sc_exe, "query", svc_name],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
        )
        if query.returncode != 0:
            return 0

        self._status(f"Остановка legacy-службы «{svc_name}»…")
        log(f"Останавливаем legacy-службу {svc_name}", "INFO")
        run_hidden([sc_exe, "stop", svc_name], capture_output=True)
        time.sleep(1)

        self._status(f"Удаление legacy-службы «{svc_name}»…")
        delete = run_hidden(
            [sc_exe, "delete", svc_name],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
        )
        if delete.returncode == 0:
            log(f"Legacy-служба {svc_name} удалена", "INFO")
        else:
            err = str(delete.stderr or delete.stdout or "").strip()
            log(f"Ошибка удаления службы {svc_name}: {err}", "⚠ WARNING")
        return 1


def clear_existing_autostart(*, status_cb: Callable[[str], None] | None = None) -> int:
    """Удаляет и канонический task, и legacy-механизмы перед новой установкой."""
    cleaner = AutoStartCleaner(status_cb=status_cb)
    return cleaner.run(remove_canonical=True, remove_legacy=True)


def clear_legacy_autostart(*, status_cb: Callable[[str], None] | None = None) -> int:
    """Удаляет только legacy-механизмы, не трогая текущий канонический task."""
    cleaner = AutoStartCleaner(status_cb=status_cb)
    return cleaner.run(remove_canonical=False, remove_legacy=True)


def has_legacy_autostart() -> bool:
    cleaner = AutoStartCleaner()

    try:
        startup_dir = (
            Path(os.environ["APPDATA"])
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        if any((startup_dir / name).exists() for name in cleaner.LEGACY_STARTUP_SHORTCUTS):
            return True
    except Exception:
        pass

    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, "ZapretGUI")
            if value and ".exe" in str(value).lower():
                return True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    schtasks = get_system_exe("schtasks.exe")
    for task_name in cleaner.LEGACY_SCHEDULER_TASKS:
        try:
            check = run_hidden(
                [schtasks, "/Query", "/TN", task_name],
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="ignore",
            )
            if check.returncode == 0:
                return True
        except Exception:
            pass

    sc_exe = get_system_exe("sc.exe")
    for svc_name in cleaner.LEGACY_SERVICE_NAMES:
        try:
            query = run_hidden(
                [sc_exe, "query", svc_name],
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="ignore",
            )
            if query.returncode == 0 and "STATE" in str(query.stdout or ""):
                return True
        except Exception:
            pass

    autostart_registry_path = rf"{REGISTRY_PATH}\Autostart"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart_registry_path, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    for filename in cleaner.LEGACY_FILES:
        for root in (Path.cwd(), Path(APP_CORE_PATH), Path(MAIN_DIRECTORY)):
            try:
                if (root / filename).exists():
                    return True
            except Exception:
                pass

    return False
