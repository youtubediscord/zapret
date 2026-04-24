from __future__ import annotations


def build_pending_strategy_items(
    *,
    strategies: dict[str, dict[str, object]],
    item_factory,
    tr,
    custom_strategy_id: str,
) -> list[object]:
    pending_items: list[object] = [
        item_factory(
            strategy_id="none",
            name=tr("page.z2_strategy_detail.tree.phase.none.name", "(без изменений)"),
            arg_text="--new",
            is_custom=False,
        ),
        item_factory(
            strategy_id=custom_strategy_id,
            name=tr("page.z2_strategy_detail.tree.phase.custom.name", "Пользовательские аргументы (custom)"),
            arg_text="...",
            is_custom=True,
        ),
    ]
    for sid, data in (strategies or {}).items():
        pending_items.append(
            item_factory(
                strategy_id=str(sid or "").strip(),
                name=str((data or {}).get("name", sid)).strip() or str(sid or "").strip(),
                arg_text=str((data or {}).get("arg_str", "") or ""),
                is_custom=False,
            )
        )
    return pending_items
