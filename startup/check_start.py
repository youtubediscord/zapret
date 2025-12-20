#startup/check_start.py
import os
import sys
from PyQt6.QtWidgets import QMessageBox, QApplication
import ctypes, sys, subprocess, winreg

# Импортируем константы из конфига
from config import BIN_FOLDER

# Добавляем импорт кэша
from startup.check_cache import startup_cache
from utils import run_hidden, get_system32_path, get_system_exe
import psutil

def _native_message(title: str, text: str, style=0x00000010):  # MB_ICONERROR
    """
    Показывает нативное окно MessageBox (не требует QApplication)
    style: 0x10 = MB_ICONERROR,  0x30 = MB_ICONWARNING | MB_YESNO
    """
    ctypes.windll.user32.MessageBoxW(0, text, title, style)

def check_system_commands() -> tuple[bool, str]:
    """
    Проверяет доступность основных системных команд с кэшированием.
    """
    # Проверяем кэш (короткое время жизни - 1 час)
    has_cache, cached_result = startup_cache.is_cached_and_valid("system_commands")
    if has_cache:
        return cached_result, ""

    try:
        from log import log
        log("Проверка системных команд", "DEBUG")
    except ImportError:
        print("DEBUG: Проверка системных команд")

    # Определяем команды для проверки с полными путями
    # Используем get_system_exe для корректной работы на любом диске
    # ВАЖНО: tasklist убран - вместо него используем psutil который уже проверен при импорте
    required_commands = [
        ("sc", f'"{get_system_exe("sc.exe")}" query'),
        ("netsh", f'"{get_system_exe("netsh.exe")}" /?'),
    ]

    failed_commands = []

    # Проверяем psutil отдельно (основной инструмент вместо tasklist)
    try:
        import psutil
        # Тестовый вызов psutil
        list(psutil.process_iter(['name']))
    except Exception as e:
        failed_commands.append(f"psutil (ошибка: {e})")
        try:
            from log import log
            log(f"ERROR: psutil не работает: {e}", level="❌ ERROR")
        except ImportError:
            print(f"ERROR: psutil не работает: {e}")
    
    # Определяем параметры для разных систем
    run_params = {
        "shell": True,
        "capture_output": True,
        "text": True,
        "timeout": 10,
        "errors": "ignore"
    }
    
    # Добавляем Windows-специфичные параметры
    if sys.platform == "win32":
        # Определяем кодировку консоли
        try:
            import locale
            console_encoding = locale.getpreferredencoding() or "utf-8"
        except:
            console_encoding = "utf-8"
        
        run_params["encoding"] = console_encoding
        
        # CREATE_NO_WINDOW доступен только на Windows
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            run_params["creationflags"] = subprocess.CREATE_NO_WINDOW
    
    for cmd_name, test_command in required_commands:
        try:
            result = run_hidden(test_command, **run_params)

            # Для разных команд разные допустимые коды возврата
            acceptable_codes = {
                "sc": [0, 1, 2],     # 1,2 = сервис не найден/остановлен
                "netsh": [0, 1]      # 1 = помощь показана
            }
            
            if result.returncode not in acceptable_codes.get(cmd_name, [0, 1]):
                failed_commands.append(f"{cmd_name} (код ошибки: {result.returncode})")
                try:
                    from log import log
                    log(f"WARNING: Команда {cmd_name} вернула код {result.returncode}", level="⚠ WARNING")
                except ImportError:
                    print(f"WARNING: Команда {cmd_name} вернула код {result.returncode}")
                    
        except subprocess.TimeoutExpired:
            failed_commands.append(f"{cmd_name} (превышен таймаут)")
            try:
                from log import log
                log(f"ERROR: Команда {cmd_name} превысила таймаут", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Команда {cmd_name} превысила таймаут")
                
        except FileNotFoundError:
            failed_commands.append(f"{cmd_name} (файл не найден)")
            try:
                from log import log
                log(f"ERROR: Команда {cmd_name} не найдена", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Команда {cmd_name} не найдена")
                
        except Exception as e:
            failed_commands.append(f"{cmd_name} ({str(e)})")
            try:
                from log import log
                log(f"ERROR: Ошибка при проверке команды {cmd_name}: {e}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Ошибка при проверке команды {cmd_name}: {e}")
    
    has_issues = bool(failed_commands)
    
    if has_issues:
        error_message = (
            "Обнаружены проблемы с системными командами:\n\n"
            + "\n".join(f"• {cmd}" for cmd in failed_commands) + 
            "\n\nЭто может быть вызвано:\n"
            "• Блокировкой антивирусом (особенно Касперский)\n"
            "• Политиками безопасности системы\n"
            "• Повреждением системных файлов\n"
            "• Нестандартной конфигурацией Windows\n\n"
            "Рекомендации:\n"
            "1. Добавьте программу в исключения антивируса\n"
            "2. Запустите от имени администратора\n"
            "3. Проверьте целостность файлов: sfc /scannow\n\n"
            "Программа может работать с ограничениями."
        )
    else:
        error_message = ""
        try:
            from log import log
            log("Все системные команды доступны", level="☑ INFO")
        except ImportError:
            print("INFO: Все системные команды доступны")
    
    # Кэшируем результат (короткое время - 1 час)
    startup_cache.cache_result("system_commands", has_issues)
    
    return has_issues, error_message
   
def check_mitmproxy() -> tuple[bool, str]:
    """
    Проверяет, запущен ли mitmproxy с кэшированием (короткое время).
    """
    # Кэш только на 5 минут для процессов
    has_cache, cached_result = startup_cache.is_cached_and_valid("mitmproxy_check")
    if has_cache:
        return cached_result, ""
    
    # Имена исполняемых файлов mitmproxy (точное совпадение)
    MITMPROXY_EXECUTABLES = [
        "mitmproxy.exe",
        "mitmdump.exe", 
        "mitmweb.exe",
    ]
    
    # Получаем PID текущего процесса для исключения
    current_pid = os.getpid()
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.info['pid'] == current_pid:
                    continue
                    
                proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                
                # Точное совпадение имени процесса с mitmproxy
                if proc_name in [exe.lower() for exe in MITMPROXY_EXECUTABLES]:
                    err = (
                        f"Обнаружен запущенный процесс mitmproxy: {proc.info['name']} (PID: {proc.info['pid']})\n\n"
                        "mitmproxy использует тот же драйвер WinDivert, что и Zapret.\n"
                        "Одновременная работа этих программ невозможна.\n\n"
                        "Пожалуйста, завершите все процессы mitmproxy и перезапустите Zapret."
                    )
                    try:
                        from log import log
                        log(f"ERROR: Найден конфликтующий процесс mitmproxy: {proc.info['name']} (PID: {proc.info['pid']})", level="❌ ERROR")
                    except ImportError:
                        print(f"ERROR: Найден конфликтующий процесс mitmproxy: {proc.info['name']}")
                    
                    startup_cache.cache_result("mitmproxy_check", True)
                    return True, err
                
                # Проверка пути исполняемого файла
                proc_exe = proc.info.get('exe', '') or ''
                if proc_exe:
                    exe_basename = os.path.basename(proc_exe).lower()
                    if exe_basename in [exe.lower() for exe in MITMPROXY_EXECUTABLES]:
                        err = (
                            f"Обнаружен запущенный процесс mitmproxy: {proc.info['name']} (PID: {proc.info['pid']})\n\n"
                            "mitmproxy использует тот же драйвер WinDivert, что и Zapret.\n"
                            "Одновременная работа этих программ невозможна.\n\n"
                            "Пожалуйста, завершите все процессы mitmproxy и перезапустите Zapret."
                        )
                        try:
                            from log import log
                            log(f"ERROR: Найден конфликтующий процесс mitmproxy по пути: {proc_exe} (PID: {proc.info['pid']})", level="❌ ERROR")
                        except ImportError:
                            print(f"ERROR: Найден конфликтующий процесс mitmproxy по пути: {proc_exe}")
                        
                        startup_cache.cache_result("mitmproxy_check", True)
                        return True, err
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        try:
            from log import log
            log(f"Ошибка при проверке процессов mitmproxy: {e}", level="⚠ WARNING")
        except ImportError:
            print(f"WARNING: Ошибка при проверке процессов mitmproxy: {e}")
        
        # При ошибке не кэшируем
        return False, ""
    
    # Кэшируем положительный результат (конфликтов не найдено)
    startup_cache.cache_result("mitmproxy_check", False)
    return False, ""
    
def check_if_in_archive():
    """
    Проверяет, находится ли EXE-файл в временной директории с кэшированием.
    """
    exe_path = os.path.abspath(sys.executable)
    
    # Проверяем кэш с контекстом пути
    has_cache, cached_result = startup_cache.is_cached_and_valid("archive_check", exe_path)
    if has_cache:
        return cached_result
    
    try:
        try:
            from log import log
            log(f"Executable path: {exe_path}", level="CHECK_START")
        except ImportError:
            print(f"DEBUG: Executable path: {exe_path}")

        system32_path = os.path.abspath(os.path.join(os.environ.get("WINDIR", ""), "System32"))
        temp_env = os.environ.get("TEMP", "")
        tmp_env = os.environ.get("TMP", "")
        temp_dirs = [temp_env, tmp_env, system32_path]
        
        is_in_temp = False
        for temp_dir in temp_dirs:
            if temp_dir and exe_path.lower().startswith(os.path.abspath(temp_dir).lower()):
                try:
                    from log import log
                    log(f"EXE запущен из временной директории: {temp_dir}", level="⚠ WARNING")
                except ImportError:
                    print(f"WARNING: EXE запущен из временной директории: {temp_dir}")
                is_in_temp = True
                break
        
        # Кэшируем результат
        startup_cache.cache_result("archive_check", is_in_temp, exe_path)
        return is_in_temp
        
    except Exception as e:
        try:
            from log import log
            log(f"Ошибка при проверке расположения EXE: {str(e)}", level="DEBUG")
        except ImportError:
            print(f"DEBUG: Ошибка при проверке расположения EXE: {str(e)}")
        return False

def is_in_onedrive(path: str) -> bool:
    """
    True, если путь находится в каталоге OneDrive
    (учитывается как пользовательский, так и корпоративный вариант).
    """
    path_lower = os.path.abspath(path).lower()

    # 1) Самый надёжный способ – сравнить с переменной окружения ONEDRIVE
    onedrive_env = os.environ.get("ONEDRIVE")
    if onedrive_env and path_lower.startswith(os.path.abspath(onedrive_env).lower()):
        return True

    # 2) Резерв – ищем «onedrive» в любом сегменте пути
    #    (OneDrive, OneDrive - CompanyName и т.п.)
    return any(seg.startswith("onedrive") for seg in path_lower.split(os.sep))

def check_path_for_onedrive() -> tuple[bool, str]:
    """
    Проверяет OneDrive в путях с кэшированием.
    """
    current_path = os.path.abspath(os.getcwd())
    exe_path = os.path.abspath(sys.executable)
    paths_context = f"{current_path}|{exe_path}|{BIN_FOLDER}"
    
    # Проверяем кэш с контекстом всех путей
    has_cache, cached_result = startup_cache.is_cached_and_valid("onedrive_check", paths_context)
    if has_cache:
        return cached_result, ""

    paths_to_check = [current_path, exe_path, BIN_FOLDER]

    for path in paths_to_check:
        if is_in_onedrive(path):
            err = (
                f"Путь содержит каталог OneDrive:\n{path}\n\n"
                "OneDrive часто блокирует доступ к файлам и может вызывать ошибки.\n"
                "Переместите программу в любую локальную папку "
                "(например, C:\\zapret) и запустите её снова."
            )
            try:
                from log import log
                log(f"ERROR: Обнаружен OneDrive в пути: {path}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Обнаружен OneDrive в пути: {path}")
            
            # Кэшируем отрицательный результат
            startup_cache.cache_result("onedrive_check", True, paths_context)
            return True, err
    
    # Кэшируем положительный результат
    startup_cache.cache_result("onedrive_check", False, paths_context)
    return False, ""

import re
import platform

def check_windows_version() -> tuple[bool, str]:
    """
    Проверяет версию Windows. Если Windows 7 или 8 - возвращает ошибку.
    Windows 7 = 6.1, Windows 8 = 6.2, Windows 8.1 = 6.3
    """
    try:
        from log import log
    except ImportError:
        log = lambda msg, **kw: print(msg)
    
    try:
        version = sys.getwindowsversion()
        major = version.major
        minor = version.minor
        
        log(f"Версия Windows: {major}.{minor}", level="DEBUG")
        
        # Windows 7 = 6.1, Windows 8 = 6.2, Windows 8.1 = 6.3
        if major == 6 and minor in (1, 2, 3):
            if minor == 1:
                os_name = "Windows 7"
            elif minor == 2:
                os_name = "Windows 8"
            else:
                os_name = "Windows 8.1"
            
            error_message = (
                f"Обнаружена устаревшая версия Windows: {os_name}\n\n"
                "Данная GUI-версия программы не поддерживает Windows 7/8/8.1.\n\n"
                "Для вашей операционной системы доступна консольная версия:\n"
                "https://t.me/bypassblock/666\n\n"
                "Рекомендуем обновить Windows до версии 10 или 11 для использования GUI-версии."
            )
            
            log(f"ERROR: Неподдерживаемая версия Windows: {os_name}", level="❌ ERROR")
            return True, error_message
        
        # Windows XP/Vista (major < 6) тоже не поддерживаются
        if major < 6:
            error_message = (
                "Обнаружена неподдерживаемая версия Windows.\n\n"
                "Данная GUI-версия программы требует Windows 10 или новее.\n\n"
                "Для старых версий Windows доступна консольная версия:\n"
                "https://t.me/bypassblock/666"
            )
            
            log(f"ERROR: Неподдерживаемая версия Windows: {major}.{minor}", level="❌ ERROR")
            return True, error_message
        
        return False, ""
        
    except Exception as e:
        log(f"Ошибка определения версии Windows: {e}", level="WARNING")
        return False, ""


def contains_special_chars(path: str) -> bool:
    """
    True, если путь содержит:
      • пробел
      • (опционально) цифру
      • символ НЕ из списка  A-Z a-z 0-9 _ . : \\ /
    """
    if " " in path:
        return True            # пробел — сразу ошибка

    # если хотите запретить цифры — раскомментируйте строку ниже
    # if re.search(r"\d", path):
    #     return True

    # проверяем оставшиеся символы
    #  ^ – отрицание; разрешаем  A-Z a-z 0-9 _ . : \ /
    return bool(re.search(r"[^A-Za-z0-9_\.:\\/]", path))

def check_path_for_special_chars():
    """Проверяет пути программы на наличие специальных символов с кэшированием"""
    current_path = os.path.abspath(os.getcwd())
    exe_path = os.path.abspath(sys.executable)
    paths_context = f"{current_path}|{exe_path}|{BIN_FOLDER}"
    
    paths_to_check = [current_path, exe_path, BIN_FOLDER]
    
    for path in paths_to_check:
        if contains_special_chars(path):
            error_message = (
                f"Путь содержит специальные символы: {path}\n\n"
                "Программа не может корректно работать в папке со специальными символами (РФ символы (недопустимы символы от А до Я!), пробелы, цифры, точки, скобки, запятые и т.д.).\n"
                "Пожалуйста, переместите программу в папку (или корень диска) без специальных символов в пути (например, по пути C:\\zapret или D:\\zapret) и запустите её снова."
            )
            try:
                from log import log
                log(f"ERROR: Путь содержит специальные символы: {path}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Путь содержит специальные символы: {path}")
            
            # Кэшируем отрицательный результат
            startup_cache.cache_result("special_chars", True, paths_context)
            return True, error_message
    
    # Кэшируем положительный результат
    startup_cache.cache_result("special_chars", False, paths_context)
    return False, ""

def display_startup_warnings():
    """
    Выполняет НЕКРИТИЧЕСКИЕ проверки запуска и отображает предупреждения
    
    Возвращает:
    - bool: True если запуск можно продолжать, False если запуск следует прервать
    """

    from log import log
    try:
        # ❌ КРИТИЧЕСКАЯ ПРОВЕРКА: версия Windows
        has_old_windows, win_error = check_windows_version()
        if has_old_windows:
            app_exists = QApplication.instance() is not None
            if app_exists:
                try:
                    QMessageBox.critical(None, "Ошибка", win_error)
                except Exception:
                    _native_message("Ошибка", win_error, 0x10)  # MB_ICONERROR
            else:
                _native_message("Ошибка", win_error, 0x10)
            return False  # Не продолжаем запуск
        
        warnings = []
        
        # ✅ ТОЛЬКО НЕКРИТИЧЕСКИЕ ПРОВЕРКИ
        has_cmd_issues, cmd_msg = check_system_commands()
        if has_cmd_issues and cmd_msg:
            warnings.append(cmd_msg)
        
        if check_if_in_archive():
            error_message = (
                "Программа запущена из временной директории.\n\n"
                "Для корректной работы необходимо распаковать архив в постоянную директорию "
                "(например, C:\\zapretgui) и запустить программу оттуда.\n\n"
                "Продолжение работы возможно, но некоторые функции могут работать некорректно."
            )
            warnings.append(error_message)

        in_onedrive, msg = check_path_for_onedrive()
        if in_onedrive:
            warnings.append(msg)
                
        has_special_chars, error_message = check_path_for_special_chars()
        if has_special_chars:
            warnings.append(error_message)
        
        # Проверяем и отключаем прокси-сервер
        proxy_was_disabled, proxy_msg = check_and_disable_proxy()
        if proxy_was_disabled and proxy_msg:
            warnings.append(proxy_msg)
        
        # Если есть предупреждения - показываем
        if warnings:
            full_message = "\n\n".join(warnings) + "\n\nПродолжить работу?"
            
            app_exists = QApplication.instance() is not None
            
            if app_exists:
                try:
                    result = QMessageBox.warning(
                        None, "Предупреждение",
                        full_message,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    return result == QMessageBox.StandardButton.Yes
                except Exception as e:
                    log(f"Ошибка показа предупреждения: {e}", level="❌ ERROR")
                    btn = _native_message("Предупреждение",
                                        full_message,
                                        0x34)  # MB_ICONWARNING | MB_YESNO
                    return btn == 6  # IDYES
            else:
                btn = _native_message("Предупреждение", full_message, 0x34)
                return btn == 6
        
        return True
        
    except Exception as e:
        error_msg = f"Ошибка при проверке условий запуска: {str(e)}"
        log(error_msg, level="❌ CRITICAL")
        return False
        
def _service_exists_reg(name: str) -> bool:
    """
    Проверка через реестр: быстрее и не зависит от локали.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            fr"SYSTEM\CurrentControlSet\Services\{name}",
        )
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False

def _service_exists_sc(name: str) -> bool:
    """
    Проверка через `sc query`.  Работает без прав администратора.
    """
    exe = get_system_exe("sc.exe")
    proc = run_hidden(
        [exe, "query", name],
        capture_output=True,
        text=True,
        encoding="cp866",   # вывод консоли cmd.exe
        errors="ignore",
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    if proc.returncode == 0:          # служба есть
        return True
    if proc.returncode == 1060:       # службы нет
        return False
    # Неопределённое состояние, но вывод всё-таки посмотрим:
    return "STATE" in proc.stdout.upper()

def _stop_and_delete_service(name: str) -> tuple[bool, str]:
    """
    Останавливает и удаляет службу Windows.
    Возвращает (успех, сообщение).
    """
    sc_exe = get_system_exe("sc.exe")
    errors = []
    
    try:
        from log import log
    except ImportError:
        log = lambda msg, **kw: print(msg)
    
    # 1. Останавливаем службу
    try:
        log(f"Останавливаем службу {name}...", level="INFO")
        proc = run_hidden(
            [sc_exe, "stop", name],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30
        )
        if proc.returncode == 0:
            log(f"Служба {name} остановлена", level="INFO")
        elif proc.returncode == 1062:  # служба не запущена
            log(f"Служба {name} уже остановлена", level="INFO")
        else:
            log(f"Код возврата sc stop: {proc.returncode}", level="DEBUG")
    except Exception as e:
        errors.append(f"Ошибка остановки: {e}")
        log(f"Ошибка остановки службы {name}: {e}", level="WARNING")
    
    # Небольшая пауза
    import time
    time.sleep(0.5)
    
    # 2. Удаляем службу
    try:
        log(f"Удаляем службу {name}...", level="INFO")
        proc = run_hidden(
            [sc_exe, "delete", name],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30
        )
        if proc.returncode == 0:
            log(f"Служба {name} удалена", level="INFO")
            return True, f"Служба {name} успешно удалена"
        elif proc.returncode == 1060:  # служба не существует
            log(f"Служба {name} уже удалена", level="INFO")
            return True, f"Служба {name} уже была удалена"
        else:
            errors.append(f"Код возврата sc delete: {proc.returncode}")
            log(f"Код возврата sc delete: {proc.returncode}, stderr: {proc.stderr}", level="WARNING")
    except Exception as e:
        errors.append(f"Ошибка удаления: {e}")
        log(f"Ошибка удаления службы {name}: {e}", level="WARNING")
    
    if errors:
        return False, "; ".join(errors)
    return True, "OK"


def _is_proxy_enabled() -> tuple[bool, str, str]:
    """
    Проверяет, включен ли ручной прокси-сервер в Windows.
    
    Возвращает:
    - (is_enabled, proxy_server, error_message)
    """
    INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS_KEY, 0, winreg.KEY_READ)
        try:
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            
            # Получаем адрес прокси, если есть
            try:
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                proxy_server = ""
            
            winreg.CloseKey(key)
            return bool(proxy_enable), proxy_server, ""
            
        except FileNotFoundError:
            # Ключ ProxyEnable не найден - значит прокси выключен
            winreg.CloseKey(key)
            return False, "", ""
            
    except Exception as e:
        return False, "", f"Ошибка чтения реестра: {e}"


def _disable_proxy() -> tuple[bool, str]:
    """
    Отключает ручной прокси-сервер в Windows.
    
    Возвращает:
    - (success, error_message)
    """
    INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    
    # Константы для InternetSetOption
    INTERNET_OPTION_SETTINGS_CHANGED = 39
    INTERNET_OPTION_REFRESH = 37
    
    try:
        from log import log
    except ImportError:
        log = lambda msg, **kw: print(msg)
    
    try:
        # Открываем ключ для записи
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            INTERNET_SETTINGS_KEY, 
            0, 
            winreg.KEY_SET_VALUE
        )
        
        # Устанавливаем ProxyEnable = 0
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        
        log("Прокси-сервер отключен в реестре", level="INFO")
        
        # Уведомляем систему об изменении настроек
        try:
            wininet = ctypes.windll.wininet
            # InternetSetOptionW(NULL, INTERNET_OPTION_SETTINGS_CHANGED, NULL, 0)
            wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
            # InternetSetOptionW(NULL, INTERNET_OPTION_REFRESH, NULL, 0)
            wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
            log("Система уведомлена об изменении настроек прокси", level="DEBUG")
        except Exception as e:
            log(f"Предупреждение: не удалось уведомить систему об изменениях: {e}", level="WARNING")
            # Не критично - изменения в реестре уже сделаны
        
        return True, ""
        
    except PermissionError:
        return False, "Нет прав для изменения настроек прокси"
    except Exception as e:
        return False, f"Ошибка отключения прокси: {e}"


def check_and_disable_proxy() -> tuple[bool, str]:
    """
    Проверяет и отключает ручной прокси-сервер Windows.
    
    Прокси-сервер (Настройки → Сеть и Интернет → Прокси-сервер → "Использовать прокси-сервер")
    может конфликтовать с работой Zapret.
    
    Возвращает:
    - (was_enabled_and_disabled, message)
    - was_enabled_and_disabled = True если прокси был включен и мы его отключили
    """
    try:
        from log import log
    except ImportError:
        log = lambda msg, **kw: print(msg)
    
    # Проверяем, включен ли прокси
    is_enabled, proxy_server, error = _is_proxy_enabled()
    
    if error:
        log(f"Ошибка проверки прокси: {error}", level="WARNING")
        return False, ""
    
    if not is_enabled:
        log("Ручной прокси-сервер не включен", level="DEBUG")
        return False, ""
    
    # Прокси включен - логируем и отключаем
    proxy_info = f" ({proxy_server})" if proxy_server else ""
    log(f"Обнаружен включенный ручной прокси-сервер{proxy_info}", level="WARNING")
    
    # Пытаемся отключить
    success, disable_error = _disable_proxy()
    
    if success:
        log(f"Ручной прокси-сервер{proxy_info} автоматически отключен", level="INFO")
        
        # Проверяем, действительно ли отключился
        is_still_enabled, _, _ = _is_proxy_enabled()
        if is_still_enabled:
            log("Предупреждение: прокси всё ещё включен после попытки отключения", level="WARNING")
            return True, (
                f"Обнаружен включенный прокси-сервер{proxy_info}.\n\n"
                "Попытка автоматического отключения не удалась.\n"
                "Пожалуйста, отключите его вручную:\n"
                "Настройки → Сеть и Интернет → Прокси-сервер → "
                "\"Использовать прокси-сервер\" → Выкл"
            )
        
        return True, (
            f"Был включен ручной прокси-сервер{proxy_info}.\n"
            "Прокси автоматически отключен для корректной работы Zapret."
        )
    else:
        log(f"Не удалось отключить прокси: {disable_error}", level="ERROR")
        return True, (
            f"Обнаружен включенный прокси-сервер{proxy_info}.\n\n"
            f"Автоматическое отключение не удалось: {disable_error}\n\n"
            "Пожалуйста, отключите прокси вручную:\n"
            "Настройки → Сеть и Интернет → Прокси-сервер → "
            "\"Использовать прокси-сервер\" → Выкл"
        )


def check_goodbyedpi() -> tuple[bool, str]:
    """
    Проверяет службы GoodbyeDPI и автоматически удаляет их.
    """
    
    SERVICE_NAMES = [
        "GoodbyeDPI",
        "GoodbyeDPI Service", 
        "GoodbyeDPI_x64",
        "GoodbyeDPI_x86",
    ]
    
    try:
        from log import log
    except ImportError:
        log = lambda msg, **kw: print(msg)

    found_services = []
    
    # Сначала находим все существующие службы
    for svc in SERVICE_NAMES:
        if _service_exists_reg(svc) or _service_exists_sc(svc):
            found_services.append(svc)
            log(f"Обнаружена служба GoodbyeDPI: {svc}", level="WARNING")
    
    if not found_services:
        # Кэшируем положительный результат
        startup_cache.cache_result("goodbyedpi_check", False)
        return False, ""
    
    # Пытаемся автоматически удалить найденные службы
    log(f"Автоматическое удаление служб GoodbyeDPI: {found_services}", level="INFO")
    
    failed_services = []
    success_services = []
    
    for svc in found_services:
        success, msg = _stop_and_delete_service(svc)
        if success:
            success_services.append(svc)
            log(f"Служба {svc}: {msg}", level="INFO")
        else:
            failed_services.append((svc, msg))
            log(f"Не удалось удалить службу {svc}: {msg}", level="ERROR")
    
    # Проверяем, остались ли службы после удаления
    still_exists = []
    for svc in found_services:
        if _service_exists_reg(svc) or _service_exists_sc(svc):
            still_exists.append(svc)
    
    if still_exists:
        # Не все службы удалены - возвращаем ошибку
        err = (
            f"Обнаружены службы GoodbyeDPI: {', '.join(still_exists)}\n\n"
            "Автоматическое удаление не удалось.\n"
            "Zapret 2 GUI несовместим с GoodbyeDPI.\n\n"
            "Удалите службы вручную командами (от администратора):\n"
        )
        for svc in still_exists:
            err += f"    sc stop {svc}\n    sc delete {svc}\n"
        err += "\nЗатем перезагрузите ПК и запустите программу снова."
        
        startup_cache.cache_result("goodbyedpi_check", True)
        return True, err
    
    # Все службы успешно удалены
    if success_services:
        log(f"Все службы GoodbyeDPI удалены: {success_services}", level="INFO")
    
    # Сбрасываем кэш так как состояние изменилось
    startup_cache.cache_result("goodbyedpi_check", False)
    return False, ""