"""Data-access helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations


def require_app_context_v1(window) -> object:
    app_context = getattr(window, "app_context", None)
    if app_context is None:
        raise RuntimeError("AppContext is required for Zapret1 strategy detail page")
    return app_context


def load_target_payload_sync_v1(
    *,
    target_key: str | None,
    current_target_key: str,
    require_app_context_fn,
    set_payload_fn,
    refresh: bool = False,
):
    key = str(target_key or current_target_key or "").strip().lower()
    if not key:
        return None

    try:
        payload = require_app_context_fn().direct_ui_snapshot_service.load_target_detail_payload(
            "direct_zapret1",
            key,
            refresh=refresh,
        )
    except Exception:
        return None

    if payload is not None and str(getattr(payload, "target_key", "") or "").strip().lower() == key:
        set_payload_fn(payload)
    return payload


def get_target_details_v1(
    *,
    target_key: str | None,
    current_target_key: str,
    direct_facade,
    current_payload,
    load_target_payload_sync_fn,
):
    key = str(target_key or current_target_key or "").strip().lower()
    if not key or not direct_facade:
        return None

    payload = current_payload
    if payload is not None and str(getattr(payload, "target_key", "") or "") == key:
        return payload.details

    payload = load_target_payload_sync_fn(key, refresh=False)
    if payload is None:
        return None
    return getattr(payload, "details", None)


def load_current_strategy_id_v1(
    *,
    direct_facade,
    target_key: str,
    get_target_details_fn,
) -> str:
    if not direct_facade or not target_key:
        return "none"
    try:
        details = get_target_details_fn(target_key)
        if details is not None:
            return str(details.current_strategy or "none").strip() or "none"
        selections = direct_facade.get_strategy_selections() or {}
        return str(selections.get(target_key) or "none").strip() or "none"
    except Exception:
        return "none"
