"""
release_manager.py
────────────────────────────────────────────────────────────────
Менеджер получения релизов с балансировкой серверов.
Приоритет: VPS Pool (HTTPS/HTTP) -> GitHub API
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
import requests
import os
import json
import time
import urllib3
from datetime import datetime

from .server_config import (
    CONNECT_TIMEOUT, READ_TIMEOUT, should_verify_ssl,
    VPS_SERVERS  # ✅ НОВЫЙ ИМПОРТ
)
from .server_pool import get_server_pool  # ✅ НОВЫЙ ИМПОРТ

from .github_release import (
    get_latest_release as github_get_latest_release, 
    normalize_version, 
    is_rate_limited
)
from log import log
from config import CHANNEL, LOGS_FOLDER

# Отключаем предупреждения SSL для самоподписанных сертификатов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ ИСПРАВЛЕННЫЕ ПУТИ
VPS_BLOCK_FILE = os.path.join(LOGS_FOLDER, '.vps_block.json')
STATS_FILE = os.path.join(LOGS_FOLDER, '.server_stats.json')

# Длительность блокировки VPS (применяется ко ВСЕМ серверам)
VPS_BLOCK_DURATION = 24 * 3600  # 24 часа

# Включать ли HEAD‑проверку файла на VPS (лучше отключить)
ENABLE_FILE_HEAD_CHECK = False

# Таймаут для запросов
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

class ServerStats:
    """Класс для хранения статистики серверов (legacy, для обратной совместимости)"""
    
    def __init__(self):
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict[str, Dict[str, Any]]:
        """Загружает статистику из файла"""
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save_stats(self):
        """Сохраняет статистику в файл"""
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f)
        except:
            pass
    
    def record_success(self, server_name: str, response_time: float):
        """Записывает успешный запрос"""
        if server_name not in self.stats:
            self.stats[server_name] = {
                'successes': 0,
                'failures': 0,
                'avg_response_time': 0,
                'last_success': None,
                'last_failure': None
            }
        
        stats = self.stats[server_name]
        stats['successes'] += 1
        stats['last_success'] = time.time()
        
        # Обновляем среднее время ответа
        if stats['avg_response_time'] == 0:
            stats['avg_response_time'] = response_time
        else:
            stats['avg_response_time'] = (stats['avg_response_time'] + response_time) / 2
        
        self._save_stats()
    
    def record_failure(self, server_name: str):
        """Записывает неудачный запрос"""
        if server_name not in self.stats:
            self.stats[server_name] = {
                'successes': 0,
                'failures': 0,
                'avg_response_time': 0,
                'last_success': None,
                'last_failure': None
            }
        
        self.stats[server_name]['failures'] += 1
        self.stats[server_name]['last_failure'] = time.time()
        self._save_stats()
    
    def get_success_rate(self, server_name: str) -> float:
        """Возвращает процент успешных запросов"""
        if server_name not in self.stats:
            return 0.5
        
        stats = self.stats[server_name]
        total = stats['successes'] + stats['failures']
        if total == 0:
            return 0.5
        
        return stats['successes'] / total

class ReleaseManager:
    """Менеджер для получения информации о релизах с балансировкой серверов"""
    
    def __init__(self):
        self.last_error: Optional[str] = None
        self.last_source: Optional[str] = None
        self.server_stats = ServerStats()  # Legacy статистика
        self._vps_block_until = self._load_vps_block_until()
        
        # ✅ ИНИЦИАЛИЗАЦИЯ ПУЛА СЕРВЕРОВ
        if VPS_SERVERS:
            self.server_pool = get_server_pool()
            log(f"🌐 ReleaseManager: пул серверов инициализирован ({len(VPS_SERVERS)} серверов)", "🔄 RELEASE")
        else:
            self.server_pool = None
            log("⚠️ ReleaseManager: нет серверов в пуле, используем только GitHub", "🔄 RELEASE")

    def get_latest_release(self, channel: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о последнем релизе
        
        Приоритет источников:
        1. Telegram (основной, быстрый)
        2. VPS серверы (резерв)
        3. GitHub API (fallback)
        
        Args:
            channel: "stable" или "dev"
            
        Returns:
            Dict с информацией о релизе или None
        """
        # ✅ 1. ПРОБУЕМ TELEGRAM (основной источник)
        result = self._try_telegram(channel)
        if result:
            return result
        
        # ✅ 2. ПРОВЕРЯЕМ ГЛОБАЛЬНУЮ БЛОКИРОВКУ VPS
        vps_blocked = self._is_vps_blocked()
        
        if vps_blocked:
            dt = datetime.fromtimestamp(self._vps_block_until)
            log(f"🚫 ВСЕ VPS серверы заблокированы до {dt}, используем только GitHub", "🔄 RELEASE")
            return self._try_github(channel)
        
        # ✅ 3. ЕСЛИ ЕСТЬ ПУЛ СЕРВЕРОВ - используем балансировку
        if self.server_pool and VPS_SERVERS:
            result = self._try_server_pool(channel)
            if result:
                return result
            
            # Пул не сработал - пробуем GitHub
            log("⚠️ Все VPS серверы недоступны, переключаемся на GitHub", "🔄 RELEASE")
            return self._try_github(channel)
        
        # ✅ 4. FALLBACK: GitHub
        log("⚠️ Пул серверов пуст, используем только GitHub", "🔄 RELEASE")
        return self._try_github(channel)
    
    def _try_telegram(self, channel: str) -> Optional[Dict[str, Any]]:
        """
        Пытается получить информацию о релизе из Telegram
        
        Args:
            channel: "stable" или "dev"
            
        Returns:
            Dict с информацией о релизе или None
        """
        try:
            from .telegram_updater import is_telegram_available, get_telegram_version_info
            
            if not is_telegram_available():
                log("⏭️ Telegram недоступен (telethon не установлен)", "🔄 RELEASE")
                return None
            
            # Маппинг каналов
            tg_channel = 'test' if channel == 'dev' else 'stable'
            
            log(f"📱 Проверка обновлений через Telegram ({tg_channel})...", "🔄 RELEASE")
            
            start_time = time.time()
            info = get_telegram_version_info(tg_channel)
            response_time = time.time() - start_time
            
            if info and info.get('version'):
                version = normalize_version(info['version'])
                
                log(f"✅ Telegram: версия {version} ({response_time:.2f}с)", "🔄 RELEASE")
                
                # Формируем результат в стандартном формате
                return {
                    "version": version,
                    "tag_name": f"v{version}",
                    "update_url": f"telegram://{info['channel']}/{info['message_id']}",  # Специальный URL
                    "release_notes": "",
                    "prerelease": channel == "dev",
                    "name": f"Zapret {version} ({channel})",
                    "published_at": info.get('date', ''),
                    "source": info['source'],
                    "verify_ssl": True,
                    "file_size": info.get('file_size'),
                    "telegram_info": info,  # Сохраняем полную информацию для скачивания
                }
            
            log(f"⚠️ Telegram: версия не найдена ({response_time:.2f}с)", "🔄 RELEASE")
            return None
            
        except Exception as e:
            log(f"❌ Telegram ошибка: {e}", "🔄 RELEASE")
            return None

    def _try_server_pool(self, channel: str) -> Optional[Dict[str, Any]]:
        """
        Пытается получить релиз из пула серверов с балансировкой.
        Перебирает все доступные серверы, пропуская заблокированные.
        
        Args:
            channel: "stable" или "dev"
            
        Returns:
            Dict с информацией о релизе или None
        """
        # Перебираем все серверы из пула
        tried_servers = set()
        max_attempts = len(VPS_SERVERS) * 2  # На случай переключений
        
        for attempt in range(max_attempts):
            # Получаем текущий выбранный сервер
            current_server = self.server_pool.get_current_server()
            server_id = current_server['id']
            
            # Проверяем не заблокирован ли сервер
            if self.server_pool.is_server_blocked(server_id):
                log(f"⏭️ {current_server['name']} заблокирован, пропускаем", "🔄 RELEASE")
                # Принудительно переключаемся на другой сервер
                self.server_pool.force_switch()
                if server_id in tried_servers:
                    continue  # Уже пробовали этот сервер
                tried_servers.add(server_id)
                continue
            
            # Если уже пробовали этот сервер - все серверы перебраны
            if server_id in tried_servers:
                break
                
            tried_servers.add(server_id)
            server_urls = self.server_pool.get_server_urls(current_server)
            
            log(f"📍 Выбран сервер: {current_server['name']} ({current_server['host']})", "🔄 RELEASE")
            
            # Пробуем HTTPS
            result = self._try_vps_url(
                channel=channel,
                server=current_server,
                url=server_urls['https'],
                protocol='HTTPS'
            )
            
            if result:
                return result
            
            # Проверяем не заблокировали ли сервер после HTTPS попытки
            if self.server_pool.is_server_blocked(server_id):
                log(f"🔄 {current_server['name']} заблокирован после HTTPS, переключаемся", "🔄 RELEASE")
                continue  # Переходим к следующему серверу
            
            # Пробуем HTTP только если сервер не заблокирован
            result = self._try_vps_url(
                channel=channel,
                server=current_server,
                url=server_urls['http'],
                protocol='HTTP'
            )
            
            if result:
                return result
        
        return None

    def _try_vps_url(
        self, 
        channel: str, 
        server: Dict[str, Any], 
        url: str, 
        protocol: str
    ) -> Optional[Dict[str, Any]]:
        """
        Пытается получить релиз с конкретного URL
        
        Args:
            channel: "stable" или "dev"
            server: Информация о сервере из пула
            url: Базовый URL сервера
            protocol: "HTTPS" или "HTTP"
            
        Returns:
            Dict с информацией о релизе или None
        """
        from .update_cache import get_cached_all_versions, set_cached_all_versions, get_all_versions_source
        
        server_id = server['id']
        server_name = f"{server['name']} ({protocol})"
        
        log(f"🔍 Проверка через {server_name}...", "🔄 RELEASE")
        
        # ✅ ПРОВЕРЯЕМ IN-MEMORY КЭШ СНАЧАЛА
        cached_all_versions = get_cached_all_versions()
        if cached_all_versions:
            log(f"📦 Используем in-memory кэш all_versions (источник: {get_all_versions_source()})", "🔄 RELEASE")
            all_data = cached_all_versions
            # Пропускаем сетевой запрос, используем кэш
            start_time = time.time()
            response_time = 0.001  # Мгновенно из кэша
        else:
            start_time = time.time()
            
            try:
                # Формируем URL API
                api_url = f"{url}/api/all_versions.json"
                
                # Определяем проверку SSL
                verify_ssl = should_verify_ssl() if protocol == 'HTTPS' else False
                
                log(f"📡 Запрос к {api_url} (verify_ssl={verify_ssl})", "🔄 RELEASE")
                
                # Отключаем предупреждения SSL
                if not verify_ssl:
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                # Делаем запрос
                response = requests.get(
                    api_url,
                    timeout=TIMEOUT,
                    verify=verify_ssl,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Zapret-Updater/3.1",
                        "Cache-Control": "no-cache"
                    }
                )
                response.raise_for_status()
                
                all_data = response.json()
                response_time = time.time() - start_time  # ✅ Вычисляем время ответа
                
                # ✅ КЭШИРУЕМ РЕЗУЛЬТАТ
                set_cached_all_versions(all_data, server_name)
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else 'unknown'
                error_msg = f"HTTP {status_code}"
                
                log(f"❌ {server_name}: {error_msg}", "🔄 RELEASE")
                
                # Записываем ошибку
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
                
                # При серьёзных ошибках блокируем ВСЕ VPS
                if isinstance(status_code, int) and 500 <= status_code < 600:
                    self._block_vps(f"HTTP {status_code} from {server_name}")
                
                self.last_error = error_msg
                return None
            
            except requests.exceptions.Timeout:
                error_msg = "timeout"
                log(f"❌ {server_name}: {error_msg}", "🔄 RELEASE")
                
                # Записываем ошибку
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
                
                self.last_error = error_msg
                return None
            
            except requests.exceptions.ConnectionError as e:
                error_msg = f"connection error: {str(e)[:50]}"
                log(f"❌ {server_name}: {error_msg}", "🔄 RELEASE")
                
                # Записываем ошибку
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
                
                self.last_error = error_msg
                return None
            
            except requests.exceptions.SSLError as e:
                error_msg = f"SSL error: {str(e)[:50]}"
                log(f"❌ {server_name}: {error_msg}", "🔄 RELEASE")
                
                # Записываем ошибку
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
                
                self.last_error = error_msg
                return None
            
            except Exception as e:
                error_msg = f"error: {str(e)[:50]}"
                log(f"❌ {server_name}: {error_msg}", "🔄 RELEASE")
                
                # Записываем ошибку
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
                
                self.last_error = error_msg
                return None
        
        # ✅ Теперь обрабатываем all_data (из кэша или из запроса)
        # Преобразуем channel (dev -> test для API)
        api_channel = "test" if channel == "dev" else channel
        
        if api_channel not in all_data or not all_data[api_channel]:
            error_msg = f"Канал {api_channel} не найден"
            log(f"⚠️ {server_name}: {error_msg}", "🔄 RELEASE")
            
            # Записываем ошибку только если это не кэш
            if not cached_all_versions:
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
            
            return None
        
        data = all_data[api_channel]
        
        if not data.get("version"):
            error_msg = f"Отсутствует версия для {api_channel}"
            log(f"⚠️ {server_name}: {error_msg}", "🔄 RELEASE")
            
            # Записываем ошибку только если это не кэш
            if not cached_all_versions:
                self.server_pool.record_failure(server_id, error_msg)
                self.server_stats.record_failure(server_name)
            
            return None
        
        # ✅ УСПЕХ - формируем результат
        # Записываем успех только если это не кэш
        if not cached_all_versions:
            self.server_pool.record_success(server_id, response_time)
            self.server_stats.record_success(server_name, response_time)
        
        # Формируем URL для скачивания
        filename = f"Zapret2Setup{'_TEST' if api_channel == 'test' else ''}.exe"
        download_url = f"{url}/download/{filename}"
        
        # Определяем verify_ssl для результата
        verify_ssl = should_verify_ssl() if protocol == 'HTTPS' else False
        
        log(f"📦 {server_name}: версия {data['version']}, файл: {filename}", "🔄 RELEASE")
        log(f"✅ {server_name}: успех ({response_time*1000:.0f}мс)", "🔄 RELEASE")
        
        result = {
            "version": normalize_version(data.get("version", "0.0.0")),
            "tag_name": f"v{data.get('version', '0.0.0')}",
            "update_url": download_url,
            "release_notes": data.get("release_notes", ""),
            "prerelease": channel == "dev",
            "name": f"Zapret {data.get('version', '0.0.0')} ({api_channel})",
            "published_at": data.get("date", ""),
            "source": server_name,
            "verify_ssl": verify_ssl,
            "file_size": data.get("file_size"),
            "mtime": data.get("mtime"),
            "modified_at": data.get("modified_at")
        }
        
        # Дополнительная информация
        if data.get("file_size"):
            size_mb = data["file_size"] / (1024 * 1024)
            log(f"📊 Размер файла: {size_mb:.2f} MB", "🔄 RELEASE")
        
        if data.get("modified_at"):
            log(f"🕒 Обновлено: {data['modified_at']}", "🔄 RELEASE")
        
        # HEAD-проверка (опционально)
        if ENABLE_FILE_HEAD_CHECK:
            self._check_file_availability(download_url, verify_ssl, data.get("file_size"))
        else:
            log("⏭ Пропускаем HEAD‑проверку файла (отключено в клиенте)", "🔄 RELEASE")
        
        self.last_source = server_name
        self.last_error = None
        
        return result

    def _check_file_availability(self, url: str, verify_ssl: bool, expected_size: Optional[int]):
        """Проверяет доступность файла через HEAD запрос"""
        try:
            head_response = requests.head(
                url,
                timeout=(3, 5),
                verify=verify_ssl,
                allow_redirects=True
            )
            
            if head_response.status_code == 200:
                content_length = head_response.headers.get('Content-Length')
                
                if content_length and expected_size:
                    reported_size = int(content_length)
                    
                    if reported_size != expected_size:
                        log(f"⚠️ Размер файла не совпадает: {reported_size} != {expected_size}", "🔄 RELEASE")
                    else:
                        log(f"✅ Файл доступен для скачивания (размер совпадает)", "🔄 RELEASE")
                else:
                    log(f"✅ Файл доступен для скачивания", "🔄 RELEASE")
            else:
                log(f"⚠️ Файл вернул статус {head_response.status_code}", "🔄 RELEASE")
                
        except Exception as e:
            log(f"⚠️ Не удалось проверить доступность файла: {e}", "🔄 RELEASE")
        
    def _try_github(self, channel: str) -> Optional[Dict[str, Any]]:
        """Пытается получить релиз с GitHub"""
        log(f"🔍 Проверка обновлений через GitHub API...", "🔄 RELEASE")
        
        start_time = time.time()
        
        try:
            result = github_get_latest_release(channel)
            
            if result:
                response_time = time.time() - start_time
                
                result['source'] = 'GitHub API'
                
                # Записываем успех
                self.server_stats.record_success('GitHub API', response_time)
                
                log(f"✅ GitHub API: найден релиз {result['version']} ({response_time:.2f}с)", "🔄 RELEASE")
                
                self.last_source = 'GitHub API'
                self.last_error = None
                
                return result
            else:
                log(f"❌ GitHub API: релиз не найден", "🔄 RELEASE")
                self.server_stats.record_failure('GitHub API')
                
        except Exception as e:
            error_msg = str(e)[:100]
            log(f"❌ GitHub API: {error_msg}", "🔄 RELEASE")
            
            self.server_stats.record_failure('GitHub API')
            self.last_error = error_msg
            
        return None

    def get_server_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику всех источников"""
        stats = {}
        
        # ✅ Статистика из пула серверов
        if self.server_pool:
            pool_stats = self.server_pool.get_all_stats()
            stats.update(pool_stats)
        
        # ✅ Добавляем legacy статистику (GitHub и т.д.)
        for server_name, server_stats in self.server_stats.stats.items():
            if server_name not in stats:
                stats[server_name] = server_stats
        
        return stats

    def get_vps_block_info(self) -> Dict[str, Any]:
        """Информация о временной блокировке VPS"""
        blocked = self._is_vps_blocked()
        until_ts = self._vps_block_until if blocked else 0
        until_dt = datetime.fromtimestamp(until_ts) if blocked else None
        return {
            "blocked": blocked,
            "until_ts": until_ts,
            "until_dt": until_dt,
        }

    def _load_vps_block_until(self) -> float:
        """Читает из файла до какого времени заблокирован VPS"""
        try:
            if os.path.exists(VPS_BLOCK_FILE):
                with open(VPS_BLOCK_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return float(data.get("until", 0))
        except Exception:
            pass
        return 0.0

    def _is_vps_blocked(self) -> bool:
        """Проверяет, заблокирован ли VPS сейчас"""
        return time.time() < self._vps_block_until

    def _block_vps(self, reason: str):
        """
        Блокирует ВСЕ VPS серверы на сутки
        (Индивидуальная блокировка серверов управляется ServerPool)
        """
        self._vps_block_until = time.time() + VPS_BLOCK_DURATION
        data = {"until": self._vps_block_until, "reason": reason}
        
        try:
            with open(VPS_BLOCK_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            log(f"⚠️ Не удалось сохранить блокировку VPS: {e}", "🔄 RELEASE")
        
        dt = datetime.fromtimestamp(self._vps_block_until)
        log(f"🚫 ВСЕ VPS серверы заблокированы до {dt} из‑за: {reason}", "🔄 RELEASE")

    def disable_vps_for_a_day(self, reason: str = "manual"):
        """Публичный метод для ручной блокировки VPS"""
        self._block_vps(reason)


# ✅ ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
_release_manager = ReleaseManager()


# ──────────────────────────── PUBLIC API С КЭШЕМ ──────────────────────────────

def get_latest_release(channel: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последнем релизе с поддержкой кэширования
    
    Args:
        channel: "stable" или "dev"
        use_cache: Использовать кэш (False для принудительной проверки)
        
    Returns:
        Dict с информацией о релизе или None
    """
    from .update_cache import UpdateCache
    
    # ✅ ПРОВЕРЯЕМ КЭШ только если use_cache=True
    if use_cache:
        cached = UpdateCache.get_cached_release(channel)
        if cached:
            log(f"📦 Используем кэшированную информацию о релизе {cached['version']} (источник: {cached.get('source', 'неизвестен')})", "🔄 RELEASE")
            return cached
    else:
        log(f"🔄 Принудительная проверка обновлений (игнорируем кэш)", "🔄 RELEASE")
    
    # Кэша нет ИЛИ принудительная проверка - делаем запрос
    log(f"🌐 Запрос к серверу для получения информации о релизе", "🔄 RELEASE")
    
    # ✅ ВЫЗЫВАЕМ МЕТОД ЭКЗЕМПЛЯРА
    result = _release_manager.get_latest_release(channel)
    
    # ✅ ВСЕГДА КЭШИРУЕМ НОВЫЙ РЕЗУЛЬТАТ
    if result:
        UpdateCache.cache_release(channel, result)
        log(f"💾 Новый результат закэширован: {result['version']} из {result.get('source', 'неизвестен')}", "🔄 CACHE")
    
    return result


def invalidate_cache(channel: Optional[str] = None):
    """
    Очищает кэш обновлений
    
    Args:
        channel: Конкретный канал или None для очистки всего
    """
    from .update_cache import UpdateCache
    UpdateCache.invalidate(channel)
    log(f"🗑️ Кэш {'канала ' + channel if channel else 'всех каналов'} очищен", "🔄 CACHE")


def get_cache_info(channel: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает информацию о состоянии кэша
    
    Args:
        channel: "stable" или "dev"
        
    Returns:
        Dict с информацией о кэше или None
    """
    from .update_cache import UpdateCache, CACHE_DURATION
    
    age = UpdateCache.get_cache_age(channel)
    if age is None:
        return None
    
    cached = UpdateCache.get_cached_release(channel)
    
    return {
        'age_seconds': age,
        'age_minutes': age // 60,
        'age_hours': age / 3600,
        'is_valid': age < CACHE_DURATION,
        'version': cached['version'] if cached else None,
        'source': cached.get('source') if cached else None
    }


def get_release_manager() -> ReleaseManager:
    """Возвращает экземпляр менеджера релизов"""
    return _release_manager

def disable_vps_for_a_day(reason: str = "download error"):
    """Публичная обёртка для временной блокировки VPS"""
    _release_manager.disable_vps_for_a_day(reason)

def get_vps_block_info() -> Dict[str, Any]:
    """Удобная обёртка для получения информации о блокировке VPS"""
    return _release_manager.get_vps_block_info()