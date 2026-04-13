"""Общий runtime-helper слой для direct target/filter списков."""

from __future__ import annotations

import time as _time

from filters.ui.targets_list import TargetsList
from log.log import log



def build_list_structure_signature(payload) -> tuple:
    selected_preset_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip().lower()
    target_items = payload.target_items or {}
    signature_rows = []
    for view in tuple(payload.target_views or ()):
        target_key = str(getattr(view, "target_key", "") or "").strip()
        meta = target_items.get(target_key)
        signature_rows.append(
            (
                target_key,
                str(getattr(view, "display_name", "") or "").strip(),
                str(getattr(meta, "full_name", "") or "").strip(),
                str(getattr(meta, "command_group", "") or "").strip(),
                int(getattr(meta, "order", 999) or 999),
                int(getattr(meta, "command_order", 999) or 999),
                str(getattr(meta, "protocol", "") or "").strip(),
                str(getattr(meta, "ports", "") or "").strip(),
                str(getattr(meta, "icon_name", "") or "").strip(),
                str(getattr(meta, "icon_color", "") or "").strip(),
                str(getattr(meta, "base_filter_hostlist", "") or "").strip(),
                str(getattr(meta, "base_filter_ipset", "") or "").strip(),
                str(getattr(meta, "strategy_type", "") or "").strip(),
                bool(getattr(meta, "requires_all_ports", False)),
            )
        )
    return (selected_preset_file_name, tuple(signature_rows))


def payload_requires_rebuild(*, payload, current_signature, targets_list) -> bool:
    if targets_list is None:
        return True
    return build_list_structure_signature(payload) != current_signature


def set_payload_loading(*, reload_btn, loading_label, loading: bool, targets_list, empty_state_label) -> None:
    try:
        if reload_btn is not None:
            reload_btn.set_loading(bool(loading))
    except Exception:
        pass

    if loading_label is None:
        return

    should_show_placeholder = bool(loading) and targets_list is None and empty_state_label is None
    loading_label.setVisible(should_show_placeholder)


def clear_dynamic_payload_widgets(*, content_host_layout) -> None:
    if content_host_layout is None:
        return
    while content_host_layout.count() > 1:
        item = content_host_layout.takeAt(1)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.deleteLater()


def build_targets_list_widget(
    *,
    page,
    content_host_layout,
    payload,
    startup_scope: str,
    empty_state_text: str,
    empty_label_cls,
    on_target_clicked,
    on_selections_changed,
    empty_state_log_message: str | None = None,
):
    target_items = payload.target_items or {}
    target_views = list(payload.target_views or ())
    strategy_names_by_target = payload.strategy_names_by_target or {}
    filter_modes = payload.filter_modes or {}
    target_selections = payload.strategy_selections or {}
    selected_preset_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip().lower()

    if not target_items:
        empty_state_label = empty_label_cls(empty_state_text)
        empty_state_label.setWordWrap(True)
        content_host_layout.addWidget(empty_state_label)
        if empty_state_log_message:
            log(str(empty_state_log_message), "INFO")
        return {
            "targets_list": None,
            "empty_state_label": empty_state_label,
            "target_selections": dict(target_selections),
            "list_structure_signature": None,
            "target_items": dict(target_items),
            "selected_preset_file_name": selected_preset_file_name,
        }

    targets_list = TargetsList(page, startup_scope=startup_scope)
    targets_list.strategy_selected.connect(on_target_clicked)
    targets_list.selections_changed.connect(on_selections_changed)
    targets_list.build_from_target_views(
        target_views,
        metadata=target_items,
        selections=target_selections,
        strategy_names_by_target=strategy_names_by_target,
        filter_modes=filter_modes,
    )
    content_host_layout.addWidget(targets_list, 1)

    return {
        "targets_list": targets_list,
        "empty_state_label": None,
        "target_selections": dict(target_selections),
        "list_structure_signature": build_list_structure_signature(payload),
        "target_items": dict(target_items),
        "selected_preset_file_name": selected_preset_file_name,
    }


def apply_payload_to_existing_list(
    *,
    targets_list,
    payload,
    ui_log_reason: str,
    update_current_strategies_display=None,
    log_debug=None,
) -> dict:
    target_items = payload.target_items or {}
    target_selections = payload.strategy_selections or {}
    filter_modes = payload.filter_modes or {}
    selected_preset_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip().lower()

    targets_list.set_strategy_names_by_target(payload.strategy_names_by_target or {})
    targets_list.set_selections(target_selections)
    targets_list.set_filter_modes(filter_modes, target_keys=target_items.keys())

    signature = build_list_structure_signature(payload)
    if callable(update_current_strategies_display):
        update_current_strategies_display()
    if callable(log_debug):
        log_debug(f"Список стратегий обновлен без полной перестройки ({ui_log_reason})")
    return {
        "targets_list": targets_list,
        "empty_state_label": None,
        "target_selections": dict(target_selections),
        "list_structure_signature": signature,
        "target_items": dict(target_items),
        "selected_preset_file_name": selected_preset_file_name,
    }


def apply_payload_snapshot(
    *,
    page,
    payload,
    reason: str,
    targets_list,
    list_structure_signature,
    content_host_layout,
    startup_scope: str,
    empty_state_text: str,
    empty_label_cls,
    on_target_clicked,
    on_selections_changed,
    startup_metric_logger=None,
    startup_metric_marker: str = "_build_content.targets_list",
    update_current_strategies_display=None,
    log_debug=None,
    empty_state_log_message: str | None = None,
):
    if payload_requires_rebuild(
        payload=payload,
        current_signature=list_structure_signature,
        targets_list=targets_list,
    ):
        _t_targets = _time.perf_counter()
        clear_dynamic_payload_widgets(content_host_layout=content_host_layout)
        result = build_targets_list_widget(
            page=page,
            content_host_layout=content_host_layout,
            payload=payload,
            startup_scope=startup_scope,
            empty_state_text=empty_state_text,
            empty_label_cls=empty_label_cls,
            on_target_clicked=on_target_clicked,
            on_selections_changed=on_selections_changed,
            empty_state_log_message=empty_state_log_message,
        )
        if callable(startup_metric_logger):
            startup_metric_logger(startup_metric_marker, (_time.perf_counter() - _t_targets) * 1000)
        if result["list_structure_signature"] is not None:
            if callable(update_current_strategies_display):
                update_current_strategies_display()
            if callable(log_debug):
                log_debug(f"Список стратегий применен из runtime snapshot ({reason})")
        return result

    return apply_payload_to_existing_list(
        targets_list=targets_list,
        payload=payload,
        ui_log_reason=reason,
        update_current_strategies_display=update_current_strategies_display,
        log_debug=log_debug,
    )
