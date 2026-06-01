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
from telegram_proxy.ui.upstream_workflow import (
    handle_upstream_preset_changed,
    handle_upstream_toggle,
    schedule_upstream_restart,
)
from telegram_proxy.ui.settings_save_flow import merge_restart_request
from telegram_proxy.ui.settings_build import (
    build_telegram_proxy_settings_panel,
)
from ui.fluent_widgets import (
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from log.log import log

import telegram_proxy.ui.page_runtime as telegram_proxy_page_runtime
import telegram_proxy.settings as telegram_proxy_settings
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
            "Маршрутизация трафика Telegram через WebSocket для обхода ЗАМЕДЛЕНИЯ (не поддерживает полный блок) по IP",
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
        self._proxy_stop_runtime = OneShotWorkerRuntime()
        self._restart_stop_runtime = OneShotWorkerRuntime()
        self._relay_check_runtime = OneShotWorkerRuntime()
        self._relay_check_pending = False
        self._relay_check_start_scheduled = False
        self._ensure_hosts_runtime = OneShotWorkerRuntime()
        self._ensure_hosts_pending = False
        self._ensure_hosts_start_scheduled = False
        self._settings_save_runtime = OneShotWorkerRuntime()
        self._open_log_file_runtime = OneShotWorkerRuntime()
        self._open_log_file_pending: list[str] = []
        self._open_log_file_start_scheduled = False
        self._external_link_runtime = OneShotWorkerRuntime()
        self._external_link_pending: list[dict[str, str]] = []
        self._external_link_start_scheduled = False
        self._log_line_runtime = OneShotWorkerRuntime()
        self._log_line_pending: list[str] = []
        self._log_line_start_scheduled = False
        self._auto_deeplink_runtime = OneShotWorkerRuntime()
        self._settings_save_pending: list[dict[str, object]] = []
        self._settings_save_start_scheduled = False
        self._settings_save_restart_pending = ""
        self._initial_state_runtime = OneShotWorkerRuntime()
        self._initial_state_load_started_at = 0.0
        self._relay_check_gen = 0
        self._cleanup_in_progress = False
        self._runtime_initialized = False
        self._built_panel_indexes: set[int] = set()
        self._initial_state = telegram_proxy_settings.TelegramProxyPageInitialStatePlan(
            upstream_catalog=telegram_proxy_settings.UpstreamCatalog(),
            settings=telegram_proxy_settings.default_state(),
        )
        self._btn_copy_logs = None
        self._btn_open_log_file = None
        self._btn_clear_logs = None
        self._log_edit = None
        self._diag_desc_label = None
        self._btn_run_diag = None
        self._btn_copy_diag = None
        self._diag_edit = None
        self._setup_ui()
        self._request_initial_state_load()
        self._after_ui_built()
        # Запуск Telegram Proxy живёт в общем старте приложения,
        # поэтому страница не поднимает его сама.

    def _proxy_manager(self):
        return self._telegram_proxy.get_proxy_manager()

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

    def _setup_ui(self):
        started_at = time.perf_counter()
        shell = build_telegram_proxy_shell(
            segmented_widget_cls=SegmentedWidget,
            parent=self,
            on_switch_tab=self._switch_tab,
        )
        self._pivot = shell.pivot
        self._stacked = shell.stacked

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
            upstream_catalog=self._initial_state.upstream_catalog,
        )
        self._status_card = widgets.status_card
        self._status_dot = widgets.status_dot
        self._status_label = widgets.status_label
        self._btn_toggle = widgets.btn_toggle
        self._stats_label = widgets.stats_label
        self._setup_section_label = widgets.setup_section_label
        self._setup_desc_label = widgets.setup_desc_label
        self._setup_card = widgets.setup_card
        self._setup_open_btn = widgets.setup_open_btn
        self._setup_copy_btn = widgets.setup_copy_btn
        self._settings_card = widgets.settings_card
        self._settings_host_row = widgets.settings_host_row
        self._host_label = widgets.host_label
        self._host_edit = widgets.host_edit
        self._port_label = widgets.port_label
        self._port_spin = widgets.port_spin
        self._auto_deeplink_toggle = widgets.auto_deeplink_toggle
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
        self._current_mtproxy_link = ""
        self._upstream_mode_toggle = widgets.upstream_mode_toggle
        self._manual_section_label = widgets.manual_section_label
        self._instructions_card = widgets.instructions_card
        self._instr1_label = widgets.instr1_label
        self._instr2_label = widgets.instr2_label
        self._manual_host_port_label = widgets.manual_host_port_label

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
            upstream_card=getattr(self, "_upstream_card", None),
            manual_section_label=getattr(self, "_manual_section_label", None),
            setup_desc_label=getattr(self, "_setup_desc_label", None),
            host_label=getattr(self, "_host_label", None),
            port_label=getattr(self, "_port_label", None),
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
            btn_copy_logs=getattr(self, "_btn_copy_logs", None),
            btn_open_log_file=getattr(self, "_btn_open_log_file", None),
            btn_clear_logs=getattr(self, "_btn_clear_logs", None),
            btn_copy_diag=getattr(self, "_btn_copy_diag", None),
            btn_run_diag=getattr(self, "_btn_run_diag", None),
            host_edit=getattr(self, "_host_edit", None),
            upstream_host_edit=getattr(self, "_upstream_host_edit", None),
            upstream_user_edit=getattr(self, "_upstream_user_edit", None),
            upstream_pass_edit=getattr(self, "_upstream_pass_edit", None),
            log_edit=getattr(self, "_log_edit", None),
            diag_edit=getattr(self, "_diag_edit", None),
            auto_deeplink_toggle=getattr(self, "_auto_deeplink_toggle", None),
            upstream_toggle=getattr(self, "_upstream_toggle", None),
            upstream_preset_row=getattr(self, "_upstream_preset_row", None),
            upstream_catalog_hint=getattr(self, "_upstream_catalog_hint", None),
            upstream_mode_toggle=getattr(self, "_upstream_mode_toggle", None),
            update_manual_instructions_callback=self._update_manual_instructions,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._apply_ui_texts()

    def _on_copy_diag(self):
        text = self._diag_edit.toPlainText()
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
        self._current_mtproxy_link = apply_upstream_preset_ui(
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
        combo = self._upstream_preset_row.combo
        combo.blockSignals(True)
        try:
            combo.clear()
            for text, data in upstream_catalog.items():
                combo.addItem(text, userData=data)
        finally:
            combo.blockSignals(False)

    def _connect_signals(self):
        mgr = self._proxy_manager()
        mgr.status_changed.connect(self._on_status_changed)

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

    def _apply_initial_settings_state(self, state: telegram_proxy_settings.TelegramProxySettingsState) -> None:
        started_at = time.perf_counter()
        self._port_spin.blockSignals(True)
        self._port_spin.setValue(state.port)
        self._port_spin.blockSignals(False)

        self._host_edit.setText(state.host)
        self._update_manual_instructions()

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
        self._log_ui_timing("telegram_proxy_ui.settings.apply", started_at)

    def _try_auto_deeplink(self):
        """Open tg:// deep link automatically on first start."""
        self._request_auto_deeplink_check()

    def create_auto_deeplink_worker(self, request_id: int):
        return self._telegram_proxy.create_auto_deeplink_worker(request_id, parent=self)

    def _request_auto_deeplink_check(self) -> None:
        if self._auto_deeplink_runtime.is_running():
            return

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_auto_deeplink_checked)
            worker.failed.connect(self._on_auto_deeplink_failed)

        self._auto_deeplink_runtime.start_qthread_worker(
            worker_factory=self.create_auto_deeplink_worker,
            bind_worker=bind_worker,
        )

    def _on_auto_deeplink_checked(self, request_id: int, should_open: bool) -> None:
        if not self._auto_deeplink_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
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
        log(f"Telegram Proxy auto deeplink check failed: {error}", "WARNING")

    # -- Log display (throttled via QTimer, no trimming) --

    def _flush_log_buffer(self):
        """Called every 500ms by QTimer. Drains new lines from ProxyLogger."""
        if self._log_edit is None:
            return
        mgr = self._proxy_manager()
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
        if self._log_line_runtime.is_running() or self.__dict__.get("_log_line_start_scheduled", False):
            self._log_line_pending.append(message)
            return

        self._start_log_line_worker(message)

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
        log(f"Telegram Proxy log append failed: {error}", "WARNING")

    def _on_log_line_worker_finished(self, _worker) -> None:
        if self._log_line_pending and not self._cleanup_in_progress:
            pending = self._log_line_pending.pop(0)
            self._schedule_log_line_worker_start(pending)

    def _schedule_log_line_worker_start(self, message: str) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = str(message or "")
        if self.__dict__.get("_log_line_start_scheduled", False):
            self._log_line_pending.append(queued)
            return
        self._log_line_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_log_line_worker_start(value))

    def _run_scheduled_log_line_worker_start(self, message: str) -> None:
        self._log_line_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_log_line_worker(message)

    # -- Log tab buttons --

    def _on_copy_all_logs(self):
        if self._log_edit is None:
            return
        text = self._log_edit.toPlainText()
        plan = self._telegram_proxy.copy_text(
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
        mgr = self._proxy_manager()
        path = mgr.proxy_logger.log_file_path
        self._start_open_log_file_worker(path)

    def create_open_log_file_worker(self, path: str):
        return self._telegram_proxy.create_open_log_file_worker(path=path, parent=self)

    def _start_open_log_file_worker(self, path: str) -> None:
        if (
            self._open_log_file_runtime.is_running()
            or self.__dict__.get("_open_log_file_start_scheduled", False)
        ):
            self.__dict__.setdefault("_open_log_file_pending", []).append(str(path or ""))
            return

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_open_log_file_finished)
            worker.failed.connect(self._on_open_log_file_failed)

        self._open_log_file_runtime.start_qthread_worker(
            worker_factory=lambda _request_id: self.create_open_log_file_worker(path),
            bind_worker=bind_worker,
            on_finished=self._on_open_log_file_worker_finished,
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
        pending_paths = self.__dict__.setdefault("_open_log_file_pending", [])
        pending = pending_paths.pop(0) if pending_paths else ""
        if pending and not self._cleanup_in_progress:
            self._schedule_open_log_file_worker_start(pending)

    def _schedule_open_log_file_worker_start(self, path: str) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = str(path or "")
        if self.__dict__.get("_open_log_file_start_scheduled", False):
            self.__dict__.setdefault("_open_log_file_pending", []).append(queued)
            return
        self._open_log_file_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_open_log_file_worker_start(value))

    def _run_scheduled_open_log_file_worker_start(self, path: str) -> None:
        self._open_log_file_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_open_log_file_worker(path)

    def _on_clear_logs(self):
        if self._log_edit is not None:
            self._log_edit.clear()

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
        mgr = self._proxy_manager()
        restart_proxy_if_running(
            page=self,
            manager=mgr,
            restarting=bool(getattr(self, "_restarting", False)),
            set_restarting=lambda value: setattr(self, "_restarting", value),
            status_label=self._status_label,
            create_stop_runtime_worker=self._telegram_proxy.create_stop_runtime_worker,
        )

    @pyqtSlot()
    def _finish_restart(self):
        if self._cleanup_in_progress:
            return
        if not self._restarting:
            return
        self._restarting = False
        self._start_proxy()

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
        enabled: bool = False,
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
            "context_extra": {
                "restart": str(restart or ""),
                "update_manual": bool(update_manual),
            },
        }
        if (
            self._settings_save_runtime.is_running()
            or self.__dict__.get("_settings_save_start_scheduled", False)
        ):
            self._settings_save_pending.append(payload)
            return
        self._start_settings_save_worker(payload)

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
                enabled=bool(payload.get("enabled")),
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
        if self.__dict__.get("_settings_save_pending"):
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
        self._settings_save_restart_pending = ""
        log(f"{self.__class__.__name__}: не удалось сохранить настройку Telegram Proxy ({action}): {error}", "WARNING")

    def _on_settings_save_worker_finished(self, _worker) -> None:
        if self._settings_save_pending and not self._cleanup_in_progress:
            pending = self._settings_save_pending.pop(0)
            self._schedule_settings_save_worker_start(dict(pending or {}))

    def _schedule_settings_save_worker_start(self, payload: dict) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = dict(payload or {})
        if self.__dict__.get("_settings_save_start_scheduled", False):
            self._settings_save_pending.append(queued)
            return
        self._settings_save_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_settings_save_worker_start(value))

    def _run_scheduled_settings_save_worker_start(self, payload: dict) -> None:
        self._settings_save_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_settings_save_worker(payload)

    @pyqtSlot()
    def _start_proxy(self):
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

    def _check_relay_after_start(self):
        if self._cleanup_in_progress:
            return
        if (
            self._relay_check_runtime.is_running()
            or self.__dict__.get("_relay_check_start_scheduled", False)
        ):
            self._relay_check_pending = True
            return
        self._start_relay_check_worker()

    def _start_relay_check_worker(self) -> None:
        self._relay_check_pending = False
        mgr = self._proxy_manager()
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
        if self.__dict__.get("_relay_check_pending", False):
            self._schedule_relay_check_worker_start()

    def _schedule_relay_check_worker_start(self) -> None:
        if self.__dict__.get("_relay_check_start_scheduled", False):
            return
        self._relay_check_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_relay_check_worker_start)
        except Exception:
            self._run_scheduled_relay_check_worker_start()

    def _run_scheduled_relay_check_worker_start(self) -> None:
        self._relay_check_start_scheduled = False
        pending = bool(self.__dict__.get("_relay_check_pending", False))
        self._relay_check_pending = False
        if self.__dict__.get("_cleanup_in_progress", False) or not pending:
            return
        self._start_relay_check_worker()

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
        mgr = self._proxy_manager()
        stop_proxy_runtime(
            page=self,
            manager=mgr,
            create_stop_runtime_worker=self._telegram_proxy.create_stop_runtime_worker,
        )

    @pyqtSlot()
    def _finish_stop_proxy(self):
        if self._cleanup_in_progress:
            return
        self._request_settings_save("proxy_enabled", enabled=False)

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
        )

    def _on_upstream_preset_changed(self, index: int):
        """Handle upstream server selection."""
        self._current_mtproxy_link = handle_upstream_preset_changed(
            index=index,
            upstream_catalog=self._upstream_catalog,
            apply_upstream_preset_ui=self._apply_upstream_preset_ui,
            upstream_host_edit=self._upstream_host_edit,
            upstream_port_spin=self._upstream_port_spin,
            upstream_user_edit=self._upstream_user_edit,
            upstream_pass_edit=self._upstream_pass_edit,
            request_upstream_fields_save=lambda host, port, user, password: self._request_settings_save(
                "upstream_fields",
                host=host,
                port=port,
                user=user,
                password=password,
                restart="now",
            ),
        )

    def _on_upstream_host_changed(self):
        self._request_settings_save(
            "upstream_fields",
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="now",
        )

    def _on_upstream_port_changed(self, port: int):
        self._request_settings_save(
            "upstream_fields",
            host=self._upstream_host_edit.text(),
            port=port,
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="schedule",
        )

    def _on_upstream_user_changed(self):
        self._request_settings_save(
            "upstream_fields",
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
            restart="now",
        )

    def _on_upstream_pass_changed(self):
        self._request_settings_save(
            "upstream_fields",
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
        link = getattr(self, '_current_mtproxy_link', '')
        if not link:
            return
        self._start_external_link_worker(
            link,
            success_log="Opened MTProxy link",
            error_prefix="Failed to open MTProxy link",
        )

    def _update_manual_instructions(self):
        """Update manual instructions label with current host/port."""
        self._manual_host_port_label.setText(
            telegram_proxy_settings.build_manual_instruction_text(
                self._host_edit.text().strip(),
                self._port_spin.value(),
            )
        )

    def _on_open_in_telegram(self):
        """Open tg://socks deep link to auto-configure Telegram."""
        url = telegram_proxy_settings.build_proxy_url(
            self._host_edit.text().strip(),
            self._port_spin.value(),
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
        if (
            self._external_link_runtime.is_running()
            or self.__dict__.get("_external_link_start_scheduled", False)
        ):
            self.__dict__.setdefault("_external_link_pending", []).append(
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
            worker_factory=lambda _request_id: self.create_external_link_worker(
                url=url,
                success_log=success_log,
                error_prefix=error_prefix,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_external_link_worker_finished,
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
        pending_links = self.__dict__.setdefault("_external_link_pending", [])
        pending = pending_links.pop(0) if pending_links else None
        if pending and not self._cleanup_in_progress:
            self._schedule_external_link_worker_start(pending)

    def _schedule_external_link_worker_start(self, payload: dict) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = {
            "url": str((payload or {}).get("url") or ""),
            "success_log": str((payload or {}).get("success_log") or ""),
            "error_prefix": str((payload or {}).get("error_prefix") or ""),
        }
        if self.__dict__.get("_external_link_start_scheduled", False):
            self.__dict__.setdefault("_external_link_pending", []).append(queued)
            return
        self._external_link_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_external_link_worker_start(value))

    def _run_scheduled_external_link_worker_start(self, payload: dict) -> None:
        self._external_link_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
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
        if (
            self._ensure_hosts_runtime.is_running()
            or self.__dict__.get("_ensure_hosts_start_scheduled", False)
        ):
            self._ensure_hosts_pending = True
            return
        self._start_ensure_hosts_worker()

    def _start_ensure_hosts_worker(self) -> None:
        self._ensure_hosts_pending = False
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
        if self.__dict__.get("_ensure_hosts_pending", False) and not self.__dict__.get("_cleanup_in_progress", False):
            self._schedule_ensure_hosts_worker_start()

    def _schedule_ensure_hosts_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_ensure_hosts_start_scheduled", False):
            self._ensure_hosts_pending = True
            return
        self._ensure_hosts_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_ensure_hosts_worker_start)

    def _run_scheduled_ensure_hosts_worker_start(self) -> None:
        self._ensure_hosts_start_scheduled = False
        pending = bool(self.__dict__.get("_ensure_hosts_pending", False))
        self._ensure_hosts_pending = False
        if not pending or self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_ensure_hosts_worker()

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
        self._ensure_hosts_pending = False
        self._ensure_hosts_start_scheduled = False
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
        self._open_log_file_pending.clear()
        self._external_link_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy external link worker",
        )
        self._external_link_runtime.cancel()
        self._external_link_pending.clear()
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
        self._proxy_stop_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy stop worker",
        )
        self._proxy_stop_runtime.cancel()
        self._restart_stop_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy restart stop worker",
        )
        self._restart_stop_runtime.cancel()
        self._relay_check_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="telegram proxy relay check worker",
        )
        self._relay_check_runtime.cancel()
        self._relay_check_pending = False
        self._relay_check_start_scheduled = False
        if self._upstream_restart_timer is not None:
            self._upstream_restart_timer.stop()
            self._upstream_restart_timer.deleteLater()
            self._upstream_restart_timer = None
        self._log_line_pending.clear()
        self._settings_save_pending.clear()
        self._settings_save_restart_pending = ""
        mgr = self._proxy_manager()
        mgr.cleanup()
