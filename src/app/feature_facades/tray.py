from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tray_commands


@dataclass(slots=True)
class TrayFeature:
    _host: Any
    _runtime_feature: Any
    _telegram_proxy_feature: Any
    _notify: Any = None
    _log_startup_metric: Any = None
    _tray_manager: Any = None

    def configure(self, *, notify=None, log_startup_metric=None) -> None:
        if notify is not None:
            self._notify = notify
        if log_startup_metric is not None:
            self._log_startup_metric = log_startup_metric

    def init(self) -> None:
        self._init_manager()

    def _init_manager(self):
        self._tray_manager = tray_commands.init_tray(
            self._host,
            tray_feature=self,
            notify=self._notify,
            log_startup_metric=self._log_startup_metric,
            existing_manager=self._tray_manager,
        )
        return self._tray_manager

    def ensure_initialized(self) -> bool:
        return self._ensure_manager() is not None

    def is_initialized(self) -> bool:
        return self._manager() is not None

    def _ensure_manager(self):
        manager = self._manager()
        if manager is not None:
            return manager
        return self._init_manager()

    def _manager(self):
        return self._tray_manager

    def record_startup_metric(self, marker: str, details: str = "") -> None:
        if self._log_startup_metric is None:
            return
        self._log_startup_metric(marker, details)

    def install_post_startup(self) -> None:
        tray_commands.install_post_startup_tray(self._host, tray_feature=self)

    def show_notification_if_available(self, title: str, content: str) -> bool:
        return bool(
            tray_commands.show_tray_notification_if_available(
                self._host,
                tray_manager=self._manager(),
                title=title,
                content=content,
            )
        )

    def hide_icon_for_exit(self) -> None:
        tray_commands.hide_tray_icon_for_exit(self._manager())

    def cleanup(self) -> None:
        tray_commands.cleanup_tray_for_close(self._manager())
        self._tray_manager = None

    def hide_to_tray(self, *, show_hint: bool = True) -> bool:
        manager = self._ensure_manager()
        if manager is None:
            return False
        return bool(manager.hide_to_tray(show_hint=show_hint))

    def launch_state(self) -> tuple[bool, str]:
        try:
            snapshot = self._runtime_feature.snapshot()
            running = bool(snapshot.launch_running)
            phase = str(snapshot.launch_phase or "").strip().lower()
            return running, phase or ("running" if running else "stopped")
        except Exception:
            return False, "stopped"

    def telegram_proxy_label(self) -> str:
        return str(self._telegram_proxy_feature.status_label())

    def connect_telegram_proxy_status_changed(self, callback) -> None:
        self._telegram_proxy_feature.connect_status_changed(callback)

    def set_telegram_proxy_enabled(self, running: bool) -> None:
        try:
            self._telegram_proxy_feature.set_enabled(bool(running))
        except Exception:
            pass

    def toggle_telegram_proxy(self) -> None:
        self._telegram_proxy_feature.toggle_async()

    def toggle_github_api_removal(self, *, status_callback=None) -> bool:
        return bool(tray_commands.toggle_github_api_removal(status_callback=status_callback))

    def toggle_discord_restart(self, *, status_callback=None) -> None:
        tray_commands.toggle_discord_restart(self._host, status_callback=status_callback)

    def apply_window_opacity(self, value: int) -> None:
        tray_commands.apply_window_opacity(self._host, int(value))


def build_tray_feature(*, host, runtime_feature, telegram_proxy_feature) -> TrayFeature:
    return TrayFeature(
        _host=host,
        _runtime_feature=runtime_feature,
        _telegram_proxy_feature=telegram_proxy_feature,
    )
