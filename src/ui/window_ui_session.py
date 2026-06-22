from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.page_names import PageName
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


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
    nav_scroll_position: Any

    sidebar_search_widget_cls: type | None
    startup_ui_pump_counter: int = 0
    nav_search_query: str = ""
    nav_mode_visibility: dict[PageName, bool] = field(default_factory=dict)
    nav_headers: list[tuple[Any, tuple[PageName, ...], str]] = field(default_factory=list)
    nav_header_by_group: dict[str, Any] = field(default_factory=dict)
    nav_items: dict[PageName, Any] = field(default_factory=dict)
    sidebar_search_nav_widget: Any | None = None
    sidebar_search_model: Any | None = None
    sidebar_search_completer: Any | None = None
    sidebar_search_selected_row: int = -1
    sidebar_search_titlebar_attached: bool = False

    ui_language: str = "ru"
    startup_page_init_metrics: list[tuple[str, int]] = field(default_factory=list)

    preset_runtime_coordinator: Any | None = None
    preset_summary_refresh_runtime: Any | None = None
    runtime_ui_bridge: Any | None = None
    page_stack_bootstrap_complete: bool = False
    ui_bootstrap_bindings_connected: bool = False
    sidebar_search_profile_loader: Callable[[str], tuple[object, ...]] | None = None
    sidebar_search_preset_loader: Callable[[str], tuple[object, ...]] | None = None
    sidebar_expanded_save_worker_factory: Callable[..., Any] | None = None
    sidebar_expanded_save_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)
    sidebar_expanded_save_state: LatestValueWorkerState | None = None
    sidebar_expanded_save_runtime_worker: Any | None = None
    sidebar_search_runtime_cache: dict[str, tuple[float, tuple[object, ...]]] = field(default_factory=dict)


def get_window_ui_session(window) -> WindowUiSession | None:
    return getattr(window, "ui_session", None)
