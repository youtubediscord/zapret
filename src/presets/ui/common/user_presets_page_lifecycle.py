"""Lifecycle/theme/language helper'ы общей страницы пользовательских preset-ов."""

from __future__ import annotations

import time

from qfluentwidgets import FluentIcon

from ui.fluent_widgets import set_tooltip


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
    apply_mode_labels_fn,
    resync_layout_metrics_fn,
    start_watching_presets_fn,
    runtime_service,
    refresh_presets_view_if_possible_fn,
    update_presets_view_height_fn,
    schedule_layout_resync_fn,
) -> None:
    if cleanup_in_progress:
        return
    try:
        start_watching_presets_fn()
    except Exception:
        pass
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
    connect_preset_signals_fn,
    on_store_changed_fn,
    on_store_switched_fn,
    on_store_content_changed_fn,
    log_fn,
    log_prefix: str,
) -> None:
    started_at = time.perf_counter()
    apply_page_theme_fn(force=True)

    try:
        connect_preset_signals_fn(
            on_changed=on_store_changed_fn,
            on_switched=on_store_switched_fn,
            on_identity_changed=on_store_switched_fn,
            on_content_changed=on_store_content_changed_fn,
        )
    except Exception:
        pass
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    log_fn(f"{log_prefix}: lazy ui init {elapsed_ms}ms", "DEBUG")


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
            fields={
                "preset_structure_revision",
                "launch_method",
                "launch_running",
                "launch_busy",
                "launch_busy_text",
                "last_status_message",
            },
            emit_initial=True,
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
                reset_all_btn.setIcon(FluentIcon.RETURN)
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
    configs_title_label,
    get_configs_btn,
    create_btn,
    import_btn,
    open_folder_btn,
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
    tr_prefix: str,
) -> None:
    apply_mode_labels_fn()

    if configs_title_label is not None:
        configs_title_label.setText(
            tr_fn(
                f"{tr_prefix}.configs.title",
                "Обменивайтесь пресетами и профилями в разделе GitHub Discussions",
            )
        )
    if get_configs_btn is not None:
        get_configs_btn.setText(tr_fn(f"{tr_prefix}.configs.button", "Получить конфиги"))

    if create_btn is not None:
        set_tooltip(create_btn, tr_fn(f"{tr_prefix}.tooltip.create", "Создать новый пресет"))

    if import_btn is not None:
        import_btn.setText(tr_fn(f"{tr_prefix}.button.import", "Импорт"))
        set_tooltip(import_btn, tr_fn(f"{tr_prefix}.tooltip.import", "Импорт пресета из файла"))

    if open_folder_btn is not None:
        open_folder_btn.setText(tr_fn(f"{tr_prefix}.button.open_folder", "Открыть папку"))
        set_tooltip(
            open_folder_btn,
            tr_fn(f"{tr_prefix}.tooltip.open_folder", "Открыть папку, где лежат ваши пресеты"),
        )

    if reset_all_btn is not None:
        current_text = reset_all_btn.text() or ""
        if "/" not in current_text:
            reset_all_btn.setText(tr_fn(f"{tr_prefix}.button.reset_all", "Вернуть встроенные"))
        set_tooltip(
            reset_all_btn,
            tr_fn(
                f"{tr_prefix}.tooltip.reset_all",
                "Возвращает встроенные пресеты. Ваши изменения во встроенных пресетах будут потеряны.",
            ),
        )

    if presets_info_btn is not None:
        presets_info_btn.setText(tr_fn(f"{tr_prefix}.button.wiki", "Вики по пресетам"))
    if info_btn is not None:
        info_btn.setText(tr_fn(f"{tr_prefix}.button.what_is_this", "Что это такое?"))

    if preset_search_input is not None:
        preset_search_input.setPlaceholderText(
            tr_fn(f"{tr_prefix}.search.placeholder", "Поиск пресетов по имени...")
        )

    if presets_delegate is not None:
        presets_delegate.set_ui_language(ui_language)

    if toolbar_layout is not None:
        toolbar_layout.refresh_for_viewport(viewport.width(), layout.contentsMargins())
    refresh_presets_view_from_cache_fn()
