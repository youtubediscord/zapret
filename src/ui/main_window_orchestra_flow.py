from __future__ import annotations

from log import log


def on_clear_learned_requested(window) -> None:
    log("Запрошена очистка данных обучения", "INFO")
    if hasattr(window, "orchestra_runner") and window.orchestra_runner:
        window.orchestra_runner.clear_learned_data()
        log("Данные обучения очищены", "INFO")
