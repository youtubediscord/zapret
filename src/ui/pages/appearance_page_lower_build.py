"""Build-helper нижних секций Appearance page."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout

from ui.fluent_widgets import SettingsCard, build_premium_badge
from app.ui_texts import tr as tr_catalog


@dataclass(slots=True)
class AppearanceHolidayWidgets:
    garland_icon_label: object
    garland_checkbox: object
    snowflakes_icon_label: object
    snowflakes_checkbox: object


@dataclass(slots=True)
class AppearanceOpacityWidgets:
    opacity_icon_label: object
    opacity_label: object
    opacity_slider: object


@dataclass(slots=True)
class AppearancePerformanceWidgets:
    performance_card: object
    performance_group: object | None
    animations_switch: object
    smooth_scroll_switch: object
    editor_smooth_scroll_switch: object


def build_holiday_sections(
    *,
    page,
    tr_language: str,
    settings_card_cls,
    caption_label_cls,
    body_label_cls,
    checkbox_cls,
    get_icon_pixmap,
    on_garland_changed,
    on_snowflakes_changed,
):
    page.add_section_title(text_key="page.appearance.section.holiday")

    garland_card = settings_card_cls()
    garland_layout = QVBoxLayout()
    garland_layout.setSpacing(12)

    garland_desc = caption_label_cls(
        tr_catalog(
            "page.appearance.holiday.garland.description",
            language=tr_language,
            default=(
                "Праздничная гирлянда с мерцающими огоньками в верхней части окна. "
                "Доступно только для подписчиков Premium."
            ),
        )
    )
    garland_desc.setWordWrap(True)
    garland_layout.addWidget(garland_desc)

    garland_row = QHBoxLayout()
    garland_row.setSpacing(12)

    garland_icon = QLabel()
    garland_icon.setPixmap(get_icon_pixmap('fa5s.holly-berry', 20))
    garland_row.addWidget(garland_icon)

    garland_label = body_label_cls(
        tr_catalog("page.appearance.holiday.garland.title", language=tr_language, default="Новогодняя гирлянда")
    )
    garland_row.addWidget(garland_label)
    garland_row.addWidget(build_premium_badge(tr_catalog("common.badge.premium", language=tr_language, default="⭐ Premium")))
    garland_row.addStretch()

    garland_checkbox = checkbox_cls()
    garland_checkbox.setEnabled(False)
    garland_checkbox.setObjectName("garlandSwitch")
    garland_checkbox.stateChanged.connect(on_garland_changed)
    garland_row.addWidget(garland_checkbox)

    garland_layout.addLayout(garland_row)
    garland_card.add_layout(garland_layout)
    page.add_widget(garland_card)

    snowflakes_card = settings_card_cls()
    snowflakes_layout = QVBoxLayout()
    snowflakes_layout.setSpacing(12)

    snowflakes_desc = caption_label_cls(
        tr_catalog(
            "page.appearance.holiday.snowflakes.description",
            language=tr_language,
            default=("Мягко падающие снежинки по всему окну. Создаёт уютную зимнюю атмосферу."),
        )
    )
    snowflakes_desc.setWordWrap(True)
    snowflakes_layout.addWidget(snowflakes_desc)

    snowflakes_row = QHBoxLayout()
    snowflakes_row.setSpacing(12)

    snowflakes_icon = QLabel()
    snowflakes_icon.setPixmap(get_icon_pixmap('fa5s.snowflake', 20))
    snowflakes_row.addWidget(snowflakes_icon)

    snowflakes_label = body_label_cls(
        tr_catalog("page.appearance.holiday.snowflakes.title", language=tr_language, default="Снежинки")
    )
    snowflakes_row.addWidget(snowflakes_label)
    snowflakes_row.addWidget(build_premium_badge(tr_catalog("common.badge.premium", language=tr_language, default="⭐ Premium")))
    snowflakes_row.addStretch()

    snowflakes_checkbox = checkbox_cls()
    snowflakes_checkbox.setEnabled(False)
    snowflakes_checkbox.setObjectName("snowflakesSwitch")
    snowflakes_checkbox.stateChanged.connect(on_snowflakes_changed)
    snowflakes_row.addWidget(snowflakes_checkbox)

    snowflakes_layout.addLayout(snowflakes_row)
    snowflakes_card.add_layout(snowflakes_layout)
    page.add_widget(snowflakes_card)
    page.add_spacing(16)

    return AppearanceHolidayWidgets(
        garland_icon_label=garland_icon,
        garland_checkbox=garland_checkbox,
        snowflakes_icon_label=snowflakes_icon,
        snowflakes_checkbox=snowflakes_checkbox,
    )


def build_opacity_section(
    *,
    page,
    tr_language: str,
    settings_card_cls,
    caption_label_cls,
    body_label_cls,
    slider_cls,
    initial_opacity: int,
    get_icon_pixmap,
    on_opacity_changed,
):
    opacity_card = settings_card_cls()
    opacity_layout = QVBoxLayout()
    opacity_layout.setSpacing(12)

    is_win11_plus = sys.platform == "win32" and sys.getwindowsversion().build >= 22000
    if is_win11_plus:
        opacity_title_text = tr_catalog(
            "page.appearance.opacity.win11.title",
            language=tr_language,
            default="Эффект акрилика окна",
        )
        opacity_desc_text = tr_catalog(
            "page.appearance.opacity.win11.description",
            language=tr_language,
            default=(
                "Настройка интенсивности акрилового эффекта всего окна приложения. "
                "При 0% эффект минимальный, при 100% — максимальный."
            ),
        )
    else:
        opacity_title_text = tr_catalog(
            "page.appearance.opacity.standard.title",
            language=tr_language,
            default="Прозрачность окна",
        )
        opacity_desc_text = tr_catalog(
            "page.appearance.opacity.standard.description",
            language=tr_language,
            default=(
                "Настройка прозрачности всего окна приложения. "
                "При 0% окно полностью прозрачное, при 100% — непрозрачное."
            ),
        )

    opacity_desc = caption_label_cls(opacity_desc_text)
    opacity_desc.setWordWrap(True)
    opacity_layout.addWidget(opacity_desc)

    opacity_row = QHBoxLayout()
    opacity_row.setSpacing(12)

    opacity_icon = QLabel()
    opacity_icon.setPixmap(get_icon_pixmap('fa5s.adjust', 20))
    opacity_row.addWidget(opacity_icon)

    opacity_title = body_label_cls(opacity_title_text)
    opacity_row.addWidget(opacity_title)
    opacity_row.addStretch()

    opacity_label = caption_label_cls(f"{initial_opacity}%")
    opacity_label.setMinimumWidth(40)
    opacity_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    opacity_row.addWidget(opacity_label)
    opacity_layout.addLayout(opacity_row)

    opacity_slider = slider_cls(Qt.Orientation.Horizontal)
    opacity_slider.setMinimum(0)
    opacity_slider.setMaximum(100)
    opacity_slider.setValue(initial_opacity)
    opacity_slider.setSingleStep(1)
    opacity_slider.setPageStep(5)
    opacity_slider.valueChanged.connect(on_opacity_changed)
    opacity_layout.addWidget(opacity_slider)

    opacity_card.add_layout(opacity_layout)
    page.add_widget(opacity_card)
    page.add_spacing(16)

    return AppearanceOpacityWidgets(
        opacity_icon_label=opacity_icon,
        opacity_label=opacity_label,
        opacity_slider=opacity_slider,
    )


def build_performance_section(
    *,
    page,
    tr_language: str,
    settings_card_group_cls,
    toggle_row_cls,
    on_animations_changed,
    on_smooth_scroll_changed,
    on_editor_smooth_scroll_changed,
):
    performance_group = settings_card_group_cls(
        tr_catalog("page.appearance.section.performance", language=tr_language, default="Производительность"),
        page.content,
    )
    perf_card = performance_group

    animations_switch = toggle_row_cls(
        "fa5s.film",
        tr_catalog("page.appearance.performance.animations.title", language=tr_language, default="Анимации интерфейса"),
        tr_catalog(
            "page.appearance.performance.animations.description",
            language=tr_language,
            default="Анимации кнопок, переходов и элементов WinUI",
        ),
    )
    animations_switch.toggled.connect(on_animations_changed)
    perf_card.addSettingCard(animations_switch)

    smooth_scroll_switch = toggle_row_cls(
        "fa5s.mouse",
        tr_catalog("page.appearance.performance.scroll.title", language=tr_language, default="Плавная прокрутка"),
        tr_catalog(
            "page.appearance.performance.scroll.description",
            language=tr_language,
            default="Инерционная прокрутка страниц настроек",
        ),
    )
    smooth_scroll_switch.toggled.connect(on_smooth_scroll_changed)
    perf_card.addSettingCard(smooth_scroll_switch)

    editor_smooth_scroll_switch = toggle_row_cls(
        "fa5s.file-alt",
        tr_catalog(
            "page.appearance.performance.editor_scroll.title",
            language=tr_language,
            default="Плавная прокрутка редакторов",
        ),
        tr_catalog(
            "page.appearance.performance.editor_scroll.description",
            language=tr_language,
            default="Плавная прокрутка внутри больших текстовых полей и редакторов. Работает только при включённых анимациях интерфейса.",
        ),
    )
    editor_smooth_scroll_switch.toggled.connect(on_editor_smooth_scroll_changed)
    perf_card.addSettingCard(editor_smooth_scroll_switch)

    page.add_widget(perf_card)
    page.add_spacing(16)

    return AppearancePerformanceWidgets(
        performance_card=perf_card,
        performance_group=performance_group,
        animations_switch=animations_switch,
        smooth_scroll_switch=smooth_scroll_switch,
        editor_smooth_scroll_switch=editor_smooth_scroll_switch,
    )
