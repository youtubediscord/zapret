"""Runtime-helper слой для Strategy Scan page."""

from __future__ import annotations

import logging

from ui.fluent_widgets import InfoBarHelper
from app.text_catalog import tr as tr_catalog


logger = logging.getLogger(__name__)


def apply_log_expand_state(
    *,
    blockcheck_feature,
    expanded: bool,
    language: str,
    control_card,
    warning_card,
    results_card,
    log_edit,
    expand_log_btn,
) -> None:
    plan = blockcheck_feature.build_log_expand_plan(
        expanded=expanded,
        language=language,
    )

    control_card.setVisible(plan.control_visible)
    warning_card.setVisible(plan.warning_visible)
    results_card.setVisible(plan.results_visible)
    log_edit.setMinimumHeight(plan.log_min_height)
    log_edit.setMaximumHeight(plan.log_max_height)
    expand_log_btn.setText(plan.button_text)


def apply_language_plan_ui(
    *,
    blockcheck_feature,
    language: str,
    log_expanded: bool,
    control_card,
    results_card,
    log_card,
    expand_log_btn,
    warning_card,
    start_btn,
    stop_btn,
    actions_title_label,
    prepare_support_btn,
    protocol_combo,
    games_scope_label,
    games_scope_combo,
    quick_domain_btn,
) -> None:
    plan = blockcheck_feature.build_language_plan(
        language=language,
        log_expanded=log_expanded,
    )
    control_card.set_title(plan.control_title)
    results_card.set_title(plan.results_title)
    log_card.set_title(plan.log_title)
    expand_log_btn.setText(plan.expand_log_text)
    warning_card.set_title(plan.warning_title)
    start_btn.setText(plan.start_text)
    stop_btn.setText(plan.stop_text)
    if actions_title_label is not None:
        actions_title_label.setText(
            tr_catalog("page.blockcheck_public.actions.title", language=language, default="Действия")
        )
    start_btn.setToolTip(
        tr_catalog(
            "page.blockcheck_public.action.start.description",
            language=language,
            default="Запустить автоматический перебор стратегий обхода DPI для выбранной цели.",
        )
    )
    stop_btn.setToolTip(
        tr_catalog(
            "page.blockcheck_public.action.stop.description",
            language=language,
            default="Остановить текущее сканирование стратегий и вернуть страницу в обычный режим.",
        )
    )
    if prepare_support_btn is not None:
        prepare_support_btn.setText(plan.prepare_support_text)
    protocol_combo.setItemText(0, plan.protocol_items[0])
    protocol_combo.setItemText(1, plan.protocol_items[1])
    protocol_combo.setItemText(2, plan.protocol_items[2])
    if games_scope_label is not None:
        games_scope_label.setText(plan.udp_scope_label)
    if games_scope_combo is not None:
        games_scope_combo.setItemText(0, plan.udp_scope_items[0])
        games_scope_combo.setItemText(1, plan.udp_scope_items[1])
    if quick_domain_btn is not None:
        quick_domain_btn.setText(plan.quick_domains_text)
        quick_domain_btn.setToolTip(plan.quick_domains_tooltip)


def set_support_status(label, text: str) -> None:
    if label is None:
        return
    label.setText(str(text or "").strip())


def prepare_strategy_scan_support(
    *,
    blockcheck_feature,
    cleanup_in_progress: bool,
    run_log_file,
    stored_scan_protocol: str,
    stored_scan_target: str,
    raw_protocol_value,
    raw_target_input: str,
    raw_protocol_label: str,
    raw_mode_label: str,
    stored_mode: str,
    parent_widget,
    support_status_label,
) -> None:
    if cleanup_in_progress:
        return

    support_context = blockcheck_feature.build_support_context(
        stored_scan_protocol=stored_scan_protocol,
        stored_scan_target=stored_scan_target,
        raw_protocol_value=raw_protocol_value,
        raw_target_input=raw_target_input,
        raw_protocol_label=raw_protocol_label,
        raw_mode_label=raw_mode_label,
        stored_mode=stored_mode,
    )

    try:
        feedback = blockcheck_feature.prepare_support(
            run_log_file=run_log_file,
            target=support_context.target,
            protocol_label=support_context.protocol_label,
            mode_label=support_context.mode_label,
            scan_protocol=support_context.scan_protocol,
        )
        result = feedback.result
        if result.zip_path:
            logger.info("Prepared Strategy Scan support archive: %s", result.zip_path)

        message_plan = blockcheck_feature.build_support_success_plan(feedback)
        set_support_status(support_status_label, message_plan.status_text)

        try:
            InfoBarHelper.success(
                parent_widget,
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Failed to prepare strategy-scan support bundle: %s", exc)
        message_plan = blockcheck_feature.build_support_error_plan(str(exc))
        set_support_status(support_status_label, message_plan.status_text)
        try:
            InfoBarHelper.warning(
                parent_widget,
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception:
            pass
