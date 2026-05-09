from __future__ import annotations

import os
import time

from app_notifications import advisory_notification
from log.log import log


def init_tray(app) -> None:
    started_at = time.perf_counter()
    if getattr(app, "tray_manager", None):
        log("Системный трей уже инициализирован, пропускаем", "DEBUG")
        return

    from config.build_info import APP_VERSION, CHANNEL
    from config.config import ICON_DEV_PATH, ICON_PATH
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication
    from tray import SystemTrayManager

    icon_path = ICON_DEV_PATH if CHANNEL.lower() == "dev" else ICON_PATH
    if not os.path.exists(icon_path):
        icon_path = ICON_PATH

    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)
    QApplication.instance().setWindowIcon(app_icon)

    app.tray_manager = SystemTrayManager(
        parent=app,
        icon_path=os.path.abspath(icon_path),
        app_version=APP_VERSION,
    )

    log("Системный трей инициализирован", "INFO")
    try:
        app.log_startup_metric("StartupTrayInit", f"{(time.perf_counter() - started_at) * 1000:.0f}ms")
    except Exception as exc:
        log(f"Не удалось записать startup-метрику StartupTrayInit: {exc}", "DEBUG")

    if bool(getattr(app, "_tray_launch_notification_pending", False)):
        app.window_notification_controller.notify(
            advisory_notification(
                level="info",
                title="Zapret работает в трее",
                content="Приложение запущено в фоновом режиме",
                source="startup.tray_launch",
                presentation="infobar",
                queue="immediate",
                duration=5000,
                dedupe_key="startup.tray_launch",
                tray_title="Zapret работает в трее",
                tray_content="Приложение запущено в фоновом режиме",
            )
        )
        app._tray_launch_notification_pending = False
