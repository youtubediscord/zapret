# dpi/ui/zapret1_mode/page.py
"""Zapret 1 mode management page (entry point for zapret1_mode mode)."""

from PyQt6.QtCore import QTimer

from ui.pages.base_page import BasePage
from settings.mode import EXE_NAME_WINWS1, ZAPRET1_MODE
from presets.ui.control.zapret1.build import (
    build_winws1_pages_management_section,
    build_winws1_pages_status_section,
)
from presets.ui.control.zapret1.sections_build import (
    build_winws1_pages_settings_sections,
)
from presets.ui.control.zapret1.runtime_helpers import (
    apply_program_settings_snapshot,
    apply_status_plan,
    apply_winws1_pages_language,
    set_toggle_checked,
)
import presets.ui.control.zapret1.runtime_helpers as winws1_page_runtime
from presets.ui.control.shared_builders import build_last_status_message_card_common
import presets.ui.control.control_runtime as control_runtime
from presets.ui.control.control_page_runtime_shared import (
    apply_last_status_message,
    set_enabled_if_changed,
    set_progress_active_if_changed,
    set_text_if_changed,
    set_visible_if_changed,
)
from presets.ui.control.windows_features.runtime import ControlPageWindowsFeatureMixin
from app.state_store import AppUiState, MainWindowStateStore
from presets.ui.control.control_page_shared import (
    ControlPageActionMixin,
    bind_control_ui_state_store,
    cleanup_control_page_subscriptions,
)
from app.ui_texts import tr as tr_catalog
from presets.ui.control.top_summary_widget import ControlTopSummaryWidget
from log.log import log

from qfluentwidgets import (
    CaptionLabel, StrongBodyLabel,
    IndeterminateProgressBar, InfoBar,
    PrimaryPushButton, PushButton, PushSettingCard, SettingCardGroup,
)


TOP_SUMMARY_PROFILE_RETRY_MS = 750
TOP_SUMMARY_PROFILE_RETRY_LIMIT = 10
ADDITIONAL_SETTINGS_PRESET_SWITCH_RELOAD_DELAY_MS = 180
TOP_SUMMARY_PRESET_SWITCH_RELOAD_DELAY_MS = 180


class Zapret1ModeControlPage(ControlPageWindowsFeatureMixin, ControlPageActionMixin, BasePage):
    """Страница управления для zapret1_mode."""

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
        super().__init__(
            "Управление Zapret 1",
            f"Настройка и запуск Zapret 1 ({EXE_NAME_WINWS1}). В «Мои пресеты» выбирается пресет, "
            "а в «Настройка пресета» меняются профили и выбранные для них готовые стратегии.",
            parent,
            title_key="page.winws1_control.title",
            subtitle_key="page.winws1_control.subtitle",
        )
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
        self._last_known_dpi_running = False
        self._program_settings_runtime_attached = False
        self._top_summary_profile_retry_count = 0
        self._top_summary_profile_retry_pending = False
        self._refresh_runtime = winws1_page_runtime.create_refresh_runtime()
        self.top_summary = None
        self.program_settings_card = None
        self.gui_autostart_toggle = None
        self.auto_dpi_toggle = None
        self.hide_to_tray_toggle = None
        self.defender_toggle = None
        self.max_block_toggle = None
        self.discord_restart_toggle = None
        self.wssize_toggle = None
        self.debug_log_toggle = None
        self.additional_settings_card = None
        self.additional_settings_notice = None
        self.last_status_message_card = None
        self.last_status_message_dot = None
        self.last_status_message_title = None
        self.last_status_message_label = None
        self.extra_card = None
        self.test_btn = None
        self.internet_cleanup_btn = None
        self.folder_btn = None
        self.docs_btn = None
        self.test_card = None
        self.internet_cleanup_card = None
        self.folder_card = None
        self.docs_card = None
        self._build_ui()
        self.bind_ui_state_store(ui_state_store)
        self._refresh_preset_name()

    def _open_docs(self) -> None:
        from config.urls import DOCS_URL

        self._request_external_open_url(
            DOCS_URL,
            error_title="Документация",
            error_default="Не удалось открыть документацию: {error}",
        )

    def _apply_pending_preset_name_refresh(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.is_page_ready():
            return
        try:
            self._refresh_preset_name()
        except Exception:
            pass

    def _startup_can_refresh_top_summary(self) -> bool:
        return True

    def _build_ui(self):
        self.top_summary = ControlTopSummaryWidget(
            language=self._ui_language,
            mode_value="Zapret 1",
            initial_icon_delay_ms=250,
            parent=self.content,
        )
        self.top_summary.presetClicked.connect(self._open_presets_callback)
        self.top_summary.profilesClicked.connect(self._open_preset_setup_page)
        self.top_summary.premiumClicked.connect(self._open_premium_callback)
        self.add_widget(self.top_summary)
        self.add_spacing(16)

        # ── Статус работы ──────────────────────────────────────────────────
        self.add_section_title(text_key="page.winws1_control.section.status")
        status_widgets = build_winws1_pages_status_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.status_dot = status_widgets.status_dot
        self.status_title = status_widgets.status_title
        self.status_desc = status_widgets.status_desc
        self.add_widget(status_widgets.card)

        self.add_spacing(16)

        # ── Управление ─────────────────────────────────────────────────────
        self.add_section_title(text_key="page.winws1_control.section.management")
        management_widgets = build_winws1_pages_management_section(
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
        self.start_btn = management_widgets.start_btn
        self.stop_winws_btn = management_widgets.stop_winws_btn
        self.stop_and_exit_btn = management_widgets.stop_and_exit_btn
        self.progress_bar = management_widgets.progress_bar
        self.loading_label = management_widgets.loading_label
        self.add_widget(management_widgets.card)
        self._build_settings_sections()
        self._attach_program_settings_runtime()
        self._schedule_additional_settings_reload(force=True)

    def _build_settings_sections(self) -> None:
        self.add_spacing(8)
        from ui.widgets.win11_controls import Win11ToggleRow

        section_widgets = build_winws1_pages_settings_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            push_setting_card_cls=PushSettingCard,
            setting_card_group_cls=SettingCardGroup,
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
        self.add_widget(self.program_settings_card)

        self.add_spacing(16)
        self.additional_settings_card = section_widgets.additional_settings_card
        self.additional_settings_notice = section_widgets.additional_settings_notice
        self.discord_restart_toggle = section_widgets.discord_restart_toggle
        self.wssize_toggle = section_widgets.wssize_toggle
        self.debug_log_toggle = section_widgets.debug_log_toggle
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

    def _sync_program_settings(self) -> None:
        self._request_program_settings_load()

    def _on_gui_autostart_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("gui_autostart", bool(enabled))

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("auto_dpi", bool(enabled))

    def _on_hide_to_tray_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("hide_to_tray", bool(enabled))

    def _apply_additional_settings_state(self, plan) -> None:
        if self.discord_restart_toggle is not None:
            self._set_toggle_checked(
                self.discord_restart_toggle,
                plan.discord_restart,
            )
        if self.wssize_toggle is not None:
            self._set_toggle_checked(
                self.wssize_toggle,
                plan.wssize_enabled,
            )
        if self.debug_log_toggle is not None:
            self._set_toggle_checked(
                self.debug_log_toggle,
                plan.debug_log_enabled,
            )

    def _refresh_additional_settings(self, *, refresh: bool = False) -> None:
        self._schedule_additional_settings_reload(force=refresh)

    def _apply_pending_additional_settings_refresh(self) -> None:
        if not self._refresh_runtime.additional_settings_dirty:
            return
        if not self.is_page_ready():
            return
        self._schedule_additional_settings_reload()

    def _schedule_additional_settings_reload(self, *, force: bool = False) -> None:
        runtime = self._refresh_runtime
        if not force and not runtime.additional_settings_dirty:
            return
        if not self.isVisible():
            runtime.additional_settings_dirty = True
            self.run_when_page_ready(self._apply_pending_additional_settings_refresh)
            return
        state = runtime.additional_settings_load_state
        if state.is_busy():
            state.pending = True
            runtime.additional_settings_dirty = True
            return

        request_id = runtime.next_additional_settings_request_id()
        runtime.additional_settings_load_runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: winws1_page_runtime.create_additional_settings_worker(
                request_id,
                self._create_additional_settings_load_worker,
                launch_method=ZAPRET1_MODE,
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
        plan = winws1_page_runtime.build_additional_settings_state(state if isinstance(state, dict) else {})
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
        if bool(getattr(runtime, "additional_settings_reload_after_preset_switch_scheduled", False)):
            return
        runtime.additional_settings_reload_after_preset_switch_scheduled = True
        try:
            QTimer.singleShot(
                ADDITIONAL_SETTINGS_PRESET_SWITCH_RELOAD_DELAY_MS,
                self._run_scheduled_additional_settings_reload_after_preset_switch,
            )
        except Exception:
            self._run_scheduled_additional_settings_reload_after_preset_switch()

    def _run_scheduled_additional_settings_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        runtime.additional_settings_reload_after_preset_switch_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not runtime.additional_settings_dirty:
            return
        if not self.isVisible():
            self.run_when_page_ready(self._apply_pending_additional_settings_refresh)
            return
        self._schedule_additional_settings_reload(force=True)

    def _refresh_preset_name(self) -> None:
        self._request_top_summary_worker()

    def _schedule_top_summary_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        if bool(getattr(runtime, "top_summary_reload_after_preset_switch_scheduled", False)):
            return
        runtime.top_summary_reload_after_preset_switch_scheduled = True
        try:
            QTimer.singleShot(
                TOP_SUMMARY_PRESET_SWITCH_RELOAD_DELAY_MS,
                self._run_scheduled_top_summary_reload_after_preset_switch,
            )
        except Exception:
            self._run_scheduled_top_summary_reload_after_preset_switch()

    def _run_scheduled_top_summary_reload_after_preset_switch(self) -> None:
        runtime = self._refresh_runtime
        runtime.top_summary_reload_after_preset_switch_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.isVisible():
            self.run_when_page_ready(self._apply_pending_preset_name_refresh)
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
            or tr_catalog("page.winws1_control.preset.not_selected", language=self._ui_language, default="Не выбран")
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
        log(f"Не удалось обновить сводку Zapret 1: {error}", "WARNING")

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

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        self._request_additional_settings_save("discord_restart", bool(enabled), launch_method=ZAPRET1_MODE)

    def _on_wssize_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("wssize", bool(enabled), launch_method=ZAPRET1_MODE)

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("debug_log", bool(enabled), launch_method=ZAPRET1_MODE)

    def _request_additional_settings_save(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        runtime.mark_additional_settings_written()
        if (
            runtime.additional_settings_save_runtime.is_running()
            or bool(getattr(runtime, "additional_settings_save_start_scheduled", False))
        ):
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
        if self._refresh_runtime.additional_settings_save_pending:
            return
        InfoBar.warning(title="Ошибка", content=f"Не удалось сохранить настройку: {error}", parent=self.window())

    def _on_additional_settings_save_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        if not runtime.accept_worker_finish(worker, "additional_settings_save_request_id"):
            return
        pending = runtime.additional_settings_save_pending
        if pending and not self._cleanup_in_progress:
            next_save = pending.pop(0)
            self._schedule_additional_settings_save_start(
                str(next_save[0]),
                bool(next_save[1]),
                launch_method=str(next_save[2]),
            )

    def _schedule_additional_settings_save_start(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        if bool(getattr(runtime, "additional_settings_save_start_scheduled", False)):
            runtime.queue_additional_settings_save(setting, bool(enabled), launch_method, front=True)
            return
        runtime.additional_settings_save_start_scheduled = True
        try:
            QTimer.singleShot(
                0,
                lambda: self._run_scheduled_additional_settings_save_start(
                    str(setting or ""),
                    bool(enabled),
                    launch_method=str(launch_method or ""),
                ),
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
        self._refresh_runtime.additional_settings_save_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_additional_settings_save_worker(
            str(setting or ""),
            bool(enabled),
            launch_method=str(launch_method or ""),
        )

    def _open_preset_setup_page(self) -> None:
        self._open_preset_setup_callback()

    def set_loading(self, loading: bool, text: str = ""):
        set_progress_active_if_changed(self.progress_bar, loading)
        set_visible_if_changed(self.progress_bar, loading)
        set_visible_if_changed(self.loading_label, loading and bool(text))
        set_text_if_changed(self.loading_label, text)
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
                "subscription_is_premium",
                "subscription_days_remaining",
            },
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        if "active_preset_revision" in changed:
            self._refresh_runtime.additional_settings_dirty = True
            self._schedule_top_summary_reload_after_preset_switch()
            self._schedule_additional_settings_reload_after_preset_switch()
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
        if runtime_status_changed:
            self.set_loading(bool(state.launch_busy), str(state.launch_busy_text or ""))
        if not changed or "last_status_message" in changed:
            self._refresh_last_status_message(state)
        if runtime_status_changed:
            self.update_status(
                state.launch_phase or ("running" if state.launch_running else "stopped"),
                str(state.launch_last_error or ""),
            )
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

    def _get_current_dpi_runtime_state(self) -> tuple[str, str]:
        """Берёт текущую фазу DPI из общего store, а не из видимости кнопок."""
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                plan = control_runtime.resolve_runtime_state(
                    snapshot_state=snapshot,
                    last_known_dpi_running=self._last_known_dpi_running,
                )
                return plan.phase, plan.last_error
            except Exception:
                pass
        plan = control_runtime.resolve_runtime_state(
            snapshot_state=None,
            last_known_dpi_running=bool(getattr(self, "_last_known_dpi_running", False)),
        )
        return plan.phase, plan.last_error

    def update_status(self, state: str | bool, last_error: str = ""):
        plan = control_runtime.build_status_plan(
            state=state,
            last_error=last_error,
            language=self._ui_language,
        )
        self._last_known_dpi_running = plan.phase == "running"
        apply_status_plan(
            plan,
            status_title=self.status_title,
            status_desc=self.status_desc,
            status_dot=self.status_dot,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
        )

    def update_strategy(self, name: str):
        _ = name

    def update_current_strategy(self, name: str):
        _ = name

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
        apply_winws1_pages_language(
            language=self._ui_language,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            gui_autostart_toggle=self.gui_autostart_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
            test_card=self.test_card,
            internet_cleanup_card=self.internet_cleanup_card,
            folder_card=self.folder_card,
            docs_card=self.docs_card,
            additional_settings_card=self.additional_settings_card,
            additional_settings_notice=self.additional_settings_notice,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
            refresh_preset_name=self._refresh_preset_name,
            get_current_dpi_runtime_state=self._get_current_dpi_runtime_state,
            update_status=self.update_status,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._refresh_runtime.stop_workers(log_fn=log)
        self._stop_defender_admin_check_worker()
        self._stop_internet_cleanup_worker()
        self._stop_external_open_url_worker()
        cleanup_control_page_subscriptions(self)
