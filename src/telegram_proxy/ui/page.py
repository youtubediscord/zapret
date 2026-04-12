# ui/pages/telegram_proxy_page.py
"""Telegram WebSocket Proxy — UI page.

Provides controls for starting/stopping the proxy, mode selection,
port configuration, and quick-setup deep link for Telegram.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout,
)

from ui.pages.base_page import BasePage
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
    load_settings_into_ui,
    refresh_pivot_texts,
    refresh_status_texts,
    refresh_upstream_preset_combo,
)
from telegram_proxy.ui.upstream_workflow import (
    handle_upstream_preset_changed,
    handle_upstream_toggle,
    save_upstream_fields,
    save_upstream_mode,
    schedule_upstream_restart,
)
from telegram_proxy.ui.settings_build import (
    build_telegram_proxy_settings_panel,
)
from ui.compat_widgets import (
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from log import log
from telegram_proxy.page_actions_controller import TelegramProxyPageActionsController
from telegram_proxy.diagnostics_controller import TelegramProxyDiagnosticsController
from telegram_proxy.page_runtime_controller import TelegramProxyRuntimeController
from telegram_proxy.page_settings_controller import TelegramProxySettingsController
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
        self._diag_poll_timer = None
        self._upstream_restart_timer = None
        self._relay_check_gen = 0
        self._cleanup_in_progress = False
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
        shell = build_telegram_proxy_shell(
            segmented_widget_cls=SegmentedWidget,
            parent=self,
            on_switch_tab=self._switch_tab,
        )
        self._pivot = shell.pivot
        self._stacked = shell.stacked

        self._build_settings_panel(shell.settings_layout)
        logs_widgets = build_telegram_proxy_logs_panel(
            shell.logs_layout,
            push_button_cls=PushButton,
            on_copy_all_logs=self._on_copy_all_logs,
            on_open_log_file=self._on_open_log_file,
            on_clear_logs=self._on_clear_logs,
        )
        self._btn_copy_logs = logs_widgets.btn_copy_logs
        self._btn_open_log_file = logs_widgets.btn_open_log_file
        self._btn_clear_logs = logs_widgets.btn_clear_logs
        self._log_edit = logs_widgets.log_edit

        diag_widgets = build_telegram_proxy_diag_panel(
            shell.diag_layout,
            caption_label_cls=CaptionLabel,
            primary_push_button_cls=PrimaryPushButton,
            push_button_cls=PushButton,
            on_run_diagnostics=self._on_run_diagnostics,
            on_copy_diag=self._on_copy_diag,
        )
        self._diag_desc_label = diag_widgets.diag_desc_label
        self._btn_run_diag = diag_widgets.btn_run_diag
        self._btn_copy_diag = diag_widgets.btn_copy_diag
        self._diag_edit = diag_widgets.diag_edit

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
        self._autostart_toggle = widgets.autostart_toggle
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

        self._refresh_upstream_preset_combo(select_index=0)

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
            proxy_port=self._port_spin.value(),
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
            update_diag=self._update_diag,
            finish_diag=self._diag_finished,
        )

    def _run_diag_tests(self):
        self._diag_result = TelegramProxyDiagnosticsController.run_all(
            proxy_port=getattr(self, "_diag_proxy_port", 1353),
            progress_callback=self._publish_diag_result,
        )
        self._diag_thread_done = True

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
        finish_diagnostics(btn_run_diag=self._btn_run_diag)

    def _refresh_pivot_texts(self) -> None:
        refresh_pivot_texts(self._pivot)

    def _refresh_status_texts(self) -> None:
        mgr = _get_proxy_manager()
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
            autostart_toggle=getattr(self, "_autostart_toggle", None),
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
        target_index, self._current_mtproxy_link = refresh_upstream_preset_combo(
            upstream_preset_row=self._upstream_preset_row,
            upstream_catalog=self._upstream_catalog,
            apply_upstream_preset_ui_callback=self._apply_upstream_preset_ui,
            select_index=select_index,
        )
        return target_index

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
        load_settings_into_ui(
            upstream_catalog=self._upstream_catalog,
            port_spin=self._port_spin,
            host_edit=self._host_edit,
            autostart_toggle=self._autostart_toggle,
            update_manual_instructions=self._update_manual_instructions,
            upstream_toggle=self._upstream_toggle,
            upstream_host_edit=self._upstream_host_edit,
            upstream_port_spin=self._upstream_port_spin,
            upstream_user_edit=self._upstream_user_edit,
            upstream_pass_edit=self._upstream_pass_edit,
            refresh_upstream_preset_combo_callback=self._refresh_upstream_preset_combo,
            upstream_mode_toggle=self._upstream_mode_toggle,
        )

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
        handle_toggle_proxy(
            manager=mgr,
            restarting=bool(getattr(self, "_restarting", False)),
            starting=bool(getattr(self, "_starting", False)),
            set_restarting=lambda value: setattr(self, "_restarting", value),
            stop_proxy=self._stop_proxy,
            start_proxy=self._start_proxy,
        )

    def _restart_if_running(self):
        mgr = _get_proxy_manager()
        restart_proxy_if_running(
            page=self,
            manager=mgr,
            restarting=bool(getattr(self, "_restarting", False)),
            set_restarting=lambda value: setattr(self, "_restarting", value),
            status_label=self._status_label,
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

    @pyqtSlot()
    def _start_proxy(self):
        mgr = _get_proxy_manager()
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
        )

    def _check_relay_after_start(self):
        mgr = _get_proxy_manager()
        start_relay_check(
            page=self,
            manager=mgr,
            current_generation=getattr(self, "_relay_check_gen", 0),
            set_generation=lambda value: setattr(self, "_relay_check_gen", value),
            status_label=self._status_label,
            set_relay_diag=lambda value: setattr(self, "_relay_diag", value),
            get_zapret_running=lambda: (
                bool(getattr(getattr(getattr(self.window(), "app", None), "launch_runtime_api", None), "is_any_running", lambda silent=True: False)(silent=True))
            ),
            log_warning=lambda text: log(text, "WARNING"),
        )

    @pyqtSlot()
    def _apply_relay_result(self):
        if self._cleanup_in_progress:
            return
        mgr = _get_proxy_manager()
        apply_relay_result(
            manager=mgr,
            diag=getattr(self, "_relay_diag", {}),
            status_label=self._status_label,
            info_bar_cls=InfoBar,
            info_bar_position=InfoBarPosition,
            parent=self,
        )

    def _stop_proxy(self):
        mgr = _get_proxy_manager()
        stop_proxy_runtime(manager=mgr)

    def _on_status_changed(self, running: bool):
        mgr = _get_proxy_manager()
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

    def _on_stats_updated(self, stats):
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
        handle_upstream_toggle(
            checked=checked,
            set_upstream_enabled=TelegramProxySettingsController.set_upstream_enabled,
            apply_upstream_preset_ui=self._apply_upstream_preset_ui,
            current_index=self._upstream_preset_row.combo.currentIndex(),
            restart_if_running=self._restart_if_running,
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
            set_upstream_fields=TelegramProxySettingsController.set_upstream_fields,
            restart_if_running=self._restart_if_running,
        )

    def _on_upstream_host_changed(self):
        save_upstream_fields(
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_port_changed(self, port: int):
        save_upstream_fields(
            host=self._upstream_host_edit.text(),
            port=port,
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
        )
        self._schedule_upstream_restart()

    def _on_upstream_user_changed(self):
        save_upstream_fields(
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_pass_changed(self):
        save_upstream_fields(
            host=self._upstream_host_edit.text(),
            port=self._upstream_port_spin.value(),
            user=self._upstream_user_edit.text(),
            password=self._upstream_pass_edit.text(),
        )
        self._restart_if_running()

    def _on_upstream_mode_changed(self, checked: bool):
        save_upstream_mode(checked=checked)
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
        self._cleanup_in_progress = True
        self._relay_check_gen = getattr(self, '_relay_check_gen', 0) + 1
        if self._log_timer is not None:
            self._log_timer.stop()
        if self._diag_poll_timer is not None:
            self._diag_poll_timer.stop()
            self._diag_poll_timer.deleteLater()
            self._diag_poll_timer = None
        if self._upstream_restart_timer is not None:
            self._upstream_restart_timer.stop()
            self._upstream_restart_timer.deleteLater()
            self._upstream_restart_timer = None
        mgr = _get_proxy_manager()
        mgr.cleanup()
