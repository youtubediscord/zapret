from __future__ import annotations

import os
import time
from typing import Any

from app_notifications import advisory_notification
from log.log import log


def toggle_github_api_removal(*, status_callback=None) -> bool:
    """Переключает флаг удаления api.github.com из hosts при запуске."""
    from settings.store import get_remove_github_api, set_remove_github_api

    try:
        current_state = bool(get_remove_github_api())
        new_state = not current_state

        if set_remove_github_api(new_state):
            state_text = "включено" if new_state else "отключено"
            message = f"Удаление api.github.com из hosts {state_text}"
            log(message, "INFO")
            if status_callback:
                status_callback(message)
            return True

        error_message = "Ошибка при сохранении настройки удаления GitHub API"
        log(error_message, "❌ ERROR")
        if status_callback:
            status_callback(error_message)
        return False
    except Exception as exc:
        error_message = f"Ошибка при переключении удаления GitHub API: {exc}"
        log(error_message, "❌ ERROR")
        if status_callback:
            status_callback(error_message)
        return False


def toggle_discord_restart(host: Any, *, status_callback=None) -> None:
    from discord.discord_restart import toggle_discord_restart as _toggle_discord_restart

    _toggle_discord_restart(host, status_callback=status_callback)


def apply_window_opacity(host: Any, value: int) -> None:
    from settings.store import set_window_opacity

    normalized_value = int(value)
    try:
        set_window_opacity(normalized_value)
    except Exception:
        pass

    try:
        host.set_window_opacity(normalized_value)
    except Exception:
        pass


def init_tray(
    host: Any,
    *,
    tray_feature: Any,
    notify,
    log_startup_metric,
    existing_manager=None,
) -> Any:
    started_at = time.perf_counter()
    if existing_manager is not None:
        log("Системный трей уже инициализирован, пропускаем", "DEBUG")
        return existing_manager

    from config.build_info import APP_VERSION, CHANNEL
    from config.config import ICON_DEV_PATH, ICON_PATH
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication
    from tray import SystemTrayManager

    icon_path = ICON_DEV_PATH if CHANNEL.lower() == "dev" else ICON_PATH
    if not os.path.exists(icon_path):
        icon_path = ICON_PATH

    app_icon = QIcon(icon_path)
    host.setWindowIcon(app_icon)
    QApplication.instance().setWindowIcon(app_icon)

    tray_manager = SystemTrayManager(
        parent=host,
        icon_path=os.path.abspath(icon_path),
        app_version=APP_VERSION,
        tray_feature=tray_feature,
    )

    log("Системный трей инициализирован", "INFO")
    try:
        log_startup_metric("StartupTrayInit", f"{(time.perf_counter() - started_at) * 1000:.0f}ms")
    except Exception as exc:
        log(f"Не удалось записать startup-метрику StartupTrayInit: {exc}", "DEBUG")

    startup_state = host.startup_state
    if bool(startup_state.tray_launch_notification_pending):
        notify(
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
        startup_state.tray_launch_notification_pending = False

    return tray_manager


def show_tray_notification_if_available(host: Any, tray_manager, title: str, content: str) -> bool:
    _ = host
    if tray_manager is None:
        return False
    tray_manager.show_notification(title, content)
    return True


def hide_tray_icon_for_exit(tray_manager) -> None:
    try:
        if tray_manager is not None:
            tray_manager.hide_icon()
    except Exception:
        pass


def cleanup_tray_for_close(tray_manager) -> None:
    try:
        if tray_manager is not None:
            tray_manager.cleanup()
    except Exception as exc:
        log(f"Ошибка очистки системного трея: {exc}", "DEBUG")


def install_post_startup_tray(host: Any, *, tray_feature: Any) -> None:
    from main.post_startup_gate import bind_startup_gate, is_window_alive
    from main.post_startup_threading import schedule_after

    if bool(host.start_in_tray):
        return

    def _start_tray() -> None:
        if not is_window_alive(host):
            return
        if tray_feature.is_initialized():
            return

        try:
            tray_feature.init()
        except Exception as exc:
            log(f"Не удалось создать системный трей после запуска: {exc}", "WARNING")

    def _schedule_tray_startup() -> None:
        if not is_window_alive(host):
            return

        delay_ms = 1500
        log(f"Системный трей отложен на {delay_ms}ms после post-init", "DEBUG")
        try:
            tray_feature.record_startup_metric(
                "StartupPostInitTrayQueued",
                f"{delay_ms}ms after post-init",
            )
        except Exception as exc:
            log(f"Не удалось записать startup-метрику StartupPostInitTrayQueued: {exc}", "DEBUG")

        schedule_after(
            delay_ms,
            lambda: is_window_alive(host) and _start_tray(),
        )

    bind_startup_gate(
        host.startup_post_init_ready,
        _schedule_tray_startup,
        is_ready=lambda: bool(host.startup_state.post_init_ready),
    )
