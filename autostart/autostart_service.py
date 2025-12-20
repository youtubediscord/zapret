"""
Создание Windows службы для BAT-режима (Zapret 1).
Использует прямой Windows API вместо sc.exe для скорости.
"""

from __future__ import annotations
from pathlib import Path
import traceback
from typing import Callable, Optional

from log import log
from utils import get_system_exe
from .autostart_strategy import _resolve_bat_folder, _find_bat_by_name
from .registry_check import set_autostart_enabled
from .service_api import (
    create_bat_service,
    delete_service,
    start_service,
    service_exists,
    stop_service
)

SERVICE_NAME = "ZapretCensorliber"
SERVICE_DISPLAY_NAME = "Zapret DPI Bypass"
SERVICE_DESCRIPTION = "Автоматический запуск Zapret для обхода DPI-блокировок"


def setup_service_for_strategy(
    selected_mode: str,
    bat_folder: str,
    index_path: str | None = None,  # Устарел, игнорируется
    ui_error_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Создаёт (или пере-создаёт) службу Windows, запускающую .bat-файл стратегии.
    Использует прямой Windows API для максимальной скорости.

    Args:
        selected_mode : отображаемое имя стратегии (поле REM NAME: в .bat)
        bat_folder    : каталог с .bat файлами
        index_path    : устарел, игнорируется
        ui_error_cb   : callback для вывода подробной ошибки в GUI

    Returns:
        True  — служба создана / обновлена
        False — ошибка (причина уже залогирована, ui_error_cb вызван)
    """
    try:
        # ---------- 1. Определяем, какой .bat должен запускаться ----------
        bat_dir = _resolve_bat_folder(bat_folder)
        
        if not bat_dir.is_dir():
            return _fail(f"Папка стратегий не найдена: {bat_dir}", ui_error_cb)

        # Ищем .bat файл по имени стратегии
        bat_path = _find_bat_by_name(bat_dir, selected_mode)
        
        if not bat_path or not bat_path.is_file():
            return _fail(f"Стратегия «{selected_mode}» не найдена в {bat_dir}", ui_error_cb)

        log(f"Найден .bat файл для стратегии '{selected_mode}': {bat_path}", "DEBUG")

        # ---------- 2. Создаём службу (приоритет: NSSM > API) --------------------------------
        log(f"Создание службы для стратегии: {selected_mode}", "INFO")
        
        # Метод 1: NSSM (предпочтительный)
        from .nssm_service import get_nssm_path, create_service_with_nssm, start_service_with_nssm
        
        nssm_path = get_nssm_path()
        if nssm_path:
            log("⚡ Создание службы через NSSM (рекомендуется)...", "INFO")
            
            # NSSM не может запускать .bat напрямую, поэтому используем cmd.exe
            if create_service_with_nssm(
                service_name=SERVICE_NAME,
                display_name=SERVICE_DISPLAY_NAME,
                exe_path=get_system_exe("cmd.exe"),
                args=["/c", str(bat_path)],
                description=f"{SERVICE_DESCRIPTION} (стратегия: {selected_mode})",
                auto_start=True
            ):
                # Запускаем службу
                if start_service_with_nssm(SERVICE_NAME):
                    log(f"✅ Служба {SERVICE_NAME} создана через NSSM и запущена", "SUCCESS")
                else:
                    log(f"⚠ Служба создана через NSSM, но не запущена", "WARNING")
                
                set_autostart_enabled(True, "service")
                return True
            else:
                log("NSSM не смог создать службу, пробуем Windows API...", "WARNING")
        else:
            log("NSSM не найден, используем Windows API...", "INFO")
        
        # Метод 2: Windows API (fallback)
        if create_bat_service(
            service_name=SERVICE_NAME,
            display_name=SERVICE_DISPLAY_NAME,
            bat_path=str(bat_path),
            description=f"{SERVICE_DESCRIPTION} (стратегия: {selected_mode})",
            auto_start=True
        ):
            log(f'Служба "{SERVICE_NAME}" создана через Windows API', "✅ SUCCESS")
            set_autostart_enabled(True, "service")
            return True
        else:
            return _fail("Не удалось создать службу ни одним из методов", ui_error_cb)

    except Exception as exc:
        msg = f"setup_service_for_strategy: {exc}\n{traceback.format_exc()}"
        return _fail(msg, ui_error_cb)


def remove_service() -> bool:
    """
    ⚡ Удаляет службу Windows (NSSM или API).
    
    Returns:
        True если служба была удалена, False если её не было
    """
    try:
        from .nssm_service import remove_service_with_nssm, service_exists_nssm
        
        # Пробуем удалить через NSSM сначала
        if service_exists_nssm(SERVICE_NAME):
            log("Удаление службы через NSSM...", "INFO")
            result = remove_service_with_nssm(SERVICE_NAME)
        else:
            # Удаляем через Windows API
            if not service_exists(SERVICE_NAME):
                log(f"Служба {SERVICE_NAME} не существует", "DEBUG")
                return False
            
            log("Удаление службы через Windows API...", "INFO")
            result = delete_service(SERVICE_NAME)
        
        if result:
            log(f'Служба "{SERVICE_NAME}" удалена', "INFO")
            
            # Проверяем остались ли другие методы автозапуска
            from .checker import CheckerManager
            checker = CheckerManager(None)
            if not checker.check_autostart_exists_full():
                set_autostart_enabled(False)
            
            return True
        else:
            return False
            
    except Exception as e:
        log(f"Ошибка удаления службы: {e}", "❌ ERROR")
        return False


def start_service_now() -> bool:
    """⚡ Запускает службу (NSSM или API)"""
    from .nssm_service import start_service_with_nssm, service_exists_nssm
    
    if service_exists_nssm(SERVICE_NAME):
        return start_service_with_nssm(SERVICE_NAME)
    
    return start_service(SERVICE_NAME)


def stop_service_now() -> bool:
    """⚡ Останавливает службу (NSSM или API)"""
    from .nssm_service import stop_service_with_nssm, service_exists_nssm
    
    if service_exists_nssm(SERVICE_NAME):
        return stop_service_with_nssm(SERVICE_NAME)
    
    return stop_service(SERVICE_NAME)


def is_service_installed() -> bool:
    """⚡ Проверяет установлена ли служба (NSSM или API)"""
    from .nssm_service import service_exists_nssm
    
    # Проверяем через NSSM сначала
    if service_exists_nssm(SERVICE_NAME):
        return True
    
    # Fallback на Windows API
    return service_exists(SERVICE_NAME)


def _fail(msg: str, ui_error_cb: Optional[Callable[[str], None]]) -> bool:
    log(msg, "❌ ERROR")
    if ui_error_cb:
        ui_error_cb(msg)
    return False
