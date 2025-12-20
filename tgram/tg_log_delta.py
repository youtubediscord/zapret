# tg_log_delta.py

"""
Дельта-лог → Telegram.
• dev-сборки (APP_VERSION начинается с 2025) шлют в отдельного бота.
"""

from __future__ import annotations
import os, sys, uuid, platform, threading, requests, pathlib, winreg, traceback
from datetime import datetime
from typing import Optional
from config import APP_VERSION, CHANNEL # build_info moved to config/__init__.py

# ───────────── определяем, test это или нет ─────────────
IS_DEV_BUILD = True if CHANNEL == "test" else False

# ───────────── обфусцированные данные ботов ───────────────────
import base64

# прод-бот (stable)
_PROD_ENC = "c3h+fnp8fn58enEKCgMyHnMRHAZ4fSxmOx4cHCIuMSYxIT8jfQoEfDgAKAAgDg=="
_PROD_XOR = 0x4B
_PROD_SUM = 527

# dev-бот (test)
_DEV_ENC = "ZGhoZW5tZWVobGYdHRs1ZCopGxgvN2sSHi0EbWwmGDpxamopPnEtbRhqEWoQMw=="
_DEV_XOR = 0x5C
_DEV_SUM = 530

# Группа для логов
CHAT_ID = -1003005847271

# Топик зависит от канала: test → 10854, stable → 1
TOPIC_ID = 10854 if IS_DEV_BUILD else 1

# Топик для ошибок (error/warning) - общий для всех версий
ERROR_TOPIC_ID = 12681

def _decode_token(encoded: str, xor_key: int, checksum: int) -> str:
    """Деобфусцирует токен"""
    try:
        decoded = base64.b64decode(encoded)
        value = ''.join(chr(b ^ xor_key) for b in decoded)
        if sum(ord(c) for c in value[:10]) != checksum:
            return ""
        return value
    except:
        return ""

#  выбираем токен
TOKEN = _decode_token(_DEV_ENC, _DEV_XOR, _DEV_SUM) if IS_DEV_BUILD else _decode_token(_PROD_ENC, _PROD_XOR, _PROD_SUM)

# интервалы / лимиты
INTERVAL  = 1800  # 30 минут между отправками
MAX_CHUNK = 3500

# ---------- Client-ID (как было) ------------------------------------
try:
    from PyQt6.QtCore import QTimer
except ImportError:
    QTimer = None

def _reg_get() -> Optional[str]:
    from config import REGISTRY_PATH
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
        cid, _ = winreg.QueryValueEx(k, "ClientID")
        return cid
    except Exception:
        return None

def _reg_set(cid: str):
    from config import REGISTRY_PATH
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
    winreg.SetValueEx(k, "ClientID", 0, winreg.REG_SZ, cid)

def get_client_id() -> str:
    if sys.platform.startswith("win"):
        cid = _reg_get()
        if cid:
            return cid
        cid = str(uuid.uuid4())
        _reg_set(cid)
        return cid
    path = pathlib.Path.home() / ".zapret_client_id"
    if path.exists():
        return path.read_text().strip()
    cid = str(uuid.uuid4())
    path.write_text(cid)
    return cid

CID  = get_client_id()
HOST = platform.node() or "unknown-pc"

# ---------- Telegram helpers ----------------------------------------
API = f"https://api.telegram.org/bot{TOKEN}"

def _async_post(url: str, **kw):
    threading.Thread(
        target=requests.post,
        kwargs=dict(url=url, timeout=30, **kw),
        daemon=True
    ).start()

def _chunks(txt: str, n: int = MAX_CHUNK):
    for i in range(0, len(txt), n):
        yield txt[i:i+n]

def _send(text: str, topic_id: int = TOPIC_ID):
    for part in _chunks(text):
        _async_post(
            f"{API}/sendMessage",
            data=dict(
                chat_id=CHAT_ID,
                message_thread_id=topic_id,
                text=f"<pre>{part}</pre>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        )

def _has_error_or_warning(text: str) -> bool:
    """Проверяет наличие error или warning в тексте (case-insensitive)"""
    lower = text.lower()
    return "error" in lower or "warning" in lower

# ---------- Tail-sender ---------------------------------------------
class LogTailSender:
    def __init__(self, path: str):
        self.path = path
        self.pos  = os.path.getsize(path) if os.path.isfile(path) else 0

    @staticmethod
    def _make_header(lines: int) -> str:
        return (
            "────────\n"
            f"ID  : {CID}\n"
            f"Zapret2 v{APP_VERSION}\n"
            f"Host: {HOST}\n"
            f"Δ {datetime.now():%H:%M:%S}  ({lines} lines)\n"
            "────────\n"
        )

    def send_delta(self):
        try:
            if not (TOKEN and CHAT_ID):
                return
            if not os.path.isfile(self.path):
                self.pos = 0
                return
            size = os.path.getsize(self.path)
            if size < self.pos:
                self.pos = 0
            if size == self.pos:
                return
            with open(self.path, "r", encoding="utf-8-sig", errors="ignore") as f:
                f.seek(self.pos)
                delta = f.read()
                self.pos = f.tell()
            if not delta.strip():
                return
            header = self._make_header(delta.count("\n") or 1)
            full_message = header + delta
            _send(full_message)

            # Если есть error/warning - дополнительно отправляем в error-топик
            if _has_error_or_warning(delta):
                _send(full_message, topic_id=ERROR_TOPIC_ID)
        except Exception:
            pass  # тихий режим

# ---------- Qt-обёртка ----------------------------------------------
class LogDeltaDaemon:
    def __init__(self, log_path: str, interval: int = INTERVAL, parent=None):
        if QTimer is None:
            raise RuntimeError("PyQt6 не установлена")
        if interval < 3:
            raise ValueError("Интервал ≥ 3 сек")
        self.sender = LogTailSender(log_path)
        self.timer  = QTimer(parent)
        self.timer.setInterval(interval * 1000)
        self.timer.timeout.connect(self.sender.send_delta)
        self.timer.start()

# ---------- Доп. функции для ручной отправки ------------------------
from pathlib import Path
import requests
def _tg_api(method: str, files=None, data=None):
    url = f"{API}/{method}"
    r   = requests.post(url, files=files, data=data, timeout=30)
    r.raise_for_status()
    return r.json()

def send_log_to_tg(log_path: str | Path, caption: str = "") -> None:
    path = Path(log_path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")[-4000:]
    data = {
        "chat_id": CHAT_ID,
        "message_thread_id": TOPIC_ID,
        "text": (caption + "\n\n" if caption else "") + text,
        "parse_mode": "HTML"
    }
    _tg_api("sendMessage", data=data)

def send_file_to_tg(file_path: str | Path, caption: str = "") -> None:
    path = Path(file_path)
    with path.open("rb") as fh:
        files = {"document": fh}
        data = {
            "chat_id": CHAT_ID,
            "message_thread_id": TOPIC_ID,
            "caption": caption or path.name
        }
        _tg_api("sendDocument", files=files, data=data)