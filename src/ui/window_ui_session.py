from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ui.page_names import PageName


@dataclass
class WindowUiSession:
    """Временное состояние UI главного окна.

    Здесь живут страницы, навигация и поиск. Это не бизнес-логика приложения.
    """

    page_factory: Any
    page_host: Any
    pages: dict[PageName, Any]
    page_class_specs: dict[PageName, Any]

    nav_icons: dict[PageName, Any]
    nav_labels: dict[PageName, str]
    default_nav_icon: Any
    has_fluent_nav: bool
    nav_scroll_position: Any

    sidebar_search_widget_cls: type | None
    lazy_signal_connections: set[str] = field(default_factory=set)
    startup_ui_pump_counter: int = 0
    nav_search_query: str = ""
    nav_mode_visibility: dict[PageName, bool] = field(default_factory=dict)
    nav_headers: list[tuple[Any, tuple[PageName, ...], str]] = field(default_factory=list)
    nav_header_by_group: dict[str, Any] = field(default_factory=dict)
    nav_items: dict[PageName, Any] = field(default_factory=dict)
    sidebar_search_nav_widget: Any | None = None
    sidebar_search_model: Any | None = None
    sidebar_search_completer: Any | None = None
    sidebar_search_titlebar_attached: bool = False

    ui_language: str = "ru"
    startup_page_init_metrics: list[tuple[str, int]] = field(default_factory=list)


def get_window_ui_session(window) -> WindowUiSession | None:
    return getattr(window, "ui_session", None)
