# dpi/ui/direct_zapret1/page.py
"""Direct Zapret1 management page (entry point for direct_zapret1 mode)."""

import os
import webbrowser

from PyQt6.QtCore import QTimer, pyqtSignal

from ui.pages.base_page import BasePage
from ui.page_dependencies import require_page_app_context
from direct_control.zapret1.build import (
    build_z1_direct_management_section,
    build_z1_direct_preset_section,
    build_z1_direct_status_section,
)
from direct_control.zapret1.deferred_build import (
    build_z1_direct_deferred_sections,
)
from direct_control.zapret1.runtime_helpers import (
    apply_program_settings_snapshot,
    apply_status_plan,
    apply_z1_direct_language,
    set_toggle_checked,
)
from direct_control.control_runtime_controller import ControlPageController
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    SettingsCard,
    set_tooltip,
)
from app_state.main_window_state import AppUiState, MainWindowStateStore
from direct_control.ui.control_page_shared import (
    ControlPageActionMixin,
    attach_program_settings_runtime,
    bind_control_ui_state_store,
    cleanup_control_page_subscriptions,
)
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        CaptionLabel, StrongBodyLabel,
        IndeterminateProgressBar, MessageBox, InfoBar,
        PushButton, PushSettingCard, FluentIcon, CardWidget, SettingCardGroup,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QLabel as StrongBodyLabel, QLabel as CaptionLabel  # type: ignore
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore
    MessageBox = None
    InfoBar = None
    PushButton = None
    PushSettingCard = None
    FluentIcon = None
    from PyQt6.QtWidgets import QWidget as CardWidget  # type: ignore
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT = False


class BigActionButton(PrimaryActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, parent=parent)


class Zapret1DirectControlPage(ControlPageActionMixin, BasePage):
    """Страница управления для direct_zapret1 (главная вкладка раздела «Стратегии»)."""

    navigate_to_strategies = pyqtSignal()   # → PageName.ZAPRET1_DIRECT
    navigate_to_presets = pyqtSignal()       # → PageName.ZAPRET1_USER_PRESETS
    navigate_to_blobs = pyqtSignal()         # → PageName.BLOBS

    def __init__(self, parent=None):
        super().__init__(
            "Управление Zapret 1",
            "Настройка и запуск Zapret 1 (winws.exe). Выберите стратегии для категорий "
            "или переключитесь на другой пресет.",
            parent,
            title_key="page.z1_control.title",
            subtitle_key="page.z1_control.subtitle",
        )
        self.parent_app = parent
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._program_settings_runtime_unsubscribe = None
        self._cleanup_in_progress = False
        self._last_known_dpi_running = False
        self._program_settings_runtime_attached = False
        self._deferred_sections_built = False
        self._deferred_sections_hydrated = False
        self._advanced_settings_dirty = True
        self.program_settings_card = None
        self.auto_dpi_toggle = None
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
        self.test_action_card = None
        self.folder_action_card = None
        self.docs_action_card = None
        self.open_strat_btn = None
        self.strategies_title_label = None
        self.strategies_desc_label = None
        self._build_ui()
        try:
            preset_name_text, preset_name_tooltip = self._load_preset_name()
            if preset_name_text:
                self.preset_name_label.setText(preset_name_text)
                set_tooltip(self.preset_name_label, preset_name_tooltip)
        except Exception:
            pass
        self.run_when_page_ready(self._run_deferred_show_work)

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            webbrowser.open(DOCS_URL)
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
        # ── Статус работы ──────────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.status")
        status_widgets = build_z1_direct_status_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent=_HAS_FLUENT,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.status_dot = status_widgets.status_dot
        self.status_title = status_widgets.status_title
        self.status_desc = status_widgets.status_desc
        self.add_widget(status_widgets.card)

        self.add_spacing(16)

        # ── Управление ─────────────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.management")
        management_widgets = build_z1_direct_management_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent=_HAS_FLUENT,
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

        # ── Пресет / Стратегии ──────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.presets")
        preset_widgets = build_z1_direct_preset_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_push_setting_card=PushSettingCard is not None,
            push_setting_card_cls=PushSettingCard,
            card_widget_cls=CardWidget,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            action_button_cls=ActionButton,
            on_open_presets=self.navigate_to_presets.emit,
        )
        self.preset_name_label = preset_widgets.preset_name_label
        self.preset_caption_label = preset_widgets.preset_caption_label
        self.presets_btn = preset_widgets.presets_btn
        self.add_widget(preset_widgets.card)

    def _build_deferred_sections(self) -> None:
        self.add_spacing(8)
        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления Zapret 1")
        deferred_widgets = build_z1_direct_deferred_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            has_fluent=_HAS_FLUENT,
            push_setting_card_cls=PushSettingCard,
            card_widget_cls=CardWidget,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            action_button_cls=ActionButton,
            setting_card_group_cls=SettingCardGroup,
            settings_card_cls=SettingsCard,
            win11_toggle_row_cls=Win11ToggleRow,
            on_open_strategies_page=self._open_strategies_page,
            on_auto_dpi_toggled=self._on_auto_dpi_toggled,
            on_confirm_reset_program_clicked=self._confirm_reset_program_clicked,
            on_discord_restart_changed=self._on_discord_restart_changed,
            on_wssize_toggled=self._on_wssize_toggled,
            on_debug_log_toggled=self._on_debug_log_toggled,
            on_navigate_to_blobs=self.navigate_to_blobs.emit,
            on_open_connection_test=self._open_connection_test,
            on_open_folder=self._open_folder,
            on_open_docs=self._open_docs,
        )
        self.strategies_card = deferred_widgets.strategies_card
        self.strategies_title_label = deferred_widgets.strategies_title_label
        self.strategies_desc_label = deferred_widgets.strategies_desc_label
        self.open_strat_btn = deferred_widgets.open_strat_btn
        self.add_widget(self.strategies_card)

        self.add_spacing(16)
        self.program_settings_section_label = deferred_widgets.program_settings_section_label
        self.program_settings_card = deferred_widgets.program_settings_card
        self.auto_dpi_toggle = deferred_widgets.auto_dpi_toggle
        self.reset_program_card = deferred_widgets.reset_program_card
        self.reset_program_btn = deferred_widgets.reset_program_btn
        self._reset_program_desc_label = deferred_widgets.reset_program_desc_label
        self.add_widget(self.program_settings_card)
        if self.reset_program_card is not None:
            self.add_spacing(8)
            self.add_widget(self.reset_program_card)

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
        self.test_btn = deferred_widgets.test_btn
        self.folder_btn = deferred_widgets.folder_btn
        self.docs_btn = deferred_widgets.docs_btn
        self.test_action_card = deferred_widgets.test_action_card
        self.folder_action_card = deferred_widgets.folder_action_card
        self.docs_action_card = deferred_widgets.docs_action_card
        self.add_widget(self.extra_card)

    def _attach_program_settings_runtime(self) -> None:
        attach_program_settings_runtime(
            self,
            require_app_context_fn=self._require_app_context,
            apply_snapshot_fn=self._apply_program_settings_snapshot,
            require_attr_name="auto_dpi_toggle",
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        if self._cleanup_in_progress:
            return
        apply_program_settings_snapshot(
            snapshot,
            auto_dpi_toggle=self.auto_dpi_toggle,
        )

    def _sync_program_settings(self) -> None:
        snapshot = self._require_app_context().program_settings_runtime_service.refresh()
        self._apply_program_settings_snapshot(snapshot)

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message="AppContext is required for Zapret1 direct control page",
        )

    def _get_program_settings_runtime_service(self):
        return self._require_app_context().program_settings_runtime_service

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = ControlPageController.save_auto_dpi(enabled)
            if InfoBar:
                InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _confirm_reset_program_clicked(self) -> None:
        title = tr_catalog("page.z1_control.button.reset", language=self._ui_language, default="Сбросить")
        confirm_text = tr_catalog(
            "page.z1_control.button.reset_confirm",
            language=self._ui_language,
            default="Сбросить?",
        )
        if MessageBox is not None:
            try:
                box = MessageBox(title, confirm_text, self.window())
                if not box.exec():
                    return
            except Exception:
                pass
        self._on_reset_program_clicked()

    def _on_reset_program_clicked(self) -> None:
        try:
            ok, message = ControlPageController.reset_startup_cache()
            if ok:
                self._set_status(message)
            elif InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _load_preset_name(self) -> tuple[str, str]:
        try:
            selection_service = self._require_app_context().preset_selection_service
            file_name = str(selection_service.get_selected_file_name("winws1") or "").strip()
            if file_name:
                display_name = os.path.splitext(os.path.basename(file_name))[0].strip() or file_name
                return display_name, display_name
        except Exception:
            pass

        return (
            tr_catalog("page.z1_control.preset.not_selected", language=self._ui_language, default="Не выбран"),
            "",
        )

    def _load_advanced_settings_state(self, *, refresh: bool = False) -> dict:
        try:
            return self._get_direct_ui_snapshot_service().load_advanced_settings_state(
                "direct_zapret1",
                refresh=refresh,
            )
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

    def _get_direct_ui_snapshot_service(self):
        return self._require_app_context().direct_ui_snapshot_service

    def _refresh_preset_name(self) -> None:
        text, tooltip = self._load_preset_name()
        self.preset_name_label.setText(text)
        set_tooltip(self.preset_name_label, tooltip)

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_wssize_toggled(self, enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                app_context=self._require_app_context(),
            ).set_wssize_enabled(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                app_context=self._require_app_context(),
            ).set_debug_log_enabled(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _open_strategies_page(self) -> None:
        self.navigate_to_strategies.emit()

    def set_loading(self, loading: bool, text: str = ""):
        if _HAS_FLUENT:
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
            fields={"launch_phase", "launch_running", "launch_busy", "launch_busy_text", "launch_last_error", "current_strategy_summary", "active_preset_revision"},
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
                plan = ControlPageController.resolve_runtime_state(
                    snapshot_state=snapshot,
                    last_known_dpi_running=self._last_known_dpi_running,
                )
                return plan.phase, plan.last_error
            except Exception:
                pass
        plan = ControlPageController.resolve_runtime_state(
            snapshot_state=None,
            last_known_dpi_running=bool(getattr(self, "_last_known_dpi_running", False)),
        )
        return plan.phase, plan.last_error

    def update_status(self, state: str | bool, last_error: str = ""):
        plan = ControlPageController.build_status_plan(
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
        apply_z1_direct_language(
            language=self._ui_language,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            presets_btn=self.presets_btn,
            open_strat_btn=self.open_strat_btn,
            preset_caption_label=self.preset_caption_label,
            strategies_title_label=self.strategies_title_label,
            strategies_desc_label=self.strategies_desc_label,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            test_action_card=getattr(self, "test_action_card", None),
            test_btn=self.test_btn,
            folder_action_card=getattr(self, "folder_action_card", None),
            folder_btn=self.folder_btn,
            docs_action_card=getattr(self, "docs_action_card", None),
            docs_btn=self.docs_btn,
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
