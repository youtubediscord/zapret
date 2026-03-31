"""
tgram ─ Telegram helpers for Zapret GUI

Модуль хранит только вспомогательные Telegram-функции сообщества.

tg_log_delta.py  – константы (TOKEN, CHAT_ID, get_client_id, …)
tg_sender.py     – функции ручной отправки (с обработкой 429)
"""

from __future__ import annotations

from .tg_log_delta import TOKEN, CHAT_ID, get_client_id

from .tg_sender     import (send_file_to_tg, send_log_to_tg,
                            is_in_flood_cooldown, get_flood_cooldown_remaining)

__all__ = [
    "TOKEN",
    "CHAT_ID",
    "get_client_id",
    "send_file_to_tg",
    "send_log_to_tg",
    "is_in_flood_cooldown",
    "get_flood_cooldown_remaining",
]
