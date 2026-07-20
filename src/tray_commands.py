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


def get_discord_restart_enabled(default: bool = True) -> bool:
    from discord.discord_restart import get_discord_restart_setting

    return bool(get_discord_restart_setting(default=default))


def set_discord_restart_enabled(enabled: bool) -> bool:
    from discord.discord_restart import set_discord_restart_setting

    return bool(set_discord_restart_setting(bool(enabled)))


def apply_window_opacity(*, set_window_opacity, value: int) -> None:
    normalized_value = int(value)

    try:
        set_window_opacity(normalized_value)
    except Exception:
        pass


def resolve_tray_icon_path() -> str:
    from app.app_icon_resources import resolve_existing_app_icon_path

    return resolve_existing_app_icon_path()


def init_tray(
    *,
    window_port: Any,
    icon_path: str,
    app_version: str,
    tray_manager_factory,
    startup_state,
    tray_feature: Any,
    notify,
    log_startup_metric,
    existing_manager=None,
) -> Any:
    started_at = time.perf_counter()
    if existing_manager is not None:
        log("Системный трей уже инициализирован, пропускаем", "DEBUG")
        return existing_manager

    tray_manager = tray_manager_factory(
        window_port=window_port,
        icon_path=os.path.abspath(str(icon_path or "")),
        app_version=str(app_version or ""),
        tray_feature=tray_feature,
    )

    log("Системный трей инициализирован", "INFO")
    try:
        log_startup_metric("StartupTrayInit", f"{(time.perf_counter() - started_at) * 1000:.0f}ms")
    except Exception as exc:
        log(f"Не удалось записать startup-метрику StartupTrayInit: {exc}", "DEBUG")

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


def show_tray_notification_if_available(*, tray_manager, title: str, content: str) -> bool:
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


def install_post_startup_tray(
    *,
    startup_state,
    close_state,
    start_in_tray: bool,
    startup_post_init_ready,
    tray_feature: Any,
) -> None:
    from main.post_startup_gate import bind_startup_gate
    from main.post_startup_threading import schedule_after

    if bool(start_in_tray):
        return

    def _is_alive() -> bool:
        return not bool(close_state.is_exiting or close_state.closing_completely)

    def _start_tray() -> None:
        if not _is_alive():
            return
        if tray_feature.is_initialized():
            return

        try:
            tray_feature.init()
        except Exception as exc:
            log(f"Не удалось создать системный трей после запуска: {exc}", "WARNING")

    def _schedule_tray_startup() -> None:
        if not _is_alive():
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
            lambda: _is_alive() and _start_tray(),
        )

    bind_startup_gate(
        startup_post_init_ready,
        _schedule_tray_startup,
        is_ready=lambda: bool(startup_state.post_init_ready),
    )
