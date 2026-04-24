import ctypes
import stat
import os
import subprocess
from pathlib import Path
from .proxy_domains import (
    get_all_services,
    get_dns_profiles,
    get_service_domain_ip_rows,
    get_service_domain_names,
)
from .adobe_domains import ADOBE_DOMAINS
from log.log import log


def _get_hosts_path_from_env() -> Path:
    """
    Возвращает путь к hosts через переменные окружения, чтобы корректно работать
    когда Windows установлена не на C:.
    """
    sys_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if sys_root:
        return Path(sys_root, "System32", "drivers", "etc", "hosts")
    return Path(r"C:\Windows\System32\drivers\etc\hosts")


HOSTS_PATH = _get_hosts_path_from_env() if os.name == "nt" else Path(r"C:\Windows\System32\drivers\etc\hosts")

_GITHUB_API_DOMAIN = "api.github.com"
_ZAPRET_TRACKER_DOMAIN = "zapret-tracker.duckdns.org"
_ZAPRET_TRACKER_IP = "88.210.52.47"
_HOSTS_BOOTSTRAP_SIGNATURE_VERSION = "v2"


def _get_hosts_bootstrap_signature() -> str:
    return f"{_HOSTS_BOOTSTRAP_SIGNATURE_VERSION}|{_ZAPRET_TRACKER_DOMAIN}|{_ZAPRET_TRACKER_IP}"


def _extract_tracker_from_bootstrap_signature(signature: str | None) -> tuple[str | None, str | None]:
    if not isinstance(signature, str):
        return None, None
    parts = [part.strip() for part in signature.split("|")]
    if len(parts) < 3:
        return None, None
    domain = parts[1].lower()
    ip = parts[2]
    if not domain or not ip:
        return None, None
    return domain, ip


def _parse_hosts_mapping_line(line: str) -> tuple[str, list[str], str] | None:
    mapping_part, sep, comment_part = str(line or "").partition("#")
    mapping_stripped = mapping_part.strip()
    if not mapping_stripped:
        return None

    parts = mapping_stripped.split()
    if len(parts) < 2:
        return None

    ip = parts[0]
    domains = parts[1:]
    comment = comment_part.strip() if sep else ""
    return ip, domains, comment


def _rewrite_hosts_bootstrap_line(
    *,
    line: str,
    remove_github: bool,
    previous_tracker_domain: str | None,
) -> tuple[str | None, bool, bool, bool, bool]:
    parsed = _parse_hosts_mapping_line(line)
    if parsed is None:
        return line, False, False, False, False

    ip, domains, comment = parsed
    domains_lower = [domain.lower() for domain in domains]
    updated_domains = domains
    removed_github = False
    tracker_has_correct_ip = False
    tracker_ip_corrected = False
    previous_tracker_removed = False
    line_changed = False

    if remove_github and _GITHUB_API_DOMAIN in domains_lower:
        removed_github = True
        updated_domains = [domain for domain in updated_domains if domain.lower() != _GITHUB_API_DOMAIN]
        line_changed = True

    if previous_tracker_domain and previous_tracker_domain in domains_lower:
        updated_domains = [domain for domain in updated_domains if domain.lower() != previous_tracker_domain]
        previous_tracker_removed = True
        line_changed = True
        log(f"Удаляем устаревший трекер-домен: {ip} {' '.join(domains)}")

    if _ZAPRET_TRACKER_DOMAIN in domains_lower:
        if ip == _ZAPRET_TRACKER_IP:
            tracker_has_correct_ip = True
        else:
            tracker_ip_corrected = True
            updated_domains = [domain for domain in updated_domains if domain.lower() != _ZAPRET_TRACKER_DOMAIN]
            line_changed = True
            log(f"Удаляем запись {_ZAPRET_TRACKER_DOMAIN} с некорректным IP: {ip} {' '.join(domains)}")

    if not line_changed:
        return line, removed_github, tracker_has_correct_ip, tracker_ip_corrected, previous_tracker_removed

    if not updated_domains:
        log(f"Удаляем из hosts: {ip} {' '.join(domains)}")
        return None, removed_github, tracker_has_correct_ip, tracker_ip_corrected, previous_tracker_removed

    rebuilt_line = f"{ip} {' '.join(updated_domains)}"
    if comment:
        rebuilt_line += f" # {comment}"

    if remove_github and removed_github:
        log(f"Обновляем строку hosts без api.github.com: {ip} {' '.join(domains)}")

    return rebuilt_line + "\n", removed_github, tracker_has_correct_ip, tracker_ip_corrected, previous_tracker_removed


def _append_tracker_row_if_needed(new_lines: list[str], *, tracker_has_correct_ip: bool) -> bool:
    if tracker_has_correct_ip:
        return False

    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()

    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    if new_lines:
        new_lines.append("\n")

    new_lines.append(f"{_ZAPRET_TRACKER_IP} {_ZAPRET_TRACKER_DOMAIN}\n")
    log(f"Добавляем в hosts: {_ZAPRET_TRACKER_IP} {_ZAPRET_TRACKER_DOMAIN}")
    return True


# ───────────────────────── hosts file read cache ─────────────────────────
#
# На старте приложение может несколько раз читать hosts подряд (проверки/страницы UI).
# Файл маленький, но повторные чтения + перебор кодировок/обработка PermissionError
# могут давать заметную задержку. Делаем безопасный кэш "на процесс":
# - инвалидируем по сигнатуре файла (mtime_ns + size)
# - обновляем кэш после успешной записи

_HOSTS_TEXT_CACHE: str | None = None
_HOSTS_SIG_CACHE: tuple[int, int] | None = None  # (mtime_ns, size)


def _get_hosts_sig(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        mtime_ns = getattr(st, "st_mtime_ns", None)
        if mtime_ns is None:
            mtime_ns = int(st.st_mtime * 1_000_000_000)
        return (int(mtime_ns), int(st.st_size))
    except Exception:
        return None


def _set_hosts_cache(content: str | None, sig: tuple[int, int] | None) -> None:
    global _HOSTS_TEXT_CACHE, _HOSTS_SIG_CACHE
    _HOSTS_TEXT_CACHE = content
    _HOSTS_SIG_CACHE = sig


def invalidate_hosts_file_cache() -> None:
    """Принудительно сбрасывает кэш чтения hosts (на случай внешних изменений)."""
    _set_hosts_cache(None, None)


def _get_all_managed_domains() -> set[str]:
    domains: set[str] = set()
    for service_name in get_all_services():
        domains.update(get_service_domain_names(service_name))
    return domains


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
    Восстанавливает стандартные права доступа к файлу hosts.
    Устанавливает: Administrators:F, SYSTEM:F, Users:R (через SID для любой локализации).

    Вызывается ТОЛЬКО явно по кнопке пользователя в UI — не автоматически.
    Это НЕ вредоносная активность: пользователь сам нажал «Восстановить права доступа»,
    чтобы вернуть стандартные ACL на файл hosts после блокировки антивирусом.

    Returns:
        tuple: (success: bool, message: str)
    """
    hosts_path = str(HOSTS_PATH)

    # Действие инициировано пользователем через кнопку в интерфейсе приложения.
    # Восстанавливаем стандартные Windows ACL: Administrators:F, SYSTEM:F, Users:R.
    log("Пользователь запросил восстановление стандартных прав доступа к файлу hosts")

    # Well-known SIDs (работают на любой локализации Windows)
    SID_ADMINISTRATORS = "*S-1-5-32-544"  # Administrators
    SID_USERS = "*S-1-5-32-545"           # Users
    SID_SYSTEM = "*S-1-5-18"              # SYSTEM

    try:
        # Снимаем атрибут "только для чтения"
        _run_cmd(['attrib', '-R', hosts_path], "attrib -R")

        # Забираем владение для группы администраторов
        _run_cmd(['takeown', '/F', hosts_path, '/A'], "takeown /A")

        # Сбрасываем ACL и выставляем стандартные права через SID
        _run_cmd(['icacls', hosts_path, '/reset'], "icacls /reset")
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_ADMINISTRATORS}:F'],
                 "icacls /grant Administrators")
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_SYSTEM}:F'],
                 "icacls /grant SYSTEM")
        _run_cmd(['icacls', hosts_path, '/grant', f'{SID_USERS}:R'],
                 "icacls /grant Users (read)")

        # Проверяем результат
        try:
            HOSTS_PATH.read_text(encoding='utf-8')
            log("Права восстановлены, файл hosts доступен для чтения")

            try:
                with HOSTS_PATH.open('a', encoding='utf-8-sig'):
                    pass
                log("Файл hosts доступен для записи")
                return True, "Права доступа к файлу hosts восстановлены"
            except PermissionError:
                return False, (
                    "Файл hosts доступен для чтения, но запись запрещена.\n"
                    "Возможные причины: защита антивируса/Defender.\n"
                    "Добавьте исключение для hosts или временно отключите защиту."
                )

        except PermissionError:
            return False, (
                "Не удалось восстановить права доступа.\n"
                "Попробуйте:\n"
                "1. Запустить программу от имени администратора\n"
                "2. Временно отключить антивирус\n"
                "3. Добавить исключение для файла hosts"
            )

        except Exception as e:
            return False, f"Ошибка при проверке прав: {e}"

    except FileNotFoundError as e:
        return False, f"Системная команда не найдена: {e}"
    except Exception as e:
        return False, f"Ошибка: {e}"

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

    # Fast path: используем кэш если файл не менялся.
    try:
        if hosts_path.exists():
            sig = _get_hosts_sig(hosts_path)
            if sig is not None and _HOSTS_SIG_CACHE == sig and _HOSTS_TEXT_CACHE is not None:
                return _HOSTS_TEXT_CACHE
    except Exception:
        pass
    
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
            _set_hosts_cache(default_content, _get_hosts_sig(hosts_path))
            log("Файл hosts успешно создан с базовым содержимым")
            return default_content
            
        except Exception as e:
            log(f"Ошибка при создании файла hosts: {e}", "❌ ERROR")
            return None
    
    # Если файл существует, пробуем прочитать с разными кодировками
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'cp866', 'latin1']

    permission_error_occurred = False

    sig_before = _get_hosts_sig(hosts_path)
    for encoding in encodings:
        try:
            content = hosts_path.read_text(encoding=encoding)
            log(f"Файл hosts успешно прочитан с кодировкой: {encoding}")
            _set_hosts_cache(content, sig_before or _get_hosts_sig(hosts_path))
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

    if permission_error_occurred:
        log("Нет доступа к файлу hosts. Используйте кнопку «Восстановить права доступа».", "WARNING")

    # Если ни одна кодировка не подошла, пробуем с игнорированием ошибок
    try:
        content = hosts_path.read_text(encoding='utf-8', errors='ignore')
        log("Файл hosts прочитан с игнорированием ошибок кодировки", level="⚠ WARNING")
        _set_hosts_cache(content, _get_hosts_sig(hosts_path))
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
        _set_hosts_cache(content, _get_hosts_sig(HOSTS_PATH))
        return True
    except PermissionError:
        log("Нет прав на запись в файл hosts. Используйте кнопку «Восстановить права доступа».", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка при записи файла hosts: {e}")
        return False
    
class HostsManager:
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self._last_status: str | None = None
        # При инициализации выполняем единоразовый bootstrap hosts.
        self.apply_hosts_bootstrap_if_needed()

    def restore_permissions(self):
        """Восстанавливает права доступа к файлу hosts"""
        success, message = restore_hosts_permissions()
        self.set_status(message)
        return success

    def apply_hosts_bootstrap_if_needed(self):
        """Единоразово применяет bootstrap hosts для текущей сигнатуры."""
        try:
            from settings.store import get_remove_github_api

            from settings.store import (
                get_hosts_bootstrap_signature,
                set_hosts_bootstrap_signature,
            )

            expected_signature = _get_hosts_bootstrap_signature()
            applied_signature = get_hosts_bootstrap_signature()

            if applied_signature == expected_signature:
                log("Bootstrap hosts уже применён для текущей сигнатуры", "DEBUG")
                return

            previous_tracker_domain, _ = _extract_tracker_from_bootstrap_signature(applied_signature)
            if previous_tracker_domain == _ZAPRET_TRACKER_DOMAIN:
                previous_tracker_domain = None

            if applied_signature:
                log(
                    f"Обновляем bootstrap hosts: сигнатура изменена ({applied_signature} -> {expected_signature})",
                    "DEBUG",
                )
            else:
                log("Выполняем bootstrap hosts для текущей сигнатуры", "DEBUG")

            content = safe_read_hosts_file()
            if content is None:
                log("Не удалось прочитать hosts для bootstrap", "❌ ERROR")
                return

            remove_github = bool(get_remove_github_api())

            lines = content.splitlines(keepends=True)
            new_lines: list[str] = []

            removed_github = False
            tracker_has_correct_ip = False
            tracker_ip_corrected = False
            previous_tracker_removed = False

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    new_lines.append(line)
                    continue
                (
                    rewritten_line,
                    line_removed_github,
                    line_tracker_has_correct_ip,
                    line_tracker_ip_corrected,
                    line_previous_tracker_removed,
                ) = _rewrite_hosts_bootstrap_line(
                    line=line,
                    remove_github=remove_github,
                    previous_tracker_domain=previous_tracker_domain,
                )

                removed_github = removed_github or line_removed_github
                tracker_has_correct_ip = tracker_has_correct_ip or line_tracker_has_correct_ip
                tracker_ip_corrected = tracker_ip_corrected or line_tracker_ip_corrected
                previous_tracker_removed = previous_tracker_removed or line_previous_tracker_removed

                if rewritten_line is not None:
                    new_lines.append(rewritten_line)

            tracker_added = _append_tracker_row_if_needed(
                new_lines,
                tracker_has_correct_ip=tracker_has_correct_ip,
            )

            changed = removed_github or tracker_ip_corrected or previous_tracker_removed or tracker_added
            if changed and not safe_write_hosts_file("".join(new_lines)):
                log("Не удалось записать hosts после bootstrap", "❌ ERROR")
                return

            if not set_hosts_bootstrap_signature(expected_signature):
                log("Не удалось сохранить сигнатуру bootstrap hosts", "⚠ WARNING")
                return

            if remove_github:
                if removed_github:
                    log("✅ Запись api.github.com удалена из hosts (первый запуск)")
                else:
                    log("✅ Запись api.github.com не найдена в hosts (первый запуск)")
            else:
                log("⚙️ Удаление api.github.com отключено в настройках")

            if tracker_added and (tracker_ip_corrected or previous_tracker_removed):
                log("✅ Запись zapret-tracker.duckdns.org обновлена на корректный IP (первый запуск)")
            elif tracker_added:
                log("✅ Запись zapret-tracker.duckdns.org добавлена в hosts (первый запуск)")
            elif tracker_ip_corrected or previous_tracker_removed:
                log("✅ Удалены некорректные записи zapret-tracker.duckdns.org (первый запуск)")
            else:
                log("✅ Запись zapret-tracker.duckdns.org уже есть в hosts")
        except Exception as e:
            log(f"Ошибка при bootstrap hosts: {e}")

    # ------------------------- сервис -------------------------
    def get_active_domains_map(self) -> dict[str, str]:
        """Возвращает {domain: ip} для всех управляемых доменов, найденных в hosts (без проверки IP)."""
        current_active: dict[str, str] = {}
        managed_domains = _get_all_managed_domains()
        try:
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
                    
                    if domain in managed_domains:
                        current_active[domain] = ip
                            
            log(f"Найдено активных управляемых доменов: {len(current_active)}", "DEBUG")
        except Exception as e:
            log(f"Ошибка при чтении hosts: {e}", "ERROR")
        return current_active

    def set_status(self, message: str):
        self._last_status = message
        if self.status_callback:
            self.status_callback(message)
        else:
            print(message)

    @property
    def last_status(self) -> str | None:
        return self._last_status

    # ------------------------- проверки -------------------------

    def is_proxy_domains_active(self) -> bool:
        """Проверяет, есть ли активные управляемые записи в hosts."""
        try:
            return bool(self.get_active_domains_map())
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

    def apply_service_dns_selections(self, service_dns: dict[str, str], static_enabled: set[str] | None = None) -> bool:
        """
        Применяет выбор DNS-профилей по сервисам.

        Args:
            service_dns: {service_name: profile_name or 'off'}
            static_enabled: set(service_name) для сервисов, которые включаются без выбора профиля
        """
        log("🟡 apply_service_dns_selections начат", "DEBUG")

        # key = normalized domain; value = (display_domain, [ip1, ip2, ...]).
        selected_by_domain: dict[str, tuple[str, list[str]]] = {}
        domain_order: list[str] = []

        def merge_rows(rows: list[tuple[str, str]]) -> None:
            per_service: dict[str, tuple[str, list[str], set[str]]] = {}
            per_service_order: list[str] = []

            for domain, ip in rows:
                domain_s = (domain or "").strip()
                ip_s = (ip or "").strip()
                if not domain_s or not ip_s:
                    continue

                domain_key = domain_s.casefold()
                ip_key = ip_s.casefold()
                item = per_service.get(domain_key)
                if item is None:
                    per_service[domain_key] = (domain_s, [ip_s], {ip_key})
                    per_service_order.append(domain_key)
                    continue

                display_domain, ips, seen_ips = item
                if ip_key in seen_ips:
                    continue
                ips.append(ip_s)
                seen_ips.add(ip_key)
                per_service[domain_key] = (display_domain, ips, seen_ips)

            for domain_key in per_service_order:
                display_domain, ips, _seen_ips = per_service[domain_key]
                if domain_key not in selected_by_domain:
                    domain_order.append(domain_key)
                # Keep old override semantics between services: later service replaces domain mapping.
                selected_by_domain[domain_key] = (display_domain, ips)

        for service_name, profile_name in (service_dns or {}).items():
            if not isinstance(service_name, str):
                continue
            if not isinstance(profile_name, str):
                continue

            normalized = profile_name.strip().lower()
            if not normalized or normalized in ("off", "откл", "откл.", "0", "false"):
                continue

            rows = get_service_domain_ip_rows(service_name, profile_name.strip())
            if not rows:
                # Профиль недоступен для сервиса (не хватает IP) — просто пропускаем.
                continue
            merge_rows(rows)

        if static_enabled:
            default_profile = (get_dns_profiles() or [None])[0]
            for service_name in static_enabled:
                rows = get_service_domain_ip_rows(service_name, default_profile) if default_profile else []
                if rows:
                    merge_rows(rows)

        selected_rows: list[tuple[str, str]] = []
        for domain_key in domain_order:
            display_domain, ips = selected_by_domain.get(domain_key, ("", []))
            for ip in ips:
                selected_rows.append((display_domain, ip))

        return self.apply_domain_ip_rows(selected_rows)

    def apply_domain_ip_map(self, domain_ip_map: dict[str, str]) -> bool:
        """Применяет домены в hosts из словаря {domain: ip}."""
        rows: list[tuple[str, str]] = []
        for domain, ip in (domain_ip_map or {}).items():
            if not isinstance(domain, str) or not isinstance(ip, str):
                continue
            rows.append((domain, ip))
        return self.apply_domain_ip_rows(rows)

    def apply_domain_ip_rows(self, domain_ip_rows: list[tuple[str, str]]) -> bool:
        """Применяет домены в hosts: удаляет все управляемые и добавляет указанные строки (domain, ip)."""
        log(f"🟡 apply_domain_ip_rows начат: {len(domain_ip_rows)} записей", "DEBUG")

        if not self.is_hosts_file_accessible():
            self.set_status("Файл hosts недоступен для изменения")
            return False

        managed_domains = _get_all_managed_domains()

        try:
            content = safe_read_hosts_file()
            if content is None:
                self.set_status("Не удалось прочитать файл hosts")
                return False

            lines = content.splitlines(keepends=True)
            new_lines: list[str] = []

            removed_count = 0
            for line in lines:
                if (
                    line.strip()
                    and not line.lstrip().startswith("#")
                    and len(line.split()) >= 2
                    and line.split()[1] in managed_domains
                ):
                    removed_count += 1
                    continue
                new_lines.append(line)

            # Убираем лишние пустые строки в конце
            while new_lines and new_lines[-1].strip() == "":
                new_lines.pop()

            desired_rows: list[tuple[str, str]] = []
            seen_rows: set[tuple[str, str]] = set()
            for row in (domain_ip_rows or []):
                if not isinstance(row, (tuple, list)) or len(row) < 2:
                    continue
                domain = str(row[0]).strip()
                ip = str(row[1]).strip()
                if not domain or not ip:
                    continue
                row_key = (domain.casefold(), ip.casefold())
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                desired_rows.append((domain, ip))

            # Ничего не добавляем — просто очищаем управляемые домены
            if not desired_rows:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                if not safe_write_hosts_file("".join(new_lines)):
                    return False
                self.set_status(f"Файл hosts обновлён: удалено {removed_count} записей")
                return True

            # Добавляем выбранные домены
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append("\n")  # Разделитель

            for domain, ip in desired_rows:
                new_lines.append(f"{ip} {domain}\n")

            if not safe_write_hosts_file("".join(new_lines)):
                self.set_status("Не удалось записать файл hosts")
                return False

            self.set_status(f"Файл hosts обновлён: добавлено {len(desired_rows)} записей")
            log(f"✅ apply_domain_ip_rows: removed={removed_count}, added={len(desired_rows)}", "DEBUG")
            return True

        except PermissionError:
            log("Ошибка прав доступа в apply_domain_ip_rows", "ERROR")
            self._no_perm()
            return False
        except Exception as e:
            log(f"Ошибка в apply_domain_ip_rows: {e}", "ERROR")
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
