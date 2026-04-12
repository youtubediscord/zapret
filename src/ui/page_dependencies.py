from __future__ import annotations


INJECTABLE_PAGE_ATTRS: tuple[str, ...] = (
    "app_context",
    "app_runtime_state",
    "launch_runtime_service",
    "launch_runtime_api",
    "launch_controller",
    "process_monitor",
    "set_status",
    "ui_state_store",
    "window_notification_controller",
    "orchestra_runner",
)


def inject_page_dependencies(page, window) -> None:
    for attr_name in INJECTABLE_PAGE_ATTRS:
        try:
            current_value = getattr(page, attr_name, None)
        except Exception:
            current_value = None
        if current_value is not None:
            continue

        try:
            window_value = getattr(window, attr_name, None)
        except Exception:
            window_value = None
        if window_value is None:
            continue

        try:
            setattr(page, attr_name, window_value)
        except Exception:
            pass


def resolve_page_dependency(page, attr_name: str, *, parent=None):
    owners = []
    if page is not None:
        owners.append(page)

    if parent is not None:
        owners.append(parent)

    try:
        page_parent = page.parent() if page is not None else None
    except Exception:
        page_parent = None
    if page_parent is not None and page_parent not in owners:
        owners.append(page_parent)

    try:
        page_window = page.window() if page is not None else None
    except Exception:
        page_window = None
    if page_window is not None and page_window not in owners:
        owners.append(page_window)

    for owner in owners:
        try:
            value = getattr(owner, attr_name, None)
        except Exception:
            value = None
        if value is not None:
            return value
    return None


def require_page_dependency(page, attr_name: str, *, parent=None, error_message: str | None = None):
    value = resolve_page_dependency(page, attr_name, parent=parent)
    if value is not None:
        return value
    raise RuntimeError(error_message or f"{attr_name} is required for page")


def require_page_app_context(page, *, parent=None, error_message: str | None = None):
    return require_page_dependency(
        page,
        "app_context",
        parent=parent,
        error_message=error_message or "AppContext is required for page",
    )


def resolve_page_app_runtime_state(page, *, parent=None):
    return resolve_page_dependency(page, "app_runtime_state", parent=parent)


def resolve_page_orchestra_runner(page, *, parent=None):
    return resolve_page_dependency(page, "orchestra_runner", parent=parent)


__all__ = [
    "INJECTABLE_PAGE_ATTRS",
    "inject_page_dependencies",
    "require_page_app_context",
    "require_page_dependency",
    "resolve_page_app_runtime_state",
    "resolve_page_dependency",
    "resolve_page_orchestra_runner",
]
