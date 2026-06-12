# ui/pages/telegram_proxy_page.py
"""Telegram WebSocket Proxy — UI page.

Provides controls for starting/stopping the proxy, mode selection,
port configuration, and quick-setup deep link for Telegram.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout,
)

from ui.pages.base_page import BasePage
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from telegram_proxy.ui.build import (
    build_telegram_proxy_diag_panel,
    build_telegram_proxy_logs_panel,
    build_telegram_proxy_shell,
)
from telegram_proxy.ui.diagnostics_workflow import (
    finish_diagnostics,
    poll_diagnostics,
    start_diagnostics,
)
from telegram_proxy.ui.proxy_runtime_workflow import (
    apply_relay_result,
    apply_stats_updated,
    apply_status_changed,
    finish_proxy_start,
    handle_toggle_proxy,
    restart_proxy_if_running,
    start_proxy_runtime,
    start_relay_check,
    stop_proxy_runtime,
)
from telegram_proxy.ui.runtime_helpers import (
    apply_ui_texts,
    apply_upstream_preset_ui,
    refresh_pivot_texts,
    refresh_status_texts,
)
from telegram_proxy.ui.text_plan import TELEGRAM_PROXY_SETTINGS_TEXT
from telegram_proxy.ui.upstream_workflow import (
    handle_upstream_preset_changed,
    handle_upstream_toggle,
    schedule_upstream_restart,
)
from telegram_proxy.ui.settings_save_flow import merge_restart_request
from telegram_proxy.ui.settings_build import (
    build_telegram_proxy_advanced_settings_panel,
    build_telegram_proxy_settings_panel,
)
from telegram_proxy.ui.worker_state import (
    TelegramProxyPageQueuedWorkerState,
    TelegramProxyPageWorkerState,
)
from ui.fluent_widgets import (
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from log.log import log

import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime
import telegram_proxy.config.settings as telegram_proxy_settings
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    SpinBox,
    InfoBar,
    InfoBarPosition,
    SegmentedWidget,
    LineEdit,
    PasswordLineEdit,
    SettingCardGroup,
    PushButton,
    PrimaryPushButton,
)

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

    def __init__(self, parent=None, *, telegram_proxy_feature, get_zapret_running):
        super().__init__(
            "Telegram Proxy",
            TELEGRAM_PROXY_SETTINGS_TEXT.page_subtitle,
            parent,
        )
        self._telegram_proxy = telegram_proxy_feature
        self._get_zapret_running = get_zapret_running
        self._log_timer = None
        self._stats_timer = None
        self._diag_poll_timer = None
        self._upstream_restart_timer = None
        self._diag_runtime = OneShotWorkerRuntime()
        self._proxy_start_runtime = OneShotWorkerRuntime()
        self._proxy_start_state = TelegramProxyPageWorkerState(self._proxy_start_runtime)
        self._proxy_stop_runtime = OneShotWorkerRuntime()
        self._proxy_stop_state = TelegramProxyPageWorkerState(self._proxy_stop_runtime)
        self._restart_stop_runtime = OneShotWorkerRuntime()
        self._restart_stop_state = TelegramProxyPageWorkerState(self._restart_stop_runtime)
        self._relay_check_runtime = OneShotWorkerRuntime()
        self._relay_check_state = TelegramProxyPageWorkerState(self._relay_check_runtime)
        self._cloudflare_check_runtime = OneShotWorkerRuntime()
        self._cloudflare_check_state = TelegramProxyPageWorkerState(self._cloudflare_check_runtime)
        self._cloudflare_check_kind = ""
        self._ensure_hosts_runtime = OneShotWorkerRuntime()
        self._ensure_hosts_state = TelegramProxyPageWorkerState(self._ensure_hosts_runtime)
        self._settings_save_runtime = OneShotWorkerRuntime()
        self._settings_save_state = TelegramProxyPageQueuedWorkerState(self._settings_save_runtime)
        self._open_log_file_runtime = OneShotWorkerRuntime()
        self._open_log_file_state = TelegramProxyPageQueuedWorkerState(self._open_log_file_runtime)
        self._external_link_runtime = OneShotWorkerRuntime()
        self._external_link_state = TelegramProxyPageQueuedWorkerState(self._external_link_runtime)
        self._log_line_runtime = OneShotWorkerRuntime()
        self._log_line_state = TelegramProxyPageQueuedWorkerState(self._log_line_runtime)
        self._auto_deeplink_runtime = OneShotWorkerRuntime()
        self._auto_deeplink_state = TelegramProxyPageWorkerState(self._auto_deeplink_runtime)
        self._settings_save_restart_pending = ""
        self._initial_state_runtime = OneShotWorkerRuntime()
        self._initial_state_load_started_at = 0.0
        self._relay_check_gen = 0
        self._cleanup_in_progress = False
        self._runtime_initialized = False
        self._built_panel_indexes: set[int] = set()
        self._advanced_settings_built = False
        self._advanced_signals_connected = False
        self._initial_advanced_build_scheduled = False
        self._advanced_auto_sections: set[str] = set()
        self._initial_state = telegram_proxy_settings.TelegramProxyPageInitialStatePlan(
            upstream_catalog=telegram_proxy_settings.UpstreamCatalog(),
            settings=telegram_proxy_settings.default_state(),
        )
        self._current_settings_state = self._initial_state.settings
        self._btn_copy_logs = None
        self._btn_open_log_file = None
        self._btn_clear_logs = None
        self._log_edit = None
        self._log_text_cache = ""
        self._log_text_line_count = 0
        self._diag_desc_label = None
        self._btn_run_diag = None
        self._btn_copy_diag = None
        self._diag_edit = None
        self._diag_text_cache = ""
        self._setup_ui()
        self._request_initial_state_load()
        self._after_ui_built()
        # Запуск Telegram Proxy живёт в общем старте приложения,
        # поэтому страница не поднимает его сама.

    def _proxy_manager(self):
        return self._telegram_proxy.get_proxy_manager()

    def _worker_state(self, state_attr: str, runtime_attr: str) -> TelegramProxyPageWorkerState:
        state = self.__dict__.get(state_attr)
        if state is None:
            state = TelegramProxyPageWorkerState(self.__dict__.get(runtime_attr))
            self.__dict__[state_attr] = state
        return state

    def _queued_worker_state(self, state_attr: str, runtime_attr: str) -> TelegramProxyPageQueuedWorkerState:
        state = self.__dict__.get(state_attr)
        if state is None:
            state = TelegramProxyPageQueuedWorkerState(self.__dict__.get(runtime_attr))
            self.__dict__[state_attr] = state
        return state

    def create_initial_state_worker(self, request_id: int):
        return self._telegram_proxy.create_page_initial_state_worker(request_id, parent=self)

    def _request_initial_state_load(self) -> None:
        self._initial_state_load_started_at = time.perf_counter()

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_initial_state_loaded)
            worker.failed.connect(self._on_initial_state_failed)

        self._initial_state_runtime.start_qthread_worker(
            worker_factory=self.create_initial_state_worker,
            bind_worker=bind_worker,
        )

    def _on_initial_state_loaded(self, request_id: int, initial_state) -> None:
        if not self._initial_state_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._log_ui_timing("telegram_proxy_ui.initial_state.load", self._initial_state_load_started_at)
        self._initial_state = initial_state
        self._apply_initial_upstream_catalog(getattr(initial_state, "upstream_catalog", None))
        self._apply_initial_settings_state(getattr(initial_state, "settings", telegram_proxy_settings.default_state()))

    def _on_initial_state_failed(self, request_id: int, error: str) -> None:
        if not self._initial_state_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Не удалось загрузить начальное состояние Telegram Proxy: {error}", "WARNING")

    def _after_ui_built(self) -> None:
        started_at = time.perf_counter()
        self._connect_signals()
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._flush_log_buffer)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._emit_stats_if_visible)
        if self.isVisible():
            self._stats_timer.start(2000)
        self._apply_ui_texts()
        self._log_ui_timing("telegram_proxy_ui.after_ui_built.total", started_at)

    def _run_runtime_init_once(self) -> None:
        plan = telegram_proxy_page_runtime.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.ensure_hosts_once:
            return
        self._runtime_initialized = True
        self._ensure_telegram_hosts()

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()
        self._apply_advanced_settings_ui()

    def _setup_ui(self):
        started_at = time.perf_counter()
        shell = build_telegram_proxy_shell(
            segmented_widget_cls=SegmentedWidget,
            parent=self,
            on_switch_tab=self._switch_tab,
        )
        self._pivot = shell.pivot
        self._stacked = shell.stacked
        self._settings_layout = shell.settings_layout

        self._build_settings_panel(shell.settings_layout)
        self._built_panel_indexes.add(0)
        self._logs_layout = shell.logs_layout
        self._diag_layout = shell.diag_layout

        self.add_widget(self._pivot)
        self.add_widget(self._stacked)
        self._stacked.setCurrentIndex(0)
        self._log_ui_timing("telegram_proxy_ui.setup_ui.total", started_at)

    def _ensure_panel_built(self, index: int) -> None:
        if index in self._built_panel_indexes:
            return
        started_at = time.perf_counter()
        if index == 1:
            self._build_logs_panel(self._logs_layout)
            self._built_panel_indexes.add(index)
            self._apply_ui_texts()
            self._flush_log_buffer()
            self._log_ui_timing("telegram_proxy_ui.logs_panel.build", started_at)
        elif index == 2:
            self._build_diag_panel(self._diag_layout)
            self._built_panel_indexes.add(index)
            self._apply_ui_texts()
            self._log_ui_timing("telegram_proxy_ui.diag_panel.build", started_at)

    def _switch_tab(self, index: int):
        self._ensure_panel_built(index)
        self._stacked.setCurrentIndex(index)
        self._sync_log_timer()
        keys = ["settings", "logs", "diag"]
        if 0 <= index < len(keys):
            self._pivot.setCurrentItem(keys[index])

    def _sync_log_timer(self) -> None:
        if self._log_timer is None:
            return
        should_run = bool(self.isVisible() and self._stacked.currentIndex() == 1 and self._log_edit is not None)
        if should_run and not self._log_timer.isActive():
            self._log_timer.start(_LOG_REFRESH_MS)
        elif not should_run and self._log_timer.isActive():
            self._log_timer.stop()

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
        from ui.widgets.win11_controls import Win11ToggleRow, Win11ComboRow
        widgets = build_telegram_proxy_settings_panel(
            layout,
            content_parent=self.content,
            status_dot_cls=_StatusDot,
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
            on_toggle_proxy=self._on_toggle_proxy,
            on_open_in_telegram=self._on_open_in_telegram,
            on_copy_link=self._on_copy_link,
            on_open_mtproxy=self._on_open_mtproxy,
            on_generate_mtproxy_secret=self._on_generate_mtproxy_secret,
            on_copy_fake_tls_nginx_config=self._on_copy_fake_tls_nginx_config,
            on_test_cloudflare=self._on_test_cloudflare,
            on_copy_cloudflare_dns=self._on_copy_cloudflare_dns,
            on_test_cloudflare_worker=self._on_test_cloudflare_worker,
            on_copy_cloudflare_worker_code=self._on_copy_cloudflare_worker_code,
            upstream_catalog=self._initial_state.upstream_catalog,
        )
        self._status_card = widgets.status_card
        self._status_dot = widgets.status_dot
        self._status_label = widgets.status_label
        self._btn_toggle = widgets.btn_toggle
        self._stats_label = widgets.stats_label
        self._setup_section_label = widgets.setup_section_label
        self._setup_desc_label = widgets.setup_desc_label
        self._setup_fallback_label = widgets.setup_fallback_label
        self._setup_card = widgets.setup_card
        self._setup_open_btn = widgets.setup_open_btn
        self._setup_copy_btn = widgets.setup_copy_btn
        self._settings_card = widgets.settings_card
        self._settings_host_row = widgets.settings_host_row
        self._host_label = widgets.host_label
        self._host_edit = widgets.host_edit
        self._port_label = widgets.port_label
        self._port_spin = widgets.port_spin
        self._proxy_mode_row = widgets.proxy_mode_row
        self._mtproxy_secret_row = widgets.mtproxy_secret_row
        self._mtproxy_secret_label = widgets.mtproxy_secret_label
        self._mtproxy_secret_edit = widgets.mtproxy_secret_edit
        self._mtproxy_generate_btn = widgets.mtproxy_generate_btn
        self._fake_tls_domain_row = widgets.fake_tls_domain_row
        self._fake_tls_domain_label = widgets.fake_tls_domain_label
        self._fake_tls_domain_edit = widgets.fake_tls_domain_edit
        self._fake_tls_nginx_btn = widgets.fake_tls_nginx_btn
        self._auto_deeplink_toggle = widgets.auto_deeplink_toggle
        self._advanced_toggle = widgets.advanced_toggle
        self._advanced_card = widgets.advanced_card
        self._upstream_card = widgets.upstream_card
        self._upstream_desc_label = widgets.upstream_desc_label
        self._upstream_toggle = widgets.upstream_toggle
        self._upstream_catalog = widgets.upstream_catalog
        self._upstream_preset_row = widgets.upstream_preset_row
        self._upstream_catalog_hint = widgets.upstream_catalog_hint
        self._upstream_manual_widget = widgets.upstream_manual_widget
        self._upstream_host_label = widgets.upstream_host_label
        self._upstream_host_edit = widgets.upstream_host_edit
        self._upstream_port_label = widgets.upstream_port_label
        self._upstream_port_spin = widgets.upstream_port_spin
        self._upstream_user_label = widgets.upstream_user_label
        self._upstream_user_edit = widgets.upstream_user_edit
        self._upstream_pass_label = widgets.upstream_pass_label
        self._upstream_pass_edit = widgets.upstream_pass_edit
        self._mtproxy_action_btn = widgets.mtproxy_action_btn
        self._mtproxy_action_widget = widgets.mtproxy_action_widget
        self._current_mtproxy_preset_id = ""
        self._upstream_mode_toggle = widgets.upstream_mode_toggle
        self._cloudflare_toggle = widgets.cloudflare_toggle
        self._cloudflare_domains_row = widgets.cloudflare_domains_row
        self._cloudflare_domains_label = widgets.cloudflare_domains_label
        self._cloudflare_domains_edit = widgets.cloudflare_domains_edit
        self._cloudflare_test_btn = widgets.cloudflare_test_btn
        self._cloudflare_dns_btn = widgets.cloudflare_dns_btn
        self._cloudflare_worker_toggle = widgets.cloudflare_worker_toggle
        self._cloudflare_worker_domains_row = widgets.cloudflare_worker_domains_row
        self._cloudflare_worker_domains_label = widgets.cloudflare_worker_domains_label
        self._cloudflare_worker_domains_edit = widgets.cloudflare_worker_domains_edit
        self._cloudflare_worker_test_btn = widgets.cloudflare_worker_test_btn
        self._cloudflare_worker_code_btn = widgets.cloudflare_worker_code_btn
        self._dc_ip_row = widgets.dc_ip_row
        self._dc_ip_label = widgets.dc_ip_label
        self._dc_ip_edit = widgets.dc_ip_edit
        self._performance_label = widgets.performance_label
        self._pool_size_label = widgets.pool_size_label
        self._pool_size_spin = widgets.pool_size_spin
        self._buffer_kb_label = widgets.buffer_kb_label
        self._buffer_kb_spin = widgets.buffer_kb_spin
        self._proxy_protocol_toggle = widgets.proxy_protocol_toggle
        self._manual_section_label = widgets.manual_section_label
        self._instructions_card = widgets.instructions_card
        self._instr1_label = widgets.instr1_label
        self._instr2_label = widgets.instr2_label
        self._manual_host_port_label = widgets.manual_host_port_label

    def _assign_advanced_settings_widgets(self, widgets) -> None:
        self._advanced_card = widgets.advanced_card
        self._upstream_card = widgets.upstream_card
        self._mtproxy_secret_row = widgets.mtproxy_secret_row
        self._mtproxy_secret_label = widgets.mtproxy_secret_label
        self._mtproxy_secret_edit = widgets.mtproxy_secret_edit
        self._mtproxy_generate_btn = widgets.mtproxy_generate_btn
        self._fake_tls_domain_row = widgets.fake_tls_domain_row
        self._fake_tls_domain_label = widgets.fake_tls_domain_label
        self._fake_tls_domain_edit = widgets.fake_tls_domain_edit
        self._fake_tls_nginx_btn = widgets.fake_tls_nginx_btn
        self._upstream_card = widgets.upstream_card
        self._upstream_desc_label = widgets.upstream_desc_label
        self._upstream_toggle = widgets.upstream_toggle
        self._upstream_catalog = widgets.upstream_catalog
        self._upstream_preset_row = widgets.upstream_preset_row
        self._upstream_catalog_hint = widgets.upstream_catalog_hint
        self._upstream_manual_widget = widgets.upstream_manual_widget
        self._upstream_host_label = widgets.upstream_host_label
        self._upstream_host_edit = widgets.upstream_host_edit
        self._upstream_port_label = widgets.upstream_port_label
        self._upstream_port_spin = widgets.upstream_port_spin
        self._upstream_user_label = widgets.upstream_user_label
        self._upstream_user_edit = widgets.upstream_user_edit
        self._upstream_pass_label = widgets.upstream_pass_label
        self._upstream_pass_edit = widgets.upstream_pass_edit
        self._mtproxy_action_btn = widgets.mtproxy_action_btn
        self._mtproxy_action_widget = widgets.mtproxy_action_widget
        self._upstream_mode_toggle = widgets.upstream_mode_toggle
        self._cloudflare_toggle = widgets.cloudflare_toggle
        self._cloudflare_domains_row = widgets.cloudflare_domains_row
        self._cloudflare_domains_label = widgets.cloudflare_domains_label
        self._cloudflare_domains_edit = widgets.cloudflare_domains_edit
        self._cloudflare_test_btn = widgets.cloudflare_test_btn
        self._cloudflare_dns_btn = widgets.cloudflare_dns_btn
        self._cloudflare_worker_toggle = widgets.cloudflare_worker_toggle
        self._cloudflare_worker_domains_row = widgets.cloudflare_worker_domains_row
        self._cloudflare_worker_domains_label = widgets.cloudflare_worker_domains_label
        self._cloudflare_worker_domains_edit = widgets.cloudflare_worker_domains_edit
        self._cloudflare_worker_test_btn = widgets.cloudflare_worker_test_btn
        self._cloudflare_worker_code_btn = widgets.cloudflare_worker_code_btn
        self._dc_ip_row = widgets.dc_ip_row
        self._dc_ip_label = widgets.dc_ip_label
        self._dc_ip_edit = widgets.dc_ip_edit
        self._performance_label = widgets.performance_label
        self._pool_size_label = widgets.pool_size_label
        self._pool_size_spin = widgets.pool_size_spin
        self._buffer_kb_label = widgets.buffer_kb_label
        self._buffer_kb_spin = widgets.buffer_kb_spin
        self._proxy_protocol_toggle = widgets.proxy_protocol_toggle
        self._manual_section_label = widgets.manual_section_label
        self._instructions_card = widgets.instructions_card
        self._instr1_label = widgets.instr1_label
        self._instr2_label = widgets.instr2_label
        self._manual_host_port_label = widgets.manual_host_port_label

    def _ensure_advanced_settings_built(self) -> None:
        if self.__dict__.get("_advanced_settings_built", False):
            return
        started_at = time.perf_counter()
        from ui.widgets.win11_controls import Win11ToggleRow, Win11ComboRow

        widgets = build_telegram_proxy_advanced_settings_panel(
            self._settings_layout,
            content_parent=self.content,
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
            on_open_mtproxy=self._on_open_mtproxy,
            on_generate_mtproxy_secret=self._on_generate_mtproxy_secret,
            on_copy_fake_tls_nginx_config=self._on_copy_fake_tls_nginx_config,
            on_test_cloudflare=self._on_test_cloudflare,
            on_copy_cloudflare_dns=self._on_copy_cloudflare_dns,
            on_test_cloudflare_worker=self._on_test_cloudflare_worker,
            on_copy_cloudflare_worker_code=self._on_copy_cloudflare_worker_code,
            upstream_catalog=self._upstream_catalog,
        )
        self._assign_advanced_settings_widgets(widgets)
        self._advanced_settings_built = True
        self._connect_advanced_signals()
        self._apply_ui_texts()
        self._apply_advanced_settings_state(self._current_settings_state)
        self._log_ui_timing("telegram_proxy_ui.advanced_settings.build", started_at)

    def _build_logs_panel(self, layout: QVBoxLayout):
        widgets = build_telegram_proxy_logs_panel(
            layout,
            push_button_cls=PushButton,
            on_copy_all_logs=self._on_copy_all_logs,
            on_open_log_file=self._on_open_log_file,
            on_clear_logs=self._on_clear_logs,
        )
        self._btn_copy_logs = widgets.btn_copy_logs
        self._btn_open_log_file = widgets.btn_open_log_file
        self._btn_clear_logs = widgets.btn_clear_logs
        self._log_edit = widgets.log_edit

    def _build_diag_panel(self, layout: QVBoxLayout):
        widgets = build_telegram_proxy_diag_panel(
            layout,
            caption_label_cls=CaptionLabel,
            primary_push_button_cls=PrimaryPushButton,
            push_button_cls=PushButton,
            on_run_diagnostics=self._on_run_diagnostics,
            on_copy_diag=self._on_copy_diag,
        )
        self._diag_desc_label = widgets.diag_desc_label
        self._btn_run_diag = widgets.btn_run_diag
        self._btn_copy_diag = widgets.btn_copy_diag
        self._diag_edit = widgets.diag_edit

    def _on_run_diagnostics(self):
        """Run network diagnostics in a background thread."""
        started = start_diagnostics(
            page=self,
            cleanup_in_progress=self._cleanup_in_progress,
            btn_run_diag=self._btn_run_diag,
            diag_edit=self._diag_edit,
            existing_poll_timer=self._diag_poll_timer,
            diag_runtime=self._diag_runtime,
            proxy_port=self._port_spin.value(),
            telegram_proxy_feature=self._telegram_proxy,
            publish_diag_result=self._publish_diag_result,
            set_diag_result=lambda value: setattr(self, "_diag_result", value),
            set_thread_done=lambda value: setattr(self, "_diag_thread_done", value),
            poll_diag_callback=self._poll_diag,
        )
        if started is None:
            return
        self._diag_poll_timer = started
        self._diag_proxy_port = self._port_spin.value()

    def _poll_diag(self):
        """Check if diag thread has new results."""
        poll_diagnostics(
            cleanup_in_progress=self._cleanup_in_progress,
            diag_poll_timer=self._diag_poll_timer,
            diag_result=self._diag_result,
            diag_thread_done=self._diag_thread_done,
            telegram_proxy_feature=self._telegram_proxy,
            update_diag=self._update_diag,
            finish_diag=self._diag_finished,
        )

    def _publish_diag_result(self, text: str) -> None:
        if self._cleanup_in_progress:
            return
        self._diag_result = text

    def _update_diag(self, text: str):
        self._diag_text_cache = str(text or "")
        self._diag_edit.setPlainText(text)
        sb = self._diag_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _diag_finished(self):
        finish_diagnostics(
            btn_run_diag=self._btn_run_diag,
            telegram_proxy_feature=self._telegram_proxy,
        )

    def _refresh_pivot_texts(self) -> None:
        refresh_pivot_texts(self._pivot)

    def _refresh_status_texts(self) -> None:
        mgr = self._proxy_manager()
        refresh_status_texts(
            manager=mgr,
            status_label=getattr(self, "_status_label", None),
            btn_toggle=getattr(self, "_btn_toggle", None),
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
        )

    def _apply_ui_texts(self) -> None:
        apply_ui_texts(
            refresh_pivot_texts_callback=self._refresh_pivot_texts,
            refresh_status_texts_callback=self._refresh_status_texts,
            setup_section_label=getattr(self, "_setup_section_label", None),
            settings_card=getattr(self, "_settings_card", None),
            advanced_card=getattr(self, "_advanced_card", None),
            upstream_card=getattr(self, "_upstream_card", None),
            manual_section_label=getattr(self, "_manual_section_label", None),
            setup_desc_label=getattr(self, "_setup_desc_label", None),
            setup_fallback_label=getattr(self, "_setup_fallback_label", None),
            host_label=getattr(self, "_host_label", None),
            port_label=getattr(self, "_port_label", None),
            mtproxy_secret_label=getattr(self, "_mtproxy_secret_label", None),
            fake_tls_domain_label=getattr(self, "_fake_tls_domain_label", None),
            dc_ip_label=getattr(self, "_dc_ip_label", None),
            performance_label=getattr(self, "_performance_label", None),
            pool_size_label=getattr(self, "_pool_size_label", None),
            buffer_kb_label=getattr(self, "_buffer_kb_label", None),
            cloudflare_domains_label=getattr(self, "_cloudflare_domains_label", None),
            cloudflare_worker_domains_label=getattr(self, "_cloudflare_worker_domains_label", None),
            upstream_desc_label=getattr(self, "_upstream_desc_label", None),
            upstream_host_label=getattr(self, "_upstream_host_label", None),
            upstream_port_label=getattr(self, "_upstream_port_label", None),
            upstream_user_label=getattr(self, "_upstream_user_label", None),
            upstream_pass_label=getattr(self, "_upstream_pass_label", None),
            mtproxy_desc_label=getattr(self, "_mtproxy_desc_label", None),
            instr1_label=getattr(self, "_instr1_label", None),
            instr2_label=getattr(self, "_instr2_label", None),
            diag_desc_label=getattr(self, "_diag_desc_label", None),
            setup_open_btn=getattr(self, "_setup_open_btn", None),
            setup_copy_btn=getattr(self, "_setup_copy_btn", None),
            mtproxy_action_btn=getattr(self, "_mtproxy_action_btn", None),
            cloudflare_test_btn=getattr(self, "_cloudflare_test_btn", None),
            cloudflare_dns_btn=getattr(self, "_cloudflare_dns_btn", None),
            fake_tls_nginx_btn=getattr(self, "_fake_tls_nginx_btn", None),
            cloudflare_worker_test_btn=getattr(self, "_cloudflare_worker_test_btn", None),
            cloudflare_worker_code_btn=getattr(self, "_cloudflare_worker_code_btn", None),
            btn_copy_logs=getattr(self, "_btn_copy_logs", None),
            btn_open_log_file=getattr(self, "_btn_open_log_file", None),
            btn_clear_logs=getattr(self, "_btn_clear_logs", None),
            btn_copy_diag=getattr(self, "_btn_copy_diag", None),
            btn_run_diag=getattr(self, "_btn_run_diag", None),
            host_edit=getattr(self, "_host_edit", None),
            mtproxy_secret_edit=getattr(self, "_mtproxy_secret_edit", None),
            fake_tls_domain_edit=getattr(self, "_fake_tls_domain_edit", None),
            dc_ip_edit=getattr(self, "_dc_ip_edit", None),
            cloudflare_domains_edit=getattr(self, "_cloudflare_domains_edit", None),
            cloudflare_worker_domains_edit=getattr(self, "_cloudflare_worker_domains_edit", None),
            upstream_host_edit=getattr(self, "_upstream_host_edit", None),
            upstream_user_edit=getattr(self, "_upstream_user_edit", None),
            upstream_pass_edit=getattr(self, "_upstream_pass_edit", None),
            log_edit=getattr(self, "_log_edit", None),
            diag_edit=getattr(self, "_diag_edit", None),
            auto_deeplink_toggle=getattr(self, "_auto_deeplink_toggle", None),
            advanced_toggle=getattr(self, "_advanced_toggle", None),
            proxy_mode_row=getattr(self, "_proxy_mode_row", None),
            proxy_protocol_toggle=getattr(self, "_proxy_protocol_toggle", None),
            upstream_toggle=getattr(self, "_upstream_toggle", None),
            upstream_preset_row=getattr(self, "_upstream_preset_row", None),
            upstream_catalog_hint=getattr(self, "_upstream_catalog_hint", None),
            upstream_mode_toggle=getattr(self, "_upstream_mode_toggle", None),
            cloudflare_toggle=getattr(self, "_cloudflare_toggle", None),
            cloudflare_worker_toggle=getattr(self, "_cloudflare_worker_toggle", None),
            update_manual_instructions_callback=self._update_manual_instructions,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._apply_ui_texts()

    def _on_copy_diag(self):
        text = str(self.__dict__.get("_diag_text_cache", "") or "")
        plan = self._telegram_proxy.copy_text(
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

    def _apply_upstream_preset_ui(self, index: int) -> None:
        if not self.__dict__.get("_advanced_settings_built", False):
            return
        self._current_mtproxy_preset_id = apply_upstream_preset_ui(
            upstream_toggle=self._upstream_toggle,
            upstream_catalog=self._upstream_catalog,
            upstream_preset_row=self._upstream_preset_row,
            upstream_catalog_hint=self._upstream_catalog_hint,
            upstream_manual_widget=self._upstream_manual_widget,
            mtproxy_action_widget=self._mtproxy_action_widget,
            upstream_mode_toggle=self._upstream_mode_toggle,
            index=index,
        )
        enable_setting_card_group_auto_height(self._upstream_card)

    def _apply_initial_upstream_catalog(self, upstream_catalog) -> None:
        if upstream_catalog is None:
            return
        self._upstream_catalog = upstream_catalog
        if not self.__dict__.get("_advanced_settings_built", False):
            return
        combo = self._upstream_preset_row.combo
        combo.blockSignals(True)
        try:
            combo.clear()
            for text, data in upstream_catalog.items():
                combo.addItem(text, userData=data)
        finally:
            combo.blockSignals(False)
        try:
            self._upstream_preset_row.refresh_accessibility()
        except Exception:
            pass

    def _connect_signals(self):
        mgr = self._proxy_manager()
        mgr.status_changed.connect(self._on_status_changed)

        self._port_spin.valueChanged.connect(self._on_port_changed)
        self._host_edit.editingFinished.connect(self._on_host_changed)
        self._advanced_toggle.toggled.connect(self._on_advanced_toggled)
        self._proxy_mode_row.currentIndexChanged.connect(self._on_proxy_mode_changed)
        self._connect_advanced_signals()

        # Sync initial state — proxy may already be running (e.g., started from tray)
        self._on_status_changed(mgr.is_running)

    def _connect_advanced_signals(self) -> None:
        if self.__dict__.get("_advanced_signals_connected", False):
            return
        if not self.__dict__.get("_advanced_settings_built", False):
            return
        self._mtproxy_secret_edit.editingFinished.connect(self._on_mtproxy_secret_changed)
        self._fake_tls_domain_edit.editingFinished.connect(self._on_fake_tls_domain_changed)
        self._proxy_protocol_toggle.toggled.connect(self._on_proxy_protocol_changed)
        self._dc_ip_edit.editingFinished.connect(self._on_dc_ip_changed)
        self._pool_size_spin.valueChanged.connect(self._on_pool_size_changed)
        self._buffer_kb_spin.valueChanged.connect(self._on_buffer_kb_changed)

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
        self._cloudflare_toggle.toggled.connect(self._on_cloudflare_changed)
        self._cloudflare_domains_edit.editingFinished.connect(self._on_cloudflare_domains_changed)
        self._cloudflare_worker_toggle.toggled.connect(self._on_cloudflare_worker_changed)
        self._cloudflare_worker_domains_edit.editingFinished.connect(self._on_cloudflare_worker_domains_changed)
        self._advanced_signals_connected = True

    def _apply_initial_settings_state(self, state: telegram_proxy_settings.TelegramProxySettingsState) -> None:
        started_at = time.perf_counter()
        self._current_settings_state = state
        self._port_spin.blockSignals(True)
        self._port_spin.setValue(state.port)
        self._port_spin.blockSignals(False)

        self._host_edit.setText(state.host)
        self._update_manual_instructions()

        self._proxy_mode_row.setCurrentData(state.mode, block_signals=True)
        self._advanced_auto_sections = self._advanced_settings_auto_sections(state)
        advanced_should_open = bool(self._advanced_auto_sections)
        self._advanced_toggle.setChecked(advanced_should_open, block_signals=True)
        if advanced_should_open:
            self._schedule_initial_advanced_settings_build()
        self._apply_advanced_settings_state(state)
        self._log_ui_timing("telegram_proxy_ui.settings.apply", started_at)

    def _schedule_initial_advanced_settings_build(self) -> None:
        if self.__dict__.get("_advanced_settings_built", False):
            return
        if self.__dict__.get("_initial_advanced_build_scheduled", False):
            return
        self._initial_advanced_build_scheduled = True
        QTimer.singleShot(150, self._run_initial_advanced_settings_build)

    def _run_initial_advanced_settings_build(self) -> None:
        self._initial_advanced_build_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        try:
            advanced = bool(self._advanced_toggle.isChecked())
        except Exception:
            advanced = False
        if not advanced:
            return
        self._ensure_advanced_settings_built()
        self._apply_advanced_settings_state(self._current_settings_state)

    def _apply_advanced_settings_state(self, state: telegram_proxy_settings.TelegramProxySettingsState) -> None:
        if not self.__dict__.get("_advanced_settings_built", False):
            return
        self._mtproxy_secret_edit.setText(state.mtproxy_secret)
        self._fake_tls_domain_edit.setText(state.fake_tls_domain)
        self._proxy_protocol_toggle.setChecked(state.proxy_protocol, block_signals=True)
        self._dc_ip_edit.setText(", ".join(state.dc_ip))
        self._pool_size_spin.blockSignals(True)
        self._pool_size_spin.setValue(state.pool_size)
        self._pool_size_spin.blockSignals(False)
        self._buffer_kb_spin.blockSignals(True)
        self._buffer_kb_spin.setValue(state.buffer_kb)
        self._buffer_kb_spin.blockSignals(False)

        self._upstream_toggle.setChecked(state.upstream_enabled, block_signals=True)

        self._upstream_host_edit.setText(state.upstream_host)
        self._upstream_port_spin.blockSignals(True)
        self._upstream_port_spin.setValue(state.upstream_port)
        self._upstream_port_spin.blockSignals(False)
        self._upstream_user_edit.setText(state.upstream_user)
        self._upstream_pass_edit.setText(state.upstream_password)

        if self._upstream_catalog.choices:
            target_index = min(max(int(state.upstream_preset_index), 0), len(self._upstream_catalog.choices) - 1)
            self._upstream_preset_row.setCurrentIndex(target_index, block_signals=True)
            self._apply_upstream_preset_ui(target_index)

        self._upstream_mode_toggle.setChecked(state.upstream_mode == "always", block_signals=True)
        self._cloudflare_toggle.setChecked(state.cloudflare_enabled, block_signals=True)
        self._cloudflare_domains_edit.setText(", ".join(state.cloudflare_domains))
        self._cloudflare_worker_toggle.setChecked(state.cloudflare_worker_enabled, block_signals=True)
        self._cloudflare_worker_domains_edit.setText(", ".join(state.cloudflare_worker_domains))
        self._apply_advanced_settings_ui()
        self._apply_local_proxy_mode_ui()
        self._apply_cloudflare_ui()
        self._apply_auto_advanced_section_visibility()

    def _advanced_settings_auto_sections(self, state: telegram_proxy_settings.TelegramProxySettingsState) -> set[str]:
        sections: set[str] = set()
        if state.mode == "mtproxy":
            sections.add("mtproxy")
        if (
            state.upstream_enabled
            or state.upstream_host
            or state.upstream_user
            or state.upstream_password
            or state.upstream_preset_id
        ):
            sections.add("upstream")
        if (
            state.cloudflare_enabled
            or state.cloudflare_domains
            or state.cloudflare_worker_enabled
            or state.cloudflare_worker_domains
        ):
            sections.add("cloudflare")
        if state.dc_ip:
            sections.add("dc_ip")
        if state.pool_size != 4 or state.buffer_kb != 256:
            sections.add("performance")
        return sections

    def _advanced_settings_should_open(self, state: telegram_proxy_settings.TelegramProxySettingsState) -> bool:
        return bool(self._advanced_settings_auto_sections(state))

    def _advanced_section_visible(self, section: str) -> bool:
        sections = set(self.__dict__.get("_advanced_auto_sections") or set())
        return not sections or str(section or "") in sections

    def _try_auto_deeplink(self):
        """Open tg:// deep link automatically on first start."""
        self._request_auto_deeplink_check()

    def create_auto_deeplink_worker(self, request_id: int):
        return self._telegram_proxy.create_auto_deeplink_worker(request_id, parent=self)

    def _request_auto_deeplink_check(self) -> None:
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").start_or_mark_pending(self._start_auto_deeplink_worker)

    def _start_auto_deeplink_worker(self) -> None:
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").pending = False
        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_auto_deeplink_checked)
            worker.failed.connect(self._on_auto_deeplink_failed)

        self._auto_deeplink_runtime.start_qthread_worker(
            worker_factory=self.create_auto_deeplink_worker,
            bind_worker=bind_worker,
            on_finished=self._on_auto_deeplink_worker_finished,
        )

    def _on_auto_deeplink_checked(self, request_id: int, should_open: bool) -> None:
        if not self._auto_deeplink_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").pending:
            return
        if not should_open:
            return
        QTimer.singleShot(2000, self._on_open_in_telegram)
        self._append_log_line("Auto-opening Telegram proxy setup link...")

    def _on_auto_deeplink_failed(self, request_id: int, error: str) -> None:
        if not self._auto_deeplink_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").pending:
            return
        log(f"Telegram Proxy auto deeplink check failed: {error}", "WARNING")

    def _on_auto_deeplink_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_auto_deeplink_runtime"), _worker):
            return
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_auto_deeplink_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_auto_deeplink_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").schedule_start(
            QTimer.singleShot,
            self._start_auto_deeplink_worker,
        )

    def _run_scheduled_auto_deeplink_worker_start(self) -> None:
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").run_scheduled(
            self._start_auto_deeplink_worker,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    # -- Log display (throttled via QTimer, no trimming) --

    def _flush_log_buffer(self):
        """Called every 500ms by QTimer. Drains new lines from ProxyLogger."""
        if self._log_edit is None:
            return
        mgr = self._proxy_manager()
        new_lines = mgr.proxy_logger.drain()
        if not new_lines:
            return
        self._append_log_text_cache(new_lines)

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

    def _append_log_text_cache(self, lines) -> None:
        normalized_lines = [str(line or "") for line in lines]
        if not normalized_lines:
            return
        chunk = "\n".join(normalized_lines)
        if self._log_text_cache:
            self._log_text_cache = f"{self._log_text_cache}\n{chunk}"
        else:
            self._log_text_cache = chunk
        self._log_text_line_count += len(normalized_lines)

    def _append_log_line(self, msg: str):
        """Append a single line to the log."""
        self._request_log_line_append(str(msg or ""))

    def create_log_line_worker(self, request_id: int, *, message: str):
        return self._telegram_proxy.create_log_line_worker(
            request_id,
            message=message,
            parent=self,
        )

    def _request_log_line_append(self, message: str) -> None:
        if not message:
            return
        state = self._queued_worker_state("_log_line_state", "_log_line_runtime")
        state.start_or_queue(message, self._start_log_line_worker, state.append)

    def _start_log_line_worker(self, message: str) -> None:
        if self._cleanup_in_progress:
            return

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_log_line_worker_completed)
            worker.failed.connect(self._on_log_line_worker_failed)

        self._log_line_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_log_line_worker(
                request_id,
                message=message,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_log_line_worker_finished,
        )

    def _on_log_line_worker_completed(self, _request_id: int) -> None:
        return

    def _on_log_line_worker_failed(self, request_id: int, error: str) -> None:
        if not self._log_line_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._queued_worker_state("_log_line_state", "_log_line_runtime").has_pending():
            return
        log(f"Telegram Proxy log append failed: {error}", "WARNING")

    def _on_log_line_worker_finished(self, _worker) -> None:
        state = self._queued_worker_state("_log_line_state", "_log_line_runtime")
        state.schedule_next_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            start=self._start_log_line_worker,
            queue_item=state.append,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_log_line_worker_start(self, message: str) -> None:
        queued = str(message or "")
        state = self._queued_worker_state("_log_line_state", "_log_line_runtime")
        state.schedule_start(
            queued,
            QTimer.singleShot,
            self._start_log_line_worker,
            queue_item=state.append,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_scheduled_log_line_worker_start(self, message: str) -> None:
        self._queued_worker_state("_log_line_state", "_log_line_runtime").run_scheduled(
            str(message or ""),
            self._start_log_line_worker,
            lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    # -- Log tab buttons --

    def _on_copy_all_logs(self):
        if self._log_edit is None:
            return
        text = str(self.__dict__.get("_log_text_cache", "") or "")
        plan = self._telegram_proxy.copy_text(
            text,
            success_title="Скопировано",
            success_content=f"{int(self.__dict__.get('_log_text_line_count', 0) or 0)} строк",
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
        mgr = self._proxy_manager()
        path = mgr.proxy_logger.log_file_path
        self._start_open_log_file_worker(path)

    def create_open_log_file_worker(self, path: str):
        return self._telegram_proxy.create_open_log_file_worker(path=path, parent=self)

    @staticmethod
    def _mark_worker_request_id(worker, request_id: int):
        try:
            worker._request_id = int(request_id)
        except Exception:
            pass
        return worker

    def _start_open_log_file_worker(self, path: str) -> None:
        state = self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime")
        if state.is_busy():
            self._queue_open_log_file_path(str(path or ""))
            return

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_open_log_file_finished)
            worker.failed.connect(self._on_open_log_file_failed)

        self._open_log_file_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._mark_worker_request_id(
                self.create_open_log_file_worker(path),
                request_id,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_open_log_file_worker_finished,
        )

    def _queue_open_log_file_path(self, path: str) -> None:
        queued = str(path or "")
        self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime").append_unique(
            queued,
            key=lambda item: item,
        )

    def _on_open_log_file_finished(self, plan) -> None:
        if self._cleanup_in_progress:
            return
        log_line = str(getattr(plan, "log_line", "") or "")
        if log_line:
            self._append_log_line(log_line)

    def _on_open_log_file_failed(self, error: str) -> None:
        if self._cleanup_in_progress:
            return
        message = str(error or "").strip()
        if message:
            self._append_log_line(f"Failed to open log file: {message}")

    def _on_open_log_file_worker_finished(self, _worker) -> None:
        state = self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime")
        state.schedule_next_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            start=self._start_open_log_file_worker,
            queue_item=lambda value: state.append_unique(value, key=lambda item: item),
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_open_log_file_worker_start(self, path: str) -> None:
        queued = str(path or "")
        state = self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime")
        state.schedule_start(
            queued,
            QTimer.singleShot,
            self._start_open_log_file_worker,
            queue_item=lambda value: state.append_unique(value, key=lambda item: item),
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_scheduled_open_log_file_worker_start(self, path: str) -> None:
        self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime").run_scheduled(
            str(path or ""),
            self._start_open_log_file_worker,
            lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _on_clear_logs(self):
        if self._log_edit is not None:
            self._log_edit.clear()
        self._log_text_cache = ""
        self._log_text_line_count = 0

    # -- Handlers --

    def _on_toggle_proxy(self):
        mgr = self._proxy_manager()
        handle_toggle_proxy(
            manager=mgr,
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
            set_restarting=lambda value: setattr(self, "_restarting", value),
            stop_proxy=self._stop_proxy,
            start_proxy=self._start_proxy,
            request_proxy_enabled_save=lambda value: self._request_settings_save(
                "proxy_enabled",
                enabled=bool(value),
            ),
        )

    def _restart_if_running(self):
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_restart_stop_state", "_restart_stop_runtime").start_or_mark_pending(self._start_restart_stop_worker)

    def _start_restart_stop_worker(self) -> None:
        mgr = self._proxy_manager()
        restart_proxy_if_running(
            page=self,
            manager=mgr,
            restarting=bool(getattr(self, "_restarting", False)),
            set_restarting=lambda value: setattr(self, "_restarting", value),
            status_label=self._status_label,
            create_stop_runtime_worker=self._telegram_proxy.create_stop_runtime_worker,
            on_finished=self._on_restart_stop_worker_finished,
        )

    @pyqtSlot()
    def _finish_restart(self):
        if self._cleanup_in_progress:
            return
        if not self._restarting:
            return
        self._restarting = False
        self._start_proxy()

    def _on_restart_stop_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_restart_stop_runtime"), _worker):
            return
        self._worker_state("_restart_stop_state", "_restart_stop_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_restart_stop_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_restart_stop_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_restart_stop_state", "_restart_stop_runtime").schedule_start(
            QTimer.singleShot,
            self._restart_if_running,
        )

    def _run_scheduled_restart_stop_worker_start(self) -> None:
        self._worker_state("_restart_stop_state", "_restart_stop_runtime").run_scheduled(
            self._restart_if_running,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_upstream_restart(self):
        """Debounced proxy restart for SpinBox valueChanged signals."""
        self._upstream_restart_timer = schedule_upstream_restart(
            page=self,
            timer=self._upstream_restart_timer,
            restart_callback=self._restart_if_running,
            delay_ms=800,
        )

    def create_settings_save_worker(self, request_id: int, *, action: str, context_extra: dict | None = None, **kwargs):
        return self._telegram_proxy.create_settings_save_worker(
            request_id,
            action=action,
            context_extra=context_extra,
            parent=self,
            **kwargs,
        )

    def _request_settings_save(
        self,
        action: str,
        *,
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        preset_id: str = "",
        enabled: bool = False,
        value: object = "",
        restart: str = "",
        update_manual: bool = False,
    ) -> None:
        payload = {
            "action": str(action or ""),
            "host": str(host or ""),
            "port": int(port or 0),
            "user": str(user or ""),
            "password": str(password or ""),
            "enabled": bool(enabled),
            "value": value,
            "context_extra": {
                "restart": str(restart or ""),
                "update_manual": bool(update_manual),
            },
        }
        if preset_id:
            payload["preset_id"] = str(preset_id or "")
        state = self._queued_worker_state("_settings_save_state", "_settings_save_runtime")
        state.start_or_queue(payload, self._start_settings_save_worker, self._queue_settings_save_payload)

    def _queue_settings_save_payload(self, payload: dict) -> None:
        queued = dict(payload or {})
        action = str(queued.get("action") or "")
        self._queued_worker_state("_settings_save_state", "_settings_save_runtime").replace_by_key(
            queued,
            key=lambda pending: str(pending.get("action") or ""),
        )

    def _start_settings_save_worker(self, payload: dict) -> None:
        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_settings_save_finished)
            worker.failed.connect(self._on_settings_save_failed)

        self._settings_save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_settings_save_worker(
                request_id,
                action=str(payload.get("action") or ""),
                host=str(payload.get("host") or ""),
                port=int(payload.get("port") or 0),
                user=str(payload.get("user") or ""),
                password=str(payload.get("password") or ""),
                preset_id=str(payload.get("preset_id") or ""),
                enabled=bool(payload.get("enabled")),
                value=payload.get("value", ""),
                context_extra=dict(payload.get("context_extra") or {}),
            ),
            bind_worker=bind_worker,
            on_finished=self._on_settings_save_worker_finished,
        )

    def _on_settings_save_finished(self, request_id: int, _action: str, _result, context) -> None:
        if not self._settings_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        context = dict(context or {})
        restart = str(context.get("restart") or "")
        self._settings_save_restart_pending = merge_restart_request(
            getattr(self, "_settings_save_restart_pending", ""),
            restart,
        )
        if self._queued_worker_state("_settings_save_state", "_settings_save_runtime").has_pending():
            return
        if bool(context.get("update_manual")):
            self._update_manual_instructions()
        restart = str(getattr(self, "_settings_save_restart_pending", "") or "")
        self._settings_save_restart_pending = ""
        if restart == "schedule":
            self._schedule_upstream_restart()
        elif restart == "now":
            self._restart_if_running()

    def _on_settings_save_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if not self._settings_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._queued_worker_state("_settings_save_state", "_settings_save_runtime").has_pending():
            return
        self._settings_save_restart_pending = ""
        log(f"{self.__class__.__name__}: не удалось сохранить настройку Telegram Proxy ({action}): {error}", "WARNING")

    def _on_settings_save_worker_finished(self, _worker) -> None:
        state = self._queued_worker_state("_settings_save_state", "_settings_save_runtime")
        state.schedule_next_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            start=self._start_settings_save_worker,
            queue_item=self._queue_settings_save_payload,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_settings_save_worker_start(self, payload: dict) -> None:
        queued = dict(payload or {})
        state = self._queued_worker_state("_settings_save_state", "_settings_save_runtime")
        state.schedule_start(
            queued,
            QTimer.singleShot,
            self._start_settings_save_worker,
            queue_item=self._queue_settings_save_payload,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_scheduled_settings_save_worker_start(self, payload: dict) -> None:
        self._queued_worker_state("_settings_save_state", "_settings_save_runtime").run_scheduled(
            dict(payload or {}),
            self._start_settings_save_worker,
            lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    @pyqtSlot()
    def _start_proxy(self):
        self._request_proxy_start()

    def _request_proxy_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_proxy_start_state", "_proxy_start_runtime").start_or_mark_pending(self._start_proxy_worker)

    def _start_proxy_worker(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_proxy_start_state", "_proxy_start_runtime").pending = False
        mgr = self._proxy_manager()
        start_proxy_runtime(
            page=self,
            manager=mgr,
            starting=bool(getattr(self, "_starting", False)),
            running=bool(mgr.is_running),
            host=self._host_edit.text().strip() or "127.0.0.1",
            port=self._port_spin.value(),
            set_starting=lambda value: setattr(self, "_starting", value),
            btn_toggle=self._btn_toggle,
            status_label=self._status_label,
            append_log_line=self._append_log_line,
            create_start_worker=self._telegram_proxy.create_start_worker,
            mode=self._local_proxy_mode(),
            mtproxy_secret=self._ensure_mtproxy_secret_if_needed(),
            pool_size=self._local_pool_size(),
            buffer_kb=self._local_buffer_kb(),
            fake_tls_domain=self._local_fake_tls_domain(),
            proxy_protocol=self._local_proxy_protocol(),
            on_finished=self._on_proxy_start_worker_finished,
        )

    @pyqtSlot()
    def _finish_start(self):
        if self._cleanup_in_progress:
            return
        finish_proxy_start(
            start_ok=getattr(self, "_start_result", False),
            set_starting=lambda value: setattr(self, "_starting", value),
            btn_toggle=self._btn_toggle,
            check_relay_after_start=self._check_relay_after_start,
            on_status_changed=self._on_status_changed,
            request_proxy_enabled_save=lambda value: self._request_settings_save(
                "proxy_enabled",
                enabled=bool(value),
            ),
        )

    def _on_proxy_start_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_proxy_start_runtime"), _worker):
            return
        self._worker_state("_proxy_start_state", "_proxy_start_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_proxy_start_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_proxy_start_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        try:
            self._worker_state("_proxy_start_state", "_proxy_start_runtime").schedule_start(
                QTimer.singleShot,
                self._start_proxy_worker,
            )
        except Exception:
            self._run_scheduled_proxy_start_worker_start()

    def _run_scheduled_proxy_start_worker_start(self) -> None:
        self._worker_state("_proxy_start_state", "_proxy_start_runtime").run_scheduled(
            self._start_proxy_worker,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _check_relay_after_start(self):
        if self._cleanup_in_progress:
            return
        self._worker_state("_relay_check_state", "_relay_check_runtime").start_or_mark_pending(self._start_relay_check_worker)

    def _start_relay_check_worker(self) -> None:
        self._worker_state("_relay_check_state", "_relay_check_runtime").pending = False
        mgr = self._proxy_manager()
        self._on_status_changed(bool(mgr.is_running))
        start_relay_check(
            page=self,
            manager=mgr,
            current_generation=getattr(self, "_relay_check_gen", 0),
            set_generation=lambda value: setattr(self, "_relay_check_gen", value),
            status_label=self._status_label,
            set_relay_diag=lambda value: setattr(self, "_relay_diag", value),
            get_zapret_running=self._get_zapret_running,
            log_warning=lambda text: log(text, "WARNING"),
            create_relay_check_worker=self._telegram_proxy.create_relay_check_worker,
            on_finished=self._on_relay_check_worker_finished,
        )

    def _on_relay_check_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_relay_check_runtime"), _worker):
            return
        self._worker_state("_relay_check_state", "_relay_check_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_relay_check_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_relay_check_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        try:
            self._worker_state("_relay_check_state", "_relay_check_runtime").schedule_start(
                QTimer.singleShot,
                self._start_relay_check_worker,
            )
        except Exception:
            self._run_scheduled_relay_check_worker_start()

    def _run_scheduled_relay_check_worker_start(self) -> None:
        self._worker_state("_relay_check_state", "_relay_check_runtime").run_scheduled(
            self._start_relay_check_worker,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    @pyqtSlot()
    def _apply_relay_result(self):
        if self._cleanup_in_progress:
            return
        mgr = self._proxy_manager()
        apply_relay_result(
            manager=mgr,
            diag=getattr(self, "_relay_diag", {}),
            status_label=self._status_label,
            info_bar_cls=InfoBar,
            info_bar_position=InfoBarPosition,
            parent=self,
        )

    def _stop_proxy(self):
        self._request_proxy_stop()

    def _request_proxy_stop(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").start_or_mark_pending(self._start_proxy_stop_worker)

    def _start_proxy_stop_worker(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").pending = False
        mgr = self._proxy_manager()
        if not bool(getattr(mgr, "is_running", False)):
            return
        stop_proxy_runtime(
            page=self,
            manager=mgr,
            create_stop_runtime_worker=self._telegram_proxy.create_stop_runtime_worker,
            on_finished=self._on_proxy_stop_worker_finished,
        )

    @pyqtSlot()
    def _finish_stop_proxy(self):
        if self._cleanup_in_progress:
            return
        self._request_settings_save("proxy_enabled", enabled=False)

    def _on_proxy_stop_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_proxy_stop_runtime"), _worker):
            return
        self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_proxy_stop_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _schedule_proxy_stop_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        try:
            self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").schedule_start(
                QTimer.singleShot,
                self._start_proxy_stop_worker,
            )
        except Exception:
            self._run_scheduled_proxy_stop_worker_start()

    def _run_scheduled_proxy_stop_worker_start(self) -> None:
        self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").run_scheduled(
            self._start_proxy_stop_worker,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _on_status_changed(self, running: bool):
        mgr = self._proxy_manager()
        apply_status_changed(
            manager=mgr,
            running=bool(running),
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
            status_dot=self._status_dot,
            stats_label=self._stats_label,
            status_label=self._status_label,
            btn_toggle=self._btn_toggle,
            port_spin=self._port_spin,
            host_edit=self._host_edit,
            relay_check_gen=getattr(self, "_relay_check_gen", 0),
            set_speed_state=lambda prev_sent, prev_recv, up, down: (
                setattr(self, "_prev_bytes_sent", prev_sent),
                setattr(self, "_prev_bytes_received", prev_recv),
                setattr(self, "_speed_hist_up", up),
                setattr(self, "_speed_hist_down", down),
            ),
            set_generation=lambda value: setattr(self, "_relay_check_gen", value),
        )
        if self._stats_timer is not None:
            if running and self.isVisible() and not self._stats_timer.isActive():
                self._stats_timer.start(2000)
            elif not running:
                self._stats_timer.stop()

    def _emit_stats_if_visible(self):
        if self._cleanup_in_progress or not self.isVisible():
            return
        mgr = self._proxy_manager()
        if not mgr.is_running:
            if self._stats_timer is not None:
                self._stats_timer.stop()
            return
        self._apply_stats(mgr.stats)

    def _apply_stats(self, stats):
        if stats is None:
            return
        apply_stats_updated(
            stats=stats,
            prev_sent=getattr(self, '_prev_bytes_sent', 0),
            prev_recv=getattr(self, '_prev_bytes_received', 0),
            speed_hist_up=tuple(getattr(self, '_speed_hist_up', ()) or ()),
            speed_hist_down=tuple(getattr(self, '_speed_hist_down', ()) or ()),
            stats_label=self._stats_label,
            set_speed_state=lambda prev_sent, prev_recv, up, down: (
                setattr(self, "_prev_bytes_sent", prev_sent),
                setattr(self, "_prev_bytes_received", prev_recv),
                setattr(self, "_speed_hist_up", up),
                setattr(self, "_speed_hist_down", down),
            ),
        )

    def _on_port_changed(self, port: int):
        normalized = telegram_proxy_settings.normalize_port(port)
        if normalized != port:
            self._port_spin.blockSignals(True)
            self._port_spin.setValue(normalized)
            self._port_spin.blockSignals(False)
        self._update_manual_instructions()
        self._request_settings_save("port", port=normalized)

    def _on_host_changed(self):
        host = telegram_proxy_settings.normalize_host(self._host_edit.text().strip())
        self._host_edit.setText(host)
        self._update_manual_instructions()
        self._request_settings_save("host", host=host)

    def _local_proxy_mode(self) -> str:
        row = getattr(self, "_proxy_mode_row", None)
        if row is None:
            return "socks5"
        try:
            return telegram_proxy_settings.normalize_proxy_mode(row.currentData())
        except Exception:
            return "socks5"

    def _local_mtproxy_secret(self) -> str:
        edit = getattr(self, "_mtproxy_secret_edit", None)
        if edit is None:
            return ""
        return telegram_proxy_settings.normalize_secret(edit.text())

    def _ensure_mtproxy_secret_if_needed(self) -> str:
        if self._local_proxy_mode() != "mtproxy":
            return ""
        self._ensure_advanced_settings_built()
        secret = self._local_mtproxy_secret()
        if secret:
            return secret
        secret = telegram_proxy_settings.generate_mtproxy_secret()
        self._mtproxy_secret_edit.setText(secret)
        self._request_settings_save("mtproxy_secret", value=secret, restart="now")
        return secret

    def _local_fake_tls_domain(self) -> str:
        edit = getattr(self, "_fake_tls_domain_edit", None)
        if edit is not None:
            return telegram_proxy_settings.normalize_fake_tls_domain(edit.text())
        try:
            start_config = self._telegram_proxy.get_start_config()
            return str(getattr(start_config, "fake_tls_domain", "") or "")
        except Exception:
            return ""

    def _local_pool_size(self) -> int:
        spin = getattr(self, "_pool_size_spin", None)
        if spin is None:
            return 4
        return telegram_proxy_settings.normalize_pool_size(spin.value())

    def _local_buffer_kb(self) -> int:
        spin = getattr(self, "_buffer_kb_spin", None)
        if spin is None:
            return 256
        return telegram_proxy_settings.normalize_buffer_kb(spin.value())

    def _local_proxy_protocol(self) -> bool:
        toggle = getattr(self, "_proxy_protocol_toggle", None)
        return bool(toggle is not None and toggle.isChecked())

    def _normalized_dc_ip_text(self) -> str:
        edit = getattr(self, "_dc_ip_edit", None)
        if edit is None:
            return ""
        overrides = telegram_proxy_settings.parse_dc_endpoint_overrides(edit.text())
        text = ", ".join(f"{dc}:{ip}" for dc, ip in overrides.items())
        edit.setText(text)
        return text

    def _apply_advanced_settings_ui(self) -> None:
        advanced = bool(self._advanced_toggle.isChecked())
        if advanced:
            self._ensure_advanced_settings_built()
        if not self.__dict__.get("_advanced_settings_built", False):
            enable_setting_card_group_auto_height(self._settings_card)
            return
        self._advanced_card.setVisible(advanced)
        self._apply_local_proxy_mode_ui()
        self._apply_cloudflare_ui()
        self._apply_auto_advanced_section_visibility()
        enable_setting_card_group_auto_height(self._settings_card)
        enable_setting_card_group_auto_height(self._advanced_card)

    def _apply_auto_advanced_section_visibility(self) -> None:
        if not self.__dict__.get("_advanced_settings_built", False):
            return

        show_upstream = self._advanced_section_visible("upstream")
        self._upstream_toggle.setVisible(show_upstream)
        if show_upstream:
            self._apply_upstream_preset_ui(self._upstream_preset_row.combo.currentIndex())
        else:
            self._upstream_preset_row.setVisible(False)
            self._upstream_catalog_hint.setVisible(False)
            self._upstream_manual_widget.setVisible(False)
            self._mtproxy_action_widget.setVisible(False)
            self._upstream_mode_toggle.setVisible(False)

        show_cloudflare = self._advanced_section_visible("cloudflare")
        self._cloudflare_toggle.setVisible(show_cloudflare)
        self._cloudflare_worker_toggle.setVisible(show_cloudflare)
        if show_cloudflare:
            self._apply_cloudflare_ui()
        else:
            self._cloudflare_domains_row.setVisible(False)
            self._cloudflare_worker_domains_row.setVisible(False)

        self._dc_ip_row.setVisible(self._advanced_section_visible("dc_ip"))

        show_performance = self._advanced_section_visible("performance")
        self._performance_label.setVisible(show_performance)
        performance_row = self._pool_size_spin.parentWidget()
        if performance_row is not None:
            performance_row.setVisible(show_performance)

        enable_setting_card_group_auto_height(self._advanced_card)

    def _apply_local_proxy_mode_ui(self) -> None:
        is_mtproxy = self._local_proxy_mode() == "mtproxy"
        if is_mtproxy:
            self._ensure_advanced_settings_built()
        if is_mtproxy and not self._advanced_toggle.isChecked():
            self._advanced_toggle.setChecked(True)
        if not self.__dict__.get("_advanced_settings_built", False):
            self._update_manual_instructions()
            enable_setting_card_group_auto_height(self._settings_card)
            return
        self._mtproxy_secret_row.setVisible(is_mtproxy)
        self._fake_tls_domain_row.setVisible(is_mtproxy)
        self._proxy_protocol_toggle.setVisible(is_mtproxy)
        self._update_manual_instructions()
        enable_setting_card_group_auto_height(self._settings_card)
        enable_setting_card_group_auto_height(self._advanced_card)

    def _apply_cloudflare_ui(self) -> None:
        if not self.__dict__.get("_advanced_settings_built", False):
            return
        cloudflare_enabled = bool(self._cloudflare_toggle.isChecked())
        worker_enabled = bool(self._cloudflare_worker_toggle.isChecked())
        self._cloudflare_domains_row.setVisible(cloudflare_enabled)
        self._cloudflare_worker_domains_row.setVisible(worker_enabled)
        self._cloudflare_worker_domains_edit.setEnabled(worker_enabled)
        enable_setting_card_group_auto_height(self._advanced_card)

    def _on_advanced_toggled(self, _checked: bool):
        if _checked:
            self._advanced_auto_sections = set()
            self._ensure_advanced_settings_built()
            self._apply_advanced_settings_state(self._current_settings_state)
        self._apply_advanced_settings_ui()

    def _on_proxy_mode_changed(self, _index: int):
        mode = self._local_proxy_mode()
        self._apply_local_proxy_mode_ui()
        if mode == "mtproxy":
            self._ensure_mtproxy_secret_if_needed()
        self._request_settings_save("proxy_mode", value=mode, restart="now", update_manual=True)

    def _on_generate_mtproxy_secret(self):
        secret = telegram_proxy_settings.generate_mtproxy_secret()
        self._mtproxy_secret_edit.setText(secret)
        self._request_settings_save("mtproxy_secret", value=secret, restart="now")

    def _on_mtproxy_secret_changed(self):
        secret = telegram_proxy_settings.normalize_secret(self._mtproxy_secret_edit.text())
        self._mtproxy_secret_edit.setText(secret)
        self._request_settings_save("mtproxy_secret", value=secret, restart="now")

    def _on_fake_tls_domain_changed(self):
        domain = telegram_proxy_settings.normalize_fake_tls_domain(self._fake_tls_domain_edit.text())
        self._fake_tls_domain_edit.setText(domain)
        self._request_settings_save("fake_tls_domain", value=domain, restart="now", update_manual=True)

    def _on_proxy_protocol_changed(self, checked: bool):
        self._request_settings_save("proxy_protocol", enabled=bool(checked), restart="now")

    def _on_dc_ip_changed(self):
        self._request_settings_save("dc_ip", value=self._normalized_dc_ip_text(), restart="now")

    def _on_pool_size_changed(self, value: int):
        normalized = telegram_proxy_settings.normalize_pool_size(value)
        if normalized != value:
            self._pool_size_spin.blockSignals(True)
            self._pool_size_spin.setValue(normalized)
            self._pool_size_spin.blockSignals(False)
        self._request_settings_save("pool_size", value=normalized, restart="schedule")

    def _on_buffer_kb_changed(self, value: int):
        normalized = telegram_proxy_settings.normalize_buffer_kb(value)
        if normalized != value:
            self._buffer_kb_spin.blockSignals(True)
            self._buffer_kb_spin.setValue(normalized)
            self._buffer_kb_spin.blockSignals(False)
        self._request_settings_save("buffer_kb", value=normalized, restart="schedule")

    def _cloudflare_domains_text(self, edit) -> str:
        domains = telegram_proxy_settings.normalize_domain_list(edit.text())
        edit.setText(", ".join(domains))
        return ", ".join(domains)

    def _on_cloudflare_changed(self, checked: bool):
        self._apply_cloudflare_ui()
        self._request_settings_save("cloudflare_enabled", enabled=bool(checked), restart="now")

    def _on_cloudflare_domains_changed(self):
        self._request_settings_save(
            "cloudflare_domains",
            value=self._cloudflare_domains_text(self._cloudflare_domains_edit),
            restart="now",
        )

    def _on_cloudflare_worker_changed(self, checked: bool):
        self._apply_cloudflare_ui()
        self._request_settings_save("cloudflare_worker_enabled", enabled=bool(checked), restart="now")

    def _on_cloudflare_worker_domains_changed(self):
        self._request_settings_save(
            "cloudflare_worker_domains",
            value=self._cloudflare_domains_text(self._cloudflare_worker_domains_edit),
            restart="now",
        )

    def _on_test_cloudflare(self):
        domains = self._cloudflare_domains_text(self._cloudflare_domains_edit)
        self._start_cloudflare_check("domain", domains)

    def _on_test_cloudflare_worker(self):
        domains = self._cloudflare_domains_text(self._cloudflare_worker_domains_edit)
        if not domains:
            self._show_cloudflare_message(
                title="Worker не указан",
                content="Введите домен Cloudflare Worker, например name.workers.dev.",
                success=False,
            )
            return
        self._start_cloudflare_check("worker", domains)

    def _on_copy_cloudflare_dns(self):
        text = self._telegram_proxy.get_cloudflare_dns_records_text()
        plan = self._telegram_proxy.copy_text(
            text,
            success_title="Скопировано",
            success_content="DNS-записи Cloudflare",
            success_log="Copied Cloudflare DNS records",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)
        if plan.ok:
            self._show_cloudflare_message(plan.info_title, plan.info_content, success=True)

    def _on_copy_cloudflare_worker_code(self):
        text = self._telegram_proxy.get_cloudflare_worker_code()
        plan = self._telegram_proxy.copy_text(
            text,
            success_title="Скопировано",
            success_content="Код Cloudflare Worker",
            success_log="Copied Cloudflare Worker code",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)
        if plan.ok:
            self._show_cloudflare_message(plan.info_title, plan.info_content, success=True)

    def _on_copy_fake_tls_nginx_config(self):
        text = self._telegram_proxy.get_fake_tls_nginx_config(
            fake_tls_domain=self._local_fake_tls_domain(),
            upstream_host=self._host_edit.text().strip(),
            upstream_port=self._port_spin.value(),
        )
        plan = self._telegram_proxy.copy_text(
            text,
            success_title="Скопировано",
            success_content="Конфиг Nginx для Fake TLS",
            success_log="Copied Fake TLS Nginx config",
        )
        if plan.log_line:
            self._append_log_line(plan.log_line)
        if plan.ok:
            self._show_cloudflare_message(plan.info_title, plan.info_content, success=True)

    def create_cloudflare_check_worker(self, request_id: int, *, kind: str, domains):
        return self._telegram_proxy.create_cloudflare_check_worker(
            request_id,
            kind=kind,
            domains=domains,
            parent=self,
        )

    def _start_cloudflare_check(self, kind: str, domains: str) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        state = self._worker_state("_cloudflare_check_state", "_cloudflare_check_runtime")
        normalized_kind = str(kind or "domain").strip().lower()
        if state.is_busy():
            self._show_cloudflare_message(
                "Проверка уже идёт",
                "Дождитесь результата текущей проверки Cloudflare.",
                success=False,
            )
            return
        self._cloudflare_check_kind = normalized_kind
        self._set_cloudflare_check_buttons_enabled(False)
        self._append_log_line(
            "Проверяем Cloudflare Worker..."
            if normalized_kind == "worker"
            else "Проверяем Cloudflare-домен..."
        )

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_cloudflare_check_finished)
            worker.failed.connect(self._on_cloudflare_check_failed)

        self._cloudflare_check_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_cloudflare_check_worker(
                request_id,
                kind=normalized_kind,
                domains=domains,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_cloudflare_check_worker_finished,
        )

    def _on_cloudflare_check_finished(self, request_id: int, result) -> None:
        if not self._cloudflare_check_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        summary = result.summary() if hasattr(result, "summary") else str(result or "")
        self._append_log_line(f"Проверка Cloudflare: {summary}")
        for entry in tuple(getattr(result, "entries", ()) or ()):
            status = "OK" if getattr(entry, "ok", False) else "FAIL"
            error = str(getattr(entry, "error", "") or "")
            suffix = f" - {error}" if error else ""
            self._append_log_line(f"Cloudflare {status}: {getattr(entry, 'host', '')}{suffix}")

        if bool(getattr(result, "ok", False)):
            self._show_cloudflare_message("Cloudflare отвечает", summary, success=True)
        else:
            self._show_cloudflare_message("Cloudflare не отвечает", summary, success=False)

    def _on_cloudflare_check_failed(self, request_id: int, error: str) -> None:
        if not self._cloudflare_check_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        message = str(error or "").strip() or "Не удалось проверить Cloudflare."
        self._append_log_line(f"Ошибка проверки Cloudflare: {message}")
        self._show_cloudflare_message("Ошибка проверки", message, success=False)

    def _on_cloudflare_check_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_cloudflare_check_runtime"), _worker):
            return
        self._set_cloudflare_check_buttons_enabled(True)
        self._worker_state("_cloudflare_check_state", "_cloudflare_check_runtime").reset()

    def _set_cloudflare_check_buttons_enabled(self, enabled: bool) -> None:
        for button in (
            getattr(self, "_cloudflare_test_btn", None),
            getattr(self, "_cloudflare_worker_test_btn", None),
        ):
            if button is not None:
                button.setEnabled(bool(enabled))
        if enabled:
            self._apply_ui_texts()
            return
        if getattr(self, "_cloudflare_check_kind", "") == "worker":
            if getattr(self, "_cloudflare_worker_test_btn", None) is not None:
                self._cloudflare_worker_test_btn.setText("Проверяем...")
        elif getattr(self, "_cloudflare_test_btn", None) is not None:
            self._cloudflare_test_btn.setText("Проверяем...")

    def _show_cloudflare_message(self, title: str, content: str, *, success: bool) -> None:
        if InfoBar is None:
            return
        try:
            if success:
                InfoBar.success(
                    title=str(title or ""),
                    content=str(content or ""),
                    parent=self,
                    duration=2500,
                    position=InfoBarPosition.TOP,
                )
            else:
                InfoBar.warning(
                    title=str(title or ""),
                    content=str(content or ""),
                    parent=self,
                    duration=3500,
                    position=InfoBarPosition.TOP,
                )
        except Exception:
            pass

    # -- Upstream proxy handlers --

    def _on_upstream_changed(self, checked: bool):
        handle_upstream_toggle(
            checked=checked,
            request_upstream_enabled=lambda value: self._request_settings_save(
                "upstream_enabled",
                enabled=bool(value),
                restart="now",
            ),
            apply_upstream_preset_ui=self._apply_upstream_preset_ui,
            current_index=self._upstream_preset_row.combo.currentIndex(),
            upstream_catalog=self._upstream_catalog,
            request_upstream_preset_save=lambda preset_id: self._request_settings_save(
                "upstream_preset",
                preset_id=preset_id,
                restart="now",
            ),
        )

    def _on_upstream_preset_changed(self, index: int):
        """Handle upstream server selection."""
        self._current_mtproxy_preset_id = handle_upstream_preset_changed(
            index=index,
            upstream_catalog=self._upstream_catalog,
            apply_upstream_preset_ui=self._apply_upstream_preset_ui,
            upstream_host_edit=self._upstream_host_edit,
            upstream_port_spin=self._upstream_port_spin,
            upstream_user_edit=self._upstream_user_edit,
            upstream_pass_edit=self._upstream_pass_edit,
            request_upstream_preset_save=lambda preset_id: self._request_settings_save(
                "upstream_preset",
                preset_id=preset_id,
                restart="now",
            ),
            request_manual_upstream_save=lambda host, port, user, password: self._request_settings_save(
                "manual_upstream",
                host=host,
                port=port,
                user=user,
                password=password,
                restart="now",
            ),
        )

    def _on_upstream_host_changed(self):
        self._request_settings_save(
            "manual_upstream",
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="now",
        )

    def _on_upstream_port_changed(self, port: int):
        self._request_settings_save(
            "manual_upstream",
            host=self._upstream_host_edit.text(),
            port=port,
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="schedule",
        )

    def _on_upstream_user_changed(self):
        self._request_settings_save(
            "manual_upstream",
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="now",
        )

    def _on_upstream_pass_changed(self):
        self._request_settings_save(
            "manual_upstream",
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="now",
        )

    def _on_upstream_mode_changed(self, checked: bool):
        self._request_settings_save("upstream_mode", enabled=bool(checked), restart="now")

    def _on_open_mtproxy(self):
        """Open MTProxy deep link in browser."""
        preset_id = getattr(self, '_current_mtproxy_preset_id', '')
        link = telegram_proxy_settings.get_upstream_mtproxy_link(preset_id)
        if not link:
            return
        self._start_external_link_worker(
            link,
            success_log="Opened MTProxy link",
            error_prefix="Failed to open MTProxy link",
        )

    def _update_manual_instructions(self):
        """Update manual instructions label with current host/port."""
        label = getattr(self, "_manual_host_port_label", None)
        if label is None:
            return
        label.setText(
            telegram_proxy_settings.build_manual_instruction_text(
                self._host_edit.text().strip(),
                self._port_spin.value(),
                mode=self._local_proxy_mode(),
            )
        )

    def _on_open_in_telegram(self):
        """Open Telegram deep link to auto-configure Telegram."""
        url = telegram_proxy_settings.build_proxy_url(
            self._host_edit.text().strip(),
            self._port_spin.value(),
            mode=self._local_proxy_mode(),
            mtproxy_secret=self._ensure_mtproxy_secret_if_needed(),
            fake_tls_domain=self._local_fake_tls_domain(),
        )
        self._start_external_link_worker(
            url,
            success_log=f"Opened deep link: {url}",
            error_prefix="Failed to open link",
        )

    def create_external_link_worker(self, *, url: str, success_log: str, error_prefix: str):
        return self._telegram_proxy.create_external_link_worker(
            url=url,
            success_log=success_log,
            error_prefix=error_prefix,
            parent=self,
        )

    def _start_external_link_worker(self, url: str, *, success_log: str, error_prefix: str) -> None:
        state = self._queued_worker_state("_external_link_state", "_external_link_runtime")
        if state.is_busy():
            self._queue_external_link(
                {
                    "url": str(url or ""),
                    "success_log": str(success_log or ""),
                    "error_prefix": str(error_prefix or ""),
                }
            )
            return

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_external_link_finished)
            worker.failed.connect(self._on_external_link_failed)

        self._external_link_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._mark_worker_request_id(
                self.create_external_link_worker(
                    url=url,
                    success_log=success_log,
                    error_prefix=error_prefix,
                ),
                request_id,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_external_link_worker_finished,
        )

    def _queue_external_link(self, payload: dict[str, str]) -> None:
        queued = {
            "url": str((payload or {}).get("url") or ""),
            "success_log": str((payload or {}).get("success_log") or ""),
            "error_prefix": str((payload or {}).get("error_prefix") or ""),
        }
        self._queued_worker_state("_external_link_state", "_external_link_runtime").append_unique(
            queued,
            key=lambda item: str(item.get("url") or ""),
        )

    def _on_external_link_finished(self, plan) -> None:
        if self._cleanup_in_progress:
            return
        log_line = str(getattr(plan, "log_line", "") or "")
        if log_line:
            self._append_log_line(log_line)

    def _on_external_link_failed(self, error: str) -> None:
        if self._cleanup_in_progress:
            return
        message = str(error or "").strip()
        if message:
            self._append_log_line(f"Failed to open link: {message}")

    def _on_external_link_worker_finished(self, _worker) -> None:
        state = self._queued_worker_state("_external_link_state", "_external_link_runtime")
        state.schedule_next_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            start=self._run_external_link_payload,
            queue_item=self._queue_external_link,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_external_link_worker_start(self, payload: dict) -> None:
        queued = {
            "url": str((payload or {}).get("url") or ""),
            "success_log": str((payload or {}).get("success_log") or ""),
            "error_prefix": str((payload or {}).get("error_prefix") or ""),
        }
        state = self._queued_worker_state("_external_link_state", "_external_link_runtime")
        state.schedule_start(
            queued,
            QTimer.singleShot,
            self._run_external_link_payload,
            queue_item=self._queue_external_link,
            is_cleanup_in_progress=lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_scheduled_external_link_worker_start(self, payload: dict) -> None:
        self._queued_worker_state("_external_link_state", "_external_link_runtime").run_scheduled(
            dict(payload or {}),
            self._run_external_link_payload,
            lambda: self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_external_link_payload(self, payload: dict) -> None:
        self._start_external_link_worker(
            str((payload or {}).get("url") or ""),
            success_log=str((payload or {}).get("success_log") or ""),
            error_prefix=str((payload or {}).get("error_prefix") or ""),
        )

    def _on_copy_link(self):
        """Copy proxy deep link to clipboard."""
        url = telegram_proxy_settings.build_proxy_url(
            self._host_edit.text().strip(),
            self._port_spin.value(),
            mode=self._local_proxy_mode(),
            mtproxy_secret=self._ensure_mtproxy_secret_if_needed(),
            fake_tls_domain=self._local_fake_tls_domain(),
        )
        plan = self._telegram_proxy.copy_text(
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
        """Проверяет и добавляет Telegram-записи в hosts через worker."""
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").start_or_mark_pending(self._start_ensure_hosts_worker)

    def _start_ensure_hosts_worker(self) -> None:
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").pending = False
        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_telegram_hosts_ensured)

        self._ensure_hosts_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._telegram_proxy.create_ensure_hosts_worker(
                request_id,
                parent=self,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_ensure_hosts_worker_finished,
        )

    def _on_telegram_hosts_ensured(self, request_id: int, plan):
        if not self._ensure_hosts_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if plan is None:
            return
        if not plan.ok and plan.log_line:
            log(plan.log_line, "WARNING")

    def _on_ensure_hosts_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_ensure_hosts_runtime"), _worker):
            return
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").schedule_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            schedule_next=self._schedule_ensure_hosts_worker_start,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return False
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _schedule_ensure_hosts_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").schedule_start(
            QTimer.singleShot,
            self._start_ensure_hosts_worker,
        )

    def _run_scheduled_ensure_hosts_worker_start(self) -> None:
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").run_scheduled(
            self._start_ensure_hosts_worker,
            cleanup_in_progress=self._cleanup_in_progress,
        )

    def showEvent(self, event):
        started_at = time.perf_counter()
        super().showEvent(event)
        self._sync_log_timer()
        if self._stats_timer is not None and self._proxy_manager().is_running and not self._stats_timer.isActive():
            self._stats_timer.start(2000)
            self._emit_stats_if_visible()
        self._log_ui_timing("telegram_proxy_ui.show_event.total", started_at)

    @staticmethod
    def _log_ui_timing(label: str, started_at: float) -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass

    def hideEvent(self, event):
        if self._log_timer is not None:
            self._log_timer.stop()
        if self._stats_timer is not None:
            self._stats_timer.stop()
        super().hideEvent(event)

    def cleanup(self):
        """Called on app exit."""
        self._cleanup_in_progress = True
        self._relay_check_gen = getattr(self, '_relay_check_gen', 0) + 1
        if self._log_timer is not None:
            self._log_timer.stop()
        if self._stats_timer is not None:
            self._stats_timer.stop()
            self._stats_timer.deleteLater()
            self._stats_timer = None
        if self._diag_poll_timer is not None:
            self._diag_poll_timer.stop()
            self._diag_poll_timer.deleteLater()
            self._diag_poll_timer = None
        self._diag_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy diagnostics worker",
        )
        self._diag_runtime.cancel()
        self._ensure_hosts_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy hosts worker",
        )
        self._ensure_hosts_runtime.cancel()
        self._worker_state("_ensure_hosts_state", "_ensure_hosts_runtime").reset()
        self._initial_state_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy initial state worker",
        )
        self._initial_state_runtime.cancel()
        self._auto_deeplink_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy auto deeplink worker",
        )
        self._auto_deeplink_runtime.cancel()
        self._worker_state("_auto_deeplink_state", "_auto_deeplink_runtime").reset()
        self._log_line_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy log line worker",
        )
        self._log_line_runtime.cancel()
        self._open_log_file_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy open log file worker",
        )
        self._open_log_file_runtime.cancel()
        self._queued_worker_state("_open_log_file_state", "_open_log_file_runtime").reset()
        self._external_link_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy external link worker",
        )
        self._external_link_runtime.cancel()
        self._queued_worker_state("_external_link_state", "_external_link_runtime").reset()
        self._settings_save_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy settings save worker",
        )
        self._settings_save_runtime.cancel()
        self._proxy_start_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy start worker",
        )
        self._proxy_start_runtime.cancel()
        self._worker_state("_proxy_start_state", "_proxy_start_runtime").reset()
        self._proxy_stop_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy stop worker",
        )
        self._proxy_stop_runtime.cancel()
        self._worker_state("_proxy_stop_state", "_proxy_stop_runtime").reset()
        self._restart_stop_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy restart stop worker",
        )
        self._restart_stop_runtime.cancel()
        self._worker_state("_restart_stop_state", "_restart_stop_runtime").reset()
        self._relay_check_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy relay check worker",
        )
        self._relay_check_runtime.cancel()
        self._worker_state("_relay_check_state", "_relay_check_runtime").reset()
        self._cloudflare_check_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy cloudflare check worker",
        )
        self._cloudflare_check_runtime.cancel()
        self._worker_state("_cloudflare_check_state", "_cloudflare_check_runtime").reset()
        if self._upstream_restart_timer is not None:
            self._upstream_restart_timer.stop()
            self._upstream_restart_timer.deleteLater()
            self._upstream_restart_timer = None
        self._queued_worker_state("_log_line_state", "_log_line_runtime").reset()
        self._queued_worker_state("_settings_save_state", "_settings_save_runtime").reset()
        self._settings_save_restart_pending = ""
        mgr = self._proxy_manager()
        mgr.cleanup()
