"""
tgram ─ Telegram helpers for Zapret GUI

Содержимое подпакета
--------------------
tg_log_delta.py  – общие константы (TOKEN, CHAT_ID, get_client_id, …)  
tg_sender.py     – низкоуровневые функции отправки (с обработкой 429)  
tg_log_full.py   – FullLogDaemon для периодической отправки файла  
"""

from __future__ import annotations

# ────────────────────────────────────────────────────────────────────
#  «Публичные» объекты, доступные при  `from tgram import …`
# ────────────────────────────────────────────────────────────────────
from .tg_log_delta import TOKEN, CHAT_ID, get_client_id

from .tg_sender     import (send_file_to_tg, send_log_to_tg,
                            is_in_flood_cooldown, get_flood_cooldown_remaining)
from .tg_log_full   import FullLogDaemon, TgSendWorker

__all__ = [
    "TOKEN",
    "CHAT_ID",
    "get_client_id",
    "send_file_to_tg",
    "send_log_to_tg",
    "is_in_flood_cooldown",
    "get_flood_cooldown_remaining",
    "FullLogDaemon",
    "start_log_daemon",
    "TgSendWorker"
]

__version__ = "1.0.0"
__author__  = "Zapret GUI Team"

# ────────────────────────────────────────────────────────────────────
#  Утилита-обёртка: быстро запустить демон отправки лога
# ────────────────────────────────────────────────────────────────────
def start_log_daemon(log_path: str,
                     interval: int = 1800,
                     parent=None) -> FullLogDaemon:
    """
    Создаёт и возвращает FullLogDaemon.
    """
    
    return FullLogDaemon(log_path, interval, parent=parent)