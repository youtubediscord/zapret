"""Build-helper верхних секций Appearance page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from ui.fluent_widgets import SettingsCard, build_premium_badge
from app.text_catalog import LANGUAGE_OPTIONS, tr as tr_catalog


@dataclass(slots=True)
class AppearanceDisplayModeWidgets:
    section_title: object
    card: object
    segmented: object | None
    spacer: object


@dataclass(slots=True)
class AppearanceLanguageWidgets:
    card: object
    desc_label: object
    name_label: object
    combo: object


@dataclass(slots=True)
class AppearanceBackgroundWidgets:
    card: object
    radio_standard: object
    radio_amoled: object
    radio_rkn_chan: object
    rkn_background_combo: object


def build_display_mode_section(
    *,
    page,
    tr_language: str,
    add_section_title,
    content_parent,
    settings_card_cls,
    caption_label_cls,
    segmented_widget_cls,
    on_display_mode_changed,
) -> AppearanceDisplayModeWidgets:
    section_title = add_section_title(
        text_key="page.appearance.section.display_mode",
        return_widget=True,
    )

    display_card = settings_card_cls()
    display_layout = QVBoxLayout()
    display_layout.setSpacing(12)

    display_desc = caption_label_cls(
        tr_catalog(
            "page.appearance.display_mode.description",
            language=tr_language,
            default="Выберите светлый или тёмный режим интерфейса.",
        )
    )
    display_desc.setWordWrap(True)
    display_layout.addWidget(display_desc)

    display_mode_seg = None
    try:
        display_mode_seg = segmented_widget_cls()
        display_mode_seg.addItem(
            "dark",
            tr_catalog("page.appearance.display_mode.option.dark", language=tr_language, default="🌙 Тёмный"),
            lambda: on_display_mode_changed("dark"),
        )
        display_mode_seg.addItem(
            "light",
            tr_catalog("page.appearance.display_mode.option.light", language=tr_language, default="☀️ Светлый"),
            lambda: on_display_mode_changed("light"),
        )
        display_mode_seg.addItem(
            "system",
            tr_catalog("page.appearance.display_mode.option.system", language=tr_language, default="⚙ Авто"),
            lambda: on_display_mode_changed("system"),
        )
        display_mode_seg.setCurrentItem("dark")
        display_layout.addWidget(display_mode_seg)
    except Exception:
        display_mode_seg = None

    display_card.add_layout(display_layout)

    spacer = QWidget(content_parent)
    spacer.setFixedHeight(16)
    spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    return AppearanceDisplayModeWidgets(
        section_title=section_title,
        card=display_card,
        segmented=display_mode_seg,
        spacer=spacer,
    )


def build_language_section(
    *,
    tr_language: str,
    add_section_title,
    settings_card_cls,
    caption_label_cls,
    body_label_cls,
    combo_cls,
    on_ui_language_changed,
) -> AppearanceLanguageWidgets:
    add_section_title(text_key="appearance.language.section")

    language_card = settings_card_cls()
    language_layout = QVBoxLayout()
    language_layout.setSpacing(12)

    language_desc = caption_label_cls(tr_catalog("appearance.language.desc", language=tr_language))
    language_desc.setWordWrap(True)
    language_layout.addWidget(language_desc)

    language_row = QHBoxLayout()
    language_row.setSpacing(12)
    language_label = body_label_cls(tr_catalog("appearance.language.label", language=tr_language))
    language_row.addWidget(language_label)
    language_row.addStretch()

    language_combo = combo_cls()
    for lang_code, lang_title in LANGUAGE_OPTIONS:
        language_combo.addItem(lang_title, userData=lang_code)
    language_combo.currentIndexChanged.connect(on_ui_language_changed)
    language_row.addWidget(language_combo)

    language_layout.addLayout(language_row)
    language_card.add_layout(language_layout)
    return AppearanceLanguageWidgets(
        card=language_card,
        desc_label=language_desc,
        name_label=language_label,
        combo=language_combo,
    )


def build_background_section(
    *,
    tr_language: str,
    add_section_title,
    settings_card_cls,
    caption_label_cls,
    body_label_cls,
    radio_button_cls,
    combo_cls,
    on_bg_preset_toggled,
    on_rkn_background_changed,
) -> AppearanceBackgroundWidgets:
    add_section_title(text_key="page.appearance.section.background")

    bg_card = settings_card_cls()
    bg_layout = QVBoxLayout()
    bg_layout.setSpacing(12)

    bg_desc = caption_label_cls(
        tr_catalog(
            "page.appearance.background.description",
            language=tr_language,
            default=(
                "Стандартный фон соответствует режиму отображения. "
                "AMOLED и РКН Тян доступны подписчикам Premium. "
                "Для РКН Тян можно выбрать готовый фон из списка."
            ),
        )
    )
    bg_desc.setWordWrap(True)
    bg_layout.addWidget(bg_desc)

    bg_radio_standard = radio_button_cls()
    bg_radio_standard.setText(
        tr_catalog("page.appearance.background.option.standard", language=tr_language, default="Стандартный")
    )
    bg_radio_standard.setChecked(True)
    bg_radio_standard.toggled.connect(lambda checked: on_bg_preset_toggled("standard", checked))
    bg_layout.addWidget(bg_radio_standard)

    amoled_row = QHBoxLayout()
    bg_radio_amoled = radio_button_cls()
    bg_radio_amoled.setText(
        tr_catalog("page.appearance.background.option.amoled", language=tr_language, default="AMOLED — чёрный")
    )
    bg_radio_amoled.setEnabled(False)
    bg_radio_amoled.toggled.connect(lambda checked: on_bg_preset_toggled("amoled", checked))
    amoled_row.addWidget(bg_radio_amoled)
    amoled_badge = build_premium_badge(
        tr_catalog("common.badge.premium", language=tr_language, default="⭐ Premium")
    )
    amoled_row.addWidget(amoled_badge)
    amoled_row.addStretch()
    bg_layout.addLayout(amoled_row)

    rkn_row = QHBoxLayout()
    bg_radio_rkn_chan = radio_button_cls()
    bg_radio_rkn_chan.setText(
        tr_catalog("page.appearance.background.option.rkn_chan", language=tr_language, default="РКН Тян")
    )
    bg_radio_rkn_chan.setEnabled(False)
    bg_radio_rkn_chan.toggled.connect(lambda checked: on_bg_preset_toggled("rkn_chan", checked))
    rkn_row.addWidget(bg_radio_rkn_chan)
    rkn_badge = build_premium_badge(
        tr_catalog("common.badge.premium", language=tr_language, default="⭐ Premium")
    )
    rkn_row.addWidget(rkn_badge)
    rkn_row.addStretch()
    bg_layout.addLayout(rkn_row)

    rkn_bg_row = QHBoxLayout()
    rkn_bg_row.setSpacing(12)
    rkn_bg_label = body_label_cls(
        tr_catalog("page.appearance.background.rkn.label", language=tr_language, default="Фон РКН Тян")
    )
    rkn_bg_row.addWidget(rkn_bg_label)
    rkn_bg_row.addStretch()

    rkn_background_combo = combo_cls()
    rkn_background_combo.currentIndexChanged.connect(on_rkn_background_changed)
    rkn_bg_row.addWidget(rkn_background_combo)
    bg_layout.addLayout(rkn_bg_row)

    bg_card.add_layout(bg_layout)
    return AppearanceBackgroundWidgets(
        card=bg_card,
        radio_standard=bg_radio_standard,
        radio_amoled=bg_radio_amoled,
        radio_rkn_chan=bg_radio_rkn_chan,
        rkn_background_combo=rkn_background_combo,
    )
