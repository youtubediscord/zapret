from __future__ import annotations

from main.window_lifecycle_setup import attach_window_lifecycle, restore_window_geometry
from main.window_notifications_setup import attach_window_notifications
from main.window_page_deps_setup import attach_window_ui_root
from main.window_startup_setup import attach_startup_deps_to_window
from main.window_startup_signal_setup import (
    connect_window_startup_signals,
    show_initial_window_if_needed,
    start_window_deferred_init,
)


def attach_app_runtime_to_window(window, app_runtime, *, page_actions_factory) -> None:
    features = app_runtime.features
    if hasattr(window, "bind_status_message_sink"):
        window.bind_status_message_sink(app_runtime.state.ui.set_last_status_message)
    if hasattr(window, "bind_open_folder_worker_factory"):
        window.bind_open_folder_worker_factory(create_open_folder_worker)
    attach_window_lifecycle(window, features)
    attach_window_notifications(window, features)
    page_actions = page_actions_factory(window)
    startup_runtime = attach_startup_deps_to_window(window, features)
    attach_window_ui_root(
        window,
        features=features,
        state=app_runtime.state,
        page_actions=page_actions,
    )
    restore_window_geometry(window)
    connect_window_startup_signals(
        window,
        continue_startup=startup_runtime.continue_deferred_init,
    )
    show_initial_window_if_needed(window)
    start_window_deferred_init(window)


def create_open_folder_worker(*, parent=None):
    from main.commands import open_program_folder
    from main.window_action_workers import WindowOpenFolderWorker

    return WindowOpenFolderWorker(open_program_folder=open_program_folder, parent=parent)


__all__ = ["attach_app_runtime_to_window"]
