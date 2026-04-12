from __future__ import annotations

from ui.navigation.schema import is_page_direct_open_allowed
from ui.page_names import PageName
from ui.window_adapter import ensure_window_adapter
from ui.workflows.common import (
    get_current_launch_method,
    refresh_page_if_possible,
)
from ui.workflows.direct import (
    get_strategies_context_pages,
    navigate_to_control,
    navigate_to_strategies,
    open_zapret1_preset_detail,
    open_zapret1_strategy_detail,
    open_zapret2_preset_detail,
    open_zapret2_strategy_detail,
    resolve_navigation_target_for_strategies,
    refresh_active_zapret2_user_presets_page,
    refresh_zapret1_user_presets_page,
    show_active_zapret2_control_page,
    show_active_zapret2_user_presets_page,
    show_zapret1_user_presets_page,
)


class WindowUiWorkflows:
    """UI-side сценарии переходов между страницами.

    Здесь живёт именно orchestration пользовательских переходов:
    detail/open/back/root/preset flow. Это не schema и не page lifecycle.
    """

    def __init__(self, window):
        self._window = window

    def _show_page(self, page_name: PageName) -> bool:
        return ensure_window_adapter(self._window).show_page(
            page_name,
            allow_internal=not is_page_direct_open_allowed(page_name),
        )

    def refresh_page_if_possible(self, page_name: PageName) -> None:
        refresh_page_if_possible(self._window, page_name)

    def _show_static_page(self, page_name: PageName) -> None:
        self._show_page(page_name)

    def open_zapret2_strategy_detail(
        self,
        target_key: str,
        *,
        remember: bool = True,
        show_page: bool = True,
    ) -> bool:
        return open_zapret2_strategy_detail(
            self._window,
            target_key,
            remember=remember,
            show_page_after_open=show_page,
            allow_internal=True,
        )

    def open_zapret1_strategy_detail(self, target_key: str) -> bool:
        return open_zapret1_strategy_detail(
            self._window,
            target_key,
            allow_internal=True,
        )

    def show_active_zapret2_user_presets_page(self) -> None:
        show_active_zapret2_user_presets_page(self._window, allow_internal=True)

    def show_zapret1_user_presets_page(self) -> None:
        show_zapret1_user_presets_page(self._window, allow_internal=True)

    def refresh_active_zapret2_user_presets_page(self) -> None:
        refresh_active_zapret2_user_presets_page(self._window, allow_internal=True)

    def refresh_zapret1_user_presets_page(self) -> None:
        refresh_zapret1_user_presets_page(self._window, allow_internal=True)

    def open_zapret2_preset_detail(self, preset_name: str) -> None:
        method = get_current_launch_method()
        open_zapret2_preset_detail(
            self._window,
            method,
            preset_name,
            allow_internal=True,
        )

    def open_zapret1_preset_detail(self, preset_name: str) -> None:
        open_zapret1_preset_detail(
            self._window,
            preset_name,
            allow_internal=True,
        )

    def redirect_to_strategies_page_for_method(self, method: str) -> None:
        current = None
        try:
            current = self._window.stackedWidget.currentWidget() if hasattr(self._window, "stackedWidget") else None
        except Exception:
            current = None

        strategies_context_pages = get_strategies_context_pages(self._window)

        if current is not None and current not in strategies_context_pages:
            return

        self._show_page(
            resolve_navigation_target_for_strategies(
                self._window,
                method,
                allow_restore_z2_detail=False,
            )
        )

    def show_autostart_page(self) -> None:
        self._show_static_page(PageName.AUTOSTART)

    def show_hosts_page(self) -> None:
        self._show_static_page(PageName.HOSTS)

    def show_servers_page(self) -> None:
        self._show_static_page(PageName.SERVERS)

    def show_active_zapret2_control_page(self) -> None:
        show_active_zapret2_control_page(self._window, allow_internal=False)

    def navigate_to_control(self) -> None:
        navigate_to_control(self._window, allow_internal=False)

    def navigate_to_strategies(self) -> None:
        navigate_to_strategies(self._window, allow_internal=False)


def ensure_ui_workflows(window) -> WindowUiWorkflows:
    workflows = getattr(window, "_ui_workflows", None)
    if workflows is None:
        workflows = WindowUiWorkflows(window)
        window._ui_workflows = workflows
    return workflows


__all__ = ["WindowUiWorkflows", "ensure_ui_workflows"]
