"""Runtime/language helper слой для Appearance page."""

from __future__ import annotations

from PyQt6.QtGui import QColor

import settings.appearance as appearance_settings
from app.text_catalog import normalize_language, tr as tr_catalog


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


def load_accent_color(*, has_color_picker: bool, color_picker_btn, begin_ui_sync, end_ui_sync) -> None:
    if not has_color_picker or color_picker_btn is None:
        return
    plan = appearance_settings.load_accent_color()
    hex_color = plan.hex_color
    if hex_color:
        color = QColor(hex_color)
        if color.isValid():
            begin_ui_sync()
            try:
                color_picker_btn.setColor(color)
                from qfluentwidgets import setThemeColor

                setThemeColor(color)
            finally:
                end_ui_sync()


def load_extra_accent_settings(
    *,
    has_color_picker: bool,
    follow_windows_accent_cb,
    tinted_bg_cb,
    tinted_intensity_slider,
    tinted_intensity_value_label,
    tinted_intensity_container,
    color_picker_btn,
    set_checked_silently,
    set_slider_value_silently,
    apply_windows_accent,
) -> None:
    if not has_color_picker:
        return
    plan = appearance_settings.load_tinted_settings()

    if follow_windows_accent_cb is not None:
        set_checked_silently(follow_windows_accent_cb, plan.follow_windows_accent)

    if tinted_bg_cb is not None:
        set_checked_silently(tinted_bg_cb, plan.tinted_background)

    if tinted_intensity_slider is not None:
        set_slider_value_silently(tinted_intensity_slider, plan.tinted_intensity)

    if tinted_intensity_value_label is not None:
        tinted_intensity_value_label.setText(str(plan.tinted_intensity))

    if tinted_intensity_container is not None:
        tinted_intensity_container.setVisible(plan.tinted_background)

    if plan.follow_windows_accent:
        apply_windows_accent()
        if color_picker_btn is not None:
            color_picker_btn.setEnabled(False)


def load_performance_settings(
    *,
    animations_switch,
    smooth_scroll_switch,
    editor_smooth_scroll_switch,
    set_checked_silently,
    sync_performance_dependencies,
) -> None:
    anim_plan = appearance_settings.load_animations_enabled()
    smooth_plan = appearance_settings.load_smooth_scroll_enabled()
    editor_plan = appearance_settings.load_editor_smooth_scroll_enabled()

    if animations_switch is not None:
        set_checked_silently(animations_switch, anim_plan.enabled)
    if smooth_scroll_switch is not None:
        set_checked_silently(smooth_scroll_switch, smooth_plan.enabled)
    if editor_smooth_scroll_switch is not None:
        set_checked_silently(editor_smooth_scroll_switch, editor_plan.enabled)
    sync_performance_dependencies(anim_plan.enabled)
