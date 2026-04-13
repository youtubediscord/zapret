# orchestra/blocked_strategies_manager.py
"""
Менеджер заблокированных стратегий (чёрный список).

Заблокированные стратегии - это стратегии, которые НЕ должны использоваться для определённых доменов.
Например, strategy=1 (pass) заблокирована для YouTube, Discord, Google и других заблокированных РКН сайтов,
так как "pass" не поможет обойти блокировку.

Типы блокировок:
1. Дефолтные (DEFAULT_BLOCKED_PASS_DOMAINS) - strategy=1 для известных заблокированных сайтов
2. Пользовательские - добавленные вручную через GUI

Хранит блокировки по 9 askey профилям (аналогично locked_strategies_manager):
- tls: HTTPS/TLS трафик (TCP 443)
- http: HTTP трафик (TCP 80)
- quic: QUIC/UDP трафик (UDP 443)
- discord: Discord Voice (UDP 50000-65535)
- wireguard: WireGuard VPN (UDP 51820)
- mtproto: Telegram MTProto (TCP 443, 5222)
- dns: DNS запросы (UDP 53)
- stun: STUN протокол (UDP 3478, 19302)
- unknown: неизвестные UDP протоколы
"""

import json
from typing import Dict, List, Callable, Optional, Set

from log.log import log

from config.config import REGISTRY_PATH

from config.reg import reg, reg_enumerate_values, reg_delete_all_values, reg_delete_value
from orchestra.ignored_targets import is_orchestra_ignored_target


# Все 9 askey профилей (синхронизировано с locked_strategies_manager)
ASKEY_ALL = ["tls", "http", "quic", "discord", "wireguard", "mtproto", "dns", "stun", "unknown"]

# TCP профили (используют hostname)
TCP_ASKEYS = ["tls", "http", "mtproto"]

# UDP профили (используют IP или hostname)
UDP_ASKEYS = ["quic", "discord", "wireguard", "dns", "stun", "unknown"]

# Маппинг старых proto на новые askey (для backward compatibility)
PROTO_TO_ASKEY = {
    "tls": "tls",
    "http": "http",
    "udp": "quic",      # Старый "udp" -> "quic" (основной UDP профиль)
    "unknown": "unknown",
    # Новые askey маппятся сами на себя
    "quic": "quic",
    "discord": "discord",
    "wireguard": "wireguard",
    "mtproto": "mtproto",
    "dns": "dns",
    "stun": "stun",
}

# Базовый путь в реестре
REGISTRY_ORCHESTRA = f"{REGISTRY_PATH}\\Orchestra"

# Legacy путь для backward compatibility (будет мигрирован)
REGISTRY_ORCHESTRA_BLOCKED_LEGACY = f"{REGISTRY_ORCHESTRA}\\Blocked"


def get_blocked_registry_path(askey: str) -> str:
    """Возвращает путь в реестре для blocked askey"""
    return f"{REGISTRY_ORCHESTRA}\\Blocked{askey.title()}"


def get_user_blocked_registry_path(askey: str) -> str:
    """Возвращает путь в реестре для user blocked askey"""
    return f"{REGISTRY_ORCHESTRA}\\UserBlocked{askey.title()}"


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
    hostname = hostname.lower().strip().rstrip('.')  # Normalize: lowercase, trim, remove trailing dots
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

    Использует унифицированную структуру по 9 askey профилям (аналогично locked_strategies_manager).
    """

    def __init__(self, locked_manager=None):
        """
        Args:
            locked_manager: LockedStrategiesManager для удаления конфликтующих locks
        """
        # Унифицированный словарь заблокированных стратегий по askey: {askey: {hostname: [strategy_list]}}
        self.blocked_by_askey: Dict[str, Dict[str, List[int]]] = {askey: {} for askey in ASKEY_ALL}

        # Унифицированный словарь user blocks по askey: {askey: {hostname: set(strategies)}}
        # User blocks - стратегии добавленные пользователем через GUI (не default)
        self.user_blocked_by_askey: Dict[str, Dict[str, Set[int]]] = {askey: {} for askey in ASKEY_ALL}

        # Legacy словарь для backward compatibility (синхронизируется с blocked_by_askey["tls"])
        # DEPRECATED: использовать blocked_by_askey["tls"]
        self.blocked_strategies: Dict[str, List[int]] = self.blocked_by_askey["tls"]

        # Менеджер залоченных стратегий (для удаления конфликтов)
        self.locked_manager = locked_manager

        # Callback для уведомлений (опционально)
        self.output_callback: Optional[Callable[[str], None]] = None

    def set_output_callback(self, callback: Callable[[str], None]):
        """Устанавливает callback для вывода сообщений в UI"""
        self.output_callback = callback

    def set_locked_manager(self, locked_manager):
        """Устанавливает менеджер залоченных стратегий"""
        self.locked_manager = locked_manager

    # ==================== НОРМАЛИЗАЦИЯ ====================

    def _normalize_askey(self, proto: str) -> str:
        """Нормализует proto/askey к стандартному askey"""
        proto = proto.lower().strip()
        return PROTO_TO_ASKEY.get(proto, proto if proto in ASKEY_ALL else "tls")

    def _normalize_hostname(self, hostname: str) -> str:
        """Нормализует hostname: lowercase, trim, remove trailing dots"""
        if not hostname:
            return ""
        return hostname.lower().strip().rstrip('.')

    def _is_ignored_hostname(self, hostname: str) -> bool:
        """Проверяет, запрещён ли этот хост для blocked-контура оркестратора."""
        return is_orchestra_ignored_target(hostname)

    # ==================== МИГРАЦИЯ ====================

    def _migrate_old_registry_format(self):
        """Мигрирует старый формат (Orchestra\\Blocked) в новый (Orchestra\\BlockedTls)"""
        try:
            # Проверяем есть ли старые данные
            old_data = reg_enumerate_values(REGISTRY_ORCHESTRA_BLOCKED_LEGACY)
            if not old_data:
                return

            migrated_count = 0
            tls_path = get_blocked_registry_path("tls")

            for hostname, json_str in old_data.items():
                hostname = self._normalize_hostname(hostname)
                try:
                    strategies = json.loads(json_str)
                    if isinstance(strategies, list) and strategies:
                        # Фильтруем только пользовательские (не дефолтные)
                        user_strategies = [int(s) for s in strategies if not self._is_default_blocked_internal(hostname, int(s))]
                        if user_strategies:
                            # Сохраняем в новый путь
                            reg(tls_path, hostname, json.dumps(user_strategies))
                            migrated_count += 1
                except (json.JSONDecodeError, ValueError):
                    pass

            # Удаляем старые данные
            if migrated_count > 0:
                try:
                    reg_delete_all_values(REGISTRY_ORCHESTRA_BLOCKED_LEGACY)
                except Exception:
                    pass
                log(f"Мигрировано {migrated_count} blocked записей из Blocked в BlockedTls", "INFO")

        except Exception as e:
            log(f"Ошибка миграции blocked: {e}", "DEBUG")

    def _is_default_blocked_internal(self, hostname: str, strategy: int) -> bool:
        """Внутренняя проверка для миграции (без нормализации)"""
        if strategy != 1:
            return False
        return is_default_blocked_pass_domain(hostname)

    # ==================== ЗАГРУЗКА/СОХРАНЕНИЕ ====================

    def load(self):
        """Загружает заблокированные стратегии из реестра + дефолтные блокировки s1"""
        # Очищаем все словари по askey БЕЗ создания новых (сохраняем ссылки!)
        for askey in ASKEY_ALL:
            self.blocked_by_askey[askey].clear()
            self.user_blocked_by_askey[askey].clear()

        # Сначала мигрируем старый формат если есть
        self._migrate_old_registry_format()

        # 1. Добавляем дефолтные блокировки: strategy=1 для DEFAULT_BLOCKED_PASS_DOMAINS (только TLS)
        tls_dict = self.blocked_by_askey["tls"]
        for domain in DEFAULT_BLOCKED_PASS_DOMAINS:
            tls_dict[domain] = [1]
        default_count = len(DEFAULT_BLOCKED_PASS_DOMAINS)

        # 2. Загружаем пользовательские блокировки из реестра для всех askey профилей
        try:
            total_user_count = 0

            for askey in ASKEY_ALL:
                reg_path = get_blocked_registry_path(askey)
                user_reg_path = get_user_blocked_registry_path(askey)
                target_dict = self.blocked_by_askey[askey]
                user_dict = self.user_blocked_by_askey[askey]

                # Загружаем blocked стратегии
                try:
                    data = reg_enumerate_values(reg_path)
                    for hostname, json_str in data.items():
                        hostname = self._normalize_hostname(hostname)
                        if self._is_ignored_hostname(hostname):
                            reg_delete_value(reg_path, hostname)
                            continue
                        try:
                            strategies = json.loads(json_str)
                            if isinstance(strategies, list) and strategies:
                                user_blocked = [int(s) for s in strategies]
                                # Мержим с существующими (дефолтными)
                                if hostname in target_dict:
                                    existing = set(target_dict[hostname])
                                    existing.update(user_blocked)
                                    target_dict[hostname] = sorted(list(existing))
                                else:
                                    target_dict[hostname] = sorted(user_blocked)
                                # Считаем user блокировки
                                for s in user_blocked:
                                    if not self.is_default_blocked(hostname, s):
                                        total_user_count += 1
                        except (json.JSONDecodeError, ValueError):
                            pass
                except Exception:
                    pass

                # Загружаем user blocks маркеры
                try:
                    user_data = reg_enumerate_values(user_reg_path)
                    for hostname, json_str in user_data.items():
                        hostname = self._normalize_hostname(hostname)
                        if self._is_ignored_hostname(hostname):
                            reg_delete_value(user_reg_path, hostname)
                            continue
                        try:
                            strategies = json.loads(json_str)
                            if isinstance(strategies, list):
                                user_dict[hostname] = set(int(s) for s in strategies)
                        except (json.JSONDecodeError, ValueError):
                            pass
                except Exception:
                    pass

            if total_user_count > 0:
                # Логируем детальную статистику
                stats = ", ".join(f"{askey.upper()}: {len(self.blocked_by_askey[askey])}"
                                  for askey in ASKEY_ALL if self.blocked_by_askey[askey])
                log(f"Загружено {total_user_count} пользовательских блокировок + {default_count} дефолтных ({stats})", "DEBUG")
            else:
                log(f"Загружено {default_count} дефолтных блокировок (s1 для заблокированных сайтов)", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки blocked strategies: {e}", "DEBUG")

    def save(self):
        """Сохраняет заблокированные стратегии в реестр (только пользовательские)"""
        try:
            total_saved = 0

            # Сохраняем для всех 9 askey профилей
            for askey in ASKEY_ALL:
                reg_path = get_blocked_registry_path(askey)
                user_reg_path = get_user_blocked_registry_path(askey)
                target_dict = self.blocked_by_askey[askey]
                user_dict = self.user_blocked_by_askey[askey]

                # Собираем данные для сохранения (только пользовательские блокировки)
                to_save = {}
                for hostname, strategies in target_dict.items():
                    hostname_norm = self._normalize_hostname(hostname)
                    # Фильтруем только пользовательские блокировки
                    user_strategies = [s for s in strategies if not self.is_default_blocked(hostname_norm, s)]
                    if user_strategies:
                        to_save[hostname_norm] = user_strategies

                # Сохраняем blocked
                for hostname, user_strategies in to_save.items():
                    try:
                        json_str = json.dumps(user_strategies)
                        reg(reg_path, hostname, json_str)
                        total_saved += len(user_strategies)
                    except Exception as e:
                        log(f"Ошибка сохранения blocked для {hostname} [{askey}]: {e}", "DEBUG")

                # Сохраняем user blocks маркеры
                for hostname, strategies_set in user_dict.items():
                    if strategies_set:
                        try:
                            json_str = json.dumps(sorted(list(strategies_set)))
                            reg(user_reg_path, hostname, json_str)
                        except Exception as e:
                            log(f"Ошибка сохранения user_blocked для {hostname} [{askey}]: {e}", "DEBUG")

            if total_saved > 0:
                log(f"Сохранено {total_saved} пользовательских заблокированных стратегий", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения blocked strategies: {e}", "ERROR")

    # ==================== ПОЛУЧЕНИЕ ДАННЫХ ====================

    def get_blocked(self, hostname: str, askey: str = "tls") -> List[int]:
        """
        Возвращает список заблокированных стратегий для домена.

        Args:
            hostname: Имя домена или IP
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            Список номеров заблокированных стратегий
        """
        hostname = self._normalize_hostname(hostname)
        askey = self._normalize_askey(askey)
        return self.blocked_by_askey[askey].get(hostname, [])

    def get_blocked_by_askey(self, askey: str) -> Dict[str, List[int]]:
        """
        Возвращает все заблокированные стратегии для указанного askey.

        Args:
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            Словарь {hostname: [strategy_list]}
        """
        askey = self._normalize_askey(askey)
        return self.blocked_by_askey[askey].copy()

    def is_blocked(self, hostname: str, strategy: int, askey: str = "tls") -> bool:
        """
        Проверяет, заблокирована ли стратегия для домена.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            True если стратегия заблокирована
        """
        if not hostname:
            return False
        hostname = self._normalize_hostname(hostname)
        askey = self._normalize_askey(askey)

        # Прямая проверка в blocked_by_askey
        blocked = self.blocked_by_askey[askey].get(hostname, [])
        if strategy in blocked:
            return True

        # Для strategy=1 проверяем субдомены дефолтных блокировок (только TCP профили)
        # (cdn.youtube.com -> youtube.com заблокирован)
        if strategy == 1 and askey in TCP_ASKEYS and is_default_blocked_pass_domain(hostname):
            return True

        return False

    def is_user_blocked(self, hostname: str, strategy: int, askey: str = "tls") -> bool:
        """
        Проверяет, является ли блокировка пользовательской (добавлена через GUI).

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            askey: Профиль протокола

        Returns:
            True если это user block
        """
        hostname = self._normalize_hostname(hostname)
        askey = self._normalize_askey(askey)
        user_set = self.user_blocked_by_askey[askey].get(hostname, set())
        return strategy in user_set

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

    # ==================== BLOCK/UNBLOCK ====================

    def _remove_conflicting_lock(self, hostname: str, strategy: int, askey: str):
        """
        Удаляет конфликтующий lock для домена (если locked strategy == blocked strategy).

        BLOCKED имеет ПРИОРИТЕТ над LOCKED (включая user lock).

        Args:
            hostname: Имя домена или IP
            strategy: Номер заблокированной стратегии
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)
        """
        if not self.locked_manager:
            return

        askey = self._normalize_askey(askey)

        # Получаем словарь locked для данного askey
        target_dict = self.locked_manager.locked_by_askey.get(askey, {})

        # Проверяем есть ли конфликт (locked strategy == blocked strategy)
        if hostname in target_dict and target_dict[hostname] == strategy:
            # Используем unlock() который также удаляет user locks
            self.locked_manager.unlock(hostname, askey)
            log(f"Удалён конфликтующий LOCK: {hostname} strategy={strategy} [{askey.upper()}] (blocked имеет приоритет)", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] Удалён конфликтующий LOCK для {hostname} (blocked имеет приоритет)")

    def block(self, hostname: str, strategy: int, askey: str = "tls", user_block: bool = False):
        """
        Блокирует стратегию для домена (добавляет в чёрный список).

        ВАЖНО: Если для этого домена есть залоченная стратегия с таким же номером,
        она будет УДАЛЕНА (включая user lock). Blocked имеет ПРИОРИТЕТ над locked.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)
            user_block: True если это ручная блокировка через GUI
        """
        hostname = self._normalize_hostname(hostname)
        askey = self._normalize_askey(askey)

        if self._is_ignored_hostname(hostname):
            log(f"[IGNORE] Оркестратор не блокирует proxy-цель: {hostname} [{askey.upper()}]", "INFO")
            if self.output_callback:
                self.output_callback(f"[INFO] Пропущена blocked-запись для proxy-цели {hostname}")
            return

        target_dict = self.blocked_by_askey[askey]
        user_dict = self.user_blocked_by_askey[askey]

        if hostname not in target_dict:
            target_dict[hostname] = []

        if strategy not in target_dict[hostname]:
            target_dict[hostname].append(strategy)
            target_dict[hostname].sort()

            # Если user_block - добавляем в user dict
            if user_block:
                if hostname not in user_dict:
                    user_dict[hostname] = set()
                user_dict[hostname].add(strategy)

            self.save()
            block_type = "[USER] " if user_block else ""
            log(f"{block_type}Заблокирована стратегия #{strategy} для {hostname} [{askey.upper()}]", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] {block_type}Заблокирована стратегия #{strategy} для {hostname}")

            # Удаляем конфликтующий lock если есть (blocked имеет ПРИОРИТЕТ)
            if self.locked_manager:
                self._remove_conflicting_lock(hostname, strategy, askey)

    def unblock(self, hostname: str, strategy: int, askey: str = "tls") -> bool:
        """
        Разблокирует стратегию для домена (удаляет из чёрного списка).
        Дефолтные блокировки (s1 для youtube, google и т.д.) не удаляются.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            True если разблокировка успешна, False если это дефолтная блокировка
        """
        hostname = self._normalize_hostname(hostname)
        askey = self._normalize_askey(askey)

        # Проверяем, не дефолтная ли это блокировка
        if self.is_default_blocked(hostname, strategy):
            log(f"Нельзя разблокировать дефолтную блокировку: {hostname} strategy={strategy}", "WARNING")
            return False

        target_dict = self.blocked_by_askey[askey]
        user_dict = self.user_blocked_by_askey[askey]
        reg_path = get_blocked_registry_path(askey)
        user_reg_path = get_user_blocked_registry_path(askey)

        if hostname in target_dict:
            if strategy in target_dict[hostname]:
                target_dict[hostname].remove(strategy)

                # Удаляем из user dict
                if hostname in user_dict:
                    user_dict[hostname].discard(strategy)
                    if not user_dict[hostname]:
                        del user_dict[hostname]
                        try:
                            reg_delete_value(user_reg_path, hostname)
                        except Exception:
                            pass

                # Если остались только дефолтные блокировки - удаляем ключ из реестра
                user_strategies = [s for s in target_dict[hostname] if not self.is_default_blocked(hostname, s)]
                if not user_strategies:
                    # Удаляем из реестра (но оставляем в памяти если есть дефолтные)
                    try:
                        reg_delete_value(reg_path, hostname)
                    except Exception:
                        pass
                    # Если нет дефолтных - удаляем и из памяти
                    if not target_dict[hostname]:
                        del target_dict[hostname]
                else:
                    # Сохраняем только пользовательские
                    self.save()

                log(f"Разблокирована стратегия #{strategy} для {hostname} [{askey.upper()}]", "INFO")

                if self.output_callback:
                    self.output_callback(f"[INFO] Разблокирована стратегия #{strategy} для {hostname}")
                return True
        return False

    def clear(self):
        """
        Очищает пользовательский чёрный список стратегий для всех askey.
        Дефолтные блокировки (s1 для youtube, google и т.д.) сохраняются.
        """
        # Считаем только пользовательские блокировки
        user_count = 0
        for askey in ASKEY_ALL:
            for hostname, strategies in list(self.blocked_by_askey[askey].items()):
                for strategy in list(strategies):
                    if not self.is_default_blocked(hostname, strategy):
                        user_count += 1

        # Очищаем реестр для всех askey (там только пользовательские)
        for askey in ASKEY_ALL:
            try:
                reg_delete_all_values(get_blocked_registry_path(askey))
            except Exception:
                pass
            try:
                reg_delete_all_values(get_user_blocked_registry_path(askey))
            except Exception:
                pass

        # Перезагружаем blocked_strategies (останутся только дефолтные)
        self.load()

        log(f"Очищен пользовательский чёрный список ({user_count} записей)", "INFO")

        if self.output_callback:
            self.output_callback(f"[INFO] Очищен пользовательский чёрный список ({user_count} записей)")

    def get_all(self, askey: str = "tls") -> Dict[str, List[int]]:
        """
        Возвращает все заблокированные стратегии для указанного askey.

        Args:
            askey: Профиль протокола (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            Словарь {hostname: [strategy_list]}
        """
        askey = self._normalize_askey(askey)
        return self.blocked_by_askey[askey].copy()

    def get_all_by_askey(self) -> Dict[str, Dict[str, List[int]]]:
        """
        Возвращает все заблокированные стратегии для всех askey.

        Returns:
            Словарь {askey: {hostname: [strategy_list]}}
        """
        return {askey: self.blocked_by_askey[askey].copy() for askey in ASKEY_ALL}

    def get_all_with_info(self, askey: str = None) -> List[dict]:
        """
        Возвращает все заблокированные стратегии с информацией о типе.

        Args:
            askey: Профиль протокола или None для всех askey

        Returns:
            [{'hostname': 'youtube.com', 'strategy': 1, 'is_default': True, 'askey': 'tls', 'is_user': False}, ...]
        """
        result = []
        askeys_to_check = [self._normalize_askey(askey)] if askey else ASKEY_ALL

        for ak in askeys_to_check:
            for hostname, strategies in sorted(self.blocked_by_askey[ak].items()):
                for strategy in strategies:
                    result.append({
                        'hostname': hostname,
                        'strategy': strategy,
                        'is_default': self.is_default_blocked(hostname, strategy),
                        'askey': ak,
                        'is_user': self.is_user_blocked(hostname, strategy, ak)
                    })
        return result

    def get_blocked_data(self) -> dict:
        """
        Возвращает данные блокировок в формате для UI (аналогично get_learned_data в locked_manager).

        Returns:
            Словарь с ключами для всех 9 askey:
            {
                'tls': {hostname: [strategy_list]},
                'http': {hostname: [strategy_list]},
                'quic': {ip: [strategy_list]},
                ...
            }
        """
        result = {askey: self.blocked_by_askey[askey].copy() for askey in ASKEY_ALL}
        # Для backward compatibility добавляем 'udp' как alias для 'quic'
        result['udp'] = result['quic']
        return result
