"""Lifecycle/theme/language helper'ы для страницы пользовательских пресетов Zapret 2."""

from __future__ import annotations

import time

from ui.compat_widgets import set_tooltip


def handle_user_presets_ui_state_changed(
    *,
    cleanup_in_progress: bool,
    runtime_service,
    state,
    changed_fields: frozenset[str],
) -> None:
    if cleanup_in_progress:
        return
    runtime_service.on_ui_state_changed(state, changed_fields)


def activate_user_presets_page(
    *,
    cleanup_in_progress: bool,
    rebuild_breadcrumb_fn,
    apply_mode_labels_fn,
    resync_layout_metrics_fn,
    runtime_service,
    refresh_presets_view_if_possible_fn,
    update_presets_view_height_fn,
    schedule_layout_resync_fn,
) -> None:
    if cleanup_in_progress:
        return
    rebuild_breadcrumb_fn()
    apply_mode_labels_fn()
    resync_layout_metrics_fn()
    if runtime_service.is_ui_dirty():
        refresh_presets_view_if_possible_fn()
    else:
        update_presets_view_height_fn()
    schedule_layout_resync_fn(include_delayed=True)


def after_user_presets_ui_built(
    *,
    apply_page_theme_fn,
    get_preset_store_fn,
    on_store_changed_fn,
    on_store_switched_fn,
    on_store_updated_fn,
    start_watching_presets_fn,
    log_fn,
) -> None:
    started_at = time.perf_counter()
    apply_page_theme_fn(force=True)

    try:
        store = get_preset_store_fn()
        store.presets_changed.connect(on_store_changed_fn)
        store.preset_switched.connect(on_store_switched_fn)
        store.preset_identity_changed.connect(on_store_switched_fn)
        store.preset_updated.connect(on_store_updated_fn)
    except Exception:
        pass
    try:
        start_watching_presets_fn()
    except Exception:
        pass

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    log_fn(f"Z2UserPresetsPage: lazy ui init {elapsed_ms}ms", "DEBUG")


def bind_user_presets_ui_state_store(
    *,
    current_store,
    store,
    current_unsubscribe,
    set_store_fn,
    set_unsubscribe_fn,
    on_ui_state_changed_fn,
) -> None:
    if current_store is store:
        return

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass

    set_store_fn(store)
    set_unsubscribe_fn(
        store.subscribe(
            on_ui_state_changed_fn,
            fields={"preset_structure_revision"},
            emit_initial=False,
        )
    )


def schedule_user_presets_layout_resync(
    *,
    cleanup_in_progress: bool,
    layout_resync_timer,
    layout_resync_delayed_timer,
    include_delayed: bool = False,
) -> None:
    if cleanup_in_progress:
        return
    layout_resync_timer.start(0)
    if include_delayed:
        layout_resync_delayed_timer.start(220)


def resync_user_presets_layout_metrics(
    *,
    cleanup_in_progress: bool,
    toolbar_layout,
    viewport,
    layout,
    update_presets_view_height_fn,
) -> None:
    if cleanup_in_progress:
        return
    if toolbar_layout is not None:
        toolbar_layout.refresh_for_viewport(viewport.width(), layout.contentsMargins())
    update_presets_view_height_fn()


def apply_user_presets_page_theme(
    *,
    get_theme_tokens_fn,
    get_semantic_palette_fn,
    get_cached_qta_pixmap_fn,
    get_themed_qta_icon_fn,
    schedule_layout_resync_fn,
    configs_icon,
    reset_all_btn,
    presets_list,
    previous_theme_key,
    force: bool = False,
    log_fn=None,
):
    try:
        tokens = get_theme_tokens_fn()
        theme_key = (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.surface_bg))
        if not force and theme_key == previous_theme_key:
            return previous_theme_key

        _ = get_semantic_palette_fn(tokens.theme_name)

        if configs_icon is not None:
            configs_icon.setPixmap(get_cached_qta_pixmap_fn("fa5b.github", color=tokens.accent_hex, size=18))

        if reset_all_btn is not None:
            try:
                reset_all_btn.setIcon(get_themed_qta_icon_fn("fa5s.undo", color=tokens.fg))
            except Exception:
                pass

        if presets_list is not None:
            presets_list.viewport().update()

        schedule_layout_resync_fn()
        return theme_key
    except Exception as exc:
        if log_fn is not None:
            log_fn(f"Ошибка применения темы на странице пресетов: {exc}", "DEBUG")
        return previous_theme_key


def cleanup_user_presets_page(
    *,
    set_cleanup_in_progress_fn,
    layout_resync_timer,
    layout_resync_delayed_timer,
    preset_search_timer,
    current_unsubscribe,
    set_unsubscribe_fn,
    set_store_fn,
    stop_watching_presets_fn,
) -> None:
    set_cleanup_in_progress_fn(True)

    for timer in (
        layout_resync_timer,
        layout_resync_delayed_timer,
        preset_search_timer,
    ):
        try:
            timer.stop()
        except Exception:
            pass

    if callable(current_unsubscribe):
        try:
            current_unsubscribe()
        except Exception:
            pass
    set_unsubscribe_fn(None)
    set_store_fn(None)

    try:
        stop_watching_presets_fn()
    except Exception:
        pass


def apply_user_presets_language(
    *,
    tr_fn,
    rebuild_breadcrumb_fn,
    back_btn,
    configs_title_label,
    get_configs_btn,
    restore_deleted_btn,
    create_btn,
    import_btn,
    reset_all_btn,
    presets_info_btn,
    info_btn,
    preset_search_input,
    presets_delegate,
    ui_language: str,
    viewport,
    layout,
    toolbar_layout,
    refresh_presets_view_from_cache_fn,
    apply_mode_labels_fn,
) -> None:
    apply_mode_labels_fn()

    if rebuild_breadcrumb_fn is not None:
        rebuild_breadcrumb_fn()
    elif back_btn is not None:
        back_btn.setText(tr_fn("page.z2_user_presets.back.control", "Управление"))

    if configs_title_label is not None:
        configs_title_label.setText(
            tr_fn(
                "page.z2_user_presets.configs.title",
                "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
            )
        )
    if get_configs_btn is not None:
        get_configs_btn.setText(tr_fn("page.z2_user_presets.configs.button", "Получить конфиги"))

    if restore_deleted_btn is not None:
        restore_deleted_btn.setText(
            tr_fn("page.z2_user_presets.button.restore_deleted", "Восстановить удалённые пресеты")
        )

    if create_btn is not None:
        set_tooltip(create_btn, tr_fn("page.z2_user_presets.tooltip.create", "Создать новый пресет"))

    if import_btn is not None:
        import_btn.setText(tr_fn("page.z2_user_presets.button.import", "Импорт"))
        set_tooltip(import_btn, tr_fn("page.z2_user_presets.tooltip.import", "Импорт пресета из файла"))

    if reset_all_btn is not None:
        current_text = reset_all_btn.text() or ""
        if "/" not in current_text:
            reset_all_btn.setText(tr_fn("page.z2_user_presets.button.reset_all", "Вернуть заводские"))
        set_tooltip(
            reset_all_btn,
            tr_fn(
                "page.z2_user_presets.tooltip.reset_all",
                "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
            ),
        )

    if presets_info_btn is not None:
        presets_info_btn.setText(tr_fn("page.z2_user_presets.button.wiki", "Вики по пресетам"))
    if info_btn is not None:
        info_btn.setText(tr_fn("page.z2_user_presets.button.what_is_this", "Что это такое?"))

    if preset_search_input is not None:
        preset_search_input.setPlaceholderText(
            tr_fn("page.z2_user_presets.search.placeholder", "Поиск пресетов по имени...")
        )

    if presets_delegate is not None:
        presets_delegate.set_ui_language(ui_language)

    if toolbar_layout is not None:
        toolbar_layout.refresh_for_viewport(viewport.width(), layout.contentsMargins())
    refresh_presets_view_from_cache_fn()
