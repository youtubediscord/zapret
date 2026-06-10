# dpi/ui/zapret2_mode/page.py
"""Zapret 2 mode management page (Strategies landing for zapret2_mode)."""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer

from ui.pages.base_page import BasePage
from settings.mode import ZAPRET2_MODE
from presets.ui.control.zapret2.build import (
    build_winws2_pages_management_section,
    build_winws2_pages_status_section,
)
from presets.ui.control.zapret2.runtime_helpers import (
    apply_additional_settings_state,
    apply_profile_language,
    apply_program_settings_snapshot,
    apply_status_plan,
    set_toggle_checked,
)
from presets.ui.control.shared_builders import build_last_status_message_card_common
from presets.ui.control.control_page_shared import (
    ControlPageActionMixin,
    bind_control_ui_state_store,
    cleanup_control_page_subscriptions,
)
from presets.ui.control.control_page_runtime_shared import (
    apply_last_status_message,
    set_enabled_if_changed,
    set_loading_status_accessibility,
    set_progress_active_if_changed,
    set_text_if_changed,
    set_visible_if_changed,
)
from presets.ui.control.windows_features.runtime import ControlPageWindowsFeatureMixin
from presets.ui.control.top_summary_widget import ControlTopSummaryWidget
from presets.ui.control.refresh_runtime_state import create_refresh_runtime
from app.ui_texts import tr as tr_catalog

from qfluentwidgets import (
    CaptionLabel, StrongBodyLabel,
    IndeterminateProgressBar,
    PrimaryPushButton, PushButton, SettingCardGroup, PushSettingCard,
)

if TYPE_CHECKING:
    from app.state_store import AppUiState, MainWindowStateStore


TOP_SUMMARY_PROFILE_RETRY_MS = 750
TOP_SUMMARY_PROFILE_RETRY_LIMIT = 10
ADDITIONAL_SETTINGS_PRESET_SWITCH_RELOAD_DELAY_MS = 180
TOP_SUMMARY_PRESET_SWITCH_RELOAD_DELAY_MS = 180


def _zapret2_page_runtime():
    from presets.ui.control.zapret2 import page_runtime

    return page_runtime


def _accent_fg_for_tokens(tokens) -> str:
    try:
        r, g, b = tokens.accent_rgb
        yiq = (r * 299 + g * 587 + b * 114) / 1000
        return "rgba(0, 0, 0, 0.90)" if yiq >= 160 else "rgba(245, 245, 245, 0.92)"
    except Exception:
        return "rgba(0, 0, 0, 0.90)"


def _log_startup_winws2_control_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    from log.log import log as _log


    _log(f"⏱ Startup UI Section: ZAPRET2_MODE_CONTROL {section} {rounded}ms", "⏱ STARTUP")


class Zapret2ModeControlPage(ControlPageWindowsFeatureMixin, ControlPageActionMixin, BasePage):
    """Главная страница управления для Zapret 2."""

    def __init__(
        self,
        parent=None,
        *,
        create_top_summary_worker,
        create_additional_settings_load_worker,
        create_additional_settings_save_worker,
        runtime_actions,
        create_program_settings_save_worker,
        create_program_settings_load_worker,
        create_program_settings_admin_check_worker,
        attach_program_settings_runtime,
        publish_program_settings_snapshot,
        remember_hide_to_tray_on_minimize_close,
        set_status,
        request_exit,
        open_connection_test,
        open_folder,
        open_presets,
        open_preset_setup,
        open_premium,
        create_external_open_url_worker,
        ui_state_store,
    ):
        _t_init = _time.perf_counter()
        _t_base = _time.perf_counter()
        super().__init__(
            "Управление",
            "Настройка и запуск Zapret 2. В «Мои пресеты» выбирается пресет, "
            "а в «Настройка пресета» меняются профили и выбранные для них готовые стратегии.",
            parent,
            title_key="page.winws2_control.title",
            subtitle_key="page.winws2_control.subtitle",
        )
        _log_startup_winws2_control_metric("__init__.base_page", (_time.perf_counter() - _t_base) * 1000)

        self._create_top_summary_worker = create_top_summary_worker
        self._create_additional_settings_load_worker = create_additional_settings_load_worker
        self._create_additional_settings_save_worker = create_additional_settings_save_worker
        self._runtime_actions = runtime_actions
        self._create_program_settings_save_worker = create_program_settings_save_worker
        self._create_program_settings_load_worker = create_program_settings_load_worker
        self._create_program_settings_admin_check_worker = create_program_settings_admin_check_worker
        self._attach_program_settings_runtime_fn = attach_program_settings_runtime
        self._publish_program_settings_snapshot = publish_program_settings_snapshot
        self._remember_hide_to_tray_on_minimize_close = remember_hide_to_tray_on_minimize_close
        self._set_status_callback = set_status
        self._request_exit_callback = request_exit
        self._open_connection_test_callback = open_connection_test
        self._open_folder_callback = open_folder
        self._open_presets_callback = open_presets
        self._open_preset_setup_callback = open_preset_setup
        self._open_premium_callback = open_premium
        self._create_external_open_url_worker = create_external_open_url_worker
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._program_settings_runtime_unsubscribe = None
        self._cleanup_in_progress = False
        self._program_settings_runtime_attached = False
        self._startup_showevent_profile_logged = False
        self._top_summary_profile_retry_count = 0
        self._top_summary_profile_retry_pending = False
        self._refresh_runtime = create_refresh_runtime()
        self.top_summary = None
        self.program_settings_card = None
        self.gui_autostart_toggle = None
        self.auto_dpi_toggle = None
        self.hide_to_tray_toggle = None
        self.defender_toggle = None
        self.max_block_toggle = None
        self.additional_settings_section_label = None
        self.discord_restart_toggle = None
        self.wssize_toggle = None
        self.debug_log_toggle = None
        self.additional_settings_card = None
        self.additional_settings_notice = None
        self.last_status_message_card = None
        self.last_status_message_dot = None
        self.last_status_message_title = None
        self.last_status_message_label = None
        self.extra_section_label = None
        self.extra_card = None
        self.test_card = None
        self.internet_cleanup_card = None
        self.folder_card = None
        self.docs_card = None
        self.test_btn = None
        self.internet_cleanup_btn = None
        self.folder_btn = None
        self.docs_btn = None
        self._build_ui()
        self.bind_ui_state_store(ui_state_store)
        self._after_ui_built()
        _log_startup_winws2_control_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def _after_ui_built(self) -> None:
        try:
            self._apply_selected_preset_name_fast()
        except Exception:
            pass
        self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)

    def _apply_pending_mode_refresh_if_ready(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.is_page_ready():
            return
        _t_show = _time.perf_counter()
        if (
            bool(self._refresh_runtime.additional_settings_dirty)
        ):
            self._schedule_additional_settings_reload()
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_winws2_control_metric("activation.total", (_time.perf_counter() - _t_show) * 1000)

    def _startup_can_refresh_top_summary(self) -> bool:
        return True

    def _apply_selected_preset_name_fast(self) -> None:
        self._request_top_summary_worker()

    def _schedule_top_summary_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        state = runtime.top_summary_preset_switch_reload_state
        state.pending = True

        def _single_shot(_delay: int, callback) -> None:
            QTimer.singleShot(TOP_SUMMARY_PRESET_SWITCH_RELOAD_DELAY_MS, callback)

        try:
            state.schedule_start(
                _single_shot,
                self._run_scheduled_top_summary_reload_after_preset_switch,
                pending_when_already_scheduled=True,
            )
        except Exception:
            self._run_scheduled_top_summary_reload_after_preset_switch()

    def _run_scheduled_top_summary_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        pending = runtime.top_summary_preset_switch_reload_state.take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.isVisible():
            self.run_when_page_ready(self._refresh_top_summary)
            return
        self._request_top_summary_worker()

    def _schedule_top_summary_profile_retry(self) -> None:
        if self._cleanup_in_progress:
            return
        if bool(getattr(self, "_top_summary_profile_retry_pending", False)):
            return
        retry_count = int(getattr(self, "_top_summary_profile_retry_count", 0) or 0)
        if retry_count >= TOP_SUMMARY_PROFILE_RETRY_LIMIT:
            return
        self._top_summary_profile_retry_count = retry_count + 1
        self._top_summary_profile_retry_pending = True
        QTimer.singleShot(TOP_SUMMARY_PROFILE_RETRY_MS, self._retry_top_summary_profile_count)

    def _retry_top_summary_profile_count(self) -> None:
        self._top_summary_profile_retry_pending = False
        if self._cleanup_in_progress:
            return
        self._refresh_top_summary()

    def _request_top_summary_worker(self) -> None:
        runtime = self._refresh_runtime
        state = runtime.top_summary_state
        if state.is_busy():
            state.pending = True
            return

        request_id = runtime.next_top_summary_request_id()
        runtime.top_summary_runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_top_summary_worker(
                request_id,
                parent=self,
            ),
            on_loaded=self._on_top_summary_loaded,
            on_failed=self._on_top_summary_failed,
            on_finished=self._on_top_summary_worker_finished,
        )

    def _on_top_summary_loaded(self, request_id: int, state) -> None:
        runtime = self._refresh_runtime
        if request_id != runtime.top_summary_request_id or self._cleanup_in_progress:
            return
        if runtime.top_summary_state.has_pending():
            return
        summary = self.top_summary
        if summary is None:
            return
        preset_text = str(getattr(state, "preset_text", "") or "").strip()
        summary.set_preset(
            preset_text
            or tr_catalog("page.winws2_control.preset.not_selected", language=self._ui_language, default="Не выбран")
        )
        profile_count = getattr(state, "profile_count", None)
        profiles_visible_setter = getattr(summary, "set_profiles_visible", None)
        if callable(profiles_visible_setter):
            profiles_visible_setter(bool(getattr(state, "profile_tab_visible", True)))
        summary.set_profile_count(profile_count)
        if profile_count is None:
            self._schedule_top_summary_profile_retry()
        else:
            self._top_summary_profile_retry_count = 0
            self._top_summary_profile_retry_pending = False

    def _on_top_summary_failed(self, request_id: int, error: str) -> None:
        if request_id != self._refresh_runtime.top_summary_request_id or self._cleanup_in_progress:
            return
        from log.log import log

        log(f"Не удалось обновить сводку Zapret 2: {error}", "WARNING")

    def _on_top_summary_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        runtime.top_summary_state.schedule_pending_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, current_worker: runtime.accept_worker_finish(
                current_worker,
                "top_summary_request_id",
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_top_summary_worker_start,
            cleanup_in_progress=bool(self._cleanup_in_progress),
        )

    def _schedule_top_summary_worker_start(self) -> None:
        runtime = self._refresh_runtime
        if self._cleanup_in_progress:
            return
        runtime.top_summary_state.pending = True
        runtime.top_summary_state.schedule_start(
            QTimer.singleShot,
            self._run_scheduled_top_summary_worker_start,
            cleanup_in_progress=bool(self._cleanup_in_progress),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_top_summary_worker_start(self) -> None:
        runtime = self._refresh_runtime
        pending = runtime.top_summary_state.take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self._cleanup_in_progress)
        )
        if not pending:
            return
        if runtime.top_summary_runtime.is_running():
            runtime.top_summary_state.pending = True
            return
        self._request_top_summary_worker()

    def _refresh_top_summary(self, state: AppUiState | None = None) -> None:
        summary = self.top_summary
        if summary is None:
            return
        snapshot = state
        if snapshot is None and self._ui_state_store is not None:
            try:
                snapshot = self._ui_state_store.snapshot()
            except Exception:
                snapshot = None
        self._apply_top_summary_premium(snapshot)
        self._request_top_summary_worker()

    def _apply_top_summary_premium(self, state: AppUiState | None = None) -> None:
        summary = self.top_summary
        if summary is None:
            return
        summary.set_premium(
            is_premium=bool(getattr(state, "subscription_is_premium", False)),
            days_remaining=getattr(state, "subscription_days_remaining", None),
        )

    def _open_preset_setup_page(self) -> None:
        self._open_preset_setup_callback()

    def _build_ui(self):
        _t_total = _time.perf_counter()
        self.top_summary = ControlTopSummaryWidget(
            language=self._ui_language,
            mode_value="Zapret 2",
            initial_icon_delay_ms=250,
            parent=self.content,
        )
        self.top_summary.presetClicked.connect(self._open_presets_callback)
        self.top_summary.profilesClicked.connect(self._open_preset_setup_page)
        self.top_summary.premiumClicked.connect(self._open_premium_callback)
        self.add_widget(self.top_summary)
        self.add_spacing(16)

        # Статус работы
        _t_status = _time.perf_counter()
        status_widgets = build_winws2_pages_status_section(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.status_section_label = status_widgets.section_label
        self.status_card = status_widgets.card
        self.status_dot = status_widgets.status_dot
        self.status_title = status_widgets.status_title
        self.status_desc = status_widgets.status_desc
        self.add_widget(status_widgets.card)
        _log_startup_winws2_control_metric("_build_ui.status_card", (_time.perf_counter() - _t_status) * 1000)

        self.add_spacing(16)

        # Управление
        _t_control = _time.perf_counter()
        management_widgets = build_winws2_pages_management_section(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            caption_label_cls=CaptionLabel,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            big_action_button_cls=PrimaryPushButton,
            stop_button_cls=PushButton,
            on_start=self._start_dpi,
            on_stop=self._stop_dpi,
            on_stop_and_exit=self._stop_and_exit,
            parent=self,
        )
        self.control_section_label = management_widgets.section_label
        self.control_card_card = management_widgets.card
        self.start_btn = management_widgets.start_btn
        self.stop_winws_btn = management_widgets.stop_winws_btn
        self.stop_and_exit_btn = management_widgets.stop_and_exit_btn
        self.progress_bar = management_widgets.progress_bar
        self.loading_label = management_widgets.loading_label
        self.add_widget(management_widgets.card)
        _log_startup_winws2_control_metric("_build_ui.control_card", (_time.perf_counter() - _t_control) * 1000)
        self._build_settings_sections()
        self._attach_program_settings_runtime()
        self._schedule_additional_settings_reload(force=True)

        _log_startup_winws2_control_metric("_build_ui.total", (_time.perf_counter() - _t_total) * 1000)

    def _build_settings_sections(self) -> None:
        self.add_spacing(8)
        from presets.ui.control.zapret2.sections_build import (
            build_winws2_pages_settings_sections,
        )
        from ui.widgets.win11_controls import Win11ToggleRow

        section_widgets = build_winws2_pages_settings_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            setting_card_group_cls=SettingCardGroup,
            push_setting_card_cls=PushSettingCard,
            win11_toggle_row_cls=Win11ToggleRow,
            on_gui_autostart_toggled=self._on_gui_autostart_toggled,
            on_auto_dpi_toggled=self._on_auto_dpi_toggled,
            on_hide_to_tray_toggled=self._on_hide_to_tray_toggled,
            on_defender_toggled=self._on_defender_toggled,
            on_max_blocker_toggled=self._on_max_blocker_toggled,
            on_discord_restart_changed=self._on_discord_restart_changed,
            on_wssize_toggled=self._on_wssize_toggled,
            on_debug_log_toggled=self._on_debug_log_toggled,
            on_open_connection_test=self._open_connection_test,
            on_open_internet_cleanup=self._on_internet_cleanup_clicked,
            on_open_folder=self._open_folder,
            on_open_docs=self._open_docs,
        )

        self.program_settings_section_label = section_widgets.program_settings_section_label
        self.program_settings_card = section_widgets.program_settings_card
        self.gui_autostart_toggle = section_widgets.gui_autostart_toggle
        self.auto_dpi_toggle = section_widgets.auto_dpi_toggle
        self.hide_to_tray_toggle = section_widgets.hide_to_tray_toggle
        self.defender_toggle = section_widgets.defender_toggle
        self.max_block_toggle = section_widgets.max_block_toggle
        self.add_spacing(8)
        self.add_spacing(16)
        self.add_widget(self.program_settings_card)

        self.additional_settings_section_label = None
        self.discord_restart_toggle = section_widgets.discord_restart_toggle
        self.wssize_toggle = section_widgets.wssize_toggle
        self.debug_log_toggle = section_widgets.debug_log_toggle
        self.additional_settings_card = section_widgets.additional_settings_card
        self.additional_settings_notice = section_widgets.additional_settings_notice
        self.add_spacing(16)
        self.add_widget(self.additional_settings_card)

        self.add_spacing(16)
        last_message_widgets = build_last_status_message_card_common(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.last_status_message_card = last_message_widgets.card
        self.last_status_message_dot = last_message_widgets.dot
        self.last_status_message_title = last_message_widgets.title_label
        self.last_status_message_label = last_message_widgets.message_label
        self.add_widget(self.last_status_message_card)
        self._refresh_last_status_message()

        self.add_spacing(16)
        self.extra_section_label = section_widgets.extra_section_label
        self.extra_card = section_widgets.extra_card
        self.test_card = section_widgets.test_card
        self.internet_cleanup_card = section_widgets.internet_cleanup_card
        self.folder_card = section_widgets.folder_card
        self.docs_card = section_widgets.docs_card
        self.test_btn = self.test_card.button
        self.internet_cleanup_btn = self.internet_cleanup_card.button
        self.folder_btn = self.folder_card.button
        self.docs_btn = self.docs_card.button
        self.add_widget(self.extra_card)

    def _apply_additional_settings_state(self, plan) -> None:
        apply_additional_settings_state(
            plan,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
        )

    def _schedule_additional_settings_reload(self, *, force: bool = False) -> None:
        from presets.ui.control.additional_settings_runtime import (
            create_additional_settings_worker as create_control_additional_settings_worker,
        )

        runtime = self._refresh_runtime
        if not force and not runtime.additional_settings_dirty:
            return
        if not self.isVisible():
            runtime.additional_settings_dirty = True
            self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)
            return
        state = runtime.additional_settings_load_state
        if state.is_busy():
            state.pending = True
            runtime.additional_settings_dirty = True
            return

        request_id = runtime.next_additional_settings_request_id()
        runtime.additional_settings_load_runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: create_control_additional_settings_worker(
                request_id,
                self._create_additional_settings_load_worker,
                launch_method=ZAPRET2_MODE,
                parent=self,
            ),
            on_loaded=self._on_additional_settings_loaded,
            on_finished=self._on_additional_settings_load_worker_finished,
            loaded_signal_name="loaded",
        )

    def _on_additional_settings_loaded(self, request_id: int, state: dict) -> None:
        if not self._refresh_runtime.accept_additional_settings_result(request_id):
            return
        if self._refresh_runtime.additional_settings_load_state.has_pending():
            return
        plan = _zapret2_page_runtime().build_additional_settings_state(state if isinstance(state, dict) else {})
        self._apply_additional_settings_state(plan)

    def _on_additional_settings_load_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        if not runtime.accept_worker_finish(worker, "additional_settings_request_id"):
            return
        state = runtime.additional_settings_load_state
        if state.has_pending() and not self._cleanup_in_progress:
            state.schedule_pending_after_finish(
                worker,
                is_current_worker_finish=lambda _runtime, current_worker: runtime.accept_worker_finish(
                    current_worker,
                    "additional_settings_request_id",
                ),
                single_shot=QTimer.singleShot,
                run_scheduled=self._run_scheduled_additional_settings_reload_start,
                clear_pending_before_schedule=True,
            )
            return
        state.pending = False

    def _schedule_additional_settings_reload_start(self) -> None:
        runtime = self._refresh_runtime
        state = runtime.additional_settings_load_state
        if state.start_scheduled:
            state.pending = True
            runtime.additional_settings_dirty = True
            return
        state.pending = True
        try:
            state.schedule_start(QTimer.singleShot, self._run_scheduled_additional_settings_reload_start)
        except Exception:
            self._run_scheduled_additional_settings_reload_start()

    def _run_scheduled_additional_settings_reload_start(self) -> None:
        runtime = self._refresh_runtime
        state = runtime.additional_settings_load_state
        was_scheduled = bool(state.start_scheduled)
        pending = state.take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is False and not was_scheduled:
            return
        self._schedule_additional_settings_reload(force=True)

    def _schedule_additional_settings_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        runtime.additional_settings_dirty = True
        state = runtime.additional_settings_preset_switch_reload_state
        state.pending = True

        def _single_shot(_delay: int, callback) -> None:
            QTimer.singleShot(ADDITIONAL_SETTINGS_PRESET_SWITCH_RELOAD_DELAY_MS, callback)

        try:
            state.schedule_start(
                _single_shot,
                self._run_scheduled_additional_settings_reload_after_preset_switch,
                pending_when_already_scheduled=True,
            )
        except Exception:
            self._run_scheduled_additional_settings_reload_after_preset_switch()

    def _run_scheduled_additional_settings_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        pending = runtime.additional_settings_preset_switch_reload_state.take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not runtime.additional_settings_dirty:
            return
        if not self.isVisible():
            self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)
            return
        self._schedule_additional_settings_reload(force=True)

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        self._request_additional_settings_save("discord_restart", bool(enabled), launch_method=ZAPRET2_MODE)

    def _on_wssize_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("wssize", bool(enabled), launch_method=ZAPRET2_MODE)

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("debug_log", bool(enabled), launch_method=ZAPRET2_MODE)

    def _request_additional_settings_save(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        runtime.mark_additional_settings_written()
        state = runtime.additional_settings_save_state
        if state.is_busy():
            runtime.queue_additional_settings_save(setting, bool(enabled), launch_method)
            return
        self._start_additional_settings_save_worker(setting, enabled, launch_method=launch_method)

    def _start_additional_settings_save_worker(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        request_id = runtime.next_additional_settings_save_request_id()
        runtime.additional_settings_save_runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_additional_settings_save_worker(
                request_id,
                setting=setting,
                enabled=bool(enabled),
                parent=self,
            ),
            on_loaded=self._on_additional_settings_save_finished,
            on_failed=self._on_additional_settings_save_failed,
            on_finished=self._on_additional_settings_save_worker_finished,
            loaded_signal_name="saved",
        )

    def _on_additional_settings_save_finished(self, request_id: int, _setting: str, _enabled: bool) -> None:
        if request_id != self._refresh_runtime.additional_settings_save_request_id:
            return

    def _on_additional_settings_save_failed(self, request_id: int, _setting: str, error: str) -> None:
        if request_id != self._refresh_runtime.additional_settings_save_request_id:
            return
        if self._refresh_runtime.additional_settings_save_state.has_pending():
            return
        from qfluentwidgets import InfoBar

        InfoBar.warning(title="Ошибка", content=f"Не удалось сохранить настройку: {error}", parent=self.window())

    def _on_additional_settings_save_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        state = runtime.additional_settings_save_state
        state.schedule_next_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, current_worker: runtime.accept_worker_finish(
                current_worker,
                "additional_settings_save_request_id",
            ),
            single_shot=QTimer.singleShot,
            start=lambda item: self._run_scheduled_additional_settings_save_start(
                str(item[0]),
                bool(item[1]),
                launch_method=str(item[2]),
            ),
            queue_item=lambda item: runtime.queue_additional_settings_save(
                str(item[0]),
                bool(item[1]),
                str(item[2]),
                front=True,
            ),
            is_cleanup_in_progress=lambda: bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _schedule_additional_settings_save_start(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        state = runtime.additional_settings_save_state
        item = (str(setting or ""), bool(enabled), str(launch_method or ""))
        try:
            state.schedule_start(
                item,
                QTimer.singleShot,
                lambda pending: self._run_scheduled_additional_settings_save_start(
                    str(pending[0]),
                    bool(pending[1]),
                    launch_method=str(pending[2]),
                ),
                queue_item=lambda pending: runtime.queue_additional_settings_save(
                    str(pending[0]),
                    bool(pending[1]),
                    str(pending[2]),
                    front=True,
                ),
                is_cleanup_in_progress=lambda: bool(getattr(self, "_cleanup_in_progress", False)),
            )
        except Exception:
            self._run_scheduled_additional_settings_save_start(
                str(setting or ""),
                bool(enabled),
                launch_method=str(launch_method or ""),
            )

    def _run_scheduled_additional_settings_save_start(
        self,
        setting: str,
        enabled: bool,
        *,
        launch_method: str,
    ) -> None:
        self._refresh_runtime.additional_settings_save_state.start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_additional_settings_save_worker(
            str(setting or ""),
            bool(enabled),
            launch_method=str(launch_method or ""),
        )

    def _sync_program_settings(self) -> None:
        self._request_program_settings_load()

    def _attach_program_settings_runtime(self) -> None:
        self._attach_program_settings_runtime_fn(
            self,
            apply_snapshot_fn=self._apply_program_settings_snapshot,
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        if self._cleanup_in_progress:
            return
        apply_program_settings_snapshot(
            snapshot,
            auto_dpi_toggle=self.auto_dpi_toggle,
            gui_autostart_toggle=self.gui_autostart_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
        )

    def _on_gui_autostart_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("gui_autostart", bool(enabled))

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("auto_dpi", bool(enabled))

    def _on_hide_to_tray_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("hide_to_tray", bool(enabled))

    def _update_stop_winws_button_text(self):
        plan = _zapret2_page_runtime().build_stop_button_plan(language=self._ui_language)
        set_text_if_changed(self.stop_winws_btn, plan.text)

    def set_loading(self, loading: bool, text: str = ""):
        set_progress_active_if_changed(self.progress_bar, loading)
        set_visible_if_changed(self.progress_bar, loading)
        set_visible_if_changed(self.loading_label, loading and bool(text))
        set_text_if_changed(self.loading_label, text)
        set_loading_status_accessibility(self.loading_label, active=loading, text=text)

        set_enabled_if_changed(self.start_btn, not loading)
        set_enabled_if_changed(self.stop_winws_btn, not loading)
        set_enabled_if_changed(self.stop_and_exit_btn, not loading)

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        bind_control_ui_state_store(
            self,
            store,
            callback=self._on_ui_state_changed,
            fields={
                "launch_phase",
                "launch_running",
                "launch_busy",
                "launch_busy_text",
                "launch_last_error",
                "last_status_message",
                "current_strategy_summary",
                "active_preset_revision",
                "preset_content_revision",
                "mode_revision",
                "subscription_is_premium",
                "subscription_days_remaining",
            },
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        runtime = self.__dict__.get("_refresh_runtime")
        presets_changed = "active_preset_revision" in changed
        preset_apply_busy = bool(
            getattr(state, "launch_busy", False)
            and "Применяем пресет" in str(getattr(state, "launch_busy_text", "") or "")
        )
        top_summary_data_changed = (
            not changed
            or "current_strategy_summary" in changed
            or "preset_content_revision" in changed
        )
        top_summary_premium_changed = (
            "subscription_is_premium" in changed
            or "subscription_days_remaining" in changed
        )
        runtime_status_changed = (
            not changed
            or bool(changed & {
                "launch_phase",
                "launch_running",
                "launch_busy",
                "launch_busy_text",
                "launch_last_error",
            })
        )
        strategy_changed = not changed or "current_strategy_summary" in changed
        if top_summary_data_changed:
            self._refresh_top_summary(state)
        elif top_summary_premium_changed:
            self._apply_top_summary_premium(state)
        if presets_changed and runtime is not None:
            if preset_apply_busy:
                runtime.top_summary_reload_after_preset_apply_pending = True
            else:
                try:
                    self._schedule_top_summary_reload_after_preset_switch()
                except Exception:
                    pass
            runtime.additional_settings_dirty = True
            if not self.isVisible():
                self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)
            if preset_apply_busy:
                runtime.additional_settings_reload_after_preset_apply_pending = True
            else:
                self._schedule_additional_settings_reload_after_preset_switch()
        if not changed or "last_status_message" in changed:
            self._refresh_last_status_message(state)
        if runtime_status_changed:
            self.set_loading(bool(state.launch_busy), str(state.launch_busy_text or ""))
            self.update_status(
                state.launch_phase or ("running" if state.launch_running else "stopped"),
                str(state.launch_last_error or ""),
            )
            if runtime is not None and not preset_apply_busy:
                if bool(getattr(runtime, "top_summary_reload_after_preset_apply_pending", False)):
                    runtime.top_summary_reload_after_preset_apply_pending = False
                    try:
                        self._schedule_top_summary_reload_after_preset_switch()
                    except Exception:
                        pass
                if bool(getattr(runtime, "additional_settings_reload_after_preset_apply_pending", False)):
                    runtime.additional_settings_reload_after_preset_apply_pending = False
                    self._schedule_additional_settings_reload_after_preset_switch()
        if strategy_changed:
            self.update_strategy(str(state.current_strategy_summary or ""))

    def _refresh_last_status_message(self, state: AppUiState | None = None) -> None:
        if self.last_status_message_label is None or self.last_status_message_dot is None:
            return
        if state is None:
            store = self._ui_state_store
            try:
                state = store.snapshot() if store is not None else None
            except Exception:
                state = None
        message = getattr(state, "last_status_message", "") if state is not None else ""
        apply_last_status_message(
            str(message or ""),
            message_label=self.last_status_message_label,
            message_dot=self.last_status_message_dot,
            empty_text=tr_catalog(
                "page.control.last_message.empty",
                language=self._ui_language,
                default="Пока нет новых сообщений",
            ),
        )

    def update_status(self, state: str | bool, last_error: str = ""):
        plan = _zapret2_page_runtime().build_status_plan(
            state=state,
            last_error=last_error,
            language=self._ui_language,
        )
        apply_status_plan(
            plan,
            status_title=self.status_title,
            status_desc=self.status_desc,
            status_dot=self.status_dot,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            update_stop_button_text=self._update_stop_winws_button_text,
        )

    def update_strategy(self, name: str):
        _ = name
        self._update_stop_winws_button_text()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        if self.top_summary is not None:
            self.top_summary.set_language(self._ui_language)
            self._refresh_top_summary()
        if self.last_status_message_title is not None:
            self.last_status_message_title.setText(
                tr_catalog(
                    "page.control.last_message.title",
                    language=self._ui_language,
                    default="Последнее сообщение",
                )
            )
            self._refresh_last_status_message()
        apply_profile_language(
            language=self._ui_language,
            start_btn=self.start_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            test_card=self.test_card,
            internet_cleanup_card=self.internet_cleanup_card,
            folder_card=self.folder_card,
            docs_card=self.docs_card,
            additional_settings_notice=self.additional_settings_notice,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            gui_autostart_toggle=self.gui_autostart_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
            additional_settings_card=self.additional_settings_card,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
            update_stop_button_text=self._update_stop_winws_button_text,
        )

    def _open_docs(self) -> None:
        from config.urls import DOCS_URL

        self._request_external_open_url(
            DOCS_URL,
            error_title="Документация",
            error_default="Не удалось открыть документацию: {error}",
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._refresh_runtime.stop_workers()
        self._stop_defender_admin_check_worker()
        self._stop_internet_cleanup_worker()
        self._stop_external_open_url_worker()
        cleanup_control_page_subscriptions(self)
