"""
updater/update_cache.py
────────────────────────────────────────────────────────────────
Кэширование результатов проверки обновлений для снижения нагрузки на сервер
"""
import json
import os
import time
from typing import Optional, Dict, Any
from config.config import LOGS_FOLDER

from log.log import log

from .channel_utils import normalize_update_channel

CACHE_FILE = os.path.join(LOGS_FOLDER, '.update_cache.json')
CACHE_DURATION = 3600  # 1 час (3600 секунд)

# ═══════════════════════════════════════════════════════════════════════════════
# ✅ IN-MEMORY кэш для all_versions.json (короткоживущий, для сессии)
# ═══════════════════════════════════════════════════════════════════════════════
_all_versions_cache: Optional[Dict[str, Any]] = None
_all_versions_cache_time: float = 0
_all_versions_cache_source: str = ""
ALL_VERSIONS_CACHE_TTL = 30  # 30 секунд - для переиспользования в одной сессии


def get_cached_all_versions() -> Optional[Dict[str, Any]]:
    """
    Возвращает закэшированный all_versions.json если он свежий.
    Используется для переиспользования между воркерами.
    """
    global _all_versions_cache, _all_versions_cache_time
    
    if _all_versions_cache is None:
        return None
    
    age = time.time() - _all_versions_cache_time
    if age > ALL_VERSIONS_CACHE_TTL:
        log(f"⏰ In-memory кэш all_versions устарел ({age:.0f}с)", "🔄 CACHE")
        return None
    
    log(f"✅ Используем in-memory кэш all_versions ({ALL_VERSIONS_CACHE_TTL - age:.0f}с до истечения)", "🔄 CACHE")
    return _all_versions_cache


def set_cached_all_versions(data: Dict[str, Any], source: str):
    """Сохраняет all_versions.json в in-memory кэш"""
    global _all_versions_cache, _all_versions_cache_time, _all_versions_cache_source
    
    _all_versions_cache = data
    _all_versions_cache_time = time.time()
    _all_versions_cache_source = source
    
    log(f"💾 all_versions закэширован в память из {source} (TTL: {ALL_VERSIONS_CACHE_TTL}с)", "🔄 CACHE")


def get_all_versions_source() -> str:
    """Возвращает источник закэшированного all_versions"""
    return _all_versions_cache_source

class UpdateCache:
    """Кэш для результатов проверки обновлений"""
    
    @staticmethod
    def get_cached_release(channel: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает закэшированный релиз если он актуален
        
        Args:
            channel: "stable" или "test"
            
        Returns:
            Dict с информацией о релизе или None
        """
        try:
            channel = normalize_update_channel(channel)
            if not os.path.exists(CACHE_FILE):
                return None
            
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            
            if channel not in cache:
                return None
            
            entry = cache[channel]
            
            # Проверяем срок годности
            cached_time = entry.get('cached_at', 0)
            age = time.time() - cached_time
            
            if age > CACHE_DURATION:
                log(f"⏰ Кэш обновлений устарел ({age/60:.0f} мин)", "🔄 CACHE")
                return None
            
            log(f"✅ Используем кэш обновлений ({(CACHE_DURATION-age)/60:.0f} мин до истечения)", "🔄 CACHE")
            return entry.get('release_info')
            
        except Exception as e:
            log(f"⚠️ Ошибка чтения кэша: {e}", "🔄 CACHE")
            return None
    
    @staticmethod
    def cache_release(channel: str, release_info: Dict[str, Any]):
        """
        Сохраняет информацию о релизе в кэш
        
        Args:
            channel: "stable" или "test"
            release_info: Информация о релизе
        """
        try:
            channel = normalize_update_channel(channel)
            # Загружаем существующий кэш
            cache = {}
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                except:
                    pass
            
            # Добавляем новую запись
            cache[channel] = {
                'release_info': release_info,
                'cached_at': time.time()
            }
            
            # Сохраняем
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
            
            log(f"💾 Кэш обновлений сохранен (TTL: {CACHE_DURATION/60:.0f} мин)", "🔄 CACHE")
            
        except Exception as e:
            log(f"⚠️ Ошибка сохранения кэша: {e}", "🔄 CACHE")
    
    @staticmethod
    def invalidate(channel: Optional[str] = None):
        """
        Очищает кэш обновлений
        
        Args:
            channel: Конкретный канал или None для очистки всего
        """
        try:
            if channel is None:
                # Удаляем весь файл кэша
                if os.path.exists(CACHE_FILE):
                    os.remove(CACHE_FILE)
                    log("🗑️ Весь кэш обновлений очищен", "🔄 CACHE")
            else:
                channel = normalize_update_channel(channel)
                # Удаляем конкретный канал
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                    
                    if channel in cache:
                        del cache[channel]
                        
                        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                            json.dump(cache, f, indent=2)
                        
                        log(f"🗑️ Кэш для канала {channel} очищен", "🔄 CACHE")
                        
        except Exception as e:
            log(f"⚠️ Ошибка очистки кэша: {e}", "🔄 CACHE")
    
    @staticmethod
    def get_cache_age(channel: str) -> Optional[int]:
        """
        Возвращает возраст кэша в секундах
        
        Args:
            channel: "stable" или "test"
            
        Returns:
            Возраст в секундах или None если кэша нет
        """
        try:
            channel = normalize_update_channel(channel)
            if not os.path.exists(CACHE_FILE):
                return None
            
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            
            if channel not in cache:
                return None
            
            cached_time = cache[channel].get('cached_at', 0)
            return int(time.time() - cached_time)
            
        except:
            return None

    @staticmethod
    def get_cache_info(channel: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает подробную информацию о кэше
        
        Args:
            channel: "stable" или "test"
            
        Returns:
            Dict с информацией о кэше или None
        """
        try:
            channel = normalize_update_channel(channel)
            if not os.path.exists(CACHE_FILE):
                return None
            
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            
            if channel not in cache:
                return None
            
            entry = cache[channel]
            cached_time = entry.get('cached_at', 0)
            age_seconds = time.time() - cached_time
            age_minutes = int(age_seconds / 60)
            age_hours = age_seconds / 3600
            is_valid = age_seconds < CACHE_DURATION
            
            release_info = entry.get('release_info', {})
            
            return {
                'version': release_info.get('version'),
                'source': release_info.get('source'),
                'cached_at': cached_time,
                'age_seconds': int(age_seconds),
                'age_minutes': age_minutes,
                'age_hours': age_hours,
                'is_valid': is_valid,
                'ttl_remaining': int(CACHE_DURATION - age_seconds) if is_valid else 0
            }
            
        except Exception as e:
            log(f"Ошибка получения информации о кэше: {e}", "🔄 CACHE")
            return None
