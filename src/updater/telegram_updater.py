"""
telegram_updater.py
────────────────────────────────────────────────────────────────
Проверка версии из Telegram каналов через Bot HTTP API.
Используется как дополнительный источник информации о версии.
"""

import os
import re
import time as _time
import requests
from typing import Optional, Dict, Any
from log.log import log

from .network_hints import maybe_log_disable_dpi_for_update
from .proxy_bypass import session_bypass_proxy


def _no_proxy_get(url: str, **kwargs) -> requests.Response:
    """GET-запрос без прокси — защита от утечки прокси-настроек build-окружения."""
    s = session_bypass_proxy()
    try:
        return s.get(url, **kwargs)
    finally:
        s.close()

# ────────────────────────────────────────────────────────────────
#  ТОКЕН TELEGRAM BOT API (только из generated runtime config)
# ────────────────────────────────────────────────────────────────
try:
    from config._build_secrets import TG_UPDATE_BOT_TOKEN as _BUILD_TOKEN
except ImportError:
    _BUILD_TOKEN = ""

_TOKEN_CACHE = ""

# Каналы для разных веток (username без @)
TELEGRAM_CHANNELS = {
    'stable': 'zapretnetdiscordyoutube',
    'dev': 'zapretguidev',
}

# Таймаут для Telegram запросов (секунды)
TELEGRAM_TIMEOUT = 10

# Глобальный флаг - отключить Telegram после flood wait
_telegram_disabled_until = 0

# Bot API URL
_API_URL_TEMPLATE = "https://api.telegram.org/bot{value}/{method}"


def get_inline_value() -> str:
    """Возвращает токен update-бота только из generated runtime config."""
    global _TOKEN_CACHE

    if _TOKEN_CACHE:
        return _TOKEN_CACHE

    if _BUILD_TOKEN:
        _TOKEN_CACHE = _BUILD_TOKEN
        return _TOKEN_CACHE

    return ""


def _call_bot_api(method: str, params: dict = None) -> Optional[dict]:
    """Вызывает Bot HTTP API"""
    key = get_inline_value()
    if not key:
        return None
    
    url = _API_URL_TEMPLATE.format(value=key, method=method)
    
    try:
        response = _no_proxy_get(url, params=params, timeout=TELEGRAM_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                return data.get('result')
        elif response.status_code == 429:
            # Rate limit
            retry_after = response.json().get('parameters', {}).get('retry_after', 60)
            global _telegram_disabled_until
            _telegram_disabled_until = _time.time() + retry_after
            log(f"⚠️ Telegram rate limit: {retry_after}с", "📱 TG")
        return None
    except requests.exceptions.ProxyError as e:
        log(f"❌ Bot API ошибка (proxy): {e}", "📱 TG")
        maybe_log_disable_dpi_for_update(e, scope="update_check", level="📱 TG")
        return None
    except Exception as e:
        log(f"❌ Bot API ошибка: {e}", "📱 TG")
        maybe_log_disable_dpi_for_update(e, scope="update_check", level="📱 TG")
        return None


def _parse_telegram_web(channel: str) -> Optional[Dict[str, Any]]:
    """
    Парсит публичную страницу канала через t.me
    Работает без авторизации.
    
    Приоритет: версия из имени файла (Zapret2Setup*.exe) > текст постов.
    """
    channel_name = TELEGRAM_CHANNELS.get(channel, TELEGRAM_CHANNELS['stable'])
    url = f"https://t.me/s/{channel_name}"
    
    try:
        response = _no_proxy_get(url, timeout=TELEGRAM_TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # ✅ ПРИОРИТЕТ 1: Ищем имя файла установщика и извлекаем версию из него
        file_name_pattern = r'(Zapret2Setup[^"<>\s]*\.exe)'
        file_names = re.findall(file_name_pattern, html)
        
        if file_names:
            # Берём последний (самый новый) файл
            file_name = file_names[-1]
            version = _extract_version_from_filename(file_name)
            
            if version:
                log(f"✅ Web: версия {version} из имени файла {file_name}", "📱 TG")
                return {
                    'version': version,
                    'file_name': file_name,
                    'source': f'Telegram @{channel_name} (web)',
                    'channel': channel_name,
                }
        
        # ✅ ПРИОРИТЕТ 2 (fallback): Ищем версию в тексте сообщений
        version_pattern = r'(\d+\.\d+\.\d+\.\d+)'
        version_matches = re.findall(version_pattern, html)
        
        if version_matches:
            version = version_matches[-1]
            file_name = file_names[-1] if file_names else f"Zapret2Setup_{version}.exe"
            
            log(f"⚠️ Web: версия {version} из текста (fallback)", "📱 TG")
            return {
                'version': version,
                'file_name': file_name,
                'source': f'Telegram @{channel_name} (web)',
                'channel': channel_name,
            }
        
        return None
        
    except Exception as e:
        log(f"❌ Ошибка парсинга t.me: {e}", "📱 TG")
        maybe_log_disable_dpi_for_update(e, scope="update_check", level="📱 TG")
        return None


def get_telegram_version_info(channel: str = 'stable') -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последней версии из Telegram канала
    
    Использует несколько методов:
    1. Bot API getChat (закрепленное сообщение)
    2. Парсинг публичной страницы t.me/s/channel
    
    Args:
        channel: 'stable' или 'dev'
        
    Returns:
        Dict с информацией о версии или None
    """
    global _telegram_disabled_until
    
    # Проверяем не отключен ли Telegram из-за flood wait
    if _time.time() < _telegram_disabled_until:
        remaining = int(_telegram_disabled_until - _time.time())
        log(f"⏭️ Telegram отключен (rate limit, осталось {remaining}с)", "📱 TG")
        return None
    
    channel_name = TELEGRAM_CHANNELS.get(channel, TELEGRAM_CHANNELS['stable'])
    
    # Метод 1: Bot API - getChat (получаем закрепленное сообщение)
    key = get_inline_value()
    if key:
        try:
            log(f"🔍 Telegram: проверка @{channel_name}...", "📱 TG")
            
            chat_info = _call_bot_api('getChat', {'chat_id': f'@{channel_name}'})
            
            if chat_info:
                pinned = chat_info.get('pinned_message')
                
                if pinned:
                    # Проверяем есть ли документ
                    doc = pinned.get('document')
                    caption = pinned.get('caption', '')
                    text = pinned.get('text', '')
                    
                    # Извлекаем версию
                    version = _extract_version(
                        doc.get('file_name', '') if doc else '',
                        caption or text
                    )
                    
                    if version:
                        result = {
                            'version': version,
                            'file_name': doc.get('file_name') if doc else f'Zapret2Setup_{version}.exe',
                            'file_size': doc.get('file_size') if doc else None,
                            'file_id': doc.get('file_id') if doc else None,
                            'source': f'Telegram @{channel_name}',
                            'channel': channel_name,
                        }
                        log(f"✅ Telegram: найдена версия {version} (закреп)", "📱 TG")
                        return result
                
                # Проверяем описание канала
                description = chat_info.get('description', '')
                if description:
                    version = _extract_version('', description)
                    if version:
                        log(f"✅ Telegram: найдена версия {version} (описание)", "📱 TG")
                        return {
                            'version': version,
                            'source': f'Telegram @{channel_name}',
                            'channel': channel_name,
                        }
                        
        except Exception as e:
            log(f"⚠️ Bot API ошибка: {e}", "📱 TG")
            maybe_log_disable_dpi_for_update(e, scope="update_check", level="📱 TG")
    
    # Метод 2: Парсинг публичной страницы (fallback)
    try:
        log(f"🔍 Telegram: парсинг t.me/s/{channel_name}...", "📱 TG")
        result = _parse_telegram_web(channel)
        if result:
            log(f"✅ Telegram: найдена версия {result['version']} (web)", "📱 TG")
            return result
    except Exception as e:
        log(f"⚠️ Web парсинг ошибка: {e}", "📱 TG")
    
    log(f"⚠️ Telegram: версия не найдена в @{channel_name}", "📱 TG")
    return None


def _extract_version_from_filename(file_name: str) -> Optional[str]:
    """
    Извлекает версию из имени файла установщика.
    
    Поддерживает оба формата:
    - Zapret2Setup_DEV_20_3_17_14.exe   → 20.3.17.14  (подчёркивания)
    - Zapret2Setup_DEV_20.3.17.14.exe   → 20.3.17.14  (точки)
    - Zapret2Setup_20_3_17_14.exe       → 20.3.17.14  (без DEV)
    """
    if not file_name:
        return None
    
    # Паттерн 1: подчёркивания в имени файла
    # Zapret2Setup[_DEV]_XX_X_XX_XX.exe
    # Берём всё после последнего "Setup" или "TEST", до ".exe"
    m = re.search(
        r'Zapret2Setup(?:_DEV)?_(\d+(?:_\d+)+)\.exe',
        file_name,
        re.IGNORECASE,
    )
    if m:
        version = m.group(1).replace('_', '.')
        # Проверяем что это похоже на версию (минимум 3 части)
        parts = version.split('.')
        if len(parts) >= 3:
            return version
    
    # Паттерн 2: точки в имени файла (старый формат)
    # Zapret2Setup_20.3.17.14.exe
    m = re.search(
        r'Zapret2Setup(?:_DEV)?[_.]?(\d+\.\d+\.\d+(?:\.\d+)?)\.exe',
        file_name,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    
    # Паттерн 3: любой 3-4 part version в имени файла (generic fallback)
    dot_patterns = [
        r'v?(\d+\.\d+\.\d+\.\d+)',  # 20.3.17.14
        r'v?(\d+\.\d+\.\d+)',        # 20.3.17
    ]
    for pattern in dot_patterns:
        match = re.search(pattern, file_name)
        if match:
            return match.group(1)
    
    return None


def _extract_version(file_name: str, text: str) -> Optional[str]:
    """
    Извлекает версию из имени файла или текста.
    Приоритет: имя файла > текст сообщения.
    """
    # ✅ ПРИОРИТЕТ 1: Извлекаем из имени файла (самый надёжный источник)
    version = _extract_version_from_filename(file_name)
    if version:
        return version
    
    # ✅ ПРИОРИТЕТ 2: Ищем в тексте сообщения (fallback)
    text_patterns = [
        r'v?(\d+\.\d+\.\d+\.\d+)',  # 19.6.0.12
        r'v?(\d+\.\d+\.\d+)',        # 19.6.0
    ]
    for pattern in text_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return None


def is_telegram_available() -> bool:
    """Проверяет доступность Telegram Bot API"""
    return bool(get_inline_value())
