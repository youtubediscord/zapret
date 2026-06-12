"""Runtime/helper слой для ConnectionTestPage."""

from __future__ import annotations

from PyQt6.QtCore import QTimer

import diagnostics.page_plans as connection_page_plans
from app.ui_texts import tr as tr_catalog
from diagnostics.ui.components import clean_connection_status_text
from ui.accessibility import set_control_accessibility, set_state_text
from ui.combo_accessibility import set_combo_items_accessibility
from ui.fluent_widgets import set_tooltip


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
    progress_state = "выполняется" if progress_visible else "не выполняется"
    set_state_text(progress_bar, f"Ход диагностики соединений: {progress_state}")

    if progress_visible:
        progress_bar.start()
    else:
        progress_bar.stop()


def set_connection_status(*, status_label, status_badge, text: str, status: str = "muted") -> None:
    status_label.setText(text)
    value = clean_connection_status_text(text)
    if value:
        set_state_text(status_label, f"Статус диагностики: {value}")
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
    _update_test_combo_accessibility(combo)
    _ensure_test_combo_accessibility_signal(combo)


def _update_test_combo_accessibility(combo) -> None:
    selected = _clean_combo_text(combo.currentText())
    name = "Сценарий диагностики"
    if selected:
        name = f"{name}, выбрано: {selected}"
    set_state_text(combo, name)
    set_control_accessibility(
        combo,
        name=name,
        description=(
            "Выберите, какие соединения проверить: Discord и YouTube, только Discord или только YouTube. "
            "Откройте список и выберите сценарий стрелками вверх и вниз."
        ),
    )
    set_combo_items_accessibility(combo, name="Сценарий диагностики", clean_label=_clean_combo_text)


def _ensure_test_combo_accessibility_signal(combo) -> None:
    if bool(getattr(combo, "_diagnostics_test_combo_accessibility_connected", False)):
        return
    try:
        combo.currentIndexChanged.connect(lambda _index: _update_test_combo_accessibility(combo))
        setattr(combo, "_diagnostics_test_combo_accessibility_connected", True)
    except Exception:
        pass


def _clean_combo_text(text: object) -> str:
    value = " ".join(str(text or "").strip().split())
    for marker in ("🌐", "🎮", "🎬"):
        value = value.replace(marker, "")
    return " ".join(value.split())


def start_connection_test(
    *,
    is_testing: bool,
    ui_language: str,
    test_combo,
    result_text,
    apply_interaction_state_callback,
    set_status_callback,
    status_badge,
    progress_badge,
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
    first_line = _clean_combo_text(
        clean_connection_status_text(plan.start_lines[0] if plan.start_lines else "").replace("🚀", "")
    )
    if first_line:
        set_state_text(result_text, f"Результат диагностики соединений: {first_line}")

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

    return {
        "cleanup_in_progress": False,
        "finish_mode": "completed",
        "is_testing": True,
        "test_type": plan.test_type,
    }


def stop_connection_test(
    *,
    page,
    runtime,
    stop_check_timer,
    append_callback,
    set_status_callback,
    stop_btn,
    worker_finished_handler,
) -> tuple[dict | None, object | None]:
    worker = getattr(runtime, "worker", None)
    if not worker or not runtime.is_running():
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
            thread_running=runtime.is_running(),
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
            target = getattr(runtime, "thread", None) or getattr(runtime, "worker", None)
            terminate = getattr(target, "terminate", None)
            if callable(terminate):
                terminate()
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
    runtime,
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
    if not is_testing and not runtime.is_running():
        return None

    if stop_check_timer is not None:
        stop_check_timer.stop()
        stop_check_timer.deleteLater()

    release_worker_resources(getattr(runtime, "worker", None))

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
        "stop_check_timer": None,
    }


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
    set_tooltip(
        start_btn,
        tr_catalog(
            "page.connection.action.start.description",
            language=language,
            default="Запустить выбранный сценарий диагностики для Discord и YouTube.",
        )
    )
    set_control_accessibility(
        start_btn,
        name=tr_catalog(
            "page.connection.action.start.accessible_name",
            language=language,
            default="Запустить диагностический тест",
        ),
        description=tr_catalog(
            "page.connection.action.start.description",
            language=language,
            default="Запустить выбранный сценарий диагностики для Discord и YouTube.",
        ),
    )
    set_tooltip(
        stop_btn,
        tr_catalog(
            "page.connection.action.stop.description",
            language=language,
            default="Останавливает текущий тест, если он уже запущен.",
        )
    )
    set_control_accessibility(
        stop_btn,
        name=tr_catalog(
            "page.connection.action.stop.accessible_name",
            language=language,
            default="Остановить диагностический тест",
        ),
        description=tr_catalog(
            "page.connection.action.stop.description",
            language=language,
            default="Останавливает текущий тест, если он уже запущен.",
        ),
    )
    set_tooltip(
        send_log_btn,
        tr_catalog(
            "page.connection.action.support.description",
            language=language,
            default="Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
        )
    )
    set_control_accessibility(
        send_log_btn,
        name=tr_catalog(
            "page.connection.action.support.accessible_name",
            language=language,
            default="Подготовить обращение с логами",
        ),
        description=tr_catalog(
            "page.connection.action.support.description",
            language=language,
            default="Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
        ),
    )


def cleanup_connection_runtime(
    *,
    cleanup_in_progress: bool,
    finish_mode: str,
    stop_check_timer,
    runtime,
    log_debug,
    log_warning,
) -> dict:
    _ = cleanup_in_progress, finish_mode
    if stop_check_timer is not None:
        stop_check_timer.stop()
        stop_check_timer.deleteLater()
        stop_check_timer = None

    worker = getattr(runtime, "worker", None)
    thread_running = runtime.is_running()
    cleanup_plan = connection_page_plans.build_cleanup_plan(
        has_worker=worker is not None,
        thread_running=thread_running,
    )
    if cleanup_plan.should_quit_thread and thread_running:
        log_debug("Останавливаем connection test worker...")
    runtime.stop(
        blocking=False,
        wait_timeout_ms=cleanup_plan.wait_timeout_ms,
        terminate_wait_ms=cleanup_plan.terminate_wait_ms,
        log_fn=lambda text, level="DEBUG": log_warning(text) if str(level).upper() == "WARNING" else log_debug(text),
        warning_prefix="connection_test_worker",
    )
    if not thread_running:
        release_worker_resources(worker)
    runtime.cancel()
    return {
        "cleanup_in_progress": True,
        "finish_mode": "completed",
        "is_testing": False,
        "stop_check_timer": None,
    }
