# orchestra/blocked_strategies_manager.py
"""
Менеджер заблокированных стратегий (чёрный список).

Заблокированные стратегии - это стратегии, которые НЕ должны использоваться для определённых доменов.
Например, strategy=1 (pass) заблокирована для YouTube, Discord, Google и других заблокированных РКН сайтов,
так как "pass" не поможет обойти блокировку.

Типы блокировок:
1. Дефолтные (DEFAULT_BLOCKED_PASS_DOMAINS) - strategy=1 для известных заблокированных сайтов
2. Пользовательские - добавленные вручную через GUI
"""

import json
from typing import Dict, List, Callable, Optional

from log import log
from config import REGISTRY_PATH
from config.reg import reg, reg_enumerate_values, reg_delete_all_values


# Путь в реестре для хранения заблокированных стратегий
REGISTRY_ORCHESTRA_BLOCKED = f"{REGISTRY_PATH}\\Orchestra\\Blocked"


# Домены для которых strategy=1 (pass) заблокирована по умолчанию - они точно заблокированы РКН
# При загрузке blocked_strategies автоматически добавляется s1 для этих доменов
DEFAULT_BLOCKED_PASS_DOMAINS = {
    # Discord
    "discord.com", "discordapp.com", "discord.gg", "discord.media", "discordapp.net",
    # YouTube / Google Video
    "youtube.com", "googlevideo.com", "ytimg.com", "yt3.ggpht.com", "youtu.be",
    "ggpht.com", "googleusercontent.com", "youtube-nocookie.com",
    # Google
    "google.com", "google.ru", "googleapis.com", "gstatic.com",
    "googleadservices.com", "googlesyndication.com", "googletagmanager.com",
    "googleanalytics.com", "google-analytics.com", "doubleclick.net",
    "dns.google", "withgoogle.com", "withyoutube.com",
    # Twitch
    "twitch.tv", "twitchcdn.net",
    # Twitter/X
    "twitter.com", "x.com", "twimg.com",
    # Instagram
    "instagram.com", "cdninstagram.com", "igcdn.com", "ig.me",
    # Facebook / Meta
    "facebook.com", "fbcdn.net", "fb.com", "fb.me",
    # WhatsApp
    "whatsapp.com", "whatsapp.net",
    # TikTok
    "tiktok.com", "tiktokcdn.com", "musical.ly",
    # Telegram
    "telegram.org", "t.me",
    # Spotify
    "spotify.com", "spotifycdn.com",
    # Netflix
    "netflix.com", "nflxvideo.net",
    # Steam
    "steampowered.com", "steamcommunity.com", "steamstatic.com",
    # Roblox
    "roblox.com", "rbxcdn.com",
    # Reddit
    "reddit.com", "redd.it", "redditmedia.com",
    # GitHub
    "github.com", "githubusercontent.com",
    # Rutracker
    "rutracker.org"
}


def is_default_blocked_pass_domain(hostname: str) -> bool:
    """
    Проверяет, является ли домен дефолтно заблокированным для strategy=1.

    Args:
        hostname: Имя домена

    Returns:
        True если домен или его родительский домен в DEFAULT_BLOCKED_PASS_DOMAINS
    """
    if not hostname:
        return False
    hostname = hostname.lower().strip()
    # Точное совпадение
    if hostname in DEFAULT_BLOCKED_PASS_DOMAINS:
        return True
    # Проверка субдоменов (cdn.discord.com -> discord.com)
    for domain in DEFAULT_BLOCKED_PASS_DOMAINS:
        if hostname.endswith("." + domain):
            return True
    return False


class BlockedStrategiesManager:
    """
    Менеджер заблокированных стратегий (чёрный список).

    Управляет списком стратегий, которые не должны использоваться для определённых доменов.
    Включает дефолтные блокировки (s1 для заблокированных сайтов) и пользовательские.
    """

    def __init__(self):
        # Заблокированные стратегии: {hostname: [strategy_list]}
        self.blocked_strategies: Dict[str, List[int]] = {}

        # Callback для уведомлений (опционально)
        self.output_callback: Optional[Callable[[str], None]] = None

    def set_output_callback(self, callback: Callable[[str], None]):
        """Устанавливает callback для вывода сообщений в UI"""
        self.output_callback = callback

    def load(self):
        """Загружает заблокированные стратегии из реестра + дефолтные блокировки s1"""
        # Очищаем БЕЗ создания нового словаря (сохраняем ссылки!)
        self.blocked_strategies.clear()

        # 1. Добавляем дефолтные блокировки: strategy=1 для DEFAULT_BLOCKED_PASS_DOMAINS
        for domain in DEFAULT_BLOCKED_PASS_DOMAINS:
            self.blocked_strategies[domain] = [1]
        default_count = len(DEFAULT_BLOCKED_PASS_DOMAINS)

        # 2. Загружаем пользовательские блокировки из реестра (мержим с дефолтными)
        try:
            data = reg_enumerate_values(REGISTRY_ORCHESTRA_BLOCKED)
            for hostname, json_str in data.items():
                try:
                    strategies = json.loads(json_str)
                    if isinstance(strategies, list) and strategies:
                        user_blocked = [int(s) for s in strategies]
                        # Мержим с существующими (дефолтными)
                        if hostname in self.blocked_strategies:
                            existing = set(self.blocked_strategies[hostname])
                            existing.update(user_blocked)
                            self.blocked_strategies[hostname] = sorted(list(existing))
                        else:
                            self.blocked_strategies[hostname] = sorted(user_blocked)
                except (json.JSONDecodeError, ValueError):
                    pass

            user_count = sum(len(s) for s in self.blocked_strategies.values()) - default_count
            if user_count > 0:
                log(f"Загружено {user_count} пользовательских блокировок + {default_count} дефолтных (s1 для заблокированных сайтов)", "DEBUG")
            else:
                log(f"Загружено {default_count} дефолтных блокировок (s1 для заблокированных сайтов)", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки blocked strategies: {e}", "DEBUG")

    def save(self):
        """Сохраняет заблокированные стратегии в реестр (только пользовательские)"""
        try:
            # Сначала очищаем старые значения
            reg_delete_all_values(REGISTRY_ORCHESTRA_BLOCKED)

            # Сохраняем ТОЛЬКО пользовательские (исключаем дефолтные)
            saved_count = 0
            for hostname, strategies in self.blocked_strategies.items():
                # Фильтруем только пользовательские блокировки
                user_strategies = [s for s in strategies if not self.is_default_blocked(hostname, s)]

                if user_strategies:
                    json_str = json.dumps(user_strategies)
                    reg(REGISTRY_ORCHESTRA_BLOCKED, hostname, json_str)
                    saved_count += len(user_strategies)

            log(f"Сохранено {saved_count} пользовательских заблокированных стратегий", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения blocked strategies: {e}", "ERROR")

    def get_blocked(self, hostname: str) -> List[int]:
        """
        Возвращает список заблокированных стратегий для домена.

        Args:
            hostname: Имя домена или IP

        Returns:
            Список номеров заблокированных стратегий
        """
        return self.blocked_strategies.get(hostname.lower(), [])

    def is_blocked(self, hostname: str, strategy: int) -> bool:
        """
        Проверяет, заблокирована ли стратегия для домена.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии

        Returns:
            True если стратегия заблокирована
        """
        if not hostname:
            return False
        hostname = hostname.lower()

        # Прямая проверка в blocked_strategies
        blocked = self.blocked_strategies.get(hostname, [])
        if strategy in blocked:
            return True

        # Для strategy=1 проверяем субдомены дефолтных блокировок
        # (cdn.youtube.com -> youtube.com заблокирован)
        if strategy == 1 and is_default_blocked_pass_domain(hostname):
            return True

        return False

    def is_default_blocked(self, hostname: str, strategy: int) -> bool:
        """
        Проверяет, является ли блокировка дефолтной (из DEFAULT_BLOCKED_PASS_DOMAINS).
        Дефолтные блокировки нельзя удалить через GUI.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии

        Returns:
            True если это дефолтная блокировка (strategy=1 для заблокированных сайтов)
        """
        if strategy != 1:
            return False
        return is_default_blocked_pass_domain(hostname)

    def block(self, hostname: str, strategy: int, proto: str = "tls"):
        """
        Блокирует стратегию для домена (добавляет в чёрный список).

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            proto: Протокол (tls/http/udp) - для информации в логах
        """
        hostname = hostname.lower()

        if hostname not in self.blocked_strategies:
            self.blocked_strategies[hostname] = []

        if strategy not in self.blocked_strategies[hostname]:
            self.blocked_strategies[hostname].append(strategy)
            self.blocked_strategies[hostname].sort()
            self.save()
            log(f"Заблокирована стратегия #{strategy} для {hostname} [{proto.upper()}]", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] Заблокирована стратегия #{strategy} для {hostname}")

    def unblock(self, hostname: str, strategy: int) -> bool:
        """
        Разблокирует стратегию для домена (удаляет из чёрного списка).
        Дефолтные блокировки (s1 для youtube, google и т.д.) не удаляются.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии

        Returns:
            True если разблокировка успешна, False если это дефолтная блокировка
        """
        hostname = hostname.lower()

        # Проверяем, не дефолтная ли это блокировка
        if self.is_default_blocked(hostname, strategy):
            log(f"Нельзя разблокировать дефолтную блокировку: {hostname} strategy={strategy}", "WARNING")
            return False

        if hostname in self.blocked_strategies:
            if strategy in self.blocked_strategies[hostname]:
                self.blocked_strategies[hostname].remove(strategy)

                # Если остались только дефолтные блокировки - удаляем весь ключ из памяти
                # (дефолтные будут добавлены заново при load)
                user_strategies = [s for s in self.blocked_strategies[hostname] if not self.is_default_blocked(hostname, s)]
                if not user_strategies:
                    # Проверяем есть ли дефолтные
                    if not is_default_blocked_pass_domain(hostname):
                        del self.blocked_strategies[hostname]

                self.save()
                log(f"Разблокирована стратегия #{strategy} для {hostname}", "INFO")

                if self.output_callback:
                    self.output_callback(f"[INFO] Разблокирована стратегия #{strategy} для {hostname}")
                return True
        return False

    def clear(self):
        """
        Очищает пользовательский чёрный список стратегий.
        Дефолтные блокировки (s1 для youtube, google и т.д.) сохраняются.
        """
        # Считаем только пользовательские блокировки
        user_count = 0
        for hostname, strategies in list(self.blocked_strategies.items()):
            for strategy in list(strategies):
                if not self.is_default_blocked(hostname, strategy):
                    user_count += 1

        # Очищаем реестр (там только пользовательские)
        reg_delete_all_values(REGISTRY_ORCHESTRA_BLOCKED)

        # Перезагружаем blocked_strategies (останутся только дефолтные)
        self.load()

        log(f"Очищен пользовательский чёрный список ({user_count} записей)", "INFO")

        if self.output_callback:
            self.output_callback(f"[INFO] Очищен пользовательский чёрный список ({user_count} записей)")

    def get_all(self) -> Dict[str, List[int]]:
        """
        Возвращает все заблокированные стратегии.

        Returns:
            Словарь {hostname: [strategy_list]}
        """
        return self.blocked_strategies.copy()

    def get_all_with_info(self) -> List[dict]:
        """
        Возвращает все заблокированные стратегии с информацией о типе.

        Returns:
            [{'hostname': 'youtube.com', 'strategy': 1, 'is_default': True}, ...]
        """
        result = []
        for hostname, strategies in sorted(self.blocked_strategies.items()):
            for strategy in strategies:
                result.append({
                    'hostname': hostname,
                    'strategy': strategy,
                    'is_default': self.is_default_blocked(hostname, strategy)
                })
        return result

    def generate_lua_table(self) -> str:
        """
        Генерирует Lua код для таблицы BLOCKED_STRATEGIES и функции is_strategy_blocked.

        Returns:
            Lua код как строка
        """
        if not self.blocked_strategies:
            return (
                "-- No blocked strategies\n"
                "BLOCKED_STRATEGIES = {}\n"
                "function is_strategy_blocked(hostname, strategy) return false end\n"
            )

        lines = ["-- Blocked strategies (default + user-defined)"]
        lines.append("BLOCKED_STRATEGIES = {")

        for hostname, strategies in self.blocked_strategies.items():
            safe_host = hostname.replace('\\', '\\\\').replace('"', '\\"')
            strat_list = ", ".join(str(s) for s in strategies)
            lines.append(f'    ["{safe_host}"] = {{{strat_list}}},')

        lines.append("}")
        lines.append("")

        # Функция проверки заблокированных стратегий (учитываем субдомены)
        lines.append("-- Check if strategy is blocked for hostname (supports subdomains)")
        lines.append("function is_strategy_blocked(hostname, strategy)")
        lines.append("    if not hostname or not BLOCKED_STRATEGIES then return false end")
        lines.append("    hostname = hostname:lower()")
        lines.append("    local function check_host(h)")
        lines.append("        local blocked = BLOCKED_STRATEGIES[h]")
        lines.append("        if not blocked then return false end")
        lines.append("        for _, s in ipairs(blocked) do")
        lines.append("            if s == strategy then return true end")
        lines.append("        end")
        lines.append("        return false")
        lines.append("    end")
        lines.append("    -- точное совпадение")
        lines.append("    if check_host(hostname) then return true end")
        lines.append("    -- проверка по суффиксу домена")
        lines.append("    local dot = hostname:find('%.')")
        lines.append("    while dot do")
        lines.append("        local suffix = hostname:sub(dot + 1)")
        lines.append("        if check_host(suffix) then return true end")
        lines.append("        dot = hostname:find('%.', dot + 1)")
        lines.append("    end")
        lines.append("    return false")
        lines.append("end")
        lines.append("")

        return "\n".join(lines)
