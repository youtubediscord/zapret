"""
github_release.py
────────────────────────────────────────────────────────────────
Получение информации о последнем релизе с GitHub для выбранного канала.
С поддержкой кэширования и умной обработкой rate limits.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from packaging import version
from datetime import datetime
import base64
import time
import json
import os
import requests
from log import log
from config import LOGS_FOLDER

# ────────────────────────────────────────────────────────────────
#  ОБФУСКАЦИЯ GITHUB ТОКЕНА
# ────────────────────────────────────────────────────────────────
_PARTS = [
    ("PTIqBQ8VGBUuPQ==", 0x5A, 0),
    ("aW8NWE8EbmlTWw==", 0x3D, 10),
    ("HXpbYXVDZVl9eQ==", 0x2C, 20),
    ("LAkkB08IDkwuKA==", 0x7E, 30),
]
_CHECKSUM = 942
_CACHE = ""


def _rebuild_token() -> str:
    """Собирает токен из обфусцированных частей"""
    global _CACHE
    
    if _CACHE:
        return _CACHE
    
    try:
        result = [''] * 40
        
        for encoded, xor_key, offset in _PARTS:
            decoded = base64.b64decode(encoded)
            for i, byte in enumerate(decoded):
                if offset + i < len(result):
                    result[offset + i] = chr(byte ^ xor_key)
        
        value = ''.join(result).rstrip('\x00')
        
        checksum = sum(ord(c) for c in value[:10])
        if checksum != _CHECKSUM:
            return ""
        
        _CACHE = value
        return _CACHE
    except:
        return ""


def _get_token() -> str:
    """Получает токен (из обфускации/env)"""
    token = _rebuild_token()
    if token and len(token) > 20:
        return token
    
    env_token = os.getenv('GITHUB_TOKEN')
    if env_token:
        return env_token
    
    return ""


GITHUB_UPDATE_1 = _get_token()

GITHUB_API_URL = "https://api.github.com/repos/youtubediscord/zapret/releases"
TIMEOUT = 10  # сек.

# Кэш для GitHub запросов
_github_cache: Dict[str, Tuple[Any, float]] = {}
CACHE_TTL = 300  # 5 минут

# Файл для сохранения кэша между запусками
CACHE_FILE = os.path.join(LOGS_FOLDER, '.github_cache.json')
RATE_LIMIT_FILE = os.path.join(LOGS_FOLDER, '.github_rate_limit')

def _load_persistent_cache():
    """Загружает кэш из файла"""
    global _github_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Проверяем TTL для каждой записи
                current_time = time.time()
                _github_cache = {
                    url: (content, timestamp) 
                    for url, (content, timestamp) in data.items()
                    if current_time - timestamp < CACHE_TTL
                }
                if _github_cache:
                    log(f"📦 Загружено {len(_github_cache)} записей из кэша", "🔄 CACHE")
    except Exception as e:
        log(f"Ошибка загрузки кэша: {e}", "⚠️ CACHE")
        _github_cache = {}

def _save_persistent_cache():
    """Сохраняет кэш в файл"""
    try:
        # Конвертируем Response объекты в JSON-сериализуемые данные
        cache_data = {}
        for url, (content, timestamp) in _github_cache.items():
            if isinstance(content, requests.Response):
                cache_data[url] = ({
                    'status_code': content.status_code,
                    'json': content.json() if content.status_code == 200 else None,
                    'headers': dict(content.headers)
                }, timestamp)
            else:
                cache_data[url] = (content, timestamp)
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
    except Exception as e:
        log(f"Ошибка сохранения кэша: {e}", "⚠️ CACHE")

def _save_rate_limit_info(reset_time: int):
    """Сохраняет информацию о rate limit"""
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            f.write(str(reset_time))
    except Exception as e:
        log(f"Ошибка сохранения rate limit: {e}", "⚠️ CACHE")

def is_rate_limited() -> Tuple[bool, Optional[datetime]]:
    """
    Проверяет, находимся ли мы в состоянии rate limit
    Returns: (is_limited, reset_time)
    """
    try:
        if os.path.exists(RATE_LIMIT_FILE):
            with open(RATE_LIMIT_FILE, 'r') as f:
                reset_time = float(f.read())
                if time.time() < reset_time:
                    reset_dt = datetime.fromtimestamp(reset_time)
                    return True, reset_dt
    except:
        pass
    return False, None

def check_rate_limit() -> Dict[str, Any]:
    """Проверяет текущий статус rate limit GitHub API"""
    try:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Zapret-Updater/3.1'
        }
        
        # Добавляем токен если есть
        token = GITHUB_UPDATE_1
        if token:
            headers['Authorization'] = f'token {token}'
        
        resp = requests.get(
            "https://api.github.com/rate_limit", 
            headers=headers, 
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            core_limit = data['rate']
            return {
                'limit': core_limit['limit'],
                'remaining': core_limit['remaining'],
                'reset': core_limit['reset'],
                'reset_dt': datetime.fromtimestamp(core_limit['reset'])
            }
    except Exception as e:
        log(f"Ошибка проверки rate limit: {e}", "⚠️ RATE_LIMIT")
    
    return {'limit': 60, 'remaining': 0, 'reset': 0}

def _get_cached_or_fetch(url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Получает данные из кэша или делает запрос"""
    # Проверяем кэш
    if url in _github_cache:
        data, timestamp = _github_cache[url]
        if time.time() - timestamp < CACHE_TTL:
            log(f"✅ Используем кэшированный ответ (осталось {int(CACHE_TTL - (time.time() - timestamp))} сек)", "🔄 CACHE")
            return data
    
    # Проверяем rate limit перед запросом
    is_limited, reset_dt = is_rate_limited()
    if is_limited:
        log(f"⏳ Rate limit активен до {reset_dt}. Используем кэш.", "⚠️ RATE_LIMIT")
        # Пытаемся вернуть устаревший кэш если есть
        if url in _github_cache:
            data, _ = _github_cache[url]
            log("📦 Возвращаем устаревший кэш из-за rate limit", "🔄 CACHE")
            return data
        return None
    
    try:
        # Делаем запрос
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Zapret-Updater/3.1'
        }
        
        # Добавляем GitHub token если есть (увеличивает лимит с 60 до 5000)
        token = GITHUB_UPDATE_1
        if token:
            headers['Authorization'] = f'token {token}'
            log("🔑 Используем GitHub token для увеличения лимита", "🔄 CACHE")
        
        response = requests.get(url, headers=headers, timeout=timeout)
        
        # Проверяем rate limit в ответе
        if response.status_code == 403:
            remaining = response.headers.get('X-RateLimit-Remaining', '0')
            reset_time = response.headers.get('X-RateLimit-Reset', '0')
            
            if remaining == '0':
                reset_timestamp = int(reset_time)
                _save_rate_limit_info(reset_timestamp)
                reset_dt = datetime.fromtimestamp(reset_timestamp)
                log(f"🚫 GitHub rate limit превышен. Сброс в {reset_dt}", "⚠️ RATE_LIMIT")
                
                # Возвращаем кэш если есть
                if url in _github_cache:
                    data, _ = _github_cache[url]
                    log("📦 Возвращаем старый кэш из-за rate limit", "🔄 CACHE")
                    return data
                return None
        
        response.raise_for_status()
        
        # Парсим JSON сразу для кэширования
        json_data = response.json()
        
        # Сохраняем в кэш
        _github_cache[url] = (json_data, time.time())
        _save_persistent_cache()
        
        # Логируем оставшиеся запросы
        remaining = response.headers.get('X-RateLimit-Remaining')
        if remaining:
            log(f"📊 Осталось запросов к GitHub: {remaining}", "🔄 CACHE")
            if int(remaining) < 10:
                log(f"⚠️ Мало запросов осталось! Рекомендуется использовать GITHUB_TOKEN", "⚠️ RATE_LIMIT")
        
        return json_data
        
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 403:
            log(f"🚫 HTTP 403: {e}", "❌ ERROR")
        else:
            log(f"❌ HTTP ошибка: {e}", "❌ ERROR")
    except Exception as e:
        log(f"❌ Ошибка запроса к GitHub: {e}", "❌ ERROR")
    
    return None

def normalize_version(ver_str: str) -> str:
    if ver_str.startswith('v') or ver_str.startswith('V'):
        ver_str = ver_str[1:]
    ver_str = ver_str.strip()
    parts = ver_str.split('.')
    if len(parts) < 2:
        raise ValueError(f"Invalid version format: {ver_str}")
    try:
        for part in parts:
            int(part)
    except ValueError:
        raise ValueError(f"Invalid version format: {ver_str}")
    return ver_str

def compare_versions(v1: str, v2: str) -> int:
    """
    Сравнивает две версии.
    Возвращает: -1 если v1 < v2, 0 если равны, 1 если v1 > v2
    """
    try:
        ver1 = version.parse(v1)
        ver2 = version.parse(v2)
        if ver1 < ver2:
            return -1
        elif ver1 > ver2:
            return 1
        else:
            return 0
    except Exception:
        # Fallback на строковое сравнение
        return -1 if v1 < v2 else (1 if v1 > v2 else 0)

# Кэш для полного списка релизов (отдельно от кэша запросов)
_all_releases_cache: Tuple[List[Dict[str, Any]], float] = ([], 0)
ALL_RELEASES_CACHE_TTL = 600  # 10 минут - не дёргаем GitHub слишком часто


def get_all_releases_with_exe() -> List[Dict[str, Any]]:
    """
    Получает все релизы с .exe файлами с умной обработкой rate limits.
    
    ✅ ОПТИМИЗИРОВАНО: 
    - Кэширует полный результат на 10 минут
    - НЕ делает отдельный запрос check_rate_limit()
    - Максимум 2 страницы для dev канала (200 релизов = достаточно)
    """
    global _all_releases_cache
    
    # ═══════════════════════════════════════════════════════════
    # ✅ ПРОВЕРЯЕМ КЭШ ПОЛНОГО СПИСКА РЕЛИЗОВ
    # ═══════════════════════════════════════════════════════════
    cached_releases, cache_time = _all_releases_cache
    if cached_releases and (time.time() - cache_time) < ALL_RELEASES_CACHE_TTL:
        age_sec = int(time.time() - cache_time)
        log(f"✅ Используем кэш релизов ({len(cached_releases)} шт., возраст {age_sec}с)", "🔄 CACHE")
        return cached_releases
    
    # Загружаем кэш запросов при первом запуске
    if not _github_cache:
        _load_persistent_cache()
    
    # ═══════════════════════════════════════════════════════════
    # ✅ НЕ ДЕЛАЕМ ОТДЕЛЬНЫЙ check_rate_limit() - экономим запрос!
    # Проверяем rate limit из кэшированного файла
    # ═══════════════════════════════════════════════════════════
    is_limited, reset_dt = is_rate_limited()
    if is_limited:
        log(f"⏳ Rate limit до {reset_dt}, используем кэш", "⚠️ RATE_LIMIT")
        if cached_releases:
            return cached_releases
        return _get_cached_releases()
    
    releases_with_exe = []
    
    page = 1
    # ✅ ОГРАНИЧЕНО: максимум 2 страницы (200 релизов - более чем достаточно)
    max_pages = 2
    
    while page <= max_pages:
        url = f"{GITHUB_API_URL}?per_page=100&page={page}"
        
        try:
            releases_page = _get_cached_or_fetch(url, TIMEOUT)
            
            if not releases_page:
                log(f"⚠️ Не удалось получить страницу {page}", "🔁 UPDATE")
                break
            
            if len(releases_page) == 0:  # Пустая страница = конец
                break
                
            for release in releases_page:
                # Ищем .exe файл в ассетах
                exe_asset = next((a for a in release.get("assets", []) if a["name"].endswith(".exe")), None)
                if not exe_asset:
                    continue
                    
                try:
                    version_str = normalize_version(release["tag_name"])
                    releases_with_exe.append({
                        "version": version_str,
                        "tag_name": release["tag_name"],
                        "update_url": exe_asset["browser_download_url"],
                        "release_notes": release.get("body", ""),
                        "prerelease": release.get("prerelease", False),
                        "name": release.get("name", ""),
                        "published_at": release.get("published_at", ""),
                        "created_at": release.get("created_at", "")
                    })
                except ValueError as e:
                    log(f"❌ Неверный формат версии {release['tag_name']}: {e}", "🔁 UPDATE")
                    continue
            
            # Если получили меньше 100, значит страниц больше нет
            if len(releases_page) < 100:
                break
                
            page += 1
            
        except Exception as e:
            log(f"Ошибка получения страницы {page}: {e}", "🔁 UPDATE")
            break
    
    # ✅ КЭШИРУЕМ ПОЛНЫЙ РЕЗУЛЬТАТ
    if releases_with_exe:
        _all_releases_cache = (releases_with_exe, time.time())
        log(f"💾 Закэшировано {len(releases_with_exe)} релизов на {ALL_RELEASES_CACHE_TTL}с", "🔄 CACHE")
    
    return releases_with_exe

def _get_cached_releases() -> List[Dict[str, Any]]:
    """Возвращает релизы из кэша"""
    releases = []
    for url, (data, _) in _github_cache.items():
        if GITHUB_API_URL in url and isinstance(data, list):
            for release in data:
                exe_asset = next((a for a in release.get("assets", []) if a["name"].endswith(".exe")), None)
                if exe_asset:
                    try:
                        version_str = normalize_version(release["tag_name"])
                        releases.append({
                            "version": version_str,
                            "tag_name": release["tag_name"],
                            "update_url": exe_asset["browser_download_url"],
                            "release_notes": release.get("body", ""),
                            "prerelease": release.get("prerelease", False),
                            "name": release.get("name", ""),
                            "published_at": release.get("published_at", ""),
                            "created_at": release.get("created_at", "")
                        })
                    except:
                        pass
    return releases

def get_latest_release(channel: str) -> Optional[dict]:
    """
    Получает информацию о последнем релизе с GitHub.
    Для stable канала использует /releases/latest.
    Для dev канала ищет самую новую версию среди ALL релизов с .exe файлами.
    """
    # Загружаем кэш при первом запуске
    if not _github_cache:
        _load_persistent_cache()
    
    try:
        if channel == "stable":
            # Для stable используем /releases/latest
            url = "https://api.github.com/repos/youtubediscord/zapret/releases/latest"
            release = _get_cached_or_fetch(url, TIMEOUT)
            
            if not release:
                log("❌ Не удалось получить последний стабильный релиз", "🔁 UPDATE")
                return None
            
            log(f"📋 Получен последний стабильный релиз: {release['tag_name']}", "🔁 UPDATE")
            
            exe_asset = next((a for a in release.get("assets", []) if a["name"].endswith(".exe")), None)
            if not exe_asset:
                log("❌ В стабильном релизе нет .exe файла", "🔁 UPDATE")
                return None
                
            version_str = normalize_version(release["tag_name"])
            return {
                "version": version_str,
                "tag_name": release["tag_name"],
                "update_url": exe_asset["browser_download_url"],
                "release_notes": release.get("body", ""),
                "prerelease": False,
                "name": release.get("name", ""),
                "published_at": release.get("published_at", "")
            }
        else:
            # Для dev канала получаем ВСЕ релизы и ищем самый новый
            log("🔍 Получение всех dev релизов для поиска самого нового...", "🔁 UPDATE")
            
            all_releases = get_all_releases_with_exe()
            if not all_releases:
                log("❌ Не найдено релизов с .exe файлом", "🔁 UPDATE")
                return None
            
            log(f"📦 Найдено {len(all_releases)} релизов с .exe файлами", "🔁 UPDATE")
            
            # Сортируем по версии (от новой к старой)
            def version_key(rel):
                try:
                    return version.parse(rel["version"])
                except:
                    return version.parse("0.0.0")
            
            all_releases.sort(key=version_key, reverse=True)
            
            # Логируем первые 5 релизов для отладки
            log("🔝 Топ релизов по версии:", "🔁 UPDATE")
            for i, rel in enumerate(all_releases[:5]):
                prerelease_mark = " (prerelease)" if rel.get("prerelease") else ""
                log(f"   {i+1}. v{rel['version']}{prerelease_mark} - {rel.get('created_at', 'н/д')}", "🔁 UPDATE")
            
            # Возвращаем самый новый
            latest = all_releases[0]
            log(f"✅ Выбран самый новый dev релиз: {latest['version']} (prerelease: {latest.get('prerelease', False)})", "🔁 UPDATE")
            
            return latest
            
    except Exception as e:
        log(f"Не удалось получить релизы с GitHub: {e}", "🔁❌ ERROR")
        return None