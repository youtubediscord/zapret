"""Proxy lifecycle/runtime helper слой для Telegram Proxy page."""

from __future__ import annotations

from PyQt6.QtCore import QMetaObject, Qt as QtNS
from qfluentwidgets import FluentIcon

from ui.accessibility import set_control_accessibility, set_state_text
import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime


def _page_runtime(page, attr: str):
    return getattr(page, attr)


def _mark_worker_request_id(worker, request_id: int):
    try:
        worker._request_id = int(request_id)
    except Exception:
        pass
    return worker


def handle_toggle_proxy(
    *,
    manager,
    restarting: bool,
    starting: bool,
    set_restarting,
    stop_proxy,
    start_proxy,
    request_proxy_enabled_save,
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
            request_proxy_enabled_save(bool(plan.persist_enabled))
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
    create_stop_runtime_worker,
    on_finished=None,
) -> None:
    plan = telegram_proxy_page_runtime.build_restart_plan(
        running=bool(manager.is_running),
        restarting=bool(restarting),
    )
    runtime = _page_runtime(page, "_restart_stop_runtime")
    if not plan.should_restart:
        # Идёт цикл рестарта/старта: не дропаем запрос, а откладываем повтор,
        # иначе сервер, выбранный во время рестарта, не применится.
        if bool(restarting) or bool(getattr(page, "_starting", False)):
            setattr(page, "_restart_again_pending", True)
        return
    if runtime.is_running():
        setattr(page, "_restart_again_pending", True)
        return

    set_restarting(True)
    status_label.setText(plan.status_text)
    set_state_text(status_label, f"Статус Telegram Proxy: {plan.status_text}")
    try:
        from log.log import log

        log("Telegram Proxy: перезапуск для применения настроек", "INFO")
    except Exception:
        pass
    runtime.start_qthread_worker(
        worker_factory=lambda request_id: _mark_worker_request_id(
            create_stop_runtime_worker(manager=manager, parent=page),
            request_id,
        ),
        on_loaded=lambda _request_id: QMetaObject.invokeMethod(
            page,
            "_finish_restart",
            QtNS.ConnectionType.QueuedConnection,
        ),
        on_finished=on_finished,
        signal_includes_request_id=False,
        loaded_signal_name="stopped",
    )


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
    create_start_worker,
    mode: str = "socks5",
    upstream_config=None,
    cloudflare_config=None,
    mtproxy_secret: str = "",
    pool_size: int = 4,
    buffer_kb: int = 256,
    fake_tls_domain: str = "",
    proxy_protocol: bool = False,
    on_finished=None,
) -> None:
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

    runtime = _page_runtime(page, "_proxy_start_runtime")
    if runtime.is_running():
        return
    runtime.start_qthread_worker(
        worker_factory=lambda request_id: _mark_worker_request_id(
            create_start_worker(
                manager=manager,
                port=port,
                mode=str(mode or "socks5"),
                host=host,
                upstream_config=upstream_config,
                cloudflare_config=cloudflare_config,
                mtproxy_secret=str(mtproxy_secret or ""),
                pool_size=int(pool_size),
                buffer_kb=int(buffer_kb),
                fake_tls_domain=str(fake_tls_domain or ""),
                proxy_protocol=bool(proxy_protocol),
                parent=page,
            ),
            request_id,
        ),
        on_loaded=lambda _request_id, ok: _finish_proxy_start_worker(page, ok),
        on_finished=on_finished,
        signal_includes_request_id=False,
        loaded_signal_name="completed",
    )


def _finish_proxy_start_worker(page, ok: bool) -> None:
    setattr(page, "_start_result", bool(ok))
    QMetaObject.invokeMethod(page, "_finish_start", QtNS.ConnectionType.QueuedConnection)


def finish_proxy_start(
    *,
    start_ok: bool,
    set_starting,
    btn_toggle,
    check_relay_after_start,
    on_status_changed,
    request_proxy_enabled_save,
) -> None:
    set_starting(False)
    plan = telegram_proxy_page_runtime.build_finish_start_plan(start_ok)
    btn_toggle.setEnabled(plan.toggle_enabled)
    if plan.persist_enabled is not None:
        request_proxy_enabled_save(bool(plan.persist_enabled))
    if plan.should_check_relay:
        on_status_changed(True)
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
    create_relay_check_worker,
    on_finished=None,
) -> None:
    runtime = _page_runtime(page, "_relay_check_runtime")
    if runtime.is_running():
        return

    start_plan = telegram_proxy_page_runtime.build_relay_start_plan(
        current_generation=current_generation,
        host=manager.host,
        port=manager.port,
    )
    set_generation(start_plan.generation)
    gen = start_plan.generation

    if manager.is_running:
        status_label.setText(start_plan.status_text)

    def _apply_worker_result(result_generation: int, diag: dict) -> None:
        if getattr(page, "_relay_check_gen", 0) != int(result_generation):
            return
        set_relay_diag(dict(diag or {}))
        QMetaObject.invokeMethod(page, "_apply_relay_result", QtNS.ConnectionType.QueuedConnection)

    def _bind_worker(worker) -> None:
        worker.completed.connect(_apply_worker_result)
        worker.warning.connect(log_warning)

    runtime.start_qthread_worker(
        worker_factory=lambda request_id: _mark_worker_request_id(
            create_relay_check_worker(
                generation=gen,
                get_zapret_running=get_zapret_running,
                parent=page,
            ),
            request_id,
        ),
        bind_worker=_bind_worker,
        on_finished=on_finished,
    )


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

    stats = manager.stats
    traffic_seen = bool(
        getattr(stats, "bytes_received", 0) > 0
        or getattr(stats, "bytes_sent", 0) > 0
    )

    plan = telegram_proxy_page_runtime.build_relay_result_plan(
        host=manager.host,
        port=manager.port,
        status=diag.get("status", "fail"),
        ms=diag.get("ms", 0),
        http_ok=bool(diag.get("http_ok", False)),
        zapret_running=bool(diag.get("zapret_running", False)),
        traffic_seen=traffic_seen,
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


def stop_proxy_runtime(*, page, manager, create_stop_runtime_worker, on_finished=None) -> None:
    runtime = _page_runtime(page, "_proxy_stop_runtime")
    if runtime.is_running():
        return

    runtime.start_qthread_worker(
        worker_factory=lambda request_id: _mark_worker_request_id(
            create_stop_runtime_worker(
                manager=manager,
                emit_status=True,
                parent=page,
            ),
            request_id,
        ),
        on_loaded=lambda _request_id: QMetaObject.invokeMethod(
            page,
            "_finish_stop_proxy",
            QtNS.ConnectionType.QueuedConnection,
        ),
        on_finished=on_finished,
        signal_includes_request_id=False,
        loaded_signal_name="stopped",
    )


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
    status_accessible_text = f"Статус Telegram Proxy: {plan.status_text}"
    set_state_text(status_label, status_accessible_text)
    set_state_text(status_dot, f"Индикатор Telegram Proxy: {plan.status_text}")
    btn_toggle.setText(plan.toggle_text)
    btn_toggle.setIcon(FluentIcon.CANCEL if "Останов" in plan.toggle_text else FluentIcon.PLAY)
    btn_toggle.setMinimumWidth(140)
    if "Останов" in plan.toggle_text:
        set_control_accessibility(
            btn_toggle,
            name="Остановить Telegram Proxy",
            description="Останавливает локальный Telegram Proxy.",
        )
    else:
        set_control_accessibility(
            btn_toggle,
            name="Запустить Telegram Proxy",
            description="Запускает локальный Telegram Proxy.",
        )
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
