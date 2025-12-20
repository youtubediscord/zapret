"""
Отдельный бот для отправки полных логов пользователями.
Используется только при ручной отправке через меню.
Выбор бота зависит от канала сборки (stable/test).
"""

from __future__ import annotations
from pathlib import Path
import requests
import time
import base64
from typing import Optional

# Группа для логов
LOG_CHAT_ID = -1003005847271

# Топик по умолчанию зависит от канала: test → 10854, stable → 1
def _get_default_topic() -> int:
    from config.build_info import CHANNEL
    return 10854 if CHANNEL == "test" else 1

# прод-бот (stable)
_PROD_ENC = "c3h+fnp8fn58enEKCgMyHnMRHAZ4fSxmOx4cHCIuMSYxIT8jfQoEfDgAKAAgDg=="
_PROD_XOR = 0x4B
_PROD_SUM = 527

# dev-бот (test)
_DEV_ENC = "ZGhoZW5tZWVobGYdHRs1ZCopGxgvN2sSHi0EbWwmGDpxamopPnEtbRhqEWoQMw=="
_DEV_XOR = 0x5C
_DEV_SUM = 530


def _decode_token(encoded: str, xor_key: int, checksum: int) -> str:
    """Декодирует токен бота"""
    try:
        decoded = base64.b64decode(encoded)
        value = ''.join(chr(b ^ xor_key) for b in decoded)

        # Проверка контрольной суммы первых 10 символов
        calc_sum = sum(ord(c) for c in value[:10])
        if calc_sum != checksum:
            return ""

        return value
    except:
        return ""


# Кэшированный токен
_token_cache = None


def _get_bot_token() -> str:
    """Возвращает токен бота в зависимости от канала сборки"""
    global _token_cache

    if _token_cache is None:
        from config.build_info import CHANNEL

        if CHANNEL == "stable":
            _token_cache = _decode_token(_PROD_ENC, _PROD_XOR, _PROD_SUM)
        else:
            _token_cache = _decode_token(_DEV_ENC, _DEV_XOR, _DEV_SUM)

    return _token_cache


# Настройки
TIMEOUT = 30
MAX_RETRIES = 3
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB максимальный размер файла


def _get_log_api() -> str:
    """API endpoint для бота"""
    return f"https://api.telegram.org/bot{_get_bot_token()}"


def _safe_api_call(method: str, *, data=None, files=None) -> tuple[Optional[dict], Optional[str]]:
    """
    Безопасный вызов Telegram API с обработкой flood-wait (тихий режим).

    Returns:
        (result_dict, error_message) - result_dict если успех, иначе (None, error_message)
    """
    from .tg_sender import _set_flood_cooldown

    for attempt in range(MAX_RETRIES + 1):
        try:
            url = f"{_get_log_api()}/{method}"
            response = requests.post(url, data=data, files=files, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json(), None

        except requests.HTTPError as e:
            if e.response and e.response.status_code == 429:
                try:
                    result = e.response.json()
                    retry_after = result.get("parameters", {}).get("retry_after", 60)
                except Exception:
                    retry_after = 60

                wait_time = int(retry_after) + 1
                if attempt < MAX_RETRIES:
                    time.sleep(wait_time)
                    continue
                else:
                    _set_flood_cooldown()
                    return None, f"Слишком много запросов. Подождите {retry_after} секунд"

            # Другие HTTP ошибки
            status_code = e.response.status_code if e.response else "неизвестен"
            _set_flood_cooldown()
            return None, f"Ошибка HTTP {status_code}"

        except requests.ConnectionError as e:
            error_str = str(e).lower()
            # Проверяем признаки блокировки Telegram
            if "api.telegram.org" in error_str or "connection refused" in error_str:
                _set_flood_cooldown()
                return None, "Telegram заблокирован или недоступен. Включите VPN или DPI bypass"
            _set_flood_cooldown()
            return None, "Нет подключения к интернету"

        except requests.Timeout:
            _set_flood_cooldown()
            return None, "Превышено время ожидания. Возможно Telegram заблокирован"

        except Exception as e:
            error_str = str(e).lower()
            # Проверяем признаки блокировки
            if "connection" in error_str and ("refused" in error_str or "reset" in error_str or "timeout" in error_str):
                _set_flood_cooldown()
                return None, "Telegram заблокирован или недоступен. Включите VPN или DPI bypass"
            _set_flood_cooldown()
            return None, f"Ошибка сети: {str(e)[:100]}"

    _set_flood_cooldown()
    return None, "Превышено количество попыток"


def send_log_file(file_path: str | Path, caption: str = "", topic_id: int = None) -> tuple[bool, Optional[str]]:
    """
    Отправляет файл лога через бота в группу с топиком (тихий режим).

    Args:
        file_path: путь к файлу лога
        caption: подпись к файлу
        topic_id: ID топика (если None - выбирается по каналу: test→10854, stable→1)

    Returns:
        (success, error_message)
    """
    from .tg_sender import is_in_flood_cooldown, _set_flood_cooldown

    if topic_id is None:
        topic_id = _get_default_topic()

    if is_in_flood_cooldown():
        return False, "Слишком частые запросы. Подождите несколько минут"

    try:
        token = _get_bot_token()
        if not token:
            return False, "Ошибка конфигурации бота"

        path = Path(file_path)
        if not path.exists():
            return False, f"Файл лога не найден: {path.name}"

        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            return False, f"Файл слишком большой ({size_mb:.1f} МБ). Максимум: 50 МБ"

        if file_size == 0:
            return False, "Файл лога пуст"

        with path.open("rb") as file:
            files = {"document": file}
            data = {
                "chat_id": LOG_CHAT_ID,
                "message_thread_id": topic_id,
                "caption": caption[:1024] if caption else path.name
            }
            result, error_msg = _safe_api_call("sendDocument", data=data, files=files)

        if result and result.get("ok"):
            return True, None

        # API вернул ошибку
        if result and not result.get("ok"):
            api_error = result.get("description", "Неизвестная ошибка API")
            return False, f"Telegram API: {api_error}"

        return False, error_msg or "Не удалось отправить файл"

    except PermissionError:
        return False, "Нет доступа к файлу лога"
    except Exception as e:
        _set_flood_cooldown()
        return False, f"Ошибка: {str(e)[:100]}"


def check_bot_connection() -> bool:
    """
    Проверяет доступность бота для логов (тихий режим).
    """
    try:
        token = _get_bot_token()
        if not token:
            return False

        result, _ = _safe_api_call("getMe")
        return result is not None and result.get("ok", False)
    except Exception:
        return False
