from __future__ import annotations

from dataclasses import dataclass

from telegram_proxy.actions import (
    TelegramProxyActionResult,
    TelegramProxyDiagnosticsFinishPlan,
    TelegramProxyDiagnosticsPollPlan,
    TelegramProxyDiagnosticsStartPlan,
    build_diagnostics_finish_plan,
    build_diagnostics_poll_plan,
    build_diagnostics_start_plan,
    copy_text,
    ensure_telegram_hosts,
    open_external_link,
    open_log_file,
)


@dataclass(frozen=True, slots=True)
class TelegramProxyStartConfig:
    host: str
    port: int
    mode: str
    upstream_config: object | None


def get_proxy_manager():
    from telegram_proxy.manager import get_proxy_manager as _get_proxy_manager

    return _get_proxy_manager()


def start_proxy_if_enabled_async() -> bool:
    from telegram_proxy.manager import start_proxy_if_enabled_async as _start_proxy_if_enabled_async

    return bool(_start_proxy_if_enabled_async())


def get_start_config() -> TelegramProxyStartConfig:
    from settings.store import get_tg_proxy_host, get_tg_proxy_port
    from telegram_proxy.settings import build_upstream_config

    return TelegramProxyStartConfig(
        host=str(get_tg_proxy_host() or "127.0.0.1"),
        port=int(get_tg_proxy_port() or 1353),
        mode="socks5",
        upstream_config=build_upstream_config(),
    )


def set_enabled(enabled: bool) -> None:
    from settings.store import set_tg_proxy_enabled

    set_tg_proxy_enabled(bool(enabled))


def run_diagnostics(*, proxy_port: int, progress_callback=None) -> str:
    from telegram_proxy.diagnostics import run_all

    return str(run_all(proxy_port=proxy_port, progress_callback=progress_callback))
