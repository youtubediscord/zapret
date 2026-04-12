"""Lifecycle/theme/language helper'ы для canonical Hosts страницы."""

from __future__ import annotations


def apply_hosts_page_theme(
    *,
    services_section_title_labels,
    service_group_chips_scrolls,
    service_group_chip_buttons,
    get_fluent_chip_style_fn,
    update_ui_fn,
    get_theme_tokens_fn,
) -> None:
    tokens = get_theme_tokens_fn()

    for label in list(services_section_title_labels):
        try:
            label.setStyleSheet(
                f"color: {tokens.fg_muted}; font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;"
            )
        except Exception:
            pass

    chips_qss = (
        "QScrollArea { background: transparent; border: none; }"
        "QScrollArea QWidget { background: transparent; }"
        "QScrollBar:horizontal { height: 4px; background: transparent; margin: 0px; }"
        f"QScrollBar::handle:horizontal {{ background: {tokens.scrollbar_handle}; border-radius: 2px; min-width: 24px; }}"
        f"QScrollBar::handle:horizontal:hover {{ background: {tokens.scrollbar_handle_hover}; }}"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; background: transparent; border: none; }"
        "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
    )
    for scroll in list(service_group_chips_scrolls):
        try:
            scroll.setStyleSheet(chips_qss)
        except Exception:
            pass

    chip_qss = get_fluent_chip_style_fn(tokens)
    for btn in list(service_group_chip_buttons):
        try:
            btn.setStyleSheet(chip_qss)
        except Exception:
            pass

    try:
        update_ui_fn()
    except Exception:
        pass


def activate_hosts_page(
    *,
    install_main_window_event_filter_fn,
    build_activation_plan_fn,
    catalog_dirty: bool,
    reconcile_hidden_refresh_fn,
    invalidate_cache_fn,
    update_ui_fn,
) -> None:
    install_main_window_event_filter_fn()
    activation_plan = build_activation_plan_fn(
        catalog_dirty=catalog_dirty,
    )

    if activation_plan.reconcile_hidden_refresh:
        reconcile_hidden_refresh_fn()
    if activation_plan.invalidate_cache:
        invalidate_cache_fn()
    if activation_plan.update_ui:
        update_ui_fn()


def run_hosts_runtime_init_once(
    *,
    runtime_initialized: bool,
    set_runtime_initialized_fn,
    install_main_window_event_filter_fn,
    ensure_ipv6_catalog_sections_fn,
    build_page_init_plan_fn,
    has_hosts_manager: bool,
    init_hosts_manager_fn,
    check_access_fn,
    rebuild_services_fn,
    mark_startup_initialized_fn,
    invalidate_cache_fn,
    update_ui_fn,
) -> None:
    if runtime_initialized:
        return
    set_runtime_initialized_fn(True)
    install_main_window_event_filter_fn()

    ipv6_catalog_changed, _ = ensure_ipv6_catalog_sections_fn()
    init_plan = build_page_init_plan_fn(
        runtime_initialized=False,
        has_hosts_manager=has_hosts_manager,
        ipv6_catalog_changed=ipv6_catalog_changed,
    )

    if init_plan.init_hosts_manager:
        init_hosts_manager_fn()
    if init_plan.check_access:
        check_access_fn()
    if init_plan.rebuild_services:
        rebuild_services_fn()
    if init_plan.mark_initialized:
        mark_startup_initialized_fn()
    if init_plan.invalidate_cache:
        invalidate_cache_fn()
    if init_plan.update_ui:
        update_ui_fn()


def install_main_window_event_filter(
    *,
    page,
    current_main_window,
    set_main_window_fn,
) -> None:
    try:
        window = page.window()
    except Exception:
        window = None
    if not window or window is current_main_window:
        return

    if current_main_window is not None:
        try:
            current_main_window.removeEventFilter(page)
        except Exception:
            pass

    set_main_window_fn(window)
    try:
        window.installEventFilter(page)
    except Exception:
        pass


def close_service_combo_popups(service_combos: dict) -> None:
    for control in list(service_combos.values()):
        if control is None:
            continue
        try:
            if hasattr(control, "_closeComboMenu"):
                control._closeComboMenu()
            elif hasattr(control, "hidePopup"):
                control.hidePopup()
        except Exception:
            pass


def apply_hosts_page_language(
    *,
    tr_fn,
    clear_btn,
    open_hosts_button,
    info_text_label,
    browser_warning_label,
    adobe_desc_label,
    adobe_title_label,
    startup_initialized: bool,
    applying: bool,
    rebuild_services_selectors_fn,
    check_hosts_access_fn,
    update_ui_fn,
) -> None:
    if clear_btn is not None:
        clear_btn.setText(tr_fn("page.hosts.button.clear", " Очистить"))

    if open_hosts_button is not None:
        open_hosts_button.setText(tr_fn("page.hosts.button.open", " Открыть"))

    if info_text_label is not None:
        info_text_label.setText(
            tr_fn(
                "page.hosts.info.note",
                "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — это не блокировка РКН. Решается не через Zapret, а через проксирование: домены направляются через отдельный прокси-сервер в файле hosts.",
            )
        )

    if browser_warning_label is not None:
        browser_warning_label.setText(
            tr_fn(
                "page.hosts.warning.browser_restart",
                "После добавления или удаления доменов необходимо перезапустить браузер, чтобы изменения вступили в силу.",
            )
        )

    if adobe_desc_label is not None:
        adobe_desc_label.setText(
            tr_fn(
                "page.hosts.adobe.description",
                "⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.",
            )
        )
    if adobe_title_label is not None:
        adobe_title_label.setText(tr_fn("page.hosts.adobe.title", "Блокировка Adobe"))

    if startup_initialized and not applying:
        rebuild_services_selectors_fn()
        check_hosts_access_fn()

    update_ui_fn()


def cleanup_hosts_page(
    *,
    set_cleanup_in_progress_fn,
    current_main_window,
    set_main_window_fn,
    page,
    catalog_watch_timer,
    set_catalog_watch_timer_fn,
    thread,
    worker,
    set_worker_fn,
    set_thread_fn,
    log_fn,
) -> None:
    set_cleanup_in_progress_fn(True)
    if current_main_window is not None:
        try:
            current_main_window.removeEventFilter(page)
        except Exception:
            pass
        set_main_window_fn(None)

    if catalog_watch_timer is not None:
        try:
            catalog_watch_timer.stop()
            catalog_watch_timer.deleteLater()
        except Exception:
            pass
        set_catalog_watch_timer_fn(None)

    if thread and thread.isRunning():
        log_fn("Останавливаем hosts worker...", "DEBUG")
        if worker is not None:
            stop = getattr(worker, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass
        thread.quit()
        if not thread.wait(2000):
            log_fn("⚠ Hosts worker не завершился, принудительно завершаем", "WARNING")
            try:
                thread.terminate()
                thread.wait(500)
            except Exception:
                pass

    set_worker_fn(None)
    set_thread_fn(None)
