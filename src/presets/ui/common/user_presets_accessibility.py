"""Accessibility helpers for user presets page controls."""

from __future__ import annotations

from ui.accessibility import set_control_accessibility


def apply_user_presets_accessibility(
    *,
    tr_fn,
    tr_prefix: str,
    get_configs_btn=None,
    create_btn=None,
    import_btn=None,
    open_folder_btn=None,
    reset_all_btn=None,
    presets_info_btn=None,
    info_btn=None,
    preset_search_input=None,
    presets_list=None,
) -> None:
    """Задаёт понятные имена элементам пользовательских пресетов для экранного диктора."""

    set_control_accessibility(
        get_configs_btn,
        name=tr_fn(f"{tr_prefix}.configs.accessible_name", "Открыть GitHub Discussions с конфигами"),
        description=tr_fn(
            f"{tr_prefix}.configs.title",
            "Обменивайтесь пресетами и профилями в разделе GitHub Discussions",
        ),
    )
    set_control_accessibility(
        create_btn,
        name=tr_fn(f"{tr_prefix}.create.accessible_name", "Создать новый пресет"),
        description=tr_fn(f"{tr_prefix}.tooltip.create", "Создать новый пресет"),
    )
    set_control_accessibility(
        import_btn,
        name=tr_fn(f"{tr_prefix}.import.accessible_name", "Импортировать пресет из файла"),
        description=tr_fn(f"{tr_prefix}.tooltip.import", "Импорт пресета из файла"),
    )
    set_control_accessibility(
        open_folder_btn,
        name=tr_fn(f"{tr_prefix}.open_folder.accessible_name", "Открыть папку пресетов"),
        description=tr_fn(f"{tr_prefix}.tooltip.open_folder", "Открыть папку, где лежат ваши пресеты"),
    )
    set_control_accessibility(
        reset_all_btn,
        name=tr_fn(f"{tr_prefix}.reset_all.accessible_name", "Вернуть встроенные пресеты"),
        description=tr_fn(
            f"{tr_prefix}.tooltip.reset_all",
            "Возвращает встроенные пресеты. Ваши изменения во встроенных пресетах будут потеряны.",
        ),
    )
    set_control_accessibility(
        presets_info_btn,
        name=tr_fn(f"{tr_prefix}.wiki.accessible_name", "Открыть вики по пресетам"),
        description=tr_fn(f"{tr_prefix}.button.wiki", "Вики по пресетам"),
    )
    set_control_accessibility(
        info_btn,
        name=tr_fn(f"{tr_prefix}.info.accessible_name", "Показать справку о пресетах"),
        description=tr_fn(f"{tr_prefix}.button.what_is_this", "Что это такое?"),
    )
    set_control_accessibility(
        preset_search_input,
        name=tr_fn(f"{tr_prefix}.search.accessible_name", "Поиск пресетов"),
        description=tr_fn(f"{tr_prefix}.search.placeholder", "Поиск пресетов по имени..."),
    )
    set_control_accessibility(
        presets_list,
        name=tr_fn(f"{tr_prefix}.list.accessible_name", "Список пользовательских пресетов"),
        description=tr_fn(
            f"{tr_prefix}.list.accessible_description",
            "Стрелки выбирают пресет, Enter делает выбранный пресет активным",
        ),
    )


__all__ = ["apply_user_presets_accessibility"]
