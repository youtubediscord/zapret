# ui/pages/appearance_page.py
"""Страница настроек оформления - темы"""

import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QColor
import qtawesome as qta

from .base_page import BasePage
from ui.appearance_page_controller import AppearancePageController
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    SettingsRow,
    build_premium_badge,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.theme import get_theme_tokens, get_rkn_background_options
from ui.text_catalog import tr as tr_catalog
from ui.widgets.win11_controls import Win11ToggleRow

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, ColorPickerButton, setThemeColor,
        ColorDialog,
        CheckBox, SegmentedWidget, RadioButton, Slider, ComboBox, SettingCardGroup,
    )
    _HAS_FLUENT_LABELS = True
    _HAS_COLOR_PICKER = True
except ImportError:
    from PyQt6.QtWidgets import (
        QCheckBox as CheckBox,
        QRadioButton as RadioButton,
        QSlider as Slider,
        QComboBox as ComboBox,
    )
    SegmentedWidget = None
    ColorDialog = None
    SettingCardGroup = None
    _HAS_FLUENT_LABELS = False
    _HAS_COLOR_PICKER = False


class AppearancePage(BasePage):
    """Страница настроек оформления"""

    # Сигнал смены режима отображения
    display_mode_changed = pyqtSignal(str)   # "dark" / "light" / "system"
    # Сигнал смены фонового пресета
    background_preset_changed = pyqtSignal(str)  # "standard" / "amoled" / "rkn_chan"
    # Сигнал изменения состояния гирлянды
    garland_changed = pyqtSignal(bool)
    # Сигнал изменения состояния снежинок
    snowflakes_changed = pyqtSignal(bool)
    # Сигнал изменения прозрачности окна (0-100)
    opacity_changed = pyqtSignal(int)
    # Сигнал изменения акцентного цвета (hex string)
    accent_color_changed = pyqtSignal(str)
    # Сигнал запроса обновления фона окна (при смене тонировки или акцента)
    background_refresh_needed = pyqtSignal()
    # Сигнал изменения Mica-эффекта
    mica_changed = pyqtSignal(bool)
    # Сигнал изменения анимаций интерфейса
    animations_changed = pyqtSignal(bool)
    # Сигнал изменения плавной прокрутки
    smooth_scroll_changed = pyqtSignal(bool)
    # Сигнал изменения плавной прокрутки внутри редакторов
    editor_smooth_scroll_changed = pyqtSignal(bool)
    # Сигнал смены языка интерфейса
    ui_language_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(
            "Оформление",
            "Настройка внешнего вида приложения",
            parent,
            title_key="page.appearance.title",
            subtitle_key="page.appearance.subtitle",
        )

        self._display_mode_seg = None    # SegmentedWidget
        self._display_mode_section_title = None
        self._display_mode_card = None
        self._display_mode_spacer = None
        self._language_combo = None      # ComboBox
        self._language_desc_label = None
        self._language_name_label = None
        self._bg_radio_standard = None   # RadioButton
        self._bg_radio_amoled = None     # RadioButton
        self._bg_radio_rkn_chan = None   # RadioButton
        self._rkn_background_combo = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._garland_checkbox = None
        self._snowflakes_checkbox = None
        self._opacity_slider = None
        self._opacity_label = None
        self._opacity_icon_label = None
        self._garland_icon_label = None
        self._snowflakes_icon_label = None
        self._color_picker_btn = None
        self._accent_group = None
        self._accent_desc_label = None
        self._accent_color_row = None
        self._follow_windows_accent_cb = None
        self._tinted_bg_cb = None
        self._tinted_intensity_container = None
        self._tinted_intensity_label = None
        self._tinted_intensity_slider = None
        self._tinted_intensity_value_label = None
        self._mica_switch = None
        self._animations_switch = None
        self._smooth_scroll_switch = None
        self._editor_smooth_scroll_switch = None
        self._performance_card = None
        self._performance_section_title = None
        self._performance_group = None
        self._build_ui()
        is_premium, garland_enabled, snowflakes_enabled, window_opacity = self._current_appearance_state()
        try:
            self.set_premium_status(is_premium)
        except Exception:
            pass

        try:
            self.set_garland_state(garland_enabled)
            self.set_snowflakes_state(snowflakes_enabled)
            self.set_opacity_value(window_opacity)
        except Exception:
            pass

        try:
            self.set_ui_language(self._ui_language)
        except Exception:
            pass

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"subscription_is_premium", "garland_enabled", "snowflakes_enabled", "window_opacity"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        self.set_premium_status(state.subscription_is_premium)
        self.set_garland_state(state.garland_enabled)
        self.set_snowflakes_state(state.snowflakes_enabled)
        self.set_opacity_value(state.window_opacity)

    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # РЕЖИМ ОТОБРАЖЕНИЯ
        # ═══════════════════════════════════════════════════════════
        self._display_mode_section_title = self.add_section_title(
            text_key="page.appearance.section.display_mode",
            return_widget=True,
        )

        display_card = SettingsCard()
        self._display_mode_card = display_card
        display_layout = QVBoxLayout()
        display_layout.setSpacing(12)

        display_desc = CaptionLabel(
            tr_catalog(
                "page.appearance.display_mode.description",
                language=self._ui_language,
                default="Выберите светлый или тёмный режим интерфейса.",
            )
        )
        display_desc.setWordWrap(True)
        display_layout.addWidget(display_desc)

        try:
            self._display_mode_seg = SegmentedWidget()
            self._display_mode_seg.addItem(
                "dark",
                tr_catalog("page.appearance.display_mode.option.dark", language=self._ui_language, default="🌙 Тёмный"),
                lambda: self._on_display_mode_changed("dark"),
            )
            self._display_mode_seg.addItem(
                "light",
                tr_catalog("page.appearance.display_mode.option.light", language=self._ui_language, default="☀️ Светлый"),
                lambda: self._on_display_mode_changed("light"),
            )
            self._display_mode_seg.addItem(
                "system",
                tr_catalog("page.appearance.display_mode.option.system", language=self._ui_language, default="⚙ Авто"),
                lambda: self._on_display_mode_changed("system"),
            )
            self._display_mode_seg.setCurrentItem("dark")
            display_layout.addWidget(self._display_mode_seg)
        except Exception:
            self._display_mode_seg = None

        display_card.add_layout(display_layout)
        self.add_widget(display_card)

        self._display_mode_spacer = QWidget(self.content)
        self._display_mode_spacer.setFixedHeight(16)
        self._display_mode_spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.add_widget(self._display_mode_spacer)

        # ═══════════════════════════════════════════════════════════
        # ЯЗЫК ИНТЕРФЕЙСА
        # ═══════════════════════════════════════════════════════════
        from ui.text_catalog import LANGUAGE_OPTIONS
        _lang = AppearancePageController.load_ui_language().language

        self.add_section_title(text_key="appearance.language.section")

        language_card = SettingsCard()
        language_layout = QVBoxLayout()
        language_layout.setSpacing(12)

        language_desc = CaptionLabel(tr_catalog("appearance.language.desc", language=_lang))
        language_desc.setWordWrap(True)
        self._language_desc_label = language_desc
        language_layout.addWidget(language_desc)

        language_row = QHBoxLayout()
        language_row.setSpacing(12)
        language_label = BodyLabel(tr_catalog("appearance.language.label", language=_lang))
        self._language_name_label = language_label
        language_row.addWidget(language_label)
        language_row.addStretch()

        self._language_combo = ComboBox()
        for lang_code, lang_title in LANGUAGE_OPTIONS:
            self._language_combo.addItem(lang_title, userData=lang_code)
        self._language_combo.currentIndexChanged.connect(self._on_ui_language_changed)
        language_row.addWidget(self._language_combo)

        language_layout.addLayout(language_row)
        language_card.add_layout(language_layout)
        self.add_widget(language_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ФОН ОКНА
        # ═══════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.appearance.section.background")

        bg_card = SettingsCard()
        bg_layout = QVBoxLayout()
        bg_layout.setSpacing(12)

        bg_desc = CaptionLabel(
            tr_catalog(
                "page.appearance.background.description",
                language=self._ui_language,
                default=(
                    "Стандартный фон соответствует режиму отображения. "
                    "AMOLED и РКН Тян доступны подписчикам Premium. "
                    "Для РКН Тян можно выбрать готовый фон из списка."
                ),
            )
        )
        bg_desc.setWordWrap(True)
        bg_layout.addWidget(bg_desc)

        # Standard row
        self._bg_radio_standard = RadioButton()
        self._bg_radio_standard.setText(
            tr_catalog("page.appearance.background.option.standard", language=self._ui_language, default="Стандартный")
        )
        self._bg_radio_standard.setChecked(True)
        self._bg_radio_standard.toggled.connect(lambda checked: self._on_bg_preset_toggled("standard", checked))
        bg_layout.addWidget(self._bg_radio_standard)

        # AMOLED row
        amoled_row = QHBoxLayout()
        self._bg_radio_amoled = RadioButton()
        self._bg_radio_amoled.setText(
            tr_catalog("page.appearance.background.option.amoled", language=self._ui_language, default="AMOLED — чёрный")
        )
        self._bg_radio_amoled.setEnabled(False)
        self._bg_radio_amoled.toggled.connect(lambda checked: self._on_bg_preset_toggled("amoled", checked))
        amoled_row.addWidget(self._bg_radio_amoled)
        amoled_badge = build_premium_badge(
            tr_catalog("common.badge.premium", language=self._ui_language, default="⭐ Premium")
        )
        amoled_row.addWidget(amoled_badge)
        amoled_row.addStretch()
        bg_layout.addLayout(amoled_row)

        # РКН Тян row
        rkn_row = QHBoxLayout()
        self._bg_radio_rkn_chan = RadioButton()
        self._bg_radio_rkn_chan.setText(
            tr_catalog("page.appearance.background.option.rkn_chan", language=self._ui_language, default="РКН Тян")
        )
        self._bg_radio_rkn_chan.setEnabled(False)
        self._bg_radio_rkn_chan.toggled.connect(lambda checked: self._on_bg_preset_toggled("rkn_chan", checked))
        rkn_row.addWidget(self._bg_radio_rkn_chan)
        rkn_badge = build_premium_badge(
            tr_catalog("common.badge.premium", language=self._ui_language, default="⭐ Premium")
        )
        rkn_row.addWidget(rkn_badge)
        rkn_row.addStretch()
        bg_layout.addLayout(rkn_row)

        rkn_bg_row = QHBoxLayout()
        rkn_bg_row.setSpacing(12)
        rkn_bg_label = BodyLabel(
            tr_catalog("page.appearance.background.rkn.label", language=self._ui_language, default="Фон РКН Тян")
        )
        rkn_bg_row.addWidget(rkn_bg_label)
        rkn_bg_row.addStretch()

        self._rkn_background_combo = ComboBox()
        self._rkn_background_combo.currentIndexChanged.connect(self._on_rkn_background_changed)
        rkn_bg_row.addWidget(self._rkn_background_combo)
        bg_layout.addLayout(rkn_bg_row)

        self._reload_rkn_background_options()

        # Mica is always enabled on Win11 — no user toggle needed.

        bg_card.add_layout(bg_layout)
        self.add_widget(bg_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # НОВОГОДНЕЕ ОФОРМЛЕНИЕ (Premium)
        # ═══════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.appearance.section.holiday")

        garland_card = SettingsCard()
        garland_layout = QVBoxLayout()
        garland_layout.setSpacing(12)

        garland_desc = CaptionLabel(
            tr_catalog(
                "page.appearance.holiday.garland.description",
                language=self._ui_language,
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
        self._garland_icon_label = garland_icon
        garland_icon.setPixmap(qta.icon('fa5s.holly-berry', color=get_theme_tokens().accent_hex).pixmap(20, 20))
        garland_row.addWidget(garland_icon)

        garland_label = BodyLabel(
            tr_catalog("page.appearance.holiday.garland.title", language=self._ui_language, default="Новогодняя гирлянда")
        )
        garland_row.addWidget(garland_label)

        premium_badge = build_premium_badge(
            tr_catalog("common.badge.premium", language=self._ui_language, default="⭐ Premium")
        )
        garland_row.addWidget(premium_badge)

        garland_row.addStretch()

        self._garland_checkbox = CheckBox()
        self._garland_checkbox.setEnabled(False)
        self._garland_checkbox.setObjectName("garlandSwitch")
        self._garland_checkbox.stateChanged.connect(self._on_garland_changed)
        garland_row.addWidget(self._garland_checkbox)

        garland_layout.addLayout(garland_row)
        garland_card.add_layout(garland_layout)
        self.add_widget(garland_card)

        # ═══════════════════════════════════════════════════════════
        # СНЕЖИНКИ (Premium)
        # ═══════════════════════════════════════════════════════════
        snowflakes_card = SettingsCard()
        snowflakes_layout = QVBoxLayout()
        snowflakes_layout.setSpacing(12)

        snowflakes_desc = CaptionLabel(
            tr_catalog(
                "page.appearance.holiday.snowflakes.description",
                language=self._ui_language,
                default=(
                    "Мягко падающие снежинки по всему окну. "
                    "Создаёт уютную зимнюю атмосферу."
                ),
            )
        )
        snowflakes_desc.setWordWrap(True)
        snowflakes_layout.addWidget(snowflakes_desc)

        snowflakes_row = QHBoxLayout()
        snowflakes_row.setSpacing(12)

        snowflakes_icon = QLabel()
        self._snowflakes_icon_label = snowflakes_icon
        snowflakes_icon.setPixmap(qta.icon('fa5s.snowflake', color=get_theme_tokens().accent_hex).pixmap(20, 20))
        snowflakes_row.addWidget(snowflakes_icon)

        snowflakes_label = BodyLabel(
            tr_catalog("page.appearance.holiday.snowflakes.title", language=self._ui_language, default="Снежинки")
        )
        snowflakes_row.addWidget(snowflakes_label)

        snowflakes_badge = build_premium_badge(
            tr_catalog("common.badge.premium", language=self._ui_language, default="⭐ Premium")
        )
        snowflakes_row.addWidget(snowflakes_badge)

        snowflakes_row.addStretch()

        self._snowflakes_checkbox = CheckBox()
        self._snowflakes_checkbox.setEnabled(False)
        self._snowflakes_checkbox.setObjectName("snowflakesSwitch")
        self._snowflakes_checkbox.stateChanged.connect(self._on_snowflakes_changed)
        snowflakes_row.addWidget(self._snowflakes_checkbox)

        snowflakes_layout.addLayout(snowflakes_row)
        snowflakes_card.add_layout(snowflakes_layout)
        self.add_widget(snowflakes_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ПРОЗРАЧНОСТЬ ОКНА
        # ═══════════════════════════════════════════════════════════
        opacity_card = SettingsCard()
        opacity_layout = QVBoxLayout()
        opacity_layout.setSpacing(12)

        is_win11_plus = sys.platform == "win32" and sys.getwindowsversion().build >= 22000
        if is_win11_plus:
            opacity_title_text = tr_catalog(
                "page.appearance.opacity.win11.title",
                language=self._ui_language,
                default="Эффект акрилика окна",
            )
            opacity_desc_text = tr_catalog(
                "page.appearance.opacity.win11.description",
                language=self._ui_language,
                default=(
                    "Настройка интенсивности акрилового эффекта всего окна приложения. "
                    "При 0% эффект минимальный, при 100% — максимальный."
                ),
            )
        else:
            opacity_title_text = tr_catalog(
                "page.appearance.opacity.legacy.title",
                language=self._ui_language,
                default="Прозрачность окна",
            )
            opacity_desc_text = tr_catalog(
                "page.appearance.opacity.legacy.description",
                language=self._ui_language,
                default=(
                    "Настройка прозрачности всего окна приложения. "
                    "При 0% окно полностью прозрачное, при 100% — непрозрачное."
                ),
            )

        opacity_desc = CaptionLabel(opacity_desc_text)
        opacity_desc.setWordWrap(True)
        opacity_layout.addWidget(opacity_desc)

        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(12)

        opacity_icon = QLabel()
        self._opacity_icon_label = opacity_icon
        opacity_icon.setPixmap(qta.icon('fa5s.adjust', color=get_theme_tokens().accent_hex).pixmap(20, 20))
        opacity_row.addWidget(opacity_icon)

        opacity_title = BodyLabel(opacity_title_text)
        opacity_row.addWidget(opacity_title)

        opacity_row.addStretch()

        initial_opacity = AppearancePageController.load_window_opacity().value

        self._opacity_label = CaptionLabel(f"{initial_opacity}%")
        self._opacity_label.setMinimumWidth(40)
        self._opacity_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_row.addWidget(self._opacity_label)

        opacity_layout.addLayout(opacity_row)

        self._opacity_slider = Slider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(0)
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setValue(initial_opacity)
        self._opacity_slider.setSingleStep(1)
        self._opacity_slider.setPageStep(5)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self._opacity_slider)

        opacity_card.add_layout(opacity_layout)
        self.add_widget(opacity_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # АКЦЕНТНЫЙ ЦВЕТ (qfluentwidgets setThemeColor)
        # ═══════════════════════════════════════════════════════════
        if _HAS_COLOR_PICKER:
            if SettingCardGroup is not None and _HAS_FLUENT_LABELS:
                self._accent_group = SettingCardGroup(
                    tr_catalog("page.appearance.section.accent", language=self._ui_language, default="Акцентный цвет"),
                    self.content,
                )
                accent_card = self._accent_group
                accent_layout = None
            else:
                self.add_section_title(text_key="page.appearance.section.accent")
                self._accent_group = None
                accent_card = SettingsCard()
                accent_layout = QVBoxLayout()
                accent_layout.setSpacing(12)

            accent_desc = CaptionLabel(
                tr_catalog(
                    "page.appearance.accent.description",
                    language=self._ui_language,
                    default=(
                        "Цвет акцентных элементов интерфейса: кнопок, иконок, индикаторов. "
                        "Изменяет цвет нативных компонентов WinUI."
                    ),
                )
            )
            accent_desc.setWordWrap(True)
            self._accent_desc_label = accent_desc
            if accent_layout is not None:
                accent_layout.addWidget(accent_desc)
            else:
                insert_widget_into_setting_card_group(accent_card, 1, accent_desc)

            accent_row = SettingsRow(
                "fa5s.palette",
                tr_catalog("page.appearance.accent.color.title", language=self._ui_language, default="Цвет акцента"),
                "",
            )
            self._accent_color_row = accent_row
            self._color_picker_btn = ColorPickerButton(
                QColor("#0078d4"),
                tr_catalog("page.appearance.accent.color.pick", language=self._ui_language, default="Выбрать цвет"),
            )
            try:
                self._color_picker_btn.clicked.disconnect()
                self._color_picker_btn.clicked.connect(self._show_accent_color_dialog)
            except Exception:
                pass
            self._color_picker_btn.colorChanged.connect(self._on_accent_color_changed)
            accent_row.set_control(self._color_picker_btn)
            if accent_layout is not None:
                accent_layout.addWidget(accent_row)
            else:
                accent_card.addSettingCard(accent_row)

            self._follow_windows_accent_cb = Win11ToggleRow(
                "fa5s.windows",
                tr_catalog("page.appearance.accent.windows.title", language=self._ui_language, default="Акцент из Windows"),
                tr_catalog(
                    "page.appearance.accent.windows.description",
                    language=self._ui_language,
                    default="Автоматически использовать системный акцентный цвет Windows",
                ),
            )
            self._follow_windows_accent_cb.toggled.connect(self._on_follow_windows_accent_changed)
            if accent_layout is not None:
                accent_layout.addWidget(self._follow_windows_accent_cb)
            else:
                accent_card.addSettingCard(self._follow_windows_accent_cb)

            self._tinted_bg_cb = Win11ToggleRow(
                "fa5s.fill-drip",
                tr_catalog(
                    "page.appearance.accent.tint_background.title",
                    language=self._ui_language,
                    default="Тонировать фон акцентным цветом",
                ),
                tr_catalog(
                    "page.appearance.accent.tint_background.description",
                    language=self._ui_language,
                    default="Фон окна окрашивается в оттенок акцентного цвета",
                ),
            )
            self._tinted_bg_cb.toggled.connect(self._on_tinted_bg_changed)
            if accent_layout is not None:
                accent_layout.addWidget(self._tinted_bg_cb)
            else:
                accent_card.addSettingCard(self._tinted_bg_cb)

            self._tinted_intensity_container = QWidget()
            intensity_row_layout = QHBoxLayout(self._tinted_intensity_container)
            intensity_row_layout.setContentsMargins(8, 0, 8, 0)
            intensity_row_layout.setSpacing(8)
            intensity_label = CaptionLabel(
                tr_catalog(
                    "page.appearance.accent.tint_intensity.label",
                    language=self._ui_language,
                    default="Интенсивность тонировки:",
                )
            )
            self._tinted_intensity_label = intensity_label
            self._tinted_intensity_slider = Slider(Qt.Orientation.Horizontal)
            self._tinted_intensity_slider.setRange(0, 30)
            self._tinted_intensity_slider.setValue(15)
            self._tinted_intensity_value_label = CaptionLabel("15")
            self._tinted_intensity_slider.valueChanged.connect(self._on_tinted_intensity_changed)
            intensity_row_layout.addWidget(intensity_label)
            intensity_row_layout.addWidget(self._tinted_intensity_slider, 1)
            intensity_row_layout.addWidget(self._tinted_intensity_value_label)
            if accent_layout is not None:
                accent_layout.addWidget(self._tinted_intensity_container)
            else:
                self._tinted_intensity_row = SettingsRow(
                    "fa5s.sliders-h",
                    tr_catalog(
                        "page.appearance.accent.tint_intensity.label",
                        language=self._ui_language,
                        default="Интенсивность тонировки:",
                    ),
                    "",
                )
                self._tinted_intensity_row.set_control(self._tinted_intensity_container)
                accent_card.addSettingCard(self._tinted_intensity_row)

            if accent_layout is not None:
                accent_card.add_layout(accent_layout)
            else:
                enable_setting_card_group_auto_height(accent_card)
            self.add_widget(accent_card)

            self.add_spacing(16)
            self._load_accent_color()
            self._load_extra_accent_settings()

        # ═══════════════════════════════════════════════════════════
        # ПРОИЗВОДИТЕЛЬНОСТЬ
        # ═══════════════════════════════════════════════════════════
        if SettingCardGroup is not None and _HAS_FLUENT_LABELS:
            self._performance_group = SettingCardGroup(
                tr_catalog("page.appearance.section.performance", language=self._ui_language, default="Производительность"),
                self.content,
            )
            perf_card = self._performance_group
            perf_layout = None
        else:
            self.add_section_title(text_key="page.appearance.section.performance")
            self._performance_group = None
            perf_card = SettingsCard()
            perf_layout = QVBoxLayout()
            perf_layout.setSpacing(12)

        self._performance_card = perf_card
        self._animations_switch = Win11ToggleRow(
            "fa5s.film",
            tr_catalog("page.appearance.performance.animations.title", language=self._ui_language, default="Анимации интерфейса"),
            tr_catalog(
                "page.appearance.performance.animations.description",
                language=self._ui_language,
                default="Анимации кнопок, переходов и элементов WinUI",
            ),
        )
        self._animations_switch.toggled.connect(self._on_animations_changed)
        if perf_layout is not None:
            perf_layout.addWidget(self._animations_switch)
        else:
            perf_card.addSettingCard(self._animations_switch)

        self._smooth_scroll_switch = Win11ToggleRow(
            "fa5s.mouse",
            tr_catalog("page.appearance.performance.scroll.title", language=self._ui_language, default="Плавная прокрутка"),
            tr_catalog(
                "page.appearance.performance.scroll.description",
                language=self._ui_language,
                default="Инерционная прокрутка страниц настроек",
            ),
        )
        self._smooth_scroll_switch.toggled.connect(self._on_smooth_scroll_changed)
        if perf_layout is not None:
            perf_layout.addWidget(self._smooth_scroll_switch)
        else:
            perf_card.addSettingCard(self._smooth_scroll_switch)

        self._editor_smooth_scroll_switch = Win11ToggleRow(
            "fa5s.file-alt",
            tr_catalog(
                "page.appearance.performance.editor_scroll.title",
                language=self._ui_language,
                default="Плавная прокрутка редакторов",
            ),
            tr_catalog(
                "page.appearance.performance.editor_scroll.description",
                language=self._ui_language,
                default="Плавная прокрутка внутри больших текстовых полей и редакторов. Работает только при включённых анимациях интерфейса.",
            ),
        )
        self._editor_smooth_scroll_switch.toggled.connect(self._on_editor_smooth_scroll_changed)
        if perf_layout is not None:
            perf_layout.addWidget(self._editor_smooth_scroll_switch)
        else:
            perf_card.addSettingCard(self._editor_smooth_scroll_switch)

        if perf_layout is not None:
            perf_card.add_layout(perf_layout)
        self.add_widget(perf_card)
        self.add_spacing(16)
        self._load_performance_settings()

        # Load saved display mode and bg preset
        self._load_display_mode()
        self._load_bg_preset()
        self._load_ui_language()

    def _show_accent_color_dialog(self) -> None:
        """Открывает fluent-диалог выбора цвета с нормальным русским заголовком."""
        if self._color_picker_btn is None or ColorDialog is None:
            return
        try:
            title = tr_catalog(
                "page.appearance.accent.color.pick",
                language=self._ui_language,
                default="Выбрать цвет",
            )
            dialog = ColorDialog(
                QColor(self._color_picker_btn.color),
                title,
                self.window(),
                False,
            )

            def _apply_color(color: QColor) -> None:
                try:
                    self._color_picker_btn.setColor(color)
                    self._color_picker_btn.colorChanged.emit(color)
                except Exception:
                    pass

            dialog.colorChanged.connect(_apply_color)
            dialog.exec()
        except Exception:
            pass

    def _load_display_mode(self):
        """Load saved display mode from registry."""
        mode = AppearancePageController.load_display_mode()
        if self._display_mode_seg is not None:
            self._display_mode_seg.blockSignals(True)
            try:
                self._display_mode_seg.setCurrentItem(mode)
            except Exception:
                pass
            self._display_mode_seg.blockSignals(False)

    def _on_display_mode_changed(self, mode: str):
        """Handle display mode toggle."""
        plan = AppearancePageController.save_display_mode(mode)
        effective_mode = plan.effective_mode

        if self._display_mode_seg is not None and effective_mode != mode:
            self._display_mode_seg.blockSignals(True)
            try:
                self._display_mode_seg.setCurrentItem(effective_mode)
            except Exception:
                pass
            self._display_mode_seg.blockSignals(False)

        try:
            from qfluentwidgets import setTheme, Theme
            if effective_mode == "light":
                setTheme(Theme.LIGHT)
            elif effective_mode == "dark":
                setTheme(Theme.DARK)
            elif effective_mode == "system":
                setTheme(Theme.AUTO)
        except Exception:
            pass
        # Update window background colors for the new mode
        try:
            from ui.theme import apply_window_background
            win = self.window()
            if win is not None:
                apply_window_background(win)
        except Exception:
            pass
        self.display_mode_changed.emit(effective_mode)

    def _load_ui_language(self):
        if self._language_combo is None:
            return

        plan = AppearancePageController.load_ui_language()
        lang = plan.language

        index = -1
        try:
            index = self._language_combo.findData(lang)
        except Exception:
            index = -1

        if index < 0:
            index = 0

        try:
            self._language_combo.blockSignals(True)
            self._language_combo.setCurrentIndex(index)
            self._language_combo.blockSignals(False)
        except Exception:
            pass

    def _on_ui_language_changed(self, index: int) -> None:
        if self._language_combo is None:
            return

        try:
            lang = self._language_combo.itemData(index)
        except Exception:
            lang = None

        if not isinstance(lang, str) or not lang:
            return

        plan = AppearancePageController.save_ui_language(lang)
        self.ui_language_changed.emit(plan.language)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        from ui.text_catalog import tr as tr_catalog

        if self._language_desc_label is not None:
            try:
                self._language_desc_label.setText(
                    tr_catalog("appearance.language.desc", language=language)
                )
            except Exception:
                pass

        if self._language_name_label is not None:
            try:
                self._language_name_label.setText(
                    tr_catalog("appearance.language.label", language=language)
                )
            except Exception:
                pass

        if self._language_combo is not None:
            try:
                from ui.text_catalog import normalize_language

                normalized = normalize_language(language)
                idx = self._language_combo.findData(normalized)
                if idx >= 0:
                    self._language_combo.blockSignals(True)
                    self._language_combo.setCurrentIndex(idx)
                    self._language_combo.blockSignals(False)
            except Exception:
                pass

        try:
            title_label = getattr(getattr(self, "_accent_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(
                    tr_catalog("page.appearance.section.accent", language=language, default="Акцентный цвет")
                )
        except Exception:
            pass

        try:
            title_label = getattr(getattr(self, "_performance_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(
                    tr_catalog("page.appearance.section.performance", language=language, default="Производительность")
                )
        except Exception:
            pass

        if self._accent_desc_label is not None:
            self._accent_desc_label.setText(
                tr_catalog(
                    "page.appearance.accent.description",
                    language=language,
                    default=(
                        "Цвет акцентных элементов интерфейса: кнопок, иконок, индикаторов. "
                        "Изменяет цвет нативных компонентов WinUI."
                    ),
                )
            )

        if self._accent_color_row is not None:
            self._accent_color_row.set_title(
                tr_catalog("page.appearance.accent.color.title", language=language, default="Цвет акцента")
            )

        if self._follow_windows_accent_cb is not None:
            self._follow_windows_accent_cb.set_texts(
                tr_catalog("page.appearance.accent.windows.title", language=language, default="Акцент из Windows"),
                tr_catalog(
                    "page.appearance.accent.windows.description",
                    language=language,
                    default="Автоматически использовать системный акцентный цвет Windows",
                ),
            )

        if self._tinted_bg_cb is not None:
            self._tinted_bg_cb.set_texts(
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

        if self._tinted_intensity_label is not None:
            self._tinted_intensity_label.setText(
                tr_catalog(
                    "page.appearance.accent.tint_intensity.label",
                    language=language,
                    default="Интенсивность тонировки:",
                )
            )

        if self._animations_switch is not None:
            self._animations_switch.set_texts(
                tr_catalog("page.appearance.performance.animations.title", language=language, default="Анимации интерфейса"),
                tr_catalog(
                    "page.appearance.performance.animations.description",
                    language=language,
                    default="Анимации кнопок, переходов и элементов WinUI",
                ),
            )

        if self._smooth_scroll_switch is not None:
            self._smooth_scroll_switch.set_texts(
                tr_catalog("page.appearance.performance.scroll.title", language=language, default="Плавная прокрутка"),
                tr_catalog(
                    "page.appearance.performance.scroll.description",
                    language=language,
                    default="Инерционная прокрутка страниц настроек",
                ),
            )
        if self._editor_smooth_scroll_switch is not None:
            self._editor_smooth_scroll_switch.set_texts(
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

    def _load_bg_preset(self):
        """Load saved background preset from registry."""
        plan = AppearancePageController.load_background_preset()
        self._apply_bg_preset_ui(plan.preset)

    def _apply_bg_preset_ui(self, preset: str):
        """Update RadioButton selection without emitting signals."""
        for radio, key in [
            (self._bg_radio_standard, "standard"),
            (self._bg_radio_amoled, "amoled"),
            (self._bg_radio_rkn_chan, "rkn_chan"),
        ]:
            if radio is not None:
                radio.blockSignals(True)
                radio.setChecked(key == preset)
                radio.blockSignals(False)
        self._update_rkn_background_control_state()
        self._update_display_mode_section_state(preset)

    @staticmethod
    def _should_show_display_mode_for_preset(preset: str | None) -> bool:
        preset_name = str(preset or "").strip().lower()
        return preset_name not in ("amoled", "rkn_chan")

    def _update_display_mode_section_state(self, preset: str | None = None) -> None:
        if preset is None:
            preset = AppearancePageController.load_background_preset().preset

        show_section = self._should_show_display_mode_for_preset(preset)

        for widget in (
            self._display_mode_section_title,
            self._display_mode_card,
            self._display_mode_spacer,
        ):
            if widget is not None:
                widget.setVisible(show_section)

        if self._display_mode_seg is not None:
            self._display_mode_seg.setEnabled(show_section)

    def _reload_rkn_background_options(self):
        if self._rkn_background_combo is None:
            return

        saved_value = AppearancePageController.load_rkn_background().value

        options = get_rkn_background_options()

        self._rkn_background_combo.blockSignals(True)
        try:
            self._rkn_background_combo.clear()
        except Exception:
            pass

        if options:
            for rel_path, label in options:
                self._rkn_background_combo.addItem(label, userData=rel_path)

            selected = str(saved_value or "").strip().replace("\\", "/")
            index = -1
            if selected:
                try:
                    index = self._rkn_background_combo.findData(selected)
                except Exception:
                    index = -1
            if index < 0:
                index = 0
            self._rkn_background_combo.setCurrentIndex(index)

            selected_rel = self._rkn_background_combo.itemData(index)
            if isinstance(selected_rel, str) and selected_rel:
                AppearancePageController.save_rkn_background(selected_rel)
        else:
            self._rkn_background_combo.addItem(
                tr_catalog("page.appearance.background.rkn.none", language=self._ui_language, default="Фоны не найдены"),
                userData="",
            )
            self._rkn_background_combo.setCurrentIndex(0)

        self._rkn_background_combo.blockSignals(False)
        self._update_rkn_background_control_state()

    def _update_rkn_background_control_state(self):
        if self._rkn_background_combo is None:
            return

        try:
            current_data = self._rkn_background_combo.itemData(self._rkn_background_combo.currentIndex())
            has_options = isinstance(current_data, str) and bool(current_data)
        except Exception:
            has_options = False

        is_rkn_selected = bool(self._bg_radio_rkn_chan and self._bg_radio_rkn_chan.isChecked())
        is_premium, _garland_enabled, _snowflakes_enabled, _window_opacity = self._current_appearance_state()
        self._rkn_background_combo.setEnabled(bool(is_premium and is_rkn_selected and has_options))

    def _on_rkn_background_changed(self, index: int):
        if self._rkn_background_combo is None or index < 0:
            return

        try:
            selected_rel = self._rkn_background_combo.itemData(index)
        except Exception:
            selected_rel = None

        if not isinstance(selected_rel, str) or not selected_rel:
            return

        AppearancePageController.save_rkn_background(selected_rel)

        if self._bg_radio_rkn_chan is not None and self._bg_radio_rkn_chan.isChecked():
            self.background_refresh_needed.emit()

    def _on_bg_preset_toggled(self, preset: str, checked: bool):
        """Handle background preset RadioButton toggle."""
        if not checked:
            return
        plan = AppearancePageController.save_background_preset(preset)
        preset = plan.preset
        if self._mica_switch:
            self._mica_switch.setEnabled(preset == "standard")
        # AMOLED and РКН Тян require dark mode — force it automatically
        if preset in ("amoled", "rkn_chan"):
            self._on_display_mode_changed("dark")
            if self._display_mode_seg is not None:
                self._display_mode_seg.blockSignals(True)
                try:
                    self._display_mode_seg.setCurrentItem("dark")
                except Exception:
                    pass
                self._display_mode_seg.blockSignals(False)
        if preset == "rkn_chan":
            self._reload_rkn_background_options()
        self._update_rkn_background_control_state()
        self._update_display_mode_section_state(preset)
        self.background_preset_changed.emit(preset)

    def _on_mica_changed(self, checked: bool):
        """Handle Mica SwitchButton toggle."""
        self.mica_changed.emit(checked)

    def set_mica_state(self, enabled: bool):
        """Set Mica SwitchButton state without triggering signal."""
        if self._mica_switch:
            self._mica_switch.blockSignals(True)
            self._mica_switch.setChecked(enabled)
            self._mica_switch.blockSignals(False)

    def _load_mica_state(self):
        """Load Mica state from registry."""
        mica_plan = AppearancePageController.load_mica_enabled()
        self.set_mica_state(mica_plan.enabled)
        if self._mica_switch:
            preset = AppearancePageController.load_background_preset().preset
            self._mica_switch.setEnabled(preset == "standard")

    def _apply_theme_tokens(self, theme_name: str) -> None:
        """Refresh qtawesome icon labels on theme change."""
        try:
            tokens = get_theme_tokens(theme_name)
        except Exception:
            tokens = get_theme_tokens()
        self._refresh_accent_icons(tokens)

    def _on_opacity_changed(self, value: int):
        """Обработчик изменения прозрачности окна"""
        # Обновляем лейбл
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

        opacity_plan = AppearancePageController.save_window_opacity(value)

        # Уведомляем главное окно
        self.opacity_changed.emit(opacity_plan.value)

        from log import log
        log(f"Прозрачность окна: {opacity_plan.value}%", "DEBUG")

    def _on_snowflakes_changed(self, state):
        """Обработчик изменения состояния снежинок"""
        enabled = state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_snowflakes_enabled(enabled)
        self.snowflakes_changed.emit(plan.enabled)

    def _on_garland_changed(self, state):
        """Обработчик изменения состояния гирлянды"""
        enabled = state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_garland_enabled(enabled)
        self.garland_changed.emit(plan.enabled)

    def _on_accent_color_changed(self, color: QColor):
        """Обработчик изменения акцентного цвета через ColorPickerButton."""
        if not _HAS_COLOR_PICKER:
            return
        try:
            setThemeColor(color)
        except Exception:
            pass
        hex_color = color.name()
        plan = AppearancePageController.save_accent_color(hex_color)
        if plan.hex_color:
            self.accent_color_changed.emit(plan.hex_color)
        # If tinted bg is active, trigger window background refresh
        tinted_plan = AppearancePageController.load_tinted_settings()
        if tinted_plan.tinted_background:
            self.background_refresh_needed.emit()

    def _refresh_accent_icons(self, tokens=None):
        """Обновляет иконки страницы при смене акцентного цвета."""
        if tokens is None:
            tokens = get_theme_tokens()
        for lbl, icon_name, size in (
            (self._garland_icon_label,   'fa5s.holly-berry', 20),
            (self._snowflakes_icon_label, 'fa5s.snowflake',  20),
            (self._opacity_icon_label,    'fa5s.adjust',     20),
        ):
            if lbl is not None:
                lbl.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(size, size))

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = force
        self._refresh_accent_icons(tokens=tokens)

    def _load_extra_accent_settings(self):
        """Загружает настройки Follow Windows Accent и Tinted Background."""
        if not _HAS_COLOR_PICKER:
            return
        plan = AppearancePageController.load_tinted_settings()

        if self._follow_windows_accent_cb is not None:
            try:
                self._follow_windows_accent_cb.setChecked(plan.follow_windows_accent, block_signals=True)
            except TypeError:
                self._follow_windows_accent_cb.blockSignals(True)
                self._follow_windows_accent_cb.setChecked(plan.follow_windows_accent)
                self._follow_windows_accent_cb.blockSignals(False)

        if self._tinted_bg_cb is not None:
            try:
                self._tinted_bg_cb.setChecked(plan.tinted_background, block_signals=True)
            except TypeError:
                self._tinted_bg_cb.blockSignals(True)
                self._tinted_bg_cb.setChecked(plan.tinted_background)
                self._tinted_bg_cb.blockSignals(False)

        if self._tinted_intensity_slider is not None:
            self._tinted_intensity_slider.blockSignals(True)
            self._tinted_intensity_slider.setValue(plan.tinted_intensity)
            self._tinted_intensity_slider.blockSignals(False)

        if self._tinted_intensity_value_label is not None:
            self._tinted_intensity_value_label.setText(str(plan.tinted_intensity))

        if self._tinted_intensity_container is not None:
            self._tinted_intensity_container.setVisible(plan.tinted_background)

        if plan.follow_windows_accent:
            self._apply_windows_accent()
            if self._color_picker_btn is not None:
                self._color_picker_btn.setEnabled(False)

    def _on_follow_windows_accent_changed(self, state):
        """Обработчик переключения 'Акцент из Windows'."""
        enabled = bool(state) if isinstance(state, bool) else state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_follow_windows_accent(enabled)
        if plan.enabled:
            self._apply_windows_accent()
            if self._color_picker_btn is not None:
                self._color_picker_btn.setEnabled(False)
        else:
            if self._color_picker_btn is not None:
                self._color_picker_btn.setEnabled(True)

    def _apply_windows_accent(self):
        """Читает системный акцент Windows и применяет его."""
        try:
            plan = AppearancePageController.load_windows_system_accent()
            hex_color = plan.hex_color
            if hex_color:
                color = QColor(hex_color)
                if color.isValid():
                    setThemeColor(color)
                    AppearancePageController.save_accent_color(hex_color)
                    if self._color_picker_btn is not None:
                        self._color_picker_btn.setColor(color)
                    self.accent_color_changed.emit(hex_color)
                    self.background_refresh_needed.emit()
        except Exception:
            pass

    def _on_tinted_bg_changed(self, state):
        """Обработчик переключения 'Тонировать фон'."""
        enabled = bool(state) if isinstance(state, bool) else state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_tinted_background(enabled)
        if self._tinted_intensity_container is not None:
            self._tinted_intensity_container.setVisible(plan.enabled)
        self.background_refresh_needed.emit()

    def _on_tinted_intensity_changed(self, value: int):
        """Обработчик изменения интенсивности тонировки."""
        plan = AppearancePageController.save_tinted_background_intensity(value)
        if self._tinted_intensity_value_label is not None:
            self._tinted_intensity_value_label.setText(str(plan.value))
        self.background_refresh_needed.emit()

    def _load_accent_color(self):
        """Загружает сохранённый акцентный цвет и применяет его."""
        if not _HAS_COLOR_PICKER or self._color_picker_btn is None:
            return
        plan = AppearancePageController.load_accent_color()
        hex_color = plan.hex_color
        if hex_color:
            color = QColor(hex_color)
            if color.isValid():
                self._color_picker_btn.setColor(color)
                setThemeColor(color)

    def set_current_theme(self, theme_name: str):
        """No-op: theme selection removed. Kept for backward compatibility."""
        pass

    def update_themes(self, themes: list, current_theme: str = None):
        """No-op: theme selection removed. Kept for backward compatibility."""
        pass

    def set_premium_status(self, is_premium: bool):
        """Update premium status — unlocks AMOLED/РКН Тян bg presets."""
        was_garland_enabled = bool(self._garland_checkbox and self._garland_checkbox.isChecked())
        was_snowflakes_enabled = bool(self._snowflakes_checkbox and self._snowflakes_checkbox.isChecked())

        # Unlock/lock premium bg preset radio buttons
        if self._bg_radio_amoled is not None:
            self._bg_radio_amoled.setEnabled(is_premium)
        if self._bg_radio_rkn_chan is not None:
            self._bg_radio_rkn_chan.setEnabled(is_premium)
        self._update_rkn_background_control_state()

        current_preset = AppearancePageController.load_background_preset().preset
        premium_effects = AppearancePageController.load_premium_effects()
        premium_plan = AppearancePageController.build_premium_status_plan(
            is_premium=is_premium,
            current_preset=current_preset,
            was_garland_enabled=was_garland_enabled,
            was_snowflakes_enabled=was_snowflakes_enabled,
            premium_effects=premium_effects,
        )

        if premium_plan.effective_preset is not None:
            preset_plan = AppearancePageController.save_background_preset(premium_plan.effective_preset)
            self._apply_bg_preset_ui(preset_plan.preset)
            self.background_preset_changed.emit(preset_plan.preset)

        if self._garland_checkbox:
            self._garland_checkbox.setEnabled(is_premium)
            self._garland_checkbox.blockSignals(True)
            self._garland_checkbox.setChecked(premium_plan.garland_checked)
            self._garland_checkbox.blockSignals(False)

        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.setEnabled(is_premium)
            self._snowflakes_checkbox.blockSignals(True)
            self._snowflakes_checkbox.setChecked(premium_plan.snowflakes_checked)
            self._snowflakes_checkbox.blockSignals(False)

        if premium_plan.disable_garland:
            plan = AppearancePageController.save_garland_enabled(False)
            self.garland_changed.emit(plan.enabled)

        if premium_plan.disable_snowflakes:
            plan = AppearancePageController.save_snowflakes_enabled(False)
            self.snowflakes_changed.emit(plan.enabled)

        self._update_display_mode_section_state()

    def set_garland_state(self, enabled: bool):
        """Устанавливает состояние чекбокса гирлянды (без эмита сигнала)"""
        if self._garland_checkbox:
            self._garland_checkbox.blockSignals(True)
            self._garland_checkbox.setChecked(enabled)
            self._garland_checkbox.blockSignals(False)

    def set_snowflakes_state(self, enabled: bool):
        """Устанавливает состояние чекбокса снежинок (без эмита сигнала)"""
        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.blockSignals(True)
            self._snowflakes_checkbox.setChecked(enabled)
            self._snowflakes_checkbox.blockSignals(False)

    def set_opacity_value(self, value: int):
        """Устанавливает значение слайдера прозрачности (без эмита сигнала)"""
        if self._opacity_slider:
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(value)
            self._opacity_slider.blockSignals(False)
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

    def _current_appearance_state(self) -> tuple[bool, bool, bool, int]:
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                return (
                    bool(snapshot.subscription_is_premium),
                    bool(snapshot.garland_enabled),
                    bool(snapshot.snowflakes_enabled),
                    int(snapshot.window_opacity),
                )
            except Exception:
                pass

        garland_enabled = bool(self._garland_checkbox and self._garland_checkbox.isChecked())
        snowflakes_enabled = bool(self._snowflakes_checkbox and self._snowflakes_checkbox.isChecked())
        window_opacity = int(self._opacity_slider.value()) if self._opacity_slider is not None else 100
        return False, garland_enabled, snowflakes_enabled, window_opacity

    def _on_animations_changed(self, enabled: bool):
        """Handle animations SwitchButton toggle."""
        plan = AppearancePageController.save_animations_enabled(enabled)
        self.animations_changed.emit(plan.enabled)
        self._sync_performance_dependencies(plan.enabled)

        editor_plan = AppearancePageController.load_editor_smooth_scroll_enabled()
        self.editor_smooth_scroll_changed.emit(editor_plan.enabled)

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Handle smooth scroll SwitchButton toggle."""
        plan = AppearancePageController.save_smooth_scroll_enabled(enabled)
        self.smooth_scroll_changed.emit(plan.enabled)

    def _on_editor_smooth_scroll_changed(self, enabled: bool):
        """Handle editor smooth scroll toggle."""
        plan = AppearancePageController.save_editor_smooth_scroll_enabled(enabled)
        self.editor_smooth_scroll_changed.emit(plan.enabled)

    def _sync_performance_dependencies(self, animations_enabled: bool) -> None:
        """Редакторская плавность зависит от мастер-переключателя анимаций."""
        if self._editor_smooth_scroll_switch is not None:
            self._editor_smooth_scroll_switch.setEnabled(bool(animations_enabled))

    def _load_performance_settings(self):
        """Load performance state from registry into switches."""
        anim_plan = AppearancePageController.load_animations_enabled()
        smooth_plan = AppearancePageController.load_smooth_scroll_enabled()
        editor_plan = AppearancePageController.load_editor_smooth_scroll_enabled()
        if self._animations_switch is not None:
            try:
                self._animations_switch.setChecked(anim_plan.enabled, block_signals=True)
            except TypeError:
                self._animations_switch.blockSignals(True)
                self._animations_switch.setChecked(anim_plan.enabled)
                self._animations_switch.blockSignals(False)
        if self._smooth_scroll_switch is not None:
            try:
                self._smooth_scroll_switch.setChecked(smooth_plan.enabled, block_signals=True)
            except TypeError:
                self._smooth_scroll_switch.blockSignals(True)
                self._smooth_scroll_switch.setChecked(smooth_plan.enabled)
                self._smooth_scroll_switch.blockSignals(False)
        if self._editor_smooth_scroll_switch is not None:
            try:
                self._editor_smooth_scroll_switch.setChecked(editor_plan.enabled, block_signals=True)
            except TypeError:
                self._editor_smooth_scroll_switch.blockSignals(True)
                self._editor_smooth_scroll_switch.setChecked(editor_plan.enabled)
                self._editor_smooth_scroll_switch.blockSignals(False)
        self._sync_performance_dependencies(anim_plan.enabled)
