"""Upstream/settings workflow helper слой для Telegram Proxy page."""

from __future__ import annotations

from PyQt6.QtCore import QTimer

import telegram_proxy.settings as telegram_proxy_settings


def schedule_upstream_restart(*, page, timer, restart_callback, delay_ms: int = 800):
    if timer is None:
        timer = QTimer(page)
        timer.setSingleShot(True)
        timer.timeout.connect(restart_callback)
    timer.start(delay_ms)
    return timer


def handle_upstream_toggle(
    *,
    checked: bool,
    set_upstream_enabled,
    apply_upstream_preset_ui,
    current_index: int,
    restart_if_running,
) -> None:
    set_upstream_enabled(checked)
    apply_upstream_preset_ui(current_index)
    restart_if_running()


def handle_upstream_preset_changed(
    *,
    index: int,
    upstream_catalog,
    apply_upstream_preset_ui,
    upstream_host_edit,
    upstream_port_spin,
    upstream_user_edit,
    upstream_pass_edit,
    set_upstream_fields,
    restart_if_running,
) -> str:
    preset = upstream_catalog.preset_at(index)
    if preset is None:
        return ""

    apply_upstream_preset_ui(index)

    is_manual = upstream_catalog.is_manual(index)
    is_mtproxy = upstream_catalog.is_mtproxy(index)

    if is_manual:
        upstream_host_edit.clear()
        upstream_port_spin.blockSignals(True)
        upstream_port_spin.setValue(1080)
        upstream_port_spin.blockSignals(False)
        upstream_user_edit.clear()
        upstream_pass_edit.clear()
        set_upstream_fields("", 1080, "", "")
        restart_if_running()
        return ""

    if is_mtproxy:
        return preset.get("link", "")

    upstream_host_edit.setText(preset.get("host", ""))
    upstream_port_spin.blockSignals(True)
    upstream_port_spin.setValue(preset.get("port", 1080))
    upstream_port_spin.blockSignals(False)
    upstream_user_edit.setText(preset.get("username", ""))
    upstream_pass_edit.setText(preset.get("password", ""))
    set_upstream_fields(
        preset.get("host", ""),
        preset.get("port", 0),
        preset.get("username", ""),
        preset.get("password", ""),
    )
    restart_if_running()
    return ""


def save_upstream_fields(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
) -> None:
    telegram_proxy_settings.set_upstream_fields(
        host.strip(),
        port,
        user.strip(),
        password,
    )


def save_upstream_mode(*, checked: bool) -> None:
    telegram_proxy_settings.set_upstream_mode(checked)
