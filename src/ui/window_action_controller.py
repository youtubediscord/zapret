from __future__ import annotations


def resolve_action_host(source):
    if source is None:
        return None

    try:
        window = source.window()
        if window is not None:
            return window
    except Exception:
        pass

    try:
        parent_app = getattr(source, "parent_app", None)
        if parent_app is not None:
            return parent_app
    except Exception:
        pass

    return source


def start_dpi(source) -> bool:
    host = resolve_action_host(source)
    if host is None:
        return False

    handler = getattr(host, "_start_requested_handler", None)
    if callable(handler):
        handler()
        return True

    controller = getattr(host, "launch_controller", None)
    if controller is not None:
        controller.start_dpi_async()
        return True

    return False


def stop_dpi(source) -> bool:
    host = resolve_action_host(source)
    if host is None:
        return False

    controller = getattr(host, "launch_controller", None)
    if controller is not None:
        controller.stop_dpi_async()
        return True

    return False


def stop_and_exit(source) -> bool:
    from log import log
    from PyQt6.QtWidgets import QApplication

    host = resolve_action_host(source)
    log("Остановка winws и закрытие программы...", "INFO")

    if host is not None:
        request_exit = getattr(host, "request_exit", None)
        if callable(request_exit):
            request_exit(stop_dpi=True)
            return True

        controller = getattr(host, "launch_controller", None)
        if controller is not None:
            try:
                host._closing_completely = True
            except Exception:
                pass
            controller.stop_and_exit_async()
            return True

    QApplication.quit()
    return True


def open_connection_test(source) -> bool:
    host = resolve_action_host(source)
    if host is None:
        return False

    handler = getattr(host, "open_connection_test", None)
    if callable(handler):
        handler()
        return True

    return False


def open_folder(source) -> bool:
    host = resolve_action_host(source)
    if host is None:
        return False

    handler = getattr(host, "open_folder", None)
    if callable(handler):
        handler()
        return True

    return False
