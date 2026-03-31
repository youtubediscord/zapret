"""
Модуль для создания Windows службы для Direct режима (Zapret 2).
Использует прямой Windows API для максимальной скорости.
"""

import os
import time
from pathlib import Path
from typing import Optional, Callable, List
from log import log
from .registry_check import set_autostart_enabled
from .service_api import (
    create_bat_service,
    create_zapret_service,
    delete_service,
    start_service,
    stop_service,
    service_exists
)

SERVICE_NAME = "ZapretDirectService"
SERVICE_DISPLAY_NAME = "Zapret Direct Mode Service"
SERVICE_DESCRIPTION = "Позволяет запустить Zapret в Direct режиме при загрузке системы"

def create_direct_service_bat(
    winws_exe: str,
    strategy_args: List[str],
    work_dir: str
) -> Optional[str]:
    """
    Создает zapret_service.bat файл для запуска из службы
    """
    try:
        from .autostart_direct import _resolve_file_paths
        from config import MAIN_DIRECTORY
        from launcher_common import apply_all_filters
        
        # Разрешаем пути
        resolved_args = _resolve_file_paths(strategy_args, work_dir)
        
        # Применяем ВСЕ фильтры в правильном порядке
        lists_dir = os.path.join(work_dir, "lists")
        resolved_args = apply_all_filters(resolved_args, lists_dir)
        
        # Создаем .bat файл в корневой папке программы
        bat_path = os.path.join(MAIN_DIRECTORY, "zapret_service.bat")
        
        # Создаем содержимое .bat файла
        bat_content = f"""@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
cd /d "{work_dir}"

echo [%date% %time%] Starting Zapret Direct Service... >> "{work_dir}\\logs\\service_start.log"
echo Working directory: %cd% >> "{work_dir}\\logs\\service_start.log"

:START
"{winws_exe}" {' '.join(resolved_args)}

set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] Process exited with code: !EXIT_CODE! >> "{work_dir}\\logs\\service_start.log"

if !EXIT_CODE! neq 0 (
    echo Restarting in 5 seconds... >> "{work_dir}\\logs\\service_start.log"
    timeout /t 5 /nobreak > nul
    goto START
)

exit /b !EXIT_CODE!
"""
        
        # Записываем файл с UTF-8 BOM для правильной кодировки
        with open(bat_path, 'w', encoding='utf-8-sig') as f:
            f.write(bat_content)
        
        log(f"Создан .bat файл для службы: {bat_path}", "INFO")
        return bat_path
        
    except Exception as e:
        log(f"Ошибка создания .bat файла для службы: {e}", "❌ ERROR")
        return None


def setup_direct_service(
    winws_exe: str,
    strategy_args: List[str],
    strategy_name: str = "direct_zapret2",
    ui_error_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """
    ⚡ Создает Windows службу для запуска Direct режима.
    Приоритет: NSSM > BAT-обертка
    """
    try:
        import ctypes
        from config import MAIN_DIRECTORY, LOGS_FOLDER
        from .autostart_direct import _resolve_file_paths
        from .autostart_remove import clear_existing_autostart
        from launcher_common import apply_all_filters
        from .service_api import create_zapret_service
        from .nssm_service import (
            get_nssm_path, 
            create_service_with_nssm, 
            start_service_with_nssm
        )

        clear_existing_autostart(status_cb=ui_error_cb)
        
        # Создаем папку для логов если её нет
        os.makedirs(LOGS_FOLDER, exist_ok=True)

        # Создание служб требует прав администратора.
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                error_msg = (
                    "Для создания службы требуются права администратора. "
                    "Перезапустите программу от имени администратора."
                )
                log(error_msg, "❌ ERROR")
                if ui_error_cb:
                    ui_error_cb(error_msg)
                return False
        except Exception:
            pass

        if not os.path.exists(winws_exe):
            error_msg = f"winws.exe не найден: {winws_exe}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False

        try:
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
        except Exception:
            launch_method = None

        # direct_zapret2: используем обертку NSSM и запускаем winws2.exe через @preset файл.
        # Это даёт корректный "service wrapper" без необходимости поддержки service-протокола в winws2.exe.
        if launch_method == "direct_zapret2":
            nssm_path = get_nssm_path()
            if nssm_path:
                log("⚡ Создание службы direct_zapret2 через NSSM (@preset)...", "INFO")

                if create_service_with_nssm(
                    service_name=SERVICE_NAME,
                    display_name=SERVICE_DISPLAY_NAME,
                    exe_path=winws_exe,
                    args=strategy_args,
                    work_dir=MAIN_DIRECTORY,
                    description=f"{SERVICE_DESCRIPTION} (стратегия: {strategy_name})",
                    auto_start=True,
                ):
                    if not start_service_with_nssm(SERVICE_NAME):
                        error_msg = "Служба создана через NSSM, но не запущена"
                        log(error_msg, "❌ ERROR")
                        try:
                            delete_service(SERVICE_NAME)
                        except Exception:
                            pass
                        if ui_error_cb:
                            ui_error_cb(error_msg)
                        return False

                    log(f"✅ Служба {SERVICE_NAME} создана через NSSM и запущена", "SUCCESS")
                    set_autostart_enabled(True, "direct_service")
                    return True

                error_msg = "NSSM не смог создать службу Direct режима"
                log(error_msg, "❌ ERROR")
                if ui_error_cb:
                    ui_error_cb(error_msg)
                return False

            # Fallback: пробуем создать через WinAPI (служба может не стартовать, если winws2.exe не Service-aware).
            log("NSSM не найден, пробуем создать службу через WinAPI...", "WARNING")
            if create_zapret_service(
                service_name=SERVICE_NAME,
                display_name=SERVICE_DISPLAY_NAME,
                exe_path=winws_exe,
                args=strategy_args,
                description=f"{SERVICE_DESCRIPTION} (стратегия: {strategy_name})",
                auto_start=True,
            ):
                try:
                    if not start_service(SERVICE_NAME):
                        error_msg = "Служба создана через WinAPI, но не удалось запустить"
                        log(error_msg, "❌ ERROR")
                        try:
                            delete_service(SERVICE_NAME)
                        except Exception:
                            pass
                        if ui_error_cb:
                            ui_error_cb(error_msg)
                        return False
                except Exception as e:
                    error_msg = f"Ошибка запуска службы после создания: {e}"
                    log(error_msg, "❌ ERROR")
                    try:
                        delete_service(SERVICE_NAME)
                    except Exception:
                        pass
                    if ui_error_cb:
                        ui_error_cb(error_msg)
                    return False

                log(f"✅ Служба {SERVICE_NAME} создана через WinAPI и запущена", "SUCCESS")
                set_autostart_enabled(True, "direct_service")
                return True

            error_msg = "Не удалось создать службу Direct режима (NSSM/WinAPI)"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
        
        # Разрешаем пути и применяем фильтры
        resolved_args = _resolve_file_paths(strategy_args, MAIN_DIRECTORY)
        lists_dir = os.path.join(MAIN_DIRECTORY, "lists")
        resolved_args = apply_all_filters(resolved_args, lists_dir)
        
        # Метод 1: NSSM (предпочтительный)
        nssm_path = get_nssm_path()
        if nssm_path:
            log("⚡ Создание службы через NSSM (рекомендуется)...", "INFO")
            
            if create_service_with_nssm(
                service_name=SERVICE_NAME,
                display_name=SERVICE_DISPLAY_NAME,
                exe_path=winws_exe,
                args=resolved_args,
                work_dir=MAIN_DIRECTORY,
                description=f"{SERVICE_DESCRIPTION} (стратегия: {strategy_name})",
                auto_start=True
            ):
                # Запускаем службу
                if not start_service_with_nssm(SERVICE_NAME):
                    error_msg = "Служба создана через NSSM, но не запущена"
                    log(error_msg, "❌ ERROR")
                    try:
                        delete_service(SERVICE_NAME)
                    except Exception:
                        pass
                    if ui_error_cb:
                        ui_error_cb(error_msg)
                    return False

                log(f"✅ Служба {SERVICE_NAME} создана через NSSM и запущена", "SUCCESS")
                set_autostart_enabled(True, "direct_service")
                return True
            else:
                log("NSSM не смог создать службу, пробуем BAT-обертку...", "WARNING")
        else:
            log("NSSM не найден, используем BAT-обертку...", "INFO")
        
        # Метод 2: BAT-обертка (fallback)
        log("Создание службы через BAT-обертку...", "INFO")
        bat_path = create_direct_service_bat(winws_exe, strategy_args, MAIN_DIRECTORY)
        if not bat_path:
            error_msg = "Не удалось создать .bat файл для службы"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
        
        if create_bat_service(
            service_name=SERVICE_NAME,
            display_name=SERVICE_DISPLAY_NAME,
            bat_path=bat_path,
            description=f"{SERVICE_DESCRIPTION} (стратегия: {strategy_name})",
            auto_start=True
        ):
            # Запускаем службу
            if not start_service(SERVICE_NAME):
                error_msg = "Служба создана через .bat, но не удалось запустить"
                log(error_msg, "❌ ERROR")
                try:
                    delete_service(SERVICE_NAME)
                except Exception:
                    pass
                if ui_error_cb:
                    ui_error_cb(error_msg)
                return False

            log(f"Служба {SERVICE_NAME} создана через .bat и запущена", "✅ SUCCESS")
            set_autostart_enabled(True, "direct_service")
            # Сообщение об успехе показывает вызывающий код
            return True
        
        error_msg = "Не удалось создать службу ни одним из методов"
        log(error_msg, "❌ ERROR")
        if ui_error_cb:
            ui_error_cb(error_msg)
        return False
            
    except Exception as e:
        log(f"Ошибка создания службы: {e}", "❌ ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        if ui_error_cb:
            ui_error_cb(f"Ошибка: {e}")
        return False


def remove_direct_service() -> bool:
    """
    ⚡ Удаляет службу Direct режима (NSSM или Windows API)
    """
    try:
        from .nssm_service import remove_service_with_nssm, service_exists_nssm
        
        # Пробуем удалить через NSSM сначала
        if service_exists_nssm(SERVICE_NAME):
            log("Удаление службы через NSSM...", "INFO")
            result = remove_service_with_nssm(SERVICE_NAME)
        else:
            # Удаляем через Windows API
            log("Удаление службы через Windows API...", "INFO")
            result = delete_service(SERVICE_NAME)
        
        # Удаляем .bat файл
        from config import MAIN_DIRECTORY
        bat_path = os.path.join(MAIN_DIRECTORY, "zapret_service.bat")
        if os.path.exists(bat_path):
            try:
                os.remove(bat_path)
                log(f"Удален файл: {bat_path}", "DEBUG")
            except:
                pass
        
        return result
        
    except Exception as e:
        log(f"Ошибка при удалении службы: {e}", "WARNING")
        return False


def check_direct_service_exists() -> bool:
    """
    ⚡ Проверяет существование службы Direct режима (NSSM или Windows API)
    """
    try:
        # NSSM создаёт обычную Windows-службу с тем же именем. Поэтому достаточно
        # проверить наличие службы через WinAPI.
        return service_exists(SERVICE_NAME)
    except Exception:
        return False


def stop_direct_service() -> bool:
    """⚡ Останавливает службу Direct режима (NSSM или Windows API)"""
    from .nssm_service import stop_service_with_nssm, service_exists_nssm
    
    if service_exists_nssm(SERVICE_NAME):
        return stop_service_with_nssm(SERVICE_NAME)
    
    return stop_service(SERVICE_NAME)


def start_direct_service() -> bool:
    """⚡ Запускает службу Direct режима (NSSM или Windows API)"""
    from .nssm_service import start_service_with_nssm, service_exists_nssm
    
    if service_exists_nssm(SERVICE_NAME):
        return start_service_with_nssm(SERVICE_NAME)
    
    return start_service(SERVICE_NAME)
