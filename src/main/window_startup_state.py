from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WindowStartupState:
    """Состояние запуска главного окна.

    Это не business-логика приложения, а короткая память startup-сценария:
    что уже было запущено, какие startup-метрики записаны и какие отложенные
    уведомления ещё нужно показать.
    """

    dpi_autostart_initiated: bool = False
    deferred_init_started: bool = False
    post_init_ready: bool = False
    subscription_ready: bool = False
    background_init_started: bool = False
    tray_launch_notification_pending: bool = False

    ttff_logged: bool = False
    ttff_ms: int | None = None
    interactive_logged: bool = False
    interactive_ms: int | None = None
    core_ready_logged: bool = False
    core_ready_ms: int | None = None
    post_init_done_logged: bool = False
    post_init_done_ms: int | None = None
