"""Runtime-helper слой для Strategy Scan page."""

from __future__ import annotations

from ui.accessibility import set_state_text
from ui.fluent_widgets import set_tooltip
from app.ui_texts import tr as tr_catalog


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
        set_state_text(actions_title_label, f"Раздел подбора стратегии: {actions_title_label.text()}")
    set_tooltip(
        start_btn,
        tr_catalog(
            "page.blockcheck_public.action.start.description",
            language=language,
            default="Запустить автоматический перебор стратегий обхода DPI для выбранной цели.",
        )
    )
    set_tooltip(
        stop_btn,
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
        set_tooltip(quick_domain_btn, plan.quick_domains_tooltip)


def set_support_status(label, text: str) -> None:
    if label is None:
        return
    label.setText(str(text or "").strip())
