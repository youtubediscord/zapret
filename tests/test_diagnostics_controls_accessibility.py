from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, IndeterminateProgressBar, ProgressBar, PushButton

from diagnostics.ui.build import build_connection_controls, build_connection_log_viewer
from diagnostics.ui.components import ConnectionStatusBadge
from diagnostics.ui.runtime_helpers import (
    apply_connection_language,
    apply_interaction_state,
    refresh_test_combo_items,
    set_connection_status,
    start_connection_test,
)


class DiagnosticsControlsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_connection_action_buttons_have_screen_reader_names(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)

        widgets = build_connection_controls(
            container_layout=layout,
            content_parent=parent,
            tr_fn=lambda _key, default: default,
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            progress_bar_cls=ProgressBar,
            push_button_cls=PushButton,
            on_start=lambda: None,
            on_stop=lambda: None,
            on_support=lambda: None,
        )

        self.assertEqual(widgets.start_btn.accessibleName(), "Запустить диагностический тест")
        self.assertIn("Discord и YouTube", widgets.start_btn.accessibleDescription())
        self.assertEqual(widgets.stop_btn.accessibleName(), "Остановить диагностический тест")
        self.assertIn("Останавливает текущий тест", widgets.stop_btn.accessibleDescription())
        self.assertEqual(widgets.send_log_btn.accessibleName(), "Подготовить обращение с логами")
        self.assertIn("архив логов", widgets.send_log_btn.accessibleDescription())

    def test_test_combo_name_includes_selected_scenario(self) -> None:
        combo = ComboBox()

        refresh_test_combo_items(combo=combo, language="ru")

        self.assertEqual(
            combo.accessibleName(),
            "Сценарий диагностики, выбрано: Все тесты (Discord + YouTube)",
        )
        self.assertEqual(
            combo.property("screenReaderStateText"),
            "Сценарий диагностики, выбрано: Все тесты (Discord + YouTube)",
        )
        self.assertIn("Discord и YouTube", combo.accessibleDescription())
        self.assertIn("стрелками вверх и вниз", combo.accessibleDescription())

        combo.setCurrentIndex(1)

        self.assertEqual(combo.accessibleName(), "Сценарий диагностики, выбрано: Только Discord")
        self.assertEqual(
            combo.property("screenReaderStateText"),
            "Сценарий диагностики, выбрано: Только Discord",
        )

    def test_test_combo_menu_items_are_named_for_screen_reader(self) -> None:
        combo = ComboBox()

        refresh_test_combo_items(combo=combo, language="ru")
        create_menu = getattr(combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)
        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Сценарий диагностики: Все тесты (Discord + YouTube), выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Сценарий диагностики: Только Discord, не выбран",
        )

    def test_status_text_is_exposed_as_screen_reader_state(self) -> None:
        status_label = CaptionLabel()
        status_badge = ConnectionStatusBadge()

        set_connection_status(
            status_label=status_label,
            status_badge=status_badge,
            text="🔄 Тестирование в процессе...",
            status="info",
        )

        self.assertEqual(status_label.text(), "🔄 Тестирование в процессе...")
        self.assertEqual(status_label.accessibleName(), "Статус диагностики: Тестирование в процессе...")
        self.assertEqual(
            status_label.property("screenReaderStateText"),
            "Статус диагностики: Тестирование в процессе...",
        )
        self.assertEqual(status_badge.accessibleName(), "Индикатор диагностики: Тестирование в процессе...")

    def test_result_log_viewer_is_named_for_screen_reader(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)

        widgets = build_connection_log_viewer(
            container_layout=layout,
            tr_fn=lambda _key, default: default,
        )

        self.assertEqual(
            widgets.result_text.accessibleName(),
            "Результат диагностики соединений: диагностика ещё не запускалась",
        )
        self.assertIn("ход и итог проверки Discord и YouTube", widgets.result_text.accessibleDescription())
        self.assertEqual(
            widgets.result_text.property("screenReaderStateText"),
            "Результат диагностики соединений: диагностика ещё не запускалась",
        )

    def test_start_connection_test_updates_result_screen_reader_state(self) -> None:
        from ui.accessibility import set_state_text

        parent = QWidget()
        layout = QVBoxLayout(parent)
        widgets = build_connection_log_viewer(
            container_layout=layout,
            tr_fn=lambda _key, default: default,
        )
        combo = ComboBox()
        refresh_test_combo_items(combo=combo, language="ru")
        status_badge = ConnectionStatusBadge()
        progress_badge = ConnectionStatusBadge()
        set_state_text(widgets.result_text, "Старый результат диагностики")

        start_connection_test(
            is_testing=False,
            ui_language="ru",
            test_combo=combo,
            result_text=widgets.result_text,
            apply_interaction_state_callback=lambda **_kwargs: None,
            set_status_callback=lambda _text, _status: None,
            status_badge=status_badge,
            progress_badge=progress_badge,
        )

        expected = "Результат диагностики соединений: Запуск тестирования: Все тесты (Discord + YouTube)"
        self.assertEqual(widgets.result_text.accessibleName(), expected)
        self.assertEqual(widgets.result_text.property("screenReaderStateText"), expected)

    def test_progress_indicator_exposes_screen_reader_state(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)

        widgets = build_connection_controls(
            container_layout=layout,
            content_parent=parent,
            tr_fn=lambda _key, default: default,
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            progress_bar_cls=IndeterminateProgressBar,
            push_button_cls=PushButton,
            on_start=lambda: None,
            on_stop=lambda: None,
            on_support=lambda: None,
        )

        self.assertEqual(widgets.progress_bar.accessibleName(), "Ход диагностики соединений")
        self.assertIn("Показывает, что проверка выполняется", widgets.progress_bar.accessibleDescription())

        apply_interaction_state(
            start_btn=widgets.start_btn,
            stop_btn=widgets.stop_btn,
            test_combo=widgets.test_combo,
            send_log_btn=widgets.send_log_btn,
            progress_bar=widgets.progress_bar,
            start_enabled=False,
            stop_enabled=True,
            combo_enabled=False,
            send_log_enabled=False,
            progress_visible=True,
        )

        self.assertEqual(widgets.progress_bar.accessibleName(), "Ход диагностики соединений: выполняется")
        self.assertEqual(
            widgets.progress_bar.property("screenReaderStateText"),
            "Ход диагностики соединений: выполняется",
        )

    def test_connection_language_refresh_keeps_screen_reader_descriptions(self) -> None:
        parent = QWidget()
        layout = QVBoxLayout(parent)
        hero_title = BodyLabel()
        hero_subtitle = BodyLabel()

        widgets = build_connection_controls(
            container_layout=layout,
            content_parent=parent,
            tr_fn=lambda _key, default: default,
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            progress_bar_cls=ProgressBar,
            push_button_cls=PushButton,
            on_start=lambda: None,
            on_stop=lambda: None,
            on_support=lambda: None,
        )

        apply_connection_language(
            language="ru",
            controls_card=widgets.controls_card,
            actions_title_label=widgets.actions_title_label,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            test_select_label=widgets.test_select_label,
            refresh_test_combo_items_callback=lambda: None,
            start_btn=widgets.start_btn,
            stop_btn=widgets.stop_btn,
            send_log_btn=widgets.send_log_btn,
        )

        self.assertEqual(widgets.start_btn.accessibleName(), "Запустить диагностический тест")
        self.assertEqual(widgets.stop_btn.accessibleName(), "Остановить диагностический тест")
        self.assertIn("Останавливает текущий тест", widgets.stop_btn.accessibleDescription())
        self.assertEqual(widgets.send_log_btn.accessibleName(), "Подготовить обращение с логами")


if __name__ == "__main__":
    unittest.main()
