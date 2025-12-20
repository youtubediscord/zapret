# net_helpers.py
import requests
from requests.adapters import HTTPAdapter, Retry

def make_session() -> requests.Session:
    """Session c 3-кратным повтором и нормальными тайм-аутами."""
    retry = Retry(
        total=3,                   # 1 + 2 повтора
        backoff_factor=1,          # 1-2-4-секундная задержка
        status_forcelist=(502, 503, 504, 522, 524),
    )

    sess = requests.Session()
    sess.headers.update({"User-Agent": "ZapretGUI/1.0"})
    sess.mount("https://", HTTPAdapter(max_retries=retry))
    return sess

HTTP = make_session()             # глобальный Session (keep-alive)
DEFAULT_TIMEOUT = (5, 30)         # 5 с на connect, 30 с на чтение