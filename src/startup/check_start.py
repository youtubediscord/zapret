#startup/check_start.py
import os
import sys
import winreg

# Импортируем константы из конфига
from app_notifications import advisory_notification, notification_action
from config.config import BIN_FOLDER

from utils.windows_process_probe import iter_process_records_winapi

def check_system_commands() -> tuple[bool, str]:
    """
    Проверяет доступность основных системных компонентов без сохранения старых результатов.
    """
    try:
        from log.log import log

        log("Проверка системных команд", "DEBUG")
    except ImportError:
        print("DEBUG: Проверка системных команд")

    failed_commands = []
    try:
        import psutil
        list(psutil.process_iter(['name']))
    except Exception as e:
        failed_commands.append(f"psutil (ошибка: {e})")
        try:
            from log.log import log

            log(f"ERROR: psutil не работает: {e}", level="❌ ERROR")
        except ImportError:
            print(f"ERROR: psutil не работает: {e}")
    
    system_root = os.environ.get("WINDIR", "")
    system32 = os.path.join(system_root, "System32") if system_root else ""
    required_paths = {
        "sc.exe": os.path.join(system32, "sc.exe") if system32 else "",
        "netsh.exe": os.path.join(system32, "netsh.exe") if system32 else "",
    }

    for cmd_name, command_path in required_paths.items():
        try:
            if not command_path or not os.path.isfile(command_path):
                failed_commands.append(f"{cmd_name} (файл не найден)")
                try:
                    from log.log import log

                    log(f"ERROR: Системный файл {cmd_name} не найден: {command_path}", level="❌ ERROR")
                except ImportError:
                    print(f"ERROR: Системный файл {cmd_name} не найден: {command_path}")
        except Exception as e:
            failed_commands.append(f"{cmd_name} ({e})")
            try:
                from log.log import log

                log(f"ERROR: Ошибка при проверке системного файла {cmd_name}: {e}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Ошибка при проверке системного файла {cmd_name}: {e}")
    
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
            from log.log import log

            log("Все системные команды доступны", level="☑ INFO")
        except ImportError:
            print("INFO: Все системные команды доступны")
    
    return has_issues, error_message
   
def check_mitmproxy() -> tuple[bool, str]:
    """
    Проверяет, запущен ли mitmproxy прямо по текущему списку процессов через WinAPI.
    """
    MITMPROXY_EXECUTABLES = [
        "mitmproxy.exe",
        "mitmdump.exe",
        "mitmweb.exe",
    ]
    mitmproxy_names = {name.lower() for name in MITMPROXY_EXECUTABLES}
    mitmproxy_names |= {os.path.splitext(name)[0] for name in mitmproxy_names}

    try:
        current_pid = os.getpid()
        for pid, process_name in iter_process_records_winapi():
            if int(pid) == int(current_pid):
                continue

            normalized = str(process_name or "").strip().lower()
            if normalized not in mitmproxy_names:
                continue

            err = (
                f"Обнаружен запущенный процесс mitmproxy: {process_name} (PID: {pid})\n\n"
                "mitmproxy использует тот же драйвер WinDivert, что и Zapret.\n"
                "Одновременная работа этих программ невозможна.\n\n"
                "Пожалуйста, завершите все процессы mitmproxy и перезапустите Zapret."
            )
            try:
                from log.log import log

                log(f"ERROR: Найден конфликтующий процесс mitmproxy: {process_name} (PID: {pid})", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Найден конфликтующий процесс mitmproxy: {process_name}")
            return True, err
    except Exception as e:
        try:
            from log.log import log

            log(f"Ошибка WinAPI-проверки процессов mitmproxy: {e}", level="⚠ WARNING")
        except ImportError:
            print(f"WARNING: Ошибка WinAPI-проверки процессов mitmproxy: {e}")
        return False, ""
    
    return False, ""
    
def check_if_in_archive():
    """
    Проверяет, находится ли EXE-файл в временной директории.
    """
    exe_path = os.path.abspath(sys.executable)

    try:
        try:
            from log.log import log

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
                    from log.log import log

                    log(f"EXE запущен из временной директории: {temp_dir}", level="⚠ WARNING")
                except ImportError:
                    print(f"WARNING: EXE запущен из временной директории: {temp_dir}")
                is_in_temp = True
                break
        
        return is_in_temp
        
    except Exception as e:
        try:
            from log.log import log

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
    Проверяет OneDrive в путях без сохранения старого результата.
    """
    current_path = os.path.abspath(os.getcwd())
    exe_path = os.path.abspath(sys.executable)

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
                from log.log import log

                log(f"ERROR: Обнаружен OneDrive в пути: {path}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Обнаружен OneDrive в пути: {path}")
            
            return True, err

    return False, ""

import re
import platform

def check_windows_version() -> tuple[bool, str]:
    """
    Проверяет версию Windows. Если Windows 7 или 8 - возвращает ошибку.
    Windows 7 = 6.1, Windows 8 = 6.2, Windows 8.1 = 6.3
    """
    try:
        from log.log import log

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
      • символ НЕ из списка: буквы/цифры (включая кириллицу), _ . : \\ /
    """
    if " " in path:
        return True            # пробел — сразу ошибка

    # если хотите запретить цифры — раскомментируйте строку ниже
    # if re.search(r"\d", path):
    #     return True

    # проверяем оставшиеся символы
    #  ^ – отрицание; разрешаем Unicode-слова (включая кириллицу) + _ . : \ /
    #  \w в Python включает буквы/цифры/underscore для Unicode.
    return bool(re.search(r"[^\w\.:\\/]", path, flags=re.UNICODE))

def check_path_for_special_chars():
    """Проверяет пути программы на наличие специальных символов."""
    current_path = os.path.abspath(os.getcwd())
    exe_path = os.path.abspath(sys.executable)
    
    paths_to_check = [current_path, exe_path, BIN_FOLDER]
    
    for path in paths_to_check:
        if contains_special_chars(path):
            error_message = (
                f"Путь содержит специальные символы: {path}\n\n"
                "Программа может работать некорректно, если в пути есть пробелы или специальные знаки.\n"
                "Рекомендуется переместить программу в папку (или корень диска) без пробелов/спецсимволов "
                "(например, C:\\zapret или D:\\zapret) и запустить её снова."
            )
            try:
                from log.log import log

                log(f"ERROR: Путь содержит специальные символы: {path}", level="❌ ERROR")
            except ImportError:
                print(f"ERROR: Путь содержит специальные символы: {path}")
            
            return True, error_message

    return False, ""

def collect_startup_notifications() -> list[dict]:
    """Собирает стартовые системные события в одном fluent-формате."""
    notifications: list[dict] = []

    has_old_windows, win_error = check_windows_version()
    if has_old_windows:
        notifications.append(
            advisory_notification(
                level="error",
                title="Неподдерживаемая Windows",
                content=win_error,
                source="startup.windows_version",
                presentation="infobar",
                queue="startup",
                duration=-1,
                dedupe_key="startup.windows_version",
                dedupe_window_ms=0,
            )
        )
        return notifications

    has_cmd_issues, cmd_msg = check_system_commands()
    if has_cmd_issues and cmd_msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=cmd_msg,
                source="startup.system_commands",
                queue="startup",
                duration=15000,
                dedupe_key="startup.system_commands",
            )
        )

    if check_if_in_archive():
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=(
                    "Программа запущена из временной директории.\n\n"
                    "Для корректной работы необходимо распаковать архив в постоянную директорию "
                    "(например, C:\\zapretgui) и запустить программу оттуда.\n\n"
                    "Продолжение работы возможно, но некоторые функции могут работать некорректно."
                ),
                source="startup.archive_path",
                queue="startup",
                duration=15000,
                dedupe_key="startup.archive_path",
            )
        )

    in_onedrive, msg = check_path_for_onedrive()
    if in_onedrive and msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=msg,
                source="startup.onedrive_path",
                queue="startup",
                duration=15000,
                dedupe_key="startup.onedrive_path",
            )
        )

    has_special_chars, error_message = check_path_for_special_chars()
    if has_special_chars and error_message:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=error_message,
                source="startup.special_chars_path",
                queue="startup",
                duration=15000,
                dedupe_key="startup.special_chars_path",
            )
        )

    proxy_notification = build_proxy_notification()
    if proxy_notification is not None:
        notifications.append(proxy_notification)

    return notifications
        
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

def _service_exists_winapi(name: str) -> bool:
    """Проверка службы через WinAPI/pywin32 без shell-команд."""
    try:
        import win32service

        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        try:
            try:
                service = win32service.OpenService(scm, name, win32service.SERVICE_QUERY_STATUS)
            except win32service.error as exc:
                if getattr(exc, "winerror", None) == 1060:
                    return False
                raise
            try:
                return True
            finally:
                win32service.CloseServiceHandle(service)
        finally:
            win32service.CloseServiceHandle(scm)
    except Exception:
        return False

def _stop_and_delete_service(name: str) -> tuple[bool, str]:
    """
    Останавливает и удаляет службу Windows через WinAPI.
    Возвращает (успех, сообщение).
    """
    try:
        from log.log import log

    except ImportError:
        log = lambda msg, **kw: print(msg)

    try:
        import win32service
        import win32serviceutil
    except Exception as exc:
        return False, f"WinAPI для служб недоступен: {exc}"

    try:
        if not _service_exists_winapi(name):
            log(f"Служба {name} уже удалена", level="INFO")
            return True, f"Служба {name} уже была удалена"

        try:
            log(f"Останавливаем службу {name}...", level="INFO")
            win32serviceutil.StopService(name)
        except win32service.error as exc:
            if getattr(exc, "winerror", None) not in (1060, 1062):
                raise

        start_wait = __import__("time").time()
        while _service_exists_winapi(name) and __import__("time").time() - start_wait < 5:
            try:
                scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
                try:
                    service = win32service.OpenService(scm, name, win32service.SERVICE_QUERY_STATUS)
                    try:
                        state = win32service.QueryServiceStatus(service)[1]
                        if state != win32service.SERVICE_STOP_PENDING:
                            break
                    finally:
                        win32service.CloseServiceHandle(service)
                finally:
                    win32service.CloseServiceHandle(scm)
            except Exception:
                break
            __import__("time").sleep(0.5)

        log(f"Удаляем службу {name}...", level="INFO")
        win32serviceutil.RemoveService(name)
        return True, f"Служба {name} успешно удалена"
    except win32service.error as exc:
        if getattr(exc, "winerror", None) == 1060:
            return True, f"Служба {name} уже была удалена"
        log(f"Ошибка удаления службы {name}: {exc}", level="WARNING")
        return False, str(exc)
    except Exception as exc:
        log(f"Ошибка удаления службы {name}: {exc}", level="WARNING")
        return False, str(exc)


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
        from log.log import log

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


def check_proxy_warning() -> tuple[bool, str]:
    """
    Проверяет включён ли ручной прокси Windows, но не меняет настройки.

    Возвращает:
    - (is_enabled, message)
    """
    try:
        from log.log import log

    except ImportError:
        log = lambda msg, **kw: print(msg)

    is_enabled, proxy_server, error = _is_proxy_enabled()

    if error:
        log(f"Ошибка проверки прокси: {error}", level="WARNING")
        return False, ""

    if not is_enabled:
        log("Ручной прокси-сервер не включен", level="DEBUG")
        return False, ""

    proxy_info = f" ({proxy_server})" if proxy_server else ""
    log(f"Обнаружен включенный ручной прокси-сервер{proxy_info}", level="WARNING")
    return True, (
        f"Обнаружен включенный ручной прокси-сервер{proxy_info}.\n\n"
        "Он может мешать работе Zapret.\n"
        "Приложение может предложить отключить его, но по умолчанию настройки прокси "
        "изменяться не будут."
    )


def build_proxy_notification() -> dict | None:
    """Возвращает неблокирующее системное событие о включенном прокси."""
    proxy_enabled, proxy_msg = check_proxy_warning()
    if not proxy_enabled:
        return None

    return advisory_notification(
        level="warning",
        title="Включен системный прокси",
        content=proxy_msg or "",
        source="startup.proxy",
        queue="startup",
        duration=18000,
        dedupe_key="startup.proxy",
        buttons=[
            notification_action("disable_proxy", "Отключить прокси"),
        ],
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
        from log.log import log

    except ImportError:
        log = lambda msg, **kw: print(msg)

    found_services = []
    
    # Сначала находим все существующие службы
    for svc in SERVICE_NAMES:
        exists = _service_exists_reg(svc) or _service_exists_winapi(svc)

        if exists:
            found_services.append(svc)
            log(f"Обнаружена служба GoodbyeDPI: {svc}", level="WARNING")
    
    if not found_services:
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
        exists = _service_exists_reg(svc) or _service_exists_winapi(svc)

        if exists:
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
        
        return True, err
    
    # Все службы успешно удалены
    if success_services:
        log(f"Все службы GoodbyeDPI удалены: {success_services}", level="INFO")
    
    return False, ""
