from __future__ import annotations
from pathlib import Path
import subprocess, json, sys, traceback
from typing import Callable, Optional

from log import log
from .autostart_strategy import _resolve_bat_folder     # переиспользуем
from .registry_check import set_autostart_enabled
from utils import run_hidden # обёртка для subprocess.run

SERVICE_NAME = "ZapretCensorliber"

def setup_service_for_strategy(
    selected_mode: str,
    bat_folder: str,
    index_path: str | None = None,
    ui_error_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Создаёт (или пере-создаёт) службу Windows, запускающую .bat-файл стратегии.

    Args:
        selected_mode : отображаемое имя стратегии (поле "name" в index.json)
        bat_folder    : каталог, где лежат .bat и index.json
        index_path    : полный путь к index.json  (опц.)
        ui_error_cb   : callback для вывода подробной ошибки в GUI

    Returns:
        True  — служба создана / обновлена
        False — ошибка (причина уже залогирована, ui_error_cb вызван)
    """
    try:
        # ---------- 1. Определяем, какой .bat должен запускаться ----------
        bat_dir = _resolve_bat_folder(bat_folder)
        idx_path = Path(index_path) if index_path else bat_dir / "index.json"
        if not idx_path.is_file():
            return _fail(f"index.json не найден: {idx_path}", ui_error_cb)

        with idx_path.open(encoding="utf-8-sig") as f:
            data = json.load(f)

        entry_key, entry_val = next(
            ((k, v) for k, v in data.items()
             if isinstance(v, dict) and v.get("name") == selected_mode),
            (None, None)
        )
        if not entry_key:
            return _fail(f"Стратегия «{selected_mode}» не найдена", ui_error_cb)

        bat_name = (
            entry_val.get("file_path")
            if isinstance(entry_val, dict) and entry_val.get("file_path")
            else (entry_key if entry_key.lower().endswith(".bat") else f"{entry_key}.bat")
        )
        bat_path = (bat_dir / bat_name).resolve()
        if not bat_path.is_file():
            return _fail(f".bat отсутствует: {bat_path}", ui_error_cb)

        # ---------- 2. (Пере)создаём службу --------------------------------
        # Останавливаем и удаляем, если уже существует
        _run_sc(["stop",  SERVICE_NAME], ignore_errors=True)
        _run_sc(["delete", SERVICE_NAME], ignore_errors=True)

        # binPath= должен содержать кавычки внутри, а sc требует пробел ПОСЛЕ '='
        bin_path = f'C:\\Windows\\System32\\cmd.exe /c "{bat_path}"'

        create_cmd = [
            "create", SERVICE_NAME,
            "binPath=", bin_path,
            "obj=", "LocalSystem",
            "start=", "auto",
        ]
        if _run_sc(create_cmd):
            _run_sc(["description", SERVICE_NAME,
                     f"Запуск стратегии {selected_mode}"])
            log(f'Служба "{SERVICE_NAME}" создана/обновлена', "INFO")
            
            # Обновляем статус автозапуска в реестре
            set_autostart_enabled(True, "service")
            
            return True
        else:
            return _fail("Не удалось создать службу", ui_error_cb)

    except Exception as exc:
        msg = f"setup_service_for_strategy: {exc}\n{traceback.format_exc()}"
        return _fail(msg, ui_error_cb)


def remove_service() -> bool:
    """
    Удаляет службу Windows
    
    Returns:
        True если служба была удалена, False если её не было
    """
    try:
        # Проверяем существование службы
        query_result = _run_sc(["query", SERVICE_NAME], ignore_errors=True)
        if not query_result:
            # Службы нет
            return False
        
        # Останавливаем службу
        _run_sc(["stop", SERVICE_NAME], ignore_errors=True)
        
        # Удаляем службу
        if _run_sc(["delete", SERVICE_NAME], ignore_errors=True):
            log(f'Служба "{SERVICE_NAME}" удалена', "INFO")
            
            # Проверяем остались ли другие методы автозапуска
            from .checker import CheckerManager
            checker = CheckerManager(None)
            if not checker.check_autostart_exists_full():
                # Если ничего не осталось - отключаем в реестре
                set_autostart_enabled(False)
            
            return True
        else:
            return False
            
    except Exception as e:
        log(f"Ошибка удаления службы: {e}", "❌ ERROR")
        return False


# -------------------------------------------------------------------------
# Вспомогательные функции
# -------------------------------------------------------------------------
def _run_sc(args: list[str], ignore_errors: bool = False) -> bool:
    """
    Запускает `sc.exe` с указанными аргументами.

    Returns True, если returncode == 0.
    """
    cmd = ["C:\\Windows\\System32\\sc.exe"] + args
    res = run_hidden(
        cmd,
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="ignore",
    )
    if res.returncode == 0:
        return True
    if not ignore_errors:
        err = f'sc {" ".join(args)} | code {res.returncode}\n{res.stderr.strip()}'
        log(err, "❌ ERROR")
    return False


def _fail(msg: str, ui_error_cb: Optional[Callable[[str], None]]) -> bool:
    log(msg, "❌ ERROR")
    if ui_error_cb:
        ui_error_cb(msg)
    return False
