"""Upstream/settings workflow helper слой для Telegram Proxy page."""

from __future__ import annotations

from PyQt6.QtCore import QTimer


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
    request_upstream_enabled,
    apply_upstream_preset_ui,
    current_index: int,
) -> None:
    request_upstream_enabled(checked)
    apply_upstream_preset_ui(current_index)


def handle_upstream_preset_changed(
    *,
    index: int,
    upstream_catalog,
    apply_upstream_preset_ui,
    upstream_host_edit,
    upstream_port_spin,
    upstream_user_edit,
    upstream_pass_edit,
    request_upstream_fields_save,
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
        request_upstream_fields_save("", 1080, "", "")
        return ""

    if is_mtproxy:
        return preset.get("link", "")

    upstream_host_edit.setText(preset.get("host", ""))
    upstream_port_spin.blockSignals(True)
    upstream_port_spin.setValue(preset.get("port", 1080))
    upstream_port_spin.blockSignals(False)
    upstream_user_edit.setText(preset.get("username", ""))
    upstream_pass_edit.setText(preset.get("password", ""))
    request_upstream_fields_save(
        preset.get("host", ""),
        preset.get("port", 0),
        preset.get("username", ""),
        preset.get("password", ""),
    )
    return ""
