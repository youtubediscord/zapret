"""
Модуль для настройки автозапуска стратегий в Direct режиме.
Запускает winws.exe напрямую через задачи планировщика.
"""

import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from typing import Optional, Callable, Dict, List
from log import log
from utils import run_hidden, get_system_exe
from .registry_check import set_autostart_enabled

# Имена для задач Direct режима
DIRECT_TASK_NAME = "ZapretDirect"
DIRECT_BOOT_TASK_NAME = "ZapretDirectBoot"  # Задача для запуска при загрузке системы

def _resolve_file_paths(args: List[str], work_dir: str) -> List[str]:
    """
    Разрешает относительные пути к файлам
    """
    from config import WINDIVERT_FILTER
    
    resolved_args = []
    lists_dir = os.path.join(work_dir, "lists")
    bin_dir = os.path.join(work_dir, "bin")
    
    for arg in args:
        # Обработка --wf-raw-part (новый формат для winws2)
        if arg.startswith("--wf-raw-part="):
            value = arg.split("=", 1)[1]
            
            # Если значение начинается с @, это означает файл
            if value.startswith("@"):
                filename = value[1:]  # Убираем @ в начале
                filename = filename.strip('"')
                
                if not os.path.isabs(filename):
                    # WINDIVERT_FILTER - это путь к папке windivert.filter
                    full_path = os.path.join(WINDIVERT_FILTER, filename)
                    
                    # Проверяем существование файла
                    if not os.path.exists(full_path):
                        log(f"Предупреждение: файл фильтра не найден: {full_path}", "WARNING")
                    
                    resolved_args.append(f'--wf-raw-part=@{full_path}')
                else:
                    resolved_args.append(f'--wf-raw-part=@{filename}')
            else:
                # Если не файл, оставляем как есть
                resolved_args.append(arg)
        
        # Обработка хостлистов
        elif any(arg.startswith(prefix) for prefix in [
            "--hostlist=", "--ipset=", "--hostlist-exclude=", "--ipset-exclude="
        ]):
            prefix, filename = arg.split("=", 1)
            filename = filename.strip('"')
            
            if not os.path.isabs(filename):
                full_path = os.path.join(lists_dir, filename)
                resolved_args.append(f'{prefix}={full_path}')
            else:
                resolved_args.append(f'{prefix}={filename}')
        
        # Обработка bin файлов
        elif any(arg.startswith(prefix) for prefix in [
            "--dpi-desync-fake-tls=",
            "--dpi-desync-fake-syndata=", 
            "--dpi-desync-fake-quic=",
            "--dpi-desync-fake-unknown-udp=",
            "--dpi-desync-split-seqovl-pattern=",
            "--dpi-desync-fake-http=",
            "--dpi-desync-fake-unknown=",
            "--dpi-desync-fakedsplit-pattern="
        ]):
            prefix, filename = arg.split("=", 1)
            
            # Проверяем специальные значения (hex или модификаторы)
            if filename.startswith("0x") or filename.startswith("!") or filename.startswith("^"):
                resolved_args.append(arg)
            else:
                filename = filename.strip('"')
                
                if not os.path.isabs(filename):
                    full_path = os.path.join(bin_dir, filename)
                    resolved_args.append(f'{prefix}={full_path}')
                else:
                    resolved_args.append(f'{prefix}={filename}')
        else:
            resolved_args.append(arg)
    
    return resolved_args

def _build_command_line(winws_exe: str, args: List[str], work_dir: str) -> str:
    """
    Строит командную строку для winws.exe с правильным экранированием
    """
    from strategy_menu.apply_filters import apply_all_filters
    
    # Разрешаем пути к файлам
    resolved_args = _resolve_file_paths(args, work_dir)
    
    # ✅ Применяем ВСЕ фильтры в правильном порядке
    lists_dir = os.path.join(work_dir, "lists")
    resolved_args = apply_all_filters(resolved_args, lists_dir)
    
    # Экранируем аргументы для командной строки Windows
    escaped_args = []
    for arg in resolved_args:
        # Если аргумент содержит пробелы или специальные символы, заключаем в кавычки
        if ' ' in arg or '&' in arg or '|' in arg or '>' in arg or '<' in arg:
            # Экранируем внутренние кавычки
            arg = arg.replace('"', '\\"')
            escaped_args.append(f'"{arg}"')
        else:
            escaped_args.append(arg)
    
    # Формируем полную командную строку
    cmd_line = f'"{winws_exe}" {" ".join(escaped_args)}'
    
    return cmd_line


def setup_direct_autostart_task(
    winws_exe: str,
    strategy_args: List[str],
    strategy_name: str = "Direct",
    ui_error_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Создает задачу планировщика для запуска winws.exe при входе пользователя
    """
    try:
        if not os.path.exists(winws_exe):
            error_msg = f"winws.exe не найден: {winws_exe}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
        
        # Определяем рабочую директорию
        exe_dir = os.path.dirname(winws_exe)
        work_dir = os.path.dirname(exe_dir)
        
        # Строим командную строку
        cmd_line = _build_command_line(winws_exe, strategy_args, work_dir)
        
        # Проверяем длину командной строки
        if len(cmd_line) > 260:
            log(f"Внимание: длина команды {len(cmd_line)} символов", "⚠ WARNING")
            # Создаем .bat файл как fallback
            return _create_task_with_bat_fallback(winws_exe, strategy_args, work_dir, DIRECT_TASK_NAME, "ONLOGON", ui_error_cb)
        
        # Сохраняем конфигурацию
        _save_direct_strategy_config(strategy_args, strategy_name, cmd_line)
        
        # Удаляем старую задачу
        _delete_task(DIRECT_TASK_NAME)
        
        # Создаем задачу с прямым запуском winws.exe
        create_cmd = [
            get_system_exe("schtasks.exe"),
            "/Create",
            "/TN", DIRECT_TASK_NAME,
            "/TR", cmd_line,
            "/SC", "ONLOGON",
            "/RU", "SYSTEM",
            "/RL", "HIGHEST",
            "/F"
        ]
        
        log(f"Создание задачи: {DIRECT_TASK_NAME}", "INFO")
        log(f"Длина команды: {len(cmd_line)} символов", "DEBUG")
        log(f"Команда schtasks: {' '.join(create_cmd)}", "DEBUG")
        
        result = run_hidden(
            create_cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore"
        )
        
        log(f"schtasks returncode: {result.returncode}", "DEBUG")
        log(f"schtasks stdout: {result.stdout}", "DEBUG")
        log(f"schtasks stderr: {result.stderr}", "DEBUG")
        
        if result.returncode == 0:
            log(f"Задача {DIRECT_TASK_NAME} создана", "✅ SUCCESS")
            # Обновляем статус в реестре
            set_autostart_enabled(True, "direct_task")
            return True
        else:
            error_msg = f"Ошибка создания задачи (код {result.returncode}):\n{result.stderr or result.stdout}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
            
    except Exception as e:
        log(f"Ошибка: {e}", "❌ ERROR")
        if ui_error_cb:
            ui_error_cb(f"Ошибка: {e}")
        return False


def setup_direct_autostart_service(
    winws_exe: str,
    strategy_args: List[str],
    strategy_name: str = "Direct",
    ui_error_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Создает задачу планировщика с триггером при запуске системы (вместо службы)
    Это более надежный способ для программ, не поддерживающих протокол служб Windows
    """
    try:
        if not os.path.exists(winws_exe):
            error_msg = f"winws.exe не найден: {winws_exe}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
        
        # Определяем рабочую директорию
        exe_dir = os.path.dirname(winws_exe)
        work_dir = os.path.dirname(exe_dir)
        
        # Строим командную строку
        cmd_line = _build_command_line(winws_exe, strategy_args, work_dir)
        
        # Проверяем длину
        if len(cmd_line) > 260:
            log(f"Команда слишком длинная ({len(cmd_line)} символов), используем .bat файл", "⚠ WARNING")
            return _create_task_with_bat_fallback(winws_exe, strategy_args, work_dir, DIRECT_BOOT_TASK_NAME, "ONSTART", ui_error_cb)
        
        # Удаляем старую задачу
        _delete_task(DIRECT_BOOT_TASK_NAME)
        
        # Разрешаем пути и применяем фильтры для XML
        from strategy_menu.apply_filters import apply_all_filters
        resolved_args = _resolve_file_paths(strategy_args, work_dir)
        lists_dir = os.path.join(work_dir, "lists")
        resolved_args = apply_all_filters(resolved_args, lists_dir)
        
        # Создаем XML для задачи с триггером при запуске системы
        xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Zapret Direct Mode - System Startup</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{winws_exe}</Command>
      <Arguments>{' '.join(resolved_args)}</Arguments>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
        
        # Сохраняем XML
        xml_path = os.path.join(work_dir, "zapret_boot_task.xml")
        with open(xml_path, 'w', encoding='utf-16') as f:
            f.write(xml_content)
        
        # Создаем задачу из XML
        create_cmd = [
            get_system_exe("schtasks.exe"),
            "/Create",
            "/TN", DIRECT_BOOT_TASK_NAME,
            "/XML", xml_path,
            "/F"
        ]
        
        result = run_hidden(
            create_cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore"
        )
        
        # Удаляем XML файл
        try:
            os.remove(xml_path)
        except:
            pass
        
        if result.returncode == 0:
            # Сохраняем конфигурацию
            _save_direct_strategy_config(strategy_args, strategy_name, cmd_line)
            
            log(f"Задача {DIRECT_BOOT_TASK_NAME} создана (запуск при загрузке)", "✅ SUCCESS")
            
            # Обновляем статус в реестре
            set_autostart_enabled(True, "direct_boot")
            
            if ui_error_cb:
                ui_error_cb(
                    "✅ Автозапуск настроен!\n\n"
                    "Создана задача планировщика с запуском при загрузке системы.\n"
                    "Это более надежный способ, чем служба Windows."
                )
            return True
        else:
            error_msg = f"Ошибка создания задачи: {result.stderr}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
            
    except Exception as e:
        log(f"Ошибка: {e}", "❌ ERROR")
        if ui_error_cb:
            ui_error_cb(f"Ошибка: {e}")
        return False


def _create_task_with_bat_fallback(
    winws_exe: str,
    args: List[str],
    work_dir: str,
    task_name: str,
    trigger: str,
    ui_error_cb: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Создает задачу через .bat файл когда командная строка слишком длинная
    """
    try:
        from strategy_menu.apply_filters import apply_all_filters
        
        # Создаем .bat файл
        bat_path = os.path.join(work_dir, "zapret_autostart.bat")
        
        # Разрешаем пути
        resolved_args = _resolve_file_paths(args, work_dir)
        
        # ✅ Применяем ВСЕ фильтры в правильном порядке
        lists_dir = os.path.join(work_dir, "lists")
        resolved_args = apply_all_filters(resolved_args, lists_dir)
        
        # Создаем .bat содержимое
        bat_content = f"""@echo off
cd /d "{work_dir}"
"{winws_exe}" {' '.join(resolved_args)}
"""
        
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)
        
        log(f"Создан fallback .bat файл: {bat_path}", "INFO")
        
        # Удаляем старую задачу
        _delete_task(task_name)
        
        # Создаем задачу для .bat файла
        create_cmd = [
            get_system_exe("schtasks.exe"),
            "/Create",
            "/TN", task_name,
            "/TR", f'"{bat_path}"',
            "/SC", trigger,
            "/RU", "SYSTEM",
            "/RL", "HIGHEST",
            "/F"
        ]
        
        log(f"Выполняем команду: {' '.join(create_cmd)}", "DEBUG")
        
        result = run_hidden(
            create_cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore"
        )
        
        log(f"schtasks returncode: {result.returncode}", "DEBUG")
        log(f"schtasks stdout: {result.stdout}", "DEBUG")
        log(f"schtasks stderr: {result.stderr}", "DEBUG")
        
        if result.returncode == 0:
            log(f"Задача {task_name} создана через .bat файл", "✅ SUCCESS")
            # Обновляем статус в реестре
            method = "direct_boot_bat" if "Boot" in task_name else "direct_task_bat"
            set_autostart_enabled(True, method)
            return True
        else:
            error_msg = f"Ошибка создания задачи (код {result.returncode}):\n{result.stderr or result.stdout}"
            log(error_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb(error_msg)
            return False
            
    except Exception as e:
        log(f"Ошибка создания fallback задачи: {e}", "❌ ERROR")
        return False


def remove_direct_autostart() -> bool:
    """
    Удаляет все механизмы автозапуска Direct режима
    """
    removed_any = False
    
    # Удаляем задачи
    if _delete_task(DIRECT_TASK_NAME):
        removed_any = True
    if _delete_task(DIRECT_BOOT_TASK_NAME):
        removed_any = True
    
    # Удаляем службу Direct режима
    from .autostart_direct_service import remove_direct_service
    if remove_direct_service():
        removed_any = True
    
    # Удаляем .bat файлы
    from config import PROGRAMDATA_PATH
    for filename in ["zapret_autostart.bat", "zapret_direct.bat", "zapret_boot_task.xml"]:
        try:
            for base_path in [Path.cwd(), Path(PROGRAMDATA_PATH)]:
                file_path = base_path / filename
                if file_path.exists():
                    file_path.unlink()
                    removed_any = True
                    log(f"Удален файл: {file_path}", "DEBUG")
        except:
            pass
    
    # Удаляем конфигурацию
    if _delete_direct_strategy_config():
        removed_any = True
    
    # Обновляем реестр если что-то удалили
    if removed_any:
        # Проверяем остались ли другие методы автозапуска
        from .checker import CheckerManager
        checker = CheckerManager(None)
        if not checker.check_autostart_exists_full():
            # Если ничего не осталось - отключаем в реестре
            set_autostart_enabled(False)
    
    return removed_any


def check_direct_autostart_exists() -> bool:
    """
    Проверяет наличие автозапуска Direct режима (для полной проверки)
    """
    return _check_task_exists(DIRECT_TASK_NAME) or _check_task_exists(DIRECT_BOOT_TASK_NAME)


# === Вспомогательные функции ===

def collect_direct_strategy_args(app_instance) -> tuple[List[str], str, str]:
    """
    Собирает аргументы для текущей Direct стратегии
    """
    try:
        from strategy_menu import get_direct_strategy_selections
        from strategy_menu.strategy_lists_separated import combine_strategies
        from config import WINWS2_EXE
        
        # Для прямого запуска всегда используем winws2.exe
        if hasattr(app_instance, 'dpi_starter') and hasattr(app_instance.dpi_starter, 'winws_exe'):
            winws_exe = app_instance.dpi_starter.winws_exe
        else:
            winws_exe = WINWS2_EXE  # Zapret 2 для прямого запуска
        
        # Получаем выборы стратегий
        selections = get_direct_strategy_selections()
        
        # Комбинируем стратегии
        combined = combine_strategies(**selections)
        
        # Парсим аргументы (posix=False для Windows чтобы сохранить бэкслеши в путях)
        import shlex
        args = shlex.split(combined['args'], posix=False)
        
        log(f"Собрано {len(args)} аргументов", "INFO")
        
        return args, "Direct", winws_exe
        
    except Exception as e:
        log(f"Ошибка сбора аргументов: {e}", "❌ ERROR")
        return [], "Direct", ""


def _delete_task(task_name: str) -> bool:
    """Удаляет задачу планировщика"""
    try:
        cmd = [get_system_exe("schtasks.exe"), "/Delete", "/TN", task_name, "/F"]
        result = run_hidden(cmd, capture_output=True)
        if result.returncode == 0:
            log(f"Задача {task_name} удалена", "INFO")
            return True
    except:
        pass
    return False


def _check_task_exists(task_name: str) -> bool:
    """Проверяет существование задачи"""
    try:
        cmd = [get_system_exe("schtasks.exe"), "/Query", "/TN", task_name]
        result = run_hidden(cmd, capture_output=True)
        return result.returncode == 0
    except:
        return False


def _save_direct_strategy_config(args: List[str], name: str, cmd_line: str):
    """Сохраняет конфигурацию в реестр"""
    try:
        import winreg
        from config import REGISTRY_PATH_DIRECT
        config = {
            "args": args,
            "name": name,
            "cmd_line": cmd_line
        }
        
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_DIRECT) as key:
            winreg.SetValueEx(key, "Config", 0, winreg.REG_SZ, json.dumps(config))
        
        log("Конфигурация сохранена", "DEBUG")
    except Exception as e:
        log(f"Ошибка сохранения конфигурации: {e}", "⚠ WARNING")


def _delete_direct_strategy_config() -> bool:
    """Удаляет конфигурацию из реестра"""
    try:
        import winreg
        from config import REGISTRY_PATH
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteKey(key, "DirectAutostart")
        log("Конфигурация удалена", "DEBUG")
        return True
    except:
        return False