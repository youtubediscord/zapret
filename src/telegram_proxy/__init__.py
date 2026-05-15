# telegram_proxy/__init__.py
"""Telegram WebSocket Proxy — routes Telegram traffic through WSS to bypass IP blocks.

Public API:
    from telegram_proxy import TelegramProxyRuntime

    runtime = TelegramProxyRuntime(port=1353, mode="socks5")
    runtime.start()
    runtime.stop()
    print(runtime.is_running)
    print(runtime.stats)
"""

import asyncio
import logging
import traceback
import threading
from dataclasses import dataclass
from typing import Optional, Callable

from telegram_proxy.wss_proxy import TelegramWSProxy, ProxyStats, UpstreamProxyConfig

log = logging.getLogger("tg_proxy")

# Default port
DEFAULT_PORT = 1353


def _is_ignorable_transport_reset_error(exc: BaseException | None) -> bool:
    if not isinstance(exc, ConnectionResetError):
        return False
    winerror = getattr(exc, "winerror", None)
    errno = getattr(exc, "errno", None)
    return winerror == 10054 or errno == 10054


def _is_ignorable_asyncio_loop_exception(context: dict) -> bool:
    exception = context.get("exception")
    protocol = context.get("protocol")
    transport = context.get("transport")
    if protocol is None and transport is None:
        return False
    return _is_ignorable_transport_reset_error(exception)


def _install_loop_exception_handler(
    loop: asyncio.AbstractEventLoop,
    *,
    on_log: Optional[Callable[[str], None]] = None,
) -> None:
    def _emit_proxy_loop_context(prefix: str, context: dict) -> None:
        if on_log is None:
            return
        try:
            message = str(context.get("message") or "").strip() or "asyncio loop exception"
            exception = context.get("exception")
            if exception is not None:
                details = "".join(
                    traceback.format_exception(
                        type(exception),
                        exception,
                        exception.__traceback__,
                    )
                ).strip()
                on_log(f"{prefix}: {message}\n{details}")
                return
            on_log(f"{prefix}: {message}")
        except Exception:
            pass

    def _handler(current_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        if _is_ignorable_asyncio_loop_exception(context):
            if on_log is not None:
                try:
                    on_log(
                        "Telegram Proxy: удалённая сторона закрыла соединение "
                        "(WinError 10054), это скрыто как сетевой сброс"
                    )
                except Exception:
                    pass
            return
        _emit_proxy_loop_context("Proxy loop exception", context)
        current_loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


class TelegramProxyRuntime:
    """Thread-safe runtime wrapper for the Telegram WSS proxy.

    Runs the asyncio event loop in a dedicated daemon thread.
    Safe to call start/stop from any thread (e.g., PyQt GUI thread).
    """

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        mode: str = "socks5",
        on_log: Optional[Callable[[str], None]] = None,
        host: str = "127.0.0.1",
        upstream_config: Optional[UpstreamProxyConfig] = None,
    ):
        self._port = port
        self._mode = mode
        self._on_log = on_log
        self._host = host
        self._upstream_config = upstream_config
        self._proxy: Optional[TelegramWSProxy] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._proxy is not None and self._proxy.is_running

    @property
    def stats(self) -> Optional[ProxyStats]:
        return self._proxy.stats if self._proxy else None

    @property
    def port(self) -> int:
        return self._port

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def host(self) -> str:
        return self._host

    def start(self) -> bool:
        """Start the proxy in a background thread. Non-blocking.

        Returns True if started successfully, False if already running.
        """
        if self.is_running:
            return False

        self._loop = asyncio.new_event_loop()
        self._proxy = TelegramWSProxy(
            port=self._port,
            mode=self._mode,
            on_log=self._on_log,
            host=self._host,
            upstream_config=self._upstream_config,
        )
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="tg-proxy-loop",
            daemon=True,
        )
        self._thread.start()
        # Wait for the server to actually start (max 5 seconds)
        self._started.wait(timeout=5.0)
        return self.is_running

    def stop(self) -> None:
        """Stop the proxy. Non-blocking with short timeout."""
        loop = self._loop
        proxy = self._proxy
        thread = self._thread

        # Clear refs first to prevent re-entrant calls
        self._loop = None
        self._proxy = None
        self._thread = None

        if not loop or not proxy:
            return

        try:
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(proxy.stop(), loop)
                try:
                    future.result(timeout=2.0)
                except Exception:
                    pass
                loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:
            # Loop already closed
            pass

        if thread and thread.is_alive():
            thread.join(timeout=1.0)

    def update_config(self, port: int = None, mode: str = None, host: str = None,
                      upstream_config: Optional[UpstreamProxyConfig] = None) -> None:
        """Update config. Requires restart to take effect."""
        if port is not None:
            self._port = port
        if mode is not None:
            self._mode = mode
        if host is not None:
            self._host = host
        if upstream_config is not None:
            self._upstream_config = upstream_config

    def restart(self) -> bool:
        """Restart with current config."""
        self.stop()
        return self.start()

    def _run_loop(self) -> None:
        """Run the asyncio event loop in a dedicated thread."""
        loop = self._loop
        if loop is None:
            self._started.set()
            return
        asyncio.set_event_loop(loop)
        _install_loop_exception_handler(loop, on_log=self._on_log)
        try:
            proxy = self._proxy
            if proxy is not None:
                loop.run_until_complete(proxy.start())
            self._started.set()
            loop.run_forever()
        except Exception as e:
            # Log bind errors so they aren't silently swallowed
            if self._on_log:
                try:
                    self._on_log(f"Proxy start failed: {type(e).__name__}: {e}")
                except Exception:
                    pass
            # _started.set() is called in finally block below
        finally:
            # All cleanup in individual try/except to never crash
            if loop is not None and not loop.is_closed():
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                except Exception:
                    pass
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
            self._started.set()
