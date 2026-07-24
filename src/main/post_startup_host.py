from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PostStartupHost:
    _window: Any

    @property
    def close_state(self):
        return self._window.close_state

    @property
    def startup_state(self):
        return self._window.startup_state

    @property
    def startup_interactive_ready(self):
        return self._window.startup_interactive_ready

    @property
    def startup_post_init_ready(self):
        return self._window.startup_post_init_ready

    def is_alive(self) -> bool:
        close_state = self.close_state
        return not bool(close_state.is_exiting or close_state.closing_completely)

    def confirm_update_install(self, version: str) -> bool:
        from ui.fluent_dialog import MessageBox
        from ui.message_box_accessibility import set_message_box_button_accessibility

        body = f"Выпущена версия {version}. Скачать и установить сейчас?"
        box = MessageBox(
            "Доступно обновление",
            body,
            self._window,
        )
        box.yesButton.setText("Скачать и установить")
        box.cancelButton.setText("Позже")
        set_message_box_button_accessibility(
            box,
            yes_name="Скачать и установить обновление",
            yes_description=body,
            cancel_name="Отложить установку обновления",
            cancel_description="Закрывает диалог без установки обновления сейчас.",
        )
        return bool(box.exec())

    def show_page(self, page_name) -> None:
        from ui.window_adapter import show_page

        show_page(self._window, page_name)

    def ensure_page(self, page_name):
        from ui.window_adapter import ensure_page

        return ensure_page(self._window, page_name)

    def get_loaded_page(self, page_name):
        from ui.window_adapter import get_loaded_page

        return get_loaded_page(self._window, page_name)


def build_post_startup_host(window) -> PostStartupHost:
    return PostStartupHost(window)


__all__ = ["PostStartupHost", "build_post_startup_host"]
