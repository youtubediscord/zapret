# ui/pages/telegram_proxy_page.py
"""Telegram WebSocket Proxy — UI page.

Provides controls for starting/stopping the proxy, mode selection,
port configuration, and quick-setup deep link for Telegram.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import qtawesome as qta

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget, QLineEdit,
)

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.compat_widgets import (
    SettingsCard,
    QuickActionsBar,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from log import log
from telegram_proxy.page_actions_controller import TelegramProxyPageActionsController
from telegram_proxy.diagnostics_controller import TelegramProxyDiagnosticsController
from telegram_proxy.page_runtime_controller import TelegramProxyRuntimeController
from telegram_proxy.page_settings_controller import TelegramProxySettingsController
from telegram_proxy.upstream_catalog import UpstreamCatalog

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    SpinBox,
    InfoBar,
    InfoBarPosition,
    SegmentedWidget,
    ComboBox,
    LineEdit,
    PasswordLineEdit,
    SettingCardGroup,
    PushButton,
    PrimaryPushButton,
)

if TYPE_CHECKING:
    from main import LupiDPIApp

def _get_proxy_manager():
    from telegram_proxy.manager import get_proxy_manager

    return get_proxy_manager()


# How often (ms) the GUI reads new log lines from the ring buffer
_LOG_REFRESH_MS = 500



class _StatusDot(QWidget):
    """Small colored circle indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#4CAF50") if self._active else QColor("#888888")
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 10, 10)
        p.end()


class TelegramProxyPage(BasePage):
    """Telegram WebSocket Proxy settings page."""

    def __init__(self, parent=None):
        super().__init__(
            "Telegram Proxy",
            "Маршрутизация трафика Telegram через WebSocket для обхода ЗАМЕДЛЕНИЯ (не поддерживает полный блок) по IP",
            parent,
        )
        self.parent_app = parent
        self._log_timer = None
        self._runtime_initialized = False
        self._setup_ui()
        self._after_ui_built()
        # Auto-start now lives in startup initialization, so it works
        # even if this page is never opened.

    def _after_ui_built(self) -> None:
        self._connect_signals()
        self._load_settings()
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._flush_log_buffer)
        self._log_timer.start(_LOG_REFRESH_MS)
        self._apply_ui_texts()
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        plan = TelegramProxyRuntimeController.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.ensure_hosts_once:
            return
        self._runtime_initialized = True
        self._ensure_telegram_hosts()

    def _setup_ui(self):
        # ── Tabs (SegmentedWidget) ──
        self._pivot = SegmentedWidget(self)

        self._stacked = QStackedWidget(self)

        # -- Panel 0: Settings --
        settings_panel = QWidget(self._stacked)
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self._build_settings_panel(settings_layout)
        self._stacked.addWidget(settings_panel)

        # -- Panel 1: Logs --
        logs_panel = QWidget(self._stacked)
        logs_layout = QVBoxLayout(logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)

        self._build_logs_panel(logs_layout)
        self._stacked.addWidget(logs_panel)

        # -- Panel 2: Diagnostics --
        diag_panel = QWidget(self._stacked)
        diag_layout = QVBoxLayout(diag_panel)
        diag_layout.setContentsMargins(0, 0, 0, 0)
        diag_layout.setSpacing(8)

        self._build_diag_panel(diag_layout)
        self._stacked.addWidget(diag_panel)

        # Wire up tabs
        self._pivot.addItem("settings", "Настройки", lambda: self._switch_tab(0))
        self._pivot.addItem("logs", "Логи", lambda: self._switch_tab(1))
        self._pivot.addItem("diag", "Диагностика", lambda: self._switch_tab(2))
        self._pivot.setCurrentItem("settings")
        self.add_widget(self._pivot)

        self.add_widget(self._stacked)
        self._switch_tab(0)

    def _switch_tab(self, index: int):
        self._stacked.setCurrentIndex(index)
        keys = ["settings", "logs", "diag"]
        if 0 <= index < len(keys):
            self._pivot.setCurrentItem(keys[index])

    def _add_settings_item(self, container, widget: QWidget) -> None:
        add_setting_card = getattr(container, "addSettingCard", None)
        if callable(add_setting_card):
            add_setting_card(widget)
        else:
            container.add_widget(widget)

    def _insert_group_label(self, container, label: QWidget, index: int = 1) -> None:
        if getattr(container, "vBoxLayout", None) is not None:
            try:
                insert_widget_into_setting_card_group(container, index, label)
                enable_setting_card_group_auto_height(container)
                return
            except Exception:
                pass
        add_widget = getattr(container, "add_widget", None)
        if callable(add_widget):
            add_widget(label)

    def _build_settings_panel(self, layout: QVBoxLayout):
        # -- Status card --
        self._status_card = SettingsCard()

        status_header = QHBoxLayout()
        self._status_dot = _StatusDot()
        self._status_label = StrongBodyLabel("Остановлен")
        status_header.addWidget(self._status_dot)
        status_header.addWidget(self._status_label)
        status_header.addStretch()

        self._btn_toggle = PushButton()
        self._btn_toggle.setText("Запустить")
        self._btn_toggle.setFixedWidth(140)
        self._btn_toggle.clicked.connect(self._on_toggle_proxy)
        status_header.addWidget(self._btn_toggle)
        self._status_card.add_layout(status_header)

        self._stats_label = CaptionLabel("")
        self._status_card.add_widget(self._stats_label)
        layout.addWidget(self._status_card)

        # -- Quick setup actions --
        self._setup_section_label = StrongBodyLabel("Быстрая настройка Telegram")
        layout.addWidget(self._setup_section_label)

        setup_desc = CaptionLabel(
            "Нажмите кнопку ниже - Telegram автоматически добавит прокси. "
            "Настройка требуется один раз.\nЕсли Telegram не открывается попробуйте скопировать ссылку и отправить в любой чат Telegram или кому-то в ЛС — после чего нажмите на отправленную ссылку и подтвердите добавление прокси в Telegram клиент.\nРекомендуем полностью ПЕРЕЗАПУСТИТЬ клиент для более корректного работа прокси после включения Zapret 2 GUI!"
        )
        self._setup_desc_label = setup_desc
        setup_desc.setWordWrap(True)
        layout.addWidget(setup_desc)

        self._setup_card = QuickActionsBar(self.content)

        self._setup_open_btn = PrimaryPushButton()
        self._setup_open_btn.setText("Открыть")
        self._setup_open_btn.setIcon(qta.icon("mdi.telegram", color="#229ED9"))
        self._setup_open_btn.setToolTip("Открыть ссылку для автоматической настройки прокси внутри Telegram.")
        self._setup_open_btn.clicked.connect(self._on_open_in_telegram)
        self._setup_card.add_button(self._setup_open_btn)

        self._setup_copy_btn = PushButton()
        self._setup_copy_btn.setText("Копировать")
        self._setup_copy_btn.setIcon(qta.icon("mdi.content-copy", color="#60cdff"))
        self._setup_copy_btn.setToolTip("Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически.")
        self._setup_copy_btn.clicked.connect(self._on_copy_link)
        self._setup_card.add_button(self._setup_copy_btn)

        layout.addWidget(self._setup_card)

        # -- Settings card --
        self._settings_card = SettingCardGroup("Настройки", self.content)
        self._settings_host_row = QWidget(self._settings_card)

        # Host + Port setting
        host_port_row = QHBoxLayout(self._settings_host_row)
        host_port_row.setContentsMargins(16, 8, 16, 6)
        host_port_row.setSpacing(12)
        host_label = BodyLabel("Адрес:")
        self._host_label = host_label
        host_port_row.addWidget(host_label)
        self._host_edit = LineEdit()
        self._host_edit.setMinimumWidth(200)
        self._host_edit.setText("127.0.0.1")
        self._host_edit.setPlaceholderText("127.0.0.1")
        self._host_edit.setClearButtonEnabled(True)
        self._host_edit.setToolTip(
            "IP-адрес для прослушивания. 127.0.0.1 — только локально, "
            "0.0.0.0 или IP вашей сети — доступ с других устройств (телефон и т.д.)"
        )
        host_port_row.addWidget(self._host_edit)

        host_port_row.addSpacing(16)

        port_label = BodyLabel("Порт:")
        self._port_label = port_label
        host_port_row.addWidget(port_label)
        self._port_spin = SpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(1353)
        self._port_spin.setFixedWidth(140)
        host_port_row.addWidget(self._port_spin)
        host_port_row.addStretch()
        insert_widget_into_setting_card_group(self._settings_card, 1, self._settings_host_row)

        # Auto-start toggle
        from ui.widgets.win11_controls import Win11ToggleRow, Win11ComboRow
        self._autostart_toggle = Win11ToggleRow(
            "mdi.play-circle-outline",
            "Автозапуск прокси",
            "Запускать прокси автоматически при старте программы",
        )
        self._autostart_toggle.toggle.setChecked(True)
        self._add_settings_item(self._settings_card, self._autostart_toggle)

        # Auto-open deep link toggle
        self._auto_deeplink_toggle = Win11ToggleRow(
            "mdi.telegram",
            "Авто-настройка Telegram",
            "При первом запуске прокси автоматически открыть ссылку настройки в Telegram",
        )
        self._auto_deeplink_toggle.toggle.setChecked(True)
        self._add_settings_item(self._settings_card, self._auto_deeplink_toggle)
        enable_setting_card_group_auto_height(self._settings_card)

        layout.addWidget(self._settings_card)

        # -- Upstream proxy card --
        self._upstream_card = SettingCardGroup("Внешний прокси (upstream)", self.content)

        upstream_desc = CaptionLabel(
            "SOCKS5 прокси-сервер для DC заблокированных вашим провайдером.\n"
            "Используется как резервный канал когда WSS relay и прямое подключение не работают."
        )
        self._upstream_desc_label = upstream_desc
        upstream_desc.setWordWrap(True)
        self._insert_group_label(self._upstream_card, upstream_desc, 1)

        # Enable toggle (reuse Win11ToggleRow already imported above)
        self._upstream_toggle = Win11ToggleRow(
            "mdi.server-network",
            "Использовать внешний прокси",
            "Маршрутизировать заблокированные DC через внешний SOCKS5 прокси",
        )
        self._upstream_toggle.toggle.setChecked(False)
        self._add_settings_item(self._upstream_card, self._upstream_toggle)

        # Upstream server selector: manual + bundled presets from source secrets
        self._upstream_catalog = UpstreamCatalog.load_from_runtime()
        self._upstream_preset_row = Win11ComboRow(
            icon_name="mdi.server-network",
            title="Сервер",
            description="Выберите сервер из списка или переключитесь на ручной ввод",
            items=self._upstream_catalog.items(),
        )
        self._upstream_preset_row.combo.setFixedWidth(250)
        self._add_settings_item(self._upstream_card, self._upstream_preset_row)
        self._upstream_catalog_hint = CaptionLabel(
            "В этой сборке список предустановленных прокси не загружен. "
            "Доступен только ручной ввод."
        )
        self._upstream_catalog_hint.setWordWrap(True)
        self._upstream_catalog_hint.setVisible(False)
        self._insert_group_label(self._upstream_card, self._upstream_catalog_hint, 2)

        # Manual input container: shown only for "Ручной ввод"
        self._upstream_manual_widget = QWidget(self._upstream_card)
        manual_layout = QVBoxLayout(self._upstream_manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        # Host + Port row
        upstream_hp_row = QHBoxLayout()
        self._upstream_host_label = BodyLabel("Хост:")
        upstream_hp_row.addWidget(self._upstream_host_label)
        self._upstream_host_edit = LineEdit()
        self._upstream_host_edit.setMinimumWidth(250)
        self._upstream_host_edit.setPlaceholderText("192.168.1.100 или proxy.example.com")
        self._upstream_host_edit.setClearButtonEnabled(True)
        upstream_hp_row.addWidget(self._upstream_host_edit)
        upstream_hp_row.addSpacing(16)
        self._upstream_port_label = BodyLabel("Порт:")
        upstream_hp_row.addWidget(self._upstream_port_label)
        self._upstream_port_spin = SpinBox()
        self._upstream_port_spin.setRange(1, 65535)
        self._upstream_port_spin.setValue(1080)
        self._upstream_port_spin.setFixedWidth(140)
        upstream_hp_row.addWidget(self._upstream_port_spin)
        upstream_hp_row.addStretch()
        manual_layout.addLayout(upstream_hp_row)

        # Username + Password row
        upstream_auth_row = QHBoxLayout()
        self._upstream_user_label = BodyLabel("Логин:")
        upstream_auth_row.addWidget(self._upstream_user_label)
        self._upstream_user_edit = LineEdit()
        self._upstream_user_edit.setMinimumWidth(200)
        self._upstream_user_edit.setPlaceholderText("username")
        upstream_auth_row.addWidget(self._upstream_user_edit)
        upstream_auth_row.addSpacing(16)
        self._upstream_pass_label = BodyLabel("Пароль:")
        upstream_auth_row.addWidget(self._upstream_pass_label)
        self._upstream_pass_edit = PasswordLineEdit()
        self._upstream_pass_edit.setMinimumWidth(200)
        self._upstream_pass_edit.setPlaceholderText("password")
        upstream_auth_row.addWidget(self._upstream_pass_edit)
        upstream_auth_row.addStretch()
        manual_layout.addLayout(upstream_auth_row)

        self._upstream_manual_widget.setVisible(True)
        self._add_settings_item(self._upstream_card, self._upstream_manual_widget)

        # MTProxy action (visible only when MTProxy preset selected)
        self._mtproxy_action_btn = PushButton()
        self._mtproxy_action_btn.setText("Открыть")
        self._mtproxy_action_btn.setIcon(qta.icon("mdi.telegram", color="#229ED9"))
        self._mtproxy_action_btn.setToolTip("MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
        self._mtproxy_action_btn.clicked.connect(self._on_open_mtproxy)
        self._mtproxy_action_widget = self._mtproxy_action_btn
        self._mtproxy_action_widget.setVisible(False)
        self._add_settings_item(self._upstream_card, self._mtproxy_action_widget)
        self._current_mtproxy_link = ""

        # Mode toggle (fallback vs always) — default ON
        self._upstream_mode_toggle = Win11ToggleRow(
            "mdi.swap-horizontal",
            "Весь трафик через прокси",
            "Если выключено — только заблокированные DC. Если включено — весь трафик Telegram.",
        )
        self._upstream_mode_toggle.toggle.setChecked(True)
        self._add_settings_item(self._upstream_card, self._upstream_mode_toggle)
        enable_setting_card_group_auto_height(self._upstream_card)

        self._refresh_upstream_preset_combo(select_index=0)

        layout.addWidget(self._upstream_card)

        # -- Instructions card --
        self._manual_section_label = StrongBodyLabel("Ручная настройка")
        layout.addWidget(self._manual_section_label)
        self._instructions_card = SettingsCard()

        instr1 = CaptionLabel("Если автоматическая настройка не сработала:")
        self._instr1_label = instr1
        instr1.setWordWrap(True)
        self._instructions_card.add_widget(instr1)

        instr2 = CaptionLabel("  Telegram -> Настройки -> Продвинутые -> Тип соединения -> Прокси")
        self._instr2_label = instr2
        instr2.setWordWrap(True)
        self._instructions_card.add_widget(instr2)

        self._manual_host_port_label = CaptionLabel("  Тип: SOCKS5  |  Хост: 127.0.0.1  |  Порт: 1353")
        self._manual_host_port_label.setWordWrap(True)
        self._instructions_card.add_widget(self._manual_host_port_label)

        layout.addWidget(self._instructions_card)
        layout.addStretch()

    def _build_logs_panel(self, layout: QVBoxLayout):
        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._btn_copy_logs = PushButton()
        self._btn_copy_logs.setText("Копировать все")
        self._btn_copy_logs.setIcon(qta.icon("mdi.content-copy", color="#60cdff"))
        self._btn_copy_logs.clicked.connect(self._on_copy_all_logs)
        toolbar.addWidget(self._btn_copy_logs)

        self._btn_open_log_file = PushButton()
        self._btn_open_log_file.setText("Открыть файл лога")
        self._btn_open_log_file.setIcon(qta.icon("fa5s.file-alt", color="#60cdff"))
        self._btn_open_log_file.clicked.connect(self._on_open_log_file)
        toolbar.addWidget(self._btn_open_log_file)

        self._btn_clear_logs = PushButton()
        self._btn_clear_logs.setText("Очистить")
        self._btn_clear_logs.setIcon(qta.icon("fa5s.eraser", color="#ff9800"))
        self._btn_clear_logs.clicked.connect(self._on_clear_logs)
        toolbar.addWidget(self._btn_clear_logs)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Log text widget — no height limit, no trimming
        self._log_edit = ScrollBlockingPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText("Лог подключений появится здесь...")
        layout.addWidget(self._log_edit)

    def _build_diag_panel(self, layout: QVBoxLayout):
        desc = CaptionLabel(
            "Проверка соединений к Telegram DC, WSS relay эндпоинтов (kws1-kws5), "
            "SOCKS5 прокси и определение типа блокировки."
        )
        self._diag_desc_label = desc
        desc.setWordWrap(True)
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._btn_run_diag = PrimaryPushButton()
        self._btn_run_diag.setText("Запустить диагностику")
        self._btn_run_diag.setIcon(qta.icon("fa5s.stethoscope", color="#60cdff"))
        self._btn_run_diag.clicked.connect(self._on_run_diagnostics)
        toolbar.addWidget(self._btn_run_diag)

        self._btn_copy_diag = PushButton()
        self._btn_copy_diag.setText("Копировать результат")
        self._btn_copy_diag.setIcon(qta.icon("mdi.content-copy", color="#60cdff"))
        self._btn_copy_diag.clicked.connect(self._on_copy_diag)
        toolbar.addWidget(self._btn_copy_diag)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._diag_edit = ScrollBlockingPlainTextEdit()
        self._diag_edit.setReadOnly(True)
        self._diag_edit.setPlaceholderText("Нажмите 'Запустить диагностику'...")
        layout.addWidget(self._diag_edit)

    def _on_run_diagnostics(self):
        """Run network diagnostics in a background thread."""
        plan = TelegramProxyPageActionsController.build_diagnostics_start_plan()
        self._btn_run_diag.setEnabled(plan.button_enabled)
        self._btn_run_diag.setText(plan.button_text)
        self._diag_edit.clear()
        self._diag_edit.appendPlainText(plan.initial_text)

        self._diag_result = None  # shared with thread
        self._diag_thread_done = False
        # Capture proxy port from UI before spawning thread
        self._diag_proxy_port = self._port_spin.value()

        import threading
        t = threading.Thread(target=self._run_diag_tests, daemon=True)
        t.start()

        # Poll for result every 200ms
        self._diag_poll_timer = QTimer(self)
        self._diag_poll_timer.timeout.connect(self._poll_diag)
        self._diag_poll_timer.start(plan.poll_interval_ms)

    def _poll_diag(self):
        """Check if diag thread has new results."""
        plan = TelegramProxyPageActionsController.build_diagnostics_poll_plan(
            result_text=self._diag_result,
            thread_done=self._diag_thread_done,
        )
        if plan.updated_text is not None:
            self._diag_edit.setPlainText(plan.updated_text)
            sb = self._diag_edit.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        if plan.should_stop_timer:
            self._diag_poll_timer.stop()
        if plan.should_finish:
            self._diag_finished()

    def _run_diag_tests(self):
        self._diag_result = TelegramProxyDiagnosticsController.run_all(
            proxy_port=getattr(self, "_diag_proxy_port", 1353),
            progress_callback=self._publish_diag_result,
        )
        self._diag_thread_done = True

    def _publish_diag_result(self, text: str) -> None:
        self._diag_result = text

    def _update_diag(self, text: str):
        self._diag_edit.setPlainText(text)
        sb = self._diag_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _diag_finished(self):
        plan = TelegramProxyPageActionsController.build_diagnostics_finish_plan()
        self._btn_run_diag.setEnabled(plan.button_enabled)
        self._btn_run_diag.setText(plan.button_text)

    def _refresh_pivot_texts(self) -> None:
        try:
            self._pivot.setItemText("settings", "Настройки")
            self._pivot.setItemText("logs", "Логи")
            self._pivot.setItemText("diag", "Диагностика")
        except Exception:
            pass

    def _refresh_status_texts(self) -> None:
        mgr = _get_proxy_manager()
        running = bool(mgr.is_running)
        plan = TelegramProxyRuntimeController.build_status_plan(
            running=running,
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
            host=mgr.host,
            port=mgr.port,
        )

        if getattr(self, "_status_label", None) is not None:
            self._status_label.setText(plan.status_text)

        if getattr(self, "_btn_toggle", None) is not None:
            self._btn_toggle.setText(plan.toggle_text)

    def _apply_ui_texts(self) -> None:
        try:
            self._refresh_pivot_texts()
            self._refresh_status_texts()

            if getattr(self, "_setup_section_label", None) is not None:
                self._setup_section_label.setText("Быстрая настройка Telegram")
            title_label = getattr(getattr(self, "_settings_card", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText("Настройки")
            title_label = getattr(getattr(self, "_upstream_card", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText("Внешний прокси (upstream)")
            if getattr(self, "_manual_section_label", None) is not None:
                self._manual_section_label.setText("Ручная настройка")

            if getattr(self, "_setup_desc_label", None) is not None:
                self._setup_desc_label.setText(
                    "Нажмите кнопку ниже - Telegram автоматически добавит прокси. "
                    "Настройка требуется один раз.\nЕсли Telegram не открывается попробуйте скопировать ссылку и отправить в любой чат Telegram или кому-то в ЛС — после чего нажмите на отправленную ссылку и подтвердите добавление прокси в Telegram клиент.\nРекомендуем полностью ПЕРЕЗАПУСТИТЬ клиент для более корректного работа прокси после включения Zapret 2 GUI!"
                )
            if getattr(self, "_host_label", None) is not None:
                self._host_label.setText("Адрес:")
            if getattr(self, "_port_label", None) is not None:
                self._port_label.setText("Порт:")
            if getattr(self, "_upstream_desc_label", None) is not None:
                self._upstream_desc_label.setText(
                    "SOCKS5 прокси-сервер для DC заблокированных вашим провайдером.\n"
                    "Используется как резервный канал когда WSS relay и прямое подключение не работают."
                )
            if getattr(self, "_upstream_host_label", None) is not None:
                self._upstream_host_label.setText("Хост:")
            if getattr(self, "_upstream_port_label", None) is not None:
                self._upstream_port_label.setText("Порт:")
            if getattr(self, "_upstream_user_label", None) is not None:
                self._upstream_user_label.setText("Логин:")
            if getattr(self, "_upstream_pass_label", None) is not None:
                self._upstream_pass_label.setText("Пароль:")
            if getattr(self, "_mtproxy_desc_label", None) is not None:
                self._mtproxy_desc_label.setText("MTProxy настраивается в Telegram напрямую. Нажмите для добавления.")
            if getattr(self, "_instr1_label", None) is not None:
                self._instr1_label.setText("Если автоматическая настройка не сработала:")
            if getattr(self, "_instr2_label", None) is not None:
                self._instr2_label.setText("  Telegram -> Настройки -> Продвинутые -> Тип соединения -> Прокси")
            if getattr(self, "_diag_desc_label", None) is not None:
                self._diag_desc_label.setText(
                    "Проверка соединений к Telegram DC, WSS relay эндпоинтов (kws1-kws5), "
                    "SOCKS5 прокси и определение типа блокировки."
                )

            if getattr(self, "_setup_open_btn", None) is not None:
                self._setup_open_btn.setText("Открыть")
                self._setup_open_btn.setToolTip(
                    "Открыть ссылку для автоматической настройки прокси внутри Telegram."
                )
            if getattr(self, "_setup_copy_btn", None) is not None:
                self._setup_copy_btn.setText("Копировать")
                self._setup_copy_btn.setToolTip(
                    "Сохранить ссылку в буфер обмена, если Telegram не открылся автоматически."
                )
            if getattr(self, "_mtproxy_action_btn", None) is not None:
                self._mtproxy_action_btn.setText("Открыть")
                self._mtproxy_action_btn.setToolTip(
                    "MTProxy настраивается в Telegram напрямую. Нажмите для добавления."
                )
            if getattr(self, "_btn_copy_logs", None) is not None:
                self._btn_copy_logs.setText("Копировать все")
            if getattr(self, "_btn_open_log_file", None) is not None:
                self._btn_open_log_file.setText("Открыть файл лога")
            if getattr(self, "_btn_clear_logs", None) is not None:
                self._btn_clear_logs.setText("Очистить")
            if getattr(self, "_btn_copy_diag", None) is not None:
                self._btn_copy_diag.setText("Копировать результат")
            if getattr(self, "_btn_run_diag", None) is not None and self._btn_run_diag.isEnabled():
                self._btn_run_diag.setText("Запустить диагностику")

            if getattr(self, "_host_edit", None) is not None:
                self._host_edit.setPlaceholderText("127.0.0.1")
            if getattr(self, "_upstream_host_edit", None) is not None:
                self._upstream_host_edit.setPlaceholderText("192.168.1.100 или proxy.example.com")
            if getattr(self, "_upstream_user_edit", None) is not None:
                self._upstream_user_edit.setPlaceholderText("username")
            if getattr(self, "_upstream_pass_edit", None) is not None:
                self._upstream_pass_edit.setPlaceholderText("password")
            if getattr(self, "_log_edit", None) is not None:
                self._log_edit.setPlaceholderText("Лог подключений появится здесь...")
            if getattr(self, "_diag_edit", None) is not None:
                self._diag_edit.setPlaceholderText("Нажмите 'Запустить диагностику'...")

            if getattr(self, "_autostart_toggle", None) is not None:
                self._autostart_toggle.set_texts(
                    "Автозапуск прокси",
                    "Запускать прокси автоматически при старте программы",
                )
            if getattr(self, "_auto_deeplink_toggle", None) is not None:
                self._auto_deeplink_toggle.set_texts(
                    "Авто-настройка Telegram",
                    "При первом запуске прокси автоматически открыть ссылку настройки в Telegram",
                )
            if getattr(self, "_upstream_toggle", None) is not None:
                self._upstream_toggle.set_texts(
                    "Использовать внешний прокси",
                    "Маршрутизировать заблокированные DC через внешний SOCKS5 прокси",
                )
            if getattr(self, "_upstream_preset_row", None) is not None:
                self._upstream_preset_row.set_texts(
                    "Сервер",
                    "Выберите сервер из списка или переключитесь на ручной ввод",
                )
            if getattr(self, "_upstream_catalog_hint", None) is not None:
                self._upstream_catalog_hint.setText(
                    "В этой сборке список предустановленных прокси не загружен. "
                    "Доступен только ручной ввод."
                )
            if getattr(self, "_upstream_mode_toggle", None) is not None:
                self._upstream_mode_toggle.set_texts(
                    "Весь трафик через прокси",
                    "Если выключено — только заблокированные DC. Если включено — весь трафик Telegram.",
                )

            if getattr(self, "_manual_host_port_label", None) is not None:
                self._update_manual_instructions()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._apply_ui_texts()

    def _on_copy_diag(self):
        text = self._diag_edit.toPlainText()
        plan = TelegramProxyPageActionsController.copy_text(
            text,
            success_title="Скопировано",
            success_content="Результат диагностики",
        )
        if plan.ok and InfoBar is not None:
            try:
                InfoBar.success(
                    title=plan.info_title,
                    content=plan.info_content,
                    parent=self,
                    duration=2000,
                    position=InfoBarPosition.TOP,
                )
            except Exception:
                pass

    def _refresh_upstream_preset_combo(self, *, select_index: int | None = None) -> int:
        combo = self._upstream_preset_row.combo
        combo.blockSignals(True)
        combo.clear()
        for label, preset in self._upstream_catalog.items():
            combo.addItem(label, userData=preset)

        if not self._upstream_catalog.choices:
            target_index = -1
        elif select_index is None:
            target_index = combo.currentIndex()
            if target_index < 0:
                target_index = 0
            target_index = min(target_index, len(self._upstream_catalog.choices) - 1)
        else:
            target_index = min(max(select_index, 0), len(self._upstream_catalog.choices) - 1)

        combo.setCurrentIndex(target_index)
        combo.blockSignals(False)

        if target_index >= 0:
            self._apply_upstream_preset_ui(target_index)
        return target_index

    def _apply_upstream_preset_ui(self, index: int) -> None:
        upstream_enabled = self._upstream_toggle.toggle.isChecked()
        preset = self._upstream_catalog.preset_at(index)
        has_bundled_presets = self._upstream_catalog.has_bundled_presets()
        is_manual = bool(preset is not None and self._upstream_catalog.is_manual(index))
        is_mtproxy = bool(preset is not None and self._upstream_catalog.is_mtproxy(index))

        self._upstream_preset_row.setVisible(upstream_enabled and has_bundled_presets)
        self._upstream_catalog_hint.setVisible(upstream_enabled and not has_bundled_presets)
        self._upstream_manual_widget.setVisible(upstream_enabled and is_manual)
        self._mtproxy_action_widget.setVisible(upstream_enabled and is_mtproxy)
        self._upstream_mode_toggle.setVisible(upstream_enabled)
        self._upstream_mode_toggle.setEnabled(upstream_enabled)
        self._upstream_mode_toggle.toggle.setEnabled(upstream_enabled)

        if preset is not None and is_mtproxy:
            self._current_mtproxy_link = self._upstream_catalog.mtproxy_link(index)
        else:
            self._current_mtproxy_link = ""

    def _connect_signals(self):
        mgr = _get_proxy_manager()
        mgr.status_changed.connect(self._on_status_changed)
        mgr.stats_updated.connect(self._on_stats_updated)

        self._autostart_toggle.toggled.connect(self._on_autostart_changed)
        self._port_spin.valueChanged.connect(self._on_port_changed)
        self._host_edit.editingFinished.connect(self._on_host_changed)

        # Upstream proxy signals
        self._upstream_toggle.toggled.connect(self._on_upstream_changed)
        self._upstream_preset_row.currentIndexChanged.connect(
            self._on_upstream_preset_changed
        )
        self._upstream_host_edit.editingFinished.connect(self._on_upstream_host_changed)
        self._upstream_port_spin.valueChanged.connect(self._on_upstream_port_changed)
        self._upstream_user_edit.editingFinished.connect(self._on_upstream_user_changed)
        self._upstream_pass_edit.editingFinished.connect(self._on_upstream_pass_changed)
        self._upstream_mode_toggle.toggled.connect(self._on_upstream_mode_changed)

        # Sync initial state — proxy may already be running (e.g., started from tray)
        self._on_status_changed(mgr.is_running)

    def _load_settings(self):
        state = TelegramProxySettingsController.load_state(self._upstream_catalog)

        self._port_spin.blockSignals(True)
        self._port_spin.setValue(state.port)
        self._port_spin.blockSignals(False)

        self._host_edit.setText(state.host)

        self._autostart_toggle.toggle.blockSignals(True)
        self._autostart_toggle.toggle.setChecked(state.autostart_enabled)
        self._autostart_toggle.toggle.blockSignals(False)
        self._update_manual_instructions()

        self._upstream_toggle.toggle.blockSignals(True)
        self._upstream_toggle.toggle.setChecked(state.upstream_enabled)
        self._upstream_toggle.toggle.blockSignals(False)

        self._upstream_host_edit.setText(state.upstream_host)
        self._upstream_port_spin.blockSignals(True)
        self._upstream_port_spin.setValue(state.upstream_port)
        self._upstream_port_spin.blockSignals(False)
        self._upstream_user_edit.setText(state.upstream_user)
        self._upstream_pass_edit.setText(state.upstream_password)

        self._refresh_upstream_preset_combo(select_index=state.upstream_preset_index)

        self._upstream_mode_toggle.toggle.blockSignals(True)
        self._upstream_mode_toggle.toggle.setChecked(state.upstream_mode == "always")
        self._upstream_mode_toggle.toggle.blockSignals(False)

    def _auto_start_check(self):
        """Auto-start proxy if autostart is enabled."""
        try:
            from config.reg import get_tg_proxy_autostart
            if get_tg_proxy_autostart():
                self._start_proxy()
                self._try_auto_deeplink()
        except Exception:
            pass

    def _try_auto_deeplink(self):
        """Open tg:// deep link automatically on first start."""
        if not TelegramProxySettingsController.consume_auto_deeplink_request():
            return
        QTimer.singleShot(2000, self._on_open_in_telegram)
        self._append_log_line("Auto-opening Telegram proxy setup link...")

    # -- Log display (throttled via QTimer, no trimming) --

    def _flush_log_buffer(self):
        """Called every 500ms by QTimer. Drains new lines from ProxyLogger."""
        mgr = _get_proxy_manager()
        new_lines = mgr.proxy_logger.drain()
        if not new_lines:
            return

        self._log_edit.setUpdatesEnabled(False)
        try:
            for line in new_lines:
                self._log_edit.appendPlainText(line)
        finally:
            self._log_edit.setUpdatesEnabled(True)

        # Auto-scroll to bottom
        sb = self._log_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _append_log_line(self, msg: str):
        """Append a single line to the log."""
        mgr = _get_proxy_manager()
        mgr.proxy_logger.log(msg)

    # -- Log tab buttons --

    def _on_copy_all_logs(self):
        text = self._log_edit.toPlainText()
        plan = TelegramProxyPageActionsController.copy_text(
            text,
            success_title="Скопировано",
            success_content=f"{len(text.splitlines())} строк",
        )
        if plan.ok and InfoBar is not None:
            try:
                InfoBar.success(
                    title=plan.info_title,
                    content=plan.info_content,
                    parent=self,
                    duration=2000,
                    position=InfoBarPosition.TOP,
                )
            except Exception:
                pass

    def _on_open_log_file(self):
        mgr = _get_proxy_manager()
        path = mgr.proxy_logger.log_file_path
        plan = TelegramProxyPageActionsController.open_log_file(path)
        if plan.log_line:
            self._append_log_line(plan.log_line)

    def _on_clear_logs(self):
        self._log_edit.clear()

    # -- Handlers --

    def _on_toggle_proxy(self):
        mgr = _get_proxy_manager()
        plan = TelegramProxyRuntimeController.build_toggle_action_plan(
            running=bool(mgr.is_running),
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
        )
        if plan.action == "cancel_restart":
            self._restarting = False
            mgr.status_changed.emit(False)
            if plan.persist_enabled is not None:
                TelegramProxySettingsController.set_proxy_enabled(plan.persist_enabled)
            return
        if plan.action == "ignore":
            return
        if plan.action == "stop":
            self._stop_proxy()
        else:
            self._start_proxy()

    def _restart_if_running(self):
        """Restart proxy if running, so new upstream config takes effect.

        Non-blocking: Qt cleanup runs on GUI thread first, then the blocking
        ProxyController.stop() runs in a background thread. When done,
        _start_proxy is invoked back on the GUI thread via QueuedConnection.
        """
        mgr = _get_proxy_manager()
        plan = TelegramProxyRuntimeController.build_restart_plan(
            running=bool(mgr.is_running),
            restarting=bool(getattr(self, "_restarting", False)),
        )
        if not plan.should_restart:
            return
        self._restarting = True
        self._status_label.setText(plan.status_text)

        # Qt operations on GUI thread BEFORE going to background (Qt-safe)
        mgr._stop_stats_polling()

        def _bg_stop():
            # Pure-Python blocking stop — no Qt objects touched, safe in any thread
            mgr._stop_controller_only()
            from PyQt6.QtCore import QMetaObject, Qt as QtNS
            QMetaObject.invokeMethod(
                self, "_finish_restart",
                QtNS.ConnectionType.QueuedConnection,
            )
        threading.Thread(target=_bg_stop, daemon=True).start()

    @pyqtSlot()
    def _finish_restart(self):
        """Called on GUI thread after background stop completes.
        Checks cancel flag and starts proxy only if restart wasn't cancelled."""
        if not self._restarting:
            # User clicked Stop during restart — don't re-start
            return
        self._restarting = False
        self._start_proxy()

    def _schedule_upstream_restart(self):
        """Debounced proxy restart for SpinBox valueChanged signals."""
        if not hasattr(self, '_upstream_restart_timer'):
            self._upstream_restart_timer = QTimer(self)
            self._upstream_restart_timer.setSingleShot(True)
            self._upstream_restart_timer.timeout.connect(self._restart_if_running)
        self._upstream_restart_timer.start(800)

    @pyqtSlot()
    def _start_proxy(self):
        mgr = _get_proxy_manager()
        port = self._port_spin.value()
        host = self._host_edit.text().strip() or "127.0.0.1"
        upstream_config = TelegramProxySettingsController.build_upstream_config()
        plan = TelegramProxyRuntimeController.build_start_plan(
            starting=bool(getattr(self, "_starting", False)),
            running=bool(mgr.is_running),
            host=host,
            port=port,
            upstream_config=upstream_config,
        )
        if not plan.should_start:
            return

        self._starting = True
        self._btn_toggle.setEnabled(plan.toggle_enabled)
        self._status_label.setText(plan.status_text)
        if plan.upstream_log_line:
            self._append_log_line(plan.upstream_log_line)

        def _bg_start():
            ok = mgr.start_proxy(port=port, mode="socks5", host=host,
                                  upstream_config=upstream_config)
            self._start_result = ok
            from PyQt6.QtCore import QMetaObject, Qt as QtNS
            QMetaObject.invokeMethod(
                self, "_finish_start",
                QtNS.ConnectionType.QueuedConnection,
            )
        threading.Thread(target=_bg_start, daemon=True).start()

    @pyqtSlot()
    def _finish_start(self):
        """Called on GUI thread after background start completes."""
        self._starting = False
        ok = getattr(self, '_start_result', False)
        plan = TelegramProxyRuntimeController.build_finish_start_plan(ok)
        self._btn_toggle.setEnabled(plan.toggle_enabled)
        if plan.persist_enabled is not None:
            TelegramProxySettingsController.set_proxy_enabled(plan.persist_enabled)
        if plan.should_check_relay:
            self._check_relay_after_start()
        elif plan.fallback_to_stopped_status:
            self._on_status_changed(False)

    def _check_relay_after_start(self):
        """Check relay reachability after proxy starts. Runs check in background.

        Logic:
        1. TLS check (port 443) — if OK → update status "Relay OK"
        2. If TLS fails → check TCP port 80 (HTTP) to distinguish:
           - Port 80 works + TLS fails = something breaks TLS (likely zapret desync)
           - Port 80 also fails = ISP blocks the IP entirely
        3. Update status label + show InfoBar warning if needed
        Uses generation counter to discard stale results after stop/restart.
        """
        # Invalidate any previous relay check
        mgr = _get_proxy_manager()
        start_plan = TelegramProxyRuntimeController.build_relay_start_plan(
            current_generation=getattr(self, "_relay_check_gen", 0),
            host=mgr.host,
            port=mgr.port,
        )
        self._relay_check_gen = start_plan.generation
        gen = start_plan.generation

        # Show "checking..." in status
        if mgr.is_running:
            self._status_label.setText(start_plan.status_text)

        def _do_check():
            import time
            # Wait for proxy to warm up and WSS pool to fill
            time.sleep(2)

            # Check if this generation is still current
            if getattr(self, '_relay_check_gen', 0) != gen:
                return  # Stale — proxy was stopped/restarted

            try:
                from telegram_proxy.wss_proxy import check_relay_reachable

                # Retry up to 3 times — DPI is intermittent and can reset
                # individual TLS connections randomly
                best_result = None
                for attempt in range(3):
                    if getattr(self, '_relay_check_gen', 0) != gen:
                        return  # Stale
                    result = check_relay_reachable(timeout=5.0)
                    if result["reachable"]:
                        best_result = result
                        break
                    if attempt < 2:
                        time.sleep(2)

                # Final generation check before writing results
                if getattr(self, '_relay_check_gen', 0) != gen:
                    return  # Stale

                if best_result and best_result["reachable"]:
                    self._relay_diag = {"status": "ok", "ms": best_result["ms"]}
                else:
                    # All attempts failed — check port 80 to determine cause
                    http_ok = TelegramProxyRuntimeController.check_relay_http()

                    # Determine if zapret is running
                    zapret_running = False
                    try:
                        app = self.window()
                        if hasattr(app, 'app') and hasattr(app.app, 'dpi_starter'):
                            zapret_running = app.app.dpi_starter.check_process_running_wmi(silent=True)
                    except Exception:
                        pass

                    self._relay_diag = {
                        "status": "fail",
                        "http_ok": http_ok,
                        "zapret_running": zapret_running,
                    }

                # Check generation before GUI callback
                if getattr(self, '_relay_check_gen', 0) != gen:
                    return  # Stale

                from PyQt6.QtCore import QMetaObject, Qt as QtNS
                QMetaObject.invokeMethod(
                    self, "_apply_relay_result",
                    QtNS.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                log(f"Relay check error: {e}", "WARNING")
        threading.Thread(target=_do_check, daemon=True).start()

    @pyqtSlot()
    def _apply_relay_result(self):
        """Update status label and show warning based on relay check. GUI thread only."""
        diag = getattr(self, "_relay_diag", {})
        mgr = _get_proxy_manager()

        if not mgr.is_running:
            return

        plan = TelegramProxyRuntimeController.build_relay_result_plan(
            host=mgr.host,
            port=mgr.port,
            status=diag.get("status", "fail"),
            ms=diag.get("ms", 0),
            http_ok=bool(diag.get("http_ok", False)),
            zapret_running=bool(diag.get("zapret_running", False)),
        )
        self._status_label.setText(plan.status_text)
        if plan.show_warning and InfoBar is not None:
            InfoBar.warning(
                plan.warning_title, plan.warning_content,
                duration=-1,
                position=InfoBarPosition.TOP,
                parent=self,
            )

    def _stop_proxy(self):
        mgr = _get_proxy_manager()
        mgr.stop_proxy()
        TelegramProxySettingsController.set_proxy_enabled(False)

    def _on_status_changed(self, running: bool):
        mgr = _get_proxy_manager()
        plan = TelegramProxyRuntimeController.build_status_plan(
            running=bool(running),
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
            host=mgr.host,
            port=mgr.port,
        )
        self._status_dot.set_active(plan.dot_active)
        if plan.reset_speed_state:
            self._prev_bytes_sent = 0
            self._prev_bytes_received = 0
            self._speed_hist_up = ()
            self._speed_hist_down = ()
        if plan.clear_stats:
            self._stats_label.setText("")
        if plan.invalidate_relay_check:
            self._relay_check_gen = getattr(self, '_relay_check_gen', 0) + 1

        self._status_label.setText(plan.status_text)
        self._btn_toggle.setText(plan.toggle_text)
        self._port_spin.setEnabled(plan.port_spin_enabled)
        self._host_edit.setEnabled(plan.host_edit_enabled)

    def _on_stats_updated(self, stats):
        if stats is None:
            return
        plan = TelegramProxyRuntimeController.build_stats_plan(
            stats=stats,
            prev_sent=getattr(self, '_prev_bytes_sent', 0),
            prev_recv=getattr(self, '_prev_bytes_received', 0),
            speed_hist_up=tuple(getattr(self, '_speed_hist_up', ()) or ()),
            speed_hist_down=tuple(getattr(self, '_speed_hist_down', ()) or ()),
            interval=2.0,
        )
        self._prev_bytes_sent = plan.next_prev_sent
        self._prev_bytes_received = plan.next_prev_recv
        self._speed_hist_up = plan.next_speed_hist_up
        self._speed_hist_down = plan.next_speed_hist_down
        self._stats_label.setText(plan.stats_text)

    def _on_autostart_changed(self, checked: bool):
        TelegramProxySettingsController.set_autostart(checked)

    def _on_port_changed(self, port: int):
        normalized = TelegramProxySettingsController.set_port(port)
        if normalized != port:
            self._port_spin.blockSignals(True)
            self._port_spin.setValue(normalized)
            self._port_spin.blockSignals(False)
        self._update_manual_instructions()

    def _on_host_changed(self):
        host = TelegramProxySettingsController.set_host(self._host_edit.text().strip())
        self._host_edit.setText(host)
        self._update_manual_instructions()

    # -- Upstream proxy handlers --

    def _on_upstream_changed(self, checked: bool):
        TelegramProxySettingsController.set_upstream_enabled(checked)
        self._apply_upstream_preset_ui(self._upstream_preset_row.combo.currentIndex())
        self._restart_if_running()

    def _on_upstream_preset_changed(self, index: int):
        """Handle upstream server selection."""
        preset = self._upstream_catalog.preset_at(index)
        if preset is None:
            return

        self._apply_upstream_preset_ui(index)

        is_manual = self._upstream_catalog.is_manual(index)
        is_mtproxy = self._upstream_catalog.is_mtproxy(index)

        if is_manual:
            self._upstream_host_edit.clear()
            self._upstream_port_spin.blockSignals(True)
            self._upstream_port_spin.setValue(1080)
            self._upstream_port_spin.blockSignals(False)
            self._upstream_user_edit.clear()
            self._upstream_pass_edit.clear()
            TelegramProxySettingsController.set_upstream_fields("", 1080, "", "")
            self._restart_if_running()
        elif is_mtproxy:
            self._current_mtproxy_link = preset.get("link", "")
        else:
            self._upstream_host_edit.setText(preset.get("host", ""))
            self._upstream_port_spin.blockSignals(True)
            self._upstream_port_spin.setValue(preset.get("port", 1080))
            self._upstream_port_spin.blockSignals(False)
            self._upstream_user_edit.setText(preset.get("username", ""))
            self._upstream_pass_edit.setText(preset.get("password", ""))
            TelegramProxySettingsController.set_upstream_fields(
                preset.get("host", ""), preset.get("port", 0),
                preset.get("username", ""), preset.get("password", ""),
            )
            self._restart_if_running()

    def _on_upstream_host_changed(self):
        TelegramProxySettingsController.set_upstream_fields(
            self._upstream_host_edit.text().strip(),
            self._upstream_port_spin.value(),
            self._upstream_user_edit.text().strip(),
            self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_port_changed(self, port: int):
        TelegramProxySettingsController.set_upstream_fields(
            self._upstream_host_edit.text().strip(),
            port,
            self._upstream_user_edit.text().strip(),
            self._upstream_pass_edit.text(),
        )
        self._schedule_upstream_restart()

    def _on_upstream_user_changed(self):
        TelegramProxySettingsController.set_upstream_fields(
            self._upstream_host_edit.text().strip(),
            self._upstream_port_spin.value(),
            self._upstream_user_edit.text().strip(),
            self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_pass_changed(self):
        TelegramProxySettingsController.set_upstream_fields(
            self._upstream_host_edit.text().strip(),
            self._upstream_port_spin.value(),
            self._upstream_user_edit.text().strip(),
            self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_mode_changed(self, checked: bool):
        TelegramProxySettingsController.set_upstream_mode(checked)
        self._restart_if_running()

    def _on_open_mtproxy(self):
        """Open MTProxy deep link in browser."""
        link = getattr(self, '_current_mtproxy_link', '')
        if not link:
            return
        plan = TelegramProxyPageActionsController.open_external_link(
            link,
            success_log="Opened MTProxy link",
            error_prefix="Failed to open MTProxy link",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)

    def _update_manual_instructions(self):
        """Update manual instructions label with current host/port."""
        self._manual_host_port_label.setText(
            TelegramProxySettingsController.build_manual_instruction_text(
                self._host_edit.text().strip(),
                self._port_spin.value(),
            )
        )

    def _on_open_in_telegram(self):
        """Open tg://socks deep link to auto-configure Telegram."""
        url = TelegramProxySettingsController.build_proxy_url(
            self._host_edit.text().strip(),
            self._port_spin.value(),
        )
        plan = TelegramProxyPageActionsController.open_external_link(
            url,
            success_log=f"Opened deep link: {url}",
            error_prefix="Failed to open link",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)

    def _on_copy_link(self):
        """Copy proxy deep link to clipboard."""
        url = TelegramProxySettingsController.build_proxy_url(
            self._host_edit.text().strip(),
            self._port_spin.value(),
        )
        plan = TelegramProxyPageActionsController.copy_text(
            url,
            success_title="Скопировано",
            success_content=url,
            success_log=f"Copied to clipboard: {url}",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)
        if plan.ok and InfoBar is not None:
            try:
                InfoBar.success(
                    title=plan.info_title,
                    content=plan.info_content,
                    parent=self,
                    duration=2000,
                    position=InfoBarPosition.TOP,
                )
            except Exception:
                pass

    def _ensure_telegram_hosts(self):
        """Check/add Telegram entries in Windows hosts file (background thread)."""
        threading.Thread(
            target=self._ensure_telegram_hosts_worker,
            daemon=True,
        ).start()

    def _ensure_telegram_hosts_worker(self):
        plan = TelegramProxyPageActionsController.ensure_telegram_hosts()
        if not plan.ok and plan.log_line:
            log(plan.log_line, "WARNING")

    def cleanup(self):
        """Called on app exit."""
        if self._log_timer is not None:
            self._log_timer.stop()
        mgr = _get_proxy_manager()
        mgr.cleanup()
