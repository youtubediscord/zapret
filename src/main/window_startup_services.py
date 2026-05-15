from __future__ import annotations

import time

from log.log import log


def init_theme_manager(app) -> None:
    started_at = time.perf_counter()

    from PyQt6.QtWidgets import QApplication
    from ui.theme import ThemeManager

    app.visual_state.theme_manager = ThemeManager(
        app=QApplication.instance(),
        widget=app,
    )

    current_theme = app.visual_state.theme_manager.current_theme
    log(f"🎨 Тема инициализирована: '{current_theme}'", "DEBUG")

    # qfluentwidgets управляет темой сам. Старый qt-material CSS здесь не нужен:
    # он может оставить тёмные цвета текста после переключения на светлую тему.
    log("⏭️ Применение CSS пропущено — qfluentwidgets управляет стилями нативно", "DEBUG")

    log(f"✅ Theme manager: {(time.perf_counter() - started_at) * 1000:.0f}ms (CSS в фоне)", "DEBUG")
