from __future__ import annotations

from log.log import log

from filters.strategy_detail.zapret2.controller import StrategyDetailPageController
from filters.ui.strategy_detail.zapret2.apply import (
    apply_args_editor_state,
    apply_filter_mode_selector_state,
    apply_tree_selected_strategy_state,
)
from filters.ui.strategy_detail.zapret2.args_editor import (
    hide_args_editor_state,
    open_args_editor_dialog,
    refresh_args_editor_state,
)
from filters.ui.strategy_detail.zapret2.preset_workflow import (
    present_preset_action_result,
    present_preset_exception,
    prompt_preset_name,
)


def refresh_args_editor_state_runtime(page) -> None:
    refresh_args_editor_state(
        edit_args_btn=getattr(page, "_edit_args_btn", None),
        target_key=page._target_key,
        selected_strategy_id=page._selected_strategy_id,
        build_state_plan_fn=StrategyDetailPageController.build_args_editor_state_plan,
        apply_args_editor_state_fn=apply_args_editor_state,
        hide_editor_fn=page._hide_args_editor,
    )


def toggle_args_editor_runtime(page) -> None:
    open_args_editor_dialog(
        build_open_plan_fn=page._build_args_editor_open_plan,
        parent=page.window(),
        language=page._ui_language,
        run_args_editor_dialog_fn=page._run_args_editor_dialog_fn,
        apply_args_fn=page._apply_args_editor,
    )


def hide_args_editor_runtime(page, clear_text: bool = False) -> None:
    page._args_editor_dirty = hide_args_editor_state(clear_text=clear_text)


def on_args_changed_runtime(page, strategy_id: str, args: list) -> None:
    if page._cleanup_in_progress:
        return
    if page._target_key:
        page.args_changed.emit(page._target_key, strategy_id, args)
        log(f"Args changed: {page._target_key}/{strategy_id} = {args}", "DEBUG")


def build_args_editor_open_plan(page):
    return StrategyDetailPageController.build_args_editor_open_plan(
        page._direct_facade,
        payload=getattr(page, "_target_payload", None),
        target_key=page._target_key,
        selected_strategy_id=page._selected_strategy_id,
    )


def apply_args_editor_runtime(page, raw: str = "") -> None:
    apply_plan = StrategyDetailPageController.build_args_apply_plan(
        target_key=page._target_key,
        selected_strategy_id=page._selected_strategy_id,
        raw_text=raw,
    )
    if not apply_plan.should_apply:
        return

    try:
        if not page._write_target_raw_args_text(
            page._target_key,
            apply_plan.normalized_text,
            save_and_sync=True,
        ):
            return
        page._preset_refresh_runtime.mark_suppressed()
        payload = page._reload_current_target_payload()
        result_plan = StrategyDetailPageController.build_args_apply_result_plan(payload=payload)
        page._selected_strategy_id = result_plan.selected_strategy_id
        page._current_strategy_id = result_plan.current_strategy_id
        page._args_editor_dirty = False
        if result_plan.should_show_loading:
            page.show_loading()
        if result_plan.should_emit_args_changed:
            page._on_args_changed(page._selected_strategy_id, apply_plan.args_lines)

    except Exception as e:
        log(f"Args editor: failed to save args: {e}", "ERROR")


def create_preset_from_current(page, name: str):
    return StrategyDetailPageController.create_preset(page._direct_facade, name=name)


def rename_current_preset(page, *, old_file_name: str, old_name: str, new_name: str):
    return StrategyDetailPageController.rename_preset(
        page._direct_facade,
        old_file_name=old_file_name,
        old_name=old_name,
        new_name=new_name,
    )


def on_create_preset_clicked(page, *, info_bar_cls, dialog_cls) -> None:
    name = prompt_preset_name(
        dialog_cls=dialog_cls,
        mode="create",
        parent=page.window(),
        language=page._ui_language,
    )
    if not name:
        return
    try:
        result = create_preset_from_current(page, name)
        present_preset_action_result(
            result,
            info_bar=info_bar_cls,
            parent=page.window(),
            log_fn=log,
            on_structure_changed=page._notify_preset_structure_changed,
        )
    except Exception as e:
        present_preset_exception(
            action_error_message="Ошибка создания пресета",
            exception=e,
            info_bar=info_bar_cls,
            parent=page.window(),
            error_title=page._tr("common.error.title", "Ошибка"),
            log_fn=log,
        )


def on_rename_preset_clicked(page, *, info_bar_cls, dialog_cls) -> None:
    try:
        coordinator = page._require_app_context().direct_flow_coordinator
        old_file_name = (
            coordinator.get_selected_source_file_name("direct_zapret2") or ""
        ).strip()

        selected_manifest = coordinator.get_selected_source_manifest("direct_zapret2")
        old_name = str(selected_manifest.name if selected_manifest is not None else "").strip()
    except Exception as e:
        present_preset_exception(
            action_error_message="Ошибка подготовки переименования пресета",
            exception=e,
            info_bar=info_bar_cls,
            parent=page.window(),
            error_title=page._tr("common.error.title", "Ошибка"),
            log_fn=log,
        )
        return

    if not old_name or not old_file_name:
        result = StrategyDetailPageController.build_missing_active_preset_result()
        present_preset_action_result(
            result,
            info_bar=info_bar_cls,
            parent=page.window(),
            log_fn=log,
            on_structure_changed=page._notify_preset_structure_changed,
        )
        return

    new_name = prompt_preset_name(
        dialog_cls=dialog_cls,
        mode="rename",
        old_name=old_name,
        parent=page.window(),
        language=page._ui_language,
    )
    if not new_name or new_name == old_name:
        return
    try:
        result = rename_current_preset(
            page,
            old_file_name=old_file_name,
            old_name=old_name,
            new_name=new_name,
        )
        present_preset_action_result(
            result,
            info_bar=info_bar_cls,
            parent=page.window(),
            log_fn=log,
            on_structure_changed=page._notify_preset_structure_changed,
        )
    except Exception as e:
        present_preset_exception(
            action_error_message="Ошибка переименования пресета",
            exception=e,
            info_bar=info_bar_cls,
            parent=page.window(),
            error_title=page._tr("common.error.title", "Ошибка"),
            log_fn=log,
        )


def on_reset_settings_confirmed(page) -> None:
    if not page._target_key:
        return

    success = page._reset_target_settings(page._target_key)
    plan = StrategyDetailPageController.build_reset_settings_plan(target_key=page._target_key, success=success)
    log(plan.log_message, plan.log_level)
    if not plan.ok:
        return

    page._preset_refresh_runtime.mark_suppressed()
    payload = page._reload_current_target_payload() if plan.should_reload_payload else None

    if plan.should_apply_syndata_settings:
        page._apply_syndata_settings(page._load_syndata_settings(page._target_key))

    if plan.should_refresh_filter_mode and hasattr(page, "_filter_mode_frame") and page._filter_mode_frame.isVisible():
        current_mode = (
            str(getattr(payload, "filter_mode", "") or "").strip().lower()
            if payload is not None else page._load_target_filter_mode(page._target_key)
        )
        apply_filter_mode_selector_state(
            page._filter_mode_selector,
            mode=current_mode,
        )

    if plan.should_refresh_strategy_selection:
        current_strategy_id = (
            (getattr(payload.details, "current_strategy", "none") or "none")
            if payload is not None else "none"
        )

        page._selected_strategy_id = current_strategy_id or "none"
        page._current_strategy_id = current_strategy_id or "none"

        if page._tcp_phase_mode:
            page._load_tcp_phase_state_from_preset()
            page._apply_tcp_phase_tabs_visibility()
            page._select_default_tcp_phase_tab()
            page._apply_filters()
        else:
            apply_tree_selected_strategy_state(
                page._strategies_tree,
                strategy_id=page._selected_strategy_id,
            )

    if plan.should_show_loading:
        page.show_loading()
    page._update_selected_strategy_header(page._selected_strategy_id)
    if plan.should_refresh_args_editor:
        page._refresh_args_editor_state()
    if plan.should_refresh_target_enabled_ui:
        page._set_target_enabled_ui((page._selected_strategy_id or "none") != "none")


def confirm_reset_settings_clicked(page, *, message_box_cls) -> None:
    if message_box_cls is not None:
        try:
            box = message_box_cls(
                page._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки"),
                page._tr("page.z2_strategy_detail.button.reset_settings.confirm", "Сбросить все?"),
                page.window(),
            )
            if not box.exec():
                return
        except Exception:
            pass
    on_reset_settings_confirmed(page)
