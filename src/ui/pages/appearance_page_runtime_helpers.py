"""Runtime/language helper слой для Appearance page."""

from __future__ import annotations

from app.ui_texts import normalize_language, tr as tr_catalog


def apply_appearance_language(
    *,
    language: str,
    begin_ui_sync,
    end_ui_sync,
    set_current_index_silently,
    language_desc_label,
    language_name_label,
    language_combo,
    accent_group,
    performance_group,
    accent_desc_label,
    accent_color_row,
    follow_windows_accent_cb,
    tinted_bg_cb,
    tinted_intensity_label,
    animations_switch,
    smooth_scroll_switch,
    editor_smooth_scroll_switch,
) -> None:
    if language_desc_label is not None:
        try:
            language_desc_label.setText(tr_catalog("appearance.language.desc", language=language))
        except Exception:
            pass

    if language_name_label is not None:
        try:
            language_name_label.setText(tr_catalog("appearance.language.label", language=language))
        except Exception:
            pass

    if language_combo is not None:
        try:
            normalized = normalize_language(language)
            idx = language_combo.findData(normalized)
            if idx >= 0:
                begin_ui_sync()
                set_current_index_silently(language_combo, idx)
        except Exception:
            pass
        finally:
            end_ui_sync()

    try:
        title_label = getattr(getattr(accent_group, "titleLabel", None), "setText", None)
        if title_label is not None:
            accent_group.titleLabel.setText(
                tr_catalog("page.appearance.section.accent", language=language, default="Акцентный цвет")
            )
    except Exception:
        pass

    try:
        title_label = getattr(getattr(performance_group, "titleLabel", None), "setText", None)
        if title_label is not None:
            performance_group.titleLabel.setText(
                tr_catalog("page.appearance.section.performance", language=language, default="Производительность")
            )
    except Exception:
        pass

    if accent_desc_label is not None:
        accent_desc_label.setText(
            tr_catalog(
                "page.appearance.accent.description",
                language=language,
                default=(
                    "Цвет акцентных элементов интерфейса: кнопок, иконок, индикаторов. "
                    "Изменяет цвет нативных компонентов WinUI."
                ),
            )
        )

    if accent_color_row is not None:
        accent_color_row.set_title(
            tr_catalog("page.appearance.accent.color.title", language=language, default="Цвет акцента")
        )

    if follow_windows_accent_cb is not None:
        follow_windows_accent_cb.set_texts(
            tr_catalog("page.appearance.accent.windows.title", language=language, default="Акцент из Windows"),
            tr_catalog(
                "page.appearance.accent.windows.description",
                language=language,
                default="Автоматически использовать системный акцентный цвет Windows",
            ),
        )

    if tinted_bg_cb is not None:
        tinted_bg_cb.set_texts(
            tr_catalog(
                "page.appearance.accent.tint_background.title",
                language=language,
                default="Тонировать фон акцентным цветом",
            ),
            tr_catalog(
                "page.appearance.accent.tint_background.description",
                language=language,
                default="Фон окна окрашивается в оттенок акцентного цвета",
            ),
        )

    if tinted_intensity_label is not None:
        tinted_intensity_label.setText(
            tr_catalog(
                "page.appearance.accent.tint_intensity.label",
                language=language,
                default="Интенсивность тонировки:",
            )
        )

    if animations_switch is not None:
        animations_switch.set_texts(
            tr_catalog("page.appearance.performance.animations.title", language=language, default="Анимации интерфейса"),
            tr_catalog(
                "page.appearance.performance.animations.description",
                language=language,
                default="Анимации кнопок, переходов и элементов WinUI",
            ),
        )

    if smooth_scroll_switch is not None:
        smooth_scroll_switch.set_texts(
            tr_catalog("page.appearance.performance.scroll.title", language=language, default="Плавная прокрутка"),
            tr_catalog(
                "page.appearance.performance.scroll.description",
                language=language,
                default="Инерционная прокрутка страниц настроек",
            ),
        )

    if editor_smooth_scroll_switch is not None:
        editor_smooth_scroll_switch.set_texts(
            tr_catalog(
                "page.appearance.performance.editor_scroll.title",
                language=language,
                default="Плавная прокрутка редакторов",
            ),
            tr_catalog(
                "page.appearance.performance.editor_scroll.description",
                language=language,
                default="Плавная прокрутка внутри больших текстовых полей и редакторов. Работает только при включённых анимациях интерфейса.",
            ),
        )
