from __future__ import annotations

from ui.navigation.schema import is_page_direct_open_allowed
from ui.navigation_targets import (
    resolve_control_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.page_names import PageName
from ui.workflows.common import (
    get_current_launch_method,
    refresh_or_show_page_after_refresh_if_possible,
    refresh_page_if_possible,
    show_page,
)
from ui.workflows.direct import (
    get_strategies_context_pages,
    open_zapret1_preset_detail,
    open_zapret1_strategy_detail,
    open_zapret2_preset_detail,
    open_zapret2_strategy_detail,
    resolve_navigation_target_for_strategies,
    resolve_zapret2_user_presets_page,
)


class WindowUiWorkflows:
    """UI-side сценарии переходов между страницами.

    Здесь живёт именно orchestration пользовательских переходов:
    detail/open/back/root/preset flow. Это не schema и не page lifecycle.
    """

    def __init__(self, window):
        self._window = window

    def _show_page(self, page_name: PageName) -> bool:
        return show_page(
            self._window,
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
        method = get_current_launch_method()
        refresh_or_show_page_after_refresh_if_possible(
            self._window,
            resolve_zapret2_user_presets_page(method),
            show_page_after_refresh=True,
            allow_internal=True,
        )

    def show_zapret1_user_presets_page(self) -> None:
        refresh_or_show_page_after_refresh_if_possible(
            self._window,
            resolve_zapret1_navigation_pages().user_presets_page,
            show_page_after_refresh=True,
            allow_internal=True,
        )

    def refresh_active_zapret2_user_presets_page(self) -> None:
        method = get_current_launch_method()
        refresh_or_show_page_after_refresh_if_possible(
            self._window,
            resolve_zapret2_user_presets_page(method),
            show_page_after_refresh=False,
            allow_internal=True,
        )

    def refresh_zapret1_user_presets_page(self) -> None:
        refresh_or_show_page_after_refresh_if_possible(
            self._window,
            resolve_zapret1_navigation_pages().user_presets_page,
            show_page_after_refresh=False,
            allow_internal=True,
        )

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
        method = get_current_launch_method(default="direct_zapret2")
        self._show_page(resolve_zapret2_navigation_pages(method).control_page)

    def navigate_to_control(self) -> None:
        method = get_current_launch_method()
        self._show_page(resolve_control_page_for_method(method))

    def navigate_to_strategies(self) -> None:
        method = get_current_launch_method(default="direct_zapret2")
        target_page = resolve_navigation_target_for_strategies(
            self._window,
            method,
            allow_restore_z2_detail=True,
        )
        self._show_page(target_page)


def ensure_ui_workflows(window) -> WindowUiWorkflows:
    workflows = getattr(window, "_ui_workflows", None)
    if workflows is None:
        workflows = WindowUiWorkflows(window)
        window._ui_workflows = workflows
    return workflows


__all__ = ["WindowUiWorkflows", "ensure_ui_workflows"]
