import ctypes
import stat
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from .proxy_domains import PROXY_DOMAINS
from .adobe_domains import ADOBE_DOMAINS
from log import log

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")


def _run_cmd(args, description):
    """Выполняет команду и логирует результат"""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            log(f"✅ {description}: успешно")
            return True
        else:
            # Проверяем stderr или stdout на наличие ошибки
            error = result.stderr.strip() or result.stdout.strip()
            log(f"⚠ {description}: {error}", "⚠ WARNING")
            return False
    except Exception as e:
        log(f"❌ {description}: {e}", "❌ ERROR")
        return False


def _get_current_username():
    """Получает имя текущего пользователя"""
    try:
        import getpass
        return getpass.getuser()
    except:
        return None


def restore_hosts_permissions():
    """
    Агрессивно восстанавливает права доступа к файлу hosts.
    Использует множество методов для обхода блокировок антивирусов.

    Returns:
        tuple: (success: bool, message: str)
    """
    hosts_path = str(HOSTS_PATH)

    log("🔧 Начинаем АГРЕССИВНОЕ восстановление прав доступа к файлу hosts...")

    # Well-known SIDs (работают на любой локализации Windows)
    # S-1-5-32-544 = Administrators / Администраторы
    # S-1-5-32-545 = Users / Пользователи
    # S-1-5-18 = SYSTEM
    # S-1-1-0 = Everyone / Все
    SID_ADMINISTRATORS = "*S-1-5-32-544"
    SID_USERS = "*S-1-5-32-545"
    SID_SYSTEM = "*S-1-5-18"
    SID_EVERYONE = "*S-1-1-0"

    current_user = _get_current_username()

    try:
        # ========== ЭТАП 1: Снимаем атрибуты файла ==========
        log("Этап 1: Снимаем системные атрибуты файла...")
        _run_cmd(['attrib', '-R', '-S', '-H', hosts_path], "attrib -R -S -H")

        # ========== ЭТАП 2: Забираем владение файлом ==========
        log("Этап 2: Забираем владение файлом...")

        # Способ 1: takeown для администраторов
        _run_cmd(['takeown', '/F', hosts_path, '/A'], "takeown /A (для группы администраторов)")

        # Способ 2: takeown для текущего пользователя
        if current_user:
            _run_cmd(['takeown', '/F', hosts_path], "takeown (для текущего пользователя)")

        # ========== ЭТАП 3: Сбрасываем ACL ==========
        log("Этап 3: Сбрасываем ACL...")
        _run_cmd(['icacls', hosts_path, '/reset'], "icacls /reset")

        # ========== ЭТАП 4: Выдаём права через SID (работает на любой локализации) ==========
        log("Этап 4: Выдаём права через SID...")

        # Полный доступ для Administrators через SID
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_ADMINISTRATORS}:F'],
                 "icacls /grant Administrators (SID)")

        # Полный доступ для SYSTEM через SID
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_SYSTEM}:F'],
                 "icacls /grant SYSTEM (SID)")

        # Чтение для Users через SID
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_USERS}:R'],
                 "icacls /grant Users (SID)")

        # Полный доступ для Everyone через SID (агрессивно!)
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_EVERYONE}:F'],
                 "icacls /grant Everyone (SID)")

        # ========== ЭТАП 5: Пробуем с английскими именами (для английской Windows) ==========
        log("Этап 5: Пробуем с английскими именами групп...")
        _run_cmd(['icacls', hosts_path, '/grant', 'Administrators:F'], "icacls Administrators:F")
        _run_cmd(['icacls', hosts_path, '/grant', 'SYSTEM:F'], "icacls SYSTEM:F")
        _run_cmd(['icacls', hosts_path, '/grant', 'Users:R'], "icacls Users:R")
        _run_cmd(['icacls', hosts_path, '/grant', 'Everyone:F'], "icacls Everyone:F")

        # ========== ЭТАП 6: Пробуем с русскими именами (для русской Windows) ==========
        log("Этап 6: Пробуем с русскими именами групп...")
        _run_cmd(['icacls', hosts_path, '/grant', 'Администраторы:F'], "icacls Администраторы:F")
        _run_cmd(['icacls', hosts_path, '/grant', 'Пользователи:R'], "icacls Пользователи:R")
        _run_cmd(['icacls', hosts_path, '/grant', 'Все:F'], "icacls Все:F")

        # ========== ЭТАП 7: Права для текущего пользователя ==========
        if current_user:
            log(f"Этап 7: Выдаём права текущему пользователю ({current_user})...")
            _run_cmd(['icacls', hosts_path, '/grant', f'{current_user}:F'],
                     f"icacls /grant {current_user}:F")

        # ========== ЭТАП 8: PowerShell для обхода некоторых блокировок ==========
        log("Этап 8: Пробуем через PowerShell...")
        ps_script = f'''
$acl = Get-Acl "{hosts_path}"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone","FullControl","Allow")
$acl.SetAccessRule($rule)
Set-Acl "{hosts_path}" $acl
'''
        _run_cmd(['powershell', '-Command', ps_script], "PowerShell Set-Acl")

        # ========== ЭТАП 9: Наследование от родительской папки ==========
        log("Этап 9: Включаем наследование прав от родительской папки...")
        _run_cmd(['icacls', hosts_path, '/inheritance:e'], "icacls /inheritance:e")

        # ========== ЭТАП 10: Финальная проверка ==========
        log("Этап 10: Проверяем результат...")

        # Пробуем прочитать файл
        try:
            content = HOSTS_PATH.read_text(encoding='utf-8')
            log("✅ Права восстановлены! Файл hosts доступен для ЧТЕНИЯ")

            # Пробуем записать (проверка прав на запись)
            try:
                with HOSTS_PATH.open('a', encoding='utf-8') as f:
                    pass  # Просто открываем на запись
                log("✅ Файл hosts доступен для ЗАПИСИ")
                return True, "Права доступа к файлу hosts успешно восстановлены"
            except PermissionError:
                log("⚠ Файл доступен для чтения, но НЕ для записи", "⚠ WARNING")
                return True, "Файл hosts доступен для чтения. Запись может быть заблокирована антивирусом."

        except PermissionError:
            log("❌ После всех попыток файл все еще недоступен", "❌ ERROR")

            # Последняя попытка - копирование через temp
            log("Этап 11: Последняя попытка - копирование через временный файл...")
            success = _try_copy_workaround(hosts_path)
            if success:
                return True, "Права восстановлены через копирование"

            return False, "Не удалось восстановить права. Возможно, антивирус блокирует доступ. Попробуйте:\n1. Временно отключить антивирус\n2. Добавить исключение для файла hosts\n3. Запустить программу от имени администратора"

        except Exception as e:
            log(f"Ошибка при проверке: {e}", "❌ ERROR")
            return False, f"Ошибка при проверке прав: {e}"

    except FileNotFoundError as e:
        log(f"Команда не найдена: {e}", "❌ ERROR")
        return False, f"Системная команда не найдена: {e}"
    except Exception as e:
        log(f"Ошибка при восстановлении прав: {e}", "❌ ERROR")
        return False, f"Ошибка: {e}"


def _try_copy_workaround(hosts_path):
    """
    Последняя попытка - копируем hosts через временный файл.
    Иногда помогает обойти блокировку антивируса.
    """
    import tempfile
    import shutil

    try:
        # Создаём временный файл
        temp_dir = tempfile.gettempdir()
        temp_hosts = os.path.join(temp_dir, "hosts_temp_copy")

        # Копируем hosts во временный файл через cmd (обход блокировок)
        result = subprocess.run(
            ['cmd', '/c', 'copy', '/Y', hosts_path, temp_hosts],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode == 0:
            log("✅ Hosts скопирован во временный файл")

            # Удаляем оригинал
            subprocess.run(
                ['cmd', '/c', 'del', '/F', '/Q', hosts_path],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Копируем обратно
            result = subprocess.run(
                ['cmd', '/c', 'copy', '/Y', temp_hosts, hosts_path],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                log("✅ Hosts восстановлен из временного файла")

                # Удаляем временный файл
                try:
                    os.remove(temp_hosts)
                except:
                    pass

                # Проверяем доступ
                try:
                    HOSTS_PATH.read_text(encoding='utf-8')
                    return True
                except:
                    return False

        return False

    except Exception as e:
        log(f"Ошибка при копировании через temp: {e}", "❌ ERROR")
        return False

def check_hosts_file_name():
    """Проверяет правильность написания имени файла hosts"""
    hosts_dir = Path(r"C:\Windows\System32\drivers\etc")
    
    # ✅ НОВОЕ: Создаем директорию если её нет
    if not hosts_dir.exists():
        try:
            hosts_dir.mkdir(parents=True, exist_ok=True)
            log(f"Создана директория: {hosts_dir}")
        except Exception as e:
            log(f"Не удалось создать директорию: {e}", "❌ ERROR")
            return False, f"Не удалось создать директорию etc: {e}"
    
    # Сначала проверяем правильный файл hosts
    hosts_lower = hosts_dir / "hosts"
    if hosts_lower.exists():
        # Дополнительно проверяем кодировку файла
        try:
            hosts_lower.read_text(encoding="utf-8-sig")
            return True, None
        except UnicodeDecodeError:
            # Файл существует, но с проблемами кодировки
            log("Файл hosts существует, но содержит некорректные символы", level="⚠ WARNING")
            return False, "Файл hosts содержит некорректные символы и не может быть прочитан в UTF-8"
    
    # Если правильного файла нет, проверяем есть ли неправильный HOSTS
    hosts_upper = hosts_dir / "HOSTS"
    if hosts_upper.exists():
        log("Обнаружен файл HOSTS (с большими буквами) - это неправильно!", level="⚠ WARNING")
        return False, "Файл должен называться 'hosts' (с маленькими буквами), а не 'HOSTS'"
    
    # ✅ НОВОЕ: Если файла нет вообще - это нормально, мы его создадим
    return True, None  # Изменено с False на True

def is_file_readonly(filepath):
    """Проверяет, установлен ли атрибут 'только для чтения' у файла"""
    try:
        file_stat = os.stat(filepath)
        return not (file_stat.st_mode & stat.S_IWRITE)
    except Exception as e:
        log(f"Ошибка при проверке атрибутов файла: {e}")
        return False

def remove_readonly_attribute(filepath):
    """Снимает атрибут 'только для чтения' с файла"""
    try:
        # Получаем текущие атрибуты файла
        file_stat = os.stat(filepath)
        # Добавляем право на запись
        os.chmod(filepath, file_stat.st_mode | stat.S_IWRITE)
        log(f"Атрибут 'только для чтения' снят с файла: {filepath}")
        return True
    except Exception as e:
        log(f"Ошибка при снятии атрибута 'только для чтения': {e}")
        return False

def safe_read_hosts_file():
    """Безопасно читает файл hosts с обработкой различных кодировок"""
    hosts_path = HOSTS_PATH
    
    # ✅ НОВОЕ: Проверяем существование файла
    if not hosts_path.exists():
        log(f"Файл hosts не существует, создаем новый: {hosts_path}")
        try:
            # Создаем директорию если её нет
            hosts_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Создаем пустой файл hosts с базовым содержимым
            default_content = """# Copyright (c) 1993-2009 Microsoft Corp.
#
# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.
#
# This file contains the mappings of IP addresses to host names. Each
# entry should be kept on an individual line. The IP address should
# be placed in the first column followed by the corresponding host name.
# The IP address and the host name should be separated by at least one
# space.
#
# Additionally, comments (such as these) may be inserted on individual
# lines or following the machine name denoted by a '#' symbol.
#
# For example:
#
#      102.54.94.97     rhino.acme.com          # source server
#       38.25.63.10     x.acme.com              # x client host

# localhost name resolution is handled within DNS itself.
#	127.0.0.1       localhost
#	::1             localhost
"""
            hosts_path.write_text(default_content, encoding='utf-8-sig')
            log("Файл hosts успешно создан с базовым содержимым")
            return default_content
            
        except Exception as e:
            log(f"Ошибка при создании файла hosts: {e}", "❌ ERROR")
            return None
    
    # Если файл существует, пробуем прочитать с разными кодировками
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'cp866', 'latin1']

    permission_error_occurred = False

    for encoding in encodings:
        try:
            content = hosts_path.read_text(encoding=encoding)
            log(f"Файл hosts успешно прочитан с кодировкой: {encoding}")
            return content
        except UnicodeDecodeError:
            continue
        except PermissionError as e:
            log(f"Ошибка при чтении файла hosts с кодировкой {encoding}: {e}")
            permission_error_occurred = True
            continue
        except Exception as e:
            log(f"Ошибка при чтении файла hosts с кодировкой {encoding}: {e}")
            continue

    # Если была ошибка доступа, пробуем восстановить права
    if permission_error_occurred:
        log("🔧 Обнаружена проблема с правами доступа, пытаемся восстановить...")
        success, message = restore_hosts_permissions()
        if success:
            # Пробуем прочитать снова после восстановления прав
            for encoding in encodings:
                try:
                    content = hosts_path.read_text(encoding=encoding)
                    log(f"Файл hosts успешно прочитан после восстановления прав с кодировкой: {encoding}")
                    return content
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    log(f"Ошибка при повторном чтении с кодировкой {encoding}: {e}")
                    continue
        else:
            log(f"Не удалось восстановить права: {message}", "❌ ERROR")

    # Если ни одна кодировка не подошла, пробуем с игнорированием ошибок
    try:
        content = hosts_path.read_text(encoding='utf-8', errors='ignore')
        log("Файл hosts прочитан с игнорированием ошибок кодировки", level="⚠ WARNING")
        return content
    except Exception as e:
        log(f"Критическая ошибка при чтении файла hosts: {e}", "❌ ERROR")
        return None

def safe_write_hosts_file(content):
    """Безопасно записывает файл hosts с правильной кодировкой"""
    try:
        # Проверяем атрибут "только для чтения" перед записью
        if is_file_readonly(HOSTS_PATH):
            log("Файл hosts имеет атрибут 'только для чтения', пытаемся снять...")
            if not remove_readonly_attribute(HOSTS_PATH):
                log("Не удалось снять атрибут 'только для чтения'")
                return False

        HOSTS_PATH.write_text(content, encoding="utf-8-sig", newline='\n')
        return True
    except PermissionError:
        log("Ошибка доступа при записи файла hosts, пытаемся восстановить права...")
        # Пробуем восстановить права и записать снова
        success, message = restore_hosts_permissions()
        if success:
            try:
                HOSTS_PATH.write_text(content, encoding="utf-8-sig", newline='\n')
                log("✅ Файл hosts успешно записан после восстановления прав")
                return True
            except Exception as e:
                log(f"Ошибка при повторной записи после восстановления прав: {e}", "❌ ERROR")
                return False
        else:
            log(f"Не удалось восстановить права: {message}", "❌ ERROR")
            return False
    except Exception as e:
        log(f"Ошибка при записи файла hosts: {e}")
        return False
    
class HostsManager:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        # 🆕 При инициализации проверяем и удаляем api.github.com
        self.check_and_remove_github_api()

    def restore_permissions(self):
        """Восстанавливает права доступа к файлу hosts"""
        success, message = restore_hosts_permissions()
        self.set_status(message)
        return success

    # 🆕 НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С api.github.com
    def check_github_api_in_hosts(self):
        """Проверяет, есть ли запись api.github.com в hosts файле"""
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
                
            lines = content.splitlines()
            
            for line in lines:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                    
                # Разбиваем строку на части (IP домен)
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]  # Второй элемент - это домен
                    if domain.lower() == "api.github.com":
                        return True
                        
            return False
        except Exception as e:
            log(f"Ошибка при проверке api.github.com в hosts: {e}")
            return False

    def remove_github_api_from_hosts(self):
        """Принудительно удаляет запись api.github.com из hosts файла"""
        try:
            content = safe_read_hosts_file()
            if content is None:
                log("Не удалось прочитать файл hosts для удаления api.github.com")
                return False
                
            lines = content.splitlines(keepends=True)
            new_lines = []
            removed_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line_stripped or line_stripped.startswith('#'):
                    new_lines.append(line)
                    continue
                    
                # Разбиваем строку на части (IP домен)
                parts = line_stripped.split()
                if len(parts) >= 2:
                    domain = parts[1]  # Второй элемент - это домен
                    if domain.lower() == "api.github.com":
                        # Нашли запись api.github.com - не добавляем её в новый файл
                        removed_lines.append(line_stripped)
                        log(f"Удаляем из hosts: {line_stripped}")
                        continue
                
                # Добавляем все остальные строки
                new_lines.append(line)
            
            if removed_lines:
                # Убираем лишние пустые строки в конце файла
                while new_lines and new_lines[-1].strip() == "":
                    new_lines.pop()
                
                # Оставляем одну пустую строку в конце, если файл не пустой
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines[-1] += '\n'
                elif new_lines:
                    new_lines.append('\n')

                if not safe_write_hosts_file("".join(new_lines)):
                    log("Не удалось записать файл hosts после удаления api.github.com")
                    return False
                
                log(f"✅ Удалена запись api.github.com из hosts файла: {removed_lines}")
                self.set_status("Запись api.github.com удалена из hosts файла")
                return True
            else:
                log("Запись api.github.com не найдена в hosts файле")
                return True  # Не ошибка, просто нет записи
                
        except PermissionError:
            log("Нет прав для удаления api.github.com из hosts файла")
            return False
        except Exception as e:
            log(f"Ошибка при удалении api.github.com из hosts: {e}")
            return False

    def check_and_remove_github_api(self):
        """Проверяет и при необходимости удаляет api.github.com из hosts"""
        try:
            # Импортируем функцию для проверки настройки реестра
            from config import get_remove_github_api
            
            # Проверяем, разрешено ли удаление GitHub API
            if not get_remove_github_api():
                log("⚙️ Удаление api.github.com отключено в настройках")
                return
                
            if self.check_github_api_in_hosts():
                log("🔍 Обнаружена запись api.github.com в hosts файле - принудительно удаляем...")
                if self.remove_github_api_from_hosts():
                    log("✅ Запись api.github.com успешно удалена из hosts")
                else:
                    log("❌ Не удалось удалить api.github.com из hosts")
            else:
                log("✅ Запись api.github.com не найдена в hosts файле")
        except Exception as e:
            log(f"Ошибка при проверке/удалении api.github.com: {e}")

    # ------------------------- сервис -------------------------
    def get_active_domains(self):
        """Возвращает множество активных доменов из hosts файла с ПРАВИЛЬНЫМИ IP адресами"""
        current_active = set()
        try:
            from .proxy_domains import PROXY_DOMAINS
            content = safe_read_hosts_file()
            if content is None:
                return current_active
                
            lines = content.splitlines()
            
            for line in lines:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                    
                # Разбиваем строку на части (IP домен)
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    domain = parts[1]
                    
                    # Проверяем что домен есть в наших PROXY_DOMAINS И IP совпадает
                    if domain in PROXY_DOMAINS:
                        expected_ip = PROXY_DOMAINS[domain]
                        if ip == expected_ip:
                            current_active.add(domain)
                        else:
                            # Домен есть но с другим IP - не считаем его активным
                            log(f"Домен {domain} найден с другим IP: {ip} (ожидается {expected_ip})", "DEBUG")
                            
            log(f"Найдено активных доменов с правильными IP: {len(current_active)}", "DEBUG")
        except Exception as e:
            log(f"Ошибка при чтении hosts: {e}", "ERROR")
        return current_active

    def set_status(self, message: str):
        if self.status_callback:
            self.status_callback(message)
        else:
            print(message)

    # ------------------------- проверки -------------------------

    def is_proxy_domains_active(self) -> bool:
        """Проверяет, есть ли активные (НЕ закомментированные) записи наших доменов в hosts"""
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
                
            lines = content.splitlines()
            domains = set(PROXY_DOMAINS.keys())
            
            for line in lines:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                    
                # Разбиваем строку на части (IP домен)
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]  # Второй элемент - это домен
                    if domain in domains:
                        # Найден активный (не закомментированный) домен
                        return True
                        
            return False
        except Exception as e:
            log(f"Ошибка при проверке hosts: {e}")
            return False

    def is_adobe_domains_active(self) -> bool:
        """Проверяет, есть ли активные записи Adobe в hosts"""
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
                
            lines = content.splitlines()
            domains = set(ADOBE_DOMAINS.keys())
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                    if domain in domains:
                        return True
                        
            return False
        except Exception as e:
            log(f"Ошибка при проверке Adobe в hosts: {e}")
            return False

    def is_hosts_file_accessible(self) -> bool:
        """Проверяет, доступен ли файл hosts для чтения и записи."""
        try:
            # Проверяем правильность написания имени файла
            is_correct, error_msg = check_hosts_file_name()
            if not is_correct:
                log(error_msg)
                return False
            
            # ✅ НОВОЕ: Если файла нет, создаем его
            if not HOSTS_PATH.exists():
                log("Файл hosts не существует, будет создан при первой записи")
                # Проверяем, можем ли мы создать файл
                try:
                    # Пробуем создать временный файл в той же директории
                    test_file = HOSTS_PATH.parent / "test_write_permission.tmp"
                    test_file.write_text("test", encoding="utf-8")
                    test_file.unlink()  # Удаляем тестовый файл
                    return True
                except PermissionError:
                    log("Нет прав для создания файла hosts. Требуются права администратора.")
                    return False
            
            # Проверяем возможность чтения с безопасной функцией
            content = safe_read_hosts_file()
            if content is None:
                return False
                    
            # Проверяем атрибут "только для чтения"
            if is_file_readonly(HOSTS_PATH):
                log("Файл hosts имеет атрибут 'только для чтения'")
            
            # Проверяем возможность записи (пробуем открыть в режиме добавления)
            try:
                with HOSTS_PATH.open("a", encoding="utf-8-sig") as f:
                    pass
            except PermissionError:
                # Если не можем открыть для записи, но файл НЕ readonly, 
                # значит действительно нет прав администратора
                if not is_file_readonly(HOSTS_PATH):
                    raise
                # Если файл readonly, попробуем снять атрибут
                log("Не удается открыть файл для записи из-за атрибута 'только для чтения'")
            
            return True
            
        except PermissionError:
            log(f"Нет прав доступа к файлу hosts: {HOSTS_PATH}")
            return False
        except FileNotFoundError:
            log(f"Файл hosts не найден: {HOSTS_PATH}")
            return False
        except Exception as e:
            log(f"Ошибка при проверке доступности hosts: {e}")
            return False

    def _no_perm(self):
        """Обработка ошибки прав доступа"""
        self.set_status("Нет прав для изменения файла hosts")
        log("Нет прав для изменения файла hosts")

    def add_proxy_domains(self) -> bool:
        """Добавляет домены в hosts файл"""
        log("🟡 add_proxy_domains начат", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        # ✅ Вызываем check_and_remove_github_api только один раз в начале
        self.check_and_remove_github_api()
        
        try:
            # Сначала удаляем старые записи
            content = safe_read_hosts_file()
            if content is None:
                return False
            
            # Удаляем старые записи вручную
            lines = content.splitlines(keepends=True)
            domains_to_remove = set(PROXY_DOMAINS.keys())
            
            new_lines = []
            for line in lines:
                if (line.strip() and 
                    not line.lstrip().startswith("#") and 
                    len(line.split()) >= 2 and 
                    line.split()[1] in domains_to_remove):
                    continue
                new_lines.append(line)
            
            # Убираем лишние пустые строки
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            
            # Добавляем новые домены
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append('\n')
            
            for domain, ip in PROXY_DOMAINS.items():
                new_lines.append(f"{ip} {domain}\n")
            
            # Записываем
            if not safe_write_hosts_file("".join(new_lines)):
                return False
            
            self.set_status(f"Файл hosts обновлён: добавлено {len(PROXY_DOMAINS)} записей")
            log(f"✅ Добавлены домены: {list(PROXY_DOMAINS.keys())[:5]}...", "DEBUG")
            return True
            
        except PermissionError:
            log("Ошибка прав доступа в add_proxy_domains", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка в add_proxy_domains: {e}", "ERROR")
            return False

    def remove_proxy_domains(self) -> bool:
        """Удаляет домены из hosts файла"""
        log("🟡 remove_proxy_domains начат", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        # ✅ НЕ вызываем check_and_remove_github_api здесь
        
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
            
            lines = content.splitlines(keepends=True)
            domains = set(PROXY_DOMAINS.keys())
            
            new_lines = []
            removed_count = 0
            
            for line in lines:
                if (line.strip() and 
                    not line.lstrip().startswith("#") and 
                    len(line.split()) >= 2 and 
                    line.split()[1] in domains):
                    removed_count += 1
                    continue
                new_lines.append(line)
            
            # Убираем лишние пустые строки
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            
            if not safe_write_hosts_file("".join(new_lines)):
                return False
            
            self.set_status(f"Файл hosts обновлён: удалено {removed_count} записей")
            log(f"✅ Удалено {removed_count} доменов", "DEBUG")
            return True
            
        except PermissionError:
            log("Ошибка прав доступа в remove_proxy_domains", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка в remove_proxy_domains: {e}", "ERROR")
            return False
    
    def apply_selected_domains(self, selected_domains):
        """Применяет выбранные домены к файлу hosts"""
        log(f"🟡 apply_selected_domains начат: {len(selected_domains)} доменов", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        # Создаем временный словарь только с выбранными доменами
        selected_proxy_domains = {
            domain: ip for domain, ip in PROXY_DOMAINS.items() 
            if domain in selected_domains
        }
        
        if not selected_proxy_domains:
            log("Нет выбранных доменов, удаляем все", "DEBUG")
            return self.remove_proxy_domains()
        
        try:
            # Читаем текущее содержимое
            content = safe_read_hosts_file()
            if content is None:
                self.set_status("Не удалось прочитать файл hosts")
                return False
            
            # Удаляем старые записи ВРУЧНУЮ
            lines = content.splitlines(keepends=True)
            domains_to_remove = set(PROXY_DOMAINS.keys())
            
            new_lines = []
            for line in lines:
                if (line.strip() and 
                    not line.lstrip().startswith("#") and 
                    len(line.split()) >= 2 and 
                    line.split()[1] in domains_to_remove):
                    continue
                new_lines.append(line)
            
            # Убираем лишние пустые строки в конце
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            
            # Добавляем выбранные домены
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            
            new_lines.append('\n')  # Разделитель
            
            for domain, ip in selected_proxy_domains.items():
                new_lines.append(f"{ip} {domain}\n")
            
            # Записываем результат
            final_content = "".join(new_lines)
            
            if not safe_write_hosts_file(final_content):
                self.set_status("Не удалось записать файл hosts")
                return False
            
            count = len(selected_proxy_domains)
            self.set_status(f"Файл hosts обновлён: добавлено {count} записей")
            log(f"✅ Добавлены выбранные домены: {list(selected_proxy_domains.keys())}", "DEBUG")
            
            log(f"🟡 apply_selected_domains завершен успешно", "DEBUG")
            return True
            
        except PermissionError:
            log("🟡 Ошибка прав доступа", "DEBUG") 
            self._no_perm()
            return False
        except Exception as e:
            error_msg = f"Ошибка при обновлении hosts: {e}"
            self.set_status(error_msg)
            log(error_msg, "ERROR")
            return False

    # НОВЫЕ МЕТОДЫ ДЛЯ ADOBE
    def add_adobe_domains(self) -> bool:
        """Добавляет домены Adobe для блокировки активации"""
        log("🔒 Добавление доменов Adobe для блокировки активации", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
            
            # Удаляем старые записи Adobe
            lines = content.splitlines(keepends=True)
            domains_to_remove = set(ADOBE_DOMAINS.keys())
            
            new_lines = []
            skip_adobe_comment = False
            for line in lines:
                # Пропускаем старый комментарий Adobe
                if "# Adobe Activation Block" in line or "# Adobe Block" in line:
                    skip_adobe_comment = True
                    continue
                if skip_adobe_comment and "# Generated by" in line:
                    skip_adobe_comment = False
                    continue
                    
                if (line.strip() and 
                    not line.lstrip().startswith("#") and 
                    len(line.split()) >= 2 and 
                    line.split()[1] in domains_to_remove):
                    continue
                new_lines.append(line)
            
            # Убираем лишние пустые строки
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            
            # Добавляем новые домены Adobe
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append('\n')
            new_lines.append('# Adobe Activation Block\n')
            new_lines.append('# Generated by Zapret-WinGUI\n')
            
            for domain, ip in ADOBE_DOMAINS.items():
                new_lines.append(f"{ip} {domain}\n")
            
            # Записываем
            if not safe_write_hosts_file("".join(new_lines)):
                return False
            
            self.set_status(f"Блокировка Adobe активирована: добавлено {len(ADOBE_DOMAINS)} записей")
            log(f"✅ Добавлены домены Adobe для блокировки", "DEBUG")
            return True
            
        except PermissionError:
            log("Ошибка прав доступа при добавлении Adobe доменов", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка при добавлении Adobe доменов: {e}", "ERROR")
            return False

    def clear_hosts_file(self) -> bool:
        """Полностью очищает файл hosts, оставляя только базовое содержимое Windows"""
        log("🗑️ Полная очистка файла hosts", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        try:
            # Базовое содержимое hosts файла Windows
            default_content = """# Copyright (c) 1993-2009 Microsoft Corp.
    #
    # This is a sample HOSTS file used by Microsoft TCP/IP for Windows.
    #
    # This file contains the mappings of IP addresses to host names. Each
    # entry should be kept on an individual line. The IP address should
    # be placed in the first column followed by the corresponding host name.
    # The IP address and the host name should be separated by at least one
    # space.
    #
    # Additionally, comments (such as these) may be inserted on individual
    # lines or following the machine name denoted by a '#' symbol.
    #
    # For example:
    #
    #      102.54.94.97     rhino.acme.com          # source server
    #       38.25.63.10     x.acme.com              # x client host

    # localhost name resolution is handled within DNS itself.
    #	127.0.0.1       localhost
    #	::1             localhost
    """
            
            if not safe_write_hosts_file(default_content):
                log("Не удалось записать файл hosts после очистки")
                return False
            
            self.set_status("Файл hosts полностью очищен")
            log("✅ Файл hosts успешно очищен (восстановлено базовое содержимое)", "DEBUG")
            return True
            
        except PermissionError:
            log("Ошибка прав доступа при очистке hosts файла", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка при очистке hosts файла: {e}", "ERROR")
            return False
        
    def remove_adobe_domains(self) -> bool:
        """Удаляет домены Adobe из hosts файла"""
        log("🔓 Удаление доменов Adobe", "DEBUG")
        
        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False
        
        try:
            content = safe_read_hosts_file()
            if content is None:
                return False
            
            lines = content.splitlines(keepends=True)
            domains = set(ADOBE_DOMAINS.keys())
            
            new_lines = []
            removed_count = 0
            skip_next = False
            
            for line in lines:
                # Удаляем комментарии Adobe
                if "# Adobe Activation Block" in line or "# Adobe Block" in line:
                    skip_next = True
                    continue
                if skip_next and "# Generated by" in line:
                    skip_next = False
                    continue
                    
                if (line.strip() and 
                    not line.lstrip().startswith("#") and 
                    len(line.split()) >= 2 and 
                    line.split()[1] in domains):
                    removed_count += 1
                    continue
                    
                new_lines.append(line)
            
            # Убираем лишние пустые строки
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()
            
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            
            if not safe_write_hosts_file("".join(new_lines)):
                return False
            
            self.set_status(f"Блокировка Adobe отключена: удалено {removed_count} записей")
            log(f"✅ Удалено {removed_count} доменов Adobe", "DEBUG")
            return True
            
        except PermissionError:
            log("Ошибка прав доступа при удалении Adobe доменов", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка при удалении Adobe доменов: {e}", "ERROR")
            return False