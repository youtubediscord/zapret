from __future__ import annotations

from collections.abc import Iterator

from PyQt6.QtWidgets import QApplication

from log.log import global_logger, log
from ui.navigation.schema import iter_page_names_for_cleanup
from ui.window_ui_session import get_window_ui_session


def detach_global_error_notifier() -> None:
    try:
        if hasattr(global_logger, "set_ui_error_notifier"):
            global_logger.set_ui_error_notifier(None)
    except Exception:
        pass


def persist_window_geometry(window, *, context: str, level: str = "DEBUG") -> None:
    try:
        window.window_geometry_runtime.persist_now(force=True)
    except Exception as e:
        log(f"Ошибка сохранения геометрии окна при {context}: {e}", level)


def release_input_interaction_states(window) -> None:
    """Сбрасывает drag/resize состояния при скрытии/потере фокуса окна."""
    try:
        window.unsetCursor()
    except Exception:
        pass


def iter_loaded_pages_for_close(window) -> Iterator[tuple[object, object]]:
    # Страницы создаются лениво: при раннем закрытии список может ещё не появиться.
    session = get_window_ui_session(window)
    loaded_pages = {} if session is None else session.pages
    for page_name, page in loaded_pages.items():
        if page is None:
            continue
        yield page_name, page


def cleanup_threaded_pages_for_close(window) -> None:
    try:
        loaded_pages = list(iter_loaded_pages_for_close(window))
        page_order = iter_page_names_for_cleanup(
            page_name for page_name, _page in loaded_pages
        )
        pages_by_name = {
            page_name: page
            for page_name, page in loaded_pages
        }

        for page_name in page_order:
            page = pages_by_name.get(page_name)
            if page is None or not hasattr(page, "cleanup"):
                continue
            try:
                page.cleanup()
            except Exception as e:
                log(f"Ошибка при очистке страницы {page_name}: {e}", "DEBUG")
    except Exception as e:
        log(f"Ошибка при очистке страниц: {e}", "DEBUG")


def cleanup_process_monitor_for_close(runtime_feature) -> None:
    try:
        # Эти сервисы создаются после первого показа окна, поэтому при очень
        # раннем закрытии их может ещё не быть.
        runtime_feature.cleanup_process_monitor()
    except Exception as e:
        log(f"Ошибка остановки process monitor: {e}", "DEBUG")


def cleanup_subscription_for_close(premium_feature) -> None:
    try:
        premium_feature.cleanup_subscription()
    except Exception as e:
        log(f"Ошибка очистки subscription_manager: {e}", "DEBUG")


def cleanup_theme_for_close(window) -> None:
    try:
        theme_manager = window.visual_state.theme_manager
        if theme_manager is not None:
            theme_manager.cleanup()
            window.visual_state.theme_manager = None
    except Exception as e:
        log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")


def cleanup_visual_and_proxy_resources_for_close(window, *, telegram_proxy_feature) -> None:
    try:
        app = QApplication.instance()
        closer = getattr(app, "_zapret_global_combo_popup_closer", None) if app is not None else None
        if closer is not None and hasattr(closer, "cleanup"):
            closer.cleanup()
    except Exception:
        pass

    telegram_proxy_feature.cleanup()

    try:
        effects = window.visual_state.holiday_effects
        if effects is not None:
            effects.cleanup()
            window.visual_state.holiday_effects = None
    except Exception as e:
        log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")


def cleanup_runtime_threads_for_close(runtime_feature) -> None:
    try:
        runtime_feature.cleanup_threads()
    except Exception as e:
        log(f"Ошибка очистки DPI runtime threads: {e}", "DEBUG")
