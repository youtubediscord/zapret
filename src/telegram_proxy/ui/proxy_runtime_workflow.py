"""Proxy lifecycle/runtime helper слой для Telegram Proxy page."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QMetaObject, Qt as QtNS

import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime
import telegram_proxy.settings as telegram_proxy_settings


def handle_toggle_proxy(
    *,
    manager,
    restarting: bool,
    starting: bool,
    set_restarting,
    stop_proxy,
    start_proxy,
) -> None:
    plan = telegram_proxy_page_runtime.build_toggle_action_plan(
        running=bool(manager.is_running),
        restarting=bool(restarting),
        starting=bool(starting),
    )
    if plan.action == "cancel_restart":
        set_restarting(False)
        manager.status_changed.emit(False)
        if plan.persist_enabled is not None:
            telegram_proxy_settings.set_proxy_enabled(plan.persist_enabled)
        return
    if plan.action == "ignore":
        return
    if plan.action == "stop":
        stop_proxy()
    else:
        start_proxy()


def restart_proxy_if_running(
    *,
    page,
    manager,
    restarting: bool,
    set_restarting,
    status_label,
) -> None:
    plan = telegram_proxy_page_runtime.build_restart_plan(
        running=bool(manager.is_running),
        restarting=bool(restarting),
    )
    if not plan.should_restart:
        return

    set_restarting(True)
    status_label.setText(plan.status_text)

    def _bg_stop():
        manager._stop_runtime_only()
        QMetaObject.invokeMethod(
            page,
            "_finish_restart",
            QtNS.ConnectionType.QueuedConnection,
        )

    threading.Thread(target=_bg_stop, daemon=True).start()


def start_proxy_runtime(
    *,
    page,
    manager,
    starting: bool,
    running: bool,
    host: str,
    port: int,
    set_starting,
    btn_toggle,
    status_label,
    append_log_line,
) -> None:
    upstream_config = telegram_proxy_settings.build_upstream_config()
    plan = telegram_proxy_page_runtime.build_start_plan(
        starting=bool(starting),
        running=bool(running),
        host=host,
        port=port,
        upstream_config=upstream_config,
    )
    if not plan.should_start:
        return

    set_starting(True)
    btn_toggle.setEnabled(plan.toggle_enabled)
    status_label.setText(plan.status_text)
    if plan.upstream_log_line:
        append_log_line(plan.upstream_log_line)

    def _bg_start():
        ok = manager.start_proxy(
            port=port,
            mode="socks5",
            host=host,
            upstream_config=upstream_config,
        )
        setattr(page, "_start_result", ok)
        QMetaObject.invokeMethod(
            page,
            "_finish_start",
            QtNS.ConnectionType.QueuedConnection,
        )

    threading.Thread(target=_bg_start, daemon=True).start()


def finish_proxy_start(
    *,
    start_ok: bool,
    set_starting,
    btn_toggle,
    check_relay_after_start,
    on_status_changed,
) -> None:
    set_starting(False)
    plan = telegram_proxy_page_runtime.build_finish_start_plan(start_ok)
    btn_toggle.setEnabled(plan.toggle_enabled)
    if plan.persist_enabled is not None:
        telegram_proxy_settings.set_proxy_enabled(plan.persist_enabled)
    if plan.should_check_relay:
        check_relay_after_start()
    elif plan.fallback_to_stopped_status:
        on_status_changed(False)


def start_relay_check(
    *,
    page,
    manager,
    current_generation: int,
    set_generation,
    status_label,
    set_relay_diag,
    get_zapret_running,
    log_warning,
) -> None:
    start_plan = telegram_proxy_page_runtime.build_relay_start_plan(
        current_generation=current_generation,
        host=manager.host,
        port=manager.port,
    )
    set_generation(start_plan.generation)
    gen = start_plan.generation

    if manager.is_running:
        status_label.setText(start_plan.status_text)

    def _do_check():
        import time

        time.sleep(2)
        if getattr(page, "_relay_check_gen", 0) != gen:
            return

        try:
            from telegram_proxy.wss_proxy import check_relay_reachable

            best_result = None
            for attempt in range(3):
                if getattr(page, "_relay_check_gen", 0) != gen:
                    return
                result = check_relay_reachable(timeout=5.0)
                if result["reachable"]:
                    best_result = result
                    break
                if attempt < 2:
                    time.sleep(2)

            if getattr(page, "_relay_check_gen", 0) != gen:
                return

            if best_result and best_result["reachable"]:
                set_relay_diag({"status": "ok", "ms": best_result["ms"]})
            else:
                http_ok = telegram_proxy_page_runtime.check_relay_http()
                set_relay_diag(
                    {
                        "status": "fail",
                        "http_ok": http_ok,
                        "zapret_running": bool(get_zapret_running()),
                    }
                )

            if getattr(page, "_relay_check_gen", 0) != gen:
                return

            QMetaObject.invokeMethod(
                page,
                "_apply_relay_result",
                QtNS.ConnectionType.QueuedConnection,
            )
        except Exception as exc:
            log_warning(f"Relay check error: {exc}")

    threading.Thread(target=_do_check, daemon=True).start()


def apply_relay_result(
    *,
    manager,
    diag,
    status_label,
    info_bar_cls,
    info_bar_position,
    parent,
) -> None:
    if not manager.is_running:
        return

    plan = telegram_proxy_page_runtime.build_relay_result_plan(
        host=manager.host,
        port=manager.port,
        status=diag.get("status", "fail"),
        ms=diag.get("ms", 0),
        http_ok=bool(diag.get("http_ok", False)),
        zapret_running=bool(diag.get("zapret_running", False)),
    )
    status_label.setText(plan.status_text)
    if plan.show_warning and info_bar_cls is not None:
        info_bar_cls.warning(
            plan.warning_title,
            plan.warning_content,
            duration=-1,
            position=info_bar_position.TOP,
            parent=parent,
        )


def stop_proxy_runtime(*, manager) -> None:
    manager.stop_proxy()
    telegram_proxy_settings.set_proxy_enabled(False)


def apply_status_changed(
    *,
    manager,
    running: bool,
    restarting: bool,
    starting: bool,
    status_dot,
    stats_label,
    status_label,
    btn_toggle,
    port_spin,
    host_edit,
    relay_check_gen: int,
    set_speed_state,
    set_generation,
) -> None:
    plan = telegram_proxy_page_runtime.build_status_plan(
        running=bool(running),
        restarting=bool(restarting),
        starting=bool(starting),
        host=manager.host,
        port=manager.port,
    )
    status_dot.set_active(plan.dot_active)
    if plan.reset_speed_state:
        set_speed_state(0, 0, (), ())
    if plan.clear_stats:
        stats_label.setText("")
    if plan.invalidate_relay_check:
        set_generation(relay_check_gen + 1)

    status_label.setText(plan.status_text)
    btn_toggle.setText(plan.toggle_text)
    port_spin.setEnabled(plan.port_spin_enabled)
    host_edit.setEnabled(plan.host_edit_enabled)


def apply_stats_updated(
    *,
    stats,
    prev_sent: int,
    prev_recv: int,
    speed_hist_up: tuple[int, ...],
    speed_hist_down: tuple[int, ...],
    stats_label,
    set_speed_state,
) -> None:
    if stats is None:
        return
    plan = telegram_proxy_page_runtime.build_stats_plan(
        stats=stats,
        prev_sent=prev_sent,
        prev_recv=prev_recv,
        speed_hist_up=tuple(speed_hist_up or ()),
        speed_hist_down=tuple(speed_hist_down or ()),
        interval=2.0,
    )
    set_speed_state(
        plan.next_prev_sent,
        plan.next_prev_recv,
        plan.next_speed_hist_up,
        plan.next_speed_hist_down,
    )
    stats_label.setText(plan.stats_text)
