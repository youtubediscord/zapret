"""Helper-слой watcher / refresh orchestration для каталога Hosts page."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QTimer

import hosts.page_plans as hosts_page_plans


def ensure_catalog_watcher(
    *,
    page,
    timer,
    interval_ms: int,
    refresh_callback: Callable[[str], None],
):
    if timer is None:
        timer = QTimer(page)
        timer.setInterval(interval_ms)
        timer.timeout.connect(lambda: refresh_callback("watcher"))
    if not timer.isActive():
        timer.start()
    return timer


def reconcile_catalog_after_hidden_refresh(
    *,
    catalog_dirty: bool,
    services_layout_exists: bool,
    rebuild_services_selectors: Callable[[], None],
    invalidate_cache: Callable[[], None],
) -> bool:
    if not catalog_dirty:
        return False
    if services_layout_exists:
        rebuild_services_selectors()
    invalidate_cache()
    return True


def refresh_catalog_if_needed(
    *,
    current_signature,
    trigger: str,
    services_layout_exists: bool,
    page_visible: bool,
    get_catalog_signature_fn: Callable[[], object],
    invalidate_catalog_cache: Callable[[], None],
    rebuild_services_selectors: Callable[[], None],
    log_info: Callable[[str], None],
):
    sig = get_catalog_signature_fn()
    refresh_plan = hosts_page_plans.build_catalog_refresh_plan(
        current_signature=current_signature,
        new_signature=sig,
        trigger=trigger,
        services_layout_exists=services_layout_exists,
    )

    if not refresh_plan.changed:
        return {
            "changed": False,
            "catalog_dirty": False,
            "catalog_sig": current_signature,
        }

    if refresh_plan.invalidate_cache:
        invalidate_catalog_cache()

    if not page_visible:
        return {
            "changed": True,
            "catalog_dirty": True,
            "catalog_sig": refresh_plan.new_signature,
        }

    if not refresh_plan.should_rebuild:
        return {
            "changed": True,
            "catalog_dirty": False,
            "catalog_sig": refresh_plan.new_signature,
        }

    if refresh_plan.should_log:
        log_info(refresh_plan.log_message)

    rebuild_services_selectors()
    return {
        "changed": True,
        "catalog_dirty": False,
        "catalog_sig": refresh_plan.new_signature,
    }


def rebuild_services_runtime_state(
    *,
    get_catalog_signature_fn: Callable[[], object],
    clear_layout: Callable[[], None],
    build_services_selectors: Callable[[], None],
):
    clear_layout()
    build_services_selectors()
    return get_catalog_signature_fn()
