"""Diagnostics/test и ISP-warning workflow для канонической DNS страницы."""

from __future__ import annotations

import threading


def start_connectivity_test(
    *,
    cleanup_in_progress: bool,
    set_test_in_progress_fn,
    update_test_action_text_fn,
    test_completed_signal,
    on_test_complete_fn,
    build_connectivity_test_plan_fn,
    run_connectivity_test_fn,
    language: str,
) -> None:
    if cleanup_in_progress:
        return

    set_test_in_progress_fn(True)
    update_test_action_text_fn()

    try:
        test_completed_signal.disconnect()
    except TypeError:
        pass
    test_completed_signal.connect(on_test_complete_fn)

    test_plan = build_connectivity_test_plan_fn(language=language)

    def thread_func():
        results = run_connectivity_test_fn(test_plan.test_hosts)
        if cleanup_in_progress:
            return
        test_completed_signal.emit(results)

    thread = threading.Thread(target=thread_func, daemon=True)
    thread.start()


def apply_connectivity_test_result(
    *,
    cleanup_in_progress: bool,
    results: list,
    set_test_in_progress_fn,
    update_test_action_text_fn,
    build_result_plan_fn,
    language: str,
    info_bar_cls,
    parent_window,
) -> None:
    if cleanup_in_progress:
        return

    set_test_in_progress_fn(False)
    update_test_action_text_fn()
    plan = build_result_plan_fn(results, language=language)

    if info_bar_cls:
        if plan.infobar_level == "success":
            info_bar_cls.success(
                title=plan.title,
                content=plan.content,
                parent=parent_window,
            )
        else:
            info_bar_cls.warning(
                title=plan.title,
                content=plan.content,
                parent=parent_window,
            )


def show_isp_dns_warning(
    *,
    cleanup_in_progress: bool,
    adapters,
    dns_info: dict,
    force_dns_active: bool,
    language: str,
    build_warning_plan_fn,
    get_theme_tokens_fn,
    build_warning_ui_fn,
    insert_warning_widget_fn,
    mark_warning_shown_fn,
    render_warning_styles_fn,
    parent,
    qframe_cls,
    qvbox_layout_cls,
    qhbox_layout_cls,
    qlabel_cls,
    qpush_button_cls,
    qt_namespace,
    add_widget_fn,
    before_widget,
    on_accept,
    on_dismiss,
    set_warning_widgets_fn,
    log_fn,
) -> None:
    if cleanup_in_progress:
        return
    try:
        plan = build_warning_plan_fn(
            adapters,
            dns_info,
            force_dns_active=force_dns_active,
            language=language,
        )
        if not plan.should_show:
            return

        tokens = get_theme_tokens_fn()
        warning_widgets = build_warning_ui_fn(
            parent=parent,
            plan=plan,
            qframe_cls=qframe_cls,
            qvbox_layout_cls=qvbox_layout_cls,
            qhbox_layout_cls=qhbox_layout_cls,
            qlabel_cls=qlabel_cls,
            qpush_button_cls=qpush_button_cls,
            qt_namespace=qt_namespace,
            on_accept=on_accept,
            on_dismiss=on_dismiss,
        )
        set_warning_widgets_fn(warning_widgets)
        mark_warning_shown_fn()

        insert_warning_widget_fn(
            layout=parent.vBoxLayout,
            before_widget=before_widget,
            add_widget_fn=add_widget_fn,
            warning_widget=warning_widgets.frame,
        )
        render_warning_styles_fn(tokens)
    except Exception as exc:
        log_fn(f"Ошибка показа ISP DNS предупреждения: {exc}", "DEBUG")


def render_isp_warning_theme(
    *,
    tokens,
    get_theme_tokens_fn,
    render_warning_styles_fn,
    warning,
    icon_label,
    title_label,
    content_label,
    accept_button,
    dismiss_button,
    qta_module,
) -> None:
    theme_tokens = tokens or get_theme_tokens_fn()
    render_warning_styles_fn(
        warning=warning,
        icon_label=icon_label,
        title_label=title_label,
        content_label=content_label,
        accept_button=accept_button,
        dismiss_button=dismiss_button,
        qta_module=qta_module,
        theme_tokens=theme_tokens,
    )


def accept_isp_dns_recommendation(
    *,
    cleanup_in_progress: bool,
    build_accept_plan_fn,
    warning,
    hide_warning_widget_fn,
    set_force_dns_toggle_fn,
    on_force_dns_toggled_fn,
    log_fn,
) -> None:
    if cleanup_in_progress:
        return
    try:
        plan = build_accept_plan_fn()
        if plan.hide_warning and warning is not None:
            hide_warning_widget_fn(warning_widget=warning)
        if plan.enable_force_dns:
            set_force_dns_toggle_fn(True)
            on_force_dns_toggled_fn(True)
    except Exception as exc:
        log_fn(f"Ошибка применения рекомендуемого DNS: {exc}", "ERROR")


def dismiss_isp_dns_warning(
    *,
    cleanup_in_progress: bool,
    build_dismiss_plan_fn,
    warning,
    hide_warning_widget_fn,
) -> None:
    if cleanup_in_progress:
        return
    plan = build_dismiss_plan_fn()
    if plan.hide_warning and warning is not None:
        hide_warning_widget_fn(warning_widget=warning)


def cleanup_network_page(
    *,
    set_cleanup_in_progress_fn,
    set_test_in_progress_fn,
    signal_objects: dict[str, object],
    warning,
    hide_warning_widget_fn,
) -> None:
    set_cleanup_in_progress_fn(True)
    set_test_in_progress_fn(False)

    for signal in signal_objects.values():
        if signal is None:
            continue
        try:
            signal.disconnect()
        except Exception:
            pass

    if warning is not None:
        try:
            hide_warning_widget_fn(warning_widget=warning)
        except Exception:
            pass
