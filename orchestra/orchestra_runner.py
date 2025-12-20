# orchestra/orchestra_runner.py
"""
Circular Orchestra Runner - автоматическое обучение стратегий DPI bypass.

Использует circular orchestrator из F:\\doc\\zapret2\\lua\\zapret-auto.lua (файл менять этот нельзя) с:
- combined_failure_detector (RST injection + silent drop)
- strategy_stats (LOCK механизм после 3 успехов, UNLOCK после 2 failures)
- domain_grouping (группировка субдоменов)

При этом сам оркестратор (его исходный код) всегда хранится H:\\Privacy\\zapret\\lua

Копировать в Program Data не нужно -  приложение берёт файлы напрямую из H:\\Privacy\\zapret\\lua\\.

Можешь посмотреть исходный код логов в исходном коде запрета F:\\doc\\zapret2\\nfq2\\desync.c
Логи - только Python - компактные для гуи чтобы не было огромных winws2 debug логов.
"""

import os
import subprocess
import threading
import json
import glob
import ipaddress
from typing import Optional, Callable, Dict, List
from datetime import datetime

from log import log
from config import MAIN_DIRECTORY, EXE_FOLDER, LUA_FOLDER, LOGS_FOLDER, BIN_FOLDER, REGISTRY_PATH, LISTS_FOLDER
from config.reg import reg
from orchestra.log_parser import LogParser, EventType, ParsedEvent, nld_cut, ip_to_subnet16, is_local_ip
from orchestra.blocked_strategies_manager import BlockedStrategiesManager
from orchestra.locked_strategies_manager import LockedStrategiesManager

# Путь в реестре (основные константы теперь в менеджерах)
REGISTRY_ORCHESTRA = f"{REGISTRY_PATH}\\Orchestra"

# Максимальное количество лог-файлов оркестратора
MAX_ORCHESTRA_LOGS = 10

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
    "ozonusercontent.com",
    # wb
    "wildberries.ru",
    "wb.ru",
    "wbbasket.ru"
}

def _is_default_whitelist_domain(hostname: str) -> bool:
    """
    Проверяет, является ли домен системным в whitelist (нельзя удалить).
    Внутренняя функция для whitelist методов.
    """
    if not hostname:
        return False
    hostname = hostname.lower().strip()
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
    - Использует circular orchestrator (не mega_circular)
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
        self.config_path = os.path.join(self.lua_path, "circular-config.txt")
        self.blobs_path = os.path.join(self.lua_path, "blobs.txt")

        # TLS 443 стратегии
        self.strategies_source_path = os.path.join(self.lua_path, "strategies-source.txt")
        self.strategies_path = os.path.join(self.lua_path, "strategies-all.txt")

        # HTTP 80 стратегии
        self.http_strategies_source_path = os.path.join(self.lua_path, "strategies-http-source.txt")
        self.http_strategies_path = os.path.join(self.lua_path, "strategies-http-all.txt")

        # UDP стратегии (QUIC)
        self.udp_strategies_source_path = os.path.join(self.lua_path, "strategies-udp-source.txt")
        self.udp_strategies_path = os.path.join(self.lua_path, "strategies-udp-all.txt")

        # Discord Voice / STUN стратегии
        self.discord_strategies_source_path = os.path.join(self.lua_path, "strategies-discord-source.txt")
        self.discord_strategies_path = os.path.join(self.lua_path, "strategies-discord-all.txt")

        # Белый список (exclude hostlist)
        self.whitelist_path = os.path.join(self.lua_path, "whitelist.txt")

        # Debug log от winws2 (для детекции LOCKED/UNLOCKING)
        # Теперь используем уникальные имена с ID сессии
        self.current_log_id: Optional[str] = None
        self.debug_log_path: Optional[str] = None
        # Загружаем настройку сохранения debug файла из реестра
        saved_debug = reg(f"{REGISTRY_PATH}\\Orchestra", "KeepDebugFile")
        self.keep_debug_file = bool(saved_debug)

        # Загружаем настройку авторестарта при Discord FAIL (по умолчанию включено)
        saved_auto_restart = reg(f"{REGISTRY_PATH}\\Orchestra", "AutoRestartOnDiscordFail")
        self.auto_restart_on_discord_fail = saved_auto_restart is None or bool(saved_auto_restart)
        self.restart_callback: Optional[Callable[[], None]] = None  # Callback для перезапуска приложения

        # Состояние
        self.running_process: Optional[subprocess.Popen] = None
        self.output_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Менеджеры стратегий
        self.blocked_manager = BlockedStrategiesManager()
        self.locked_manager = LockedStrategiesManager(blocked_manager=self.blocked_manager)

        # Алиасы для совместимости (TODO: постепенно убрать)
        self.locked_strategies = self.locked_manager.locked_strategies
        self.http_locked_strategies = self.locked_manager.http_locked_strategies
        self.udp_locked_strategies = self.locked_manager.udp_locked_strategies
        self.strategy_history = self.locked_manager.strategy_history
        self.blocked_strategies = self.blocked_manager.blocked_strategies

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

        # Обновляем алиасы для совместимости
        self.locked_strategies = self.locked_manager.locked_strategies
        self.http_locked_strategies = self.locked_manager.http_locked_strategies
        self.udp_locked_strategies = self.locked_manager.udp_locked_strategies
        self.strategy_history = self.locked_manager.strategy_history
        self.blocked_strategies = self.blocked_manager.blocked_strategies

        return self.locked_strategies

    def _generate_learned_lua(self) -> Optional[str]:
        """
        Генерирует learned-strategies.lua для предзагрузки в strategy-stats.lua.
        Этот файл хранится по пути H:\Privacy\zapret\lua\strategy-stats.lua
        Вызывает strategy_preload() и strategy_preload_history() для каждого домена.

        Returns:
            Путь к файлу или None если нет данных
        """
        has_tls = bool(self.locked_strategies)
        has_http = bool(self.http_locked_strategies)
        has_udp = bool(self.udp_locked_strategies)
        has_history = bool(self.strategy_history)

        # blocked_strategies уже содержит и дефолтные (s1 для DEFAULT_BLOCKED_PASS_DOMAINS)
        # и пользовательские блокировки - используем напрямую
        has_blocked = bool(self.blocked_strategies)

        if not has_tls and not has_http and not has_udp and not has_history and not has_blocked:
            return None

        lua_path = os.path.join(self.lua_path, "learned-strategies.lua")
        log(f"Генерация learned-strategies.lua: {lua_path}", "DEBUG")
        log(f"  TLS: {len(self.locked_strategies)}, HTTP: {len(self.http_locked_strategies)}, UDP: {len(self.udp_locked_strategies)}", "DEBUG")
        total_tls = len(self.locked_strategies)
        total_http = len(self.http_locked_strategies)
        total_udp = len(self.udp_locked_strategies)
        total_history = len(self.strategy_history)

        try:
            with open(lua_path, 'w', encoding='utf-8') as f:
                f.write("-- Auto-generated: preload strategies from registry\n")
                f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"-- TLS: {total_tls}, HTTP: {total_http}, UDP: {total_udp}, History: {total_history}\n\n")

                # Генерируем таблицу заблокированных стратегий для Lua
                if self.blocked_strategies:
                    f.write("-- Blocked strategies (default + user-defined)\n")
                    f.write("BLOCKED_STRATEGIES = {\n")
                    for hostname, strategies in self.blocked_strategies.items():
                        safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                        strat_list = ", ".join(str(s) for s in strategies)
                        f.write(f'    ["{safe_host}"] = {{{strat_list}}},\n')
                    f.write("}\n\n")

                    # Функция проверки заблокированных стратегий (учитываем субдомены)
                    f.write("-- Check if strategy is blocked for hostname (supports subdomains)\n")
                    f.write("function is_strategy_blocked(hostname, strategy)\n")
                    f.write("    if not hostname or not BLOCKED_STRATEGIES then return false end\n")
                    f.write("    hostname = hostname:lower()\n")
                    f.write("    local function check_host(h)\n")
                    f.write("        local blocked = BLOCKED_STRATEGIES[h]\n")
                    f.write("        if not blocked then return false end\n")
                    f.write("        for _, s in ipairs(blocked) do\n")
                    f.write("            if s == strategy then return true end\n")
                    f.write("        end\n")
                    f.write("        return false\n")
                    f.write("    end\n")
                    f.write("    -- точное совпадение\n")
                    f.write("    if check_host(hostname) then return true end\n")
                    f.write("    -- проверка по суффиксу домена\n")
                    f.write("    local dot = hostname:find('%.')\n")
                    f.write("    while dot do\n")
                    f.write("        local suffix = hostname:sub(dot + 1)\n")
                    f.write("        if check_host(suffix) then return true end\n")
                    f.write("        dot = hostname:find('%.', dot + 1)\n")
                    f.write("    end\n")
                    f.write("    return false\n")
                    f.write("end\n\n")
                else:
                    # Если нет заблокированных - функция всегда возвращает false
                    f.write("-- No blocked strategies\n")
                    f.write("BLOCKED_STRATEGIES = {}\n")
                    f.write("function is_strategy_blocked(hostname, strategy) return false end\n\n")

                # Предзагрузка TLS стратегий (с фильтрацией заблокированных)
                blocked_tls = 0
                for hostname, strategy in self.locked_strategies.items():
                    if self.blocked_manager.is_blocked(hostname, strategy):
                        blocked_tls += 1
                        continue
                    safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                    f.write(f'strategy_preload("{safe_host}", {strategy}, "tls")\n')

                # Предзагрузка HTTP стратегий (с фильтрацией заблокированных)
                blocked_http = 0
                for hostname, strategy in self.http_locked_strategies.items():
                    if self.blocked_manager.is_blocked(hostname, strategy):
                        blocked_http += 1
                        continue
                    safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                    f.write(f'strategy_preload("{safe_host}", {strategy}, "http")\n')

                # Предзагрузка UDP стратегий (с фильтрацией заблокированных)
                blocked_udp = 0
                for ip, strategy in self.udp_locked_strategies.items():
                    if self.blocked_manager.is_blocked(ip, strategy):
                        blocked_udp += 1
                        continue
                    safe_ip = ip.replace('\\', '\\\\').replace('"', '\\"')
                    f.write(f'strategy_preload("{safe_ip}", {strategy}, "udp")\n')

                # Для доменов с заблокированной s1 из истории, которые НЕ залочены - preload с лучшей стратегией
                blocked_from_history = 0
                for hostname in self.strategy_history.keys():
                    # Пропускаем если уже залочен (обработан выше)
                    if hostname in self.locked_strategies or hostname in self.http_locked_strategies:
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
                    f.write(f'strategy_preload("{safe_host}", {best_strat}, "tls")\n')
                    blocked_from_history += 1
                if blocked_from_history > 0:
                    log(f"Добавлено {blocked_from_history} доменов из истории (s1 заблокирована)", "DEBUG")

                # Предзагрузка истории (фильтруем заблокированные стратегии)
                history_skipped = 0
                for hostname, strategies in self.strategy_history.items():
                    safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
                    for strat_key, data in strategies.items():
                        strat_num = int(strat_key) if isinstance(strat_key, str) else strat_key
                        # Пропускаем заблокированные стратегии
                        if self.blocked_manager.is_blocked(hostname, strat_num):
                            history_skipped += 1
                            continue
                        s = data.get('successes') or 0
                        f_count = data.get('failures') or 0
                        f.write(f'strategy_preload_history("{safe_host}", {strat_key}, {s}, {f_count})\n')
                if history_skipped > 0:
                    log(f"Пропущено {history_skipped} записей истории (заблокированы)", "DEBUG")

                actual_tls = total_tls - blocked_tls
                actual_http = total_http - blocked_http
                actual_udp = total_udp - blocked_udp
                total_blocked = blocked_tls + blocked_http + blocked_udp
                f.write(f'\nDLOG("learned-strategies: loaded {actual_tls} TLS + {actual_http} HTTP + {actual_udp} UDP + {total_history} history (blocked: {total_blocked})")\n')

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
                if self.blocked_strategies:
                    f.write('\n-- Install blocked strategies filter for circular rotation\n')
                    f.write('local _blocked_wrap_installed = false\n')
                    f.write('local function install_blocked_filter()\n')
                    f.write('    if _blocked_wrap_installed then return end\n')
                    f.write('    _blocked_wrap_installed = true\n')
                    f.write('    if circular and type(circular) == "function" then\n')
                    f.write('        local original_circular = circular\n')
                    f.write('        circular = function(t, hostname, ...)\n')
                    f.write('            local result = original_circular(t, hostname, ...)\n')
                    f.write('            if result and hostname and is_strategy_blocked(hostname, result) then\n')
                    f.write('                local max_skip = 10\n')
                    f.write('                for i = 1, max_skip do\n')
                    f.write('                    result = original_circular(t, hostname, ...)\n')
                    f.write('                    if not result or not is_strategy_blocked(hostname, result) then break end\n')
                    f.write('                    DLOG("BLOCKED: skip strategy " .. result .. " for " .. hostname)\n')
                    f.write('                end\n')
                    f.write('            end\n')
                    f.write('            return result\n')
                    f.write('        end\n')
                    f.write('        DLOG("Blocked strategies filter installed for circular")\n')
                    f.write('    end\n')
                    f.write('end\n')
                    f.write('install_blocked_filter()\n')

            total_blocked = blocked_tls + blocked_http + blocked_udp
            block_info = f", заблокировано {total_blocked}" if total_blocked > 0 else ""

            log(f"Сгенерирован learned-strategies.lua ({total_tls} TLS + {total_http} HTTP + {total_udp} UDP + {total_history} history{block_info})", "DEBUG")
            return lua_path

        except Exception as e:
            log(f"Ошибка генерации learned-strategies.lua: {e}", "ERROR")
            return None

    def _generate_single_numbered_file(self, source_path: str, output_path: str, name: str) -> int:
        """
        Генерирует один файл стратегий с автоматической нумерацией.

        Returns:
            Количество стратегий или -1 при ошибке
        """
        if not os.path.exists(source_path):
            log(f"Исходные стратегии не найдены: {source_path}", "ERROR")
            return -1

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            strategy_num = 0
            numbered_lines = []

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '--lua-desync=' in line:
                    strategy_num += 1
                    # Добавляем :strategy=N к КАЖДОМУ --lua-desync параметру в строке
                    parts = line.split(' ')
                    new_parts = []
                    for part in parts:
                        if part.startswith('--lua-desync='):
                            new_parts.append(f"{part}:strategy={strategy_num}")
                        else:
                            new_parts.append(part)
                    numbered_lines.append(' '.join(new_parts))
                else:
                    numbered_lines.append(line)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(numbered_lines) + '\n')

            log(f"Сгенерировано {strategy_num} {name} стратегий", "DEBUG")
            return strategy_num

        except Exception as e:
            log(f"Ошибка генерации {name} стратегий: {e}", "ERROR")
            return -1

    def _generate_numbered_strategies(self) -> bool:
        """
        Генерирует strategies-all.txt, strategies-http-all.txt и strategies-udp-all.txt с автоматической нумерацией.
        Путь C:\ProgramData\ZapretTwoDev\lua\strategies-all.txt

        Returns:
            True если генерация успешна
        """
        # TLS стратегии (обязательные)
        tls_count = self._generate_single_numbered_file(
            self.strategies_source_path,
            self.strategies_path,
            "TLS"
        )
        if tls_count < 0:
            return False

        # HTTP стратегии (опциональные)
        if os.path.exists(self.http_strategies_source_path):
            http_count = self._generate_single_numbered_file(
                self.http_strategies_source_path,
                self.http_strategies_path,
                "HTTP"
            )
            if http_count < 0:
                log("HTTP стратегии не сгенерированы, продолжаем без них", "WARNING")
        else:
            log("HTTP source не найден, пропускаем", "DEBUG")

        # UDP стратегии (опциональные - для QUIC)
        if os.path.exists(self.udp_strategies_source_path):
            udp_count = self._generate_single_numbered_file(
                self.udp_strategies_source_path,
                self.udp_strategies_path,
                "UDP"
            )
            if udp_count < 0:
                log("UDP стратегии не сгенерированы, продолжаем без них", "WARNING")
        else:
            log("UDP source не найден, пропускаем", "DEBUG")

        # Discord Voice / STUN стратегии (опциональные)
        if os.path.exists(self.discord_strategies_source_path):
            discord_count = self._generate_single_numbered_file(
                self.discord_strategies_source_path,
                self.discord_strategies_path,
                "Discord"
            )
            if discord_count < 0:
                log("Discord стратегии не сгенерированы, продолжаем без них", "WARNING")
        else:
            log("Discord source не найден, пропускаем", "DEBUG")

        return True

    def _read_output(self):
        """Поток чтения stdout от winws2 с использованием LogParser"""
        parser = LogParser()
        history_save_counter = 0

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

                    # Записываем в debug лог
                    if log_file:
                        try:
                            log_file.write(f"{line}\n")
                        except Exception:
                            pass

                    # Парсим строку
                    event = parser.parse_line(line)
                    if not event:
                        continue

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    is_udp = event.l7proto in ("udp", "quic", "stun", "discord", "wireguard", "dht")

                    # === LOCK ===
                    if event.event_type == EventType.LOCK:
                        host = event.hostname
                        strat = event.strategy
                        proto = event.l7proto or "tls"

                        # Пропускаем заблокированные стратегии
                        if self.blocked_manager.is_blocked(host, strat):
                            continue

                        # Protocol tag and target dict
                        if proto == "udp" or is_udp:
                            target_dict = self.udp_locked_strategies
                            proto_tag = f"[{event.l7proto.upper()}]" if event.l7proto else "[UDP]"
                            port_str = ""
                        elif proto == "http":
                            target_dict = self.http_locked_strategies
                            proto_tag = "[HTTP]"
                            port_str = ":80"
                        else:
                            target_dict = self.locked_strategies
                            proto_tag = "[TLS]"
                            port_str = ":443"

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
                        host = event.hostname
                        removed = False
                        for target_dict, proto_tag, port_str in [
                            (self.locked_strategies, "[TLS]", ":443"),
                            (self.http_locked_strategies, "[HTTP]", ":80"),
                            (self.udp_locked_strategies, "[UDP]", "")
                        ]:
                            if host in target_dict:
                                del target_dict[host]
                                removed = True
                                msg = f"[{timestamp}] {proto_tag} 🔓 UNLOCKED: {host}{port_str} - re-learning..."
                                log(msg, "INFO")
                                if self.output_callback:
                                    self.output_callback(msg)
                                if self.unlock_callback:
                                    self.unlock_callback(host)
                        if removed:
                            self.locked_manager.save()
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
                                if is_udp:
                                    target_dict = self.udp_locked_strategies
                                elif proto == "http":
                                    target_dict = self.http_locked_strategies
                                else:
                                    target_dict = self.locked_strategies

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

                            # Проверяем Discord FAIL для авторестарта Discord
                            if self.auto_restart_on_discord_fail and "discord" in host.lower():
                                log(f"🔄 Обнаружен FAIL Discord ({host}), перезапускаю Discord...", "WARNING")
                                if self.output_callback:
                                    self.output_callback(f"[{timestamp}] ⚠️ Discord FAIL - перезапуск Discord...")
                                if self.restart_callback:
                                    # Вызываем callback для перезапуска Discord (через главный поток)
                                    self.restart_callback()

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
                if self.strategy_history:
                    self.locked_manager.save_history()

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

        # Генерируем strategies-all.txt с автоматической нумерацией
        if not self._generate_numbered_strategies():
            return False

        # Генерируем whitelist.txt
        self._generate_whitelist_file()

        # Генерируем circular-config.txt с абсолютными путями
        self._generate_circular_config()

        log("Оркестратор готов к запуску", "INFO")
        log("ℹ️ Оркестратор видит только НОВЫЕ соединения. Для тестирования:", "INFO")
        log("   • Перезапустите браузер или откройте приватное окно", "INFO")
        log("   • Очистите кэш (Ctrl+Shift+Del)", "INFO")
        log("   • Принудительная перезагрузка (Ctrl+F5)", "INFO")
        return True

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
            return False

        # Загружаем предыдущие стратегии и историю из реестра
        self.load_existing_strategies()

        # Инициализируем счётчики успехов из истории
        # Для доменов которые уже в locked - не важно (не будет повторного LOCK)
        # Для доменов в истории но не locked - продолжаем с сохранённого значения
        self._success_counts = {}
        for hostname, strategies in self.strategy_history.items():
            for strat_key, data in strategies.items():
                successes = data.get('successes') or 0
                if successes > 0:
                    host_key = f"{hostname}:{strat_key}"
                    self._success_counts[host_key] = successes

        # Логируем загруженные данные
        total_locked = len(self.locked_strategies) + len(self.http_locked_strategies) + len(self.udp_locked_strategies)
        total_history = len(self.strategy_history)
        if total_locked or total_history:
            log(f"Загружено из реестра: {len(self.locked_strategies)} TLS + {len(self.http_locked_strategies)} HTTP + {len(self.udp_locked_strategies)} UDP стратегий, история для {total_history} доменов", "INFO")

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
            # Запускаем winws2 с @config_file
            cmd = [self.winws_exe, f"@{self.config_path}"]

            # Добавляем предзагрузку стратегий из реестра
            if learned_lua:
                cmd.append(f"--lua-init=@{learned_lua}")

            # Debug: выводим в stdout для парсинга, записываем в файл вручную в _read_output
            cmd.append("--debug=1")

            log_msg = f"Запуск: winws2.exe @{os.path.basename(self.config_path)}"
            if total_locked:
                log_msg += f" ({total_locked} стратегий из реестра)"
            log(log_msg, "INFO")
            log(f"Командная строка: {' '.join(cmd)}", "DEBUG")

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

            log(f"Оркестратор запущен (PID: {self.running_process.pid})", "INFO")

            print(f"[DEBUG start] output_callback={self.output_callback}")  # DEBUG
            if self.output_callback:
                print("[DEBUG start] calling output_callback...")  # DEBUG
                self.output_callback(f"[INFO] Оркестратор запущен (PID: {self.running_process.pid})")
                self.output_callback(f"[INFO] Лог сессии: {self.current_log_id}")
                if self.locked_strategies:
                    self.output_callback(f"[INFO] Загружено {len(self.locked_strategies)} стратегий")

            return True

        except Exception as e:
            log(f"Ошибка запуска оркестратора: {e}", "ERROR")
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

            log(f"Оркестратор остановлен. Сохранено {len(self.locked_strategies)} стратегий, история для {len(self.strategy_history)} доменов", "INFO")
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
        """Возвращает словарь locked стратегий {hostname: strategy_num}"""
        return self.locked_strategies.copy()

    def clear_learned_data(self) -> bool:
        """Очищает данные обучения для переобучения с нуля"""
        result = self.locked_manager.clear()
        # Обновляем алиасы
        self.locked_strategies = self.locked_manager.locked_strategies
        self.http_locked_strategies = self.locked_manager.http_locked_strategies
        self.udp_locked_strategies = self.locked_manager.udp_locked_strategies
        self.strategy_history = self.locked_manager.strategy_history
        return result

    def get_learned_data(self) -> dict:
        """Возвращает данные обучения в формате для UI"""
        # Загружаем если не загружены
        if not self.locked_strategies and not self.http_locked_strategies:
            self.load_existing_strategies()
        return self.locked_manager.get_learned_data()

    # ==================== WHITELIST METHODS ====================

    def load_whitelist(self) -> set:
        """Загружает whitelist из реестра + добавляет системные домены"""
        # 1. Очищаем
        self.user_whitelist = []
        self.whitelist = set()
        
        # 2. Добавляем системные (DEFAULT_WHITELIST_DOMAINS)
        self.whitelist.update(DEFAULT_WHITELIST_DOMAINS)
        default_count = len(DEFAULT_WHITELIST_DOMAINS)
        
        # 3. Загружаем пользовательские из реестра
        try:
            data = reg(REGISTRY_ORCHESTRA, "Whitelist")
            if data:
                self.user_whitelist = json.loads(data)
                # Добавляем в объединённый whitelist
                self.whitelist.update(self.user_whitelist)
                log(f"Загружен whitelist: {default_count} системных + {len(self.user_whitelist)} пользовательских", "DEBUG")
            else:
                log(f"Загружен whitelist: {default_count} системных доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки whitelist: {e}", "DEBUG")
        
        return self.whitelist

    def save_whitelist(self):
        """Сохраняет пользовательский whitelist в реестр"""
        try:
            data = json.dumps(self.user_whitelist, ensure_ascii=False)
            reg(REGISTRY_ORCHESTRA, "Whitelist", data)
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
        Читает все ipset-*.txt и my-ipset.txt из папки lists.
        """
        if self.ipset_networks:
            return
        try:
            ipset_files = glob.glob(os.path.join(LISTS_FOLDER, "ipset-*.txt"))
            # Добавляем пользовательский ipset
            ipset_files.append(os.path.join(LISTS_FOLDER, "my-ipset.txt"))

            networks: list[tuple[ipaddress._BaseNetwork, str]] = []
            for path in ipset_files:
                if not os.path.exists(path):
                    continue
                base = os.path.basename(path)
                label = os.path.splitext(base)[0]
                if label.startswith("ipset-"):
                    label = label[len("ipset-"):]
                elif label == "my-ipset":
                    label = "my-ipset"
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

    def _generate_circular_config(self) -> bool:
        """Генерирует circular-config.txt с абсолютными путями к файлам стратегий"""
        try:
            # Загружаем ipset подсети (для отображения игр/сервисов по IP в UDP логах)
            self._load_ipset_networks()

            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write("--wf-tcp-out=80,443-65535\n")
                f.write("--wf-tcp-in=80,443-65535\n")
                # ВАЖНО: без явного UDP-фильтра WinDivert не ловит QUIC/STUN/WireGuard
                f.write("--wf-udp-out=1-65535\n")
                f.write("--wf-udp-in=1-65535\n")
                f.write("--wf-raw-part=@windivert.filter/windivert_part.stun_bidirectional.txt\n")
                f.write("--wf-raw-part=@windivert.filter/windivert_part.discord_bidirectional.txt\n")
                f.write("--wf-raw-part=@windivert.filter/windivert_part.quic_bidirectional.txt\n")
                f.write("--wf-raw-part=@windivert.filter/windivert_part.games_udp_bidirectional.txt\n")
                f.write("\n")
                f.write("--lua-init=@lua/zapret-lib.lua\n")
                f.write("--lua-init=@lua/zapret-antidpi.lua\n")
                f.write("--lua-init=@lua/zapret-auto.lua\n")
                f.write("--lua-init=@lua/custom_funcs.lua\n")
                f.write("--lua-init=@lua/silent-drop-detector.lua\n")
                f.write("--lua-init=@lua/strategy-stats.lua\n")
                f.write("--lua-init=@lua/combined-detector.lua\n")
                f.write("@lua/blobs.txt\n")
                f.write("\n")
                
                # Profile 1: TLS 443
                f.write("# Profile 1: TLS 443\n")
                f.write("--filter-tcp=443\n")
                f.write("--hostlist-exclude=lua/whitelist.txt\n")
                f.write("--in-range=-d1000\n")
                f.write("--out-range=-d1000\n")
                f.write("--lua-desync=circular_quality:fails=1:failure_detector=combined_failure_detector:success_detector=combined_success_detector:lock_successes=3:lock_tests=5:lock_rate=0.6:inseq=0x1000:nld=2\n")
                # НЕ отключаем входящий трафик - нужен для детектора успеха!
                # --in-range=x отключает входящий для всех стратегий
                # Вместо этого ограничим через -d для экономии CPU
                f.write("--in-range=-d1000\n")
                f.write("--out-range=-d1000\n")
                f.write("--payload=tls_client_hello\n")
                
                # Встраиваем TLS стратегии из файла
                if os.path.exists(self.strategies_path):
                    with open(self.strategies_path, 'r', encoding='utf-8') as strat_file:
                        for line in strat_file:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                f.write(line + "\n")
                
                f.write("\n")
                
                # Profile 2: HTTP 80
                f.write("# Profile 2: HTTP 80\n")
                f.write("--new\n")
                f.write("--filter-tcp=80\n")
                f.write("--hostlist-exclude=lua/whitelist.txt\n")
                f.write("--in-range=-d1000\n")
                f.write("--out-range=-d1000\n")
                f.write("--lua-desync=circular_quality:fails=1:failure_detector=combined_failure_detector:success_detector=combined_success_detector:lock_successes=3:lock_tests=5:lock_rate=0.6:inseq=0x1000:nld=2\n")
                # НЕ отключаем входящий трафик - нужен для детектора успеха!
                f.write("--in-range=-d1000\n")
                f.write("--out-range=-d1000\n")
                f.write("--payload=http_req\n")
                
                # Встраиваем HTTP стратегии из файла
                if os.path.exists(self.http_strategies_path):
                    with open(self.http_strategies_path, 'r', encoding='utf-8') as strat_file:
                        for line in strat_file:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                f.write(line + "\n")
                
                f.write("\n")
                
                # Profile 3: UDP
                f.write("# Profile 3: UDP (QUIC, STUN, Discord, WireGuard, Games)\n")
                f.write("--new\n")
                f.write("--filter-udp=443-65535\n")
                f.write("--payload=all\n")
                f.write("--in-range=-d100\n")
                f.write("--out-range=-d100\n")
                f.write("--lua-desync=circular_quality:fails=3:hostkey=udp_global_hostkey:failure_detector=udp_aggressive_failure_detector:success_detector=udp_protocol_success_detector:lock_successes=2:lock_tests=4:lock_rate=0.5:udp_fail_out=3:udp_fail_in=0:udp_in=1:nld=2\n")
                f.write("--in-range=-d100\n")
                f.write("--out-range=-d100\n")
                f.write("--payload=all\n")
                
                # Встраиваем UDP стратегии из файла
                if os.path.exists(self.udp_strategies_path):
                    with open(self.udp_strategies_path, 'r', encoding='utf-8') as strat_file:
                        for line in strat_file:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                f.write(line + "\n")
                
                f.write("\n")
                f.write("--debug=1\n")
            
            log(f"Сгенерирован circular-config.txt", "DEBUG")
            return True
            
        except Exception as e:
            log(f"Ошибка генерации circular-config.txt: {e}", "ERROR")
            return False

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