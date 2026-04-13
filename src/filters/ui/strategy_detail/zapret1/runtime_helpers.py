"""Runtime/helper слой для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from filters.ui.strategy_detail.filter_mode_ui import (
    apply_filter_mode_selector_texts,
    sync_basic_target_controls,
)


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
    full_name = target_info.get("full_name", target_key) or target_key
    description = target_info.get("description", "")
    protocol = target_info.get("protocol", "")
    ports = target_info.get("ports", "")

    if title_label is not None:
        title_label.setText(full_name)
    if desc_label is not None:
        desc_label.setText(description)
        desc_label.setVisible(bool(description))

    subtitle_parts = []
    if protocol:
        subtitle_parts.append(str(protocol))
    if ports:
        subtitle_parts.append(tr_fn("page.z1_strategy_detail.subtitle.ports", "порты: {ports}", ports=ports))

    if subtitle_label is not None:
        subtitle_label.setText(" | ".join(subtitle_parts))

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
                "Нет доступных стратегий. Проверьте %APPDATA%\\zapret\\direct_zapret1\\",
            )
        )

    rebuild_breadcrumb_fn()
    update_header_labels_fn()
    rebuild_tree_rows_fn()
    refresh_args_preview_fn()
