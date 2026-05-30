"""Helper-слой фоновых операций Hosts page."""

from collections.abc import Callable

from PyQt6.QtCore import QThread

import hosts.page_plans as hosts_page_plans


def start_hosts_operation(
    *,
    hosts_runtime,
    applying: bool,
    operation: str,
    payload,
    create_operation_worker_fn,
    on_operation_complete: Callable[[bool, str], None],
    on_thread_finished: Callable[[], None],
    parent,
):
    if not hosts_runtime or applying:
        return None

    worker = create_operation_worker_fn(
        hosts_runtime=hosts_runtime,
        operation=operation,
        payload=payload,
    )
    thread = QThread(parent)

    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_operation_complete)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(on_thread_finished)
    thread.finished.connect(thread.deleteLater)
    thread.start()

    return {
        "applying": True,
        "current_operation": operation,
        "worker": worker,
        "thread": thread,
    }


def reset_all_service_profiles_ui(
    *,
    service_combos: dict,
    is_fluent_combo: Callable[[object], bool],
    toggle_cls,
    get_building_state: Callable[[], bool],
    set_building_state: Callable[[bool], None],
    update_profile_visual: Callable[[str], None],
    save_user_selection_fn: Callable[[dict[str, str]], bool],
) -> dict[str, str]:
    reset_plan = hosts_page_plans.build_reset_selection_plan()
    new_selection = dict(reset_plan.new_selection)
    save_user_selection_fn(new_selection)

    was_building = get_building_state()
    set_building_state(True)
    try:
        for control in service_combos.values():
            if is_fluent_combo(control):
                control.blockSignals(True)
                control.setCurrentIndex(0)
                control.blockSignals(False)
            elif isinstance(control, toggle_cls):
                control.setChecked(False)
    finally:
        set_building_state(was_building)

    for service_name in list(service_combos.keys()):
        update_profile_visual(service_name)

    return new_selection


def complete_hosts_operation(
    *,
    current_operation: str | None,
    success: bool,
    message: str,
    hosts_path: str,
    invalidate_cache: Callable[[], None],
    update_ui: Callable[[], None],
    reset_profiles_ui: Callable[[], None],
    hide_error: Callable[[], None],
    show_error: Callable[[str], None],
):
    completion_plan = hosts_page_plans.build_operation_completion_plan(
        operation=current_operation,
        success=success,
        message=message,
        hosts_path=hosts_path,
    )

    invalidate_cache()
    update_ui()

    if completion_plan.reset_profiles:
        reset_profiles_ui()

    if completion_plan.clear_error:
        hide_error()
    else:
        show_error(completion_plan.error_message)

    return {
        "current_operation": None,
        "applying": False,
    }
