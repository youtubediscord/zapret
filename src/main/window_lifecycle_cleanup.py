from __future__ import annotations

from collections.abc import Iterator

from PyQt6.QtWidgets import QApplication

from log.log import global_logger, log
from ui.navigation.schema import iter_page_names_for_cleanup


def detach_global_error_notifier() -> None:
    try:
        if hasattr(global_logger, "set_ui_error_notifier"):
            global_logger.set_ui_error_notifier(None)
    except Exception:
        pass


def persist_window_geometry(window, *, context: str, level: str = "DEBUG") -> None:
    try:
        geometry_controller = getattr(window, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.persist_now(force=True)
    except Exception as e:
        log(f"Ошибка сохранения геометрии окна при {context}: {e}", level)


def release_input_interaction_states(window) -> None:
    """Сбрасывает drag/resize состояния при скрытии/потере фокуса окна."""
    try:
        if bool(getattr(window, "_is_resizing", False)) and hasattr(window, "_end_resize"):
            window._end_resize()
        else:
            window._is_resizing = False
            window._resize_edge = None
            window._resize_start_pos = None
            window._resize_start_geometry = None
            window.unsetCursor()
    except Exception:
        pass

    try:
        window._is_dragging = False
        window._drag_start_pos = None
        window._drag_window_pos = None
    except Exception:
        pass

    try:
        title_bar = getattr(window, "title_bar", None)
        if title_bar is not None:
            title_bar._is_moving = False
            title_bar._is_system_moving = False
            title_bar._drag_pos = None
            title_bar._window_pos = None
    except Exception:
        pass


def iter_loaded_pages_for_close(window) -> Iterator[tuple[object, object]]:
    loaded_pages = getattr(window, "pages", {}) or {}
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


def cleanup_support_managers_for_close(window) -> None:
    try:
        process_monitor_manager = getattr(window, "process_monitor_manager", None)
        if process_monitor_manager is not None:
            process_monitor_manager.stop_monitoring()
    except Exception as e:
        log(f"Ошибка остановки process_monitor_manager: {e}", "DEBUG")

    try:
        subscription_manager = getattr(window, "subscription_manager", None)
        if subscription_manager is not None:
            subscription_manager.cleanup()
    except Exception as e:
        log(f"Ошибка очистки subscription_manager: {e}", "DEBUG")

    try:
        dns_ui_manager = getattr(window, "dns_ui_manager", None)
        if dns_ui_manager is not None:
            dns_ui_manager.cleanup()
    except Exception as e:
        log(f"Ошибка при очистке dns_ui_manager: {e}", "DEBUG")

    try:
        theme_manager = getattr(window, "theme_manager", None)
        if theme_manager is not None:
            theme_manager.cleanup()
    except Exception as e:
        log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")


def cleanup_visual_and_proxy_resources_for_close(window) -> None:
    try:
        app = QApplication.instance()
        closer = getattr(app, "_zapret_global_combo_popup_closer", None) if app is not None else None
        if closer is not None and hasattr(closer, "cleanup"):
            closer.cleanup()
    except Exception:
        pass

    try:
        from telegram_proxy.ui.page import _get_proxy_manager

        _get_proxy_manager().cleanup()
    except Exception:
        pass

    try:
        effects = getattr(window, "_holiday_effects", None)
        if effects is not None:
            effects.cleanup()
            window._holiday_effects = None
    except Exception as e:
        log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")


def cleanup_runtime_threads_for_close(window) -> None:
    try:
        launch_controller = getattr(window, "launch_controller", None)
        if launch_controller is not None:
            launch_controller.cleanup_threads()
    except Exception as e:
        log(f"Ошибка очистки DPI controller threads: {e}", "DEBUG")

    try:
        if hasattr(window, "_dpi_start_thread") and window._dpi_start_thread:
            try:
                if window._dpi_start_thread.isRunning():
                    window._dpi_start_thread.quit()
                    window._dpi_start_thread.wait(1000)
            except RuntimeError:
                pass

        if hasattr(window, "_dpi_stop_thread") and window._dpi_stop_thread:
            try:
                if window._dpi_stop_thread.isRunning():
                    window._dpi_stop_thread.quit()
                    window._dpi_stop_thread.wait(1000)
            except RuntimeError:
                pass
    except Exception as e:
        log(f"Ошибка при очистке потоков: {e}", "❌ ERROR")


def cleanup_tray_for_close(window) -> None:
    try:
        tray_manager = getattr(window, "tray_manager", None)
        if tray_manager is not None:
            tray_manager.cleanup()
            window.tray_manager = None
    except Exception as e:
        log(f"Ошибка очистки системного трея: {e}", "DEBUG")


def hide_tray_icon_for_exit(window) -> None:
    try:
        if hasattr(window, "tray_manager") and window.tray_manager:
            window.tray_manager.hide_icon()
    except Exception:
        pass
