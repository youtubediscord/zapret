import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QSpinBox, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, LineEdit, PrimaryPushButton, PushButton, SegmentedWidget

from telegram_proxy.ui.build import (
    build_telegram_proxy_diag_panel,
    build_telegram_proxy_logs_panel,
    build_telegram_proxy_shell,
)
from telegram_proxy.ui.proxy_runtime_workflow import apply_status_changed
from telegram_proxy.ui.proxy_runtime_workflow import restart_proxy_if_running


class _AccessibleStatusDot:
    def __init__(self) -> None:
        self.active = False
        self._accessible_name = ""
        self._accessible_description = ""

    def set_active(self, active: bool) -> None:
        self.active = bool(active)

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text or "")

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text or "")


class TelegramProxyAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _layout(self) -> QVBoxLayout:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        return QVBoxLayout(parent)

    def test_shell_tabs_read_current_section(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        widgets = build_telegram_proxy_shell(
            segmented_widget_cls=SegmentedWidget,
            parent=parent,
            on_switch_tab=lambda _index: None,
        )

        self.assertEqual(widgets.pivot.accessibleName(), "Раздел Telegram Proxy, выбрано: Настройки")
        self.assertIn("Настройки, Логи или Диагностика", widgets.pivot.accessibleDescription())

        widgets.pivot.setCurrentItem("logs")

        self.assertEqual(widgets.pivot.accessibleName(), "Раздел Telegram Proxy, выбрано: Логи")
        self.assertEqual(
            widgets.pivot.property("screenReaderStateText"),
            "Раздел Telegram Proxy, выбрано: Логи",
        )

    def test_logs_panel_controls_are_named_for_screen_reader(self) -> None:
        widgets = build_telegram_proxy_logs_panel(
            self._layout(),
            push_button_cls=PushButton,
            on_copy_all_logs=lambda: None,
            on_open_log_file=lambda: None,
            on_clear_logs=lambda: None,
        )

        self.assertEqual(widgets.btn_copy_logs.accessibleName(), "Копировать лог Telegram Proxy")
        self.assertIn("копирует весь лог", widgets.btn_copy_logs.accessibleDescription().lower())
        self.assertEqual(widgets.btn_open_log_file.accessibleName(), "Открыть файл лога Telegram Proxy")
        self.assertIn("открывает файл", widgets.btn_open_log_file.accessibleDescription().lower())
        self.assertEqual(widgets.btn_clear_logs.accessibleName(), "Очистить лог Telegram Proxy")
        self.assertIn("очищает видимый лог", widgets.btn_clear_logs.accessibleDescription().lower())
        self.assertEqual(widgets.log_edit.accessibleName(), "Лог Telegram Proxy")
        self.assertIn("события подключений", widgets.log_edit.accessibleDescription())

    def test_diagnostics_panel_controls_are_named_for_screen_reader(self) -> None:
        widgets = build_telegram_proxy_diag_panel(
            self._layout(),
            caption_label_cls=CaptionLabel,
            primary_push_button_cls=PrimaryPushButton,
            push_button_cls=PushButton,
            on_run_diagnostics=lambda: None,
            on_copy_diag=lambda: None,
        )

        self.assertEqual(widgets.diag_desc_label.accessibleName(), "Описание диагностики Telegram Proxy")
        self.assertIn("Telegram DC", widgets.diag_desc_label.accessibleDescription())
        self.assertEqual(widgets.btn_run_diag.accessibleName(), "Запустить диагностику Telegram Proxy")
        self.assertIn("проверяет соединения", widgets.btn_run_diag.accessibleDescription().lower())
        self.assertEqual(widgets.btn_copy_diag.accessibleName(), "Копировать результат диагностики Telegram Proxy")
        self.assertIn("копирует результат", widgets.btn_copy_diag.accessibleDescription().lower())
        self.assertEqual(widgets.diag_edit.accessibleName(), "Результат диагностики Telegram Proxy")
        self.assertIn("подробный результат", widgets.diag_edit.accessibleDescription())

    def test_status_change_sets_screen_reader_state_text(self) -> None:
        status_dot = _AccessibleStatusDot()
        stats_label = QLabel()
        status_label = QLabel()
        btn_toggle = PushButton("Запустить")
        port_spin = QSpinBox()
        host_edit = LineEdit()

        apply_status_changed(
            manager=SimpleNamespace(host="127.0.0.1", port=1353),
            running=True,
            restarting=False,
            starting=False,
            status_dot=status_dot,
            stats_label=stats_label,
            status_label=status_label,
            btn_toggle=btn_toggle,
            port_spin=port_spin,
            host_edit=host_edit,
            relay_check_gen=0,
            set_speed_state=lambda *_args: None,
            set_generation=lambda _value: None,
        )

        self.assertEqual(status_label.accessibleName(), "Статус Telegram Proxy: Работает на 127.0.0.1:1353")
        self.assertEqual(status_dot.accessibleName(), "Индикатор Telegram Proxy: Работает на 127.0.0.1:1353")
        self.assertEqual(btn_toggle.accessibleName(), "Остановить Telegram Proxy")
        self.assertIn("Останавливает", btn_toggle.accessibleDescription())

    def test_restart_status_sets_screen_reader_state_text(self) -> None:
        status_label = QLabel()
        runtime = SimpleNamespace(
            is_running=lambda: False,
            start_qthread_worker=lambda **_kwargs: None,
        )
        page = SimpleNamespace(_restart_stop_runtime=runtime)

        restart_proxy_if_running(
            page=page,
            manager=SimpleNamespace(is_running=True),
            restarting=False,
            set_restarting=lambda _value: None,
            status_label=status_label,
            create_stop_runtime_worker=lambda **_kwargs: object(),
        )

        self.assertEqual(status_label.text(), "Перезапуск прокси...")
        self.assertEqual(status_label.accessibleName(), "Статус Telegram Proxy: Перезапуск прокси...")
        self.assertEqual(
            status_label.property("screenReaderStateText"),
            "Статус Telegram Proxy: Перезапуск прокси...",
        )


if __name__ == "__main__":
    unittest.main()
