from __future__ import annotations


def target_supports_filter_switch(target_info) -> bool:
    if isinstance(target_info, dict):
        host = str(target_info.get("base_filter_hostlist") or "").strip()
        ipset = str(target_info.get("base_filter_ipset") or "").strip()
        return bool(host and ipset)

    host = str(getattr(target_info, "base_filter_hostlist", "") or "").strip()
    ipset = str(getattr(target_info, "base_filter_ipset", "") or "").strip()
    return bool(host and ipset)


def load_target_filter_mode(direct_facade, *, target_key: str, current_payload=None) -> str:
    if not direct_facade:
        return "hostlist"

    normalized_target = str(target_key or "").strip().lower()
    payload = current_payload
    if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == normalized_target:
        return str(getattr(payload, "filter_mode", "") or "hostlist")

    try:
        return str(direct_facade.get_target_filter_mode(normalized_target) or "hostlist")
    except Exception:
        return "hostlist"


def save_target_filter_mode(direct_facade, *, target_key: str, mode: str) -> bool:
    if not direct_facade:
        return False
    normalized_target = str(target_key or "").strip().lower()
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in ("hostlist", "ipset"):
        normalized_mode = "hostlist"
    try:
        result = direct_facade.update_target_filter_mode(
            normalized_target,
            normalized_mode,
            save_and_sync=True,
        )
    except Exception:
        return False
    return bool(result is not False)


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

