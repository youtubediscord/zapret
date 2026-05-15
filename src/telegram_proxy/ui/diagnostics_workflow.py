"""Diagnostics workflow helper слой для Telegram Proxy page."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QTimer


def start_diagnostics(
    *,
    page,
    cleanup_in_progress: bool,
    btn_run_diag,
    diag_edit,
    existing_poll_timer,
    proxy_port: int,
    telegram_proxy_feature,
    publish_diag_result,
    set_diag_result,
    set_thread_done,
    poll_diag_callback,
):
    if cleanup_in_progress:
        return None

    plan = telegram_proxy_feature.build_diagnostics_start_plan()
    btn_run_diag.setEnabled(plan.button_enabled)
    btn_run_diag.setText(plan.button_text)
    diag_edit.clear()
    diag_edit.appendPlainText(plan.initial_text)

    set_diag_result(None)
    set_thread_done(False)

    def _run_diag_tests():
        result_text = telegram_proxy_feature.run_diagnostics(
            proxy_port=proxy_port,
            progress_callback=publish_diag_result,
        )
        set_diag_result(result_text)
        set_thread_done(True)

    thread = threading.Thread(target=_run_diag_tests, daemon=True)
    thread.start()

    poll_timer = existing_poll_timer
    if poll_timer is not None:
        poll_timer.stop()
        poll_timer.deleteLater()
    poll_timer = QTimer(page)
    poll_timer.timeout.connect(poll_diag_callback)
    poll_timer.start(plan.poll_interval_ms)

    return poll_timer


def poll_diagnostics(
    *,
    cleanup_in_progress: bool,
    diag_poll_timer,
    diag_result,
    diag_thread_done: bool,
    telegram_proxy_feature,
    update_diag,
    finish_diag,
):
    if cleanup_in_progress:
        if diag_poll_timer is not None:
            diag_poll_timer.stop()
        return

    plan = telegram_proxy_feature.build_diagnostics_poll_plan(
        result_text=diag_result,
        thread_done=diag_thread_done,
    )
    if plan.updated_text is not None:
        update_diag(plan.updated_text)
    if plan.should_stop_timer and diag_poll_timer is not None:
        diag_poll_timer.stop()
    if plan.should_finish:
        finish_diag()


def finish_diagnostics(*, btn_run_diag, telegram_proxy_feature) -> None:
    plan = telegram_proxy_feature.build_diagnostics_finish_plan()
    btn_run_diag.setEnabled(plan.button_enabled)
    btn_run_diag.setText(plan.button_text)
