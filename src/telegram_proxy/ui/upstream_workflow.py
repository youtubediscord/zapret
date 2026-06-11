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
    upstream_catalog=None,
    request_upstream_preset_save=None,
) -> None:
    request_upstream_enabled(checked)
    apply_upstream_preset_ui(current_index)
    if not checked or upstream_catalog is None or request_upstream_preset_save is None:
        return

    preset = upstream_catalog.preset_at(current_index)
    if preset is None or upstream_catalog.is_manual(current_index) or upstream_catalog.is_mtproxy(current_index):
        return

    request_upstream_preset_save(str(preset.get("id") or "").strip())


def handle_upstream_preset_changed(
    *,
    index: int,
    upstream_catalog,
    apply_upstream_preset_ui,
    upstream_host_edit,
    upstream_port_spin,
    upstream_user_edit,
    upstream_pass_edit,
    request_upstream_preset_save,
    request_manual_upstream_save,
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
        request_manual_upstream_save("", 1080, "", "")
        return ""

    if is_mtproxy:
        return str(preset.get("id") or "").strip()

    upstream_host_edit.clear()
    upstream_port_spin.blockSignals(True)
    upstream_port_spin.setValue(1080)
    upstream_port_spin.blockSignals(False)
    upstream_user_edit.clear()
    upstream_pass_edit.clear()
    request_upstream_preset_save(str(preset.get("id") or "").strip())
    return ""
