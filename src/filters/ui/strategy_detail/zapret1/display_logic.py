from __future__ import annotations

from typing import Any

from filters.ui.strategy_detail.filter_mode_ui import (
    apply_filter_mode_selector_texts,
    sync_basic_target_controls,
)
from filters.ui.strategy_detail.shared_detail_header import build_detail_header_text_state


_LABEL_ORDER = {
    "recommended": 0,
    "stable": 1,
    None: 2,
    "none": 2,
    "experimental": 3,
    "game": 4,
    "caution": 5,
}


def normalize_target_info_v1(target_key: str, target_info: Any) -> dict[str, Any]:
    if isinstance(target_info, dict):
        info = dict(target_info)
        info.setdefault("key", target_key)
        info.setdefault("full_name", target_key)
        info.setdefault("description", "")
        info.setdefault("base_filter", "")
        info.setdefault("base_filter_hostlist", "")
        info.setdefault("base_filter_ipset", "")
        return info

    return {
        "key": getattr(target_info, "key", target_key),
        "full_name": getattr(target_info, "full_name", target_key),
        "description": getattr(target_info, "description", ""),
        "protocol": getattr(target_info, "protocol", ""),
        "ports": getattr(target_info, "ports", ""),
        "icon_name": getattr(target_info, "icon_name", ""),
        "icon_color": getattr(target_info, "icon_color", "#909090"),
        "base_filter": getattr(target_info, "base_filter", ""),
        "base_filter_hostlist": getattr(target_info, "base_filter_hostlist", ""),
        "base_filter_ipset": getattr(target_info, "base_filter_ipset", ""),
    }


def sorted_strategy_items_v1(strategies: dict[str, dict], sort_mode: str) -> list[dict]:
    items = [s for s in (strategies or {}).values() if s.get("id")]

    if sort_mode == "alpha_asc":
        return sorted(items, key=lambda s: (s.get("name", "")).lower())
    if sort_mode == "alpha_desc":
        return sorted(items, key=lambda s: (s.get("name", "")).lower(), reverse=True)

    return sorted(
        items,
        key=lambda s: (
            _LABEL_ORDER.get(s.get("label"), 2),
            (s.get("name", "")).lower(),
        ),
    )


def default_strategy_id_v1(strategies: dict[str, dict], sort_mode: str) -> str:
    for item in sorted_strategy_items_v1(strategies, sort_mode):
        sid = str(item.get("id") or "").strip()
        if sid and sid != "none":
            return sid
    return "none"


def strategy_display_name_v1(strategy_id: str, strategies: dict[str, dict], tr) -> str:
    sid = (strategy_id or "").strip()
    if not sid or sid == "none":
        return tr("page.z1_strategy_detail.tree.disabled.name", "Выключено")
    if sid == "custom":
        return tr("page.z1_strategy_detail.tree.custom.name", "Свой набор")
    info = (strategies or {}).get(sid)
    if info:
        return info.get("name", sid)
    return sid


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


def update_selected_label(
    *,
    selected_label,
    tr_fn,
    current_strategy_id: str,
    strategy_display_name_fn,
) -> None:
    if selected_label is None:
        return
    selected_label.setText(
        tr_fn(
            "page.z1_strategy_detail.selected.current",
            "Текущая стратегия: {strategy}",
            strategy=strategy_display_name_fn(current_strategy_id),
        )
    )


def update_header_labels(
    *,
    title_label,
    desc_label,
    subtitle_label,
    tr_fn,
    target_info: dict,
    target_key: str,
    update_selected_label_fn,
) -> None:
    header_state = build_detail_header_text_state(
        target_info=target_info,
        target_key=target_key,
        tr=tr_fn,
        ports_text_key="page.z1_strategy_detail.subtitle.ports",
        ports_text_default="порты: {ports}",
        empty_title=target_key,
        empty_detail="Target",
    )

    if title_label is not None:
        title_label.setText(header_state.title_text)
    if desc_label is not None:
        desc_label.setText(header_state.description_text)
        desc_label.setVisible(bool(header_state.description_text))

    if subtitle_label is not None:
        subtitle_label.setText(header_state.subtitle_text)

    update_selected_label_fn()


def sync_target_controls(
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
    sync_basic_target_controls(
        enable_toggle=enable_toggle,
        edit_args_btn=edit_args_btn,
        filter_mode_frame=filter_mode_frame,
        filter_mode_selector=filter_mode_selector,
        current_strategy_id=current_strategy_id,
        target_key=target_key,
        target_info=target_info,
        load_target_filter_mode_fn=load_target_filter_mode_fn,
    )


def refresh_args_preview(
    *,
    args_preview_label,
    tr_fn,
    get_current_args_fn,
) -> None:
    if args_preview_label is None:
        return

    current_args = get_current_args_fn()
    if not current_args:
        args_preview_label.setText(tr_fn("page.z1_strategy_detail.args.none", "(нет аргументов)"))
        return

    lines = [line for line in current_args.splitlines() if line.strip()]
    preview = "\n".join(lines[:8])
    if len(lines) > 8:
        preview += tr_fn(
            "page.z1_strategy_detail.args.more",
            "\n... (+{count} строк)",
            count=len(lines) - 8,
        )
    args_preview_label.setText(preview)


def apply_strategy_detail_v1_language(
    *,
    tr_fn,
    target_key: str,
    back_btn,
    title_label,
    state_label,
    enable_toggle,
    filter_label,
    filter_mode_selector,
    search_edit,
    sort_combo,
    sort_mode: str,
    edit_args_btn,
    list_card,
    empty_label,
    rebuild_breadcrumb_fn,
    update_header_labels_fn,
    rebuild_tree_rows_fn,
    refresh_args_preview_fn,
) -> None:
    if back_btn is not None:
        back_btn.setText(tr_fn("page.z1_strategy_detail.back.strategies", "← Стратегии Zapret 1"))

    if title_label is not None and not target_key:
        title_label.setText(tr_fn("page.z1_strategy_detail.header.category_fallback", "Target"))

    if state_label is not None:
        state_label.setText(tr_fn("page.z1_strategy_detail.state.category_bypass", "Обход для target'а"))

    if enable_toggle is not None:
        if hasattr(enable_toggle, "setOnText"):
            enable_toggle.setOnText(tr_fn("page.z1_strategy_detail.toggle.on", "Включено"))
        if hasattr(enable_toggle, "setOffText"):
            enable_toggle.setOffText(tr_fn("page.z1_strategy_detail.toggle.off", "Выключено"))

    if filter_label is not None:
        filter_label.setText(tr_fn("page.z1_strategy_detail.filter.label", "Фильтр:"))

    apply_filter_mode_selector_texts(
        filter_mode_selector,
        ipset_text=tr_fn("page.z1_strategy_detail.filter.ipset", "IPset"),
        hostlist_text=tr_fn("page.z1_strategy_detail.filter.hostlist", "Hostlist"),
    )

    if search_edit is not None:
        search_edit.setPlaceholderText(
            tr_fn(
                "page.z1_strategy_detail.search.placeholder",
                "Поиск стратегии по названию или аргументам",
            )
        )

    if sort_combo is not None:
        selected_mode = sort_combo.currentData() or sort_mode
        sort_combo.blockSignals(True)
        sort_combo.clear()
        sort_combo.addItem(
            tr_fn("page.z1_strategy_detail.sort.recommended", "По рекомендации"),
            userData="recommended",
        )
        sort_combo.addItem(
            tr_fn("page.z1_strategy_detail.sort.alpha_asc", "По алфавиту A-Z"),
            userData="alpha_asc",
        )
        sort_combo.addItem(
            tr_fn("page.z1_strategy_detail.sort.alpha_desc", "По алфавиту Z-A"),
            userData="alpha_desc",
        )
        idx = sort_combo.findData(selected_mode)
        sort_combo.setCurrentIndex(idx if idx >= 0 else 0)
        sort_combo.blockSignals(False)

    if edit_args_btn is not None:
        edit_args_btn.setText(tr_fn("page.z1_strategy_detail.button.edit_args", "Редактировать аргументы"))

    if list_card is not None:
        list_card.set_title(tr_fn("page.z1_strategy_detail.card.strategies", "Стратегии"))

    if empty_label is not None:
        empty_label.setText(
            tr_fn(
                "page.z1_strategy_detail.empty.no_strategies",
                "Нет доступных стратегий. Проверьте папку presets рядом с программой.",
            )
        )

    rebuild_breadcrumb_fn()
    update_header_labels_fn()
    rebuild_tree_rows_fn()
    refresh_args_preview_fn()
