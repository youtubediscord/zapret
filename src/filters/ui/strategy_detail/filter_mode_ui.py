from __future__ import annotations

from filters.strategy_detail.shared_filter_mode import target_supports_filter_switch


def apply_filter_mode_selector_state(selector, *, mode: str) -> None:
    normalized_mode = str(mode or "").strip().lower()
    if selector is None:
        return
    selector.blockSignals(True)
    try:
        selector.setChecked(normalized_mode == "ipset")
    except Exception:
        pass
    selector.blockSignals(False)


def apply_filter_mode_selector_texts(selector, *, ipset_text: str, hostlist_text: str) -> None:
    if selector is None:
        return
    try:
        if hasattr(selector, "setOnText"):
            selector.setOnText(str(ipset_text or "IPset"))
        if hasattr(selector, "setOffText"):
            selector.setOffText(str(hostlist_text or "Hostlist"))
    except Exception:
        pass


def sync_basic_target_controls(
    *,
    enable_toggle,
    edit_args_btn,
    filter_mode_frame,
    filter_mode_selector,
    current_strategy_id: str,
    target_key: str,
    target_info,
    load_target_filter_mode_fn,
) -> None:
    enabled = (current_strategy_id or "none") != "none"

    if enable_toggle is not None:
        enable_toggle.blockSignals(True)
        try:
            if hasattr(enable_toggle, "setChecked"):
                enable_toggle.setChecked(enabled)
        finally:
            enable_toggle.blockSignals(False)

    if edit_args_btn is not None:
        try:
            edit_args_btn.setEnabled(enabled)
        except Exception:
            pass

    if filter_mode_frame is None:
        return

    can_switch = bool(target_supports_filter_switch(target_info))
    try:
        filter_mode_frame.setVisible(can_switch)
    except Exception:
        pass
    if not can_switch:
        return

    saved_mode = load_target_filter_mode_fn(target_key)
    apply_filter_mode_selector_state(filter_mode_selector, mode=saved_mode)
