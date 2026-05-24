from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ui.page_warmup import warm_page
from ui.window_adapter import get_loaded_page, show_page


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
        from qfluentwidgets import MessageBox

        box = MessageBox(
            "Доступно обновление",
            f"Выпущена версия {version}. Скачать и установить сейчас?",
            self._window,
        )
        box.yesButton.setText("Скачать и установить")
        box.cancelButton.setText("Позже")
        return bool(box.exec())

    def show_page(self, page_name) -> None:
        show_page(self._window, page_name)

    def warm_page(self, page_name) -> bool:
        return bool(warm_page(self._window, page_name))

    def get_loaded_page(self, page_name):
        return get_loaded_page(self._window, page_name)


def build_post_startup_host(window) -> PostStartupHost:
    return PostStartupHost(window)


__all__ = ["PostStartupHost", "build_post_startup_host"]
