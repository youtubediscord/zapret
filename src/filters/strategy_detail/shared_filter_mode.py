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
