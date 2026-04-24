from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnableTogglePlanV1:
    should_select_strategy: bool
    strategy_id: str
    remember_last_enabled_strategy_id: str | None
    should_restore_toggle_off: bool


def save_filter_mode_v1(direct_facade, *, target_key: str, mode: str) -> bool:
    from filters.strategy_detail.shared_filter_mode import save_target_filter_mode

    return save_target_filter_mode(
        direct_facade,
        target_key=target_key,
        mode=mode,
    )


def resolve_enable_toggle_plan_v1(
    *,
    enabled: bool,
    last_enabled_strategy_id: str,
    default_strategy_id: str,
    current_strategy_id: str,
) -> EnableTogglePlanV1:
    if enabled:
        strategy_id = str(last_enabled_strategy_id or "").strip()
        if not strategy_id or strategy_id == "none":
            strategy_id = str(default_strategy_id or "").strip() or "none"
        if strategy_id == "none":
            return EnableTogglePlanV1(
                should_select_strategy=False,
                strategy_id="none",
                remember_last_enabled_strategy_id=None,
                should_restore_toggle_off=True,
            )
        return EnableTogglePlanV1(
            should_select_strategy=True,
            strategy_id=strategy_id,
            remember_last_enabled_strategy_id=None,
            should_restore_toggle_off=False,
        )

    remembered = None
    if current_strategy_id and current_strategy_id != "none":
        remembered = str(current_strategy_id).strip()
    return EnableTogglePlanV1(
        should_select_strategy=True,
        strategy_id="none",
        remember_last_enabled_strategy_id=remembered,
        should_restore_toggle_off=False,
    )


def persist_strategy_selection_v1(direct_facade, *, target_key: str, strategy_id: str) -> str:
    sid = (strategy_id or "none").strip() or "none"
    ok = direct_facade.set_strategy_selection(
        target_key,
        sid,
        save_and_sync=True,
    )
    if ok is False:
        raise RuntimeError("Не удалось сохранить выбор стратегии")
    return sid


def handle_filter_mode_change_v1(
    *,
    direct_facade,
    target_key: str,
    new_mode: str,
    tr_fn,
    info_bar_cls,
    has_fluent: bool,
    parent_window,
    log_fn,
    sync_target_controls_fn,
) -> None:
    if not direct_facade or not target_key:
        return

    try:
        ok = save_filter_mode_v1(
            direct_facade,
            target_key=target_key,
            mode=new_mode,
        )
        if not ok:
            raise RuntimeError(
                tr_fn(
                    "page.z1_strategy_detail.error.filter_mode_save",
                    "Не удалось сохранить режим фильтрации",
                )
            )
        log_fn(f"V1 filter mode set: {target_key} = {new_mode}", "INFO")
        if has_fluent and info_bar_cls is not None:
            info_bar_cls.success(
                title=tr_fn("page.z1_strategy_detail.infobar.filter_mode.title", "Режим фильтрации"),
                content=tr_fn("page.z1_strategy_detail.filter.ipset", "IPset")
                if new_mode == "ipset"
                else tr_fn("page.z1_strategy_detail.filter.hostlist", "Hostlist"),
                parent=parent_window,
                duration=1500,
            )
    except Exception as exc:
        log_fn(f"V1 filter mode error: {exc}", "ERROR")
        if has_fluent and info_bar_cls is not None:
            info_bar_cls.error(
                title=tr_fn("common.error.title", "Ошибка"),
                content=str(exc),
                parent=parent_window,
            )
        sync_target_controls_fn()


def handle_enable_toggle_v1(
    *,
    direct_facade,
    target_key: str,
    enabled: bool,
    last_enabled_strategy_id: str,
    default_strategy_id_fn,
    enable_toggle,
    sync_target_controls_fn,
    select_strategy_fn,
    current_strategy_id: str,
    set_last_enabled_strategy_id_fn,
) -> None:
    if not direct_facade or not target_key:
        return

    plan = resolve_enable_toggle_plan_v1(
        enabled=enabled,
        last_enabled_strategy_id=last_enabled_strategy_id,
        default_strategy_id=default_strategy_id_fn(),
        current_strategy_id=current_strategy_id,
    )

    if plan.remember_last_enabled_strategy_id is not None:
        set_last_enabled_strategy_id_fn(plan.remember_last_enabled_strategy_id)

    if plan.should_restore_toggle_off:
        if enable_toggle is not None:
            enable_toggle.blockSignals(True)
            enable_toggle.setChecked(False)
            enable_toggle.blockSignals(False)
        sync_target_controls_fn()
        return

    if plan.should_select_strategy:
        select_strategy_fn(plan.strategy_id)


def handle_strategy_selection_v1(
    *,
    direct_facade,
    target_key: str,
    strategy_id: str,
    show_loading_fn,
    set_current_strategy_id_fn,
    set_last_enabled_strategy_id_fn,
    update_selected_label_fn,
    refresh_args_preview_fn,
    sync_target_controls_fn,
    apply_tree_selected_strategy_state_fn,
    tree,
    emit_strategy_selected_fn,
    log_fn,
    has_fluent: bool,
    info_bar_cls,
    tr_fn,
    strategy_display_name_fn,
    parent_window,
    show_success_fn,
    reload_target_fn,
) -> None:
    if not direct_facade or not target_key:
        return

    show_loading_fn()
    try:
        sid = persist_strategy_selection_v1(
            direct_facade,
            target_key=target_key,
            strategy_id=strategy_id,
        )

        set_current_strategy_id_fn(sid)
        if sid != "none":
            set_last_enabled_strategy_id_fn(sid)
        update_selected_label_fn()
        refresh_args_preview_fn()
        sync_target_controls_fn()

        apply_tree_selected_strategy_state_fn(
            tree,
            strategy_id=sid,
        )

        emit_strategy_selected_fn(target_key, sid)
        log_fn(f"V1 strategy set: {target_key} = {sid}", "INFO")

        if has_fluent and info_bar_cls is not None:
            info_bar_cls.success(
                title=tr_fn("page.z1_strategy_detail.infobar.strategy_applied", "Стратегия применена"),
                content=strategy_display_name_fn(sid),
                parent=parent_window,
                duration=1800,
            )

        show_success_fn()
    except Exception as exc:
        log_fn(f"V1 strategy selection error: {exc}", "ERROR")
        if has_fluent and info_bar_cls is not None:
            info_bar_cls.error(title="Ошибка", content=str(exc), parent=parent_window)
        reload_target_fn()
