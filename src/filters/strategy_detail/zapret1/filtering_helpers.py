"""Search/sort/tree helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from filters.ui import StrategyTreeRow


def normalize_search_text(text: str) -> str:
    return (text or "").strip().lower()


def resolve_sort_mode_change(*, sort_combo, current_sort_mode: str) -> str | None:
    if not sort_combo:
        return None
    mode = sort_combo.currentData()
    mode = str(mode or "recommended")
    if mode == current_sort_mode:
        return None
    return mode


def apply_sort_mode_v1(*, tree, sort_mode: str) -> None:
    if not tree:
        return

    sort_map = {
        "recommended": "default",
        "alpha_asc": "name_asc",
        "alpha_desc": "name_desc",
    }
    tree.set_sort_mode(sort_map.get(sort_mode, "default"))
    tree.apply_sort()


def apply_search_filter_v1(*, tree, search_text: str) -> None:
    if tree:
        tree.apply_filter(search_text, set())


def rebuild_tree_rows_v1(
    *,
    tree,
    tr_fn,
    current_strategy_id: str,
    get_current_args_fn,
    sorted_strategy_items: list[dict],
    apply_sort_mode_fn,
    apply_search_filter_fn,
    empty_label,
    strategies: dict[str, dict],
) -> None:
    if not tree:
        return

    tree.clear_strategies()

    tree.add_strategy(
        StrategyTreeRow(
            strategy_id="none",
            name=tr_fn("page.z1_strategy_detail.tree.disabled.name", "Выключено"),
            args=[
                tr_fn(
                    "page.z1_strategy_detail.tree.disabled.args",
                    "Отключить обход DPI для этого target'а",
                )
            ],
        )
    )

    if current_strategy_id == "custom":
        custom_lines = [line.strip() for line in get_current_args_fn().splitlines() if line.strip()]
        tree.add_strategy(
            StrategyTreeRow(
                strategy_id="custom",
                name=tr_fn("page.z1_strategy_detail.tree.custom.name", "Свой набор"),
                args=custom_lines
                or [
                    tr_fn(
                        "page.z1_strategy_detail.tree.custom.args",
                        "Пользовательские аргументы",
                    )
                ],
            )
        )

    for strategy in sorted_strategy_items:
        sid = (strategy.get("id") or "").strip()
        if not sid:
            continue
        args_lines = [line.strip() for line in (strategy.get("args") or "").splitlines() if line.strip()]
        tree.add_strategy(
            StrategyTreeRow(
                strategy_id=sid,
                name=strategy.get("name", sid),
                args=args_lines,
            )
        )

    apply_sort_mode_fn()
    apply_search_filter_fn()

    active_sid = current_strategy_id if tree.has_strategy(current_strategy_id) else "none"
    tree.set_selected_strategy(active_sid)

    if empty_label is not None:
        empty_label.setVisible(not bool(strategies))
