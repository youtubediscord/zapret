from __future__ import annotations

from dataclasses import dataclass

from telegram_proxy.upstream_catalog import UpstreamCatalog


@dataclass(slots=True)
class TelegramProxySettingsState:
    host: str
    port: int
    autostart_enabled: bool
    upstream_enabled: bool
    upstream_host: str
    upstream_port: int
    upstream_user: str
    upstream_password: str
    upstream_mode: str
    upstream_preset_index: int


class TelegramProxySettingsController:
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 1353
    DEFAULT_UPSTREAM_PORT = 1080

    @classmethod
    def default_state(cls) -> TelegramProxySettingsState:
        return TelegramProxySettingsState(
            host=cls.DEFAULT_HOST,
            port=cls.DEFAULT_PORT,
            autostart_enabled=False,
            upstream_enabled=False,
            upstream_host="",
            upstream_port=cls.DEFAULT_UPSTREAM_PORT,
            upstream_user="",
            upstream_password="",
            upstream_mode="fallback",
            upstream_preset_index=0,
        )

    @staticmethod
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

    @classmethod
    def normalize_host(cls, host: str) -> str:
        text = str(host or "").strip()
        if cls.validate_host(text):
            return text
        return cls.DEFAULT_HOST

    @classmethod
    def normalize_port(cls, port: int | None) -> int:
        try:
            value = int(port or 0)
        except (TypeError, ValueError):
            return cls.DEFAULT_PORT
        if 1024 <= value <= 65535:
            return value
        return cls.DEFAULT_PORT

    @classmethod
    def normalize_upstream_port(cls, port: int | None) -> int:
        try:
            value = int(port or 0)
        except (TypeError, ValueError):
            return cls.DEFAULT_UPSTREAM_PORT
        if 1 <= value <= 65535:
            return value
        return cls.DEFAULT_UPSTREAM_PORT

    @classmethod
    def build_manual_instruction_text(cls, host: str, port: int) -> str:
        return f"  Тип: SOCKS5  |  Хост: {cls.normalize_host(host)}  |  Порт: {cls.normalize_port(port)}"

    @classmethod
    def build_proxy_url(cls, host: str, port: int) -> str:
        return f"tg://socks?server={cls.normalize_host(host)}&port={cls.normalize_port(port)}"

    @classmethod
    def load_state(cls, upstream_catalog: UpstreamCatalog) -> TelegramProxySettingsState:
        state = cls.default_state()

        try:
            from config.reg import (
                get_tg_proxy_autostart,
                get_tg_proxy_host,
                get_tg_proxy_port,
                get_tg_proxy_upstream_enabled,
                get_tg_proxy_upstream_host,
                get_tg_proxy_upstream_mode,
                get_tg_proxy_upstream_pass,
                get_tg_proxy_upstream_port,
                get_tg_proxy_upstream_user,
            )

            host = cls.normalize_host(get_tg_proxy_host())
            port = cls.normalize_port(get_tg_proxy_port())
            upstream_host = str(get_tg_proxy_upstream_host() or "").strip()
            upstream_port = cls.normalize_upstream_port(get_tg_proxy_upstream_port())
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
                autostart_enabled=bool(get_tg_proxy_autostart()),
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

    @staticmethod
    def set_autostart(enabled: bool) -> None:
        try:
            from config.reg import set_tg_proxy_autostart

            set_tg_proxy_autostart(bool(enabled))
        except Exception:
            pass

    @classmethod
    def set_port(cls, port: int) -> int:
        normalized = cls.normalize_port(port)
        try:
            from config.reg import set_tg_proxy_port

            set_tg_proxy_port(normalized)
        except Exception:
            pass
        return normalized

    @classmethod
    def set_host(cls, host: str) -> str:
        normalized = cls.normalize_host(host)
        try:
            from config.reg import set_tg_proxy_host

            set_tg_proxy_host(normalized)
        except Exception:
            pass
        return normalized

    @staticmethod
    def set_proxy_enabled(enabled: bool) -> None:
        try:
            from config.reg import set_tg_proxy_enabled

            set_tg_proxy_enabled(bool(enabled))
        except Exception:
            pass

    @staticmethod
    def set_upstream_enabled(enabled: bool) -> None:
        try:
            from config.reg import set_tg_proxy_upstream_enabled

            set_tg_proxy_upstream_enabled(bool(enabled))
        except Exception:
            pass

    @staticmethod
    def set_upstream_mode(always_enabled: bool) -> None:
        try:
            from config.reg import set_tg_proxy_upstream_mode

            set_tg_proxy_upstream_mode("always" if always_enabled else "fallback")
        except Exception:
            pass

    @classmethod
    def set_upstream_fields(cls, host: str, port: int, user: str, password: str) -> None:
        try:
            from config.reg import (
                set_tg_proxy_upstream_host,
                set_tg_proxy_upstream_pass,
                set_tg_proxy_upstream_port,
                set_tg_proxy_upstream_user,
            )

            set_tg_proxy_upstream_host(str(host or "").strip())
            set_tg_proxy_upstream_port(cls.normalize_upstream_port(port))
            set_tg_proxy_upstream_user(str(user or "").strip())
            set_tg_proxy_upstream_pass(str(password or ""))
        except Exception:
            pass

    @classmethod
    def load_upstream_test_target(cls) -> tuple[str, int] | None:
        try:
            from config.reg import (
                get_tg_proxy_upstream_enabled,
                get_tg_proxy_upstream_host,
                get_tg_proxy_upstream_port,
            )

            if not get_tg_proxy_upstream_enabled():
                return None

            host = str(get_tg_proxy_upstream_host() or "").strip()
            port = cls.normalize_upstream_port(get_tg_proxy_upstream_port())
            if not host or port <= 0:
                return None
            return host, port
        except Exception:
            return None

    @classmethod
    def build_upstream_config(cls):
        try:
            from telegram_proxy.wss_proxy import UpstreamProxyConfig
            from config.reg import (
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
            port = cls.normalize_upstream_port(get_tg_proxy_upstream_port())
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

    @staticmethod
    def consume_auto_deeplink_request() -> bool:
        try:
            from config import REGISTRY_PATH
            from config.reg import reg

            if reg(REGISTRY_PATH, "TgProxyDeeplinkDone"):
                return False
            reg(REGISTRY_PATH, "TgProxyDeeplinkDone", 1)
            return True
        except Exception:
            return False
