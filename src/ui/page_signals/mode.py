from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from winws_runtime.public import handle_launch_method_changed
from ui.navigation.sidebar_builder import sync_nav_visibility
from ui.navigation_pages import (
    resolve_preset_raw_editor_back_page_for_method,
    resolve_preset_raw_editor_root_page_for_method,
    resolve_profile_setup_root_page_for_method,
    resolve_zapret1_navigation_pages,
    resolve_zapret2_navigation_pages,
)
from ui.orchestra_runtime_actions import on_clear_learned_requested
from ui.page_contracts import PageSignalName
from ui.page_names import PageName
from ui.profile_setup_workflow import (
    on_open_profile_setup,
    on_profile_setup_changed,
)
from ui.workflows.mode import (
    open_preset_raw_editor_for_method,
    redirect_to_preset_setup_page_for_method,
    show_active_mode_control_page,
)
from ui.window_display_state import on_profile_ui_mode_changed_in_store

from .helpers import (
    connect_page_signal_if_present,
    connect_show_page_signal_if_present,
)


def _show_active_mode_control_page(window) -> None:
    show_active_mode_control_page(window, allow_internal=False)


def _open_preset_raw_editor(window, method: str, preset_name: str) -> None:
    open_preset_raw_editor_for_method(window, method, preset_name, allow_internal=True)


def _connect_control_page_entries(window, page_name: PageName, page: QWidget, pages, method: str) -> None:
    # Control page держит два соседних входа:
    # "Мои пресеты" -> выбор/активация/raw preset;
    # "Настройка preset-а" -> profiles выбранного preset-а.
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.navigate_to_presets",
        page,
        PageSignalName.NAVIGATE_TO_PRESETS,
        pages.user_presets_page,
        allow_internal=True,
    )
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.navigate_to_preset_setup",
        page,
        PageSignalName.NAVIGATE_TO_PRESET_SETUP,
        pages.preset_setup_page,
        allow_internal=True,
    )
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.navigate_to_blobs",
        page,
        PageSignalName.NAVIGATE_TO_BLOBS,
        PageName.BLOBS,
        allow_internal=True,
    )
    if method == ZAPRET2_MODE:
        connect_page_signal_if_present(
            window,
            f"{page_name.name}.profile_ui_mode_changed",
            page,
            PageSignalName.PROFILE_UI_MODE_CHANGED,
            lambda mode, w=window: on_profile_ui_mode_changed_in_store(w.ui_state_store, mode),
        )


def _connect_preset_setup_page(window, page_name: PageName, page: QWidget, pages, method: str) -> None:
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.back_to_control",
        page,
        PageSignalName.BACK_CLICKED,
        pages.control_page,
        allow_internal=True,
    )
    connect_page_signal_if_present(
        window,
        f"{page_name.name}.open_profile_setup",
        page,
        PageSignalName.OPEN_PROFILE_SETUP,
        lambda profile_key, w=window, m=method: on_open_profile_setup(w, m, profile_key),
    )


def _connect_user_presets_page(window, page_name: PageName, page: QWidget, pages, method: str) -> None:
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.back_to_control",
        page,
        PageSignalName.BACK_CLICKED,
        pages.control_page,
        allow_internal=True,
    )
    # "Мои пресеты" открывают raw preset. Это отдельная ветка от настройки profiles.
    connect_page_signal_if_present(
        window,
        f"{page_name.name}.preset_open_requested",
        page,
        PageSignalName.PRESET_OPEN_REQUESTED,
        lambda preset_name, w=window, m=method: _open_preset_raw_editor(w, m, preset_name),
    )


def _connect_preset_raw_editor_page(window, page_name: PageName, page: QWidget, method: str) -> None:
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.back_clicked",
        page,
        PageSignalName.BACK_CLICKED,
        resolve_preset_raw_editor_back_page_for_method(method),
        allow_internal=True,
    )
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.navigate_to_root",
        page,
        PageSignalName.NAVIGATE_TO_ROOT,
        resolve_preset_raw_editor_root_page_for_method(method),
    )


def _connect_profile_setup_page(window, page_name: PageName, page: QWidget, pages, method: str) -> None:
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.back_clicked",
        page,
        PageSignalName.BACK_CLICKED,
        pages.preset_setup_page,
        allow_internal=True,
    )
    connect_show_page_signal_if_present(
        window,
        f"{page_name.name}.navigate_to_root",
        page,
        PageSignalName.NAVIGATE_TO_ROOT,
        resolve_profile_setup_root_page_for_method(method),
    )
    connect_page_signal_if_present(
        window,
        f"{page_name.name}.profile_changed",
        page,
        PageSignalName.PROFILE_CHANGED,
        lambda profile_key, change_kind, w=window, m=method: on_profile_setup_changed(w, m, profile_key, change_kind),
    )


def _on_launch_method_changed(window, method: str) -> None:
    plan = handle_launch_method_changed(window, method)

    if plan.dispatch_action == "restart":
        log_text = (
            f"Метод '{method}' сохранён, дальнейший запуск передан в единый runtime pipeline"
        )
    elif plan.dispatch_action == "stop":
        log_text = (
            f"Метод '{method}' сохранён, активный DPI будет остановлен через единый runtime pipeline"
        )
    else:
        log_text = f"Метод '{method}' сохранён без немедленного запуска"

    try:
        from log.log import log


        log(log_text, "INFO")
    except Exception:
        pass

    try:
        sync_nav_visibility(window, method)
    except Exception:
        pass

    try:
        redirect_to_preset_setup_page_for_method(window, method)
    except Exception:
        pass


def connect_mode_page_signals(window, page_name: PageName, page: QWidget) -> None:
    winws1_pages = resolve_zapret1_navigation_pages()
    winws2_pages = resolve_zapret2_navigation_pages()

    if page_name == winws2_pages.control_page:
        _connect_control_page_entries(window, page_name, page, winws2_pages, ZAPRET2_MODE)
    if page_name == winws2_pages.preset_setup_page:
        _connect_preset_setup_page(window, page_name, page, winws2_pages, ZAPRET2_MODE)
    if page_name == winws2_pages.user_presets_page:
        _connect_user_presets_page(window, page_name, page, winws2_pages, ZAPRET2_MODE)
    if page_name == winws2_pages.preset_raw_editor_page:
        _connect_preset_raw_editor_page(window, page_name, page, ZAPRET2_MODE)
    if page_name == winws2_pages.profile_setup_page:
        _connect_profile_setup_page(window, page_name, page, winws2_pages, ZAPRET2_MODE)
    if page_name == PageName.BLOBS:
        connect_page_signal_if_present(
            window,
            "BLOBS.back_to_control",
            page,
            PageSignalName.BACK_CLICKED,
            lambda w=window: _show_active_mode_control_page(w),
        )

    if page_name == winws1_pages.control_page:
        _connect_control_page_entries(window, page_name, page, winws1_pages, ZAPRET1_MODE)
    if page_name == winws1_pages.preset_setup_page:
        _connect_preset_setup_page(window, page_name, page, winws1_pages, ZAPRET1_MODE)
    if page_name == winws1_pages.user_presets_page:
        _connect_user_presets_page(window, page_name, page, winws1_pages, ZAPRET1_MODE)
    if page_name == winws1_pages.preset_raw_editor_page:
        _connect_preset_raw_editor_page(window, page_name, page, ZAPRET1_MODE)
    if page_name == winws1_pages.profile_setup_page:
        _connect_profile_setup_page(window, page_name, page, winws1_pages, ZAPRET1_MODE)

    if page_name == PageName.DPI_SETTINGS:
        connect_page_signal_if_present(window, "dpi_settings.launch_method_changed", page, PageSignalName.LAUNCH_METHOD_CHANGED, lambda method, w=window: _on_launch_method_changed(w, method))

    if page_name == PageName.ORCHESTRA:
        connect_page_signal_if_present(
            window,
            "orchestra.clear_learned_requested",
            page,
            PageSignalName.CLEAR_LEARNED_REQUESTED,
            lambda w=window: on_clear_learned_requested(w),
        )


__all__ = ["connect_mode_page_signals"]
