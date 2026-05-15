"""Runtime/helper слой для ConnectionTestPage."""

from __future__ import annotations

from PyQt6.QtCore import QThread, QTimer

import diagnostics.page_plans as connection_page_plans
from app.text_catalog import tr as tr_catalog


def apply_interaction_state(
    *,
    start_btn,
    stop_btn,
    test_combo,
    send_log_btn,
    progress_bar,
    start_enabled: bool,
    stop_enabled: bool,
    combo_enabled: bool,
    send_log_enabled: bool,
    progress_visible: bool,
) -> None:
    start_btn.setEnabled(start_enabled)
    stop_btn.setEnabled(stop_enabled)
    test_combo.setEnabled(combo_enabled)
    send_log_btn.setEnabled(send_log_enabled)
    progress_bar.setVisible(progress_visible)

    if progress_visible:
        progress_bar.start()
    else:
        progress_bar.stop()


def set_connection_status(*, status_label, status_badge, text: str, status: str = "muted") -> None:
    status_label.setText(text)
    status_badge.set_status(text, status)


def refresh_test_combo_items(*, combo, language: str) -> None:
    current = combo.currentIndex() if combo is not None else 0
    items = [
        (
            tr_catalog("page.connection.test.all", language=language, default="🌐 Все тесты (Discord + YouTube)"),
            "all",
        ),
        (
            tr_catalog("page.connection.test.discord_only", language=language, default="🎮 Только Discord"),
            "discord",
        ),
        (
            tr_catalog("page.connection.test.youtube_only", language=language, default="🎬 Только YouTube"),
            "youtube",
        ),
    ]
    combo.clear()
    for label, test_type in items:
        combo.addItem(label)
        combo.setItemData(combo.count() - 1, test_type)
    combo.setCurrentIndex(max(0, min(current, len(items) - 1)))


def start_connection_test(
    *,
    page,
    is_testing: bool,
    ui_language: str,
    test_combo,
    result_text,
    apply_interaction_state_callback,
    set_status_callback,
    status_badge,
    progress_badge,
    create_worker_fn,
    worker_update_handler,
    worker_finished_handler,
) -> dict | None:
    if is_testing:
        result_text.append("ℹ️ Тест уже выполняется. Дождитесь завершения.")
        return None

    selection = test_combo.currentText()
    test_type = test_combo.currentData() or "all"
    plan = connection_page_plans.build_start_plan(
        selection=selection,
        test_type=str(test_type),
    )

    result_text.clear()
    for line in plan.start_lines:
        result_text.append(line)

    apply_interaction_state_callback(
        start_enabled=plan.start_enabled,
        stop_enabled=plan.stop_enabled,
        combo_enabled=plan.combo_enabled,
        send_log_enabled=plan.send_log_enabled,
        progress_visible=plan.progress_visible,
    )
    set_status_callback(plan.status_text, plan.status_tone)
    status_badge.set_status(plan.status_badge_text, plan.status_tone)
    progress_badge.set_status(plan.progress_badge_text, plan.status_tone)

    worker_thread = QThread(page)
    worker = create_worker_fn(plan.test_type)
    worker.moveToThread(worker_thread)
    worker_thread.started.connect(worker.run)
    worker.update_signal.connect(worker_update_handler)
    worker.finished_signal.connect(worker_finished_handler)
    worker.finished_signal.connect(worker_thread.quit)
    worker.finished_signal.connect(worker.deleteLater)
    worker_thread.finished.connect(worker_thread.deleteLater)
    worker_thread.start()

    return {
        "cleanup_in_progress": False,
        "finish_mode": "completed",
        "worker": worker,
        "worker_thread": worker_thread,
        "is_testing": True,
    }


def stop_connection_test(
    *,
    page,
    worker,
    worker_thread,
    stop_check_timer,
    append_callback,
    set_status_callback,
    stop_btn,
    worker_finished_handler,
) -> tuple[dict | None, object | None]:
    if not worker or not worker_thread:
        return None, stop_check_timer
    if stop_check_timer is not None:
        return None, stop_check_timer

    plan = connection_page_plans.build_stop_plan()
    for line in plan.append_lines:
        append_callback(line)
    set_status_callback(plan.status_text, plan.status_tone)
    stop_btn.setEnabled(False)
    worker.stop_gracefully()

    attempts = {"count": 0}
    timer = QTimer(page)

    def check_thread():
        attempts["count"] += 1
        poll_plan = connection_page_plans.build_stop_poll_plan(
            attempt_count=attempts["count"],
            thread_running=bool(worker_thread and worker_thread.isRunning()),
            max_attempts=plan.max_attempts,
            finalize_delay_ms=plan.finalize_delay_ms,
        )
        if poll_plan.action == "finish":
            timer.stop()
            if poll_plan.append_line:
                append_callback(poll_plan.append_line)
            worker_finished_handler()
        elif poll_plan.action == "force_terminate":
            timer.stop()
            if poll_plan.append_line:
                append_callback(poll_plan.append_line)
            if worker_thread:
                worker_thread.terminate()
                QTimer.singleShot(poll_plan.finalize_delay_ms, worker_finished_handler)

    timer.timeout.connect(check_thread)
    timer.start(plan.poll_interval_ms)
    return {"finish_mode": "stopped"}, timer


def apply_worker_update(*, message: str, append_callback, result_text) -> None:
    for line in connection_page_plans.build_worker_update_lines(message):
        append_callback(line)

    scrollbar = result_text.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())


def release_worker_resources(worker) -> None:
    if worker is None:
        return
    release = getattr(worker, "release_resources", None)
    if not callable(release):
        return
    try:
        release()
    except Exception:
        pass


def finish_connection_test(
    *,
    cleanup_in_progress: bool,
    is_testing: bool,
    worker,
    worker_thread,
    stop_check_timer,
    finish_mode: str,
    apply_interaction_state_callback,
    set_status_callback,
    status_badge,
    progress_badge,
    append_callback,
) -> dict | None:
    if cleanup_in_progress:
        return None
    if not is_testing and worker is None and worker_thread is None:
        return None

    if stop_check_timer is not None:
        stop_check_timer.stop()
        stop_check_timer.deleteLater()

    release_worker_resources(worker)

    if finish_mode == "stopped":
        plan = connection_page_plans.build_stopped_finish_plan()
    else:
        plan = connection_page_plans.build_finish_plan()

    apply_interaction_state_callback(
        start_enabled=plan.start_enabled,
        stop_enabled=plan.stop_enabled,
        combo_enabled=plan.combo_enabled,
        send_log_enabled=plan.send_log_enabled,
        progress_visible=plan.progress_visible,
    )
    set_status_callback(plan.status_text, plan.status_tone)
    status_badge.set_status(plan.status_badge_text, plan.status_tone)
    progress_badge.set_status(plan.progress_badge_text, "muted")
    for line in plan.finish_lines:
        append_callback(line)

    return {
        "finish_mode": "completed",
        "is_testing": False,
        "worker": None,
        "worker_thread": None,
        "stop_check_timer": None,
    }


def open_support_with_log(*, selection: str, append_callback, set_status_callback) -> None:
    plan = connection_page_plans.prepare_support_request_for_connection(
        selection=selection,
    )
    for line in plan.log_lines:
        append_callback(line)
    set_status_callback(plan.status_text, plan.status_tone)


def apply_connection_language(
    *,
    language: str,
    controls_card,
    actions_title_label,
    hero_title,
    hero_subtitle,
    test_select_label,
    refresh_test_combo_items_callback,
    start_btn,
    stop_btn,
    send_log_btn,
) -> None:
    try:
        if controls_card is not None:
            controls_card.set_title(
                tr_catalog("page.connection.card.testing", language=language, default="Тестирование")
            )
    except Exception:
        pass
    if actions_title_label is not None:
        actions_title_label.setText(
            tr_catalog("page.connection.actions.title", language=language, default="Действия")
        )

    hero_title.setText(
        tr_catalog("page.connection.hero.title", language=language, default="Диагностика сетевых соединений")
    )
    hero_subtitle.setText(
        tr_catalog(
            "page.connection.hero.subtitle",
            language=language,
            default="Проверьте доступность Discord и YouTube, а затем одной кнопкой соберите ZIP с логами и откройте GitHub Discussions.",
        )
    )
    test_select_label.setText(
        tr_catalog("page.connection.test.select", language=language, default="Выбор теста:")
    )
    refresh_test_combo_items_callback()

    start_btn.setText(tr_catalog("page.connection.button.start", language=language, default="Запустить тест"))
    stop_btn.setText(tr_catalog("page.connection.button.stop", language=language, default="Стоп"))
    send_log_btn.setText(tr_catalog("page.connection.button.send_log", language=language, default="Подготовить обращение"))
    start_btn.setToolTip(
        tr_catalog(
            "page.connection.action.start.description",
            language=language,
            default="Запустить выбранный сценарий диагностики для Discord и YouTube.",
        )
    )
    stop_btn.setToolTip(
        tr_catalog(
            "page.connection.action.stop.description",
            language=language,
            default="Остановить текущий тест, если он уже запущен.",
        )
    )
    send_log_btn.setToolTip(
        tr_catalog(
            "page.connection.action.support.description",
            language=language,
            default="Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
        )
    )


def cleanup_connection_runtime(
    *,
    cleanup_in_progress: bool,
    finish_mode: str,
    stop_check_timer,
    worker,
    worker_thread,
    log_debug,
    log_warning,
) -> dict:
    _ = cleanup_in_progress, finish_mode
    if stop_check_timer is not None:
        stop_check_timer.stop()
        stop_check_timer.deleteLater()
        stop_check_timer = None

    cleanup_plan = connection_page_plans.build_cleanup_plan(
        has_worker=worker is not None,
        thread_running=bool(worker_thread and worker_thread.isRunning()),
    )
    if cleanup_plan.should_quit_thread and worker_thread and worker_thread.isRunning():
        log_debug("Останавливаем connection test worker...")
        if cleanup_plan.should_request_stop and worker:
            worker.stop_gracefully()
        worker_thread.quit()
        if not worker_thread.wait(cleanup_plan.wait_timeout_ms):
            log_warning("⚠ Connection test worker не завершился, принудительно завершаем")
            if cleanup_plan.should_terminate:
                worker_thread.terminate()
                worker_thread.wait(cleanup_plan.terminate_wait_ms)
    release_worker_resources(worker)
    return {
        "cleanup_in_progress": True,
        "finish_mode": "completed",
        "is_testing": False,
        "worker": None,
        "worker_thread": None,
        "stop_check_timer": None,
    }
