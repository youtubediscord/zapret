# tgram/tg_sender.py
"""
Мини-обёртка для отправки лога (текст / файл) в Telegram-бота.

Зависимостей, кроме requests, нет – поэтому работает синхронно
и не создаёт предупреждений вида
    RuntimeWarning: coroutine 'Bot.send_document' was never awaited
"""

from __future__ import annotations
from pathlib import Path
import requests
import time 

# ------------------------------------------------------------------
# общие данные берём из tg_log_delta
# ------------------------------------------------------------------
from .tg_log_delta import TOKEN, CHAT_ID, TOPIC_ID, _tg_api as _call_tg_api

TIMEOUT = 30           # секунд

def _mask_token(text: str) -> str:
    """Маскирует токен бота в тексте ошибки."""
    if TOKEN and TOKEN in text:
        return text.replace(TOKEN, "***MASKED***")
    return text
MAX_RETRIES = 3         # сколько раз повторять при flood-wait
FLOOD_COOLDOWN = 1800  # 30 минут cooldown после ошибки (равен интервалу отправки)

# Глобальный cooldown после flood-wait (время до которого блокируем отправки)
_flood_cooldown_until = 0.0

# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------
def _cut_to_4k(text: str, limit: int = 4000) -> str:
    """Обрезаем строку до последних 4 000 символов (лимит Telegram)."""
    return text[-limit:] if len(text) > limit else text

def is_in_flood_cooldown() -> bool:
    """Проверяет, находимся ли мы в режиме cooldown после flood-wait."""
    return time.time() < _flood_cooldown_until


def get_flood_cooldown_remaining() -> float:
    """Возвращает оставшееся время cooldown в секундах."""
    remaining = _flood_cooldown_until - time.time()
    return max(0.0, remaining)


def _set_flood_cooldown():
    """Устанавливает cooldown после ошибки (тихий режим)."""
    global _flood_cooldown_until
    _flood_cooldown_until = time.time() + FLOOD_COOLDOWN


def _safe_call_tg_api(method: str, *, data=None, files=None):
    """
    Обёртка, которая корректно обрабатывает 429 (Too Many Requests) и другие ошибки.
    При любой ошибке устанавливает cooldown вместо спама в лог.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _call_tg_api(method, data=data, files=files)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0

            # 429 - flood-wait, ждём и повторяем
            if status == 429:
                try:
                    retry_after = e.response.json().get("parameters", {}) \
                                               .get("retry_after", 1)
                except Exception:
                    retry_after = 1
                wait = int(retry_after) + 1
                time.sleep(wait)
                continue

            # Любая другая HTTP ошибка (400, 403, etc) - cooldown без спама
            _set_flood_cooldown()
            return None  # тихо выходим

        except Exception:
            # Сетевые ошибки и прочее - тоже cooldown
            _set_flood_cooldown()
            return None

    # Повторы кончились
    _set_flood_cooldown()
    return None

# ------------------------------------------------------------------
# public API
# ------------------------------------------------------------------
def send_log_to_tg(log_path: str | Path, caption: str = "") -> bool:
    """Отправляет текст лога в TG. Возвращает True при успехе (тихий режим)."""
    if is_in_flood_cooldown():
        return False

    try:
        path = Path(log_path)
        if not path.exists():
            return False

        text = _cut_to_4k(path.read_text(encoding="utf-8-sig", errors="replace"))
        data = {"chat_id": CHAT_ID,
                "message_thread_id": TOPIC_ID,
                "text": f"{caption}\n\n{text}" if caption else text,
                "parse_mode": "HTML"}
        result = _safe_call_tg_api("sendMessage", data=data)
        return result is not None
    except Exception:
        _set_flood_cooldown()
        return False


def send_file_to_tg(file_path: str | Path, caption: str = "") -> bool:
    """Возвращает True при успешной отправке, False при ошибке (тихий режим)"""
    # Проверяем cooldown перед отправкой
    if is_in_flood_cooldown():
        return False

    try:
        path = Path(file_path)
        if not path.exists():
            return False

        with path.open("rb") as fh:
            files = {"document": fh}
            data = {"chat_id": CHAT_ID, "message_thread_id": TOPIC_ID, "caption": caption or path.name}
            result = _safe_call_tg_api("sendDocument", data=data, files=files)

        return result is not None
    except Exception:
        _set_flood_cooldown()
        return False