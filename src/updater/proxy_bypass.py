"""
proxy_bypass.py
────────────────────────────────────────────────────────────────
Утилита для автоматического обхода системного прокси при сетевых ошибках.

Когда DPI-инструмент (winws/winws2) устанавливает переменные окружения
HTTP_PROXY / HTTPS_PROXY, все requests-запросы идут через этот прокси.
Если прокси недоступен, запросы падают с ProxyError.

Этот модуль предоставляет:
- request_get_bypass_proxy() — requests.get без прокси
- session_bypass_proxy() — Session с trust_env=False
"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any
from log.log import log



def session_bypass_proxy() -> requests.Session:
    """
    Создаёт Session, которая игнорирует системные прокси.
    Аналог того, что делает donater/api.py.
    """
    s = requests.Session()
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


def request_get_bypass_proxy(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: Any = 10,
    verify: bool = True,
    stream: bool = False,
) -> requests.Response:
    """
    Делает GET-запрос, полностью минуя системный прокси.

    Параметры совпадают с requests.get(), но proxies принудительно пуст.
    """
    session = session_bypass_proxy()
    try:
        return session.get(
            url,
            headers=headers,
            timeout=timeout,
            verify=verify,
            stream=stream,
        )
    finally:
        session.close()
