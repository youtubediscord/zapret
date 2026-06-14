"""Diagnostics/test и ISP-warning workflow для канонической DNS страницы."""

from __future__ import annotations


def prepare_connectivity_test(
    *,
    cleanup_in_progress: bool,
    set_test_in_progress_fn,
    update_test_action_text_fn,
    build_connectivity_test_plan_fn,
    language: str,
):
    if cleanup_in_progress:
        return None

    set_test_in_progress_fn(True)
    update_test_action_text_fn()
    return build_connectivity_test_plan_fn(language=language)


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
    plan,
    qpush_button_cls,
    qt_namespace,
    on_accept,
    log_fn,
    info_bar_cls,
    info_bar_position_cls,
    parent_window,
) -> None:
    if cleanup_in_progress:
        return
    try:
        if not plan.should_show:
            return

        bar = info_bar_cls.warning(
            title=plan.title,
            content=plan.content,
            isClosable=True,
            position=info_bar_position_cls.TOP_RIGHT,
            duration=10000,
            parent=parent_window,
        )

        if bar is not None and getattr(plan, "action_text", ""):
            action_btn = qpush_button_cls(plan.action_text)
            action_btn.setCursor(qt_namespace.CursorShape.PointingHandCursor)

            def _accept_from_infobar():
                try:
                    bar.close()
                except Exception:
                    pass
                on_accept()

            action_btn.clicked.connect(_accept_from_infobar)
            bar.addWidget(action_btn)
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
    apply_recommended_dns_fn,
    log_fn,
) -> None:
    if cleanup_in_progress:
        return
    try:
        plan = build_accept_plan_fn()
        if plan.hide_warning and warning is not None:
            hide_warning_widget_fn(warning_widget=warning)
        if plan.apply_recommended_dns:
            apply_recommended_dns_fn()
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
