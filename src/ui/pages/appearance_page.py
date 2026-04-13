# ui/pages/appearance_page.py
"""Страница настроек оформления - темы"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QColor

from .base_page import BasePage
from ui.appearance_page_controller import AppearancePageController
from ui.pages.appearance_page_lower_build import (
    build_holiday_sections,
    build_opacity_section,
    build_performance_section,
)
from ui.pages.appearance_page_runtime_helpers import (
    apply_appearance_language,
    load_accent_color,
    load_extra_accent_settings,
    load_performance_settings,
)
from ui.pages.appearance_page_top_build import (
    build_background_section,
    build_display_mode_section,
    build_language_section,
)
from ui.compat_widgets import (
    SettingsCard,
    SettingsRow,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_rkn_background_options
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
        self._ui_sync_depth = 0
        self._background_refresh_queued = False
        self._cleanup_in_progress = False
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
        if self._cleanup_in_progress:
            return
        self.set_premium_status(state.subscription_is_premium)
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
        self.background_refresh_needed.emit()

    def _emit_accent_update(self, hex_color: str | None = None, *, refresh_background: bool = False) -> None:
        if hex_color:
            self.accent_color_changed.emit(hex_color)
        if refresh_background:
            self._schedule_background_refresh()

    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # РЕЖИМ ОТОБРАЖЕНИЯ
        # ═══════════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════════
        # ЯЗЫК ИНТЕРФЕЙСА
        # ═══════════════════════════════════════════════════════════
        _lang = AppearancePageController.load_ui_language().language
        language_widgets = build_language_section(
            tr_language=_lang,
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

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ФОН ОКНА
        # ═══════════════════════════════════════════════════════════
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

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # НОВОГОДНЕЕ ОФОРМЛЕНИЕ (Premium)
        # ═══════════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════════
        # ПРОЗРАЧНОСТЬ ОКНА
        # ═══════════════════════════════════════════════════════════
        initial_opacity = AppearancePageController.load_window_opacity().value
        opacity_widgets = build_opacity_section(
            page=self,
            tr_language=self._ui_language,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            slider_cls=Slider,
            initial_opacity=initial_opacity,
            get_icon_pixmap=lambda icon, size: get_cached_qta_pixmap(icon, color=get_theme_tokens().accent_hex, size=size),
            on_opacity_changed=self._on_opacity_changed,
        )
        self._opacity_icon_label = opacity_widgets.opacity_icon_label
        self._opacity_label = opacity_widgets.opacity_label
        self._opacity_slider = opacity_widgets.opacity_slider

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
        performance_widgets = build_performance_section(
            page=self,
            tr_language=self._ui_language,
            settings_card_group_cls=SettingCardGroup,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
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
            self._begin_ui_sync()
            try:
                self._set_current_item_silently(self._display_mode_seg, mode)
            except Exception:
                pass
            finally:
                self._end_ui_sync()

    def _on_display_mode_changed(self, mode: str):
        """Handle display mode toggle."""
        if self._is_ui_syncing():
            return
        plan = AppearancePageController.save_display_mode(mode)
        effective_mode = plan.effective_mode

        if self._display_mode_seg is not None and effective_mode != mode:
            self._begin_ui_sync()
            try:
                self._set_current_item_silently(self._display_mode_seg, effective_mode)
            except Exception:
                pass
            finally:
                self._end_ui_sync()

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
            self._begin_ui_sync()
            self._set_current_index_silently(self._language_combo, index)
        except Exception:
            pass
        finally:
            self._end_ui_sync()

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

        plan = AppearancePageController.save_ui_language(lang)
        self.ui_language_changed.emit(plan.language)

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
                self._set_checked_silently(radio, key == preset)
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
                    AppearancePageController.save_rkn_background(selected_rel)
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

        AppearancePageController.save_rkn_background(selected_rel)

        if self._bg_radio_rkn_chan is not None and self._bg_radio_rkn_chan.isChecked():
            self._schedule_background_refresh()

    def _on_bg_preset_toggled(self, preset: str, checked: bool):
        """Handle background preset RadioButton toggle."""
        if self._is_ui_syncing():
            return
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
        self.background_preset_changed.emit(preset)

    def _on_mica_changed(self, checked: bool):
        """Handle Mica SwitchButton toggle."""
        if self._is_ui_syncing():
            return
        self.mica_changed.emit(checked)

    def set_mica_state(self, enabled: bool):
        """Set Mica SwitchButton state without triggering signal."""
        if self._mica_switch:
            self._set_checked_silently(self._mica_switch, enabled)

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
        if self._is_ui_syncing():
            return
        # Обновляем лейбл
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

        opacity_plan = AppearancePageController.save_window_opacity(value)

        # Уведомляем главное окно
        self.opacity_changed.emit(opacity_plan.value)

        from log.log import log

        log(f"Прозрачность окна: {opacity_plan.value}%", "DEBUG")

    def _on_snowflakes_changed(self, state):
        """Обработчик изменения состояния снежинок"""
        if self._is_ui_syncing():
            return
        enabled = state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_snowflakes_enabled(enabled)
        self.snowflakes_changed.emit(plan.enabled)

    def _on_garland_changed(self, state):
        """Обработчик изменения состояния гирлянды"""
        if self._is_ui_syncing():
            return
        enabled = state == Qt.CheckState.Checked.value
        plan = AppearancePageController.save_garland_enabled(enabled)
        self.garland_changed.emit(plan.enabled)

    def _on_accent_color_changed(self, color: QColor):
        """Обработчик изменения акцентного цвета через ColorPickerButton."""
        if self._is_ui_syncing():
            return
        if not _HAS_COLOR_PICKER:
            return
        try:
            setThemeColor(color)
        except Exception:
            pass
        hex_color = color.name()
        plan = AppearancePageController.save_accent_color(hex_color)
        tinted_plan = AppearancePageController.load_tinted_settings()
        self._emit_accent_update(
            plan.hex_color,
            refresh_background=bool(tinted_plan.tinted_background),
        )

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

    def _load_extra_accent_settings(self):
        """Загружает настройки Follow Windows Accent и Tinted Background."""
        load_extra_accent_settings(
            has_color_picker=_HAS_COLOR_PICKER,
            follow_windows_accent_cb=self._follow_windows_accent_cb,
            tinted_bg_cb=self._tinted_bg_cb,
            tinted_intensity_slider=self._tinted_intensity_slider,
            tinted_intensity_value_label=self._tinted_intensity_value_label,
            tinted_intensity_container=self._tinted_intensity_container,
            color_picker_btn=self._color_picker_btn,
            set_checked_silently=self._set_checked_silently,
            set_slider_value_silently=self._set_slider_value_silently,
            apply_windows_accent=self._apply_windows_accent,
        )

    def _on_follow_windows_accent_changed(self, state):
        """Обработчик переключения 'Акцент из Windows'."""
        if self._is_ui_syncing():
            return
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
                    self._begin_ui_sync()
                    try:
                        setThemeColor(color)
                        AppearancePageController.save_accent_color(hex_color)
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
        plan = AppearancePageController.save_tinted_background(enabled)
        if self._tinted_intensity_container is not None:
            self._tinted_intensity_container.setVisible(plan.enabled)
        self._schedule_background_refresh()

    def _on_tinted_intensity_changed(self, value: int):
        """Обработчик изменения интенсивности тонировки."""
        if self._is_ui_syncing():
            return
        plan = AppearancePageController.save_tinted_background_intensity(value)
        if self._tinted_intensity_value_label is not None:
            self._tinted_intensity_value_label.setText(str(plan.value))
        self._schedule_background_refresh()

    def _load_accent_color(self):
        """Загружает сохранённый акцентный цвет и применяет его."""
        load_accent_color(
            has_color_picker=_HAS_COLOR_PICKER,
            color_picker_btn=self._color_picker_btn,
            begin_ui_sync=self._begin_ui_sync,
            end_ui_sync=self._end_ui_sync,
        )

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
            self._set_checked_silently(self._garland_checkbox, premium_plan.garland_checked)

        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.setEnabled(is_premium)
            self._set_checked_silently(self._snowflakes_checkbox, premium_plan.snowflakes_checked)

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
        plan = AppearancePageController.save_animations_enabled(enabled)
        self.animations_changed.emit(plan.enabled)
        self._sync_performance_dependencies(plan.enabled)

        editor_plan = AppearancePageController.load_editor_smooth_scroll_enabled()
        self.editor_smooth_scroll_changed.emit(editor_plan.enabled)

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Handle smooth scroll SwitchButton toggle."""
        if self._is_ui_syncing():
            return
        plan = AppearancePageController.save_smooth_scroll_enabled(enabled)
        self.smooth_scroll_changed.emit(plan.enabled)

    def _on_editor_smooth_scroll_changed(self, enabled: bool):
        """Handle editor smooth scroll toggle."""
        if self._is_ui_syncing():
            return
        plan = AppearancePageController.save_editor_smooth_scroll_enabled(enabled)
        self.editor_smooth_scroll_changed.emit(plan.enabled)

    def _sync_performance_dependencies(self, animations_enabled: bool) -> None:
        """Редакторская плавность зависит от мастер-переключателя анимаций."""
        if self._editor_smooth_scroll_switch is not None:
            self._editor_smooth_scroll_switch.setEnabled(bool(animations_enabled))

    def _load_performance_settings(self):
        """Load performance state from registry into switches."""
        load_performance_settings(
            animations_switch=self._animations_switch,
            smooth_scroll_switch=self._smooth_scroll_switch,
            editor_smooth_scroll_switch=self._editor_smooth_scroll_switch,
            set_checked_silently=self._set_checked_silently,
            sync_performance_dependencies=self._sync_performance_dependencies,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._background_refresh_queued = False

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_unsubscribe = None
        self._ui_state_store = None
