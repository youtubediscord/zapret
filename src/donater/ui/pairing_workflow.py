"""Helper-слой workflow для Premium pairing и информации об устройстве."""

from __future__ import annotations

import time
from collections.abc import Callable

from PyQt6.QtWidgets import QApplication

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
):
    snapshot = _read_pairing_snapshot(premium_feature, current_time=current_time)
    return premium_page_plans.build_pairing_autopoll_plan(
        checker_ready=bool(premium_feature.is_checker_ready()),
        storage_ready=bool(premium_feature.is_storage_ready()),
        page_visible=bool(page_visible),
        activation_in_progress=bool(activation_in_progress),
        connection_test_in_progress=bool(connection_test_in_progress),
        worker_running=bool(worker_running),
        has_device_token=bool(snapshot.get("has_device_token")),
        has_pending_pair_code=bool(snapshot.get("has_pending_pair_code")),
    )


def has_pending_pair_code(premium_feature, *, current_time: int | None = None) -> bool:
    snapshot = _read_pairing_snapshot(premium_feature, current_time=current_time)
    return bool(snapshot.get("has_pending_pair_code"))


def can_poll_pairing_status(
    *,
    premium_feature,
    page_visible: bool,
    activation_in_progress: bool,
    connection_test_in_progress: bool,
    worker_running: bool,
    current_time: int | None = None,
) -> bool:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
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
) -> None:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
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
) -> None:
    plan = build_pairing_autopoll_runtime_plan(
        premium_feature=premium_feature,
        page_visible=page_visible,
        activation_in_progress=activation_in_progress,
        connection_test_in_progress=connection_test_in_progress,
        worker_running=worker_running,
        current_time=current_time,
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


def update_device_info_labels(
    *,
    premium_feature,
    tr: Callable[[str, str], str],
    device_id_label,
    saved_key_label,
    last_check_label,
    on_error: Callable[[Exception], None] | None = None,
    current_time: int | None = None,
) -> None:
    if not premium_feature.is_checker_ready():
        return

    try:
        snapshot = premium_feature.read_device_info_snapshot(
            current_time=int(time.time()) if current_time is None else int(current_time),
        )
        if not snapshot:
            return
        plan = premium_page_plans.build_device_info_plan(
            device_id=snapshot.get("device_id"),
            device_token=snapshot.get("device_token"),
            pair_code=snapshot.get("pair_code"),
            last_check=snapshot.get("last_check"),
            token_present_text=tr("page.premium.label.device_token.present", "device token: ✅"),
            token_absent_text=tr("page.premium.label.device_token.absent", "device token: ❌"),
            pair_template_text=tr("page.premium.label.pair_code.value", "pair: {pair_code}"),
        )

        device_id_label.setText(
            tr(
                plan.device_id_text_key,
                plan.device_id_text_default,
                **plan.device_id_kwargs,
            )
        )
        saved_key_label.setText(plan.saved_key_text)
        last_check_label.setText(
            tr(
                plan.last_check_text_key,
                plan.last_check_text_default,
                **plan.last_check_kwargs,
            )
        )
    except Exception as exc:
        if on_error is not None:
            on_error(exc)


def apply_pair_code_start_ui(
    *,
    activate_btn,
    key_input,
    tr: Callable[[str, str], str],
    set_activation_status: Callable[..., None],
    stop_autopoll: Callable[[], None],
):
    plan = premium_page_plans.build_pair_code_start_plan()
    if plan.stop_autopoll:
        stop_autopoll()
    if plan.clear_key_input:
        key_input.clear()
    activate_btn.setEnabled(plan.activate_enabled)
    activate_btn.setText(
        tr(plan.activate_text_key, plan.activate_text_default)
    )
    set_activation_status(
        text=plan.activation_status_plan.text,
        text_key=plan.activation_status_plan.text_key,
        text_default=plan.activation_status_plan.text_default,
        text_kwargs=plan.activation_status_plan.text_kwargs,
    )
    return plan


def apply_pair_code_result_ui(
    result,
    *,
    activate_btn,
    key_input,
    tr: Callable[[str, str], str],
    set_activation_status: Callable[..., None],
    update_device_info: Callable[[], None],
    start_autopoll: Callable[[], None],
    stop_autopoll: Callable[[], None],
):
    plan = premium_page_plans.build_pair_code_result_plan(result)
    activate_btn.setEnabled(plan.activate_enabled)
    activate_btn.setText(tr(plan.activate_text_key, plan.activate_text_default))
    if plan.clear_key_input:
        key_input.clear()
    else:
        key_input.setText(plan.key_input_text)
    if plan.copy_to_clipboard and plan.key_input_text:
        try:
            QApplication.clipboard().setText(plan.key_input_text)
        except Exception:
            pass
    set_activation_status(
        text=plan.activation_status_plan.text,
        text_key=plan.activation_status_plan.text_key,
        text_default=plan.activation_status_plan.text_default,
        text_kwargs=plan.activation_status_plan.text_kwargs,
    )
    if plan.update_device_info:
        update_device_info()
    if plan.start_autopoll:
        start_autopoll()
    if plan.stop_autopoll:
        stop_autopoll()
    return plan


def apply_pair_code_error_ui(
    error,
    *,
    activate_btn,
    key_input,
    tr: Callable[[str, str], str],
    set_activation_status: Callable[..., None],
    update_device_info: Callable[[], None],
    stop_autopoll: Callable[[], None],
):
    plan = premium_page_plans.build_pair_code_error_plan(str(error or ""))
    if plan.clear_key_input:
        key_input.clear()
    activate_btn.setEnabled(plan.activate_enabled)
    activate_btn.setText(tr(plan.activate_text_key, plan.activate_text_default))
    set_activation_status(
        text=plan.activation_status_plan.text,
        text_key=plan.activation_status_plan.text_key,
        text_default=plan.activation_status_plan.text_default,
        text_kwargs=plan.activation_status_plan.text_kwargs,
    )
    if plan.update_device_info:
        update_device_info()
    if plan.stop_autopoll:
        stop_autopoll()
    return plan
