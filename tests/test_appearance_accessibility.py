from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QColor, QPixmap
from qfluentwidgets import BodyLabel, CaptionLabel, CheckBox, ColorPickerButton, ComboBox, RadioButton, SegmentedWidget, Slider

from ui.fluent_widgets import SettingsCard
from ui.pages.appearance_page_lower_build import build_holiday_sections, build_opacity_section
from ui.pages.appearance_page_top_build import (
    build_background_section,
    build_display_mode_section,
    build_language_section,
    update_rkn_background_combo_accessibility,
    update_sidebar_icon_style_accessibility,
)


class AppearanceAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_display_mode_selector_reads_current_mode(self) -> None:
        widgets = build_display_mode_section(
            page=None,
            tr_language="ru",
            add_section_title=lambda **_kwargs: BodyLabel("Режим отображения"),
            content_parent=QWidget(),
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            segmented_widget_cls=SegmentedWidget,
            on_display_mode_changed=lambda _mode: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(widgets.segmented.accessibleName(), "Режим отображения интерфейса, выбрано: Тёмный")
        self.assertIn("светлый, тёмный или автоматический", widgets.segmented.accessibleDescription())

        widgets.segmented.setCurrentItem("light")

        self.assertEqual(widgets.segmented.accessibleName(), "Режим отображения интерфейса, выбрано: Светлый")
        self.assertEqual(
            widgets.segmented.property("screenReaderStateText"),
            "Режим отображения интерфейса, выбрано: Светлый",
        )

    def test_display_mode_items_read_name_and_selection_for_screen_reader(self) -> None:
        widgets = build_display_mode_section(
            page=None,
            tr_language="ru",
            add_section_title=lambda **_kwargs: BodyLabel("Режим отображения"),
            content_parent=QWidget(),
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            segmented_widget_cls=SegmentedWidget,
            on_display_mode_changed=lambda _mode: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(
            widgets.segmented.items["dark"].accessibleName(),
            "Режим отображения интерфейса: Тёмный, выбрано",
        )
        self.assertEqual(
            widgets.segmented.items["light"].accessibleName(),
            "Режим отображения интерфейса: Светлый, не выбрано",
        )

        widgets.segmented.setCurrentItem("light")

        self.assertEqual(
            widgets.segmented.items["dark"].accessibleName(),
            "Режим отображения интерфейса: Тёмный, не выбрано",
        )
        self.assertEqual(
            widgets.segmented.items["light"].accessibleName(),
            "Режим отображения интерфейса: Светлый, выбрано",
        )

    def test_language_selector_reads_current_language(self) -> None:
        widgets = build_language_section(
            tr_language="ru",
            add_section_title=lambda **_kwargs: None,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            on_ui_language_changed=lambda _index: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertIn("Язык интерфейса", widgets.combo.accessibleName())
        self.assertIn("выбрано:", widgets.combo.accessibleName())
        self.assertIn("Выберите язык", widgets.combo.accessibleDescription())

    def test_language_selector_menu_items_read_selected_state(self) -> None:
        widgets = build_language_section(
            tr_language="ru",
            add_section_title=lambda **_kwargs: None,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            combo_cls=ComboBox,
            on_ui_language_changed=lambda _index: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        create_menu = getattr(widgets.combo, "_create_accessible_combo_menu", None)

        self.assertIsNotNone(create_menu)

        menu = create_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Язык интерфейса: Русский, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Язык интерфейса: English, не выбран",
        )

    def test_background_controls_read_state_and_premium_limit(self) -> None:
        widgets = build_background_section(
            tr_language="ru",
            add_section_title=lambda **_kwargs: None,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            radio_button_cls=RadioButton,
            combo_cls=ComboBox,
            on_bg_preset_toggled=lambda *_args: None,
            on_rkn_background_changed=lambda _index: None,
        )
        self.addCleanup(widgets.card.deleteLater)

        self.assertEqual(widgets.radio_standard.accessibleName(), "Фон окна: Стандартный, выбрано")
        self.assertEqual(widgets.radio_amoled.accessibleName(), "Фон окна: AMOLED — чёрный, недоступно без Premium")
        self.assertEqual(widgets.radio_rkn_chan.accessibleName(), "Фон окна: РКН Тян, недоступно без Premium")
        self.assertEqual(widgets.rkn_background_combo.accessibleName(), "Фон РКН Тян, вариантов пока нет")

    def test_rkn_background_selector_menu_items_read_selected_state(self) -> None:
        combo = ComboBox()
        self.addCleanup(combo.deleteLater)
        combo.addItem("Сакура", userData="sakura.png")
        combo.addItem("Ночь", userData="night.png")
        combo.setCurrentIndex(1)

        update_rkn_background_combo_accessibility(combo)
        create_menu = getattr(combo, "_create_accessible_combo_menu", None)

        self.assertIsNotNone(create_menu)

        menu = create_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Фон РКН Тян: Сакура, не выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Фон РКН Тян: Ночь, выбран",
        )

    def test_sidebar_icon_style_selector_reads_current_style(self) -> None:
        segmented = SegmentedWidget()
        self.addCleanup(segmented.deleteLater)
        segmented.addItem("standard", "Стандартные", lambda: None)
        segmented.addItem("windows11_fluent", "Windows 11 Fluent", lambda: None)
        segmented.setCurrentItem("standard")

        update_sidebar_icon_style_accessibility(segmented, style="standard")

        self.assertEqual(segmented.accessibleName(), "Стиль иконок бокового меню, выбрано: Стандартные")
        self.assertIn("Выберите стиль иконок", segmented.accessibleDescription())

        segmented.setCurrentItem("windows11_fluent")
        update_sidebar_icon_style_accessibility(segmented, style="windows11_fluent")

        self.assertEqual(segmented.accessibleName(), "Стиль иконок бокового меню, выбрано: Windows 11 Fluent")
        self.assertEqual(
            segmented.property("screenReaderStateText"),
            "Стиль иконок бокового меню, выбрано: Windows 11 Fluent",
        )

    def test_sidebar_icon_style_items_read_name_and_selection_for_screen_reader(self) -> None:
        segmented = SegmentedWidget()
        self.addCleanup(segmented.deleteLater)
        segmented.addItem("standard", "Стандартные", lambda: None)
        segmented.addItem("windows11_fluent", "Windows 11 Fluent", lambda: None)
        segmented.setCurrentItem("standard")

        update_sidebar_icon_style_accessibility(segmented, style="standard")

        self.assertEqual(
            segmented.items["standard"].accessibleName(),
            "Стиль иконок бокового меню: Стандартные, выбрано",
        )
        self.assertEqual(
            segmented.items["windows11_fluent"].accessibleName(),
            "Стиль иконок бокового меню: Windows 11 Fluent, не выбрано",
        )

        segmented.setCurrentItem("windows11_fluent")
        update_sidebar_icon_style_accessibility(segmented, style="windows11_fluent")

        self.assertEqual(
            segmented.items["standard"].accessibleName(),
            "Стиль иконок бокового меню: Стандартные, не выбрано",
        )
        self.assertEqual(
            segmented.items["windows11_fluent"].accessibleName(),
            "Стиль иконок бокового меню: Windows 11 Fluent, выбрано",
        )

    def test_opacity_slider_reads_current_percent(self) -> None:
        class _Page:
            content = QWidget()

            def __init__(self) -> None:
                self.widgets = []

            def add_widget(self, widget) -> None:
                self.widgets.append(widget)

            def add_spacing(self, _value: int) -> None:
                pass

        page = _Page()
        widgets = build_opacity_section(
            page=page,
            tr_language="ru",
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            slider_cls=Slider,
            initial_opacity=72,
            get_icon_pixmap=lambda *_args: QPixmap(20, 20),
            on_opacity_changed=lambda _value: None,
        )

        self.assertEqual(widgets.opacity_slider.accessibleName(), "Прозрачность окна, значение: 72%")
        self.assertIn("Настройка прозрачности", widgets.opacity_slider.accessibleDescription())
        self.assertEqual(widgets.opacity_label.accessibleName(), "Текущее значение прозрачности окна: 72%")
        self.assertEqual(
            widgets.opacity_label.property("screenReaderStateText"),
            "Текущее значение прозрачности окна: 72%",
        )

        widgets.opacity_slider.setValue(85)

        self.assertEqual(widgets.opacity_slider.accessibleName(), "Прозрачность окна, значение: 85%")
        self.assertEqual(
            widgets.opacity_slider.property("screenReaderStateText"),
            "Прозрачность окна, значение: 85%",
        )

        from ui.pages.appearance_page import AppearancePage

        page_for_update = AppearancePage.__new__(AppearancePage)
        page_for_update._opacity_label = widgets.opacity_label
        page_for_update._is_ui_syncing = lambda: False
        page_for_update._request_appearance_save = lambda *_args, **_kwargs: None
        page_for_update._on_opacity_changed_callback = lambda _value: None

        AppearancePage._on_opacity_changed(page_for_update, 64)

        self.assertEqual(widgets.opacity_label.accessibleName(), "Текущее значение прозрачности окна: 64%")
        self.assertEqual(
            widgets.opacity_label.property("screenReaderStateText"),
            "Текущее значение прозрачности окна: 64%",
        )

    def test_holiday_switches_read_premium_limit_and_state(self) -> None:
        class _Page:
            content = QWidget()

            def __init__(self) -> None:
                self.widgets = []

            def add_section_title(self, **_kwargs) -> None:
                pass

            def add_widget(self, widget) -> None:
                self.widgets.append(widget)

            def add_spacing(self, _value: int) -> None:
                pass

        page = _Page()
        widgets = build_holiday_sections(
            page=page,
            tr_language="ru",
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            checkbox_cls=CheckBox,
            get_icon_pixmap=lambda *_args: QPixmap(20, 20),
            on_garland_changed=lambda _state: None,
            on_snowflakes_changed=lambda _state: None,
        )

        self.assertEqual(widgets.garland_checkbox.accessibleName(), "Новогодняя гирлянда, недоступно без Premium")
        self.assertIn("Premium", widgets.garland_checkbox.accessibleDescription())
        self.assertEqual(widgets.snowflakes_checkbox.accessibleName(), "Снежинки, недоступно без Premium")

        widgets.garland_checkbox.setEnabled(True)
        widgets.garland_checkbox.setChecked(True)
        widgets.snowflakes_checkbox.setEnabled(True)
        widgets.snowflakes_checkbox.setChecked(True)
        widgets.snowflakes_checkbox.setChecked(False)

        self.assertEqual(widgets.garland_checkbox.accessibleName(), "Новогодняя гирлянда, включено")
        self.assertEqual(
            widgets.garland_checkbox.property("screenReaderStateText"),
            "Новогодняя гирлянда, включено",
        )
        self.assertEqual(widgets.snowflakes_checkbox.accessibleName(), "Снежинки, выключено")

    def test_saved_holiday_state_refreshes_screen_reader_state(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        garland = CheckBox()
        snowflakes = CheckBox()
        self.addCleanup(garland.deleteLater)
        self.addCleanup(snowflakes.deleteLater)
        garland.setEnabled(True)
        snowflakes.setEnabled(True)

        page = AppearancePage.__new__(AppearancePage)
        page._garland_checkbox = garland
        page._snowflakes_checkbox = snowflakes
        page._set_checked_silently = lambda widget, value: widget.setChecked(bool(value))

        AppearancePage.set_garland_state(page, True)
        AppearancePage.set_snowflakes_state(page, False)

        self.assertEqual(garland.accessibleName(), "Новогодняя гирлянда, включено")
        self.assertEqual(snowflakes.accessibleName(), "Снежинки, выключено")

    def test_accent_color_button_reads_current_color(self) -> None:
        from settings.appearance import AppearancePageInitialStatePlan
        from ui.pages.appearance_page import AppearancePage

        button = ColorPickerButton(QColor("#0078d4"), "Выбрать цвет")
        self.addCleanup(button.deleteLater)

        page = AppearancePage.__new__(AppearancePage)
        page._color_picker_btn = button
        page._follow_windows_accent_cb = None
        page._tinted_bg_cb = None
        page._tinted_intensity_slider = None
        page._tinted_intensity_value_label = None
        page._tinted_intensity_container = None
        page._begin_ui_sync = lambda: None
        page._end_ui_sync = lambda: None
        page._is_ui_syncing = lambda: False
        page._request_appearance_save = lambda *_args, **_kwargs: None
        page._emit_accent_update = lambda *_args, **_kwargs: None

        AppearancePage._apply_initial_accent_state(
            page,
            AppearancePageInitialStatePlan(
                display_mode="dark",
                ui_language="ru",
                background_preset="standard",
                rkn_background=None,
                mica_enabled=False,
                window_opacity=100,
                accent_color="#112233",
                follow_windows_accent=False,
                tinted_background=False,
                tinted_intensity=15,
                animations_enabled=True,
                smooth_scroll_enabled=True,
                editor_smooth_scroll_enabled=True,
                sidebar_icon_style="standard",
                garland_enabled=False,
                snowflakes_enabled=False,
            ),
        )

        self.assertEqual(button.accessibleName(), "Цвет акцента, текущий цвет: #112233")
        self.assertIn("Открывает выбор цвета", button.accessibleDescription())

        AppearancePage._on_accent_color_changed(page, QColor("#445566"))

        self.assertEqual(button.accessibleName(), "Цвет акцента, текущий цвет: #445566")
        self.assertEqual(
            button.property("screenReaderStateText"),
            "Цвет акцента, текущий цвет: #445566",
        )

    def test_tinted_intensity_slider_reads_saved_and_current_value(self) -> None:
        from settings.appearance import AppearancePageInitialStatePlan
        from ui.pages.appearance_page import AppearancePage

        slider = Slider(Qt.Orientation.Horizontal)
        value_label = CaptionLabel("15")
        container = QWidget()
        self.addCleanup(slider.deleteLater)
        self.addCleanup(value_label.deleteLater)
        self.addCleanup(container.deleteLater)
        slider.setRange(0, 100)
        slider.setValue(15)

        page = AppearancePage.__new__(AppearancePage)
        page._color_picker_btn = None
        page._follow_windows_accent_cb = None
        page._tinted_bg_cb = None
        page._tinted_intensity_slider = slider
        page._tinted_intensity_value_label = value_label
        page._tinted_intensity_container = container
        page._tinted_intensity_row = None
        page._begin_ui_sync = lambda: None
        page._end_ui_sync = lambda: None
        page._is_ui_syncing = lambda: False
        page._set_slider_value_silently = lambda widget, value: widget.setValue(int(value))
        page._request_appearance_save = lambda *_args, **_kwargs: None
        page._schedule_background_refresh = lambda: None

        AppearancePage._apply_initial_accent_state(
            page,
            AppearancePageInitialStatePlan(
                display_mode="dark",
                ui_language="ru",
                background_preset="standard",
                rkn_background=None,
                mica_enabled=False,
                window_opacity=100,
                accent_color=None,
                follow_windows_accent=False,
                tinted_background=True,
                tinted_intensity=80,
                animations_enabled=True,
                smooth_scroll_enabled=True,
                editor_smooth_scroll_enabled=True,
                sidebar_icon_style="standard",
                garland_enabled=False,
                snowflakes_enabled=False,
            ),
        )

        self.assertEqual(slider.maximum(), 100)
        self.assertEqual(slider.value(), 80)
        self.assertEqual(slider.accessibleName(), "Интенсивность тонировки, значение: 80 из 100")
        self.assertIn("силу окрашивания фона", slider.accessibleDescription())
        self.assertEqual(value_label.accessibleName(), "Текущее значение интенсивности тонировки: 80 из 100")
        self.assertEqual(
            value_label.property("screenReaderStateText"),
            "Текущее значение интенсивности тонировки: 80 из 100",
        )

        AppearancePage._on_tinted_intensity_changed(page, 55)

        self.assertEqual(slider.accessibleName(), "Интенсивность тонировки, значение: 55 из 100")
        self.assertEqual(
            slider.property("screenReaderStateText"),
            "Интенсивность тонировки, значение: 55 из 100",
        )
        self.assertEqual(value_label.accessibleName(), "Текущее значение интенсивности тонировки: 55 из 100")
        self.assertEqual(
            value_label.property("screenReaderStateText"),
            "Текущее значение интенсивности тонировки: 55 из 100",
        )

    def test_tinted_toggle_hides_intensity_row_and_refreshes_from_new_state(self) -> None:
        import settings.appearance as appearance_settings
        from ui.pages.appearance_page import AppearancePage

        self.addCleanup(appearance_settings.clear_warmed_tinted_settings_cache)

        class _Visible:
            def __init__(self) -> None:
                self.values = []

            def setVisible(self, value: bool) -> None:
                self.values.append(bool(value))

        row = _Visible()
        container = _Visible()
        saved = []
        refreshes = []

        page = AppearancePage.__new__(AppearancePage)
        page._tinted_intensity_row = row
        page._tinted_intensity_container = container
        page._is_ui_syncing = lambda: False
        page._request_appearance_save = lambda action, value: saved.append((action, value))
        page._schedule_background_refresh = lambda: refreshes.append(appearance_settings.peek_warmed_tinted_settings())

        appearance_settings.store_warmed_tinted_settings(False, True, 70)

        AppearancePage._on_tinted_bg_changed(page, False)

        self.assertEqual(saved, [("tinted_background", False)])
        self.assertEqual(row.values, [False])
        self.assertEqual(container.values, [False])
        self.assertEqual(len(refreshes), 1)
        self.assertFalse(refreshes[0].tinted_background)
        self.assertEqual(refreshes[0].tinted_intensity, 70)

    def test_saved_sidebar_icon_style_refreshes_screen_reader_state(self) -> None:
        from ui.pages.appearance_page import AppearancePage

        segmented = SegmentedWidget()
        self.addCleanup(segmented.deleteLater)
        segmented.addItem("standard", "Стандартные", lambda: None)
        segmented.addItem("windows11_fluent", "Windows 11 Fluent", lambda: None)
        segmented.setCurrentItem("standard")
        page = AppearancePage.__new__(AppearancePage)
        page._sidebar_icon_style_seg = segmented
        page._begin_ui_sync = lambda: None
        page._end_ui_sync = lambda: None
        page._set_current_item_silently = lambda widget, item: widget.setCurrentItem(item)

        AppearancePage._apply_sidebar_icon_style_value(page, "windows11_fluent")

        self.assertEqual(segmented.accessibleName(), "Стиль иконок бокового меню, выбрано: Windows 11 Fluent")


if __name__ == "__main__":
    unittest.main()
