"""Support/orchestra workflow helper'ы для страницы логов."""

from __future__ import annotations


def get_orchestra_runner(*, window_getter, qapp_instance_getter):
    try:
        app = window_getter()
        runner = getattr(app, "orchestra_runner", None) if app else None
        if runner:
            return runner
    except Exception:
        pass

    try:
        qapp = qapp_instance_getter()
        if qapp:
            active_window_getter = getattr(qapp, "activeWindow", None)
            main_window = active_window_getter() if callable(active_window_getter) else None
            runner = getattr(main_window, "orchestra_runner", None) if main_window else None
            if runner:
                return runner

            for widget in qapp.topLevelWidgets():
                runner = getattr(widget, "orchestra_runner", None)
                if runner:
                    return runner
    except Exception:
        pass

    return None


def update_orchestra_indicator(*, container, is_orchestra_mode: bool) -> None:
    if container is None:
        return
    container.setVisible(bool(is_orchestra_mode))


def apply_support_feedback(
    *,
    result,
    build_feedback_fn,
    build_error_feedback_fn,
    info_bar,
    parent,
    log_fn,
    render_status_fn,
    status_state_setter,
) -> None:
    try:
        if getattr(result, "zip_path", None):
            log_fn(f"Подготовлен архив поддержки: {result.zip_path}", "INFO")
        feedback = build_feedback_fn(result)
        status_state_setter(feedback.status_text, feedback.status_tone)
        render_status_fn()

        if info_bar:
            info_bar.success(
                title=feedback.infobar_title,
                content=feedback.infobar_content,
                parent=parent,
                duration=5000,
            )
    except Exception as e:
        log_fn(f"Ошибка подготовки обращения из логов: {e}", "ERROR")
        feedback = build_error_feedback_fn(str(e))
        status_state_setter(feedback.status_text, feedback.status_tone)
        render_status_fn()
        if info_bar:
            info_bar.warning(
                title=feedback.infobar_title,
                content=feedback.infobar_content,
                parent=parent,
            )
