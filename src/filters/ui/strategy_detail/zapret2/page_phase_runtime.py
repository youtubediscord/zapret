from __future__ import annotations

import json

from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.strategy_detail.zapret2.tcp_phase_workflow import (
    apply_tcp_phase_row_click_result,
    apply_tcp_phase_save_result,
    build_strategy_args_lookup,
    load_tcp_phase_state,
)
from filters.ui.strategy_detail.zapret2.common import (
    TCP_EMBEDDED_FAKE_TECHNIQUES,
    TCP_PHASE_COMMAND_ORDER,
    TCP_PHASE_TAB_ORDER,
)
from filters.ui.strategy_detail.zapret2.tcp_phase_ui import (
    apply_tcp_phase_tabs_visibility,
    select_default_tcp_phase_tab,
    set_active_phase_chip,
    update_tcp_phase_chip_markers,
)


def get_target_strategy_args_text(page) -> str:
    if not page._target_key:
        return ""
    payload = getattr(page, "_target_payload", None)
    if payload is not None and str(getattr(payload, "target_key", "") or "") == page._target_key:
        return str(getattr(payload, "raw_args_text", "") or "")
    return page._read_target_raw_args_text(page._target_key)


def get_strategy_args_text_by_id(page, strategy_id: str) -> str:
    data = dict(page._strategies_data_by_id.get(strategy_id, {}) or {})
    args = data.get("args", "")
    if isinstance(args, (list, tuple)):
        args = "\n".join([str(a) for a in args if a is not None])
    return page._normalize_args_text(str(args or ""))


def infer_strategy_id_from_args_exact(page, args_text: str) -> str:
    normalized = page._normalize_args_text(args_text)
    if not normalized:
        return "none"

    for sid, data in (page._strategies_data_by_id or {}).items():
        if not sid or sid in ("none", page.TCP_FAKE_DISABLED_STRATEGY_ID):
            continue
        args_val = (data or {}).get("args") if isinstance(data, dict) else ""
        if isinstance(args_val, (list, tuple)):
            args_val = "\n".join([str(a) for a in args_val if a is not None])
        candidate = page._normalize_args_text(str(args_val or ""))
        if candidate and candidate == normalized:
            return sid

    return page.CUSTOM_STRATEGY_ID


def extract_desync_techniques_from_args(page, args_text: str) -> list[str]:
    out: list[str] = []
    for raw in (args_text or "").splitlines():
        line = raw.strip()
        if not line or not line.startswith("--"):
            continue
        tech = page._extract_desync_technique_from_arg(line)
        if tech:
            out.append(tech)
    return out


def infer_tcp_phase_key_for_strategy_args(page, args_text: str) -> str | None:
    phase_keys: set[str] = set()
    for tech in extract_desync_techniques_from_args(page, args_text):
        phase = page._map_desync_technique_to_tcp_phase(tech)
        if phase:
            phase_keys.add(phase)
    if len(phase_keys) == 1:
        return next(iter(phase_keys))
    return None


def update_tcp_phase_chip_markers_runtime(page) -> None:
    if not page._tcp_phase_mode:
        return

    tabbar = page._phase_tabbar
    if not tabbar:
        return

    update_tcp_phase_chip_markers(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        tabbar=tabbar,
        phase_tab_index_by_key=page._phase_tab_index_by_key,
        tcp_phase_tab_order=TCP_PHASE_TAB_ORDER,
        selected_ids=page._tcp_phase_selected_ids,
        custom_args=page._tcp_phase_custom_args,
        fake_disabled_strategy_id=page.TCP_FAKE_DISABLED_STRATEGY_ID,
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
        build_marker_plan_fn=StrategyDetailPageController.build_tcp_phase_marker_plan,
    )


def load_tcp_phase_state_from_preset_runtime(page) -> None:
    page._tcp_phase_selected_ids = {}
    page._tcp_phase_custom_args = {}
    page._tcp_hide_fake_phase = False

    selected_ids, custom_args, hide_fake_phase = load_tcp_phase_state(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        target_key=page._target_key,
        args_text=get_target_strategy_args_text(page),
        strategies_data_by_id=page._strategies_data_by_id,
        phase_order=TCP_PHASE_COMMAND_ORDER,
        embedded_fake_techniques=TCP_EMBEDDED_FAKE_TECHNIQUES,
        fake_disabled_strategy_id=page.TCP_FAKE_DISABLED_STRATEGY_ID,
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
        normalize_args_text_fn=page._normalize_args_text,
        extract_desync_technique_fn=page._extract_desync_technique_from_arg,
        map_phase_fn=page._map_desync_technique_to_tcp_phase,
        infer_phase_key_fn=lambda args_text: infer_tcp_phase_key_for_strategy_args(page, args_text),
        build_state_plan_fn=StrategyDetailPageController.build_tcp_phase_state_plan,
    )
    page._tcp_phase_selected_ids = selected_ids
    page._tcp_phase_custom_args = custom_args
    page._tcp_hide_fake_phase = hide_fake_phase

    page._update_selected_strategy_header(page._selected_strategy_id)
    update_tcp_phase_chip_markers_runtime(page)


def apply_tcp_phase_tabs_visibility_runtime(page) -> None:
    apply_tcp_phase_tabs_visibility(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        phase_tabbar=page._phase_tabbar,
        hide_fake_phase=bool(page._tcp_hide_fake_phase),
        active_phase_key=page._active_phase_key,
        build_tabs_visibility_plan_fn=StrategyDetailPageController.build_tcp_phase_tabs_visibility_plan,
        set_active_phase_chip_fn=page._set_active_phase_chip,
        reapply_filters_fn=page._apply_filters,
    )


def set_active_phase_chip_runtime(page, phase_key: str) -> None:
    final_phase_key = set_active_phase_chip(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        phase_tabbar=page._phase_tabbar,
        phase_tab_index_by_key=page._phase_tab_index_by_key,
        requested_phase_key=phase_key,
        build_active_phase_chip_plan_fn=StrategyDetailPageController.build_active_phase_chip_plan,
    )
    if final_phase_key:
        page._active_phase_key = final_phase_key


def select_default_tcp_phase_tab_runtime(page) -> None:
    select_default_tcp_phase_tab(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        selected_ids=page._tcp_phase_selected_ids,
        hide_fake_phase=bool(page._tcp_hide_fake_phase),
        phase_priority=["multisplit", "multidisorder", "multidisorder_legacy", "tcpseg", "oob", "other"],
        build_default_tab_plan_fn=StrategyDetailPageController.build_default_tcp_phase_tab_plan,
        set_active_phase_chip_fn=page._set_active_phase_chip,
    )


def save_tcp_phase_state_to_preset(page, *, show_loading: bool = True) -> None:
    if not (page._tcp_phase_mode and page._target_key):
        return

    strategy_args_by_id = build_strategy_args_lookup(
        strategies_data_by_id=page._strategies_data_by_id,
        load_args_text_fn=lambda strategy_id: get_strategy_args_text_by_id(page, strategy_id),
    )
    new_args = StrategyDetailPageController.build_tcp_phase_args_text(
        selected_ids=page._tcp_phase_selected_ids,
        custom_args=page._tcp_phase_custom_args,
        hide_fake_phase=bool(page._tcp_hide_fake_phase),
        phase_order=TCP_PHASE_COMMAND_ORDER,
        strategy_args_by_id=strategy_args_by_id,
        fake_disabled_strategy_id=page.TCP_FAKE_DISABLED_STRATEGY_ID,
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
    )

    try:
        if not page._write_target_raw_args_text(
            page._target_key,
            new_args,
            save_and_sync=True,
        ):
            return
        page._preset_refresh_runtime.mark_suppressed()
        payload = page._reload_current_target_payload()
        plan = StrategyDetailPageController.build_tcp_phase_save_result_plan(
            payload=payload,
            show_loading=show_loading,
        )
        apply_tcp_phase_save_result(
            plan,
            target_key=page._target_key,
            set_selected_state_fn=lambda selected_id, current_id: (
                setattr(page, "_selected_strategy_id", selected_id),
                setattr(page, "_current_strategy_id", current_id),
            ),
            set_target_enabled_ui_fn=page._set_target_enabled_ui,
            refresh_args_editor_fn=page._refresh_args_editor_state,
            show_loading_fn=page.show_loading,
            stop_loading_fn=page._stop_loading,
            hide_success_icon_fn=lambda: page._success_icon.hide(),
            update_header_fn=page._update_selected_strategy_header,
            update_markers_fn=page._update_tcp_phase_chip_markers,
            emit_selection_fn=page.strategy_selected.emit,
        )

    except Exception as e:
        log(f"TCP phase save failed: {e}", "ERROR")


def on_tcp_phase_row_clicked(page, strategy_id: str) -> None:
    if not page._strategies_tree:
        return
    try:
        is_visible = bool(page._strategies_tree.is_strategy_visible(strategy_id))
    except Exception:
        is_visible = False

    strategy_args_by_id = build_strategy_args_lookup(
        strategies_data_by_id=page._strategies_data_by_id,
        load_args_text_fn=lambda sid: get_strategy_args_text_by_id(page, sid),
    )
    plan = StrategyDetailPageController.build_tcp_phase_row_click_plan(
        tcp_phase_mode=bool(page._tcp_phase_mode),
        target_key=page._target_key,
        active_phase_key=page._active_phase_key,
        strategy_id=strategy_id,
        is_visible=is_visible,
        selected_ids=page._tcp_phase_selected_ids,
        custom_args=page._tcp_phase_custom_args,
        strategy_args_by_id=strategy_args_by_id,
        phase_order=TCP_PHASE_COMMAND_ORDER,
        embedded_fake_techniques=TCP_EMBEDDED_FAKE_TECHNIQUES,
        custom_strategy_id=page.CUSTOM_STRATEGY_ID,
        fake_disabled_strategy_id=page.TCP_FAKE_DISABLED_STRATEGY_ID,
    )
    apply_tcp_phase_row_click_result(
        plan,
        set_phase_state_fn=lambda selected_ids, custom_args, hide_fake_phase: (
            setattr(page, "_tcp_phase_selected_ids", selected_ids),
            setattr(page, "_tcp_phase_custom_args", custom_args),
            setattr(page, "_tcp_hide_fake_phase", hide_fake_phase),
        ),
        strategies_tree=page._strategies_tree,
        apply_tabs_visibility_fn=page._apply_tcp_phase_tabs_visibility,
        save_state_fn=page._save_tcp_phase_state_to_preset,
    )


def load_target_last_tcp_phase_tab(page, target_key: str) -> str | None:
    try:
        from config.reg import reg
        from config.config import REGISTRY_PATH_GUI
    except Exception:
        return None

    key = str(target_key or "").strip().lower()
    if not key:
        return None

    try:
        raw = reg(REGISTRY_PATH_GUI, page._REG_TCP_PHASE_TABS_BY_TARGET)
        if not raw:
            return None
        data = json.loads(raw) if isinstance(raw, str) else {}
        phase = str((data or {}).get(key) or "").strip().lower()
        if phase and phase in (page._phase_tab_index_by_key or {}):
            return phase
    except Exception:
        return None

    return None


def save_target_last_tcp_phase_tab(page, target_key: str, phase_key: str) -> None:
    try:
        from config.reg import reg
        from config.config import REGISTRY_PATH_GUI
    except Exception:
        return

    target_key_n = str(target_key or "").strip().lower()
    phase = str(phase_key or "").strip().lower()
    if not target_key_n or not phase:
        return

    if page._tcp_phase_mode and phase not in (page._phase_tab_index_by_key or {}):
        return

    try:
        raw = reg(REGISTRY_PATH_GUI, page._REG_TCP_PHASE_TABS_BY_TARGET)
        data = {}
        if isinstance(raw, str) and raw.strip():
            try:
                data = json.loads(raw) or {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        data[target_key_n] = phase
        reg(REGISTRY_PATH_GUI, page._REG_TCP_PHASE_TABS_BY_TARGET, json.dumps(data, ensure_ascii=False))
    except Exception:
        return


def select_out_range_mode(page, mode: str) -> None:
    if mode != page._out_range_mode:
        page._out_range_mode = mode
        try:
            page._out_range_seg.setCurrentItem(mode)
        except Exception:
            pass
        page._schedule_syndata_settings_save()


def on_send_toggled(page, checked: bool) -> None:
    page._send_settings.setVisible(checked)
    page._schedule_syndata_settings_save()


def on_syndata_toggled(page, checked: bool) -> None:
    page._syndata_settings.setVisible(checked)
    page._schedule_syndata_settings_save()


def schedule_syndata_settings_save(page, delay_ms: int = 180) -> None:
    plan = StrategyDetailPageController.build_syndata_timer_plan(
        target_key=page._target_key,
        delay_ms=delay_ms,
    )
    if not plan.should_schedule:
        return
    page._pending_syndata_target_key = plan.pending_target_key
    try:
        page._syndata_save_timer.start(plan.delay_ms)
    except Exception:
        page._flush_syndata_settings_save()


def flush_syndata_settings_save(page) -> None:
    raw_payload = {
        "enabled": page._syndata_toggle.isChecked(),
        "blob": page._blob_combo.currentText(),
        "tls_mod": page._tls_mod_combo.currentText(),
        "autottl_delta": page._autottl_delta_selector.value(),
        "autottl_min": page._autottl_min_selector.value(),
        "autottl_max": page._autottl_max_selector.value(),
        "out_range": page._out_range_spin.value(),
        "out_range_mode": page._out_range_mode,
        "tcp_flags_unset": page._tcp_flags_combo.currentText(),
        "send_enabled": page._send_toggle.isChecked(),
        "send_repeats": page._send_repeats_spin.value(),
        "send_ip_ttl": page._send_ip_ttl_selector.value(),
        "send_ip6_ttl": page._send_ip6_ttl_selector.value(),
        "send_ip_id": page._send_ip_id_combo.currentText(),
        "send_badsum": page._send_badsum_check.isChecked(),
    }
    plan = StrategyDetailPageController.build_syndata_persist_plan(
        target_key=page._target_key,
        pending_target_key=page._pending_syndata_target_key,
        payload=raw_payload,
    )
    if not plan.should_save:
        return
    page._pending_syndata_target_key = None

    log(f"Syndata settings saved for {plan.normalized_target_key}: {plan.payload}", "DEBUG")
    page._preset_refresh_runtime.mark_suppressed()
    page._write_target_details_settings(
        plan.normalized_target_key,
        plan.payload,
        save_and_sync=True,
    )


def load_syndata_settings(page, target_key: str) -> dict:
    details = page._get_target_details(target_key)
    protocol = str(getattr(page._target_info, "protocol", "") or "")
    return StrategyDetailPageController.build_target_settings_payload(details=details, protocol=protocol)
