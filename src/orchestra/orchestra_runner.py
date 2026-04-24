# orchestra/orchestra_runner.py
"""
Circular Orchestra Runner - автоматическое обучение стратегий DPI bypass.

Использует circular orchestrator из F:\\doc\\zapret2\\lua\\zapret-auto.lua (файл менять этот нельзя) с:
- combined_failure_detector (RST injection + silent drop)
- strategy_stats (LOCK механизм после 3 успехов, UNLOCK после 2 failures)
- domain_grouping (группировка субдоменов)

При этом сам оркестратор (его исходный код) всегда хранится /home/privacy/zapret/lua/

Копировать в Program Data не нужно -  приложение берёт файлы напрямую из /home/privacy/zapret/lua/.

Можешь посмотреть исходный код логов в исходном коде запрета F:\\doc\\zapret2\\nfq2\\desync.c
Логи - только Python - компактные для гуи чтобы не было огромных winws2 debug логов.
"""

import os
import subprocess
import threading
import json
import glob
import ipaddress
import time
from collections import deque
from typing import Optional, Callable, Dict, List
from datetime import datetime

from log.log import log

from utils.circular_strategy_numbering import (
    renumber_circular_strategies,
    strip_strategy_tags,
)
from config.config import MAIN_DIRECTORY, EXE_FOLDER, LUA_FOLDER, LOGS_FOLDER, BIN_FOLDER
from lists.core.paths import get_lists_dir

from settings.store import (
    get_orchestra_auto_restart_on_discord_fail,
    get_orchestra_discord_fails_for_restart,
    get_orchestra_keep_debug_file,
    get_orchestra_whitelist_user_domains,
    remove_orchestra_history_target,
    remove_orchestra_locked_target,
    remove_orchestra_user_blocked_target,
    remove_orchestra_user_locked,
    set_orchestra_whitelist_user_domains,
)
from orchestra.ignored_targets import (
    get_orchestra_ignored_exact_domains,
    is_orchestra_ignored_target,
)
from orchestra.log_parser import LogParser, EventType, ParsedEvent, nld_cut, ip_to_subnet16, is_local_ip
from orchestra.blocked_strategies_manager import BlockedStrategiesManager
from orchestra.locked_strategies_manager import (
    LockedStrategiesManager,
    ASKEY_ALL,
    TCP_ASKEYS,
    UDP_ASKEYS,
    PROTO_TO_ASKEY,
)
LISTS_FOLDER = get_lists_dir()

# Максимальное количество лог-файлов оркестратора
MAX_ORCHESTRA_LOGS = 10

# Максимальный размер лог-файла (1 ГБ) - при превышении файл очищается
MAX_LOG_SIZE_BYTES = 1024 * 1024 * 1024

# Интервал проверки размера файла (каждые N строк)
LOG_SIZE_CHECK_INTERVAL = 1000

# Белый список по умолчанию - сайты которые НЕ нужно обрабатывать
# Эти сайты работают без DPI bypass или требуют особой обработки
# Встраиваются автоматически при load_whitelist() как системные (нельзя удалить)
DEFAULT_WHITELIST_DOMAINS = {
    # Российские сервисы (работают без bypass)
    "vk.com",
    "vk.ru",
    "vkvideo.ru",
    "vk-portal.net",
    "mycdn.me",
    "userapi.com",
    "mail.ru",
    "max.ru",
    "ok.ru",
    "okcdn.ru",
    "yandex.ru",
    "ya.ru",
    "yandex.net",
    "yandex.by",
    "yandex.kz",
    "sberbank.ru",
    "nalog.ru",
    # Банки
    "tinkoff.ru",
    "alfabank.ru",
    "vtb.ru",
    # Государственные
    "mos.ru",
    "gosuslugi.ru",
    "government.ru",
    # Антивирусы и безопасность
    "kaspersky.ru",
    "kaspersky.com",
    "drweb.ru",
    "drweb.com",
    # Microsoft (обычно работает)
    "microsoft.com",
    "live.com",
    "office.com",
    # Локальные адреса
    "localhost",
    "127.0.0.1",
    # Образование
    "netschool.edu22.info",
    "edu22.info",
    # Конструкторы сайтов
    "tilda.ws",
    "tilda.cc",
    "tildacdn.com",
    # AI сервисы (обычно работают)
    "claude.ai",
    "anthropic.com",
    "claude.com",
    # ozon
    "ozon.ru",
    "ozone.ru",
    "ozonusercontent.com",
    # wb
    "wildberries.ru",
    "wb.ru",
    "wbbasket.ru",
    # Telegram Proxy работает как отдельный модуль, оркестратор не должен его обучать.
    *get_orchestra_ignored_exact_domains(),
}

def _is_default_whitelist_domain(hostname: str) -> bool:
    """
    Проверяет, является ли домен системным в whitelist (нельзя удалить).
    Внутренняя функция для whitelist методов.
    """
    if not hostname:
        return False
    hostname = hostname.lower().strip().rstrip('.')  # Normalize: lowercase, trim, remove trailing dots
    return hostname in DEFAULT_WHITELIST_DOMAINS


# Локальные IP диапазоны (для UDP - проверяем IP напрямую)
LOCAL_IP_PREFIXES = (
    # IPv4
    "127.",        # Loopback
    "10.",         # Private Class A
    "192.168.",    # Private Class C
    "172.16.", "172.17.", "172.18.", "172.19.",  # Private Class B
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "169.254.",    # Link-local
    "0.",          # This network
    # IPv6
    "::1",         # Loopback
    "fe80:",       # Link-local
    "fc00:", "fd00:",  # Unique local (private)
)

# Константы для скрытого запуска процесса
SW_HIDE = 0
CREATE_NO_WINDOW = 0x08000000
STARTF_USESHOWWINDOW = 0x00000001

class OrchestraRunner:
    """
    Runner для circular оркестратора с автоматическим обучением.

    Особенности:
    - Использует circular orchestrator
    - Детекция: RST injection + silent drop + SUCCESS по байтам (2KB)
    - LOCK после 3 успехов на одной стратегии
    - UNLOCK после 2 failures (автоматическое переобучение)
    - Группировка субдоменов (googlevideo.com, youtube.com и т.д.)
    - Python логи (компактные)
    """

    def __init__(self, zapret_path: str = None):
        if zapret_path is None:
            zapret_path = MAIN_DIRECTORY

        self.zapret_path = zapret_path
        self.winws_exe = os.path.join(EXE_FOLDER, "winws2.exe")
        self.lua_path = LUA_FOLDER
        self.logs_path = LOGS_FOLDER
        self.bin_path = BIN_FOLDER

        # Файлы конфигурации (в lua папке)
        # ВАЖНО: circular-config.txt теперь СТАТИЧЕСКИЙ файл в /home/privacy/zapret/lua/
        # Стратегии встроены напрямую в circular-config.txt, отдельные strategies-*.txt не нужны
        self.config_path = os.path.join(self.lua_path, "circular-config.txt")
        self.runtime_config_path = os.path.join(self.lua_path, "circular-config.runtime.txt")
        self.launch_config_path = self.config_path
        self.blobs_path = os.path.join(self.lua_path, "blobs.txt")

        # Белый список (exclude hostlist)
        self.whitelist_path = os.path.join(self.lua_path, "whitelist.txt")

        # Debug log от winws2 (для детекции LOCKED/UNLOCKING)
        # Теперь используем уникальные имена с ID сессии
        self.current_log_id: Optional[str] = None
        self.debug_log_path: Optional[str] = None
        # Загружаем настройку сохранения debug файла из settings.json
        self.keep_debug_file = bool(get_orchestra_keep_debug_file())

        # Загружаем настройку авторестарта при Discord FAIL
        self.auto_restart_on_discord_fail = bool(get_orchestra_auto_restart_on_discord_fail())
        self.restart_callback: Optional[Callable[[], None]] = None  # Callback для перезапуска приложения

        # Счётчик Discord FAIL для рестарта (рестарт только после N фейлов подряд)
        self.discord_fail_count = 0
        self.discord_fails_threshold = int(get_orchestra_discord_fails_for_restart())

        # Состояние
        self.running_process: Optional[subprocess.Popen] = None
        self.output_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Менеджеры стратегий
        self.blocked_manager = BlockedStrategiesManager()
        self.locked_manager = LockedStrategiesManager(blocked_manager=self.blocked_manager)
        # Обратная ссылка: blocked нужен locked для удаления конфликтующих locks
        self.blocked_manager.set_locked_manager(self.locked_manager)

        # Кэши ipset подсетей для UDP (игры/Discord/QUIC)
        self.ipset_networks: list[tuple[ipaddress._BaseNetwork, str]] = []

        # Белый список (exclude list) - домены которые НЕ обрабатываются
        self.user_whitelist: list = []  # Только пользовательские (из реестра)
        self.whitelist: set = set()     # Полный список (default + user) для генерации файла

        # Callbacks
        self.output_callback: Optional[Callable[[str], None]] = None
        self.lock_callback: Optional[Callable[[str, int], None]] = None
        self.unlock_callback: Optional[Callable[[str], None]] = None

        # Мониторинг активности (для подсказок пользователю)
        self.last_activity_time: Optional[float] = None
        self.inactivity_warning_shown: bool = False

        # Диагностика старта/быстрого падения процесса
        self.last_start_error: str = ""
        self.last_exit_info: Optional[dict] = None
        self.last_start_attempt_ts: float = 0.0
        self._recent_output_lines = deque(maxlen=60)
        self.last_launch_config_path: str = ""
        self.last_launch_command: List[str] = []
        self._startup_forwarded_signatures = deque(maxlen=80)
        self._ignored_runtime_targets_logged: set[str] = set()

    def _remember_output_line(self, line: str):
        """Запоминает последние строки stdout для диагностики падений."""
        text = (line or "").strip()
        if not text:
            return
        self._recent_output_lines.append(text)

    def _get_recent_output_tail(self, max_lines: int = 8) -> list:
        """Возвращает последние строки вывода winws2 для диагностики."""
        if max_lines <= 0:
            return []
        lines = list(self._recent_output_lines)
        if not lines:
            return []
        return lines[-max_lines:]

    def _looks_like_error_output_line(self, line: str) -> bool:
        """Определяет, похожа ли сырая строка winws2 на ошибку запуска."""
        text = str(line or "").strip().lower()
        if not text:
            return False

        markers = (
            "error",
            "fatal",
            "failed",
            "invalid",
            "cannot",
            "can't",
            "access denied",
            "permission",
            "not found",
            "unknown option",
            "winerror",
            "exception",
            "ошиб",
            "не удалось",
            "не найден",
            "некоррект",
        )
        return any(marker in text for marker in markers)

    def _is_startup_phase(self, window_sec: float = 12.0) -> bool:
        """Возвращает True в течение первых window_sec секунд после запуска."""
        if self.last_start_attempt_ts <= 0:
            return False
        return (time.monotonic() - self.last_start_attempt_ts) <= window_sec

    def _get_config_preview_lines(self, config_path: str, max_lines: int = 6) -> list:
        """Возвращает короткий preview активного конфига запуска."""
        path = str(config_path or "").strip()
        if not path or max_lines <= 0:
            return []

        if not os.path.exists(path):
            return [f"Конфиг не найден: {path}"]

        preview = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for index, raw in enumerate(fh, start=1):
                    line = str(raw or "").strip()
                    if not line or line.startswith("#") or line.startswith(";"):
                        continue

                    if len(line) > 220:
                        line = line[:220] + " ..."

                    preview.append(f"  L{index}: {line}")
                    if len(preview) >= max_lines:
                        break
        except Exception as e:
            return [f"Не удалось прочитать конфиг: {e}"]

        return preview

    def _build_startup_diagnostics(self, exit_code: Optional[int], uptime_sec: float) -> list:
        """Собирает подробные диагностические строки по падению старта."""
        lines = []

        if exit_code is not None:
            lines.append(f"winws2 завершился с кодом {exit_code} через {uptime_sec:.1f}с")

        if exit_code == 87:
            lines.append("Код 87 (ERROR_INVALID_PARAMETER): вероятна ошибка параметра в конфиге или командной строке")

        if self.last_launch_config_path:
            lines.append(f"Конфиг запуска: {self.last_launch_config_path}")
            preview = self._get_config_preview_lines(self.last_launch_config_path, 6)
            if preview:
                lines.append("Фрагмент конфига:")
                lines.extend(preview)

        if self.last_launch_command:
            cmd_preview = " ".join(self.last_launch_command)
            if len(cmd_preview) > 500:
                cmd_preview = cmd_preview[:500] + " ..."
            lines.append(f"Команда: {cmd_preview}")

        lines.append(f"Рабочая папка: {self.zapret_path}")

        tail = self._get_recent_output_tail(8)
        if tail:
            lines.append("Последние строки winws2:")
            for line in tail:
                clean = str(line).strip()
                if len(clean) > 300:
                    clean = clean[:300] + " ..."
                lines.append(f"  • {clean}")
        else:
            lines.append("winws2 не успел вывести диагностические строки в stdout")

        if self.current_log_id:
            lines.append(f"Лог сессии: orchestra_{self.current_log_id}.log")

        return lines

    def _emit_startup_diagnostics(self, lines: list):
        """Пишет расширенную диагностику старта в лог и в callback UI."""
        if not lines:
            return

        for line in lines:
            if not line:
                continue
            log(f"[startup-diagnostics] {line}", "INFO")
            if self.output_callback:
                self.output_callback(f"[INFO] {line}")

    def _should_ignore_orchestra_host(self, hostname: Optional[str]) -> bool:
        """Возвращает True для целей, которые оркестратор обязан полностью игнорировать."""
        return is_orchestra_ignored_target(hostname or "")

    def _should_ignore_orchestra_event(self, event: ParsedEvent) -> bool:
        """Отбрасывает события для отдельного Telegram Proxy модуля до любой обработки."""
        host = (getattr(event, "hostname", None) or "").strip()
        if not self._should_ignore_orchestra_host(host):
            return False

        signature = f"{getattr(event.event_type, 'value', 'event')}:{host.lower()}"
        if signature not in self._ignored_runtime_targets_logged:
            self._ignored_runtime_targets_logged.add(signature)
            log(f"Оркестратор игнорирует Telegram Proxy цель: {host}", "DEBUG")

        return True

    def _purge_ignored_training_state(self) -> None:
        """
        Удаляет старые lock/history/blocked записи для Telegram Proxy.

        Это нужно, чтобы отдельный модуль Telegram не возвращался в обучение
        из старого реестра после того, как мы объявили его системно игнорируемым.
        """
        removed_locked = 0
        removed_user_locks = 0
        removed_history = 0
        removed_blocked = 0
        removed_user_blocked = 0

        for askey in ASKEY_ALL:
            locked_dict = self.locked_manager.locked_by_askey[askey]
            user_locked = self.locked_manager.user_locked_by_askey[askey]

            for hostname in list(locked_dict.keys()):
                if not self._should_ignore_orchestra_host(hostname):
                    continue
                del locked_dict[hostname]
                remove_orchestra_locked_target(askey, hostname)
                removed_locked += 1

            for hostname in list(user_locked):
                if not self._should_ignore_orchestra_host(hostname):
                    continue
                user_locked.discard(hostname)
                remove_orchestra_user_locked(askey, hostname)
                removed_user_locks += 1

            blocked_dict = self.blocked_manager.blocked_by_askey[askey]
            user_blocked = self.blocked_manager.user_blocked_by_askey[askey]

            for hostname in list(blocked_dict.keys()):
                if not self._should_ignore_orchestra_host(hostname):
                    continue
                del blocked_dict[hostname]
                remove_orchestra_user_blocked_target(askey, hostname)
                removed_blocked += 1

            for hostname in list(user_blocked.keys()):
                if not self._should_ignore_orchestra_host(hostname):
                    continue
                del user_blocked[hostname]
                remove_orchestra_user_blocked_target(askey, hostname)
                removed_user_blocked += 1

        for hostname in list(self.locked_manager.strategy_history.keys()):
            if not self._should_ignore_orchestra_host(hostname):
                continue
            del self.locked_manager.strategy_history[hostname]
            remove_orchestra_history_target(hostname)
            removed_history += 1

        total_removed = removed_locked + removed_user_locks + removed_history + removed_blocked + removed_user_blocked
        if total_removed:
            log(
                "Очищены legacy-данные Telegram Proxy из оркестратора: "
                f"locked={removed_locked}, user_locked={removed_user_locks}, "
                f"history={removed_history}, blocked={removed_blocked}, "
                f"user_blocked={removed_user_blocked}",
                "INFO",
            )

    def _forward_startup_raw_output(self, timestamp: str, line: str):
        """Прокидывает важные сырые строки winws2 в UI во время старта."""
        text = str(line or "").strip()
        if not text:
            return

        signature = " ".join(text.lower().split())
        if signature in self._startup_forwarded_signatures:
            return

        self._startup_forwarded_signatures.append(signature)
        msg = f"[{timestamp}] [WINWS2] {text}"
        log(f"[winws2 startup] {text}", "INFO")
        if self.output_callback:
            self.output_callback(msg)

    def _guess_start_failure_reason(self, exit_code: Optional[int] = None) -> str:
        """Пытается определить вероятную причину быстрого завершения процесса."""
        tail = "\n".join(self._recent_output_lines).lower()

        if exit_code == 87:
            return "некорректный параметр запуска (проверьте конфиг и параметры winws2)"

        checks = (
            (("windivert", "filter driver", "wd_filter"), "ошибка WinDivert (драйвер/доступ/занято)"),
            (("access is denied", "permission denied", "denied"), "недостаточно прав (запуск без администратора)"),
            (("no such file", "not found", "cannot open", "failed to open"), "не найден файл из конфигурации (lua/bin/lists)"),
            (("unknown option", "invalid option", "bad option", "invalid argument", "error_invalid_parameter"), "некорректный параметр в конфиге/команде"),
            (("lua", "syntax error", "runtime error", "stack traceback"), "ошибка Lua-скрипта"),
        )

        for tokens, reason in checks:
            if any(token in tail for token in tokens):
                return reason

        if exit_code == 0:
            return "процесс завершился сразу после старта"
        if exit_code is not None:
            return f"процесс завершился с кодом {exit_code}"
        return "процесс завершился сразу после запуска"

    def set_keep_debug_file(self, keep: bool):
        """Сохранять ли debug файл после остановки (для отладки)"""
        self.keep_debug_file = keep
        log(f"Debug файл будет {'сохранён' if keep else 'удалён'} после остановки", "DEBUG")

    def set_output_callback(self, callback: Callable[[str], None]):
        """Callback для получения строк лога"""
        self.output_callback = callback
        self.blocked_manager.set_output_callback(callback)
        self.locked_manager.set_output_callback(callback)

    def set_lock_callback(self, callback: Callable[[str, int], None]):
        """Callback при LOCK стратегии (hostname, strategy_num)"""
        self.lock_callback = callback
        self.locked_manager.set_lock_callback(callback)

    def set_unlock_callback(self, callback: Callable[[str], None]):
        """Callback при UNLOCK стратегии (hostname)"""
        self.unlock_callback = callback
        self.locked_manager.set_unlock_callback(callback)

    # ==================== LOG ROTATION METHODS ====================

    def _generate_log_id(self) -> str:
        """
        Генерирует уникальный ID для лог-файла.
        Формат: YYYYMMDD_HHMMSS (только timestamp для читаемости)
        """
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _generate_log_path(self, log_id: str) -> str:
        """Генерирует путь к лог-файлу по ID"""
        return os.path.join(self.logs_path, f"orchestra_{log_id}.log")

    def _get_all_orchestra_logs(self) -> List[dict]:
        """
        Возвращает список всех лог-файлов оркестратора.

        Returns:
            Список словарей с информацией о логах, отсортированный по дате (новые первые):
            [{'id': str, 'path': str, 'size': int, 'created': datetime, 'filename': str}, ...]
        """
        logs = []
        pattern = os.path.join(self.logs_path, "orchestra_*.log")

        for filepath in glob.glob(pattern):
            try:
                filename = os.path.basename(filepath)
                # Извлекаем ID из имени файла (orchestra_YYYYMMDD_HHMMSS_XXXX.log)
                log_id = filename.replace("orchestra_", "").replace(".log", "")

                stat = os.stat(filepath)

                # Парсим дату из ID (YYYYMMDD_HHMMSS)
                try:
                    created = datetime.strptime(log_id, "%Y%m%d_%H%M%S")
                except ValueError:
                    created = datetime.fromtimestamp(stat.st_mtime)

                logs.append({
                    'id': log_id,
                    'path': filepath,
                    'filename': filename,
                    'size': stat.st_size,
                    'created': created
                })
            except Exception as e:
                log(f"Ошибка чтения лог-файла {filepath}: {e}", "DEBUG")

        # Сортируем по дате создания (новые первые)
        logs.sort(key=lambda x: x['created'], reverse=True)
        return logs

    def _cleanup_old_logs(self) -> int:
        """
        Удаляет старые лог-файлы, оставляя только MAX_ORCHESTRA_LOGS штук.

        Returns:
            Количество удалённых файлов
        """
        logs = self._get_all_orchestra_logs()
        deleted = 0

        if len(logs) > MAX_ORCHESTRA_LOGS:
            # Удаляем самые старые (они в конце списка)
            logs_to_delete = logs[MAX_ORCHESTRA_LOGS:]

            for log_info in logs_to_delete:
                try:
                    os.remove(log_info['path'])
                    deleted += 1
                    log(f"Удалён старый лог: {log_info['filename']}", "DEBUG")
                except Exception as e:
                    log(f"Ошибка удаления лога {log_info['filename']}: {e}", "DEBUG")

        if deleted:
            log(f"Ротация логов оркестратора: удалено {deleted} файлов", "INFO")

        return deleted

    def get_log_history(self) -> List[dict]:
        """
        Возвращает историю логов для UI.

        Returns:
            Список словарей с информацией о логах (без полного пути)
        """
        logs = self._get_all_orchestra_logs()
        return [{
            'id': l['id'],
            'filename': l['filename'],
            'size': l['size'],
            'size_str': self._format_size(l['size']),
            'created': l['created'].strftime("%Y-%m-%d %H:%M:%S"),
            'is_current': l['id'] == self.current_log_id
        } for l in logs]

    def _format_size(self, size: int) -> str:
        """Форматирует размер файла в человекочитаемый вид"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def get_log_content(self, log_id: str) -> Optional[str]:
        """
        Возвращает содержимое лог-файла по ID.

        Args:
            log_id: ID лога

        Returns:
            Содержимое файла или None
        """
        log_path = self._generate_log_path(log_id)
        if not os.path.exists(log_path):
            return None

        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            log(f"Ошибка чтения лога {log_id}: {e}", "DEBUG")
            return None

    def delete_log(self, log_id: str) -> bool:
        """
        Удаляет лог-файл по ID.

        Args:
            log_id: ID лога

        Returns:
            True если удаление успешно
        """
        # Нельзя удалить текущий активный лог
        if log_id == self.current_log_id and self.is_running():
            log(f"Нельзя удалить активный лог: {log_id}", "WARNING")
            return False

        log_path = self._generate_log_path(log_id)
        if not os.path.exists(log_path):
            return False

        try:
            os.remove(log_path)
            log(f"Удалён лог: orchestra_{log_id}.log", "INFO")
            return True
        except Exception as e:
            log(f"Ошибка удаления лога {log_id}: {e}", "ERROR")
            return False

    def clear_all_logs(self) -> int:
        """
        Удаляет все лог-файлы оркестратора (кроме текущего активного).

        Returns:
            Количество удалённых файлов
        """
        logs = self._get_all_orchestra_logs()
        deleted = 0

        for log_info in logs:
            # Пропускаем текущий активный лог
            if log_info['id'] == self.current_log_id and self.is_running():
                continue

            try:
                os.remove(log_info['path'])
                deleted += 1
            except Exception:
                pass

        if deleted:
            log(f"Удалено {deleted} лог-файлов оркестратора", "INFO")

        return deleted

    def _create_startup_info(self):
        """Создает STARTUPINFO для скрытого запуска"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
        return startupinfo

    def load_existing_strategies(self) -> Dict[str, int]:
        """Загружает ранее сохраненные стратегии и историю из реестра"""
        # Загружаем blocked сначала (нужен для проверки конфликтов в locked)
        self.blocked_manager.load()

        # Загружаем locked стратегии (включая историю)
        self.locked_manager.load()
        self._purge_ignored_training_state()

        # Возвращаем TLS стратегии для backward compatibility
        return self.locked_manager.locked_by_askey["tls"]

    def _generate_learned_lua(self) -> Optional[str]:
        """
        Генерирует learned-strategies.lua для предзагрузки в strategy-stats.lua.
        Этот файл хранится по пути /home/privacy/zapret/lua/strategy-stats.lua
        Вызывает strategy_preload() и strategy_preload_history() для каждого домена.

        Returns:
            Путь к файлу или None если нет данных
        """
        # Проверяем наличие данных по всем askey профилям
        has_any_locked = any(self.locked_manager.locked_by_askey[askey] for askey in ASKEY_ALL)
        has_history = bool(self.locked_manager.strategy_history)
        has_blocked = bool(self.blocked_manager.blocked_strategies)

        if not has_any_locked and not has_history and not has_blocked:
            return None

        lua_path = os.path.join(self.lua_path, "learned-strategies.lua")

        # Собираем статистику по всем askey
        counts = {askey: len(self.locked_manager.locked_by_askey[askey]) for askey in ASKEY_ALL}
        total_locked = sum(counts.values())
        total_history = len(self.locked_manager.strategy_history)

        stats_str = ", ".join(f"{askey.upper()}: {cnt}" for askey, cnt in counts.items() if cnt > 0)
        log(f"Генерация learned-strategies.lua: {lua_path}", "DEBUG")
        log(f"  {stats_str or 'пусто'}", "DEBUG")

        try:
            with open(lua_path, 'w', encoding='utf-8') as f:
                f.write("-- Auto-generated: preload strategies from registry\n")
                f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"-- {stats_str or 'empty'}, History: {total_history}\n\n")

                # Генерируем blocked стратегии через slm_preload_blocked(askey, hostname, strategies)
                # Функция slm_is_blocked() теперь определена в strategy-lock-manager.lua
                # ВАЖНО: blocked применяется ко всем TCP профилям (tls, http, mtproto)
                blocked_strategies = self.blocked_manager.blocked_strategies
                if blocked_strategies:
                    f.write("-- Blocked strategies (default + user-defined)\n")
                    f.write("-- Function slm_is_blocked() is defined in strategy-lock-manager.lua\n")
                    f.write("-- Format: slm_preload_blocked(askey, hostname, {strategies})\n")
                    for hostname, strategies in blocked_strategies.items():
                        safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"').lower()
                        strat_set = "{" + ", ".join(str(s) for s in strategies) + "}"
                        # Применяем blocked ко всем TCP профилям
                        for tcp_askey in TCP_ASKEYS:
                            f.write(f'slm_preload_blocked("{tcp_askey}", "{safe_host}", {strat_set})\n')
                    f.write("\n")
                else:
                    f.write("-- No blocked strategies\n\n")

                # Предзагрузка locked стратегий для всех 9 askey профилей
                blocked_counts = {askey: 0 for askey in ASKEY_ALL}
                for askey in ASKEY_ALL:
                    for hostname, strategy in self.locked_manager.locked_by_askey[askey].items():
                        is_user = hostname in self.locked_manager.user_locked_by_askey[askey]
                        # User locks НЕ пропускаем даже если стратегия заблокирована
                        if not is_user and self.blocked_manager.is_blocked(hostname, strategy):
                            blocked_counts[askey] += 1
                            continue
                        safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                        # askey первым параметром: slm_preload_locked(askey, hostname, strategy, is_user)
                        f.write(f'slm_preload_locked("{askey}", "{safe_host}", {strategy}, {"true" if is_user else "false"})\n')

                # Для доменов с заблокированной s1 из истории, которые НЕ залочены - preload с лучшей стратегией
                blocked_from_history = 0
                tls_locked = self.locked_manager.locked_by_askey["tls"]
                http_locked = self.locked_manager.locked_by_askey["http"]
                for hostname in self.locked_manager.strategy_history.keys():
                    # Пропускаем если уже залочен (обработан выше)
                    if hostname in tls_locked or hostname in http_locked:
                        continue
                    # Только для доменов с заблокированной strategy=1
                    if not self.blocked_manager.is_blocked(hostname, 1):
                        continue
                    # Находим лучшую стратегию (исключая strategy=1 и другие заблокированные)
                    best_strat = self.locked_manager.get_best_strategy_from_history(hostname, exclude_strategy=1)
                    if not best_strat:
                        continue
                    # Дополнительная защита: если стратегия заблокирована — пропускаем
                    if self.blocked_manager.is_blocked(hostname, best_strat):
                        continue
                    safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                    # askey первым параметром: slm_preload_locked(askey, hostname, strategy)
                    f.write(f'slm_preload_locked("tls", "{safe_host}", {best_strat})\n')
                    blocked_from_history += 1
                if blocked_from_history > 0:
                    log(f"Добавлено {blocked_from_history} доменов из истории (s1 заблокирована)", "DEBUG")

                # Предзагрузка истории (фильтруем заблокированные стратегии)
                # TODO: в будущем история может хранить askey для разных протоколов
                # Пока используем "tls" по умолчанию для всей истории
                history_skipped = 0
                for hostname, strategies in self.locked_manager.strategy_history.items():
                    safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                    for strat_key, data in strategies.items():
                        strat_num = int(strat_key) if isinstance(strat_key, str) else strat_key
                        # Пропускаем заблокированные стратегии
                        if self.blocked_manager.is_blocked(hostname, strat_num):
                            history_skipped += 1
                            continue
                        s = data.get('successes') or 0
                        f_count = data.get('failures') or 0
                        # askey первым параметром: slm_preload_history(askey, hostname, strategy, successes, failures)
                        f.write(f'slm_preload_history("tls", "{safe_host}", {strat_key}, {s}, {f_count})\n')
                if history_skipped > 0:
                    log(f"Пропущено {history_skipped} записей истории (заблокированы)", "DEBUG")

                # Подсчёт статистики
                total_blocked = sum(blocked_counts.values())
                actual_locked = total_locked - total_blocked
                f.write(f'\nDLOG("learned-strategies: loaded {actual_locked} strategies + {total_history} history (blocked: {total_blocked})")\n')

                # Install circular wrapper to apply preloaded strategies
                f.write('\n-- Install circular wrapper to apply preloaded strategies on first packet\n')
                f.write('install_circular_wrapper()\n')
                f.write('DLOG("learned-strategies: wrapper installed, circular=" .. tostring(circular ~= nil) .. ", original=" .. tostring(original_circular ~= nil))\n')

                # Debug: wrap circular again to see why APPLIED doesn't work
                f.write('\n-- DEBUG: extra wrapper to diagnose APPLIED issue\n')
                f.write('if circular and working_strategies then\n')
                f.write('    local _debug_circular = circular\n')
                f.write('    circular = function(ctx, desync)\n')
                f.write('        local hostname = standard_hostkey and standard_hostkey(desync) or "?"\n')
                f.write('        local askey = (desync and desync.arg and desync.arg.key and #desync.arg.key>0) and desync.arg.key or (desync and desync.func_instance or "?")\n')
                f.write('        local data = working_strategies[hostname]\n')
                f.write('        if data then\n')
                f.write('            local expected = get_autostate_key_by_payload and get_autostate_key_by_payload(data.payload_type) or "?"\n')
                f.write('            DLOG("DEBUG circular: host=" .. hostname .. " askey=" .. askey .. " expected=" .. expected .. " locked=" .. tostring(data.locked) .. " applied=" .. tostring(data.applied))\n')
                f.write('        end\n')
                f.write('        return _debug_circular(ctx, desync)\n')
                f.write('    end\n')
                f.write('    DLOG("learned-strategies: DEBUG wrapper installed")\n')
                f.write('end\n')

                # Wrap circular to skip blocked strategies during rotation
                # slm_is_blocked() is now defined in strategy-lock-manager.lua
                if blocked_strategies:
                    f.write('\n-- Install blocked strategies filter for circular rotation\n')
                    f.write('-- slm_is_blocked() is defined in strategy-lock-manager.lua\n')
                    f.write('local _blocked_wrap_installed = false\n')
                    f.write('local function install_blocked_filter()\n')
                    f.write('    if _blocked_wrap_installed then return end\n')
                    f.write('    _blocked_wrap_installed = true\n')
                    f.write('    if circular and type(circular) == "function" then\n')
                    f.write('        local original_circular = circular\n')
                    f.write('        circular = function(t, hostname, ...)\n')
                    f.write('            local result = original_circular(t, hostname, ...)\n')
                    f.write('            if result and hostname and slm_is_blocked(hostname, result) then\n')
                    f.write('                local max_skip = 10\n')
                    f.write('                for i = 1, max_skip do\n')
                    f.write('                    result = original_circular(t, hostname, ...)\n')
                    f.write('                    if not result or not slm_is_blocked(hostname, result) then break end\n')
                    f.write('                    DLOG("BLOCKED: skip strategy " .. result .. " for " .. hostname)\n')
                    f.write('                end\n')
                    f.write('            end\n')
                    f.write('            return result\n')
                    f.write('        end\n')
                    f.write('        DLOG("Blocked strategies filter installed for circular")\n')
                    f.write('    end\n')
                    f.write('end\n')
                    f.write('install_blocked_filter()\n')

            block_info = f", заблокировано {total_blocked}" if total_blocked > 0 else ""
            log(f"Сгенерирован learned-strategies.lua ({total_locked} locked + {total_history} history{block_info})", "DEBUG")
            return lua_path

        except Exception as e:
            log(f"Ошибка генерации learned-strategies.lua: {e}", "ERROR")
            return None

    # REMOVED: _generate_single_numbered_file() - стратегии теперь встроены в circular-config.txt
    # REMOVED: _generate_numbered_strategies() - стратегии теперь встроены в circular-config.txt

    def _read_output(self):
        """Поток чтения stdout от winws2 с использованием LogParser"""
        parser = LogParser()
        history_save_counter = 0
        log_line_counter = 0  # Счётчик строк для периодической проверки размера файла

        # Открываем файл для записи сырого debug лога (для отправки в техподдержку)
        log_file = None
        if self.debug_log_path:
            try:
                log_file = open(self.debug_log_path, 'w', encoding='utf-8', buffering=1)  # line buffered
                log_file.write(f"=== Orchestra Debug Log Started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            except Exception as e:
                log(f"Не удалось открыть лог-файл: {e}", "WARNING")

        if self.running_process and self.running_process.stdout:
            try:
                for line in self.running_process.stdout:
                    if self.stop_event.is_set():
                        break

                    line = line.rstrip()
                    if not line:
                        continue

                    timestamp = datetime.now().strftime("%H:%M:%S")

                    self._remember_output_line(line)

                    # Записываем в debug лог
                    if log_file:
                        try:
                            log_file.write(f"{line}\n")
                            log_line_counter += 1

                            # Периодически проверяем размер файла
                            if log_line_counter >= LOG_SIZE_CHECK_INTERVAL:
                                log_line_counter = 0
                                try:
                                    log_file.flush()
                                    file_size = os.path.getsize(self.debug_log_path)
                                    if file_size > MAX_LOG_SIZE_BYTES:
                                        # Файл превысил лимит - очищаем
                                        log_file.close()
                                        log_file = open(self.debug_log_path, 'w', encoding='utf-8', buffering=1)
                                        log_file.write(f"=== Log truncated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (exceeded {MAX_LOG_SIZE_BYTES // (1024*1024*1024)} GB) ===\n")
                                        log(f"Лог-файл оркестратора очищен (превышен лимит {MAX_LOG_SIZE_BYTES // (1024*1024*1024)} ГБ)", "INFO")
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    # Парсим строку
                    event = parser.parse_line(line)
                    if not event:
                        if self._is_startup_phase() and self._looks_like_error_output_line(line):
                            self._forward_startup_raw_output(timestamp, line)
                        continue

                    if self._should_ignore_orchestra_event(event):
                        continue

                    is_udp = event.l7proto in ("udp", "quic", "stun", "discord", "wireguard", "dht", "unknown")

                    # === LOCK ===
                    if event.event_type == EventType.LOCK:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"

                        # Пропускаем заблокированные стратегии
                        if self.blocked_manager.is_blocked(host, strat):
                            continue

                        # Маппинг l7proto -> askey
                        askey = PROTO_TO_ASKEY.get(proto, proto if proto in ASKEY_ALL else "tls")

                        # Пропускаем user locks - их нельзя перезаписать auto-lock
                        if self.locked_manager.is_user_locked(host, askey):
                            log(f"SKIP auto-lock: {host} has user lock [{askey.upper()}]", "DEBUG")
                            continue

                        # Protocol tag and port for UI
                        if askey in UDP_ASKEYS:
                            proto_tag = f"[{askey.upper()}]"
                            port_str = ""
                        elif askey == "http":
                            proto_tag = "[HTTP]"
                            port_str = ":80"
                        else:
                            proto_tag = f"[{askey.upper()}]"
                            port_str = ":443" if askey in TCP_ASKEYS else ""

                        target_dict = self.locked_manager.locked_by_askey[askey]
                        if host not in target_dict or target_dict[host] != strat:
                            target_dict[host] = strat
                            msg = f"[{timestamp}] {proto_tag} 🔒 LOCKED: {host}{port_str} = strategy {strat}"
                            log(msg, "INFO")
                            if self.output_callback:
                                self.output_callback(msg)
                            if self.lock_callback:
                                self.lock_callback(host, strat)
                            self.locked_manager.save()
                        continue

                    # === UNLOCK ===
                    if event.event_type == EventType.UNLOCK:
                        host = (event.hostname or "").strip().lower()
                        proto = (event.l7proto or "tls").strip().lower()
                        askey = PROTO_TO_ASKEY.get(proto, proto if proto in ASKEY_ALL else "tls")
                        removed = False

                        if not host:
                            continue

                        # Ищем хост во всех askey профилях и удаляем.
                        # IMPORTANT: do NOT auto-unlock user-locked entries.
                        for ak in ASKEY_ALL:
                            target_dict = self.locked_manager.locked_by_askey[ak]
                            if host in target_dict:
                                try:
                                    if self.locked_manager.is_user_locked(host, ak):
                                        # User explicitly pinned this domain; ignore AUTO-UNLOCK/UNLOCK from Lua.
                                        log(f"SKIP auto-unlock: {host} has user lock [{ak.upper()}]", "INFO")
                                        continue
                                except Exception:
                                    pass

                                del target_dict[host]
                                removed = True
                                proto_tag = f"[{ak.upper()}]"
                                port_str = ":443" if ak == "tls" else (":80" if ak == "http" else "")
                                msg = f"[{timestamp}] {proto_tag} 🔓 UNLOCKED: {host}{port_str} - re-learning..."
                                log(msg, "INFO")
                                if self.output_callback:
                                    self.output_callback(msg)
                                if self.unlock_callback:
                                    self.unlock_callback(host)
                        if removed:
                            self.locked_manager.save()
                        continue

                    # === RESET ===
                    if event.event_type == EventType.RESET:
                        host = event.hostname
                        msg = f"[{timestamp}] 🔄 RESET: {host} - statistics cleared"
                        log(msg, "INFO")
                        if self.output_callback:
                            self.output_callback(msg)
                        continue

                    # === APPLIED ===
                    if event.event_type == EventType.APPLIED:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"
                        prev = parser.last_applied.get((host, proto))

                        # Protocol tag for APPLIED
                        if is_udp:
                            proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                        elif proto == "http":
                            proto_tag = "[HTTP]"
                        else:
                            proto_tag = "[TLS]"

                        if prev is None or prev != strat:
                            if prev is None:
                                msg = f"[{timestamp}] {proto_tag} 🎯 APPLIED: {host} = strategy {strat}"
                            else:
                                msg = f"[{timestamp}] {proto_tag} 🔄 APPLIED: {host} {prev} → {strat}"
                            if self.output_callback:
                                self.output_callback(msg)
                        continue

                    # === SUCCESS (from strategy_quality) ===
                    if event.event_type == EventType.SUCCESS and event.total is not None:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"

                        if host and strat:
                            self.locked_manager.increment_history(host, strat, is_success=True)
                            history_save_counter += 1

                            # Сброс счётчика Discord FAIL при SUCCESS
                            if "discord" in host.lower() and self.discord_fail_count > 0:
                                self.discord_fail_count = 0

                            # Protocol tag for clear identification
                            if is_udp:
                                proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                                port_str = ""
                            elif proto == "http":
                                proto_tag = "[HTTP]"
                                port_str = ":80"
                            else:
                                proto_tag = "[TLS]"
                                port_str = ":443"
                            msg = f"[{timestamp}] {proto_tag} ✓ SUCCESS: {host}{port_str} strategy={strat} ({event.successes}/{event.total})"
                            if self.output_callback:
                                self.output_callback(msg)

                            if history_save_counter >= 5:
                                self.locked_manager.save_history()
                                history_save_counter = 0
                        continue

                    # === SUCCESS (from std_success_detector) ===
                    if event.event_type == EventType.SUCCESS:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"

                        if host and strat and not self.blocked_manager.is_blocked(host, strat):
                            self.locked_manager.increment_history(host, strat, is_success=True)
                            history_save_counter += 1

                            # Сброс счётчика Discord FAIL при SUCCESS
                            if "discord" in host.lower() and self.discord_fail_count > 0:
                                self.discord_fail_count = 0

                            # Protocol tag for clear identification
                            if is_udp:
                                proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                                port_str = ""
                            elif proto == "http":
                                proto_tag = "[HTTP]"
                                port_str = ":80"
                            else:
                                proto_tag = "[TLS]"
                                port_str = ":443"

                            # Auto-LOCK после успехов
                            host_key = f"{host}:{strat}"
                            if not hasattr(self, '_success_counts'):
                                self._success_counts = {}
                            self._success_counts[host_key] = self._success_counts.get(host_key, 0) + 1

                            lock_threshold = 1 if is_udp else 3
                            if self._success_counts[host_key] >= lock_threshold:
                                # Маппинг l7proto -> askey
                                askey = PROTO_TO_ASKEY.get(proto, proto if proto in ASKEY_ALL else "tls")

                                # Пропускаем user locks - их нельзя перезаписать auto-lock
                                if self.locked_manager.is_user_locked(host, askey):
                                    log(f"SKIP auto-lock: {host} has user lock [{askey.upper()}]", "DEBUG")
                                else:
                                    target_dict = self.locked_manager.locked_by_askey[askey]

                                    if host not in target_dict or target_dict[host] != strat:
                                        target_dict[host] = strat
                                        msg = f"[{timestamp}] {proto_tag} 🔒 LOCKED: {host}{port_str} = strategy {strat}"
                                        log(msg, "INFO")
                                        if self.output_callback:
                                            self.output_callback(msg)
                                        self.locked_manager.save()
                                        self.locked_manager.save_history()
                                        history_save_counter = 0

                            msg = f"[{timestamp}] {proto_tag} ✓ SUCCESS: {host}{port_str} strategy={strat}"
                            if self.output_callback:
                                self.output_callback(msg)

                            if history_save_counter >= 5:
                                self.locked_manager.save_history()
                                history_save_counter = 0
                        continue

                    # === FAIL ===
                    if event.event_type == EventType.FAIL:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"

                        if host and strat:
                            self.locked_manager.increment_history(host, strat, is_success=False)
                            history_save_counter += 1

                            # Protocol tag for clear identification
                            if is_udp:
                                proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                                port_str = ""
                            elif proto == "http":
                                proto_tag = "[HTTP]"
                                port_str = ":80"
                            else:
                                proto_tag = "[TLS]"
                                port_str = ":443"
                            msg = f"[{timestamp}] {proto_tag} ✗ FAIL: {host}{port_str} strategy={strat} ({event.successes}/{event.total})"
                            if self.output_callback:
                                self.output_callback(msg)

                            # Проверяем Discord FAIL для авторестарта Discord (с подсчётом фейлов)
                            if self.auto_restart_on_discord_fail and "discord" in host.lower():
                                self.discord_fail_count += 1
                                log(f"Discord FAIL #{self.discord_fail_count}/{self.discord_fails_threshold} ({host})", "DEBUG")
                                if self.discord_fail_count >= self.discord_fails_threshold:
                                    log(f"🔄 Достигнут порог Discord FAIL ({self.discord_fail_count}), перезапускаю Discord...", "WARNING")
                                    if self.output_callback:
                                        self.output_callback(f"[{timestamp}] ⚠️ Discord FAIL x{self.discord_fail_count} - перезапуск Discord...")
                                    if self.restart_callback:
                                        # Вызываем callback для перезапуска Discord (через главный поток)
                                        self.restart_callback()
                                    self.discord_fail_count = 0  # Сброс после рестарта

                            if history_save_counter >= 5:
                                self.locked_manager.save_history()
                                history_save_counter = 0
                        continue

                    # === ROTATE ===
                    if event.event_type == EventType.ROTATE:
                        host = event.hostname or parser.current_host
                        proto = event.l7proto or "tls"
                        # Protocol tag for rotate
                        if is_udp:
                            proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                        elif proto == "http":
                            proto_tag = "[HTTP]"
                        else:
                            proto_tag = "[TLS]"
                        msg = f"[{timestamp}] {proto_tag} 🔄 Strategy rotated to {event.strategy}"
                        if host:
                            msg += f" ({host})"
                        if self.output_callback:
                            self.output_callback(msg)
                        continue

                    # === RST ===
                    if event.event_type == EventType.RST:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"
                        # Protocol tag for RST
                        if is_udp:
                            proto_tag = f"[{proto.upper()}]" if proto else "[UDP]"
                            port_str = ""
                        elif proto == "http":
                            proto_tag = "[HTTP]"
                            port_str = ":80"
                        else:
                            proto_tag = "[TLS]"
                            port_str = ":443"

                        if host and strat:
                            msg = f"[{timestamp}] {proto_tag} ⚡ RST detected: {host}{port_str} strategy={strat}"
                        elif host:
                            msg = f"[{timestamp}] {proto_tag} ⚡ RST detected: {host}{port_str}"
                        else:
                            msg = f"[{timestamp}] {proto_tag} ⚡ RST detected - DPI block"
                        if self.output_callback:
                            self.output_callback(msg)
                        continue

                    # === HISTORY ===
                    if event.event_type == EventType.HISTORY:
                        self.locked_manager.update_history(event.hostname, event.strategy, event.successes, event.failures)
                        # Не спамим UI историей - данные и так сохраняются
                        # msg = f"[{timestamp}] HISTORY: {event.hostname} strat={event.strategy} ({event.successes}✓/{event.failures}✗) = {event.rate}%"
                        # if self.output_callback:
                        #     self.output_callback(msg)
                        self.locked_manager.save_history()
                        continue

                    # === PRELOADED ===
                    if event.event_type == EventType.PRELOADED:
                        proto_str = f" [{event.l7proto}]" if event.l7proto else ""
                        msg = f"[{timestamp}] PRELOADED: {event.hostname} = strategy {event.strategy}{proto_str}"
                        if self.output_callback:
                            self.output_callback(msg)
                        continue

            except Exception as e:
                import traceback
                log(f"Read output error: {e}", "DEBUG")
                log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            finally:
                # Закрываем лог-файл
                if log_file:
                    try:
                        log_file.write(f"=== Orchestra Debug Log Ended {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                        log_file.close()
                    except Exception:
                        pass
                # Сохраняем историю при завершении
                if self.locked_manager.strategy_history:
                    self.locked_manager.save_history()

                # Диагностика неожиданного завершения процесса
                process = self.running_process
                if process and not self.stop_event.is_set():
                    try:
                        exit_code = process.poll()
                    except Exception:
                        exit_code = None

                    if exit_code is not None:
                        uptime_sec = 0.0
                        if self.last_start_attempt_ts > 0:
                            uptime_sec = max(0.0, time.monotonic() - self.last_start_attempt_ts)

                        reason = self._guess_start_failure_reason(exit_code)
                        diagnostics = self._build_startup_diagnostics(exit_code, uptime_sec)
                        self.last_exit_info = {
                            "exit_code": int(exit_code),
                            "uptime_sec": round(uptime_sec, 2),
                            "reason": reason,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "config_path": self.last_launch_config_path,
                            "command": list(self.last_launch_command),
                            "recent_output": self._get_recent_output_tail(8),
                        }

                        message = (
                            f"Оркестратор завершился (код: {exit_code}, аптайм: {uptime_sec:.1f}с). "
                            f"Причина: {reason}"
                        )
                        log(message, "❌ ERROR")
                        if self.output_callback:
                            self.output_callback(f"[❌ ERROR] {message}")

                        self._emit_startup_diagnostics(diagnostics)

                        if uptime_sec < 3.0:
                            self.last_start_error = message

    def prepare(self) -> bool:
        """
        Проверяет наличие всех необходимых файлов.

        Returns:
            True если все файлы на месте
        """
        # Проверяем winws2.exe
        if not os.path.exists(self.winws_exe):
            log(f"winws2.exe не найден: {self.winws_exe}", "ERROR")
            return False

        # Проверяем Lua файлы
        required_lua_files = [
            "zapret-lib.lua",
            "zapret-antidpi.lua",
            "zapret-auto.lua",
            "silent-drop-detector.lua",
            "strategy-stats.lua",
            "combined-detector.lua",
        ]

        missing = []
        for lua_file in required_lua_files:
            path = os.path.join(self.lua_path, lua_file)
            if not os.path.exists(path):
                missing.append(lua_file)

        if missing:
            log(f"Отсутствуют Lua файлы: {', '.join(missing)}", "ERROR")
            return False

        if not os.path.exists(self.config_path):
            log(f"Конфиг не найден: {self.config_path}", "ERROR")
            return False

        self._prepare_launch_config_path()

        # Генерируем whitelist.txt (динамический - пользователь добавляет домены)
        self._generate_whitelist_file()

        log("Оркестратор готов к запуску", "INFO")
        log("ℹ️ Оркестратор видит только НОВЫЕ соединения. Для тестирования:", "INFO")
        log("   • Перезапустите браузер или откройте приватное окно", "INFO")
        log("   • Очистите кэш (Ctrl+Shift+Del)", "INFO")
        log("   • Принудительная перезагрузка (Ctrl+F5)", "INFO")
        return True

    def _prepare_launch_config_path(self) -> str:
        """Prepares runtime config with strategy tags while keeping source clean."""
        self.launch_config_path = self.config_path

        try:
            with open(self.config_path, "r", encoding="utf-8", errors="replace") as f:
                source_content = f.read()
        except Exception:
            return self.launch_config_path

        cleaned_source = strip_strategy_tags(source_content)
        if cleaned_source != source_content:
            try:
                with open(self.config_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(cleaned_source)
                log("circular-config.txt очищен от legacy :strategy=N тегов", "DEBUG")
            except Exception as e:
                log(f"Не удалось очистить {self.config_path}: {e}", "DEBUG")

        runtime_content = renumber_circular_strategies(cleaned_source)
        if runtime_content == cleaned_source:
            return self.launch_config_path

        try:
            with open(self.runtime_config_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(runtime_content)
            self.launch_config_path = self.runtime_config_path
        except Exception as e:
            log(f"Не удалось создать runtime-конфиг {self.runtime_config_path}: {e}", "WARNING")
            self.launch_config_path = self.config_path

        return self.launch_config_path

    def start(self) -> bool:
        """
        Запускает оркестратор.

        Returns:
            True если запуск успешен
        """
        if self.is_running():
            log("Оркестратор уже запущен", "WARNING")
            return False

        if not self.prepare():
            self.last_start_error = "Оркестратор не готов к запуску (проверьте lua/exe/config файлы)"
            return False

        self.last_start_error = ""
        self.last_exit_info = None
        self._recent_output_lines.clear()
        self.last_start_attempt_ts = 0.0
        self.last_launch_config_path = ""
        self.last_launch_command = []
        self._startup_forwarded_signatures.clear()

        # Загружаем предыдущие стратегии и историю из реестра
        self.load_existing_strategies()

        # Инициализируем счётчики успехов из истории
        # Для доменов которые уже в locked - не важно (не будет повторного LOCK)
        # Для доменов в истории но не locked - продолжаем с сохранённого значения
        self._success_counts = {}
        for hostname, strategies in self.locked_manager.strategy_history.items():
            for strat_key, data in strategies.items():
                successes = data.get('successes') or 0
                if successes > 0:
                    host_key = f"{hostname}:{strat_key}"
                    self._success_counts[host_key] = successes

        # Логируем загруженные данные
        counts = {askey: len(self.locked_manager.locked_by_askey[askey]) for askey in ASKEY_ALL}
        total_locked = sum(counts.values())
        total_history = len(self.locked_manager.strategy_history)
        if total_locked or total_history:
            stats_str = ", ".join(f"{askey.upper()}: {cnt}" for askey, cnt in counts.items() if cnt > 0)
            log(f"Загружено из реестра: {stats_str or 'пусто'}, история для {total_history} доменов", "INFO")

        # Генерируем уникальный ID для этой сессии логов
        self.current_log_id = self._generate_log_id()
        self.debug_log_path = self._generate_log_path(self.current_log_id)
        log(f"Создан лог-файл: orchestra_{self.current_log_id}.log", "DEBUG")

        # Выполняем ротацию старых логов
        self._cleanup_old_logs()

        # Сбрасываем stop event
        self.stop_event.clear()

        # Генерируем learned-strategies.lua для предзагрузки в strategy-stats.lua
        learned_lua = self._generate_learned_lua()

        try:
            launch_config_path = self.launch_config_path or self.config_path

            # Запускаем winws2 с @config_file
            cmd = [self.winws_exe, f"@{launch_config_path}"]

            # Добавляем предзагрузку стратегий из реестра
            if learned_lua:
                cmd.append(f"--lua-init=@{learned_lua}")

            # Debug: выводим в stdout для парсинга, записываем в файл вручную в _read_output
            cmd.append("--debug=1")

            log_msg = f"Запуск: winws2.exe @{os.path.basename(launch_config_path)}"
            if total_locked:
                log_msg += f" ({total_locked} стратегий из реестра)"
            log(log_msg, "INFO")
            log(f"Командная строка: {' '.join(cmd)}", "DEBUG")

            self.last_launch_config_path = launch_config_path
            self.last_launch_command = list(cmd)

            self.last_start_attempt_ts = time.monotonic()

            self.running_process = subprocess.Popen(
                cmd,
                cwd=self.zapret_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=self._create_startup_info(),
                creationflags=CREATE_NO_WINDOW,
                text=True,
                bufsize=1
            )

            # Чтение stdout (парсим LOCKED/UNLOCKING для UI)
            self.output_thread = threading.Thread(target=self._read_output, daemon=True)
            self.output_thread.start()

            # Подтверждаем, что процесс пережил стартовое окно.
            startup_alive_sec = 1.2
            startup_timeout_sec = 3.0
            deadline = self.last_start_attempt_ts + startup_timeout_sec

            while time.monotonic() < deadline:
                if not self.running_process:
                    self.last_start_error = "Оркестратор не создал процесс"
                    log(self.last_start_error, "ERROR")
                    return False

                exit_code = self.running_process.poll()
                if exit_code is not None:
                    uptime_sec = max(0.0, time.monotonic() - self.last_start_attempt_ts)
                    reason = self._guess_start_failure_reason(exit_code)
                    diagnostics = self._build_startup_diagnostics(exit_code, uptime_sec)
                    self.last_start_error = (
                        f"Оркестратор завершился сразу после запуска (код: {exit_code}, "
                        f"аптайм: {uptime_sec:.1f}с). Причина: {reason}"
                    )
                    self.last_exit_info = {
                        "exit_code": int(exit_code),
                        "uptime_sec": round(uptime_sec, 2),
                        "reason": reason,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "config_path": self.last_launch_config_path,
                        "command": list(self.last_launch_command),
                        "recent_output": self._get_recent_output_tail(8),
                    }
                    log(self.last_start_error, "ERROR")
                    if self.output_callback:
                        self.output_callback(f"[❌ ERROR] {self.last_start_error}")
                    self._emit_startup_diagnostics(diagnostics)
                    self.running_process = None
                    return False

                if time.monotonic() - self.last_start_attempt_ts >= startup_alive_sec:
                    break

                time.sleep(0.1)

            log(f"Оркестратор запущен (PID: {self.running_process.pid})", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] Оркестратор запущен (PID: {self.running_process.pid})")
                self.output_callback(f"[INFO] Лог сессии: {self.current_log_id}")
                tls_count = len(self.locked_manager.locked_by_askey["tls"])
                if tls_count:
                    self.output_callback(f"[INFO] Загружено {tls_count} TLS стратегий")

            return True

        except Exception as e:
            self.last_start_error = f"Ошибка запуска оркестратора: {e}"
            log(self.last_start_error, "ERROR")
            return False

    def stop(self) -> bool:
        """
        Останавливает оркестратор.

        Returns:
            True если остановка успешна
        """
        if not self.is_running():
            log("Оркестратор не запущен", "DEBUG")
            return True

        try:
            self.stop_event.set()

            self.running_process.terminate()
            try:
                self.running_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.running_process.kill()
                self.running_process.wait()

            # Сохраняем стратегии и историю
            self.locked_manager.save()
            self.locked_manager.save_history()

            # Лог оркестратора всегда сохраняется (для отправки в техподдержку)
            # Ротация старых логов выполняется при следующем запуске (_cleanup_old_logs)

            tls_saved = len(self.locked_manager.locked_by_askey["tls"])
            history_saved = len(self.locked_manager.strategy_history)
            log(f"Оркестратор остановлен. Сохранено {tls_saved} TLS стратегий, история для {history_saved} доменов", "INFO")
            if self.current_log_id:
                log(f"Лог сессии сохранён: orchestra_{self.current_log_id}.log", "DEBUG")

            if self.output_callback:
                self.output_callback(f"[INFO] Оркестратор остановлен")
                if self.current_log_id:
                    self.output_callback(f"[INFO] Лог сохранён: {self.current_log_id}")

            # Сбрасываем ID текущего лога
            self.current_log_id = None
            self.running_process = None
            return True

        except Exception as e:
            log(f"Ошибка остановки оркестратора: {e}", "ERROR")
            return False

    def restart(self) -> bool:
        """
        Перезапускает оркестратор (stop + start).
        Используется после изменения чёрного списка в UI.

        Returns:
            True если перезапуск успешен
        """
        was_running = self.is_running()

        if was_running:
            log("Перезапуск оркестратора...", "INFO")
            if self.output_callback:
                self.output_callback("[INFO] Перезапуск оркестратора...")

            if not self.stop():
                log("Не удалось остановить оркестратор для перезапуска", "ERROR")
                return False

        # Небольшая пауза для освобождения ресурсов
        import time
        time.sleep(0.5)

        if not self.start():
            log("Не удалось запустить оркестратор после остановки", "ERROR")
            return False

        log("Оркестратор перезапущен", "INFO")
        return True

    def is_running(self) -> bool:
        """Проверяет, запущен ли оркестратор"""
        if self.running_process is None:
            return False
        return self.running_process.poll() is None

    def get_pid(self) -> Optional[int]:
        """Возвращает PID процесса или None"""
        if self.running_process is not None:
            return self.running_process.pid
        return None

    def get_locked_strategies(self) -> Dict[str, int]:
        """Возвращает словарь TLS locked стратегий {hostname: strategy_num}"""
        return self.locked_manager.locked_by_askey["tls"].copy()

    def clear_learned_data(self) -> bool:
        """Очищает данные обучения для переобучения с нуля"""
        result = self.locked_manager.clear()

        # Удаляем файл learned-strategies.lua чтобы при перезапуске был чистый старт
        learned_lua = os.path.join(self.lua_path, "learned-strategies.lua")
        if os.path.exists(learned_lua):
            try:
                os.remove(learned_lua)
                log("Удалён файл learned-strategies.lua", "DEBUG")
            except Exception as e:
                log(f"Не удалось удалить learned-strategies.lua: {e}", "WARNING")

        # Перезапускаем winws2 чтобы применить сброс (очистить hrec.nstrategy в памяти Lua)
        if self.is_running():
            log("Перезапуск оркестратора после сброса обучения...", "INFO")
            if self.output_callback:
                self.output_callback("[INFO] Перезапуск оркестратора для применения сброса обучения...")
            self.restart()

        return result

    def get_learned_data(self) -> dict:
        """Возвращает данные обучения в формате для UI"""
        # Загружаем если не загружены
        tls_locked = self.locked_manager.locked_by_askey["tls"]
        http_locked = self.locked_manager.locked_by_askey["http"]
        if not tls_locked and not http_locked:
            self.load_existing_strategies()
        return self.locked_manager.get_learned_data()

    # ==================== WHITELIST METHODS ====================

    def load_whitelist(self) -> set:
        """Загружает whitelist из settings.json + добавляет системные домены"""
        # 1. Очищаем
        self.user_whitelist = []
        self.whitelist = set()
        
        # 2. Добавляем системные (DEFAULT_WHITELIST_DOMAINS)
        self.whitelist.update(DEFAULT_WHITELIST_DOMAINS)
        default_count = len(DEFAULT_WHITELIST_DOMAINS)
        
        # 3. Загружаем пользовательские из settings.json
        try:
            self.user_whitelist = list(get_orchestra_whitelist_user_domains())
            self.whitelist.update(self.user_whitelist)
            if self.user_whitelist:
                log(f"Загружен whitelist: {default_count} системных + {len(self.user_whitelist)} пользовательских", "DEBUG")
            else:
                log(f"Загружен whitelist: {default_count} системных доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки whitelist: {e}", "DEBUG")
        
        return self.whitelist

    def save_whitelist(self):
        """Сохраняет пользовательский whitelist в settings.json."""
        try:
            set_orchestra_whitelist_user_domains(list(self.user_whitelist))
            log(f"Сохранено {len(self.user_whitelist)} пользовательских доменов в whitelist", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения whitelist: {e}", "ERROR")

    def is_default_whitelist_domain(self, domain: str) -> bool:
        """Проверяет, является ли домен системным (нельзя удалить)"""
        return _is_default_whitelist_domain(domain)

    def get_whitelist(self) -> list:
        """
        Возвращает полный whitelist (default + user) с пометками о типе.
        
        Returns:
            [{'domain': 'vk.com', 'is_default': True}, ...]
        """
        # Загружаем если ещё не загружен
        if not self.whitelist:
            self.load_whitelist()
        
        result = []
        for domain in sorted(self.whitelist):
            result.append({
                'domain': domain,
                'is_default': self.is_default_whitelist_domain(domain)
            })
        return result

    def add_to_whitelist(self, domain: str) -> bool:
        """Добавляет домен в пользовательский whitelist"""
        domain = domain.strip().lower()
        if not domain:
            return False

        # Загружаем текущий whitelist если ещё не загружен
        if not self.whitelist:
            self.load_whitelist()

        # Проверяем что не в системном списке
        if self.is_default_whitelist_domain(domain):
            log(f"Домен {domain} уже в системном whitelist", "DEBUG")
            return False

        # Проверяем что ещё не добавлен пользователем
        if domain in self.user_whitelist:
            log(f"Домен {domain} уже в пользовательском whitelist", "DEBUG")
            return False

        # Добавляем
        self.user_whitelist.append(domain)
        self.whitelist.add(domain)
        self.save_whitelist()
        # Регенерируем whitelist.txt чтобы он был актуален при следующем запуске
        self._generate_whitelist_file()
        log(f"Добавлен в whitelist: {domain}", "INFO")
        return True

    def remove_from_whitelist(self, domain: str) -> bool:
        """Удаляет домен из пользовательского whitelist"""
        domain = domain.strip().lower()

        # Загружаем текущий whitelist если ещё не загружен
        if not self.whitelist:
            self.load_whitelist()

        # Нельзя удалить системный домен
        if self.is_default_whitelist_domain(domain):
            log(f"Нельзя удалить {domain} из системного whitelist", "WARNING")
            return False

        # Проверяем что домен действительно добавлен пользователем
        if domain not in self.user_whitelist:
            log(f"Домен {domain} не найден в пользовательском whitelist", "DEBUG")
            return False

        # Удаляем
        self.user_whitelist.remove(domain)
        self.whitelist.discard(domain)
        self.save_whitelist()
        # Регенерируем whitelist.txt
        self._generate_whitelist_file()
        log(f"Удалён из whitelist: {domain}", "INFO")
        return True

    def _load_ipset_networks(self):
        """
        Загружает ipset подсети для определения игр/сервисов по IP (UDP/QUIC).
        Читает ipset-*.txt из папки lists (кроме *.base/*.user).
        """
        if self.ipset_networks:
            return
        try:
            ipset_files = glob.glob(os.path.join(LISTS_FOLDER, "ipset-*.txt"))

            filtered_files: list[str] = []
            for path in ipset_files:
                base_name = os.path.basename(path).lower()
                if base_name.endswith(".base.txt") or base_name.endswith(".user.txt"):
                    continue
                filtered_files.append(path)

            ipset_files = filtered_files

            networks: list[tuple[ipaddress._BaseNetwork, str]] = []
            for path in ipset_files:
                if not os.path.exists(path):
                    continue
                base = os.path.basename(path)
                label = os.path.splitext(base)[0]
                if label.startswith("ipset-"):
                    label = label[len("ipset-"):]
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            try:
                                net = ipaddress.ip_network(line, strict=False)
                                networks.append((net, label))
                            except ValueError:
                                continue
                except Exception as e:
                    log(f"Ошибка чтения {path}: {e}", "DEBUG")

            self.ipset_networks = networks
            if networks:
                log(f"Загружено {len(networks)} ipset подсетей ({len(ipset_files)} файлов)", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки ipset подсетей: {e}", "DEBUG")

    def _resolve_ipset_label(self, ip: str) -> Optional[str]:
        """Возвращает имя ipset файла по IP, если найдено соответствие подсети."""
        if not ip or not self.ipset_networks:
            return None
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return None
        for net, label in self.ipset_networks:
            if ip_obj in net:
                return label
        return None

    # REMOVED: _write_strategies_from_file() - стратегии теперь встроены в circular-config.txt
    # REMOVED: _generate_circular_config() - конфиг теперь статический в /home/privacy/zapret/lua/circular-config.txt

    def _generate_whitelist_file(self) -> bool:
        """Генерирует файл whitelist.txt для winws2 --hostlist-exclude"""
        try:
            # Загружаем whitelist если нужно
            if not self.whitelist:
                self.load_whitelist()

            with open(self.whitelist_path, 'w', encoding='utf-8') as f:
                f.write("# Orchestra whitelist - exclude these domains from DPI bypass\n")
                f.write("# System domains (built-in) + User domains (from registry)\n\n")
                for domain in sorted(self.whitelist):
                    f.write(f"{domain}\n")

            system_count = len(DEFAULT_WHITELIST_DOMAINS)
            user_count = len(self.user_whitelist)
            log(f"Сгенерирован whitelist.txt ({system_count} системных + {user_count} пользовательских = {len(self.whitelist)} всего)", "DEBUG")
            return True

        except Exception as e:
            log(f"Ошибка генерации whitelist: {e}", "ERROR")
            return False
