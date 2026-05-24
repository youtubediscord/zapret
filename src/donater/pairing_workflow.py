"""Runtime workflow для Premium pairing."""

from __future__ import annotations

import time
from collections.abc import Callable

import donater.ui.page_plans as premium_page_plans


def _read_pairing_snapshot(premium_feature, *, current_time: int | None = None):
    return premium_feature.read_pairing_snapshot(
        current_time=int(time.time()) if current_time is None else int(current_time),
    )


def build_pairing_autopoll_runtime_plan(
    *,
    premium_feature,
    page_visible: bool,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    worker_running: bool,
    current_time: int | None = None,
    pairing_snapshot: dict | None = None,
):
    checker_ready = bool(premium_feature.is_checker_ready())
    storage_ready = bool(premium_feature.is_storage_ready())
    if pairing_snapshot is not None:
        snapshot = pairing_snapshot
    elif storage_ready:
        snapshot = _read_pairing_snapshot(premium_feature, current_time=current_time)
    else:
        snapshot = {
            "has_device_token": False,
            "has_pending_pair_code": False,
        }
    return premium_page_plans.build_pairing_autopoll_plan(
        checker_ready=checker_ready,
        storage_ready=storage_ready,
        page_visible=bool(page_visible),
        activation_in_progress=bool(activation_in_progress),
        connection_test_in_progress=bool(connection_test_in_progress),
        worker_running=bool(worker_running),
        has_device_token=bool(snapshot.get("has_device_token")),
        has_pending_pair_code=bool(snapshot.get("has_pending_pair_code")),
    )


def can_poll_pairing_status(
    *,
    premium_feature,
    page_visible: bool,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    worker_running: bool,
    current_time: int | None = None,
    pairing_snapshot: dict | None = None,
) -> bool:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
        pairing_snapshot=pairing_snapshot,
    )
    return plan.can_poll


def start_pairing_status_autopoll(
    timer,
    *,
    premium_feature,
    page_visible: bool,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    worker_running: bool,
    current_time: int | None = None,
    pairing_snapshot: dict | None = None,
) -> None:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
        pairing_snapshot=pairing_snapshot,
    )
    if plan.start_timer and not timer.isActive():
        timer.start()


def stop_pairing_status_autopoll(timer) -> None:
    if timer.isActive():
        timer.stop()


def sync_pairing_status_autopoll(
    timer,
    *,
    premium_feature,
    page_visible: bool,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    worker_running: bool,
    current_time: int | None = None,
    pairing_snapshot: dict | None = None,
) -> None:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
        pairing_snapshot=pairing_snapshot,
    )
    if plan.start_timer:
        start_pairing_status_autopoll(
            timer,
            premium_feature=premium_feature,
            page_visible=page_visible,
            activation_in_progress=activation_in_progress,
            connection_test_in_progress=connection_test_in_progress,
            worker_running=worker_running,
            current_time=current_time,
            pairing_snapshot=pairing_snapshot,
        )
    if plan.stop_timer:
        stop_pairing_status_autopoll(timer)


def poll_pairing_status(
    *,
    can_poll: bool,
    stop_autopoll: Callable[[], None],
    check_status: Callable[[], None],
) -> None:
    plan = premium_page_plans.build_pairing_poll_plan(
        can_poll=bool(can_poll),
    )
    if plan.should_stop_timer:
        stop_autopoll()
        return
    if plan.should_check_status:
        check_status()
