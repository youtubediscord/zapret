"""
server_pool.py
────────────────────────────────────────────────────────────────
Умная балансировка нагрузки между VPS серверами
"""

import os
import json
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from log import log
from config import LOGS_FOLDER

from .server_config import (
    VPS_SERVERS,
    MAX_CONSECUTIVE_FAILURES,
    SERVER_BLOCK_DURATION,
    FAST_RESPONSE_THRESHOLD,
    AUTO_SWITCH_TO_FASTER,
)

# Файл статистики серверов
POOL_STATS_FILE = os.path.join(LOGS_FOLDER, '.server_pool_stats.json')

# Файл выбранного сервера
SELECTED_SERVER_FILE = os.path.join(LOGS_FOLDER, '.selected_server.json')


class ServerPool:
    """Пул серверов с балансировкой нагрузки и автоматическим переключением"""
    
    def __init__(self):
        self.servers = VPS_SERVERS.copy()
        self.stats = self._load_stats()
        self.selected_server = self._load_selected_server()

        if not self.servers:
            log("⚠️ ServerPool: нет серверов (UPDATE_SERVERS не задан в generated runtime config)", "POOL")
            self.selected_server = None
            return

        # Если нет выбранного сервера - выбираем случайный
        if not self.selected_server:
            self.selected_server = self._select_random_server()
            self._save_selected_server()

        log(f"🌐 ServerPool инициализирован: {len(self.servers)} серверов", "POOL")
        log(f"📍 Выбран сервер: {self.selected_server['name']}", "POOL")
    
    def _load_stats(self) -> Dict[str, Any]:
        """Загружает статистику серверов"""
        try:
            if os.path.exists(POOL_STATS_FILE):
                with open(POOL_STATS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            log(f"Ошибка загрузки статистики серверов: {e}", "⚠️ POOL")
        
        # Инициализируем пустую статистику
        stats = {}
        for server in self.servers:
            stats[server['id']] = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'consecutive_failures': 0,
                'avg_response_time': 0,
                'last_success': None,
                'last_failure': None,
                'blocked_until': None,
            }
        return stats
    
    def _save_stats(self):
        """Сохраняет статистику"""
        try:
            with open(POOL_STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            log(f"Ошибка сохранения статистики: {e}", "⚠️ POOL")
    
    def _load_selected_server(self) -> Optional[Dict[str, Any]]:
        """Загружает выбранный сервер"""
        try:
            if os.path.exists(SELECTED_SERVER_FILE):
                with open(SELECTED_SERVER_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    server_id = data.get('server_id')
                    
                    # Ищем сервер по ID
                    for server in self.servers:
                        if server['id'] == server_id:
                            return server
        except Exception as e:
            log(f"Ошибка загрузки выбранного сервера: {e}", "⚠️ POOL")
        
        return None
    
    def _save_selected_server(self):
        """Сохраняет выбранный сервер"""
        try:
            data = {
                'server_id': self.selected_server['id'],
                'selected_at': time.time(),
            }
            with open(SELECTED_SERVER_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log(f"Ошибка сохранения выбранного сервера: {e}", "⚠️ POOL")
    
    def _select_random_server(self) -> Dict[str, Any]:
        """
        Выбирает случайный сервер с учётом весов
        
        Пример: если есть 2 сервера с весами 60 и 40,
        то первый будет выбран в 60% случаев
        """
        # Фильтруем незаблокированные сервера
        available = self._get_available_servers()
        
        if not available:
            log("⚠️ Нет доступных серверов, используем первый из списка", "POOL")
            return self.servers[0]
        
        # Взвешенный случайный выбор
        total_weight = sum(s['weight'] for s in available)
        rand = random.uniform(0, total_weight)
        
        cumulative = 0
        for server in available:
            cumulative += server['weight']
            if rand <= cumulative:
                log(f"🎲 Случайный выбор: {server['name']} (вес: {server['weight']})", "POOL")
                return server
        
        # Fallback
        return available[0]
    
    def _get_available_servers(self) -> List[Dict[str, Any]]:
        """Возвращает список незаблокированных серверов"""
        available = []
        current_time = time.time()
        
        for server in self.servers:
            server_id = server['id']
            stats = self.stats.get(server_id, {})
            
            blocked_until = stats.get('blocked_until')
            
            if blocked_until and current_time < blocked_until:
                # Сервер заблокирован
                blocked_dt = datetime.fromtimestamp(blocked_until)
                log(f"🚫 {server['name']} заблокирован до {blocked_dt}", "POOL")
                continue
            
            available.append(server)
        
        return available
    
    def get_current_server(self) -> Dict[str, Any]:
        """Возвращает текущий выбранный сервер"""
        return self.selected_server
    
    def get_server_urls(self, server: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Возвращает URL'ы для сервера"""
        if server is None:
            server = self.selected_server
        
        return {
            'https': f"https://{server['host']}:{server['https_port']}",
            'http': f"http://{server['host']}:{server['http_port']}",
        }
    
    def record_success(self, server_id: str, response_time: float):
        """Записывает успешный запрос"""
        if server_id not in self.stats:
            return
        
        stats = self.stats[server_id]
        
        stats['total_requests'] += 1
        stats['successful_requests'] += 1
        stats['consecutive_failures'] = 0  # Сбрасываем счётчик ошибок
        stats['last_success'] = time.time()
        
        # Обновляем среднее время отклика (скользящее среднее)
        if stats['avg_response_time'] == 0:
            stats['avg_response_time'] = response_time
        else:
            # 80% старое значение + 20% новое
            stats['avg_response_time'] = stats['avg_response_time'] * 0.8 + response_time * 0.2
        
        self._save_stats()
        
        log(f"✅ {server_id}: успех ({response_time*1000:.0f}мс, среднее: {stats['avg_response_time']*1000:.0f}мс)", "POOL")
        
        # Проверяем, не стоит ли переключиться на более быстрый сервер
        if AUTO_SWITCH_TO_FASTER:
            self._check_faster_server()
    
    def record_failure(self, server_id: str, error: str):
        """Записывает неудачный запрос"""
        if server_id not in self.stats:
            return
        
        stats = self.stats[server_id]
        
        stats['total_requests'] += 1
        stats['failed_requests'] += 1
        stats['consecutive_failures'] += 1
        stats['last_failure'] = time.time()
        
        log(f"❌ {server_id}: ошибка ({stats['consecutive_failures']}/{MAX_CONSECUTIVE_FAILURES}) - {error[:50]}", "POOL")
        
        # Блокируем сервер при превышении лимита ошибок
        if stats['consecutive_failures'] >= MAX_CONSECUTIVE_FAILURES:
            stats['blocked_until'] = time.time() + SERVER_BLOCK_DURATION
            blocked_dt = datetime.fromtimestamp(stats['blocked_until'])
            
            log(f"🚫 {server_id} ЗАБЛОКИРОВАН до {blocked_dt} (слишком много ошибок)", "⚠️ POOL")
            
            # Переключаемся на другой сервер
            self._switch_to_next_server()
        
        self._save_stats()
    
    def _check_faster_server(self):
        """Проверяет, не стоит ли переключиться на более быстрый сервер"""
        current_id = self.selected_server['id']
        current_stats = self.stats.get(current_id, {})
        current_time = current_stats.get('avg_response_time', 999)
        
        # Если текущий сервер медленный, ищем альтернативу
        if current_time > FAST_RESPONSE_THRESHOLD / 1000:
            for server in self._get_available_servers():
                if server['id'] == current_id:
                    continue
                
                server_stats = self.stats.get(server['id'], {})
                server_time = server_stats.get('avg_response_time', 999)
                
                # Если другой сервер быстрее хотя бы на 30%
                if server_time < current_time * 0.7:
                    log(f"⚡ Переключение на более быстрый сервер: {server['name']} ({server_time*1000:.0f}мс vs {current_time*1000:.0f}мс)", "POOL")
                    self.selected_server = server
                    self._save_selected_server()
                    break
    
    def _switch_to_next_server(self):
        """Переключается на следующий доступный сервер"""
        available = self._get_available_servers()
        
        if not available:
            log("⚠️ Нет доступных серверов для переключения!", "POOL")
            return
        
        # Исключаем текущий сервер
        available = [s for s in available if s['id'] != self.selected_server['id']]
        
        if not available:
            log("⚠️ Все остальные сервера недоступны", "POOL")
            return
        
        # Выбираем сервер с наивысшим приоритетом
        available.sort(key=lambda s: s['priority'])
        new_server = available[0]
        
        log(f"🔄 Переключение: {self.selected_server['name']} → {new_server['name']}", "POOL")
        
        self.selected_server = new_server
        self._save_selected_server()
    
    def force_switch_server(self):
        """Принудительное переключение на другой сервер (для тестирования)"""
        available = [s for s in self._get_available_servers() if s['id'] != self.selected_server['id']]
        
        if available:
            self.selected_server = random.choice(available)
            self._save_selected_server()
            log(f"🔄 Принудительное переключение на {self.selected_server['name']}", "POOL")
            return True
        else:
            log("⚠️ Нет других доступных серверов", "POOL")
            return False
    
    # Алиас для совместимости
    force_switch = force_switch_server
    
    def is_server_blocked(self, server_id: str) -> bool:
        """Проверяет заблокирован ли сервер"""
        stats = self.stats.get(server_id, {})
        blocked_until = stats.get('blocked_until')
        if blocked_until and time.time() < blocked_until:
            return True
        return False
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Возвращает полную статистику всех серверов"""
        result = {}
        current_time = time.time()
        
        for server in self.servers:
            server_id = server['id']
            stats = self.stats.get(server_id, {})
            
            blocked_until = stats.get('blocked_until')
            is_blocked = blocked_until and current_time < blocked_until
            
            result[server['name']] = {
                'id': server_id,
                'host': server['host'],
                'priority': server['priority'],
                'weight': server['weight'],
                'total_requests': stats.get('total_requests', 0),
                'successful': stats.get('successful_requests', 0),
                'failed': stats.get('failed_requests', 0),
                'consecutive_failures': stats.get('consecutive_failures', 0),
                'avg_response_time': stats.get('avg_response_time', 0),
                'last_success': stats.get('last_success'),
                'last_failure': stats.get('last_failure'),
                'is_blocked': is_blocked,
                'blocked_until': blocked_until,
                'is_current': server_id == self.selected_server['id'],
            }
        
        return result
    
    def unblock_server(self, server_id: str) -> bool:
        """Разблокирует сервер (для админских функций)"""
        if server_id in self.stats:
            self.stats[server_id]['blocked_until'] = None
            self.stats[server_id]['consecutive_failures'] = 0
            self._save_stats()
            log(f"🔓 Сервер {server_id} разблокирован", "POOL")
            return True
        return False


# Singleton экземпляр
_pool_instance: Optional[ServerPool] = None

def get_server_pool() -> ServerPool:
    """Возвращает singleton экземпляр пула серверов"""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = ServerPool()
    return _pool_instance
