"""
Модуль для блокировки установки и работы программы MAX
"""

import os
import winreg
import ctypes
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Tuple
from log import log

# Ключ в реестре для хранения настройки
from config import REGISTRY_PATH_GUI
REGISTRY_KEY_MAX_BLOCKED = "MaxBlocked"

# Путь к политикам Explorer для блокировки запуска
EXPLORER_POLICIES_PATH = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
DISALLOW_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\DisallowRun"

# Пути, которые нужно заблокировать
MAX_PATHS = [
    r"%LOCALAPPDATA%\oneme",
    r"%LOCALAPPDATA%\max",
    r"C:\Program Files\max",
]

# Процессы для блокировки
MAX_PROCESSES = [
    "max.exe",
    "MAX.exe",
    "max.msi", 
    "MAX.msi", 
    "max1.exe",
    "MAX1.exe",
    "max1.msi", 
    "MAX1.msi", 
    "maxsetup.exe",
    "max_installer.exe",
    "maxupdater.exe",
    "max_uninstall.exe",
    "oneme.exe",
    "onemesetup.exe",
    "max-service.exe"
]


class MaxBlockerManager:
    """Управление блокировкой программы MAX"""
    
    def __init__(self, status_callback: Optional[Callable] = None):
        self.status_callback = status_callback or (lambda x: None)
        
    def _set_status(self, msg: str):
        """Обновляет статус через callback"""
        self.status_callback(msg)
        log(f"MaxBlocker: {msg}", "INFO")
    
    def is_max_blocked(self) -> bool:
        """Проверяет, включена ли блокировка MAX"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                value, _ = winreg.QueryValueEx(key, REGISTRY_KEY_MAX_BLOCKED)
                return bool(value)
        except (FileNotFoundError, OSError):
            return False
    
    def set_max_blocked(self, blocked: bool) -> bool:
        """Сохраняет состояние блокировки в реестр"""
        try:
            # Создаем ключ если не существует
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI) as key:
                winreg.SetValueEx(key, REGISTRY_KEY_MAX_BLOCKED, 0, winreg.REG_DWORD, int(blocked))
            return True
        except Exception as e:
            log(f"Ошибка записи в реестр: {e}", "❌ ERROR")
            return False
    
    def block_processes_in_registry(self) -> bool:
        """
        Блокирует запуск процессов MAX через политику DisallowRun в реестре
        """
        try:
            # 1. Создаем/открываем ключ политик Explorer
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, EXPLORER_POLICIES_PATH) as explorer_key:
                # Включаем политику DisallowRun
                winreg.SetValueEx(explorer_key, "DisallowRun", 0, winreg.REG_DWORD, 1)
                log("Политика DisallowRun включена", "✅ INFO")
            
            # 2. Создаем подключ DisallowRun для списка заблокированных программ
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, DISALLOW_RUN_PATH) as disallow_key:
                # Получаем текущий список заблокированных программ
                existing_values = {}
                index = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(disallow_key, index)
                        existing_values[value.lower()] = name
                        index += 1
                    except WindowsError:
                        break
                
                # Добавляем наши процессы
                next_index = 1
                for process in MAX_PROCESSES:
                    process_lower = process.lower()
                    
                    # Если процесс уже в списке, пропускаем
                    if process_lower in existing_values:
                        log(f"Процесс {process} уже заблокирован", "ℹ️ INFO")
                        continue
                    
                    # Находим свободный индекс
                    while str(next_index) in existing_values.values():
                        next_index += 1
                    
                    # Добавляем процесс в список
                    winreg.SetValueEx(disallow_key, str(next_index), 0, winreg.REG_SZ, process)
                    log(f"Процесс {process} добавлен в DisallowRun с индексом {next_index}", "✅ INFO")
                    next_index += 1
            
            # 3. Обновляем политики Explorer для немедленного применения
            self._refresh_explorer_policies()
            
            return True
            
        except Exception as e:
            log(f"Ошибка блокировки процессов в реестре: {e}", "❌ ERROR")
            return False
    
    def unblock_processes_in_registry(self) -> bool:
        """
        Удаляет блокировку процессов MAX из реестра
        """
        try:
            # Открываем ключ DisallowRun
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DISALLOW_RUN_PATH, 
                                   0, winreg.KEY_ALL_ACCESS) as disallow_key:
                    
                    # Получаем все значения
                    values_to_delete = []
                    index = 0
                    
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(disallow_key, index)
                            # Проверяем, является ли это одним из наших процессов
                            if value.lower() in [p.lower() for p in MAX_PROCESSES]:
                                values_to_delete.append(name)
                                log(f"Найден процесс MAX для удаления: {value} (ключ: {name})", "🔍 INFO")
                            index += 1
                        except WindowsError:
                            break
                    
                    # Удаляем найденные значения
                    for name in values_to_delete:
                        try:
                            winreg.DeleteValue(disallow_key, name)
                            log(f"Удален ключ блокировки: {name}", "✅ INFO")
                        except:
                            pass
                    
                    # Проверяем, остались ли другие заблокированные программы
                    remaining_count = 0
                    try:
                        index = 0
                        while True:
                            winreg.EnumValue(disallow_key, index)
                            remaining_count += 1
                            index += 1
                    except WindowsError:
                        pass
                    
                    # Если больше нет заблокированных программ, отключаем политику
                    if remaining_count == 0:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, EXPLORER_POLICIES_PATH,
                                           0, winreg.KEY_SET_VALUE) as explorer_key:
                            winreg.SetValueEx(explorer_key, "DisallowRun", 0, winreg.REG_DWORD, 0)
                            log("Политика DisallowRun отключена (нет заблокированных программ)", "✅ INFO")
                        
                        # Удаляем пустой ключ DisallowRun
                        try:
                            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, DISALLOW_RUN_PATH)
                            log("Ключ DisallowRun удален", "✅ INFO")
                        except:
                            pass
                            
            except FileNotFoundError:
                log("Ключ DisallowRun не найден, блокировка уже отключена", "ℹ️ INFO")
                return True
            
            # Обновляем политики Explorer
            self._refresh_explorer_policies()
            
            return True
            
        except Exception as e:
            log(f"Ошибка удаления блокировки процессов из реестра: {e}", "❌ ERROR")
            return False
    
    def _refresh_explorer_policies(self):
        """
        Обновляет политики Explorer для немедленного применения изменений
        """
        try:
            # Способ 1: Через gpupdate
            subprocess.run(['gpupdate', '/force'], capture_output=True, timeout=5)
            
            # Способ 2: Перезапуск Explorer (более агрессивный метод)
            # Закомментировано, так как может быть слишком навязчиво
            # subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe'], capture_output=True)
            # subprocess.run(['start', 'explorer.exe'], shell=True, capture_output=True)
            
            # Способ 3: Отправка сообщения об обновлении политик
            import ctypes
            from ctypes import wintypes
            
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            
            result = ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                ctypes.cast("Policy", ctypes.c_wchar_p),
                2,  # SMTO_ABORTIFHUNG
                5000,
                ctypes.byref(wintypes.DWORD())
            )
            
            log("Политики Explorer обновлены", "✅ INFO")
            
        except Exception as e:
            log(f"Ошибка обновления политик Explorer: {e}", "⚠️ WARNING")
    
    def create_blocking_files(self) -> Tuple[int, int]:
        """
        Создает пустые файлы в местах установки MAX
        Возвращает (успешно_созданных, всего_путей)
        """
        success_count = 0
        paths = []
        
        for path_template in MAX_PATHS:
            # Разворачиваем переменные окружения
            path = os.path.expandvars(path_template)
            paths.append(path)
            
            try:
                # Если путь существует и это папка - удаляем
                if os.path.exists(path):
                    if os.path.isdir(path):
                        try:
                            # Пытаемся удалить папку
                            import shutil
                            shutil.rmtree(path, ignore_errors=True)
                            log(f"Удалена папка MAX: {path}", "🗑️ INFO")
                        except:
                            pass
                    elif os.path.isfile(path):
                        # Если это уже файл-блокировка, пропускаем
                        success_count += 1
                        continue
                
                # Создаем файл-блокировку
                # Создаем родительскую директорию если нужно
                parent_dir = os.path.dirname(path)
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                
                # Создаем пустой файл
                with open(path, 'w') as f:
                    f.write("BLOCKED BY ZAPRET GUI\n")
                
                # Делаем файл только для чтения
                os.chmod(path, 0o444)
                
                success_count += 1
                log(f"Создан блокирующий файл: {path}", "✅ INFO")
                
            except Exception as e:
                log(f"Ошибка создания блокирующего файла {path}: {e}", "⚠️ WARNING")
        
        return success_count, len(paths)
    
    def remove_blocking_files(self) -> Tuple[int, int]:
        """
        Удаляет блокирующие файлы
        Возвращает (успешно_удаленных, всего_путей)
        """
        success_count = 0
        paths = []
        
        for path_template in MAX_PATHS:
            path = os.path.expandvars(path_template)
            paths.append(path)
            
            try:
                if os.path.exists(path) and os.path.isfile(path):
                    # Снимаем атрибут "только чтение"
                    os.chmod(path, 0o666)
                    # Удаляем файл
                    os.remove(path)
                    success_count += 1
                    log(f"Удален блокирующий файл: {path}", "✅ INFO")
                else:
                    # Файла нет - считаем что успешно
                    success_count += 1
                    
            except Exception as e:
                log(f"Ошибка удаления блокирующего файла {path}: {e}", "⚠️ WARNING")
        
        return success_count, len(paths)
    
    def block_max_in_firewall(self) -> bool:
        """
        Добавляет правила Windows Firewall для блокировки MAX
        """
        try:
            # Блокируем исходящие соединения для max.exe
            rules = [
                ('netsh', 'advfirewall', 'firewall', 'add', 'rule', 
                 'name=Block MAX Outbound', 'dir=out', 'program=*max.exe', 
                 'action=block', 'enable=yes'),
                ('netsh', 'advfirewall', 'firewall', 'add', 'rule',
                 'name=Block MAX Inbound', 'dir=in', 'program=*max.exe',
                 'action=block', 'enable=yes'),
            ]
            
            for rule_cmd in rules:
                result = subprocess.run(rule_cmd, capture_output=True, text=True, shell=True, encoding='cp866', errors='replace')
                if result.returncode != 0:
                    log(f"Ошибка добавления правила firewall: {result.stderr}", "⚠️ WARNING")
            
            log("Правила блокировки MAX добавлены в Windows Firewall", "✅ INFO")
            return True
            
        except Exception as e:
            log(f"Ошибка настройки firewall: {e}", "❌ ERROR")
            return False
    
    def unblock_max_in_firewall(self) -> bool:
        """
        Удаляет правила блокировки MAX из Windows Firewall
        """
        try:
            rules = [
                ('netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=Block MAX Outbound'),
                ('netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=Block MAX Inbound'),
            ]
            
            for rule_cmd in rules:
                subprocess.run(rule_cmd, capture_output=True, text=True, shell=True, encoding='cp866', errors='replace')
            
            log("Правила блокировки MAX удалены из Windows Firewall", "✅ INFO")
            return True
            
        except Exception as e:
            log(f"Ошибка удаления правил firewall: {e}", "❌ ERROR")
            return False
    
    def kill_max_processes(self) -> int:
        """
        Завершает все процессы MAX
        Возвращает количество завершенных процессов
        """
        killed_count = 0
        
        for process_name in MAX_PROCESSES:
            try:
                # Используем Win API для завершения процесса
                from utils.process_killer import kill_process_by_name
                killed = kill_process_by_name(process_name, kill_all=True)
                
                if killed > 0:
                    killed_count += killed
                    log(f"Процесс {process_name} завершён через Win API", "🛑 INFO")
                    
            except Exception as e:
                log(f"Ошибка завершения процесса {process_name}: {e}", "⚠️ WARNING")
        
        return killed_count
    
    def add_to_hosts_file(self) -> bool:
        """
        Добавляет блокировку доменов MAX в файл hosts
        """
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        blocked_domains = [
            "max.ru",
            "download.max.ru",
            "update.max.ru",
            "api.max.ru",
            "cdn.max.ru",
            "oneme.com",
            "download.oneme.com",
        ]
        
        try:
            # Читаем текущий hosts файл
            with open(hosts_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # Маркер для наших записей
            marker = "# MAX BLOCKED BY ZAPRET GUI"
            
            # Проверяем, есть ли уже наши записи
            if marker in content:
                return True
            
            # Добавляем блокировки
            new_entries = [f"\n{marker}"]
            for domain in blocked_domains:
                new_entries.append(f"127.0.0.1 {domain}")
                new_entries.append(f"::1 {domain}")
            new_entries.append(f"# END MAX BLOCK\n")
            
            # Записываем обратно
            with open(hosts_path, 'a', encoding='utf-8-sig') as f:
                f.write('\n'.join(new_entries))
            
            log("Домены MAX добавлены в hosts файл", "✅ INFO")
            return True
            
        except Exception as e:
            log(f"Ошибка изменения hosts файла: {e}", "❌ ERROR")
            return False
    
    def remove_from_hosts_file(self) -> bool:
        """
        Удаляет блокировку доменов MAX из файла hosts
        """
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        
        try:
            with open(hosts_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # Фильтруем строки, удаляя наши блокировки
            marker_start = "# MAX BLOCKED BY ZAPRET GUI"
            marker_end = "# END MAX BLOCK"
            
            new_lines = []
            skip = False
            
            for line in lines:
                if marker_start in line:
                    skip = True
                elif marker_end in line:
                    skip = False
                    continue
                elif not skip:
                    new_lines.append(line)
            
            # Записываем обратно
            with open(hosts_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(new_lines)
            
            log("Домены MAX удалены из hosts файла", "✅ INFO")
            return True
            
        except Exception as e:
            log(f"Ошибка изменения hosts файла: {e}", "❌ ERROR")
            return False
    
    def enable_blocking(self) -> Tuple[bool, str]:
        """
        Включает полную блокировку MAX
        Возвращает (успех, сообщение)
        """
        self._set_status("Включение блокировки MAX...")
        
        results = []
        
        # 1. Завершаем процессы MAX
        killed = self.kill_max_processes()
        if killed > 0:
            results.append(f"✅ Завершено процессов: {killed}")
        
        # 2. Блокируем запуск через реестр (ГЛАВНОЕ ИЗМЕНЕНИЕ)
        if self.block_processes_in_registry():
            results.append("✅ Запуск заблокирован через политики Windows")
        else:
            results.append("⚠️ Не удалось заблокировать через реестр")
        
        # 3. Создаем блокирующие файлы
        created, total = self.create_blocking_files()
        results.append(f"✅ Создано блокирующих файлов: {created}/{total}")
        
        # 4. Добавляем правила firewall (если есть права админа)
        if ctypes.windll.shell32.IsUserAnAdmin():
            if self.block_max_in_firewall():
                results.append("✅ Правила firewall добавлены")
            
            # 5. Блокируем в hosts файле
            if self.add_to_hosts_file():
                results.append("✅ Домены заблокированы в hosts")
        else:
            results.append("⚠️ Для полной блокировки требуются права администратора")
        
        # Сохраняем состояние
        self.set_max_blocked(True)
        
        message = "Блокировка MAX включена:\n" + "\n".join(results)
        self._set_status("Блокировка MAX включена")
        
        log("=" * 50, "INFO")
        log("БЛОКИРОВКА MAX АКТИВИРОВАНА", "🛡️ INFO")
        log("Заблокированные процессы:", "INFO")
        for proc in MAX_PROCESSES:
            log(f"  • {proc}", "INFO")
        log("=" * 50, "INFO")
        
        return True, message
    
    def disable_blocking(self) -> Tuple[bool, str]:
        """
        Отключает блокировку MAX
        Возвращает (успех, сообщение)
        """
        self._set_status("Отключение блокировки MAX...")
        
        results = []
        
        # 1. Удаляем блокировку из реестра (ГЛАВНОЕ ИЗМЕНЕНИЕ)
        if self.unblock_processes_in_registry():
            results.append("✅ Блокировка через реестр удалена")
        else:
            results.append("⚠️ Не удалось удалить блокировку из реестра")
        
        # 2. Удаляем блокирующие файлы
        removed, total = self.remove_blocking_files()
        results.append(f"✅ Удалено блокирующих файлов: {removed}/{total}")
        
        # 3. Удаляем правила firewall (если есть права админа)
        if ctypes.windll.shell32.IsUserAnAdmin():
            if self.unblock_max_in_firewall():
                results.append("✅ Правила firewall удалены")
            
            # 4. Удаляем из hosts файла
            if self.remove_from_hosts_file():
                results.append("✅ Домены разблокированы в hosts")
        
        # Сохраняем состояние
        self.set_max_blocked(False)
        
        message = "Блокировка MAX отключена:\n" + "\n".join(results)
        self._set_status("Блокировка MAX отключена")
        
        log("=" * 50, "INFO")
        log("БЛОКИРОВКА MAX ДЕАКТИВИРОВАНА", "✅ INFO")
        log("=" * 50, "INFO")
        
        return True, message


# Глобальные функции для удобства
def is_max_blocked() -> bool:
    """Проверяет, включена ли блокировка MAX"""
    manager = MaxBlockerManager()
    return manager.is_max_blocked()

def set_max_blocked(blocked: bool) -> bool:
    """Устанавливает состояние блокировки MAX"""
    manager = MaxBlockerManager()
    return manager.set_max_blocked(blocked)