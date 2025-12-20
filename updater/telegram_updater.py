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
from typing import Optional, Dict, Any, Callable
from log import log

# Обфусцированные встроенные данные
_INLINE_PARTS = [
    ("eHp7f397eXZ+fnU=", 0x4F, 0),
    ("amptXw==", 0x2B, 11),
    ("WEooTm00dltXSihhWFFeKQ==", 0x19, 15),
    ("k4C5iIutlZeIu7qS+vqG", 0xC3, 31),
]

# Контрольная сумма первых символов
_INLINE_CHECKSUM = 517


def _rebuild_inline_value() -> str:
    """Собирает встроенную строку из частей"""
    import base64
    
    try:
        result = [''] * 46
        
        for encoded, xor_key, offset in _INLINE_PARTS:
            decoded = base64.b64decode(encoded)
            for i, byte in enumerate(decoded):
                if offset + i < len(result):
                    result[offset + i] = chr(byte ^ xor_key)
        
        value = ''.join(result).rstrip('\x00')
        
        checksum = sum(ord(c) for c in value[:10])
        if checksum != _INLINE_CHECKSUM:
            return ""
        
        return value
    except:
        return ""

_INLINE_CACHE = ""

# Каналы для разных веток (username без @)
TELEGRAM_CHANNELS = {
    'stable': 'zapretnetdiscordyoutube',
    'test': 'zapretguidev',
}

# Таймаут для Telegram запросов (секунды)
TELEGRAM_TIMEOUT = 10

# Глобальный флаг - отключить Telegram после flood wait
_telegram_disabled_until = 0

# Bot API URL
_API_URL_TEMPLATE = "https://api.telegram.org/bot{value}/{method}"


def get_inline_value() -> str:
    """Возвращает встроенное значение (из obf/env/файла)"""
    global _INLINE_CACHE
    
    if _INLINE_CACHE:
        return _INLINE_CACHE
    
    embedded = _rebuild_inline_value()
    if embedded and len(embedded) > 20:
        _INLINE_CACHE = embedded
        return _INLINE_CACHE
    
    env_value = os.getenv('ZAPRET_TG_BOT_TOKEN')
    if env_value:
        _INLINE_CACHE = env_value
        return _INLINE_CACHE
    
    try:
        from config import LOGS_FOLDER
        token_file = os.path.join(LOGS_FOLDER, '.tg_bot_token')
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                _INLINE_CACHE = f.read().strip()
                return _INLINE_CACHE
    except:
        pass
    
    return ""


def _call_bot_api(method: str, params: dict = None) -> Optional[dict]:
    """Вызывает Bot HTTP API"""
    key = get_inline_value()
    if not key:
        return None
    
    url = _API_URL_TEMPLATE.format(value=key, method=method)
    
    try:
        response = requests.get(url, params=params, timeout=TELEGRAM_TIMEOUT)
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
    except Exception as e:
        log(f"❌ Bot API ошибка: {e}", "📱 TG")
        return None


def _parse_telegram_web(channel: str) -> Optional[Dict[str, Any]]:
    """
    Парсит публичную страницу канала через t.me
    Работает без авторизации
    """
    channel_name = TELEGRAM_CHANNELS.get(channel, TELEGRAM_CHANNELS['stable'])
    url = f"https://t.me/s/{channel_name}"
    
    try:
        response = requests.get(url, timeout=TELEGRAM_TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Ищем ссылки на .exe файлы
        # Формат: href="https://cdn...telegram-cdn.../documents/...exe..."
        exe_pattern = r'href="(https://[^"]+\.exe[^"]*)"'
        exe_matches = re.findall(exe_pattern, html)
        
        # Ищем версию в тексте сообщений
        version_pattern = r'(\d+\.\d+\.\d+\.\d+)'
        version_matches = re.findall(version_pattern, html)
        
        if version_matches:
            # Берём последнюю (самую новую) версию
            version = version_matches[-1]
            
            # Ищем имя файла
            file_name_pattern = r'(Zapret2Setup[^"<>\s]*\.exe)'
            file_names = re.findall(file_name_pattern, html)
            file_name = file_names[-1] if file_names else f"Zapret2Setup_{version}.exe"
            
            return {
                'version': version,
                'file_name': file_name,
                'source': f'Telegram @{channel_name} (web)',
                'channel': channel_name,
            }
        
        return None
        
    except Exception as e:
        log(f"❌ Ошибка парсинга t.me: {e}", "📱 TG")
        return None


def get_telegram_version_info(channel: str = 'stable') -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последней версии из Telegram канала
    
    Использует несколько методов:
    1. Bot API getChat (закрепленное сообщение)
    2. Парсинг публичной страницы t.me/s/channel
    
    Args:
        channel: 'stable' или 'test'
        
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


def _extract_version(file_name: str, text: str) -> Optional[str]:
    """Извлекает версию из имени файла или текста"""
    patterns = [
        r'v?(\d+\.\d+\.\d+\.\d+)',  # 19.6.0.12
        r'v?(\d+\.\d+\.\d+)',        # 19.6.0
    ]
    
    # Сначала ищем в имени файла
    for pattern in patterns:
        match = re.search(pattern, file_name)
        if match:
            return match.group(1)
    
    # Затем в тексте сообщения
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return None


def is_telegram_available() -> bool:
    """Проверяет доступность Telegram Bot API"""
    return bool(get_inline_value())


def download_from_telegram(
    channel: str = 'stable',
    save_path: str = None,
    progress_callback: Callable[[int, int], None] = None,
    file_id: str = None
) -> Optional[str]:
    """
    Скачивание через Bot API ограничено 20MB.
    Для больших файлов используйте VPS серверы.
    
    Returns:
        None - скачивание через Telegram отключено для больших файлов
    """
    log("⚠️ Telegram: скачивание больших файлов недоступно (лимит 20MB)", "📱 TG")
    log("ℹ️ Используйте VPS серверы для скачивания", "📱 TG")
    return None
