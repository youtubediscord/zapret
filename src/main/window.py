from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal

from main.runtime_state import log_startup_metric as emit_startup_metric
from main.window_actions import WindowActionsMixin
from main.window_lifecycle import WindowLifecycleMixin
from main.window_startup import (
    WindowStartupMixin,
    startup_bootstrap_for,
    window_bootstrap_for,
)
from main.window_state_sync import WindowStateSyncMixin
from ui.fluent_app_window import ZapretFluentWindow
from ui.theme_subscription_manager import ThemeSubscriptionManager
from ui.window_ui_facade import MainWindowUI

if TYPE_CHECKING:
    from app_context import AppContext
    from donater.subscription_manager import SubscriptionManager
    from main.startup_coordinator import StartupCoordinator
    from winws_runtime.monitoring import ProcessMonitorManager


class LupiDPIApp(
    WindowStartupMixin,
    WindowLifecycleMixin,
    WindowActionsMixin,
    WindowStateSyncMixin,
    ZapretFluentWindow,
    MainWindowUI,
    ThemeSubscriptionManager,
):
    """Главное окно приложения — FluentWindow + навигация + подписки."""

    deferred_init_requested = pyqtSignal()
    continue_startup_requested = pyqtSignal()
    finalize_ui_bootstrap_requested = pyqtSignal()
    startup_interactive_ready = pyqtSignal(str)
    startup_post_init_ready = pyqtSignal(str)
    runner_failure_requested = pyqtSignal(object)
    active_preset_content_changed_requested = pyqtSignal(str)

    process_monitor_manager: "ProcessMonitorManager"
    subscription_manager: "SubscriptionManager"
    startup_coordinator: "StartupCoordinator"

    def log_startup_metric(self, marker: str, details: str = "") -> None:
        emit_startup_metric(marker, details)


def window_bootstrap(*, start_in_tray: bool) -> tuple["AppContext", "LupiDPIApp"]:
    return window_bootstrap_for(LupiDPIApp, start_in_tray=start_in_tray)


def startup_bootstrap(window: "LupiDPIApp") -> None:
    startup_bootstrap_for(window)


__all__ = ["LupiDPIApp", "window_bootstrap", "startup_bootstrap"]
