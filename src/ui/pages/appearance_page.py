# ui/pages/appearance_page.py
"""Страница настроек оформления - темы"""

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QColor

from .base_page import BasePage
import settings.appearance as appearance_settings
from ui.pages.appearance_page_lower_build import (
    build_holiday_sections,
    build_opacity_section,
    build_performance_section,
)
from ui.pages.appearance_page_runtime_helpers import (
    apply_appearance_language,
)
from ui.pages.appearance_page_top_build import (
    build_background_section,
    build_display_mode_section,
    build_language_section,
)
from ui.fluent_widgets import (
    SettingsCard,
    SettingsRow,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from app.state_store import AppUiState, MainWindowStateStore
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from app.ui_texts import tr as tr_catalog
from ui.widgets.win11_controls import Win11ToggleRow
from log.log import log
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ColorPickerButton,
    setThemeColor,
    ColorDialog,
    CheckBox,
    SegmentedWidget,
    RadioButton,
    Slider,
    ComboBox,
    SettingCardGroup,
)


class AppearancePage(BasePage):
    """Страница настроек оформления"""

    def __init__(
        self,
        parent=None,
        *,
        on_garland_changed,
        on_snowflakes_changed,
        on_background_refresh_needed,
        on_background_preset_changed,
        on_opacity_changed,
        on_mica_changed,
        on_animations_changed,
        on_smooth_scroll_changed,
        on_editor_smooth_scroll_changed,
        on_ui_language_changed,
        on_sidebar_icon_style_changed,
        appearance_feature,
        ui_state_store,
    ):
        super().__init__(
            "Оформление",
            "Настройка внешнего вида приложения",
            parent,
            title_key="page.appearance.title",
            subtitle_key="page.appearance.subtitle",
        )
        self._on_garland_changed_callback = on_garland_changed
        self._on_snowflakes_changed_callback = on_snowflakes_changed
        self._on_background_refresh_needed_callback = on_background_refresh_needed
        self._on_background_preset_changed_callback = on_background_preset_changed
        self._on_opacity_changed_callback = on_opacity_changed
        self._on_mica_changed_callback = on_mica_changed
        self._on_animations_changed_callback = on_animations_changed
        self._on_smooth_scroll_changed_callback = on_smooth_scroll_changed
        self._on_editor_smooth_scroll_changed_callback = on_editor_smooth_scroll_changed
        self._on_ui_language_changed_callback = on_ui_language_changed
        self._on_sidebar_icon_style_changed_callback = on_sidebar_icon_style_changed
        self._appearance = appearance_feature

        self._display_mode_seg = None    # SegmentedWidget
        self._display_mode_section_title = None
        self._display_mode_card = None
        self._display_mode_spacer = None
        self._language_combo = None      # ComboBox
        self._language_desc_label = None
        self._language_name_label = None
        self._sidebar_icon_style_seg = None
        self._sidebar_icon_style_card = None
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
        self._initial_state_plan = None
        self._lower_sections_built = False
        self._lower_sections_build_scheduled = False
        self._ui_sync_depth = 0
        self._background_refresh_queued = False
        self._cleanup_in_progress = False
        self._appearance_save_runtime = OneShotWorkerRuntime()
        self._appearance_save_pending: list[dict[str, object]] = []
        self._appearance_save_start_scheduled = False
        self._initial_state_load_runtime = OneShotWorkerRuntime()
        self._initial_state_load_pending = False
        self._initial_state_load_pending_force = False
        self._initial_state_load_start_scheduled = False
        self._rkn_background_options_runtime = OneShotWorkerRuntime()
        self._rkn_background_options_pending = False
        self._rkn_background_options_start_scheduled = False
        self._windows_accent_load_runtime = OneShotWorkerRuntime()
        self._windows_accent_load_pending = False
        self._windows_accent_load_start_scheduled = False
        self._build_ui()
        self.bind_ui_state_store(ui_state_store)

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

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        if changed == {"window_opacity"}:
            self.set_opacity_value(state.window_opacity)
            return
        if changed == {"garland_enabled"} and bool(state.subscription_is_premium):
            self.set_garland_state(state.garland_enabled)
            return
        if changed == {"snowflakes_enabled"} and bool(state.subscription_is_premium):
            self.set_snowflakes_state(state.snowflakes_enabled)
            return
        premium_effects = appearance_settings.AppearancePremiumEffectsPlan(
            garland_enabled=bool(state.garland_enabled),
            snowflakes_enabled=bool(state.snowflakes_enabled),
        )
        self.set_premium_status(
            state.subscription_is_premium,
            current_preset=self._current_bg_preset_from_ui(),
            premium_effects=premium_effects,
        )
        self.set_garland_state(state.garland_enabled)
        self.set_snowflakes_state(state.snowflakes_enabled)
        self.set_opacity_value(state.window_opacity)

    def _begin_ui_sync(self) -> None:
        self._ui_sync_depth += 1

    def _end_ui_sync(self) -> None:
        if self._ui_sync_depth > 0:
            self._ui_sync_depth -= 1

    def _is_ui_syncing(self) -> bool:
        return self._ui_sync_depth > 0

    def _set_checked_silently(self, widget, value: bool) -> None:
        if widget is None:
            return
        try:
            widget.setChecked(bool(value), block_signals=True)
            return
        except TypeError:
            pass
        widget.blockSignals(True)
        try:
            widget.setChecked(bool(value))
        finally:
            widget.blockSignals(False)

    def _set_current_index_silently(self, widget, index: int) -> None:
        if widget is None:
            return
        widget.blockSignals(True)
        try:
            widget.setCurrentIndex(int(index))
        finally:
            widget.blockSignals(False)

    def _set_current_item_silently(self, widget, item) -> None:
        if widget is None:
            return
        widget.blockSignals(True)
        try:
            widget.setCurrentItem(item)
        finally:
            widget.blockSignals(False)

    def _set_slider_value_silently(self, widget, value: int) -> None:
        if widget is None:
            return
        widget.blockSignals(True)
        try:
            widget.setValue(int(value))
        finally:
            widget.blockSignals(False)

    def _schedule_background_refresh(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._background_refresh_queued:
            return
        self._background_refresh_queued = True
        QTimer.singleShot(0, self._flush_background_refresh)

    def _flush_background_refresh(self) -> None:
        if self._cleanup_in_progress:
            self._background_refresh_queued = False
            return
        self._background_refresh_queued = False
        self._on_background_refresh_needed_callback()

    def _emit_accent_update(self, hex_color: str | None = None, *, refresh_background: bool = False) -> None:
        if refresh_background:
            self._schedule_background_refresh()

    def _build_ui(self):
        total_started_at = time.perf_counter()
        warmed_state = appearance_settings.consume_warmed_page_initial_state()
        initial_state = warmed_state or appearance_settings.build_default_page_initial_state()
        if warmed_state is not None:
            self._initial_state_plan = warmed_state
        else:
            initial_state.ui_language = self._ui_language
        self._ui_language = initial_state.ui_language
        # ═══════════════════════════════════════════════════════════
        # РЕЖИМ ОТОБРАЖЕНИЯ
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        display_widgets = build_display_mode_section(
            page=self,
            tr_language=self._ui_language,
            add_section_title=self.add_section_title,
            content_parent=self.content,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            segmented_widget_cls=SegmentedWidget,
            on_display_mode_changed=self._on_display_mode_changed,
        )
        self._display_mode_section_title = display_widgets.section_title
        self._display_mode_card = display_widgets.card
        self._display_mode_seg = display_widgets.segmented
        self._display_mode_spacer = display_widgets.spacer
        self.add_widget(display_widgets.card)
        self.add_widget(display_widgets.spacer)
        self._log_ui_timing("appearance_ui.display_section.build", section_started_at)

        # ═══════════════════════════════════════════════════════════
        # ЯЗЫК ИНТЕРФЕЙСА
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        language_widgets = build_language_section(
            tr_language=initial_state.ui_language,
            add_section_title=self.add_section_title,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            on_ui_language_changed=self._on_ui_language_changed,
        )
        self._language_desc_label = language_widgets.desc_label
        self._language_name_label = language_widgets.name_label
        self._language_combo = language_widgets.combo
        self.add_widget(language_widgets.card)
        self._log_ui_timing("appearance_ui.language_section.build", section_started_at)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ИКОНКИ БОКОВОГО МЕНЮ
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        self.add_section_title(
            "Иконки меню",
            text_key="page.appearance.section.sidebar_icons",
        )
        sidebar_icon_card = SettingsCard()
        sidebar_icon_layout = QVBoxLayout()
        sidebar_icon_layout.setSpacing(12)
        sidebar_icon_desc = CaptionLabel(
            tr_catalog(
                "page.appearance.sidebar_icons.description",
                language=self._ui_language,
                default="Выберите стиль иконок в левом боковом меню.",
            )
        )
        sidebar_icon_desc.setWordWrap(True)
        sidebar_icon_layout.addWidget(sidebar_icon_desc)
        sidebar_icon_seg = SegmentedWidget()
        sidebar_icon_seg.addItem(
            "standard",
            tr_catalog("page.appearance.sidebar_icons.option.standard", language=self._ui_language, default="Стандартные"),
            lambda: self._on_sidebar_icon_style_changed("standard"),
        )
        sidebar_icon_seg.addItem(
            "windows11_fluent",
            tr_catalog(
                "page.appearance.sidebar_icons.option.windows11_fluent",
                language=self._ui_language,
                default="Windows 11 Fluent",
            ),
            lambda: self._on_sidebar_icon_style_changed("windows11_fluent"),
        )
        sidebar_icon_layout.addWidget(sidebar_icon_seg)
        sidebar_icon_card.add_layout(sidebar_icon_layout)
        self._sidebar_icon_style_card = sidebar_icon_card
        self._sidebar_icon_style_seg = sidebar_icon_seg
        self.add_widget(sidebar_icon_card)
        self._log_ui_timing("appearance_ui.sidebar_icon_section.build", section_started_at)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ФОН ОКНА
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        background_widgets = build_background_section(
            tr_language=self._ui_language,
            add_section_title=self.add_section_title,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            radio_button_cls=RadioButton,
            combo_cls=ComboBox,
            on_bg_preset_toggled=self._on_bg_preset_toggled,
            on_rkn_background_changed=self._on_rkn_background_changed,
        )
        self._bg_radio_standard = background_widgets.radio_standard
        self._bg_radio_amoled = background_widgets.radio_amoled
        self._bg_radio_rkn_chan = background_widgets.radio_rkn_chan
        self._rkn_background_combo = background_widgets.rkn_background_combo
        self.add_widget(background_widgets.card)
        self._log_ui_timing("appearance_ui.background_section.build", section_started_at)

        self.add_spacing(16)

        # Load saved display mode and bg preset
        section_started_at = time.perf_counter()
        self._apply_initial_display_state(initial_state)
        self._request_initial_state_load(force=warmed_state is None)
        self._log_ui_timing("appearance_ui.initial_state.load", section_started_at)
        self._log_ui_timing("appearance_ui.build.total", total_started_at)

    def on_page_activated(self) -> None:
        self._schedule_lower_sections_build()

    def on_page_hidden(self) -> None:
        self._lower_sections_build_scheduled = False

    def _schedule_lower_sections_build(self) -> None:
        if self._lower_sections_built or self._lower_sections_build_scheduled:
            return
        self._lower_sections_build_scheduled = True
        QTimer.singleShot(0, self._ensure_lower_sections_built)

    def _ensure_lower_sections_built(self) -> bool:
        if self._lower_sections_built:
            return True
        self._lower_sections_build_scheduled = False
        if self._cleanup_in_progress or not self.isVisible():
            return False
        initial_state = self._initial_state_plan
        if initial_state is None:
            self._request_initial_state_load(force=False)
            return False
        lower_started_at = time.perf_counter()

        # ═══════════════════════════════════════════════════════════
        # НОВОГОДНЕЕ ОФОРМЛЕНИЕ (Premium)
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        holiday_widgets = build_holiday_sections(
            page=self,
            tr_language=self._ui_language,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            checkbox_cls=CheckBox,
            get_icon_pixmap=lambda icon, size: get_cached_qta_pixmap(icon, color=get_theme_tokens().accent_hex, size=size),
            on_garland_changed=self._on_garland_changed,
            on_snowflakes_changed=self._on_snowflakes_changed,
        )
        self._garland_icon_label = holiday_widgets.garland_icon_label
        self._garland_checkbox = holiday_widgets.garland_checkbox
        self._snowflakes_icon_label = holiday_widgets.snowflakes_icon_label
        self._snowflakes_checkbox = holiday_widgets.snowflakes_checkbox
        self._log_ui_timing("appearance_ui.holiday_section.build", section_started_at)

        # ═══════════════════════════════════════════════════════════
        # ПРОЗРАЧНОСТЬ ОКНА
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        opacity_widgets = build_opacity_section(
            page=self,
            tr_language=self._ui_language,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            slider_cls=Slider,
            initial_opacity=initial_state.window_opacity,
            get_icon_pixmap=lambda icon, size: get_cached_qta_pixmap(icon, color=get_theme_tokens().accent_hex, size=size),
            on_opacity_changed=self._on_opacity_changed,
        )
        self._opacity_icon_label = opacity_widgets.opacity_icon_label
        self._opacity_label = opacity_widgets.opacity_label
        self._opacity_slider = opacity_widgets.opacity_slider
        self._log_ui_timing("appearance_ui.opacity_section.build", section_started_at)

        # ═══════════════════════════════════════════════════════════
        # АКЦЕНТНЫЙ ЦВЕТ (qfluentwidgets setThemeColor)
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        self._accent_group = SettingCardGroup(
            tr_catalog("page.appearance.section.accent", language=self._ui_language, default="Акцентный цвет"),
            self.content,
        )
        accent_card = self._accent_group
        accent_layout = None

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

        enable_setting_card_group_auto_height(accent_card)
        self.add_widget(accent_card)
        self._log_ui_timing("appearance_ui.accent_section.build", section_started_at)

        self.add_spacing(16)
        section_started_at = time.perf_counter()
        self._apply_initial_accent_state(initial_state)
        self._log_ui_timing("appearance_ui.accent_settings.load", section_started_at)

        # ═══════════════════════════════════════════════════════════
        # ПРОИЗВОДИТЕЛЬНОСТЬ
        # ═══════════════════════════════════════════════════════════
        section_started_at = time.perf_counter()
        performance_widgets = build_performance_section(
            page=self,
            tr_language=self._ui_language,
            settings_card_group_cls=SettingCardGroup,
            toggle_row_cls=Win11ToggleRow,
            on_animations_changed=self._on_animations_changed,
            on_smooth_scroll_changed=self._on_smooth_scroll_changed,
            on_editor_smooth_scroll_changed=self._on_editor_smooth_scroll_changed,
        )
        self._performance_card = performance_widgets.performance_card
        self._performance_group = performance_widgets.performance_group
        self._animations_switch = performance_widgets.animations_switch
        self._smooth_scroll_switch = performance_widgets.smooth_scroll_switch
        self._editor_smooth_scroll_switch = performance_widgets.editor_smooth_scroll_switch
        self._apply_initial_performance_state(initial_state)
        self._log_ui_timing("appearance_ui.performance_section.build", section_started_at)

        self.set_mica_state(initial_state.mica_enabled)
        try:
            is_premium, garland_enabled, snowflakes_enabled, window_opacity = self._current_appearance_state()
            self.set_premium_status(
                is_premium,
                current_preset=self._current_bg_preset_from_ui(),
                premium_effects=appearance_settings.AppearancePremiumEffectsPlan(
                    garland_enabled=garland_enabled,
                    snowflakes_enabled=snowflakes_enabled,
                ),
            )
            self.set_opacity_value(window_opacity)
        except Exception:
            pass
        self._lower_sections_built = True
        self._log_ui_timing("appearance_ui.lower_sections.build", lower_started_at)
        return True

    @staticmethod
    def _log_ui_timing(label: str, started_at: float) -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass

    def _show_accent_color_dialog(self) -> None:
        """Открывает fluent-диалог выбора цвета с нормальным русским заголовком."""
        if self._color_picker_btn is None:
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

    def _apply_initial_display_state(self, plan: appearance_settings.AppearancePageInitialStatePlan) -> None:
        self._apply_display_mode_value(plan.display_mode)
        self._apply_sidebar_icon_style_value(plan.sidebar_icon_style)
        self._apply_bg_preset_ui(plan.background_preset)
        self.set_ui_language(plan.ui_language)
        self.set_mica_state(plan.mica_enabled)

    def _apply_display_mode_value(self, mode: str) -> None:
        if self._display_mode_seg is not None:
            self._begin_ui_sync()
            try:
                self._set_current_item_silently(self._display_mode_seg, mode)
            except Exception:
                pass
            finally:
                self._end_ui_sync()

    def _apply_sidebar_icon_style_value(self, style: str) -> None:
        if self._sidebar_icon_style_seg is not None:
            self._begin_ui_sync()
            try:
                normalized = appearance_settings.normalize_sidebar_icon_style(style)
                self._set_current_item_silently(self._sidebar_icon_style_seg, normalized)
            except Exception:
                pass
            finally:
                self._end_ui_sync()

    def create_appearance_save_worker(self, request_id: int, *, action: str, value=None, context_extra: dict | None = None):
        return self._appearance.create_appearance_save_worker(
            request_id,
            action=action,
            value=value,
            context_extra=context_extra,
            parent=self,
        )

    def create_initial_state_load_worker(self, request_id: int):
        return self._appearance.create_initial_state_load_worker(request_id, parent=self)

    def _request_initial_state_load(self, *, force: bool) -> None:
        if self._cleanup_in_progress:
            return
        if not force and self._initial_state_plan is not None:
            return
        if (
            self._initial_state_load_runtime.is_running()
            or self.__dict__.get("_initial_state_load_start_scheduled", False)
        ):
            self._initial_state_load_pending = True
            self._initial_state_load_pending_force = (
                bool(self.__dict__.get("_initial_state_load_pending_force", False))
                or bool(force)
            )
            return
        self._initial_state_load_pending = False
        self._initial_state_load_pending_force = False
        self._start_initial_state_load_worker()

    def _start_initial_state_load_worker(self) -> None:
        self._initial_state_load_runtime.start_qthread_worker(
            worker_factory=self.create_initial_state_load_worker,
            on_loaded=self._on_initial_state_loaded,
            on_failed=self._on_initial_state_failed,
            on_finished=self._on_initial_state_worker_finished,
        )

    def _on_initial_state_loaded(self, request_id: int, plan) -> None:
        if not self._initial_state_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_initial_state_load_pending", False):
            return
        self._initial_state_plan = plan
        self._ui_language = plan.ui_language
        self._apply_initial_display_state(plan)
        if self._lower_sections_build_scheduled or self.isVisible():
            self._schedule_lower_sections_build()

    def _on_initial_state_failed(self, request_id: int, error: str) -> None:
        if not self._initial_state_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка загрузки настроек оформления: {error}", "WARNING")
        if self._initial_state_plan is None:
            self._initial_state_plan = appearance_settings.build_default_page_initial_state()
        if self._lower_sections_build_scheduled or self.isVisible():
            self._schedule_lower_sections_build()

    def _on_initial_state_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_initial_state_load_runtime"), _worker):
            return
        if self.__dict__.get("_initial_state_load_pending", False) and not self._cleanup_in_progress:
            self._schedule_initial_state_load_worker_start()

    def _schedule_initial_state_load_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_initial_state_load_start_scheduled", False):
            self._initial_state_load_pending = True
            return
        self._initial_state_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_initial_state_load_worker_start)

    def _run_scheduled_initial_state_load_worker_start(self) -> None:
        self._initial_state_load_start_scheduled = False
        pending = bool(self.__dict__.get("_initial_state_load_pending", False))
        force = bool(self.__dict__.get("_initial_state_load_pending_force", False))
        self._initial_state_load_pending = False
        self._initial_state_load_pending_force = False
        if self.__dict__.get("_cleanup_in_progress", False) or not pending:
            return
        self._request_initial_state_load(force=force)

    def _request_appearance_save(self, action: str, value=None, **context_extra) -> None:
        payload = {
            "action": str(action or ""),
            "value": value,
            "context_extra": dict(context_extra or {}),
        }
        if self._appearance_save_runtime.is_running() or self.__dict__.get("_appearance_save_start_scheduled", False):
            self._queue_appearance_save_payload(payload)
            self._coalesce_appearance_save_pending()
            return
        self._start_appearance_save_worker(payload)

    def _queue_appearance_save_payload(self, payload: dict[str, object]) -> None:
        self._appearance_save_pending.append(payload)

    def _coalesce_appearance_save_pending(self) -> None:
        latest_by_action: dict[str, dict[str, object]] = {}
        order: list[str] = []
        for payload in self._appearance_save_pending:
            action = str(payload.get("action") or "")
            if action not in latest_by_action:
                order.append(action)
            latest_by_action[action] = payload
        self._appearance_save_pending = [latest_by_action[action] for action in order]

    def _has_pending_appearance_save_action(self, action: str) -> bool:
        action = str(action or "")
        pending_payloads = self.__dict__.get("_appearance_save_pending", [])
        return any(str(payload.get("action") or "") == action for payload in pending_payloads)

    def _start_appearance_save_worker(self, payload: dict[str, object]) -> None:
        self._appearance_save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_appearance_save_worker(
                request_id,
                action=str(payload.get("action") or ""),
                value=payload.get("value"),
                context_extra=dict(payload.get("context_extra") or {}),
            ),
            on_loaded=self._on_appearance_save_finished,
            on_failed=self._on_appearance_save_failed,
            on_finished=self._on_appearance_save_worker_finished,
            loaded_signal_name="completed",
        )

    def _apply_display_mode_runtime(self, mode: str) -> None:
        try:
            from qfluentwidgets import setTheme, Theme
            if mode == "light":
                setTheme(Theme.LIGHT)
            elif mode == "dark":
                setTheme(Theme.DARK)
            elif mode == "system":
                setTheme(Theme.AUTO)
        except Exception:
            pass
        try:
            from ui.theme import apply_window_background
            win = self.window()
            if win is not None:
                apply_window_background(win)
        except Exception:
            pass

    def _on_appearance_save_finished(self, request_id: int, action: str, result, context) -> None:
        if not self._appearance_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        context = dict(context or {})
        if self._has_pending_appearance_save_action(action):
            return
        if action == "display_mode":
            effective_mode = str(getattr(result, "effective_mode", context.get("value") or "dark") or "dark")
            requested_mode = str(context.get("value") or "").strip()
            if effective_mode and requested_mode and effective_mode != requested_mode:
                self._apply_display_mode_value(effective_mode)
                self._apply_display_mode_runtime(effective_mode)
        elif action == "accent_color":
            accent_plan = dict(result or {}).get("accent") if isinstance(result, dict) else result
            tinted_plan = dict(result or {}).get("tinted") if isinstance(result, dict) else None
            hex_color = str(getattr(accent_plan, "hex_color", context.get("value") or "") or "")
            self._emit_accent_update(
                hex_color,
                refresh_background=bool(getattr(tinted_plan, "tinted_background", False)),
            )
        elif action == "animations_enabled":
            editor_plan = dict(result or {}).get("editor_smooth_scroll") if isinstance(result, dict) else None
            self._on_editor_smooth_scroll_changed_callback(bool(getattr(editor_plan, "enabled", False)))
        elif action == "sidebar_icon_style":
            style = appearance_settings.normalize_sidebar_icon_style(
                str(getattr(result, "style", context.get("value") or "standard") or "standard")
            )
            self._apply_sidebar_icon_style_value(style)
            self._on_sidebar_icon_style_changed_callback(style)

    def _on_appearance_save_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if not self._appearance_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._has_pending_appearance_save_action(action):
            return
        log(f"Ошибка сохранения настройки внешнего вида ({action}): {error}", "WARNING")

    def _on_appearance_save_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_appearance_save_runtime"), _worker):
            return
        if self._appearance_save_pending and not self._cleanup_in_progress:
            self._schedule_appearance_save_worker_start()

    def _schedule_appearance_save_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_appearance_save_start_scheduled", False):
            return
        self._appearance_save_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_appearance_save_worker_start)

    def _run_scheduled_appearance_save_worker_start(self) -> None:
        self._appearance_save_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._coalesce_appearance_save_pending()
        if not self._appearance_save_pending:
            return
        payload = self._appearance_save_pending.pop(0)
        self._start_appearance_save_worker(dict(payload or {}))

    def _on_display_mode_changed(self, mode: str):
        """Handle display mode toggle."""
        if self._is_ui_syncing():
            return
        effective_mode = str(mode or "dark")
        self._request_appearance_save("display_mode", effective_mode)
        self._apply_display_mode_runtime(effective_mode)

    def _on_ui_language_changed(self, index: int) -> None:
        if self._is_ui_syncing():
            return
        if self._language_combo is None:
            return

        try:
            lang = self._language_combo.itemData(index)
        except Exception:
            lang = None

        if not isinstance(lang, str) or not lang:
            return

        lang = appearance_settings.normalize_language(lang)
        self._request_appearance_save("ui_language", lang)
        self._on_ui_language_changed_callback(lang)

    def _on_sidebar_icon_style_changed(self, style: str) -> None:
        if self._is_ui_syncing():
            return
        normalized = appearance_settings.normalize_sidebar_icon_style(style)
        self._request_appearance_save("sidebar_icon_style", normalized)
        self._on_sidebar_icon_style_changed_callback(normalized)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_appearance_language(
            language=language,
            begin_ui_sync=self._begin_ui_sync,
            end_ui_sync=self._end_ui_sync,
            set_current_index_silently=self._set_current_index_silently,
            language_desc_label=self._language_desc_label,
            language_name_label=self._language_name_label,
            language_combo=self._language_combo,
            accent_group=self._accent_group,
            performance_group=self._performance_group,
            accent_desc_label=self._accent_desc_label,
            accent_color_row=self._accent_color_row,
            follow_windows_accent_cb=self._follow_windows_accent_cb,
            tinted_bg_cb=self._tinted_bg_cb,
            tinted_intensity_label=self._tinted_intensity_label,
            animations_switch=self._animations_switch,
            smooth_scroll_switch=self._smooth_scroll_switch,
            editor_smooth_scroll_switch=self._editor_smooth_scroll_switch,
        )

    def _apply_bg_preset_ui(self, preset: str):
        """Update RadioButton selection without emitting signals."""
        for radio, key in [
            (self._bg_radio_standard, "standard"),
            (self._bg_radio_amoled, "amoled"),
            (self._bg_radio_rkn_chan, "rkn_chan"),
        ]:
            if radio is not None:
                self._set_checked_silently(radio, key == preset)
        self._update_rkn_background_control_state()
        self._update_display_mode_section_state(preset)
        self._on_background_preset_changed_callback(preset)

    def _current_bg_preset_from_ui(self) -> str:
        if self._bg_radio_rkn_chan is not None and self._bg_radio_rkn_chan.isChecked():
            return "rkn_chan"
        if self._bg_radio_amoled is not None and self._bg_radio_amoled.isChecked():
            return "amoled"
        return "standard"

    @staticmethod
    def _should_show_display_mode_for_preset(preset: str | None) -> bool:
        preset_name = str(preset or "").strip().lower()
        return preset_name not in ("amoled", "rkn_chan")

    def _update_display_mode_section_state(self, preset: str) -> None:
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
        self._request_rkn_background_options_load()

    def create_rkn_background_options_load_worker(self, request_id: int):
        return self._appearance.create_rkn_background_options_load_worker(request_id, parent=self)

    def _request_rkn_background_options_load(self) -> None:
        if self._cleanup_in_progress:
            return
        if (
            self._rkn_background_options_runtime.is_running()
            or self.__dict__.get("_rkn_background_options_start_scheduled", False)
        ):
            self._rkn_background_options_pending = True
            return
        self._start_rkn_background_options_load_worker()

    def _start_rkn_background_options_load_worker(self) -> None:
        self._rkn_background_options_runtime.start_qthread_worker(
            worker_factory=self.create_rkn_background_options_load_worker,
            on_loaded=self._on_rkn_background_options_loaded,
            on_failed=self._on_rkn_background_options_failed,
            on_finished=self._on_rkn_background_options_worker_finished,
        )

    def _on_rkn_background_options_loaded(self, request_id: int, result) -> None:
        if not self._rkn_background_options_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_rkn_background_options_pending", False):
            return
        data = result if isinstance(result, dict) else {}
        self._apply_rkn_background_options(
            saved_value=data.get("saved_value"),
            options=data.get("options") or (),
        )

    def _on_rkn_background_options_failed(self, request_id: int, error: str) -> None:
        if not self._rkn_background_options_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка загрузки RKN-фонов: {error}", "WARNING")
        self._apply_rkn_background_options(saved_value=None, options=())

    def _on_rkn_background_options_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_rkn_background_options_runtime"), _worker):
            return
        if self._rkn_background_options_pending and not self._cleanup_in_progress:
            self._rkn_background_options_pending = False
            self._schedule_rkn_background_options_load_worker_start()

    def _schedule_rkn_background_options_load_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_rkn_background_options_start_scheduled", False):
            self._rkn_background_options_pending = True
            return
        self._rkn_background_options_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_rkn_background_options_load_worker_start)

    def _run_scheduled_rkn_background_options_load_worker_start(self) -> None:
        self._rkn_background_options_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_rkn_background_options_load_worker()

    def _apply_rkn_background_options(self, *, saved_value, options) -> None:
        if self._rkn_background_combo is None:
            return
        self._begin_ui_sync()
        self._rkn_background_combo.blockSignals(True)
        try:
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
                    self._request_appearance_save("rkn_background", selected_rel)
            else:
                self._rkn_background_combo.addItem(
                    tr_catalog("page.appearance.background.rkn.none", language=self._ui_language, default="Фоны не найдены"),
                    userData="",
                )
                self._rkn_background_combo.setCurrentIndex(0)
        finally:
            self._rkn_background_combo.blockSignals(False)
            self._end_ui_sync()
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
        if self._is_ui_syncing():
            return
        if self._rkn_background_combo is None or index < 0:
            return

        try:
            selected_rel = self._rkn_background_combo.itemData(index)
        except Exception:
            selected_rel = None

        if not isinstance(selected_rel, str) or not selected_rel:
            return

        self._request_appearance_save("rkn_background", selected_rel)

        if self._bg_radio_rkn_chan is not None and self._bg_radio_rkn_chan.isChecked():
            self._schedule_background_refresh()

    def _on_bg_preset_toggled(self, preset: str, checked: bool):
        """Handle background preset RadioButton toggle."""
        if self._is_ui_syncing():
            return
        if not checked:
            return
        self._request_appearance_save("background_preset", preset)
        if self._mica_switch:
            self._mica_switch.setEnabled(preset == "standard")
        # AMOLED and РКН Тян require dark mode — force it automatically
        if preset in ("amoled", "rkn_chan"):
            self._on_display_mode_changed("dark")
            if self._display_mode_seg is not None:
                self._begin_ui_sync()
                try:
                    self._set_current_item_silently(self._display_mode_seg, "dark")
                except Exception:
                    pass
                finally:
                    self._end_ui_sync()
        if preset == "rkn_chan":
            self._reload_rkn_background_options()
        self._update_rkn_background_control_state()
        self._update_display_mode_section_state(preset)

    def _on_mica_changed(self, checked: bool):
        """Handle Mica SwitchButton toggle."""
        if self._is_ui_syncing():
            return
        self._request_appearance_save("mica_enabled", bool(checked))
        self._on_mica_changed_callback(checked)

    def set_mica_state(self, enabled: bool):
        """Set Mica SwitchButton state without triggering signal."""
        if self._mica_switch:
            self._set_checked_silently(self._mica_switch, enabled)

    def _apply_theme_tokens(self, theme_name: str) -> None:
        """Refresh qtawesome icon labels on theme change."""
        try:
            tokens = get_theme_tokens(theme_name)
        except Exception:
            tokens = get_theme_tokens()
        self._refresh_accent_icons(tokens)

    def _on_opacity_changed(self, value: int):
        """Обработчик изменения прозрачности окна"""
        if self._is_ui_syncing():
            return
        # Обновляем лейбл
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

        self._request_appearance_save("window_opacity", int(value))
        self._on_opacity_changed_callback(int(value))
        log(f"Прозрачность окна: {int(value)}%", "DEBUG")

    def _on_snowflakes_changed(self, state):
        """Обработчик изменения состояния снежинок"""
        if self._is_ui_syncing():
            return
        enabled = state == Qt.CheckState.Checked.value
        self._request_appearance_save("snowflakes_enabled", enabled)
        self._on_snowflakes_changed_callback(enabled)

    def _on_garland_changed(self, state):
        """Обработчик изменения состояния гирлянды"""
        if self._is_ui_syncing():
            return
        enabled = state == Qt.CheckState.Checked.value
        self._request_appearance_save("garland_enabled", enabled)
        self._on_garland_changed_callback(enabled)

    def _on_accent_color_changed(self, color: QColor):
        """Обработчик изменения акцентного цвета через ColorPickerButton."""
        if self._is_ui_syncing():
            return
        try:
            setThemeColor(color)
        except Exception:
            pass
        hex_color = color.name()
        self._request_appearance_save("accent_color", hex_color)
        self._emit_accent_update(hex_color, refresh_background=False)

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
                lbl.setPixmap(get_cached_qta_pixmap(icon_name, color=tokens.accent_hex, size=size))

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = force
        self._refresh_accent_icons(tokens=tokens)

    def _apply_initial_accent_state(self, plan: appearance_settings.AppearancePageInitialStatePlan) -> None:
        if self._color_picker_btn is not None and plan.accent_color:
            color = QColor(plan.accent_color)
            if color.isValid():
                self._begin_ui_sync()
                try:
                    self._color_picker_btn.setColor(color)
                    setThemeColor(color)
                finally:
                    self._end_ui_sync()

        if self._follow_windows_accent_cb is not None:
            self._set_checked_silently(self._follow_windows_accent_cb, plan.follow_windows_accent)

        if self._tinted_bg_cb is not None:
            self._set_checked_silently(self._tinted_bg_cb, plan.tinted_background)

        if self._tinted_intensity_slider is not None:
            self._set_slider_value_silently(self._tinted_intensity_slider, plan.tinted_intensity)

        if self._tinted_intensity_value_label is not None:
            self._tinted_intensity_value_label.setText(str(plan.tinted_intensity))

        if self._tinted_intensity_container is not None:
            self._tinted_intensity_container.setVisible(plan.tinted_background)

        if self._color_picker_btn is not None:
            self._color_picker_btn.setEnabled(not plan.follow_windows_accent)

    def _on_follow_windows_accent_changed(self, state):
        """Обработчик переключения 'Акцент из Windows'."""
        if self._is_ui_syncing():
            return
        enabled = bool(state) if isinstance(state, bool) else state == Qt.CheckState.Checked.value
        self._request_appearance_save("follow_windows_accent", enabled)
        if enabled:
            self._request_windows_accent_load()
            if self._color_picker_btn is not None:
                self._color_picker_btn.setEnabled(False)
        else:
            if self._color_picker_btn is not None:
                self._color_picker_btn.setEnabled(True)

    def create_windows_accent_load_worker(self, request_id: int):
        return self._appearance.create_windows_accent_load_worker(request_id, parent=self)

    def _request_windows_accent_load(self) -> None:
        if self._cleanup_in_progress:
            return
        if (
            self._windows_accent_load_runtime.is_running()
            or self.__dict__.get("_windows_accent_load_start_scheduled", False)
        ):
            self._windows_accent_load_pending = True
            return
        self._start_windows_accent_load_worker()

    def _start_windows_accent_load_worker(self) -> None:
        self._windows_accent_load_runtime.start_qthread_worker(
            worker_factory=self.create_windows_accent_load_worker,
            on_loaded=self._on_windows_accent_loaded,
            on_failed=self._on_windows_accent_failed,
            on_finished=self._on_windows_accent_worker_finished,
        )

    def _on_windows_accent_loaded(self, request_id: int, plan) -> None:
        if not self._windows_accent_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_windows_accent_load_pending", False):
            return
        self._apply_windows_accent(plan)

    def _on_windows_accent_failed(self, request_id: int, error: str) -> None:
        if not self._windows_accent_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка загрузки системного акцента Windows: {error}", "WARNING")

    def _on_windows_accent_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_windows_accent_load_runtime"), _worker):
            return
        if self._windows_accent_load_pending and not self._cleanup_in_progress:
            self._windows_accent_load_pending = False
            self._schedule_windows_accent_load_worker_start()

    def _schedule_windows_accent_load_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_windows_accent_load_start_scheduled", False):
            self._windows_accent_load_pending = True
            return
        self._windows_accent_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_windows_accent_load_worker_start)

    def _run_scheduled_windows_accent_load_worker_start(self) -> None:
        self._windows_accent_load_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_windows_accent_load_worker()

    def _apply_windows_accent(self, plan):
        """Применяет уже загруженный системный акцент Windows."""
        try:
            hex_color = plan.hex_color
            if hex_color:
                color = QColor(hex_color)
                if color.isValid():
                    self._begin_ui_sync()
                    try:
                        setThemeColor(color)
                        self._request_appearance_save("accent_color", hex_color)
                        if self._color_picker_btn is not None:
                            self._color_picker_btn.setColor(color)
                    finally:
                        self._end_ui_sync()
                    self._emit_accent_update(hex_color, refresh_background=True)
        except Exception:
            pass

    def _on_tinted_bg_changed(self, state):
        """Обработчик переключения 'Тонировать фон'."""
        if self._is_ui_syncing():
            return
        enabled = bool(state) if isinstance(state, bool) else state == Qt.CheckState.Checked.value
        self._request_appearance_save("tinted_background", enabled)
        if self._tinted_intensity_container is not None:
            self._tinted_intensity_container.setVisible(enabled)
        self._schedule_background_refresh()

    def _on_tinted_intensity_changed(self, value: int):
        """Обработчик изменения интенсивности тонировки."""
        if self._is_ui_syncing():
            return
        self._request_appearance_save("tinted_intensity", int(value))
        if self._tinted_intensity_value_label is not None:
            self._tinted_intensity_value_label.setText(str(value))
        self._schedule_background_refresh()

    def set_premium_status(
        self,
        is_premium: bool,
        *,
        current_preset: str,
        premium_effects: appearance_settings.AppearancePremiumEffectsPlan,
    ):
        """Update premium status — unlocks AMOLED/РКН Тян bg presets."""
        was_garland_enabled = bool(self._garland_checkbox and self._garland_checkbox.isChecked())
        was_snowflakes_enabled = bool(self._snowflakes_checkbox and self._snowflakes_checkbox.isChecked())

        # Unlock/lock premium bg preset radio buttons
        if self._bg_radio_amoled is not None:
            self._bg_radio_amoled.setEnabled(is_premium)
        if self._bg_radio_rkn_chan is not None:
            self._bg_radio_rkn_chan.setEnabled(is_premium)
        self._update_rkn_background_control_state()

        premium_plan = appearance_settings.build_premium_status_plan(
            is_premium=is_premium,
            current_preset=current_preset,
            was_garland_enabled=was_garland_enabled,
            was_snowflakes_enabled=was_snowflakes_enabled,
            premium_effects=premium_effects,
        )

        if premium_plan.effective_preset is not None:
            self._request_appearance_save("background_preset", premium_plan.effective_preset)
            self._apply_bg_preset_ui(premium_plan.effective_preset)
            self._on_background_preset_changed_callback(premium_plan.effective_preset)

        if self._garland_checkbox:
            self._garland_checkbox.setEnabled(is_premium)
            self._set_checked_silently(self._garland_checkbox, premium_plan.garland_checked)

        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.setEnabled(is_premium)
            self._set_checked_silently(self._snowflakes_checkbox, premium_plan.snowflakes_checked)

        if premium_plan.disable_garland:
            self._request_appearance_save("garland_enabled", False)
            self._on_garland_changed_callback(False)

        if premium_plan.disable_snowflakes:
            self._request_appearance_save("snowflakes_enabled", False)
            self._on_snowflakes_changed_callback(False)

        self._update_display_mode_section_state(premium_plan.effective_preset or current_preset)

    def set_garland_state(self, enabled: bool):
        """Устанавливает состояние чекбокса гирлянды (без эмита сигнала)"""
        if self._garland_checkbox:
            self._set_checked_silently(self._garland_checkbox, enabled)

    def set_snowflakes_state(self, enabled: bool):
        """Устанавливает состояние чекбокса снежинок (без эмита сигнала)"""
        if self._snowflakes_checkbox:
            self._set_checked_silently(self._snowflakes_checkbox, enabled)

    def set_opacity_value(self, value: int):
        """Устанавливает значение слайдера прозрачности (без эмита сигнала)"""
        if self._opacity_slider:
            self._set_slider_value_silently(self._opacity_slider, value)
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
        if self._is_ui_syncing():
            return
        self._request_appearance_save("animations_enabled", enabled)
        self._on_animations_changed_callback(bool(enabled))
        self._sync_performance_dependencies(bool(enabled))

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Handle smooth scroll SwitchButton toggle."""
        if self._is_ui_syncing():
            return
        self._request_appearance_save("smooth_scroll_enabled", enabled)
        self._on_smooth_scroll_changed_callback(bool(enabled))

    def _on_editor_smooth_scroll_changed(self, enabled: bool):
        """Handle editor smooth scroll toggle."""
        if self._is_ui_syncing():
            return
        self._request_appearance_save("editor_smooth_scroll_enabled", enabled)
        self._on_editor_smooth_scroll_changed_callback(bool(enabled))

    def _sync_performance_dependencies(self, animations_enabled: bool) -> None:
        """Редакторская плавность зависит от мастер-переключателя анимаций."""
        if self._editor_smooth_scroll_switch is not None:
            self._editor_smooth_scroll_switch.setEnabled(bool(animations_enabled))

    def _apply_initial_performance_state(self, plan: appearance_settings.AppearancePageInitialStatePlan) -> None:
        if self._animations_switch is not None:
            self._set_checked_silently(self._animations_switch, plan.animations_enabled)
        if self._smooth_scroll_switch is not None:
            self._set_checked_silently(self._smooth_scroll_switch, plan.smooth_scroll_enabled)
        if self._editor_smooth_scroll_switch is not None:
            self._set_checked_silently(self._editor_smooth_scroll_switch, plan.editor_smooth_scroll_enabled)
        self._sync_performance_dependencies(plan.animations_enabled)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._background_refresh_queued = False

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._appearance_save_pending.clear()
        self._appearance_save_start_scheduled = False
        self._initial_state_load_pending = False
        self._initial_state_load_pending_force = False
        self._initial_state_load_start_scheduled = False
        self._windows_accent_load_pending = False
        self._windows_accent_load_start_scheduled = False
        self._rkn_background_options_start_scheduled = False
        for runtime, name in (
            (self._initial_state_load_runtime, "загрузка оформления"),
            (self._appearance_save_runtime, "сохранение оформления"),
            (self._rkn_background_options_runtime, "RKN-фоны"),
            (self._windows_accent_load_runtime, "акцент Windows"),
        ):
            runtime.stop(log_fn=log, warning_prefix=name)
            runtime.cancel()
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
