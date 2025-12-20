# orchestra/locked_strategies_manager.py
"""
Менеджер залоченных (зафиксированных) стратегий.

Залоченные стратегии - это стратегии, которые уже найдены оркестратором и работают для домена.
После успешного обучения (3 успеха подряд) стратегия "лочится" и используется постоянно.

Хранит:
- TLS стратегии: для HTTPS/TLS трафика
- HTTP стратегии: для HTTP трафика
- UDP стратегии: для QUIC/UDP трафика
- История: статистика успехов/неудач для каждой стратегии
"""

import json
from typing import Dict, Optional, Callable

from log import log
from config import REGISTRY_PATH
from config.reg import reg, reg_enumerate_values, reg_delete_all_values, reg_delete_value


# Пути в реестре для хранения обученных стратегий (subkeys)
REGISTRY_ORCHESTRA = f"{REGISTRY_PATH}\\Orchestra"
REGISTRY_ORCHESTRA_TLS = f"{REGISTRY_ORCHESTRA}\\TLS"          # TLS стратегии: domain=strategy (REG_DWORD)
REGISTRY_ORCHESTRA_HTTP = f"{REGISTRY_ORCHESTRA}\\HTTP"        # HTTP стратегии: domain=strategy (REG_DWORD)
REGISTRY_ORCHESTRA_UDP = f"{REGISTRY_ORCHESTRA}\\UDP"          # UDP стратегии: IP=strategy (REG_DWORD)
REGISTRY_ORCHESTRA_HISTORY = f"{REGISTRY_ORCHESTRA}\\History"  # История: domain=JSON (REG_SZ)


class LockedStrategiesManager:
    """
    Менеджер залоченных (зафиксированных) стратегий.

    Управляет списком стратегий, которые успешно работают для определённых доменов.
    После обучения стратегия лочится и используется постоянно, пока не будет разлочена.
    """

    def __init__(self, blocked_manager=None):
        """
        Args:
            blocked_manager: BlockedStrategiesManager для проверки заблокированных стратегий
        """
        # Залоченные стратегии: {hostname: strategy}
        self.locked_strategies: Dict[str, int] = {}          # TLS
        self.http_locked_strategies: Dict[str, int] = {}     # HTTP
        self.udp_locked_strategies: Dict[str, int] = {}      # UDP

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

    def _migrate_old_registry_format(self):
        """Мигрирует старый формат (JSON в одном ключе) в новый (subkeys)"""
        try:
            # Проверяем есть ли старые данные
            old_tls = reg(REGISTRY_ORCHESTRA, "LearnedStrategies")
            old_http = reg(REGISTRY_ORCHESTRA, "LearnedStrategiesHTTP")
            old_history = reg(REGISTRY_ORCHESTRA, "StrategyHistory")

            migrated = False

            # Мигрируем TLS
            if old_tls and old_tls != "{}":
                try:
                    data = json.loads(old_tls)
                    for domain, strategy in data.items():
                        reg(REGISTRY_ORCHESTRA_TLS, domain, int(strategy))
                    reg(REGISTRY_ORCHESTRA, "LearnedStrategies", None)  # Удаляем старый ключ
                    migrated = True
                    log(f"Мигрировано {len(data)} TLS стратегий в новый формат", "INFO")
                except Exception:
                    pass

            # Мигрируем HTTP
            if old_http and old_http != "{}":
                try:
                    data = json.loads(old_http)
                    for domain, strategy in data.items():
                        reg(REGISTRY_ORCHESTRA_HTTP, domain, int(strategy))
                    reg(REGISTRY_ORCHESTRA, "LearnedStrategiesHTTP", None)  # Удаляем старый ключ
                    migrated = True
                    log(f"Мигрировано {len(data)} HTTP стратегий в новый формат", "INFO")
                except Exception:
                    pass

            # Мигрируем историю
            if old_history and old_history != "{}":
                try:
                    data = json.loads(old_history)
                    for domain, strategies in data.items():
                        json_str = json.dumps(strategies, ensure_ascii=False)
                        reg(REGISTRY_ORCHESTRA_HISTORY, domain, json_str)
                    reg(REGISTRY_ORCHESTRA, "StrategyHistory", None)  # Удаляем старый ключ
                    migrated = True
                    log(f"Мигрирована история для {len(data)} доменов в новый формат", "INFO")
                except Exception:
                    pass

            if migrated:
                log("Миграция реестра завершена", "INFO")

        except Exception as e:
            log(f"Ошибка миграции реестра: {e}", "DEBUG")

    # ==================== ЗАГРУЗКА/СОХРАНЕНИЕ ====================

    def load(self) -> Dict[str, int]:
        """
        Загружает залоченные стратегии и историю из реестра.

        Returns:
            Словарь TLS стратегий {hostname: strategy}
        """
        # Очищаем существующие словари БЕЗ создания новых (сохраняем ссылки!)
        self.locked_strategies.clear()
        self.http_locked_strategies.clear()
        self.udp_locked_strategies.clear()

        # Сначала мигрируем старый формат если есть
        self._migrate_old_registry_format()

        try:
            # TLS стратегии
            tls_data = reg_enumerate_values(REGISTRY_ORCHESTRA_TLS)
            for domain, strategy in tls_data.items():
                self.locked_strategies[domain] = int(strategy)

            # HTTP стратегии
            http_data = reg_enumerate_values(REGISTRY_ORCHESTRA_HTTP)
            for domain, strategy in http_data.items():
                self.http_locked_strategies[domain] = int(strategy)

            # UDP стратегии
            udp_data = reg_enumerate_values(REGISTRY_ORCHESTRA_UDP)
            for ip, strategy in udp_data.items():
                self.udp_locked_strategies[ip] = int(strategy)

            total = len(self.locked_strategies) + len(self.http_locked_strategies) + len(self.udp_locked_strategies)
            if total:
                log(f"Загружено {len(self.locked_strategies)} TLS + {len(self.http_locked_strategies)} HTTP + {len(self.udp_locked_strategies)} UDP стратегий", "INFO")

            # Очистка доменов со strategy=1 для дефолтно заблокированных
            self._clean_blocked_conflicts()

        except Exception as e:
            log(f"Ошибка загрузки стратегий из реестра: {e}", "DEBUG")

        # Загружаем историю
        self.load_history()

        return self.locked_strategies

    def _clean_blocked_conflicts(self):
        """Удаляет locked стратегии которые конфликтуют с blocked"""
        if not self.blocked_manager:
            return

        from .blocked_strategies_manager import is_default_blocked_pass_domain

        # Очистка s1 для дефолтно заблокированных доменов
        blocked_cleaned = []
        for domain, strategy in list(self.locked_strategies.items()):
            if strategy == 1 and is_default_blocked_pass_domain(domain):
                blocked_cleaned.append(domain)
                del self.locked_strategies[domain]
                try:
                    reg_delete_value(REGISTRY_ORCHESTRA_TLS, domain)
                except Exception:
                    pass

        for domain, strategy in list(self.http_locked_strategies.items()):
            if strategy == 1 and is_default_blocked_pass_domain(domain):
                blocked_cleaned.append(domain)
                del self.http_locked_strategies[domain]
                try:
                    reg_delete_value(REGISTRY_ORCHESTRA_HTTP, domain)
                except Exception:
                    pass

        if blocked_cleaned:
            log(f"Очищено {len(blocked_cleaned)} доменов со strategy=1: {', '.join(blocked_cleaned[:5])}{'...' if len(blocked_cleaned) > 5 else ''}", "INFO")

        # Очистка конфликтов: locked + blocked = удаляем lock
        conflicts_cleaned = []

        for domain, strategy in list(self.locked_strategies.items()):
            if self.blocked_manager.is_blocked(domain, strategy):
                conflicts_cleaned.append((domain, strategy, "TLS"))
                del self.locked_strategies[domain]
                try:
                    reg_delete_value(REGISTRY_ORCHESTRA_TLS, domain)
                except Exception:
                    pass

        for domain, strategy in list(self.http_locked_strategies.items()):
            if self.blocked_manager.is_blocked(domain, strategy):
                conflicts_cleaned.append((domain, strategy, "HTTP"))
                del self.http_locked_strategies[domain]
                try:
                    reg_delete_value(REGISTRY_ORCHESTRA_HTTP, domain)
                except Exception:
                    pass

        for ip, strategy in list(self.udp_locked_strategies.items()):
            if self.blocked_manager.is_blocked(ip, strategy):
                conflicts_cleaned.append((ip, strategy, "UDP"))
                del self.udp_locked_strategies[ip]
                try:
                    reg_delete_value(REGISTRY_ORCHESTRA_UDP, ip)
                except Exception:
                    pass

        if conflicts_cleaned:
            log(f"Очищено {len(conflicts_cleaned)} конфликтующих LOCK:", "INFO")
            for domain, strategy, proto in conflicts_cleaned[:10]:
                log(f"  - {domain} strategy={strategy} [{proto}]", "INFO")

    def save(self):
        """Сохраняет залоченные стратегии в реестр"""
        try:
            # TLS стратегии
            for domain, strategy in self.locked_strategies.items():
                reg(REGISTRY_ORCHESTRA_TLS, domain, int(strategy))

            # HTTP стратегии
            for domain, strategy in self.http_locked_strategies.items():
                reg(REGISTRY_ORCHESTRA_HTTP, domain, int(strategy))

            # UDP стратегии
            for ip, strategy in self.udp_locked_strategies.items():
                reg(REGISTRY_ORCHESTRA_UDP, ip, int(strategy))

            log(f"Сохранено {len(self.locked_strategies)} TLS + {len(self.http_locked_strategies)} HTTP + {len(self.udp_locked_strategies)} UDP стратегий", "DEBUG")

        except Exception as e:
            log(f"Ошибка сохранения стратегий в реестр: {e}", "ERROR")

    # ==================== LOCK/UNLOCK ====================

    def lock(self, hostname: str, strategy: int, proto: str = "tls"):
        """
        Залочивает (фиксирует) стратегию для домена.

        Args:
            hostname: Имя домена или IP
            strategy: Номер стратегии
            proto: Протокол (tls/http/udp)
        """
        hostname = hostname.lower()
        proto = proto.lower()

        # Выбираем нужный словарь и реестр
        if proto == "http":
            target_dict = self.http_locked_strategies
            reg_path = REGISTRY_ORCHESTRA_HTTP
        elif proto == "udp":
            target_dict = self.udp_locked_strategies
            reg_path = REGISTRY_ORCHESTRA_UDP
        else:  # tls
            target_dict = self.locked_strategies
            reg_path = REGISTRY_ORCHESTRA_TLS

        # Сохраняем стратегию
        target_dict[hostname] = strategy
        reg(reg_path, hostname, strategy)

        log(f"Залочена стратегия #{strategy} для {hostname} [{proto.upper()}]", "INFO")

        if self.output_callback:
            self.output_callback(f"[INFO] 🔒 Залочена стратегия #{strategy} для {hostname} [{proto.upper()}]")

        if self.lock_callback:
            self.lock_callback(hostname, strategy)

    def unlock(self, hostname: str, proto: str = "tls"):
        """
        Разлочивает (снимает фиксацию) стратегию для домена.

        Args:
            hostname: Имя домена или IP
            proto: Протокол (tls/http/udp)
        """
        hostname = hostname.lower()
        proto = proto.lower()

        # Выбираем нужный словарь и реестр
        if proto == "http":
            target_dict = self.http_locked_strategies
            reg_path = REGISTRY_ORCHESTRA_HTTP
        elif proto == "udp":
            target_dict = self.udp_locked_strategies
            reg_path = REGISTRY_ORCHESTRA_UDP
        else:  # tls
            target_dict = self.locked_strategies
            reg_path = REGISTRY_ORCHESTRA_TLS

        if hostname in target_dict:
            old_strategy = target_dict[hostname]
            del target_dict[hostname]
            # Удаляем из реестра
            try:
                reg(reg_path, hostname, None)  # None = удалить значение
            except Exception:
                pass

            log(f"Разлочена стратегия #{old_strategy} для {hostname} [{proto.upper()}]", "INFO")

            if self.output_callback:
                self.output_callback(f"[INFO] 🔓 Разлочена стратегия для {hostname} [{proto.upper()}] — начнётся переобучение")

            if self.unlock_callback:
                self.unlock_callback(hostname)

    def clear(self) -> bool:
        """
        Очищает все залоченные стратегии и историю.

        Returns:
            True если очистка успешна
        """
        try:
            # Очищаем subkeys в реестре
            reg_delete_all_values(REGISTRY_ORCHESTRA_TLS)
            reg_delete_all_values(REGISTRY_ORCHESTRA_HTTP)
            reg_delete_all_values(REGISTRY_ORCHESTRA_UDP)
            reg_delete_all_values(REGISTRY_ORCHESTRA_HISTORY)
            log("Очищены обученные стратегии и история в реестре", "INFO")

            # Очищаем БЕЗ создания новых словарей (сохраняем ссылки!)
            self.locked_strategies.clear()
            self.http_locked_strategies.clear()
            self.udp_locked_strategies.clear()
            self.strategy_history.clear()

            if self.output_callback:
                self.output_callback("[INFO] Данные обучения и история сброшены")

            return True

        except Exception as e:
            log(f"Ошибка очистки данных обучения: {e}", "ERROR")
            return False

    def get_all(self) -> Dict[str, int]:
        """Возвращает словарь TLS locked стратегий {hostname: strategy}"""
        return self.locked_strategies.copy()

    def get_learned_data(self) -> dict:
        """
        Возвращает данные обучения в формате для UI.

        Returns:
            Словарь {
                'tls': {hostname: [strategy]},
                'http': {hostname: [strategy]},
                'udp': {ip: [strategy]},
                'history': {hostname: {strategy: {successes, failures, rate}}}
            }
        """
        # Загружаем если ещё не загружены
        if not self.locked_strategies and not self.http_locked_strategies and not self.udp_locked_strategies:
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

        return {
            'tls': {host: [strat] for host, strat in self.locked_strategies.items()},
            'http': {host: [strat] for host, strat in self.http_locked_strategies.items()},
            'udp': {ip: [strat] for ip, strat in self.udp_locked_strategies.items()},
            'history': history_with_rates
        }

    # ==================== ИСТОРИЯ СТРАТЕГИЙ ====================

    def load_history(self):
        """Загружает историю стратегий из реестра"""
        self.strategy_history = {}
        try:
            history_data = reg_enumerate_values(REGISTRY_ORCHESTRA_HISTORY)
            for domain, json_str in history_data.items():
                try:
                    self.strategy_history[domain] = json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            if self.strategy_history:
                log(f"Загружена история для {len(self.strategy_history)} доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка загрузки истории: {e}", "DEBUG")
            self.strategy_history = {}

    def save_history(self):
        """Сохраняет историю стратегий в реестр"""
        try:
            for domain, strategies in self.strategy_history.items():
                json_str = json.dumps(strategies, ensure_ascii=False)
                reg(REGISTRY_ORCHESTRA_HISTORY, domain, json_str)
            log(f"Сохранена история для {len(self.strategy_history)} доменов", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения истории: {e}", "ERROR")

    def update_history(self, hostname: str, strategy: int, successes: int, failures: int):
        """Обновляет историю для домена/стратегии (полная замена значений)"""
        if hostname not in self.strategy_history:
            self.strategy_history[hostname] = {}

        strat_key = str(strategy)
        self.strategy_history[hostname][strat_key] = {
            'successes': successes,
            'failures': failures
        }

    def increment_history(self, hostname: str, strategy: int, is_success: bool):
        """Инкрементирует счётчик успехов или неудач для домена/стратегии"""
        if hostname not in self.strategy_history:
            self.strategy_history[hostname] = {}

        strat_key = str(strategy)
        if strat_key not in self.strategy_history[hostname]:
            self.strategy_history[hostname][strat_key] = {'successes': 0, 'failures': 0}

        if is_success:
            self.strategy_history[hostname][strat_key]['successes'] += 1
        else:
            self.strategy_history[hostname][strat_key]['failures'] += 1

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
