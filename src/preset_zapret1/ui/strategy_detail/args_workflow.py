"""Args workflow helper'ы для страницы деталей стратегии Zapret 1."""

from __future__ import annotations


def open_args_editor_dialog_v1(
    *,
    has_fluent: bool,
    current_strategy_id: str,
    get_current_args_fn,
    parent,
    language: str,
    run_args_editor_dialog_fn,
    apply_args_fn,
    log_fn,
) -> None:
    if not has_fluent or (current_strategy_id or "none") == "none":
        return
    try:
        edited_text = run_args_editor_dialog_fn(
            initial_text=get_current_args_fn(),
            parent=parent,
            language=language,
        )
        if edited_text is not None:
            apply_args_fn(edited_text.strip())
    except Exception as exc:
        log_fn(f"Zapret1StrategyDetailPage: args editor error: {exc}", "ERROR")


def save_custom_args_v1(
    *,
    direct_facade,
    target_key: str,
    args_text: str,
    load_target_payload_sync_fn,
    set_current_strategy_id_fn,
    set_last_enabled_strategy_id_fn,
    emit_strategy_selected_fn,
    sync_target_controls_fn,
    has_fluent: bool,
    info_bar_cls,
    tr_fn,
    parent_window,
    request_target_payload_fn,
    log_fn,
) -> None:
    if not direct_facade or not target_key:
        return

    try:
        if not direct_facade.update_target_raw_args_text(
            target_key,
            args_text,
            save_and_sync=True,
        ):
            return

        payload = load_target_payload_sync_fn(target_key, refresh=True)
        current_strategy_id = (
            str(getattr(getattr(payload, "details", None), "current_strategy", "none") or "none")
            if payload is not None
            else "none"
        )
        set_current_strategy_id_fn(current_strategy_id)
        if current_strategy_id != "none":
            set_last_enabled_strategy_id_fn(current_strategy_id)
        emit_strategy_selected_fn(target_key, current_strategy_id)
        sync_target_controls_fn()

        if has_fluent and info_bar_cls is not None:
            if args_text:
                info_bar_cls.success(
                    title=tr_fn("page.z1_strategy_detail.infobar.args_saved.title", "Аргументы сохранены"),
                    content=tr_fn(
                        "page.z1_strategy_detail.infobar.args_saved.content",
                        "Пользовательские аргументы применены",
                    ),
                    parent=parent_window,
                    duration=1800,
                )
            else:
                info_bar_cls.success(
                    title=tr_fn("page.z1_strategy_detail.infobar.args_cleared.title", "Аргументы очищены"),
                    content=tr_fn(
                        "page.z1_strategy_detail.infobar.args_cleared.content",
                        "Target возвращён в режим 'Выключено'",
                    ),
                    parent=parent_window,
                    duration=1800,
                )

        request_target_payload_fn(target_key, refresh=True, reason="args_saved")
    except Exception as exc:
        log_fn(f"V1 save custom args error: {exc}", "ERROR")
        if has_fluent and info_bar_cls is not None:
            info_bar_cls.error(
                title=tr_fn("common.error.title", "Ошибка"),
                content=str(exc),
                parent=parent_window,
            )
