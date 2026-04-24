# telegram_proxy/manager.py
"""QThread-based lifecycle manager for Telegram WSS proxy.

Integrates with PyQt6 event system — emits signals on status changes
so the UI page can update without polling.
"""

from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from typing import Optional, Callable

from telegram_proxy import ProxyController
from telegram_proxy.wss_proxy import ProxyStats, UpstreamProxyConfig
from telegram_proxy.proxy_logger import get_proxy_logger

_shared_proxy_manager: Optional["TelegramProxyManager"] = None


class TelegramProxyManager(QThread):
    """Manages proxy lifecycle from GUI thread.

    Signals:
        status_changed(bool)   — emitted when proxy starts/stops
        log_message(str)       — emitted on proxy log events
        stats_updated(object)  — emitted periodically with ProxyStats
    """

    status_changed = pyqtSignal(bool)
    log_message = pyqtSignal(str)
    stats_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller: Optional[ProxyController] = None
        self._stats_timer: Optional[QTimer] = None
        self._proxy_logger = get_proxy_logger()

    @property
    def is_running(self) -> bool:
        c = self._controller
        return c is not None and c.is_running

    @property
    def stats(self) -> Optional[ProxyStats]:
        c = self._controller
        return c.stats if c else None

    @property
    def port(self) -> int:
        c = self._controller
        return c.port if c else 1353

    @property
    def mode(self) -> str:
        c = self._controller
        return c.mode if c else "socks5"

    @property
    def host(self) -> str:
        c = self._controller
        return c.host if c else "127.0.0.1"

    @property
    def proxy_logger(self):
        return self._proxy_logger

    def start_proxy(self, port: int = 1353, mode: str = "socks5", host: str = "127.0.0.1",
                    upstream_config: Optional[UpstreamProxyConfig] = None) -> bool:
        """Start the proxy. Thread-safe, non-blocking."""
        if self.is_running:
            return False

        self._controller = ProxyController(
            port=port,
            mode=mode,
            on_log=self._on_log,
            host=host,
            upstream_config=upstream_config,
        )
        ok = self._controller.start()
        if ok:
            self.status_changed.emit(True)
            self._start_stats_polling()
        else:
            self._on_log("Failed to start proxy")
        return ok

    def stop_proxy(self) -> None:
        """Stop the proxy. Thread-safe."""
        if not self._controller:
            return

        self._stop_stats_polling()
        self._controller.stop()
        self._controller = None
        self.status_changed.emit(False)

    def _stop_controller_only(self) -> None:
        """Stop only the ProxyController (blocking, pure-Python, no Qt).
        Safe to call from any thread. Qt cleanup (timer, signal) must be
        done separately on the GUI thread."""
        controller = self._controller
        if controller:
            controller.stop()
            # Only clear if no new controller was created during stop
            if self._controller is controller:
                self._controller = None

    def restart_proxy(self, port: int = 1353, mode: str = "socks5", host: str = "127.0.0.1",
                      upstream_config: Optional[UpstreamProxyConfig] = None) -> bool:
        """Restart with new config."""
        self.stop_proxy()
        return self.start_proxy(port, mode, host, upstream_config=upstream_config)

    def cleanup(self) -> None:
        """Called on app exit."""
        try:
            self._stop_stats_polling()
        except Exception:
            pass
        try:
            if self._stats_timer is not None:
                self._stats_timer.deleteLater()
        except Exception:
            pass
        try:
            if self._controller:
                self._controller.stop()
        except Exception:
            pass
        self._controller = None
        self._stats_timer = None

    def _on_log(self, msg: str) -> None:
        # Write to file logger + ring buffer (thread-safe)
        self._proxy_logger.log(msg)
        # Emit signal for backward compat (UI now uses drain() instead)
        self.log_message.emit(msg)

    def _start_stats_polling(self) -> None:
        if self._stats_timer is None:
            self._stats_timer = QTimer()
            self._stats_timer.timeout.connect(self._emit_stats)
        self._stats_timer.start(2000)  # Every 2 seconds

    def _stop_stats_polling(self) -> None:
        if self._stats_timer:
            self._stats_timer.stop()

    def _emit_stats(self) -> None:
        c = self._controller
        if c and c.is_running:
            self.stats_updated.emit(c.stats)


def get_proxy_manager() -> TelegramProxyManager:
    global _shared_proxy_manager
    if _shared_proxy_manager is None:
        _shared_proxy_manager = TelegramProxyManager()
    return _shared_proxy_manager


def build_upstream_proxy_config_from_settings() -> Optional[UpstreamProxyConfig]:
    try:
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

        up_host = get_tg_proxy_upstream_host()
        up_port = get_tg_proxy_upstream_port()
        if not up_host or up_port <= 0:
            return None

        return UpstreamProxyConfig(
            enabled=True,
            host=up_host,
            port=up_port,
            mode=get_tg_proxy_upstream_mode(),
            username=get_tg_proxy_upstream_user(),
            password=get_tg_proxy_upstream_pass(),
        )
    except Exception:
        return None


def autostart_proxy_if_enabled_async() -> bool:
    try:
        from settings.store import get_tg_proxy_autostart, get_tg_proxy_host, get_tg_proxy_port
    except Exception:
        return False

    try:
        if not get_tg_proxy_autostart():
            return False

        manager = get_proxy_manager()
        if manager.is_running:
            return False

        port = get_tg_proxy_port()
        host = get_tg_proxy_host()
        upstream_config = build_upstream_proxy_config_from_settings()

        def _start() -> None:
            try:
                manager.start_proxy(
                    port=port,
                    mode="socks5",
                    host=host,
                    upstream_config=upstream_config,
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
