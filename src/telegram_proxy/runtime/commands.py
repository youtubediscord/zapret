from __future__ import annotations

import os
import subprocess
import webbrowser
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
    from telegram_proxy.config.settings import build_upstream_config

    return TelegramProxyStartConfig(
        host=str(get_tg_proxy_host() or "127.0.0.1"),
        port=int(get_tg_proxy_port() or 1353),
        mode="socks5",
        upstream_config=build_upstream_config(),
    )


def build_upstream_config():
    from telegram_proxy.config.settings import build_upstream_config as _build_upstream_config

    return _build_upstream_config()


def set_enabled(enabled: bool) -> None:
    from settings.store import set_tg_proxy_enabled

    set_tg_proxy_enabled(bool(enabled))


def append_log_line(message: str) -> None:
    manager = get_proxy_manager()
    manager.proxy_logger.log(str(message or ""))


def consume_auto_deeplink_request() -> bool:
    import telegram_proxy.config.settings as telegram_proxy_settings

    return bool(telegram_proxy_settings.consume_auto_deeplink_request())


def load_page_initial_state():
    import telegram_proxy.config.settings as telegram_proxy_settings

    return telegram_proxy_settings.load_page_initial_state()


def save_settings_action(
    action: str,
    *,
    host: str = "",
    port: int = 0,
    user: str = "",
    password: str = "",
    enabled: bool = False,
):
    import telegram_proxy.config.settings as telegram_proxy_settings

    action_name = str(action or "").strip()
    if action_name == "host":
        return telegram_proxy_settings.set_host(host)
    if action_name == "port":
        return telegram_proxy_settings.set_port(port)
    if action_name == "proxy_enabled":
        return telegram_proxy_settings.set_proxy_enabled(enabled)
    if action_name == "upstream_enabled":
        return telegram_proxy_settings.set_upstream_enabled(enabled)
    if action_name == "upstream_fields":
        return telegram_proxy_settings.set_upstream_fields(host, port, user, password)
    if action_name == "upstream_mode":
        return telegram_proxy_settings.set_upstream_mode(enabled)
    raise ValueError(f"Неизвестная настройка Telegram Proxy: {action_name}")


def open_log_file(path: str) -> TelegramProxyActionResult:
    target = os.path.normpath(str(path or ""))
    if os.path.exists(target):
        try:
            subprocess.Popen(["explorer", "/select,", target])
            return TelegramProxyActionResult(True, "", "", "")
        except Exception as e:
            return TelegramProxyActionResult(False, f"Failed to open log file: {e}", "", "")
    return TelegramProxyActionResult(False, f"Log file not found: {target}", "", "")


def open_external_link(url: str, *, success_log: str, error_prefix: str) -> TelegramProxyActionResult:
    target = str(url or "").strip()
    if not target:
        return TelegramProxyActionResult(False, f"{error_prefix}: empty url", "", "")
    try:
        webbrowser.open(target)
        return TelegramProxyActionResult(True, success_log, "", "")
    except Exception as e:
        return TelegramProxyActionResult(False, f"{error_prefix}: {e}", "", "")


def run_diagnostics(*, proxy_port: int, progress_callback=None) -> str:
    from telegram_proxy.diagnostics import run_all

    return str(run_all(proxy_port=proxy_port, progress_callback=progress_callback))


def check_relay_reachable(*, timeout: float = 5.0) -> dict:
    from telegram_proxy.wss_proxy import check_relay_reachable as _check_relay_reachable

    return dict(_check_relay_reachable(timeout=timeout))


def check_relay_http(relay_ip: str = "149.154.167.220", timeout: float = 5.0) -> bool:
    import socket

    try:
        sock = socket.create_connection((relay_ip, 80), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False
