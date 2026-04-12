"""Item-level actions workflow для страницы пользовательских пресетов Zapret 2."""

from __future__ import annotations


def toggle_pin_preset_action(
    *,
    name: str,
    resolve_display_name_fn,
    storage_api,
    refresh_presets_view_from_cache_fn,
    log_fn,
) -> None:
    try:
        display_name = resolve_display_name_fn(name)
        pinned = storage_api.toggle_preset_pin(name, display_name)
        log_fn(f"Пресет '{display_name}' {'закреплён' if pinned else 'откреплён'}", "INFO")
        refresh_presets_view_from_cache_fn()
    except Exception as exc:
        log_fn(f"Ошибка закрепления пресета: {exc}", "ERROR")


def move_preset_by_step_action(
    *,
    name: str,
    direction: int,
    storage_api,
    runtime_service,
    refresh_presets_view_from_cache_fn,
    log_fn,
) -> None:
    try:
        moved = storage_api.move_preset_by_step(
            name,
            direction,
            cached_metadata=runtime_service.cached_presets_metadata(),
        )
        if moved:
            refresh_presets_view_from_cache_fn()
    except Exception as exc:
        log_fn(f"Ошибка перестановки пресета: {exc}", "ERROR")


def handle_item_dropped_action(
    *,
    source_kind: str,
    source_id: str,
    target_kind: str,
    target_id: str,
    storage_api,
    runtime_service,
    refresh_presets_view_from_cache_fn,
    log_fn,
) -> None:
    try:
        moved = storage_api.move_preset_on_drop(
            source_kind=source_kind,
            source_id=source_id,
            target_kind=target_kind,
            target_id=target_id,
            cached_metadata=runtime_service.cached_presets_metadata(),
        )
        if moved:
            log_fn(f"Элемент '{source_id}' перенесён перетаскиванием", "INFO")
            refresh_presets_view_from_cache_fn()
    except Exception as exc:
        log_fn(f"Ошибка перетаскивания элемента: {exc}", "ERROR")


def activate_preset_action(
    *,
    name: str,
    resolve_display_name_fn,
    actions_api,
    runtime_service,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    display_name = resolve_display_name_fn(name)
    result = actions_api.activate_preset(file_name=name, display_name=display_name)
    log_fn(result.log_message, result.log_level)
    if result.ok and result.activated_file_name:
        runtime_service.apply_active_preset_marker_for_target(result.activated_file_name)
        return

    if result.infobar_level == "error":
        info_bar_cls.error(
            title=result.infobar_title or tr_fn("common.error.title", "Ошибка"),
            content=result.infobar_content,
            parent=parent_window,
        )


def open_edit_preset_menu_action(
    *,
    page,
    name: str,
    global_pos,
    is_builtin_preset_file_fn,
    tr_fn,
    make_menu_action,
    fluent_icon,
    round_menu_cls,
    on_preset_list_action_fn,
    show_preset_actions_menu_fn,
) -> None:
    is_builtin = is_builtin_preset_file_fn(name)
    chosen = show_preset_actions_menu_fn(
        page,
        global_pos=global_pos,
        is_builtin=is_builtin,
        labels={
            "open": tr_fn("page.z2_user_presets.menu.open", "Открыть"),
            "rating": tr_fn("page.z2_user_presets.menu.rating", "Рейтинг"),
            "move_up": tr_fn("page.z2_user_presets.menu.move_up", "Переместить выше"),
            "move_down": tr_fn("page.z2_user_presets.menu.move_down", "Переместить ниже"),
            "rename": tr_fn("page.z2_user_presets.menu.rename", "Переименовать"),
            "duplicate": tr_fn("page.z2_user_presets.menu.duplicate", "Дублировать"),
            "export": tr_fn("page.z2_user_presets.menu.export", "Экспорт"),
            "reset": tr_fn("page.z2_user_presets.menu.reset", "Сбросить"),
            "delete": tr_fn("page.z2_user_presets.menu.delete", "Удалить"),
        },
        make_menu_action=make_menu_action,
        icon_resolver=fluent_icon,
        round_menu_cls=round_menu_cls,
    )
    if chosen:
        on_preset_list_action_fn(chosen, name)


def show_rating_menu_action(
    *,
    page,
    name: str,
    global_pos,
    resolve_display_name_fn,
    hierarchy_store,
    refresh_callback,
    tr_fn,
    show_preset_rating_menu_fn,
) -> None:
    display_name = resolve_display_name_fn(name)
    show_preset_rating_menu_fn(
        page,
        preset_file_name=name,
        display_name=display_name,
        hierarchy_store=hierarchy_store,
        refresh_callback=refresh_callback,
        clear_label=tr_fn("page.z2_user_presets.menu.rating_clear", "Сбросить рейтинг"),
        global_pos=global_pos,
    )


def rename_preset_action(
    *,
    name: str,
    is_builtin_preset_file_fn,
    show_inline_action_rename_fn,
    info_bar_cls,
    tr_fn,
    parent_window,
) -> None:
    if is_builtin_preset_file_fn(name):
        info_bar_cls.warning(
            title=tr_fn("common.error.title", "Ошибка"),
            content="Встроенный пресет нельзя переименовать. Создайте копию, если нужен свой вариант.",
            parent=parent_window,
        )
        return
    show_inline_action_rename_fn(name)


def duplicate_preset_action(
    *,
    name: str,
    resolve_display_name_fn,
    actions_api,
    runtime_service,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    try:
        display_name = resolve_display_name_fn(name)
        result = actions_api.duplicate_preset(file_name=name, display_name=display_name)
        if result.structure_changed:
            runtime_service.mark_presets_structure_changed()
        log_fn(result.log_message, result.log_level)
    except Exception as exc:
        log_fn(f"Ошибка дублирования пресета: {exc}", "ERROR")
        info_bar_cls.error(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.z2_user_presets.error.generic", "Ошибка: {error}", error=exc),
            parent=parent_window,
        )


def reset_preset_action(
    *,
    name: str,
    resolve_display_name_fn,
    actions_api,
    message_box_cls,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    try:
        display_name = resolve_display_name_fn(name)
        if message_box_cls:
            box = message_box_cls(
                tr_fn("page.z2_user_presets.dialog.reset_single.title", "Сбросить пресет?"),
                tr_fn(
                    "page.z2_user_presets.dialog.reset_single.body",
                    "Пресет '{name}' будет перезаписан данными из шаблона.\n"
                    "Все изменения в этом пресете будут потеряны.\n"
                    "Этот пресет станет активным и будет применен заново.",
                    name=display_name,
                ),
                parent_window,
            )
            box.yesButton.setText(
                tr_fn("page.z2_user_presets.dialog.reset_single.button", "Сбросить")
            )
            box.cancelButton.setText(
                tr_fn("page.z2_user_presets.dialog.button.cancel", "Отмена")
            )
            if not box.exec():
                return

        result = actions_api.reset_preset_to_template(file_name=name, display_name=display_name)
        log_fn(result.log_message, result.log_level)
    except Exception as exc:
        log_fn(f"Ошибка сброса пресета: {exc}", "ERROR")
        info_bar_cls.error(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.z2_user_presets.error.generic", "Ошибка: {error}", error=exc),
            parent=parent_window,
        )


def delete_preset_action(
    *,
    name: str,
    resolve_display_name_fn,
    storage_api,
    actions_api,
    runtime_service,
    message_box_cls,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    try:
        display_name = resolve_display_name_fn(name)
        if storage_api.is_builtin_preset_file(name):
            result = actions_api.delete_preset(file_name=name, display_name=display_name)
            if result.infobar_level == "warning":
                info_bar_cls.warning(
                    title=tr_fn("common.error.title", "Ошибка"),
                    content=result.infobar_content,
                    parent=parent_window,
                )
            return

        if message_box_cls:
            box = message_box_cls(
                tr_fn("page.z2_user_presets.dialog.delete_single.title", "Удалить пресет?"),
                tr_fn(
                    "page.z2_user_presets.dialog.delete_single.body",
                    "Пресет '{name}' будет удален из списка пользовательских пресетов.\n"
                    "Изменения в этом пресете будут потеряны.\n"
                    "Вернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
                    name=display_name,
                ),
                parent_window,
            )
            box.yesButton.setText(
                tr_fn("page.z2_user_presets.dialog.delete_single.button", "Удалить")
            )
            box.cancelButton.setText(
                tr_fn("page.z2_user_presets.dialog.button.cancel", "Отмена")
            )
            if not box.exec():
                return

        result = actions_api.delete_preset(file_name=name, display_name=display_name)
        if result.error_code == "not_found":
            log_fn(result.log_message, result.log_level)
            runtime_service.recover_missing_deleted_preset(name)
            return
        if result.structure_changed:
            runtime_service.mark_presets_structure_changed()
        log_fn(result.log_message, result.log_level)
    except Exception as exc:
        log_fn(f"Ошибка удаления пресета: {exc}", "ERROR")
        info_bar_cls.error(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.z2_user_presets.error.generic", "Ошибка: {error}", error=exc),
            parent=parent_window,
        )


def export_preset_action(
    *,
    page,
    name: str,
    resolve_display_name_fn,
    file_dialog_cls,
    actions_api,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    display_name = resolve_display_name_fn(name)
    file_path, _ = file_dialog_cls.getSaveFileName(
        page,
        tr_fn("page.z2_user_presets.file_dialog.export_title", "Экспортировать пресет"),
        f"{display_name}.txt",
        "Preset files (*.txt);;All files (*.*)",
    )
    if not file_path:
        return

    try:
        result = actions_api.export_preset(file_name=name, file_path=file_path, display_name=display_name)
        log_fn(result.log_message, result.log_level)
        if result.infobar_level == "success":
            info_bar_cls.success(
                title=result.infobar_title,
                content=result.infobar_content,
                parent=parent_window,
            )
    except Exception as exc:
        log_fn(f"Ошибка экспорта пресета: {exc}", "ERROR")
        info_bar_cls.error(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.z2_user_presets.error.generic", "Ошибка: {error}", error=exc),
            parent=parent_window,
        )


def restore_deleted_presets_action(
    *,
    actions_api,
    runtime_service,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    try:
        result = actions_api.restore_deleted_presets()
        if result.structure_changed:
            runtime_service.mark_presets_structure_changed()
        log_fn(result.log_message, result.log_level)
    except Exception as exc:
        log_fn(f"Ошибка восстановления удалённых пресетов: {exc}", "ERROR")
        info_bar_cls.error(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn(
                "page.z2_user_presets.error.restore_deleted",
                "Ошибка восстановления: {error}",
                error=exc,
            ),
            parent=parent_window,
        )


def open_presets_info_action(
    *,
    actions_api,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    result = actions_api.open_presets_info()
    log_fn(result.log_message, result.log_level)
    if (not result.ok) and result.infobar_level == "warning":
        info_bar_cls.warning(
            title=result.infobar_title or tr_fn("common.error.title", "Ошибка"),
            content=result.infobar_content,
            parent=parent_window,
        )


def open_new_configs_post_action(
    *,
    actions_api,
    info_bar_cls,
    tr_fn,
    parent_window,
    log_fn,
) -> None:
    result = actions_api.open_new_configs_post()
    log_fn(result.log_message, result.log_level)
    if (not result.ok) and result.infobar_level == "warning":
        info_bar_cls.warning(
            title=result.infobar_title or tr_fn("common.error.title", "Ошибка"),
            content=result.infobar_content,
            parent=parent_window,
        )
