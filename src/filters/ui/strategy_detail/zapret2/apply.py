from __future__ import annotations

from filters.ui.strategy_detail.shared_detail_feedback import apply_detail_loading_indicator
from filters.ui.strategy_detail.shared_detail_header import apply_detail_header_state

def apply_selected_strategy_header_state(label, state, *, set_tooltip_fn) -> None:
    try:
        if not state.visible:
            label.hide()
            return
        label.set_full_text(state.text)
        set_tooltip_fn(label, state.tooltip)
        label.show()
    except Exception:
        pass


def apply_loading_indicator_state(
    spinner,
    success_icon,
    *,
    loading: bool = False,
    success: bool = False,
    success_pixmap=None,
) -> None:
    apply_detail_loading_indicator(
        spinner,
        success_icon,
        loading=loading,
        success=success,
        success_pixmap=success_pixmap,
    )

def apply_target_payload_header_state(
    title_label,
    subtitle_label,
    breadcrumb,
    *,
    title_text: str,
    subtitle_text: str,
    detail_text: str,
    control_text: str,
    strategies_text: str,
) -> None:
    apply_detail_header_state(
        title_label,
        subtitle_label,
        breadcrumb,
        title_text=title_text,
        subtitle_text=subtitle_text,
        detail_text=detail_text,
        control_text=control_text,
        strategies_text=strategies_text,
    )
