from __future__ import annotations

from app_notifications import advisory_notification, notification_action
from log.log import log

from ui.page_method_dispatch import (
    show_active_strategy_page_loading,
    show_active_strategy_page_success,
)


class RuntimeUiBridge:
    """Единый runtime -> UI bridge без знания runtime-кода о main_window."""

    def __init__(self, window):
        self._window = window

    def show_active_strategy_page_loading(self) -> bool:
        return show_active_strategy_page_loading(self._window)

    def show_active_strategy_page_success(self) -> bool:
        return show_active_strategy_page_success(self._window)

    def show_launch_error(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        try:
            while text.startswith(("❌", "⚠️", "⚠")):
                text = text[1:].strip()
        except Exception:
            pass
        if not text:
            text = "Не удалось запустить DPI"

        try:
            notification_controller = getattr(self._window, "window_notification_controller", None)
            if notification_controller is not None:
                auto_fix_action = None
                if text.startswith("[AUTOFIX:"):
                    end_idx = text.find("]")
                    if end_idx > 0:
                        auto_fix_action = text[9:end_idx]
                        text = text[end_idx + 1 :].strip()

                buttons = []
                duration = 10000
                if auto_fix_action:
                    buttons.append(notification_action("autofix", "Исправить", value=auto_fix_action))
                    duration = -1

                notification_controller.notify(
                    advisory_notification(
                        level="error",
                        title="Ошибка",
                        content=text,
                        source="launch.dpi_error",
                        presentation="infobar",
                        queue="immediate",
                        duration=duration,
                        buttons=buttons,
                        dedupe_key=f"launch.dpi_error:{' '.join(text.split()).lower()}",
                    )
                )
        except Exception as e:
            log(f"Не удалось показать InfoBar ошибки запуска: {e}", "DEBUG")

    def show_launch_warning(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        try:
            while text.startswith(("⚠️", "⚠")):
                text = text[1:].strip()
        except Exception:
            pass
        if not text:
            return

        try:
            notification_controller = getattr(self._window, "window_notification_controller", None)
            if notification_controller is not None:
                notification_controller.notify(
                    advisory_notification(
                        level="warning",
                        title="Предупреждение",
                        content=text,
                        source="launch.dpi_warning",
                        presentation="infobar",
                        queue="immediate",
                        duration=9000,
                        dedupe_key=f"launch.dpi_warning:{' '.join(text.split()).lower()}",
                    )
                )
        except Exception as e:
            log(f"Не удалось показать InfoBar предупреждения запуска: {e}", "DEBUG")


def ensure_runtime_ui_bridge(window) -> RuntimeUiBridge:
    bridge = getattr(window, "runtime_ui_bridge", None)
    if bridge is None:
        bridge = RuntimeUiBridge(window)
        window.runtime_ui_bridge = bridge
    return bridge


__all__ = ["RuntimeUiBridge", "ensure_runtime_ui_bridge"]
