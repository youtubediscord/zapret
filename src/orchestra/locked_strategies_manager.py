# orchestra/locked_strategies_manager.py
"""
Менеджер залоченных (зафиксированных) стратегий.

Залоченные стратегии - это стратегии, которые уже найдены оркестратором и работают для домена.
После успешного обучения (3 успеха подряд) стратегия "лочится" и используется постоянно.

Хранит стратегии по 9 askey профилям:
- tls: HTTPS/TLS трафик (TCP 443)
- http: HTTP трафик (TCP 80)
- quic: QUIC/UDP трафик (UDP 443)
- discord: Discord Voice (UDP 50000-65535)
- wireguard: WireGuard VPN (UDP 51820)
- mtproto: Telegram MTProto (TCP 443, 5222)
- dns: DNS запросы (UDP 53)
- stun: STUN протокол (UDP 3478, 19302)
- unknown: неизвестные UDP протоколы

История: статистика успехов/неудач для каждой стратегии
"""

import json
from typing import Dict, Optional, Callable, Set, List

from log.log import log

from settings.store import (
    clear_orchestra_history,
    clear_orchestra_locked_map,
    clear_orchestra_user_locked,
    get_orchestra_history,
    get_orchestra_locked_map,
    get_orchestra_user_locked,
    remove_orchestra_history_target,
    remove_orchestra_locked_target,
    remove_orchestra_user_locked,
    set_orchestra_history,
    set_orchestra_history_for_target,
    set_orchestra_locked_map,
    set_orchestra_locked_strategy,
    set_orchestra_user_locked,
)
from orchestra.ignored_targets import is_orchestra_ignored_target


# Все 9 askey профилей
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

class LockedStrategiesManager:
    """
    Менеджер залоченных (зафиксированных) стратегий.

    Управляет списком стратегий, которые успешно работают для определённых доменов.
    После обучения стратегия лочится и используется постоянно, пока не будет разлочена.

    Использует унифицированную структуру по 9 askey профилям.
    """

    def __init__(self, blocked_manager=None):
        """
        Args:
            blocked_manager: BlockedStrategiesManager для проверки заблокированных стратегий
        """
        # Унифицированный словарь залоченных стратегий по askey: {askey: {hostname: strategy}}
        self.locked_by_askey: Dict[str, Dict[str, int]] = {askey: {} for askey in ASKEY_ALL}

        # Унифицированный словарь user locks по askey: {askey: set(hostname)}
        self.user_locked_by_askey: Dict[str, Set[str]] = {askey: set() for askey in ASKEY_ALL}

        # История стратегий: {hostname: {strategy: {successes, failures}}}
        self.strategy_history: Dict[str, Dict[str, Dict[str, int]]] = {}

        # Менеджер заблокированных стратегий (для проверки конфликтов)
        self.blocked_manager = blocked_manager

        # Callbacks
        self.output_callback: Optional[Callable[[str], None]] = None
        self.lock_callback: Optional[Callable[[str, int], None]] = None
        self.unlock_callback: Optional[Callable[[str], None]] = None

    def set_output_callback(self, callback: Callable[[str], None]):
        """Устанавливает callback для вывода сообщений в UI"""
        self.output_callback = callback

    def set_lock_callback(self, callback: Callable[[str, int], None]):
        """Устанавливает callback при LOCK стратегии"""
        self.lock_callback = callback

    def set_unlock_callback(self, callback: Callable[[str], None]):
        """Устанавливает callback при UNLOCK стратегии"""
        self.unlock_callback = callback

    def set_blocked_manager(self, blocked_manager):
        """Устанавливает менеджер заблокированных стратегий"""
        self.blocked_manager = blocked_manager

    # ==================== МИГРАЦИЯ ====================

    def _normalize_askey(self, proto: str) -> str:
        """Нормализует proto/askey к стандартному askey"""
        proto = proto.lower().strip()
        return PROTO_TO_ASKEY.get(proto, proto if proto in ASKEY_ALL else "tls")

    def _is_ignored_hostname(self, hostname: str) -> bool:
        """Проверяет, запрещён ли этот хост для lock/history контура оркестратора."""
        return is_orchestra_ignored_target(hostname)

    def _migrate_old_registry_format(self):
        """Legacy-миграция удалена: стартуем только из settings.json."""
        return None

    # ==================== ЗАГРУЗКА/СОХРАНЕНИЕ ====================

    def load(self) -> Dict[str, int]:
        """
        Загружает залоченные стратегии и историю из settings.json.

        Returns:
            Словарь TLS стратегий {hostname: strategy} (для backward compatibility)
        """
        # Очищаем все словари по askey БЕЗ создания новых (сохраняем ссылки!)
        for askey in ASKEY_ALL:
            self.locked_by_askey[askey].clear()
            self.user_locked_by_askey[askey].clear()

        try:
            total_loaded = 0
            total_user_locks = 0

            # Загружаем стратегии для всех 9 askey профилей
            for askey in ASKEY_ALL:
                try:
                    data = get_orchestra_locked_map(askey)
                    for hostname, strategy in data.items():
                        hostname_norm = hostname.lower()
                        if self._is_ignored_hostname(hostname_norm):
                            remove_orchestra_locked_target(askey, hostname)
                            continue
                        self.locked_by_askey[askey][hostname_norm] = int(strategy)
                    total_loaded += len(data)
                except Exception:
                    pass

                try:
                    user_data = list(get_orchestra_user_locked(askey))
                    for hostname in user_data:
                        hostname_norm = hostname.lower()
                        if self._is_ignored_hostname(hostname_norm):
                            remove_orchestra_user_locked(askey, hostname)
                            continue
                        self.user_locked_by_askey[askey].add(hostname_norm)
                    total_user_locks += len(user_data)
                except Exception:
                    pass

            if total_loaded:
                # Логируем детальную статистику
                stats = ", ".join(f"{askey.upper()}: {len(self.locked_by_askey[askey])}"
                                  for askey in ASKEY_ALL if self.locked_by_askey[askey])
                log(f"Загружено {total_loaded} стратегий ({stats}), user locks: {total_user_locks}", "INFO")

            # Очистка доменов со strategy=1 для дефолтно заблокированных
            self._clean_blocked_conflicts()

        except Exception as e:
            log(f"Ошибка загрузки стратегий из settings.json: {e}", "DEBUG")

        # Загружаем историю
        self.load_history()

        return self.locked_by_askey["tls"]

    def _clean_blocked_conflicts(self):
        """Удаляет locked стратегии которые конфликтуют с blocked"""
        if not self.blocked_manager:
            return

        from .blocked_strategies_manager import is_default_blocked_pass_domain

        blocked_cleaned = []
        conflicts_cleaned = []

        # Проходим по всем askey профилям
        for askey in ASKEY_ALL:
            target_dict = self.locked_by_askey[askey]
            user_set = self.user_locked_by_askey[askey]

            # Очистка s1 для дефолтно заблокированных доменов (только TCP профили)
            # НО: не удаляем user locks - пользователь явно залочил домен
            if askey in TCP_ASKEYS:
                for hostname, strategy in list(target_dict.items()):
                    if strategy == 1 and is_default_blocked_pass_domain(hostname):
                        if hostname not in user_set:  # Не удалять user locks!
                            blocked_cleaned.append((hostname, askey))
                            del target_dict[hostname]
                            try:
                                remove_orchestra_locked_target(askey, hostname)
                            except Exception:
                                pass

            # Очистка конфликтов: locked + blocked = удаляем lock (включая user locks!)
            # ВАЖНО: blocked имеет ПРИОРИТЕТ над user_lock
            for hostname, strategy in list(target_dict.items()):
                if self.blocked_manager.is_blocked(hostname, strategy):
                    conflicts_cleaned.append((hostname, strategy, askey.upper()))
                    del target_dict[hostname]
                    try:
                        remove_orchestra_locked_target(askey, hostname)
                    except Exception:
                        pass
                    if hostname in user_set:
                        user_set.discard(hostname)
                        try:
                            remove_orchestra_user_locked(askey, hostname)
                        except Exception:
                            pass

        if blocked_cleaned:
            sample = [f"{h}[{a}]" for h, a in blocked_cleaned[:5]]
            log(f"Очищено {len(blocked_cleaned)} доменов со strategy=1: {', '.join(sample)}{'...' if len(blocked_cleaned) > 5 else ''}", "INFO")

        if conflicts_cleaned:
            log(f"Очищено {len(conflicts_cleaned)} конфликтующих LOCK (blocked имеет приоритет):", "INFO")
            for hostname, strategy, askey_upper in conflicts_cleaned[:10]:
                log(f"  - {hostname} strategy={strategy} [{askey_upper}]", "INFO")

    def save(self):
        """Сохраняет залоченные стратегии в settings.json."""
        try:
            total_saved = 0

            for askey in ASKEY_ALL:
                target_dict = self.locked_by_askey[askey]
                set_orchestra_locked_map(askey, {hostname: int(strategy) for hostname, strategy in target_dict.items()})
                set_orchestra_user_locked(askey, sorted(self.user_locked_by_askey[askey]))
                total_saved += len(target_dict)

            # Логируем детальную статистику
            stats = ", ".join(f"{askey.upper()}: {len(self.locked_by_askey[askey])}"
                              for askey in ASKEY_ALL if self.locked_by_askey[askey])
            if stats:
                log(f"Сохранено {total_saved} стратегий ({stats})", "DEBUG")

        except Exception as e:
            log(f"Ошибка сохранения стратегий в settings.json: {e}", "ERROR")

    # ==================== LOCK/UNLOCK ====================

    def lock(self, hostname: str, strategy: int, proto: str = "tls", user_lock: bool = False):
        """
        Залочивает (фиксирует) стратегию для домена.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            proto: Протокол/askey (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)
            user_lock: True если это ручная блокировка через UI (не перезаписывается auto-lock)
        """
        hostname = hostname.lower()
        askey = self._normalize_askey(proto)

        if self._is_ignored_hostname(hostname):
            log(f"[IGNORE] Оркестратор не лочит proxy-цель: {hostname} [{askey.upper()}]", "INFO")
            if self.output_callback:
                self.output_callback(f"[INFO] Пропущен lock для proxy-цели {hostname}")
            return

        # Получаем словари и пути реестра для данного askey
        target_dict = self.locked_by_askey[askey]
        user_set = self.user_locked_by_askey[askey]
        # Сохраняем стратегию
        target_dict[hostname] = strategy
        set_orchestra_locked_strategy(askey, hostname, strategy)

        # Если user_lock - добавляем в user set и сохраняем в реестр
        if user_lock:
            user_set.add(hostname)
            set_orchestra_user_locked(askey, sorted(user_set))
            log(f"[USER] Залочена стратегия #{strategy} для {hostname} [{askey.upper()}]", "INFO")
        else:
            if hostname in user_set:
                set_orchestra_user_locked(askey, sorted(user_set))
            log(f"Залочена стратегия #{strategy} для {hostname} [{askey.upper()}]", "INFO")

        if self.output_callback:
            lock_type = "[USER] " if user_lock else ""
            self.output_callback(f"[INFO] {lock_type}Залочена стратегия #{strategy} для {hostname} [{askey.upper()}]")

        if self.lock_callback:
            self.lock_callback(hostname, strategy)

    def unlock(self, hostname: str, proto: str = "tls"):
        """
        Разлочивает (снимает фиксацию) стратегию для домена.

        Args:
            hostname: Имя домена или IP
            proto: Протокол/askey (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)
        """
        hostname = hostname.lower()
        askey = self._normalize_askey(proto)

        # Получаем словари и пути реестра для данного askey
        target_dict = self.locked_by_askey[askey]
        user_set = self.user_locked_by_askey[askey]
        if hostname in target_dict:
            old_strategy = target_dict[hostname]
            del target_dict[hostname]
            try:
                remove_orchestra_locked_target(askey, hostname)
            except Exception:
                pass

            if hostname in user_set:
                user_set.discard(hostname)
                try:
                    remove_orchestra_user_locked(askey, hostname)
                except Exception:
                    pass

            log(f"Разлочена стратегия #{old_strategy} для {hostname} [{askey.upper()}]", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] Разлочена стратегия для {hostname} [{askey.upper()}] - начнётся переобучение")

            if self.unlock_callback:
                self.unlock_callback(hostname)

    def is_user_locked(self, hostname: str, proto: str = "tls") -> bool:
        """
        Проверяет, является ли стратегия ручной блокировкой (user lock).

        User locks не перезаписываются auto-lock от Lua.

        Args:
            hostname: Имя домена или IP
            proto: Протокол/askey (tls/http/quic/discord/wireguard/mtproto/dns/stun/unknown)

        Returns:
            True если это user lock
        """
        hostname = hostname.lower()
        askey = self._normalize_askey(proto)
        return hostname in self.user_locked_by_askey[askey]

    def clear(self) -> bool:
        """
        Очищает все залоченные стратегии и историю.

        Returns:
            True если очистка успешна
        """
        try:
            for askey in ASKEY_ALL:
                clear_orchestra_locked_map(askey)
                clear_orchestra_user_locked(askey)

            clear_orchestra_history()
            log("Очищены обученные стратегии, user locks и история в settings.json", "INFO")

            # Очищаем все словари по askey БЕЗ создания новых (сохраняем ссылки!)
            for askey in ASKEY_ALL:
                self.locked_by_askey[askey].clear()
                self.user_locked_by_askey[askey].clear()

            # Очищаем историю
            self.strategy_history.clear()

            if self.output_callback:
                self.output_callback("[INFO] Данные обучения и история сброшены")

            return True

        except Exception as e:
            log(f"Ошибка очистки данных обучения: {e}", "ERROR")
            return False

    def get_all(self) -> Dict[str, int]:
        """Возвращает словарь TLS locked стратегий {hostname: strategy}"""
        return self.locked_by_askey["tls"].copy()

    def get_all_by_askey(self, askey: str) -> Dict[str, int]:
        """Возвращает словарь locked стратегий для указанного askey {hostname: strategy}"""
        askey = self._normalize_askey(askey)
        return self.locked_by_askey[askey].copy()

    def get_learned_data(self) -> dict:
        """
        Возвращает данные обучения в формате для UI.

        Returns:
            Словарь с ключами для всех 9 askey:
            {
                'tls': {hostname: [strategy]},
                'http': {hostname: [strategy]},
                'quic': {ip: [strategy]},
                'discord': {ip: [strategy]},
                'wireguard': {ip: [strategy]},
                'mtproto': {hostname: [strategy]},
                'dns': {ip: [strategy]},
                'stun': {ip: [strategy]},
                'unknown': {ip: [strategy]},
                'history': {hostname: {strategy: {successes, failures, rate}}}
            }
        """
        # Загружаем если ещё не загружены
        has_any = any(self.locked_by_askey[askey] for askey in ASKEY_ALL)
        if not has_any:
            self.load()

        # Подготавливаем историю с рейтингами
        history_with_rates = {}
        for hostname, strategies in self.strategy_history.items():
            history_with_rates[hostname] = {}
            for strat_key, data in strategies.items():
                s = data.get('successes') or 0
                f = data.get('failures') or 0
                total = s + f
                rate = int((s / total) * 100) if total > 0 else 0
                history_with_rates[hostname][int(strat_key)] = {
                    'successes': s,
                    'failures': f,
                    'rate': rate
                }

        # Формируем результат для всех 9 askey
        result = {
            askey: {host: [strat] for host, strat in self.locked_by_askey[askey].items()}
            for askey in ASKEY_ALL
        }
        result['history'] = history_with_rates

        # Для backward compatibility добавляем 'udp' как alias для 'quic'
        result['udp'] = result['quic']

        return result

    # ==================== ИСТОРИЯ СТРАТЕГИЙ ====================

    def load_history(self):
        """Загружает историю стратегий из settings.json."""
        self.strategy_history = {}
        try:
            history_data = get_orchestra_history()
            for domain, json_str in history_data.items():
                if self._is_ignored_hostname(domain):
                    remove_orchestra_history_target(domain)
                    continue
                try:
                    if isinstance(json_str, dict):
                        self.strategy_history[domain] = json_str
                except Exception:
                    pass

            if self.strategy_history:
                log(f"Загружена история для {len(self.strategy_history)} доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки истории: {e}", "DEBUG")
            self.strategy_history = {}

    def save_history(self):
        """Сохраняет историю стратегий в settings.json."""
        try:
            sanitized: dict[str, dict[str, dict[str, int]]] = {}
            for domain, strategies in self.strategy_history.items():
                if self._is_ignored_hostname(domain):
                    remove_orchestra_history_target(domain)
                    continue
                sanitized[domain] = strategies
            set_orchestra_history(sanitized)
            log(f"Сохранена история для {len(self.strategy_history)} доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения истории: {e}", "ERROR")

    def update_history(self, hostname: str, strategy: int, successes: int, failures: int):
        """Обновляет историю для домена/стратегии (полная замена значений)"""
        if self._is_ignored_hostname(hostname):
            return
        if hostname not in self.strategy_history:
            self.strategy_history[hostname] = {}

        strat_key = str(strategy)
        self.strategy_history[hostname][strat_key] = {
            'successes': successes,
            'failures': failures
        }
        set_orchestra_history_for_target(hostname, self.strategy_history[hostname])

    def increment_history(self, hostname: str, strategy: int, is_success: bool):
        """Инкрементирует счётчик успехов или неудач для домена/стратегии"""
        if self._is_ignored_hostname(hostname):
            return
        if hostname not in self.strategy_history:
            self.strategy_history[hostname] = {}

        strat_key = str(strategy)
        if strat_key not in self.strategy_history[hostname]:
            self.strategy_history[hostname][strat_key] = {'successes': 0, 'failures': 0}

        if is_success:
            self.strategy_history[hostname][strat_key]['successes'] += 1
        else:
            self.strategy_history[hostname][strat_key]['failures'] += 1
        set_orchestra_history_for_target(hostname, self.strategy_history[hostname])

    def get_history_for_domain(self, hostname: str) -> dict:
        """Возвращает историю стратегий для домена с рейтингами"""
        if hostname not in self.strategy_history:
            return {}

        result = {}
        for strat_key, data in self.strategy_history[hostname].items():
            s = data.get('successes') or 0
            f = data.get('failures') or 0
            total = s + f
            rate = int((s / total) * 100) if total > 0 else 0
            result[int(strat_key)] = {
                'successes': s,
                'failures': f,
                'rate': rate
            }
        return result

    def get_best_strategy_from_history(self, hostname: str, exclude_strategy: int = None) -> Optional[int]:
        """
        Находит лучшую стратегию из истории для домена.

        Args:
            hostname: Домен для поиска
            exclude_strategy: Стратегия для исключения

        Returns:
            Номер лучшей стратегии или None
        """
        if hostname not in self.strategy_history:
            return None

        best_strategy = None
        best_rate = -1

        for strat_key, data in self.strategy_history[hostname].items():
            strat_num = int(strat_key)

            # Пропускаем исключённую стратегию
            if exclude_strategy is not None and strat_num == exclude_strategy:
                continue

            # Пропускаем заблокированные
            if self.blocked_manager and self.blocked_manager.is_blocked(hostname, strat_num):
                continue

            successes = data.get('successes') or 0
            failures = data.get('failures') or 0
            total = successes + failures

            if total == 0:
                continue

            rate = (successes / total) * 100

            if rate > best_rate:
                best_rate = rate
                best_strategy = strat_num

        return best_strategy
