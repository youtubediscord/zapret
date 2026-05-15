from __future__ import annotations

from dataclasses import dataclass

from telegram_proxy.upstream_catalog import UpstreamCatalog


@dataclass(slots=True)
class TelegramProxySettingsState:
    host: str
    port: int
    upstream_enabled: bool
    upstream_host: str
    upstream_port: int
    upstream_user: str
    upstream_password: str
    upstream_mode: str
    upstream_preset_index: int

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1353
DEFAULT_UPSTREAM_PORT = 1080

def default_state() -> TelegramProxySettingsState:
    return TelegramProxySettingsState(
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        upstream_enabled=False,
        upstream_host="",
        upstream_port=DEFAULT_UPSTREAM_PORT,
        upstream_user="",
        upstream_password="",
        upstream_mode="fallback",
        upstream_preset_index=0,
    )

def validate_host(host: str) -> bool:
    if not host:
        return False
    parts = host.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False

def normalize_host(host: str) -> str:
    text = str(host or "").strip()
    if validate_host(text):
        return text
    return DEFAULT_HOST

def normalize_port(port: int | None) -> int:
    try:
        value = int(port or 0)
    except (TypeError, ValueError):
        return DEFAULT_PORT
    if 1024 <= value <= 65535:
        return value
    return DEFAULT_PORT

def normalize_upstream_port(port: int | None) -> int:
    try:
        value = int(port or 0)
    except (TypeError, ValueError):
        return DEFAULT_UPSTREAM_PORT
    if 1 <= value <= 65535:
        return value
    return DEFAULT_UPSTREAM_PORT

def build_manual_instruction_text(host: str, port: int) -> str:
    return f"  Тип: SOCKS5  |  Хост: {normalize_host(host)}  |  Порт: {normalize_port(port)}"

def build_proxy_url(host: str, port: int) -> str:
    return f"tg://socks?server={normalize_host(host)}&port={normalize_port(port)}"

def load_state(upstream_catalog: UpstreamCatalog) -> TelegramProxySettingsState:
    state = default_state()

    try:
        from settings.store import (
            get_tg_proxy_host,
            get_tg_proxy_port,
            get_tg_proxy_upstream_enabled,
            get_tg_proxy_upstream_host,
            get_tg_proxy_upstream_mode,
            get_tg_proxy_upstream_pass,
            get_tg_proxy_upstream_port,
            get_tg_proxy_upstream_user,
        )

        host = normalize_host(get_tg_proxy_host())
        port = normalize_port(get_tg_proxy_port())
        upstream_host = str(get_tg_proxy_upstream_host() or "").strip()
        upstream_port = normalize_upstream_port(get_tg_proxy_upstream_port())
        upstream_user = str(get_tg_proxy_upstream_user() or "").strip()
        upstream_password = str(get_tg_proxy_upstream_pass() or "")
        upstream_mode = str(get_tg_proxy_upstream_mode() or "fallback").strip().lower() or "fallback"
        upstream_preset_index = upstream_catalog.find_choice_index(
            host=upstream_host,
            port=upstream_port,
            username=upstream_user,
            password=upstream_password,
        )

        return TelegramProxySettingsState(
            host=host,
            port=port,
            upstream_enabled=bool(get_tg_proxy_upstream_enabled()),
            upstream_host=upstream_host,
            upstream_port=upstream_port,
            upstream_user=upstream_user,
            upstream_password=upstream_password,
            upstream_mode=upstream_mode,
            upstream_preset_index=upstream_preset_index,
        )
    except Exception:
        return state

def set_port(port: int) -> int:
    normalized = normalize_port(port)
    try:
        from settings.store import set_tg_proxy_port

        set_tg_proxy_port(normalized)
    except Exception:
        pass
    return normalized

def set_host(host: str) -> str:
    normalized = normalize_host(host)
    try:
        from settings.store import set_tg_proxy_host

        set_tg_proxy_host(normalized)
    except Exception:
        pass
    return normalized

def set_proxy_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_enabled

        set_tg_proxy_enabled(bool(enabled))
    except Exception:
        pass

def set_upstream_enabled(enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_upstream_enabled

        set_tg_proxy_upstream_enabled(bool(enabled))
    except Exception:
        pass

def set_upstream_mode(always_enabled: bool) -> None:
    try:
        from settings.store import set_tg_proxy_upstream_mode

        set_tg_proxy_upstream_mode("always" if always_enabled else "fallback")
    except Exception:
        pass

def set_upstream_fields(host: str, port: int, user: str, password: str) -> None:
    try:
        from settings.store import (
            set_tg_proxy_upstream_host,
            set_tg_proxy_upstream_pass,
            set_tg_proxy_upstream_port,
            set_tg_proxy_upstream_user,
        )

        set_tg_proxy_upstream_host(str(host or "").strip())
        set_tg_proxy_upstream_port(normalize_upstream_port(port))
        set_tg_proxy_upstream_user(str(user or "").strip())
        set_tg_proxy_upstream_pass(str(password or ""))
    except Exception:
        pass

def load_upstream_test_target() -> tuple[str, int] | None:
    try:
        from settings.store import (
            get_tg_proxy_upstream_enabled,
            get_tg_proxy_upstream_host,
            get_tg_proxy_upstream_port,
        )

        if not get_tg_proxy_upstream_enabled():
            return None

        host = str(get_tg_proxy_upstream_host() or "").strip()
        port = normalize_upstream_port(get_tg_proxy_upstream_port())
        if not host or port <= 0:
            return None
        return host, port
    except Exception:
        return None

def build_upstream_config():
    try:
        from telegram_proxy.wss_proxy import UpstreamProxyConfig
        from settings.store import (
            get_tg_proxy_upstream_enabled,
            get_tg_proxy_upstream_host,
            get_tg_proxy_upstream_mode,
            get_tg_proxy_upstream_pass,
            get_tg_proxy_upstream_port,
            get_tg_proxy_upstream_user,
        )

        if not get_tg_proxy_upstream_enabled():
            return None

        host = str(get_tg_proxy_upstream_host() or "").strip()
        port = normalize_upstream_port(get_tg_proxy_upstream_port())
        if not host or port <= 0:
            return None

        return UpstreamProxyConfig(
            enabled=True,
            host=host,
            port=port,
            mode=str(get_tg_proxy_upstream_mode() or "fallback"),
            username=str(get_tg_proxy_upstream_user() or "").strip(),
            password=str(get_tg_proxy_upstream_pass() or ""),
        )
    except Exception:
        return None

def consume_auto_deeplink_request() -> bool:
    try:
        from settings.store import get_tg_proxy_deeplink_done, set_tg_proxy_deeplink_done

        if get_tg_proxy_deeplink_done():
            return False
        set_tg_proxy_deeplink_done(True)
        return True
    except Exception:
        return False
