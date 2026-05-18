# dpi/ui/zapret1_mode/page.py
"""Zapret 1 mode management page (entry point for zapret1_mode mode)."""

from PyQt6.QtCore import QTimer

from ui.pages.base_page import BasePage
from settings.mode import EXE_NAME_WINWS1, ZAPRET1_MODE
from presets.ui.control.zapret1.build import (
    build_winws1_pages_management_section,
    build_winws1_presets_section,
    build_winws1_pages_status_section,
)
from presets.ui.control.zapret1.deferred_build import (
    build_winws1_pages_deferred_sections,
)
from presets.ui.control.zapret1.runtime_helpers import (
    apply_program_settings_snapshot,
    apply_status_plan,
    apply_winws1_pages_language,
    save_debug_log_enabled,
    save_wssize_enabled,
    set_toggle_checked,
)
import presets.ui.control.control_runtime as control_runtime
from presets.ui.control.windows_features.runtime import ControlPageWindowsFeatureMixin
from ui.fluent_widgets import (
    ActionButton,
    PrimaryActionButton,
    set_tooltip,
)
from app.state_store import AppUiState, MainWindowStateStore
from presets.ui.control.control_page_shared import (
    ControlPageActionMixin,
    bind_control_ui_state_store,
    cleanup_control_page_subscriptions,
)
from app.text_catalog import tr as tr_catalog
from presets.ui.control.top_summary_widget import ControlTopSummaryWidget

from qfluentwidgets import (
    CaptionLabel, StrongBodyLabel,
    IndeterminateProgressBar, InfoBar,
    PushSettingCard, SettingCardGroup,
)


class BigActionButton(PrimaryActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, parent=parent)


class Zapret1ModeControlPage(ControlPageWindowsFeatureMixin, ControlPageActionMixin, BasePage):
    """Страница управления для zapret1_mode."""

    def __init__(
        self,
        parent=None,
        *,
        presets_feature,
        profile_feature,
        runtime_feature,
        program_settings_feature,
        set_status,
        request_exit,
        open_connection_test,
        open_folder,
        open_presets,
        open_preset_setup,
        open_blobs,
        open_premium,
        external_actions_feature,
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
        self._presets = presets_feature
        self._profile = profile_feature
        self._runtime_feature = runtime_feature
        self._program_settings = program_settings_feature
        self._set_status_callback = set_status
        self._request_exit_callback = request_exit
        self._open_connection_test_callback = open_connection_test
        self._open_folder_callback = open_folder
        self._open_presets_callback = open_presets
        self._open_preset_setup_callback = open_preset_setup
        self._open_blobs_callback = open_blobs
        self._open_premium_callback = open_premium
        self._external_actions = external_actions_feature
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._program_settings_runtime_unsubscribe = None
        self._cleanup_in_progress = False
        self._last_known_dpi_running = False
        self._program_settings_runtime_attached = False
        self._deferred_sections_built = False
        self._deferred_sections_hydrated = False
        self._advanced_settings_dirty = True
        self.top_summary = None
        self.program_settings_card = None
        self.auto_dpi_toggle = None
        self.hide_to_tray_toggle = None
        self.defender_toggle = None
        self.max_block_toggle = None
        self.discord_restart_toggle = None
        self.wssize_toggle = None
        self.debug_log_toggle = None
        self.blobs_action_card = None
        self.blobs_open_btn = None
        self.advanced_card = None
        self.advanced_notice = None
        self.extra_card = None
        self.test_btn = None
        self.folder_btn = None
        self.docs_btn = None
        self.test_card = None
        self.folder_card = None
        self.docs_card = None
        self.preset_setup_card = None
        self.preset_setup_open_btn = None
        self._build_ui()
        self.bind_ui_state_store(ui_state_store)
        try:
            preset_name_text, preset_name_tooltip = self._load_preset_name()
            if preset_name_text:
                self.preset_name_label.setText(preset_name_text)
                set_tooltip(self.preset_name_label, preset_name_tooltip)
                if self.top_summary is not None:
                    self.top_summary.set_preset(preset_name_text)
        except Exception:
            pass
        self.run_when_page_ready(self._run_deferred_show_work)

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            self._external_actions.open_url(DOCS_URL)
        except Exception:
            pass

    def _apply_pending_preset_name_refresh(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.is_page_ready():
            return
        try:
            self._refresh_preset_name()
        except Exception:
            pass

    def _run_deferred_show_work(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.isVisible():
            return
        if not self._deferred_sections_built:
            self._build_deferred_sections()
            self._deferred_sections_built = True
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._run_deferred_show_work())
            return
        if not self._deferred_sections_hydrated:
            self._attach_program_settings_runtime()
            self._refresh_advanced_settings()
            self._deferred_sections_hydrated = True
            return
        self._apply_pending_advanced_settings_refresh()

    def _build_ui(self):
        self.top_summary = ControlTopSummaryWidget(
            language=self._ui_language,
            mode_value="Zapret 1",
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
            big_action_button_cls=BigActionButton,
            stop_button_cls=StopButton,
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

        self.add_spacing(16)

        # ── Ветка пресета: выбор пресета отдельно от настройки его профилей ──
        self.add_section_title(text_key="page.winws1_control.section.presets")
        preset_widgets = build_winws1_presets_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            push_setting_card_cls=PushSettingCard,
            on_open_presets=self._open_presets_callback,
        )
        self.preset_name_label = preset_widgets.title_label
        self.preset_caption_label = preset_widgets.caption_label
        self.presets_btn = preset_widgets.button
        self.add_widget(preset_widgets.card)

    def _build_deferred_sections(self) -> None:
        self.add_spacing(8)
        from ui.widgets.win11_controls import Win11ToggleRow

        deferred_widgets = build_winws1_pages_deferred_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            push_setting_card_cls=PushSettingCard,
            setting_card_group_cls=SettingCardGroup,
            win11_toggle_row_cls=Win11ToggleRow,
            on_open_preset_setup_page=self._open_preset_setup_page,
            on_auto_dpi_toggled=self._on_auto_dpi_toggled,
            on_hide_to_tray_toggled=self._on_hide_to_tray_toggled,
            on_defender_toggled=self._on_defender_toggled,
            on_max_blocker_toggled=self._on_max_blocker_toggled,
            on_discord_restart_changed=self._on_discord_restart_changed,
            on_wssize_toggled=self._on_wssize_toggled,
            on_debug_log_toggled=self._on_debug_log_toggled,
            on_navigate_to_blobs=self._open_blobs_callback,
            on_open_connection_test=self._open_connection_test,
            on_open_folder=self._open_folder,
            on_open_docs=self._open_docs,
        )
        self.preset_setup_card = deferred_widgets.preset_setup_card
        self.preset_setup_open_btn = deferred_widgets.preset_setup_open_btn
        self.add_widget(self.preset_setup_card)

        self.add_spacing(16)
        self.program_settings_section_label = deferred_widgets.program_settings_section_label
        self.program_settings_card = deferred_widgets.program_settings_card
        self.auto_dpi_toggle = deferred_widgets.auto_dpi_toggle
        self.hide_to_tray_toggle = deferred_widgets.hide_to_tray_toggle
        self.defender_toggle = deferred_widgets.defender_toggle
        self.max_block_toggle = deferred_widgets.max_block_toggle
        self.add_widget(self.program_settings_card)

        self.add_spacing(16)
        self.advanced_card = deferred_widgets.advanced_card
        self.advanced_notice = deferred_widgets.advanced_notice
        self.discord_restart_toggle = deferred_widgets.discord_restart_toggle
        self.wssize_toggle = deferred_widgets.wssize_toggle
        self.debug_log_toggle = deferred_widgets.debug_log_toggle
        self.blobs_action_card = deferred_widgets.blobs_action_card
        self.blobs_open_btn = deferred_widgets.blobs_open_btn
        self.add_widget(self.advanced_card)

        self.add_spacing(16)
        self.extra_card = deferred_widgets.extra_card
        self.test_card = deferred_widgets.test_card
        self.folder_card = deferred_widgets.folder_card
        self.docs_card = deferred_widgets.docs_card
        self.test_btn = self.test_card.button
        self.folder_btn = self.folder_card.button
        self.docs_btn = self.docs_card.button
        self.add_widget(self.extra_card)

    def _attach_program_settings_runtime(self) -> None:
        self._program_settings.attach_program_settings_runtime(
            self,
            apply_snapshot_fn=self._apply_program_settings_snapshot,
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        if self._cleanup_in_progress:
            return
        apply_program_settings_snapshot(
            snapshot,
            auto_dpi_toggle=self.auto_dpi_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
        )

    def _sync_program_settings(self) -> None:
        snapshot = self._program_settings.refresh_program_settings_snapshot()
        if snapshot is not None:
            self._apply_program_settings_snapshot(snapshot)

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = self._program_settings.set_auto_dpi_enabled(enabled)
            InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_hide_to_tray_toggled(self, enabled: bool) -> None:
        try:
            self._program_settings.set_hide_to_tray_on_minimize_close(bool(enabled))
        finally:
            self._sync_program_settings()

    def _load_preset_name(self) -> tuple[str, str]:
        try:
            display = self._presets.get_selected_source_preset_display(
                ZAPRET1_MODE,
            )
            if display[0]:
                return display
        except Exception:
            pass

        return (
            tr_catalog("page.winws1_control.preset.not_selected", language=self._ui_language, default="Не выбран"),
            "",
        )

    def _load_advanced_settings_state(self, *, refresh: bool = False) -> dict:
        _ = refresh
        try:
            return self._profile.get_advanced_settings_state(ZAPRET1_MODE)
        except Exception:
            return {}

    def _apply_advanced_settings_state(self, state: dict | None) -> None:
        payload = state if isinstance(state, dict) else {}
        if self.discord_restart_toggle is not None:
            self._set_toggle_checked(
                self.discord_restart_toggle,
                bool(payload.get("discord_restart", True)),
            )
        if self.wssize_toggle is not None:
            self._set_toggle_checked(
                self.wssize_toggle,
                bool(payload.get("wssize_enabled", False)),
            )
        if self.debug_log_toggle is not None:
            self._set_toggle_checked(
                self.debug_log_toggle,
                bool(payload.get("debug_log_enabled", False)),
            )
        self._advanced_settings_dirty = False

    def _refresh_advanced_settings(self, *, refresh: bool = False) -> None:
        self._apply_advanced_settings_state(
            self._load_advanced_settings_state(refresh=refresh)
        )

    def _apply_pending_advanced_settings_refresh(self) -> None:
        if not self._advanced_settings_dirty:
            return
        if not self._deferred_sections_hydrated:
            return
        if not self.is_page_ready():
            return
        try:
            self._refresh_advanced_settings()
        except Exception:
            pass

    def _refresh_preset_name(self) -> None:
        text, tooltip = self._load_preset_name()
        self.preset_name_label.setText(text)
        set_tooltip(self.preset_name_label, tooltip)
        if self.top_summary is not None:
            self.top_summary.set_preset(text)

    def _load_enabled_profile_count(self) -> int | None:
        try:
            return int(self._profile.count_enabled_profiles(ZAPRET1_MODE))
        except Exception:
            return None

    def _refresh_top_summary(self, state: AppUiState | None = None) -> None:
        summary = self.top_summary
        if summary is None:
            return
        preset_text, _tooltip = self._load_preset_name()
        summary.set_preset(preset_text)
        summary.set_profile_count(self._load_enabled_profile_count())
        snapshot = state
        if snapshot is None and self._ui_state_store is not None:
            try:
                snapshot = self._ui_state_store.snapshot()
            except Exception:
                snapshot = None
        summary.set_premium(
            is_premium=bool(getattr(snapshot, "subscription_is_premium", False)),
            days_remaining=getattr(snapshot, "subscription_days_remaining", None),
        )

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_wssize_toggled(self, enabled: bool) -> None:
        try:
            save_wssize_enabled(
                bool(enabled),
                profile_feature=self._profile,
                runtime_feature=self._runtime_feature,
            )
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        try:
            save_debug_log_enabled(
                bool(enabled),
                profile_feature=self._profile,
                runtime_feature=self._runtime_feature,
            )
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _open_preset_setup_page(self) -> None:
        self._open_preset_setup_callback()

    def set_loading(self, loading: bool, text: str = ""):
        if loading:
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
        self.progress_bar.setVisible(loading)
        self.loading_label.setVisible(loading and bool(text))
        self.loading_label.setText(text)
        self.start_btn.setEnabled(not loading)
        self.stop_winws_btn.setEnabled(not loading)
        self.stop_and_exit_btn.setEnabled(not loading)

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
            self._advanced_settings_dirty = True
            self._refresh_preset_name()
            if self.isVisible():
                if self._deferred_sections_hydrated:
                    self._refresh_advanced_settings()
            else:
                self.run_when_page_ready(self._apply_pending_preset_name_refresh)
                self.run_when_page_ready(self._apply_pending_advanced_settings_refresh)
        if (
            not changed
            or "active_preset_revision" in changed
            or "preset_content_revision" in changed
            or "subscription_is_premium" in changed
            or "subscription_days_remaining" in changed
        ):
            self._refresh_top_summary(state)
        self.set_loading(bool(state.launch_busy), str(state.launch_busy_text or ""))
        self.update_status(
            state.launch_phase or ("running" if state.launch_running else "stopped"),
            str(state.launch_last_error or ""),
        )
        self.update_strategy(str(state.current_strategy_summary or ""))

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
        apply_winws1_pages_language(
            language=self._ui_language,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            presets_btn=self.presets_btn,
            preset_setup_open_btn=self.preset_setup_open_btn,
            preset_caption_label=self.preset_caption_label,
            preset_setup_card=self.preset_setup_card,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
            test_card=self.test_card,
            folder_card=self.folder_card,
            docs_card=self.docs_card,
            advanced_card=self.advanced_card,
            advanced_notice=self.advanced_notice,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
            blobs_action_card=self.blobs_action_card,
            blobs_open_btn=self.blobs_open_btn,
            refresh_preset_name=self._refresh_preset_name,
            get_current_dpi_runtime_state=self._get_current_dpi_runtime_state,
            update_status=self.update_status,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        cleanup_control_page_subscriptions(self)
