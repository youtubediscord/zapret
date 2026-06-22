# telegram_proxy/manager.py
"""QThread-based lifecycle manager for Telegram WSS proxy.

Integrates with PyQt6 event system — emits signals on status changes.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, Callable

from telegram_proxy import TelegramProxyRuntime
from telegram_proxy.wss_proxy import CloudflareFallbackConfig, ProxyStats, UpstreamProxyConfig
from telegram_proxy.proxy_logger import get_proxy_logger

_shared_proxy_manager: Optional["TelegramProxyManager"] = None


class TelegramProxyManager(QThread):
    """Manages proxy lifecycle from GUI thread.

    Signals:
        status_changed(bool)      — emitted when proxy starts/stops
        upstream_selected(str,str) — emitted when bundled SOCKS fallback proves working
    """

    status_changed = pyqtSignal(bool)
    upstream_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._runtime: Optional[TelegramProxyRuntime] = None
        self._proxy_logger = get_proxy_logger()

    @property
    def is_running(self) -> bool:
        c = self._runtime
        return c is not None and c.is_running

    @property
    def stats(self) -> Optional[ProxyStats]:
        c = self._runtime
        return c.stats if c else None

    @property
    def port(self) -> int:
        c = self._runtime
        return c.port if c else 1353

    @property
    def mode(self) -> str:
        c = self._runtime
        return c.mode if c else "socks5"

    @property
    def host(self) -> str:
        c = self._runtime
        return c.host if c else "127.0.0.1"

    @property
    def proxy_logger(self):
        return self._proxy_logger

    def start_proxy(self, port: int = 1353, mode: str = "socks5", host: str = "127.0.0.1",
                    upstream_config: Optional[UpstreamProxyConfig] = None,
                    cloudflare_config: Optional[CloudflareFallbackConfig] = None,
                    mtproxy_secret: str = "",
                    dc_endpoint_overrides: Optional[dict[int, str]] = None,
                    pool_size: int = 4,
                    buffer_kb: int = 256,
                    fake_tls_domain: str = "",
                    proxy_protocol: bool = False) -> bool:
        """Start the proxy. Thread-safe, non-blocking."""
        if self.is_running:
            return False

        self._runtime = TelegramProxyRuntime(
            port=port,
            mode=mode,
            on_log=self._on_log,
            on_upstream_selected=self._on_upstream_selected,
            host=host,
            upstream_config=upstream_config,
            cloudflare_config=cloudflare_config,
            mtproxy_secret=mtproxy_secret,
            dc_endpoint_overrides=dc_endpoint_overrides,
            pool_size=pool_size,
            buffer_kb=buffer_kb,
            fake_tls_domain=fake_tls_domain,
            proxy_protocol=proxy_protocol,
        )
        ok = self._runtime.start()
        if ok:
            self.status_changed.emit(True)
        else:
            self._on_log("Failed to start proxy")
        return ok

    def stop_proxy(self) -> None:
        """Stop the proxy. Thread-safe."""
        if not self._runtime:
            return

        self._runtime.stop()
        self._runtime = None
        self.status_changed.emit(False)

    def _stop_runtime_only(self) -> None:
        """Stop only the TelegramProxyRuntime (blocking, pure-Python, no Qt).
        Safe to call from any thread. Qt cleanup (timer, signal) must be
        done separately on the GUI thread."""
        runtime = self._runtime
        if runtime:
            runtime.stop()
            # Only clear if no new runtime was created during stop
            if self._runtime is runtime:
                self._runtime = None

    def restart_proxy(self, port: int = 1353, mode: str = "socks5", host: str = "127.0.0.1",
                      upstream_config: Optional[UpstreamProxyConfig] = None,
                      cloudflare_config: Optional[CloudflareFallbackConfig] = None,
                      mtproxy_secret: str = "",
                      dc_endpoint_overrides: Optional[dict[int, str]] = None,
                      pool_size: int = 4,
                      buffer_kb: int = 256,
                      fake_tls_domain: str = "",
                      proxy_protocol: bool = False) -> bool:
        """Restart with new config."""
        self.stop_proxy()
        return self.start_proxy(
            port,
            mode,
            host,
            upstream_config=upstream_config,
            cloudflare_config=cloudflare_config,
            mtproxy_secret=mtproxy_secret,
            dc_endpoint_overrides=dc_endpoint_overrides,
            pool_size=pool_size,
            buffer_kb=buffer_kb,
            fake_tls_domain=fake_tls_domain,
            proxy_protocol=proxy_protocol,
        )

    def cleanup(self) -> None:
        """Called on app exit."""
        try:
            if self._runtime:
                self._runtime.stop()
        except Exception:
            pass
        self._runtime = None

    def _on_log(self, msg: str) -> None:
        self._proxy_logger.log(msg)

    def _on_upstream_selected(self, preset_id: str, preset_name: str) -> None:
        self.upstream_selected.emit(str(preset_id or ""), str(preset_name or ""))


def get_proxy_manager() -> TelegramProxyManager:
    global _shared_proxy_manager
    if _shared_proxy_manager is None:
        _shared_proxy_manager = TelegramProxyManager()
    return _shared_proxy_manager


def build_upstream_proxy_config_from_settings() -> Optional[UpstreamProxyConfig]:
    try:
        import telegram_proxy.config.settings as telegram_proxy_settings

        return telegram_proxy_settings.build_upstream_config()
    except Exception:
        return None


def build_cloudflare_proxy_config_from_settings() -> CloudflareFallbackConfig:
    try:
        import telegram_proxy.config.settings as telegram_proxy_settings

        return telegram_proxy_settings.build_cloudflare_config()
    except Exception:
        return CloudflareFallbackConfig()


def build_dc_endpoint_overrides_from_settings() -> dict[int, str]:
    try:
        import telegram_proxy.config.settings as telegram_proxy_settings

        return telegram_proxy_settings.build_dc_endpoint_overrides()
    except Exception:
        return {}


def start_proxy_if_enabled_async() -> bool:
    try:
        from settings.store import (
            get_tg_proxy_enabled,
            get_tg_proxy_buffer_kb,
            get_tg_proxy_fake_tls_domain,
            get_tg_proxy_host,
            get_tg_proxy_mode,
            get_tg_proxy_mtproxy_secret,
            get_tg_proxy_pool_size,
            get_tg_proxy_port,
            get_tg_proxy_proxy_protocol,
        )
    except Exception:
        return False

    try:
        if not get_tg_proxy_enabled():
            return False

        manager = get_proxy_manager()
        if manager.is_running:
            return False

        port = get_tg_proxy_port()
        host = get_tg_proxy_host()
        try:
            import telegram_proxy.config.settings as telegram_proxy_settings

            mode = telegram_proxy_settings.normalize_proxy_mode(get_tg_proxy_mode())
            mtproxy_secret = telegram_proxy_settings.ensure_mtproxy_secret_for_mode(
                mode,
                get_tg_proxy_mtproxy_secret(),
            )
        except Exception:
            mode = "socks5"
            mtproxy_secret = get_tg_proxy_mtproxy_secret()
        upstream_config = build_upstream_proxy_config_from_settings()
        cloudflare_config = build_cloudflare_proxy_config_from_settings()
        dc_endpoint_overrides = build_dc_endpoint_overrides_from_settings()
        try:
            import telegram_proxy.config.settings as telegram_proxy_settings

            pool_size = telegram_proxy_settings.normalize_pool_size(get_tg_proxy_pool_size())
            buffer_kb = telegram_proxy_settings.normalize_buffer_kb(get_tg_proxy_buffer_kb())
            fake_tls_domain = telegram_proxy_settings.normalize_fake_tls_domain(get_tg_proxy_fake_tls_domain())
            proxy_protocol = bool(get_tg_proxy_proxy_protocol())
        except Exception:
            pool_size = 4
            buffer_kb = 256
            fake_tls_domain = ""
            proxy_protocol = False

        def _start() -> None:
            try:
                manager.start_proxy(
                    port=port,
                    mode=mode,
                    host=host,
                    upstream_config=upstream_config,
                    cloudflare_config=cloudflare_config,
                    mtproxy_secret=mtproxy_secret,
                    dc_endpoint_overrides=dc_endpoint_overrides,
                    pool_size=pool_size,
                    buffer_kb=buffer_kb,
                    fake_tls_domain=fake_tls_domain,
                    proxy_protocol=proxy_protocol,
                )
            except Exception:
                pass

        import threading

        threading.Thread(
            target=_start,
            daemon=True,
            name="TelegramProxyAutostart",
        ).start()
        return True
    except Exception:
        return False
