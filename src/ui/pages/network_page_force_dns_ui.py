"""UI-helper'ы для Force DNS слоя страницы Network."""

from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsOpacityEffect


def set_force_dns_toggle(toggle_row, checked: bool) -> None:
    try:
        toggle_row.setChecked(checked, block_signals=True)
        return
    except TypeError:
        pass
    toggle_row.toggle.blockSignals(True)
    try:
        toggle_row.setChecked(checked)
    finally:
        toggle_row.toggle.blockSignals(False)


def update_force_dns_status_label(
    *,
    label,
    enabled: bool,
    details_key: str | None,
    details_kwargs: dict | None,
    details_fallback: str,
    language: str,
    build_status_plan_fn,
) -> None:
    if label is None:
        return
    plan = build_status_plan_fn(
        enabled=enabled,
        details_key=details_key,
        details_kwargs=details_kwargs,
        details_fallback=details_fallback,
        language=language,
    )
    label.setText(plan.text)


def update_dns_selection_block_state(*, blocked: bool, dns_cards_container, custom_card) -> None:
    for widget in (dns_cards_container, custom_card):
        if widget is None:
            continue
        if blocked:
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.35)
            widget.setGraphicsEffect(effect)
        else:
            widget.setGraphicsEffect(None)


def highlight_force_dns_card(*, card, get_theme_tokens_fn, schedule_fn) -> None:
    if card is None:
        return

    tokens = get_theme_tokens_fn()
    highlight_style = f"""
        SettingsCard {{
            background-color: {tokens.accent_soft_bg_hover};
            border: 2px solid {tokens.accent_hex};
            border-radius: 10px;
        }}
    """
    original_style = card.styleSheet()
    card.setStyleSheet(highlight_style)
    schedule_fn(700, lambda: card.setStyleSheet(original_style))
