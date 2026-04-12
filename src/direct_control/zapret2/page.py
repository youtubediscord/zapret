# dpi/ui/direct_zapret2/page.py
"""Direct Zapret2 management page (Strategies landing for direct_zapret2)."""

import os
import time as _time
import webbrowser

from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ui.pages.base_page import BasePage
from ui.page_dependencies import require_page_app_context
from direct_control.zapret2.build import (
    build_z2_direct_management_section,
    build_z2_direct_preset_section,
    build_z2_direct_status_section,
)
from direct_control.zapret2.deferred_build import (
    build_z2_direct_deferred_sections,
)
from direct_control.zapret2.runtime_helpers import (
    apply_advanced_settings_plan,
    apply_direct_language,
    apply_program_settings_snapshot,
    apply_status_plan,
    run_confirmation_dialog,
    set_toggle_checked,
    show_action_result_plan,
    sync_direct_mode_label,
)
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    ResetActionButton,
    SettingsCard,
    enable_setting_card_group_auto_height,
    set_tooltip,
)
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.window_action_controller import (
    open_connection_test,
    open_folder,
    start_dpi,
    stop_and_exit,
    stop_dpi,
)
from direct_control.zapret2.controller import Zapret2DirectControlPageController

try:
    from qfluentwidgets import (
        CaptionLabel, StrongBodyLabel, SubtitleLabel, BodyLabel,
        IndeterminateProgressBar, MessageBox, InfoBar,
        SegmentedWidget, MessageBoxBase, CardWidget,
        PushButton, TransparentPushButton, FluentIcon, SettingCardGroup, PushSettingCard,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    MessageBox = None
    InfoBar = None
    MessageBoxBase = object  # type: ignore[assignment]
    SegmentedWidget = None  # type: ignore[assignment]
    CardWidget = None  # type: ignore[assignment]
    PushButton = None  # type: ignore[assignment]
    TransparentPushButton = None  # type: ignore[assignment]
    FluentIcon = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    _HAS_FLUENT_LABELS = False


class DirectLaunchModeDialog(MessageBoxBase):
    """Диалог выбора Basic / Advanced режима прямого запуска."""

    def __init__(self, current_mode: str, parent=None, language: str | None = None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.title",
                language=language,
                default="Режим прямого запуска",
            ),
            self.widget,
        )
        self.mode_seg = SegmentedWidget(self.widget)
        self.mode_seg.addItem(
            "basic",
            tr_catalog("page.z2_control.mode.basic", language=language, default="Basic"),
        )
        self.mode_seg.addItem(
            "advanced",
            tr_catalog("page.z2_control.mode.advanced", language=language, default="Advanced"),
        )
        self.mode_seg.setCurrentItem(
            current_mode if current_mode in ("basic", "advanced") else "basic"
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.description",
                language=language,
                default=(
                    "Прямой запуск поддерживает несколько режимов: упрощенный и расширенный для профи. "
                    "Настройки не сохраняются между режимами Вы можете выбрать любой. Рекомендуем начать с базового. "
                    "Бывает что базовый из-за готовых стратегий плохо пробивает сайты, тогда рекомендуем попробовать "
                    "продвинутый в котором можно более тонко настроить техники дурения."
                ),
            ),
            self.widget,
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.basic_description",
                language=language,
                default=(
                    "Basic (базовый) — готовая таблица стратегий без понятия фаз. "
                    "Собирать свои стратегии нельзя."
                ),
            ),
            self.widget,
        )
        self.adv_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.advanced_description",
                language=language,
                default=(
                    "Advanced (продвинутый) — каждая функция настраивается индивидуально, "
                    "можно выбирать несколько фаз и смешивать их друг с другом."
                ),
            ),
            self.widget,
        )
        self.basic_desc.setWordWrap(True)
        self.adv_desc.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.mode_seg)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.basic_desc)
        self.viewLayout.addWidget(self.adv_desc)
        self.yesButton.setText(tr_catalog("page.z2_control.mode.dialog.button.apply", language=language, default="Применить"))
        self.cancelButton.setText(tr_catalog("page.z2_control.mode.dialog.button.cancel", language=language, default="Отмена"))
        self.widget.setMinimumWidth(440)

    def get_mode(self) -> str:
        return self.mode_seg.currentRouteKey()


def _accent_fg_for_tokens(tokens) -> str:
    try:
        r, g, b = tokens.accent_rgb
        yiq = (r * 299 + g * 587 + b * 114) / 1000
        return "rgba(0, 0, 0, 0.90)" if yiq >= 160 else "rgba(245, 245, 245, 0.92)"
    except Exception:
        return "rgba(0, 0, 0, 0.90)"


def _log_startup_z2_control_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    from log import log as _log

    _log(f"⏱ Startup UI Section: ZAPRET2_DIRECT_CONTROL {section} {rounded}ms", "⏱ STARTUP")


class BigActionButton(PrimaryActionButton):
    """Большая кнопка запуска (акцентная, PrimaryPushButton)."""

    def __init__(self, text: str, icon_name: str | None = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    """Кнопка остановки (нейтральная, PushButton)."""

    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, parent=parent)


class Zapret2DirectControlPage(BasePage):
    """Страница управления для direct_zapret2 (главная вкладка раздела "Стратегии")."""

    navigate_to_presets = pyqtSignal()        # → PageName.ZAPRET2_USER_PRESETS
    navigate_to_direct_launch = pyqtSignal()  # → PageName.ZAPRET2_DIRECT
    navigate_to_blobs = pyqtSignal()          # → PageName.BLOBS
    direct_mode_changed = pyqtSignal(str)     # "basic" | "advanced"
    deferred_show_requested = pyqtSignal()

    def __init__(self, parent=None):
        _t_init = _time.perf_counter()
        _t_base = _time.perf_counter()
        super().__init__(
            "Управление",
            "Настройка и запуск Zapret 2. Выберите готовые пресеты-конфиги, "
            "а при необходимости выполните тонкую настройку для каждого target'а в разделе «Прямой запуск».",
            parent,
            title_key="page.z2_control.title",
            subtitle_key="page.z2_control.subtitle",
        )
        _log_startup_z2_control_metric("__init__.base_page", (_time.perf_counter() - _t_base) * 1000)

        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._program_settings_runtime_unsubscribe = None
        self._cleanup_in_progress = False
        self._program_settings_runtime_attached = False
        self._startup_showevent_profile_logged = False
        self._deferred_sections_built = False
        self._deferred_sections_hydrated = False
        self._refresh_runtime = Zapret2DirectControlPageController.create_refresh_runtime()
        self.direct_mode_label = None
        self.direct_mode_caption = None
        self.direct_open_btn = None
        self.direct_mode_btn = None
        self.program_settings_card = None
        self.auto_dpi_toggle = None
        self.defender_toggle = None
        self.max_block_toggle = None
        self.reset_program_card = None
        self.reset_program_btn = None
        self._reset_program_desc_label = None
        self.advanced_settings_section_label = None
        self.discord_restart_toggle = None
        self.wssize_toggle = None
        self.debug_log_toggle = None
        self.blobs_action_card = None
        self.blobs_open_btn = None
        self.advanced_card = None
        self.advanced_notice = None
        self.extra_section_label = None
        self.extra_card = None
        self.test_btn = None
        self.folder_btn = None
        self.docs_btn = None
        self.deferred_show_requested.connect(
            self._run_deferred_show_work,
            Qt.ConnectionType.QueuedConnection,
        )
        self._build_ui()
        self._after_ui_built()
        _log_startup_z2_control_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def _after_ui_built(self) -> None:
        try:
            self._apply_selected_preset_name_fast()
        except Exception:
            pass
        self._update_stop_winws_button_text()
        self.run_when_page_ready(self._apply_pending_direct_refresh_if_ready)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = (tokens, force)

    def _start_dpi(self) -> None:
        start_dpi(self)

    def _stop_dpi(self) -> None:
        stop_dpi(self)

    def _stop_and_exit(self) -> None:
        stop_and_exit(self)

    def _open_connection_test(self) -> None:
        open_connection_test(self)

    def _open_folder(self) -> None:
        open_folder(self)

    def _apply_pending_direct_refresh_if_ready(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.is_page_ready():
            return
        _t_show = _time.perf_counter()
        if (
            not self._deferred_sections_built
            or not self._deferred_sections_hydrated
            or bool(self._refresh_runtime.advanced_settings_dirty)
        ):
            self.deferred_show_requested.emit()
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_z2_control_metric("activation.total", (_time.perf_counter() - _t_show) * 1000)

    def _load_selected_preset_name(self) -> tuple[str, str]:
        try:
            file_name = str(self._require_app_context().preset_selection_service.get_selected_file_name("winws2") or "").strip()
        except Exception:
            file_name = ""

        if not file_name:
            return "", ""

        display_name = os.path.splitext(os.path.basename(file_name))[0].strip() or file_name
        return display_name, display_name

    def _require_app_context(self):
        return require_page_app_context(
            self,
            parent=self.parent(),
            error_message="AppContext is required for Zapret2 direct control page",
        )

    def _get_selection_service(self):
        return self._require_app_context().preset_selection_service

    def _apply_selected_preset_name_fast(self) -> None:
        default_text = tr_catalog(
            "page.z2_control.preset.not_selected",
            language=self._ui_language,
            default="Не выбран",
        )

        try:
            preset_name_text, preset_name_tooltip = self._load_selected_preset_name()
        except Exception:
            preset_name_text = ""
            preset_name_tooltip = ""

        text = str(preset_name_text or "").strip() or default_text
        tooltip = str(preset_name_tooltip or "").strip()
        self.preset_name_label.setText(text)
        set_tooltip(self.preset_name_label, tooltip)

    def _run_deferred_show_work(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.isVisible():
            return

        if not self._deferred_sections_built:
            _t_build = _time.perf_counter()
            self._build_deferred_sections()
            self._deferred_sections_built = True
            _log_startup_z2_control_metric(
                "showEvent.build_deferred_sections",
                (_time.perf_counter() - _t_build) * 1000,
            )
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._run_deferred_show_work())
            return

        if not self._deferred_sections_hydrated:
            _t_hydrate = _time.perf_counter()
            self._attach_program_settings_runtime()
            try:
                self._sync_direct_launch_mode_from_settings()
            except Exception:
                pass
            self._deferred_sections_hydrated = True
            self._schedule_advanced_settings_reload(force=True)
            _log_startup_z2_control_metric(
                "showEvent.hydrate_deferred_sections",
                (_time.perf_counter() - _t_hydrate) * 1000,
            )
            return

        _t_adv = _time.perf_counter()
        self._schedule_advanced_settings_reload()
        _log_startup_z2_control_metric(
            "showEvent.load_advanced_settings",
            (_time.perf_counter() - _t_adv) * 1000,
        )

    def _open_direct_launch_page(self) -> None:
        self.navigate_to_direct_launch.emit()

    def _build_ui(self):
        _t_total = _time.perf_counter()
        # Статус работы
        _t_status = _time.perf_counter()
        status_widgets = build_z2_direct_status_section(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent_labels=_HAS_FLUENT_LABELS,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self.status_section_label = status_widgets.section_label
        self.status_card = status_widgets.card
        self.status_dot = status_widgets.status_dot
        self.status_title = status_widgets.status_title
        self.status_desc = status_widgets.status_desc
        self.add_widget(status_widgets.card)
        _log_startup_z2_control_metric("_build_ui.status_card", (_time.perf_counter() - _t_status) * 1000)

        self.add_spacing(16)

        # Управление
        _t_control = _time.perf_counter()
        management_widgets = build_z2_direct_management_section(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent_labels=_HAS_FLUENT_LABELS,
            caption_label_cls=CaptionLabel,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            big_action_button_cls=BigActionButton,
            stop_button_cls=StopButton,
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
        _log_startup_z2_control_metric("_build_ui.control_card", (_time.perf_counter() - _t_control) * 1000)

        self.add_spacing(16)

        # ── Запуск: две вертикальные WinUI-карточки ──────────────────────
        _t_preset = _time.perf_counter()
        preset_widgets = build_z2_direct_preset_section(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            card_widget_cls=CardWidget,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            push_button_cls=PushButton,
            fluent_icon=FluentIcon,
            on_open_presets=self.navigate_to_presets.emit,
        )
        self.preset_section_label = preset_widgets.section_label
        self.preset_card = preset_widgets.card
        self.preset_name_label = preset_widgets.preset_name_label
        self.current_preset_caption = preset_widgets.current_preset_caption
        self.presets_btn = preset_widgets.presets_btn
        self.add_widget(preset_widgets.card)
        _log_startup_z2_control_metric("_build_ui.preset_card", (_time.perf_counter() - _t_preset) * 1000)
        _log_startup_z2_control_metric("_build_ui.total", (_time.perf_counter() - _t_total) * 1000)

    def _build_deferred_sections(self) -> None:
        self.add_spacing(8)
        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None  # type: ignore[assignment]

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления Zapret 2")
        deferred_widgets = build_z2_direct_deferred_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            push_button_cls=PushButton,
            transparent_push_button_cls=TransparentPushButton,
            setting_card_group_cls=SettingCardGroup,
            push_setting_card_cls=PushSettingCard,
            card_widget_cls=CardWidget,
            fluent_icon=FluentIcon,
            reset_action_button_cls=ResetActionButton,
            settings_card_cls=SettingsCard,
            win11_toggle_row_cls=Win11ToggleRow,
            on_open_direct_launch_page=self._open_direct_launch_page,
            on_open_direct_mode_dialog=self._open_direct_mode_dialog,
            on_auto_dpi_toggled=self._on_auto_dpi_toggled,
            on_defender_toggled=self._on_defender_toggled,
            on_max_blocker_toggled=self._on_max_blocker_toggled,
            on_confirm_reset_program_clicked=self._confirm_reset_program_clicked,
            on_reset_program_clicked=self._on_reset_program_clicked,
            on_discord_restart_changed=self._on_discord_restart_changed,
            on_wssize_toggled=self._on_wssize_toggled,
            on_debug_log_toggled=self._on_debug_log_toggled,
            on_navigate_to_blobs=self.navigate_to_blobs.emit,
            on_open_connection_test=self._open_connection_test,
            on_open_folder=self._open_folder,
            on_open_docs=self._open_docs,
        )

        self.direct_section_label = deferred_widgets.direct_section_label
        self.direct_card = deferred_widgets.direct_card
        self.direct_mode_label = deferred_widgets.direct_mode_label
        self.direct_mode_caption = deferred_widgets.direct_mode_caption
        self.direct_open_btn = deferred_widgets.direct_open_btn
        self.direct_mode_btn = deferred_widgets.direct_mode_btn
        self.add_widget(self.direct_card)

        self.program_settings_section_label = deferred_widgets.program_settings_section_label
        self.program_settings_card = deferred_widgets.program_settings_card
        self.auto_dpi_toggle = deferred_widgets.auto_dpi_toggle
        self.defender_toggle = deferred_widgets.defender_toggle
        self.max_block_toggle = deferred_widgets.max_block_toggle
        self.reset_program_card = deferred_widgets.reset_program_card
        self.reset_program_btn = deferred_widgets.reset_program_btn
        self._reset_program_desc_label = deferred_widgets.reset_program_desc_label
        self.add_spacing(8)
        self.add_spacing(16)
        self.add_widget(self.program_settings_card)
        if deferred_widgets.program_settings_section_label is not None:
            pass
        if deferred_widgets.reset_program_btn is not None:
            self.add_widget(self.reset_program_card)
        enable_setting_card_group_auto_height(self.program_settings_card)

        self.advanced_settings_section_label = None
        self.discord_restart_toggle = deferred_widgets.discord_restart_toggle
        self.wssize_toggle = deferred_widgets.wssize_toggle
        self.debug_log_toggle = deferred_widgets.debug_log_toggle
        self.blobs_action_card = deferred_widgets.blobs_action_card
        self.blobs_open_btn = deferred_widgets.blobs_open_btn
        self.advanced_card = deferred_widgets.advanced_card
        self.advanced_notice = deferred_widgets.advanced_notice
        self.add_spacing(16)
        self.add_widget(self.advanced_card)

        self.extra_section_label = deferred_widgets.extra_section_label
        self.extra_card = deferred_widgets.extra_card
        self.test_btn = deferred_widgets.test_btn
        self.folder_btn = deferred_widgets.folder_btn
        self.docs_btn = deferred_widgets.docs_btn
        self.add_widget(self.extra_card)

    def _apply_advanced_settings_plan(self, plan) -> None:
        apply_advanced_settings_plan(
            plan,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
        )

    def _schedule_advanced_settings_reload(self, *, force: bool = False) -> None:
        runtime = self._refresh_runtime
        if not force and not runtime.advanced_settings_dirty:
            return
        if not self.isVisible():
            runtime.advanced_settings_dirty = True
            self.run_when_page_ready(self._apply_pending_direct_refresh_if_ready)
            return
        worker = runtime.advanced_settings_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                pass

        request_id = runtime.next_advanced_settings_request_id()
        worker = Zapret2DirectControlPageController.create_advanced_settings_worker(
            request_id,
            self._require_app_context().direct_ui_snapshot_service,
            self,
        )
        runtime.advanced_settings_worker = worker
        worker.loaded.connect(self._on_advanced_settings_loaded)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_advanced_settings_loaded(self, request_id: int, state: dict) -> None:
        if not self._refresh_runtime.accept_advanced_settings_result(request_id):
            return
        plan = Zapret2DirectControlPageController.build_advanced_settings_apply_plan(state if isinstance(state, dict) else {})
        self._apply_advanced_settings_plan(plan)

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        self._refresh_runtime.mark_advanced_settings_written()
        Zapret2DirectControlPageController.save_discord_restart_setting(enabled)

    def _on_wssize_toggled(self, enabled: bool) -> None:
        self._refresh_runtime.mark_advanced_settings_written()
        Zapret2DirectControlPageController.save_wssize_enabled(
            enabled,
            app_context=self._require_app_context(),
        )

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        self._refresh_runtime.mark_advanced_settings_written()
        Zapret2DirectControlPageController.save_debug_log_enabled(
            enabled,
            app_context=self._require_app_context(),
        )

    # ==================== Direct mode UI: Basic/Advanced ====================

    def _sync_direct_launch_mode_from_settings(self) -> None:
        sync_direct_mode_label(language=self._ui_language, direct_mode_label=self.direct_mode_label)

    def _open_direct_mode_dialog(self) -> None:
        current = Zapret2DirectControlPageController.get_direct_launch_mode_setting()
        dlg = DirectLaunchModeDialog(current, self.window(), language=self._ui_language)
        if dlg.exec():
            new_mode = dlg.get_mode()
            if new_mode != current:
                self._on_direct_launch_mode_selected(new_mode)
                self.direct_mode_changed.emit(new_mode)

    def _on_direct_launch_mode_selected(self, mode: str) -> None:
        wanted = str(mode or "").strip().lower()
        if wanted not in ("basic", "advanced"):
            return

        current = Zapret2DirectControlPageController.get_direct_launch_mode_setting()
        plan = Zapret2DirectControlPageController.build_direct_mode_change_plan(
            wanted_mode=wanted,
            current_mode=current,
        )
        if plan.should_apply:
            Zapret2DirectControlPageController.apply_direct_mode_change(
                wanted_mode=wanted,
                app_context=self._require_app_context(),
                reload_host=self.parent_app,
            )
        if plan.refresh_strategy_after:
            self.update_strategy("")
        if plan.refresh_mode_label_after:
            self._sync_direct_launch_mode_from_settings()

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        set_toggle_checked(toggle, checked)

    def _confirm_reset_program_clicked(self) -> None:
        title = tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить")
        confirm_text = tr_catalog(
            "page.z2_control.button.reset_confirm",
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

    def _sync_program_settings(self) -> None:
        snapshot = self._require_app_context().program_settings_runtime_service.refresh()
        self._apply_program_settings_snapshot(snapshot)

    def _attach_program_settings_runtime(self) -> None:
        if self._program_settings_runtime_attached:
            return
        if self.auto_dpi_toggle is None:
            return
        self._program_settings_runtime_attached = True
        self._program_settings_runtime_unsubscribe = self._require_app_context().program_settings_runtime_service.subscribe(
            self._apply_program_settings_snapshot,
            emit_initial=True,
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        if self._cleanup_in_progress:
            return
        apply_program_settings_snapshot(
            snapshot,
            auto_dpi_toggle=self.auto_dpi_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
        )

    def _get_program_settings_runtime_service(self):
        return self._require_app_context().program_settings_runtime_service

    def _set_status(self, msg: str) -> None:
        try:
            status_setter = getattr(self, "set_status", None)
            if callable(status_setter):
                status_setter(msg)
        except Exception:
            pass

    def _show_action_result_plan(self, plan, toggle=None) -> None:
        show_action_result_plan(
            plan,
            window=self.window(),
            set_status=self._set_status,
            info_bar_cls=InfoBar,
            toggle=toggle,
        )

    def _run_confirmation_dialog(self, dialog_plan, toggle=None) -> bool:
        return run_confirmation_dialog(
            dialog_plan,
            message_box_cls=MessageBox,
            window=self.window(),
            toggle=toggle,
        )

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = Zapret2DirectControlPageController.save_auto_dpi(enabled)
            self._set_status(plan.message)
            InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_defender_toggled(self, disable: bool) -> None:
        start_plan = Zapret2DirectControlPageController.build_defender_toggle_start_plan(
            disable=disable,
            language=self._ui_language,
        )
        if start_plan.blocked:
            InfoBar.error(
                title=start_plan.blocked_title,
                content=start_plan.blocked_content,
                parent=self.window(),
            )
            if start_plan.blocked_revert_checked is not None:
                self._set_toggle_checked(self.defender_toggle, start_plan.blocked_revert_checked)
            return

        try:
            for dialog_plan in start_plan.confirmations:
                if not self._run_confirmation_dialog(dialog_plan, self.defender_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = Zapret2DirectControlPageController.run_defender_toggle(
                disable=disable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.defender_toggle)
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        start_plan = Zapret2DirectControlPageController.build_max_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        try:
            for dialog_plan in start_plan.confirmations:
                if not self._run_confirmation_dialog(dialog_plan, self.max_block_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = Zapret2DirectControlPageController.run_max_block_toggle(
                enable=enable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.max_block_toggle)
        finally:
            self._sync_program_settings()

    def _on_reset_program_clicked(self) -> None:
        try:
            ok, message = Zapret2DirectControlPageController.reset_startup_cache()
            if ok:
                self._set_status(message)
            else:
                InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=self.window())
        except Exception as e:
            InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {e}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _update_stop_winws_button_text(self):
        plan = Zapret2DirectControlPageController.build_stop_button_plan(language=self._ui_language)
        self.stop_winws_btn.setText(plan.text)

    def set_loading(self, loading: bool, text: str = ""):
        if _HAS_FLUENT_LABELS:
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
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={
                "launch_phase",
                "launch_running",
                "launch_busy",
                "launch_busy_text",
                "launch_last_error",
                "current_strategy_summary",
                "active_preset_revision",
                "mode_revision",
            },
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        presets_changed = "active_preset_revision" in changed
        if "mode_revision" in changed:
            self._sync_direct_launch_mode_from_settings()
        if presets_changed:
            try:
                self._apply_selected_preset_name_fast()
            except Exception:
                pass
            self._refresh_runtime.advanced_settings_dirty = True
            if self.isVisible() and self._deferred_sections_hydrated:
                self._schedule_advanced_settings_reload(force=True)
            else:
                self.run_when_page_ready(self._apply_pending_direct_refresh_if_ready)
        self.set_loading(bool(state.launch_busy), str(state.launch_busy_text or ""))
        self.update_status(
            state.launch_phase or ("running" if state.launch_running else "stopped"),
            str(state.launch_last_error or ""),
        )
        self.update_strategy(str(state.current_strategy_summary or ""))

    def update_status(self, state: str | bool, last_error: str = ""):
        plan = Zapret2DirectControlPageController.build_status_plan(
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
        apply_direct_language(
            language=self._ui_language,
            start_btn=self.start_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            presets_btn=self.presets_btn,
            direct_open_btn=self.direct_open_btn,
            direct_mode_btn=self.direct_mode_btn,
            blobs_open_btn=self.blobs_open_btn,
            test_btn=self.test_btn,
            folder_btn=self.folder_btn,
            docs_btn=self.docs_btn,
            current_preset_caption=self.current_preset_caption,
            direct_mode_caption=self.direct_mode_caption,
            advanced_notice=self.advanced_notice,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
            reset_program_card=self.reset_program_card,
            reset_program_btn=self.reset_program_btn,
            reset_program_desc_label=self._reset_program_desc_label,
            advanced_card=self.advanced_card,
            blobs_action_card=self.blobs_action_card,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
            update_stop_button_text=self._update_stop_winws_button_text,
            sync_direct_launch_mode_from_settings=self._sync_direct_launch_mode_from_settings,
        )

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            webbrowser.open(DOCS_URL)
        except Exception as e:
            InfoBar.warning(title="Документация", content=f"Не удалось открыть документацию: {e}", parent=self.window())

    def cleanup(self) -> None:
        self._cleanup_in_progress = True

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None

        unsubscribe_runtime = getattr(self, "_program_settings_runtime_unsubscribe", None)
        if callable(unsubscribe_runtime):
            try:
                unsubscribe_runtime()
            except Exception:
                pass
        self._program_settings_runtime_unsubscribe = None
