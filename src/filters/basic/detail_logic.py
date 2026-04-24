from __future__ import annotations


def build_pending_strategy_items(
    *,
    strategies: dict[str, dict[str, object]],
    item_factory,
    tr,
    custom_strategy_id: str,
) -> list[object]:
    _ = custom_strategy_id
    pending_items: list[object] = [
        item_factory(
            strategy_id="none",
            name=tr("page.z2_strategy_detail.tree.disabled.name", "Выключено (без DPI-обхода)"),
            arg_text="",
            is_custom=False,
        )
    ]
    for sid, data in (strategies or {}).items():
        normalized_sid = str(sid or "").strip()
        pending_items.append(
            item_factory(
                strategy_id=normalized_sid,
                name=str((data or {}).get("name", sid) or normalized_sid),
                arg_text=str((data or {}).get("arg_str", "") or ""),
                is_custom=False,
            )
        )
    return pending_items

