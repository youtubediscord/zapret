"""Build-helper верхних секций Appearance page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from ui.fluent_widgets import SettingsCard, build_premium_badge
from app.ui_texts import LANGUAGE_OPTIONS, tr as tr_catalog
from ui.accessibility import set_control_accessibility, set_state_text
from ui.combo_accessibility import set_combo_items_accessibility
from ui.segmented_accessibility import set_segmented_items_accessibility


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
        update_display_mode_accessibility(display_mode_seg, mode="dark")
        display_mode_seg.currentItemChanged.connect(
            lambda mode: update_display_mode_accessibility(display_mode_seg, mode=mode)
        )
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
    update_language_combo_accessibility(language_combo)
    language_combo.currentIndexChanged.connect(
        lambda _index: update_language_combo_accessibility(language_combo)
    )
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
    update_rkn_background_combo_accessibility(rkn_background_combo)
    rkn_background_combo.currentIndexChanged.connect(on_rkn_background_changed)
    rkn_background_combo.currentIndexChanged.connect(
        lambda _index: update_rkn_background_combo_accessibility(rkn_background_combo)
    )
    rkn_bg_row.addWidget(rkn_background_combo)
    bg_layout.addLayout(rkn_bg_row)

    bg_card.add_layout(bg_layout)
    _update_background_radio_accessibility(
        bg_radio_standard,
        bg_radio_amoled,
        bg_radio_rkn_chan,
    )
    for radio in (bg_radio_standard, bg_radio_amoled, bg_radio_rkn_chan):
        radio.toggled.connect(
            lambda _checked, standard=bg_radio_standard, amoled=bg_radio_amoled, rkn=bg_radio_rkn_chan: (
                _update_background_radio_accessibility(standard, amoled, rkn)
            )
        )
    return AppearanceBackgroundWidgets(
        card=bg_card,
        radio_standard=bg_radio_standard,
        radio_amoled=bg_radio_amoled,
        radio_rkn_chan=bg_radio_rkn_chan,
        rkn_background_combo=rkn_background_combo,
    )


def update_display_mode_accessibility(widget, *, mode: object | None = None) -> None:
    labels = {
        "dark": "Тёмный",
        "light": "Светлый",
        "system": "Авто",
    }
    key = str(mode or "").strip()
    if not key:
        try:
            key = str(widget.currentItem() or "").strip()
        except Exception:
            key = ""
    selected = labels.get(key, key or "Тёмный")
    state = f"Режим отображения интерфейса, выбрано: {selected}"
    set_state_text(widget, state)
    set_control_accessibility(
        widget,
        name=state,
        description="Выберите светлый, тёмный или автоматический режим интерфейса.",
    )
    set_segmented_items_accessibility(
        widget,
        name="Режим отображения интерфейса",
        labels=labels,
    )


def update_sidebar_icon_style_accessibility(widget, *, style: object | None = None) -> None:
    labels = {
        "standard": "Стандартные",
        "windows11_fluent": "Windows 11 Fluent",
    }
    key = str(style or "").strip()
    if not key:
        try:
            key = str(widget.currentItem() or "").strip()
        except Exception:
            key = ""
    selected = labels.get(key, key or "Стандартные")
    state = f"Стиль иконок бокового меню, выбрано: {selected}"
    set_state_text(widget, state)
    set_control_accessibility(
        widget,
        name=state,
        description="Выберите стиль иконок в левом боковом меню.",
    )
    set_segmented_items_accessibility(
        widget,
        name="Стиль иконок бокового меню",
        labels=labels,
    )


def update_language_combo_accessibility(combo) -> None:
    selected = str(combo.currentText() or "").strip() or "не выбран"
    state = f"Язык интерфейса, выбрано: {selected}"
    set_state_text(combo, state)
    set_control_accessibility(
        combo,
        name=state,
        description="Выберите язык интерфейса программы.",
    )
    set_combo_items_accessibility(combo, name="Язык интерфейса")


def _update_background_radio_accessibility(standard, amoled, rkn) -> None:
    _set_background_radio_accessibility(standard, label="Стандартный", premium_locked=False)
    _set_background_radio_accessibility(amoled, label="AMOLED — чёрный", premium_locked=True)
    _set_background_radio_accessibility(rkn, label="РКН Тян", premium_locked=True)


def _set_background_radio_accessibility(radio, *, label: str, premium_locked: bool) -> None:
    if bool(premium_locked) and not bool(radio.isEnabled()):
        state = "недоступно без Premium"
    else:
        state = "выбрано" if bool(radio.isChecked()) else "не выбрано"
    text = f"Фон окна: {label}, {state}"
    set_state_text(radio, text)
    description = "Выберите этот фон окна."
    if bool(premium_locked):
        description = "Этот фон окна доступен подписчикам Premium."
    set_control_accessibility(radio, name=text, description=description)


def update_rkn_background_combo_accessibility(combo) -> None:
    try:
        count = int(combo.count())
    except Exception:
        count = 0
    if count <= 0:
        state = "Фон РКН Тян, вариантов пока нет"
    else:
        selected = str(combo.currentText() or "").strip() or "не выбран"
        state = f"Фон РКН Тян, выбрано: {selected}"
        if not bool(combo.isEnabled()):
            state = f"{state}, недоступно"
    set_state_text(combo, state)
    set_control_accessibility(
        combo,
        name=state,
        description="Выберите готовый фон РКН Тян.",
    )
    set_combo_items_accessibility(combo, name="Фон РКН Тян")
