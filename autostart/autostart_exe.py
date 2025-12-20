"""
Самостоятельный модуль для управления автозапуском приложения через Планировщик задач Windows.
Не зависит от других модулей проекта.
"""

import os
import sys
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from utils import get_system_exe

TASK_NAME = "ZapretGUI_AutoStart"

# Внутренняя функция логирования (не зависит от внешнего log.py)
def _log(message: str, level: str = "INFO"):
    """Внутреннее логирование модуля"""
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} [{level}] {message}")

def _run_schtasks(args: list, check_output: bool = True) -> Any:
    """Выполняет команду schtasks с правильной обработкой кодировок"""
    cmd = [get_system_exe("schtasks.exe")] + args
    
    for encoding in ['utf-8', 'cp866', 'cp1251']:
        try:
            result = subprocess.run(
                cmd, 
                capture_output=check_output, 
                text=True,
                encoding=encoding, 
                errors='replace',
                timeout=30
            )
            return result
        except (UnicodeDecodeError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue
    
    # Последняя попытка без указания кодировки
    try:
        result = subprocess.run(cmd, capture_output=check_output, timeout=30)
        return result
    except Exception as e:
        class ErrorResult:
            returncode = -1
            stdout = ""
            stderr = str(e)
        return ErrorResult()

def setup_autostart_for_exe(selected_mode: Optional[str] = None,
                            status_cb: Optional[Callable[[str], None]] = None) -> bool:
    """
    Настраивает автозапуск через планировщик задач Windows
    
    Args:
        selected_mode: Выбранный режим (сохраняется в реестр если указан)
        status_cb: Функция для отчета о статусе
    
    Returns:
        True если успешно, False при ошибке
    """
    def _status(msg: str):
        if status_cb:
            status_cb(msg)
    
    try:
        from .registry_check import set_autostart_enabled
        
        _log("Включаем автозапуск GUI", "INFO")
        exe_path = sys.executable
        
        # Удаляем старые механизмы
        _remove_old_shortcut()
        
        # Удаляем существующую задачу если есть
        if is_autostart_enabled():
            _log(f"Удалена существующая задача: {TASK_NAME}", "INFO")
            remove_autostart()
        
        # Создаём новую задачу
        create_args = [
            "/Create",
            "/TN", TASK_NAME,
            "/TR", f'"{exe_path}" --tray',
            "/SC", "ONLOGON",
            "/RL", "HIGHEST",
            "/F"
        ]
        
        result = _run_schtasks(create_args)
        
        if result.returncode != 0:
            error_msg = getattr(result, 'stderr', 'Неизвестная ошибка')
            _log(f"Ошибка создания задачи: {error_msg}", "❌ ERROR")
            _status("Не удалось создать задачу автозапуска")
            return False
        
        # Сохраняем режим в реестр если указан
        if selected_mode:
            _save_last_strategy(selected_mode)
        
        # Обновляем статус автозапуска в реестре
        set_autostart_enabled(True, "exe")
        
        _log(f"Задача автозапуска создана: {TASK_NAME}", "INFO")
        _status("Автозапуск успешно настроен через Планировщик заданий")
        return True
        
    except Exception as exc:
        _log(f"setup_autostart_for_exe: {exc}", "❌ ERROR")
        _status(f"Ошибка: {exc}")
        return False

def remove_autostart() -> bool:
    """Удаляет задачу автозапуска из планировщика"""
    try:
        from .registry_check import set_autostart_enabled
        
        delete_args = ["/Delete", "/TN", TASK_NAME, "/F"]
        result = _run_schtasks(delete_args)
        
        if result.returncode == 0:
            _log(f"Задача автозапуска удалена: {TASK_NAME}", "INFO")
            
            # Проверяем остались ли другие методы автозапуска
            from .checker import CheckerManager
            checker = CheckerManager(None)
            if not checker.check_autostart_exists_full():
                set_autostart_enabled(False)
            
            return True
        elif result.returncode == 1:
            # Задача не найдена - это тоже успех
            _log("Задача автозапуска не найдена", "INFO")
            return True
        else:
            error_msg = getattr(result, 'stderr', 'Неизвестная ошибка')
            _log(f"Не удалось удалить задачу: {error_msg}", "⚠ WARNING")
            return False
            
    except Exception as exc:
        _log(f"remove_autostart: {exc}", "❌ ERROR")
        return False

def is_autostart_enabled() -> bool:
    """Проверяет, включен ли автозапуск через планировщик (полная проверка)"""
    try:
        query_args = ["/Query", "/TN", TASK_NAME]
        result = _run_schtasks(query_args)
        return result.returncode == 0
    except Exception:
        return False

def _remove_old_shortcut() -> bool:
    """Удаляет старый ярлык из папки автозагрузки"""
    try:
        shortcut_path = _startup_shortcut_path()
        if shortcut_path.exists():
            shortcut_path.unlink()
            _log(f"Удален старый ярлык автозапуска: {shortcut_path}", "INFO")
            return True
    except Exception as e:
        _log(f"Ошибка при удалении старого ярлыка: {e}", "⚠ WARNING")
    return False

def remove_all_autostart_mechanisms() -> bool:
    """
    Удаляет все механизмы автозапуска (ярлыки и задачи планировщика)
    ВНИМАНИЕ: Эта функция вызывается из основного приложения
    """
    from .registry_check import set_autostart_enabled
    
    _log("Удаление всех механизмов автозапуска…", "INFO")
    
    removed_any = False
    
    # 1. Удаляем старый ярлык
    if _remove_old_shortcut():
        removed_any = True
    
    # 2. Удаляем задачу из планировщика
    task_was_enabled = is_autostart_enabled()
    if task_was_enabled:
        if remove_autostart():
            removed_any = True
    
    # 3. Дополнительная попытка удаления (на случай скрытых задач)
    if not task_was_enabled:
        try:
            delete_args = ["/Delete", "/TN", TASK_NAME, "/F"]
            result = _run_schtasks(delete_args, check_output=False)
            if result.returncode == 0:
                removed_any = True
                _log(f"Удалена скрытая задача: {TASK_NAME}", "INFO")
        except Exception:
            pass
    
    # 4. Финальная проверка
    final_check = is_autostart_enabled()
    if final_check:
        _log(f"ВНИМАНИЕ: Задача {TASK_NAME} все еще существует после удаления!", "⚠ WARNING")
        # Попытка принудительного удаления через PowerShell
        try:
            ps_cmd = f'Unregister-ScheduledTask -TaskName "{TASK_NAME}" -Confirm:$false -ErrorAction SilentlyContinue'
            subprocess.run(['powershell', '-Command', ps_cmd], 
                         capture_output=True, timeout=10)
            
            # Повторная проверка
            if not is_autostart_enabled():
                _log(f"Задача {TASK_NAME} удалена через PowerShell", "INFO")
                removed_any = True
        except Exception:
            pass
    
    if not removed_any:
        _log("Механизмы автозапуска не найдены", "INFO")
    else:
        _log("Все механизмы автозапуска удалены", "INFO")
        
        # Обновляем реестр если все удалено
        from .checker import CheckerManager
        checker = CheckerManager(None)
        if not checker.check_autostart_exists_full():
            set_autostart_enabled(False)
    
    return True

def _save_last_strategy(strategy: str) -> bool:
    """Сохраняет последнюю стратегию в реестр"""
    try:
        import winreg
        from config import REGISTRY_PATH_GUI
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
            winreg.SetValueEx(key, "LastStrategy", 0, winreg.REG_SZ, strategy)
        
        _log(f"Сохранена стратегия в реестр: {strategy}", "INFO")
        return True
        
    except Exception as e:
        _log(f"Не удалось записать последнюю выбранную стратегию в реестр: {e}", "⚠ WARNING")
        return False

def _startup_shortcut_path() -> Path:
    """Возвращает путь к ярлыку автозагрузки (для совместимости со старым кодом)"""
    return (Path(os.environ["APPDATA"]) /
            "Microsoft/Windows/Start Menu/Programs/Startup/ZapretGUI.lnk")

def get_autostart_status() -> Dict[str, Any]:
    """Возвращает полную информацию о состоянии автозапуска"""
    return {
        "task_enabled": is_autostart_enabled(),
        "shortcut_exists": _startup_shortcut_path().exists(),
        "task_name": TASK_NAME
    }

def debug_autostart() -> None:
    """Отладочная информация (можно вызвать из main.py для диагностики)"""
    _log("=== DEBUG: Состояние автозапуска ===", "INFO")
    
    status = get_autostart_status()
    _log(f"Задача в планировщике: {status['task_enabled']}", "INFO")
    _log(f"Ярлык в автозагрузке: {status['shortcut_exists']}", "INFO")
    
    if status['task_enabled']:
        # Подробная информация о задаче
        try:
            detail_args = ["/Query", "/TN", TASK_NAME, "/FO", "LIST"]
            result = _run_schtasks(detail_args)
            if result.returncode == 0 and hasattr(result, 'stdout'):
                _log("Детали задачи:", "INFO")
                for line in result.stdout.split('\n'):
                    if any(key in line.lower() for key in ['status', 'state', 'run as']):
                        _log(f"  {line.strip()}", "INFO")
        except Exception as e:
            _log(f"Ошибка получения деталей задачи: {e}", "WARNING")
    
    _log("=== Конец отладки ===", "INFO")