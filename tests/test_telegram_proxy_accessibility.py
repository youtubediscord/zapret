import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QSizePolicy, QSpinBox, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SettingCardGroup,
    SpinBox,
    StrongBodyLabel,
)

from telegram_proxy.ui.build import (
    build_telegram_proxy_diag_panel,
    build_telegram_proxy_logs_panel,
    build_telegram_proxy_shell,
)
from telegram_proxy.ui.settings_build import build_telegram_proxy_advanced_settings_panel
from telegram_proxy.ui.settings_build import build_telegram_proxy_settings_panel
from telegram_proxy.ui.proxy_runtime_workflow import apply_status_changed
from telegram_proxy.ui.proxy_runtime_workflow import restart_proxy_if_running
from telegram_proxy.ui.runtime_helpers import refresh_status_texts
from telegram_proxy.ui.page import TelegramProxyPage
from ui.widgets.win11_controls import Win11ComboRow, Win11ToggleRow


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
        self.assertEqual(
            widgets.pivot.items["settings"].accessibleName(),
            "Раздел Telegram Proxy: Настройки, выбрано",
        )
        self.assertEqual(
            widgets.pivot.items["logs"].accessibleName(),
            "Раздел Telegram Proxy: Логи, не выбрано",
        )

        widgets.pivot.setCurrentItem("logs")

        self.assertEqual(widgets.pivot.accessibleName(), "Раздел Telegram Proxy, выбрано: Логи")
        self.assertEqual(
            widgets.pivot.property("screenReaderStateText"),
            "Раздел Telegram Proxy, выбрано: Логи",
        )
        self.assertEqual(
            widgets.pivot.items["settings"].accessibleName(),
            "Раздел Telegram Proxy: Настройки, не выбрано",
        )
        self.assertEqual(
            widgets.pivot.items["logs"].accessibleName(),
            "Раздел Telegram Proxy: Логи, выбрано",
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
        self.assertEqual(widgets.btn_copy_logs.property("screenReaderStateText"), "Копировать лог Telegram Proxy")
        self.assertIn("копирует весь лог", widgets.btn_copy_logs.accessibleDescription().lower())
        self.assertEqual(widgets.btn_open_log_file.accessibleName(), "Открыть файл лога Telegram Proxy")
        self.assertEqual(
            widgets.btn_open_log_file.property("screenReaderStateText"),
            "Открыть файл лога Telegram Proxy",
        )
        self.assertIn("открывает файл", widgets.btn_open_log_file.accessibleDescription().lower())
        self.assertEqual(widgets.btn_clear_logs.accessibleName(), "Очистить лог Telegram Proxy")
        self.assertEqual(widgets.btn_clear_logs.property("screenReaderStateText"), "Очистить лог Telegram Proxy")
        self.assertIn("очищает видимый лог", widgets.btn_clear_logs.accessibleDescription().lower())
        self.assertEqual(widgets.log_edit.accessibleName(), "Лог Telegram Proxy: пока нет событий подключений")
        self.assertIn("события подключений", widgets.log_edit.accessibleDescription())
        self.assertEqual(
            widgets.log_edit.property("screenReaderStateText"),
            "Лог Telegram Proxy: пока нет событий подключений",
        )

    def test_logs_panel_expands_log_view_inside_page(self) -> None:
        layout = self._layout()

        widgets = build_telegram_proxy_logs_panel(
            layout,
            push_button_cls=PushButton,
            on_copy_all_logs=lambda: None,
            on_open_log_file=lambda: None,
            on_clear_logs=lambda: None,
        )

        self.assertEqual(layout.stretch(layout.indexOf(widgets.log_edit)), 1)
        self.assertEqual(
            widgets.log_edit.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
        )

    def test_shell_stacked_area_expands_between_tabs(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)

        widgets = build_telegram_proxy_shell(
            segmented_widget_cls=SegmentedWidget,
            parent=parent,
            on_switch_tab=lambda _index: None,
        )

        self.assertEqual(
            widgets.stacked.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
        )
        self.assertEqual(
            widgets.logs_panel.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
        )

    def test_page_gives_stacked_tabs_remaining_height(self) -> None:
        import inspect

        source = inspect.getsource(TelegramProxyPage._setup_ui)

        self.assertIn("self.add_widget(self._stacked, stretch=1)", source)

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
        self.assertEqual(
            widgets.diag_desc_label.property("screenReaderStateText"),
            "Описание диагностики Telegram Proxy",
        )
        self.assertIn("Telegram DC", widgets.diag_desc_label.accessibleDescription())
        self.assertEqual(widgets.btn_run_diag.accessibleName(), "Запустить диагностику Telegram Proxy")
        self.assertEqual(
            widgets.btn_run_diag.property("screenReaderStateText"),
            "Запустить диагностику Telegram Proxy",
        )
        self.assertIn("проверяет соединения", widgets.btn_run_diag.accessibleDescription().lower())
        self.assertEqual(widgets.btn_copy_diag.accessibleName(), "Копировать результат диагностики Telegram Proxy")
        self.assertEqual(
            widgets.btn_copy_diag.property("screenReaderStateText"),
            "Копировать результат диагностики Telegram Proxy",
        )
        self.assertIn("копирует результат", widgets.btn_copy_diag.accessibleDescription().lower())
        self.assertEqual(
            widgets.diag_edit.accessibleName(),
            "Результат диагностики Telegram Proxy: диагностика пока не запускалась",
        )
        self.assertIn("подробный результат", widgets.diag_edit.accessibleDescription())
        self.assertEqual(
            widgets.diag_edit.property("screenReaderStateText"),
            "Результат диагностики Telegram Proxy: диагностика пока не запускалась",
        )

    def test_advanced_settings_fields_are_named_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = build_telegram_proxy_advanced_settings_panel(
            layout,
            content_parent=parent,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            push_button_cls=PushButton,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            spin_box_cls=SpinBox,
            password_line_edit_cls=PasswordLineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_combo_row_cls=Win11ComboRow,
            on_open_mtproxy=lambda: None,
            on_generate_mtproxy_secret=lambda: None,
            on_copy_fake_tls_nginx_config=lambda: None,
            on_test_cloudflare=lambda: None,
            on_copy_cloudflare_dns=lambda: None,
            on_test_cloudflare_worker=lambda: None,
            on_copy_cloudflare_worker_code=lambda: None,
            upstream_catalog={"manual": "Manual"},
        )

        self.assertEqual(widgets.mtproxy_secret_edit.accessibleName(), "Secret MTProxy")
        self.assertIn("ключ подключения", widgets.mtproxy_secret_edit.accessibleDescription())
        self.assertEqual(widgets.mtproxy_generate_btn.accessibleName(), "Создать secret MTProxy")
        self.assertIn("случайный secret", widgets.mtproxy_generate_btn.accessibleDescription())
        self.assertEqual(widgets.fake_tls_domain_edit.accessibleName(), "Домен MTProxy Fake TLS")
        self.assertIn("Fake TLS", widgets.fake_tls_domain_edit.accessibleDescription())
        self.assertEqual(widgets.fake_tls_nginx_btn.accessibleName(), "Скопировать Nginx-конфиг MTProxy Fake TLS")
        self.assertEqual(widgets.upstream_host_edit.accessibleName(), "Хост upstream-прокси Telegram Proxy")
        self.assertEqual(
            widgets.upstream_port_spin.accessibleName(),
            "Порт upstream-прокси Telegram Proxy, значение: 1080",
        )
        self.assertEqual(widgets.upstream_user_edit.accessibleName(), "Логин upstream-прокси Telegram Proxy")
        self.assertEqual(widgets.upstream_pass_edit.accessibleName(), "Пароль upstream-прокси Telegram Proxy")
        self.assertEqual(widgets.mtproxy_action_btn.accessibleName(), "Открыть MTProxy в Telegram")
        self.assertEqual(widgets.cloudflare_domains_edit.accessibleName(), "Домены Cloudflare для Telegram Proxy")
        self.assertIn("запасного WSS-пути", widgets.cloudflare_domains_edit.accessibleDescription())
        self.assertEqual(widgets.cloudflare_test_btn.accessibleName(), "Проверить Cloudflare-домен Telegram Proxy")
        self.assertEqual(widgets.cloudflare_dns_btn.accessibleName(), "Скопировать DNS-записи Cloudflare Telegram Proxy")
        self.assertEqual(widgets.cloudflare_worker_domains_edit.accessibleName(), "Домены Cloudflare Worker для Telegram Proxy")
        self.assertEqual(widgets.cloudflare_worker_test_btn.accessibleName(), "Проверить Cloudflare Worker Telegram Proxy")
        self.assertEqual(widgets.cloudflare_worker_code_btn.accessibleName(), "Скопировать код Cloudflare Worker")
        self.assertEqual(widgets.dc_ip_edit.accessibleName(), "Ручные адреса Telegram DC")
        self.assertIn("номер дата-центра и IP", widgets.dc_ip_edit.accessibleDescription())
        self.assertEqual(widgets.pool_size_spin.accessibleName(), "Пул WSS Telegram Proxy, значение: 4")
        self.assertEqual(widgets.buffer_kb_spin.accessibleName(), "Размер буфера Telegram Proxy, значение: 256")

    def test_settings_panel_main_controls_are_named_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = build_telegram_proxy_settings_panel(
            layout,
            content_parent=parent,
            status_dot_cls=QLabel,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            push_button_cls=PushButton,
            primary_push_button_cls=PrimaryPushButton,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            spin_box_cls=SpinBox,
            password_line_edit_cls=PasswordLineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_combo_row_cls=Win11ComboRow,
            on_toggle_proxy=lambda: None,
            on_open_in_telegram=lambda: None,
            on_copy_link=lambda: None,
            on_open_mtproxy=lambda: None,
            on_generate_mtproxy_secret=lambda: None,
            on_copy_fake_tls_nginx_config=lambda: None,
            on_test_cloudflare=lambda: None,
            on_copy_cloudflare_dns=lambda: None,
            on_test_cloudflare_worker=lambda: None,
            on_copy_cloudflare_worker_code=lambda: None,
            upstream_catalog={"manual": "Manual"},
        )

        self.assertEqual(widgets.setup_open_btn.accessibleName(), "Открыть Telegram Proxy в Telegram")
        self.assertEqual(
            widgets.setup_open_btn.property("screenReaderStateText"),
            "Открыть Telegram Proxy в Telegram",
        )
        self.assertIn("автоматической настройки", widgets.setup_open_btn.accessibleDescription())
        self.assertEqual(widgets.setup_copy_btn.accessibleName(), "Копировать ссылку Telegram Proxy")
        self.assertEqual(
            widgets.setup_copy_btn.property("screenReaderStateText"),
            "Копировать ссылку Telegram Proxy",
        )
        self.assertIn("буфер обмена", widgets.setup_copy_btn.accessibleDescription())
        self.assertEqual(widgets.host_edit.accessibleName(), "Адрес Telegram Proxy")
        self.assertIn("IP-адрес", widgets.host_edit.accessibleDescription())
        self.assertEqual(widgets.port_spin.accessibleName(), "Порт Telegram Proxy, значение: 1353")
        self.assertIn("порт", widgets.port_spin.accessibleDescription().lower())

        widgets.port_spin.setValue(1443)

        self.assertEqual(widgets.port_spin.accessibleName(), "Порт Telegram Proxy, значение: 1443")
        self.assertEqual(
            widgets.port_spin.property("screenReaderStateText"),
            "Порт Telegram Proxy, значение: 1443",
        )

    def test_advanced_spinboxes_read_current_value_for_screen_reader(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)

        widgets = build_telegram_proxy_advanced_settings_panel(
            layout,
            content_parent=parent,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            push_button_cls=PushButton,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            spin_box_cls=SpinBox,
            password_line_edit_cls=PasswordLineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_combo_row_cls=Win11ComboRow,
            on_open_mtproxy=lambda: None,
            on_generate_mtproxy_secret=lambda: None,
            on_copy_fake_tls_nginx_config=lambda: None,
            on_test_cloudflare=lambda: None,
            on_copy_cloudflare_dns=lambda: None,
            on_test_cloudflare_worker=lambda: None,
            on_copy_cloudflare_worker_code=lambda: None,
            upstream_catalog={"manual": "Manual"},
        )

        self.assertEqual(
            widgets.upstream_port_spin.accessibleName(),
            "Порт upstream-прокси Telegram Proxy, значение: 1080",
        )
        self.assertEqual(widgets.pool_size_spin.accessibleName(), "Пул WSS Telegram Proxy, значение: 4")
        self.assertEqual(widgets.buffer_kb_spin.accessibleName(), "Размер буфера Telegram Proxy, значение: 256")

        widgets.pool_size_spin.setValue(6)
        widgets.buffer_kb_spin.setValue(512)

        self.assertEqual(widgets.pool_size_spin.accessibleName(), "Пул WSS Telegram Proxy, значение: 6")
        self.assertEqual(widgets.buffer_kb_spin.accessibleName(), "Размер буфера Telegram Proxy, значение: 512")

    def test_settings_clear_buttons_do_not_take_tab_focus(self) -> None:
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        layout = QVBoxLayout(parent)
        main_widgets = build_telegram_proxy_settings_panel(
            layout,
            content_parent=parent,
            status_dot_cls=QLabel,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            push_button_cls=PushButton,
            primary_push_button_cls=PrimaryPushButton,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            spin_box_cls=SpinBox,
            password_line_edit_cls=PasswordLineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_combo_row_cls=Win11ComboRow,
            on_toggle_proxy=lambda: None,
            on_open_in_telegram=lambda: None,
            on_copy_link=lambda: None,
            on_open_mtproxy=lambda: None,
            on_generate_mtproxy_secret=lambda: None,
            on_copy_fake_tls_nginx_config=lambda: None,
            on_test_cloudflare=lambda: None,
            on_copy_cloudflare_dns=lambda: None,
            on_test_cloudflare_worker=lambda: None,
            on_copy_cloudflare_worker_code=lambda: None,
            upstream_catalog={"manual": "Manual"},
        )
        advanced_widgets = build_telegram_proxy_advanced_settings_panel(
            layout,
            content_parent=parent,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            push_button_cls=PushButton,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            spin_box_cls=SpinBox,
            password_line_edit_cls=PasswordLineEdit,
            win11_toggle_row_cls=Win11ToggleRow,
            win11_combo_row_cls=Win11ComboRow,
            on_open_mtproxy=lambda: None,
            on_generate_mtproxy_secret=lambda: None,
            on_copy_fake_tls_nginx_config=lambda: None,
            on_test_cloudflare=lambda: None,
            on_copy_cloudflare_dns=lambda: None,
            on_test_cloudflare_worker=lambda: None,
            on_copy_cloudflare_worker_code=lambda: None,
            upstream_catalog={"manual": "Manual"},
        )
        line_edits = (
            main_widgets.host_edit,
            advanced_widgets.mtproxy_secret_edit,
            advanced_widgets.fake_tls_domain_edit,
            advanced_widgets.upstream_host_edit,
            advanced_widgets.cloudflare_domains_edit,
            advanced_widgets.cloudflare_worker_domains_edit,
            advanced_widgets.dc_ip_edit,
        )

        for line_edit in line_edits:
            line_edit.setText("example")
            buttons = [
                child
                for child in line_edit.findChildren(object)
                if str(getattr(child, "objectName", lambda: "")() or "") == "lineEditButton"
                and hasattr(child, "setFocusPolicy")
            ]

            self.assertTrue(buttons)
            self.assertTrue(all(button.focusPolicy() == Qt.FocusPolicy.NoFocus for button in buttons))

    def test_upstream_catalog_refresh_updates_menu_item_accessibility(self) -> None:
        row = Win11ComboRow(
            icon_name="mdi.server-network",
            title="Сервер",
            description="Выберите сервер из списка или переключитесь на ручной ввод",
            items=[],
        )
        self.addCleanup(row.deleteLater)

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._advanced_settings_built = True
        page._upstream_preset_row = row

        TelegramProxyPage._apply_initial_upstream_catalog(
            page,
            {
                "Основной сервер": "main",
                "Запасной сервер": "backup",
            },
        )

        create_menu = getattr(row.combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Сервер: Основной сервер, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Сервер: Запасной сервер, не выбран",
        )

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

    def test_refresh_status_texts_sets_screen_reader_state_text(self) -> None:
        status_label = QLabel()
        btn_toggle = PushButton("Запустить")

        refresh_status_texts(
            manager=SimpleNamespace(is_running=True, host="127.0.0.1", port=1353),
            status_label=status_label,
            btn_toggle=btn_toggle,
            restarting=False,
            starting=False,
        )

        self.assertEqual(status_label.text(), "Работает на 127.0.0.1:1353")
        self.assertEqual(status_label.accessibleName(), "Статус Telegram Proxy: Работает на 127.0.0.1:1353")
        self.assertEqual(
            status_label.property("screenReaderStateText"),
            "Статус Telegram Proxy: Работает на 127.0.0.1:1353",
        )
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
