"""Selection/language helper слой для страницы direct target'ов Zapret 2."""

from __future__ import annotations

from ui.text_catalog import tr as tr_catalog


def apply_strategy_selection(
    *,
    target_key: str,
    strategy_id: str,
    target_selections: dict,
    targets_list,
    require_app_context,
    parent_app,
    strategy_selected_emit,
    strategies_changed_emit,
    log_info,
    log_error,
) -> tuple[dict, bool]:
    try:
        from core.presets.direct_facade import DirectPresetFacade
        from direct_launch.flow.apply_policy import request_direct_runtime_content_apply

        if (strategy_id or "").strip().lower() == "custom":
            new_selections = dict(target_selections or {})
            new_selections[target_key] = "custom"
            if targets_list:
                targets_list.update_selection(target_key, "custom")
            return new_selections, False

        direct_facade = DirectPresetFacade.from_launch_method(
            "direct_zapret2",
            app_context=require_app_context(),
            on_dpi_reload_needed=lambda: request_direct_runtime_content_apply(
                parent_app,
                launch_method="direct_zapret2",
                reason="strategy_changed",
            ),
        )
        direct_facade.set_strategy_selection(target_key, strategy_id, save_and_sync=True)

        new_selections = dict(target_selections or {})
        new_selections[target_key] = strategy_id
        if targets_list:
            targets_list.update_selection(target_key, strategy_id)

        strategy_selected_emit(target_key, strategy_id)
        strategies_changed_emit(new_selections)
        log_info(f"Выбрана стратегия: {target_key} = {strategy_id}")
        return new_selections, True
    except Exception as exc:
        log_error(f"Ошибка сохранения выбора: {exc}")
        return dict(target_selections or {}), False


def apply_filter_mode_change(
    *,
    target_key: str,
    filter_mode: str,
    targets_list,
    log_debug,
) -> bool:
    try:
        if targets_list:
            targets_list.update_filter_mode(target_key, filter_mode)
        return True
    except Exception as exc:
        log_debug(f"Ошибка обновления filter_mode: {exc}")
        return False


def update_current_strategies_display(
    *,
    target_selections: dict,
    ui_language: str,
    current_strategy_label,
    log_debug,
) -> None:
    try:
        selections = dict(target_selections or {})
        active_count = sum(1 for s in selections.values() if s and s != "none")

        if active_count > 0:
            current_strategy_label.setText(
                tr_catalog(
                    "page.z2_direct.current.active_count",
                    language=ui_language,
                    default="{count} активных",
                ).format(count=active_count)
            )
        else:
            current_strategy_label.setText(
                tr_catalog(
                    "page.z2_direct.current.not_selected",
                    language=ui_language,
                    default="Не выбрана",
                )
            )
    except Exception as exc:
        log_debug(f"Ошибка обновления отображения: {exc}")


def apply_direct_z2_language(
    *,
    ui_language: str,
    rebuild_breadcrumb,
    request_btn,
    expand_btn,
    collapse_btn,
    info_btn,
    update_current_strategies_display,
) -> None:
    rebuild_breadcrumb()

    if request_btn is not None:
        request_btn.setText(
            tr_catalog("page.z2_direct.request.button", language=ui_language, default="ОТКРЫТЬ ФОРМУ НА GITHUB")
        )
        request_btn.setToolTip(
            tr_catalog(
                "page.z2_direct.request.hint",
                language=ui_language,
                default=(
                    "Хотите добавить новый сайт или сервис в Zapret 2? "
                    "Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset."
                ),
            )
        )
    if expand_btn is not None:
        expand_btn.setText(
            tr_catalog("page.z2_direct.toolbar.expand", language=ui_language, default="Развернуть")
        )
        expand_btn.setToolTip(
            tr_catalog(
                "page.z2_direct.toolbar.expand.description",
                language=ui_language,
                default="Развернуть все категории и target'ы в списке.",
            )
        )
    if collapse_btn is not None:
        collapse_btn.setText(
            tr_catalog("page.z2_direct.toolbar.collapse", language=ui_language, default="Свернуть")
        )
        collapse_btn.setToolTip(
            tr_catalog(
                "page.z2_direct.toolbar.collapse.description",
                language=ui_language,
                default="Свернуть все категории и target'ы в списке.",
            )
        )
    if info_btn is not None:
        info_btn.setText(
            tr_catalog("page.z2_direct.toolbar.info", language=ui_language, default="Что это такое?")
        )
        info_btn.setToolTip(
            tr_catalog(
                "page.z2_direct.toolbar.info.description",
                language=ui_language,
                default="Показать краткое объяснение по работе прямого запуска Zapret 2.",
            )
        )

    update_current_strategies_display()
