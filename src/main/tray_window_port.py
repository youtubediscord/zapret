from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TrayWindowPort:
    """Узкий доступ трея к главному окну."""

    _window: Any

    def set_window_icon(self, icon) -> None:
        self._window.setWindowIcon(icon)

    def create_menu(self):
        from qfluentwidgets import RoundMenu

        return RoundMenu(parent=self._window)

    def exec_popup_menu(self, menu, position) -> None:
        from ui.popup_menu import exec_popup_menu

        exec_popup_menu(
            menu,
            position,
            owner=self._window,
            monitor_global_mouse=True,
        )

    def prompt_console_command(self):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit

        return QInputDialog.getText(
            self._window,
            "Консоль",
            "Введите команду:",
            QLineEdit.EchoMode.Normal,
            "",
        )

    def is_visible(self) -> bool:
        try:
            return bool(self._window.isVisible())
        except Exception:
            return False

    def persist_geometry(self) -> None:
        try:
            from ui.window_adapter import persist_window_geometry

            persist_window_geometry(self._window)
        except Exception as exc:
            from log.log import log

            log(f"Ошибка сохранения геометрии окна: {exc}", "ERROR")

    def release_input_interaction_states(self) -> None:
        from ui.window_adapter import release_input_interaction_states

        release_input_interaction_states(self._window)

    def hide(self) -> None:
        from ui.window_adapter import hide_window

        hide_window(self._window)

    def show(self) -> None:
        from ui.window_adapter import show_window

        show_window(self._window)

    def request_exit(self, *, stop_dpi: bool) -> None:
        from ui.window_adapter import request_exit

        request_exit(self._window, stop_dpi=bool(stop_dpi))


def build_tray_window_port(window) -> TrayWindowPort:
    return TrayWindowPort(window)


__all__ = ["TrayWindowPort", "build_tray_window_port"]
