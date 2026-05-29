# dpi/ui/zapret2_mode/page.py
"""Zapret 2 mode management page (Strategies landing for zapret2_mode)."""

import time as _time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ui.pages.base_page import BasePage
from settings.mode import ZAPRET2_MODE
from presets.ui.control.zapret2.build import (
    build_winws2_pages_management_section,
    build_winws2_pages_status_section,
)
from presets.ui.control.zapret2.deferred_build import (
    build_winws2_pages_deferred_sections,
)
from presets.ui.control.zapret2.runtime_helpers import (
    apply_additional_settings_state,
    apply_profile_language,
    apply_program_settings_snapshot,
    apply_status_plan,
    set_toggle_checked,
    sync_profile_ui_mode_label,
)
from presets.ui.control.shared_builders import build_last_status_message_card_common
from ui.fluent_widgets import (
    enable_setting_card_group_auto_height,
)
from app.state_store import AppUiState, MainWindowStateStore
from presets.ui.control.control_page_shared import (
    ControlPageActionMixin,
    bind_control_ui_state_store,
    cleanup_control_page_subscriptions,
)
from presets.ui.control.control_page_runtime_shared import apply_last_status_message
from app.ui_texts import tr as tr_catalog
from presets.ui.control.windows_features.runtime import ControlPageWindowsFeatureMixin
from presets.ui.control.top_summary_widget import ControlTopSummaryWidget
from presets.ui.control.additional_settings_runtime import (
    create_additional_settings_save_worker as create_control_additional_settings_save_worker,
    create_additional_settings_worker as create_control_additional_settings_worker,
    create_top_summary_worker as create_control_top_summary_worker,
)
import presets.ui.control.zapret2.page_runtime as zapret2_page_runtime
from log.log import log

from qfluentwidgets import (
    CaptionLabel, StrongBodyLabel, SubtitleLabel, BodyLabel,
    IndeterminateProgressBar, InfoBar,
    SegmentedWidget, MessageBoxBase,
    PrimaryPushButton, PushButton, SettingCardGroup, PushSettingCard,
)


STARTUP_DEFERRED_SECTIONS_AFTER_INTERACTIVE_MS = 1_500
STARTUP_DEFERRED_SECTIONS_AFTER_POST_INIT_MS = 5_000
STARTUP_TOP_SUMMARY_AFTER_INTERACTIVE_MS = 350
STARTUP_INITIAL_UI_STATE_AFTER_INTERACTIVE_MS = 350
TOP_SUMMARY_PROFILE_RETRY_MS = 750
TOP_SUMMARY_PROFILE_RETRY_LIMIT = 10


class ProfileUiModeDialog(MessageBoxBase):
    """Диалог выбора Basic / Advanced режима режима профилей."""

    def __init__(self, current_mode: str, parent=None, language: str | None = None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(
            tr_catalog(
                "page.winws2_control.mode.dialog.title",
                language=language,
                default="Режим отображения профилей",
            ),
            self.widget,
        )
        self.mode_seg = SegmentedWidget(self.widget)
        self.mode_seg.addItem(
            "basic",
            tr_catalog("page.winws2_control.mode.basic", language=language, default="Basic"),
        )
        self.mode_seg.addItem(
            "advanced",
            tr_catalog("page.winws2_control.mode.advanced", language=language, default="Advanced"),
        )
        self.mode_seg.setCurrentItem(
            current_mode if current_mode in ("basic", "advanced") else "basic"
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.winws2_control.mode.dialog.description",
                language=language,
                default=(
                    "Профили поддерживают несколько режимов: упрощённый и расширенный. "
                    "Настройки не переносятся между режимами, поэтому можно выбрать любой. "
                    "Рекомендуем начать с базового. Если базовый режим с готовыми стратегиями плохо открывает сайты, "
                    "попробуйте продвинутый: там можно тоньше настроить техники дурения."
                ),
            ),
            self.widget,
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.winws2_control.mode.dialog.basic_description",
                language=language,
                default=(
                    "Basic (базовый) — выбор готовой стратегии без настройки фаз. "
                    "Свой набор аргументов в этом режиме собрать нельзя."
                ),
            ),
            self.widget,
        )
        self.adv_desc = BodyLabel(
            tr_catalog(
                "page.winws2_control.mode.dialog.advanced_description",
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
        self.yesButton.setText(tr_catalog("page.winws2_control.mode.dialog.button.apply", language=language, default="Применить"))
        self.cancelButton.setText(tr_catalog("page.winws2_control.mode.dialog.button.cancel", language=language, default="Отмена"))
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


def _log_startup_winws2_control_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    from log.log import log as _log


    _log(f"⏱ Startup UI Section: ZAPRET2_MODE_CONTROL {section} {rounded}ms", "⏱ STARTUP")


class Zapret2ModeControlPage(ControlPageWindowsFeatureMixin, ControlPageActionMixin, BasePage):
    """Главная страница управления для Zapret 2."""

    deferred_show_requested = pyqtSignal()

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
        self._program_settings_runtime_attached = False
        self._startup_showevent_profile_logged = False
        self._deferred_sections_built = False
        self._deferred_sections_hydrated = False
        self._startup_deferred_sections_waiting = False
        self._startup_deferred_sections_allowed = False
        self._startup_top_summary_waiting = False
        self._startup_initial_ui_state_waiting = False
        self._top_summary_profile_retry_count = 0
        self._top_summary_profile_retry_pending = False
        self._refresh_runtime = zapret2_page_runtime.create_refresh_runtime()
        self.profile_ui_mode_label = None
        self.profile_ui_mode_caption = None
        self.top_summary = None
        self.profile_ui_mode_btn = None
        self.program_settings_card = None
        self.auto_dpi_toggle = None
        self.hide_to_tray_toggle = None
        self.defender_toggle = None
        self.max_block_toggle = None
        self.additional_settings_section_label = None
        self.discord_restart_toggle = None
        self.wssize_toggle = None
        self.debug_log_toggle = None
        self.blobs_action_card = None
        self.blobs_open_btn = None
        self.additional_settings_card = None
        self.additional_settings_notice = None
        self.last_status_message_card = None
        self.last_status_message_dot = None
        self.last_status_message_title = None
        self.last_status_message_label = None
        self.extra_section_label = None
        self.extra_card = None
        self.test_card = None
        self.folder_card = None
        self.docs_card = None
        self.test_btn = None
        self.folder_btn = None
        self.docs_btn = None
        self.deferred_show_requested.connect(
            self._run_deferred_show_work,
            Qt.ConnectionType.QueuedConnection,
        )
        self._build_ui()
        self.bind_ui_state_store(ui_state_store)
        self._after_ui_built()
        _log_startup_winws2_control_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def _after_ui_built(self) -> None:
        if self._startup_can_refresh_top_summary():
            try:
                self._apply_selected_preset_name_fast()
            except Exception:
                pass
        else:
            self._wait_for_startup_interactive_before_top_summary()
        self._update_stop_winws_button_text()
        self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = (tokens, force)

    def _apply_pending_mode_refresh_if_ready(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.is_page_ready():
            return
        _t_show = _time.perf_counter()
        if (
            not self._deferred_sections_built
            or not self._deferred_sections_hydrated
            or bool(self._refresh_runtime.additional_settings_dirty)
        ):
            if not self._startup_can_run_deferred_sections():
                self._wait_for_startup_interactive_before_deferred_sections()
                if not self._startup_showevent_profile_logged:
                    self._startup_showevent_profile_logged = True
                    _log_startup_winws2_control_metric("activation.total", (_time.perf_counter() - _t_show) * 1000)
                return
            self.deferred_show_requested.emit()
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_winws2_control_metric("activation.total", (_time.perf_counter() - _t_show) * 1000)

    def _startup_can_run_deferred_sections(self) -> bool:
        try:
            state = getattr(self.window(), "startup_state", None)
        except Exception:
            return True
        if state is None:
            return True
        if not bool(getattr(state, "interactive_logged", False)):
            return False
        if not bool(getattr(state, "post_init_ready", False)):
            return False
        return bool(self._startup_deferred_sections_allowed)

    def _wait_for_startup_interactive_before_deferred_sections(self) -> None:
        if bool(self._startup_deferred_sections_waiting):
            return
        self._startup_deferred_sections_waiting = True
        try:
            state = getattr(self.window(), "startup_state", None)
            if state is not None and bool(getattr(state, "interactive_logged", False)):
                if bool(getattr(state, "post_init_ready", False)):
                    self._schedule_deferred_sections_after_post_init()
                else:
                    self._wait_for_startup_post_init_before_deferred_sections()
                return
        except Exception:
            pass
        try:
            signal = getattr(self.window(), "startup_interactive_ready", None)
            signal.connect(
                self._on_startup_interactive_ready_for_deferred_sections,
                Qt.ConnectionType.QueuedConnection,
            )
        except Exception:
            QTimer.singleShot(
                STARTUP_DEFERRED_SECTIONS_AFTER_INTERACTIVE_MS,
                self._request_deferred_sections_after_startup,
            )

    def _on_startup_interactive_ready_for_deferred_sections(self, *_args) -> None:
        if self._cleanup_in_progress:
            return
        try:
            state = getattr(self.window(), "startup_state", None)
            if state is not None and bool(getattr(state, "post_init_ready", False)):
                self._schedule_deferred_sections_after_post_init()
                return
        except Exception:
            pass
        self._wait_for_startup_post_init_before_deferred_sections()

    def _wait_for_startup_post_init_before_deferred_sections(self) -> None:
        try:
            signal = getattr(self.window(), "startup_post_init_ready", None)
            signal.connect(
                self._on_startup_post_init_ready_for_deferred_sections,
                Qt.ConnectionType.QueuedConnection,
            )
        except Exception:
            QTimer.singleShot(
                STARTUP_DEFERRED_SECTIONS_AFTER_INTERACTIVE_MS,
                self._request_deferred_sections_after_startup,
            )

    def _on_startup_post_init_ready_for_deferred_sections(self, *_args) -> None:
        self._schedule_deferred_sections_after_post_init()

    def _schedule_deferred_sections_after_post_init(self) -> None:
        QTimer.singleShot(
            STARTUP_DEFERRED_SECTIONS_AFTER_POST_INIT_MS,
            self._request_deferred_sections_after_startup,
        )

    def _request_deferred_sections_after_startup(self) -> None:
        self._startup_deferred_sections_waiting = False
        self._startup_deferred_sections_allowed = True
        if self._cleanup_in_progress:
            return
        self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)

    def _startup_can_refresh_top_summary(self) -> bool:
        try:
            state = getattr(self.window(), "startup_state", None)
        except Exception:
            return True
        if state is None:
            return True
        return bool(getattr(state, "interactive_logged", False))

    def _startup_can_apply_initial_ui_state(self) -> bool:
        try:
            state = getattr(self.window(), "startup_state", None)
        except Exception:
            return True
        if state is None:
            return True
        return bool(getattr(state, "interactive_logged", False))

    def _wait_for_startup_interactive_before_top_summary(self) -> None:
        if bool(self._startup_top_summary_waiting):
            return
        self._startup_top_summary_waiting = True
        try:
            signal = getattr(self.window(), "startup_interactive_ready", None)
            signal.connect(
                self._on_startup_interactive_ready_for_top_summary,
                Qt.ConnectionType.QueuedConnection,
            )
        except Exception:
            QTimer.singleShot(
                STARTUP_TOP_SUMMARY_AFTER_INTERACTIVE_MS,
                self._request_top_summary_after_startup,
            )

    def _on_startup_interactive_ready_for_top_summary(self, *_args) -> None:
        QTimer.singleShot(
            STARTUP_TOP_SUMMARY_AFTER_INTERACTIVE_MS,
            self._request_top_summary_after_startup,
        )

    def _request_top_summary_after_startup(self) -> None:
        self._startup_top_summary_waiting = False
        if self._cleanup_in_progress:
            return
        self.run_when_page_ready(self._refresh_top_summary_after_startup)

    def _wait_for_startup_interactive_before_initial_ui_state(self) -> None:
        if bool(self._startup_initial_ui_state_waiting):
            return
        self._startup_initial_ui_state_waiting = True
        try:
            state = getattr(self.window(), "startup_state", None)
            if state is not None and bool(getattr(state, "interactive_logged", False)):
                QTimer.singleShot(
                    STARTUP_INITIAL_UI_STATE_AFTER_INTERACTIVE_MS,
                    self._request_initial_ui_state_after_startup,
                )
                return
        except Exception:
            pass
        try:
            signal = getattr(self.window(), "startup_interactive_ready", None)
            signal.connect(
                self._on_startup_interactive_ready_for_initial_ui_state,
                Qt.ConnectionType.QueuedConnection,
            )
        except Exception:
            QTimer.singleShot(
                STARTUP_INITIAL_UI_STATE_AFTER_INTERACTIVE_MS,
                self._request_initial_ui_state_after_startup,
            )

    def _on_startup_interactive_ready_for_initial_ui_state(self, *_args) -> None:
        QTimer.singleShot(
            STARTUP_INITIAL_UI_STATE_AFTER_INTERACTIVE_MS,
            self._request_initial_ui_state_after_startup,
        )

    def _request_initial_ui_state_after_startup(self) -> None:
        self._startup_initial_ui_state_waiting = False
        if self._cleanup_in_progress:
            return
        store = self._ui_state_store
        if store is None:
            return
        try:
            state = store.snapshot()
        except Exception:
            return
        self._on_ui_state_changed(state, frozenset())

    def _refresh_top_summary_after_startup(self) -> None:
        _t_summary = _time.perf_counter()
        self._refresh_top_summary()
        _log_startup_winws2_control_metric(
            "startup.refresh_top_summary_after_interactive",
            (_time.perf_counter() - _t_summary) * 1000,
        )

    def _apply_selected_preset_name_fast(self) -> None:
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
        worker = runtime.top_summary_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    runtime.top_summary_pending = True
                    return
            except Exception:
                runtime.top_summary_worker = None

        request_id = runtime.next_top_summary_request_id()
        worker = create_control_top_summary_worker(
            request_id,
            self._presets,
            self._profile,
            launch_method=ZAPRET2_MODE,
            parent=self,
        )
        runtime.top_summary_worker = worker
        worker.loaded.connect(self._on_top_summary_loaded)
        worker.failed.connect(self._on_top_summary_failed)
        worker.finished.connect(lambda w=worker: self._on_top_summary_worker_finished(w))
        worker.start()

    def _on_top_summary_loaded(self, request_id: int, state) -> None:
        runtime = self._refresh_runtime
        if request_id != runtime.top_summary_request_id or self._cleanup_in_progress:
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
        summary.set_profile_count(profile_count)
        if profile_count is None:
            self._schedule_top_summary_profile_retry()
        else:
            self._top_summary_profile_retry_count = 0
            self._top_summary_profile_retry_pending = False

    def _on_top_summary_failed(self, request_id: int, error: str) -> None:
        if request_id != self._refresh_runtime.top_summary_request_id or self._cleanup_in_progress:
            return
        log(f"Не удалось обновить сводку Zapret 2: {error}", "WARNING")

    def _on_top_summary_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        if runtime.top_summary_worker is worker:
            runtime.top_summary_worker = None
        worker.deleteLater()
        if runtime.top_summary_pending and not self._cleanup_in_progress:
            runtime.top_summary_pending = False
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
        summary.set_premium(
            is_premium=bool(getattr(snapshot, "subscription_is_premium", False)),
            days_remaining=getattr(snapshot, "subscription_days_remaining", None),
        )
        self._request_top_summary_worker()

    def _run_deferred_show_work(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.isVisible():
            return

        if not self._deferred_sections_built:
            _t_build = _time.perf_counter()
            self._build_deferred_sections()
            self._deferred_sections_built = True
            _log_startup_winws2_control_metric(
                "showEvent.build_deferred_sections",
                (_time.perf_counter() - _t_build) * 1000,
            )
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._run_deferred_show_work())
            return

        if not self._deferred_sections_hydrated:
            _t_hydrate = _time.perf_counter()
            self._attach_program_settings_runtime()
            try:
                self._sync_profile_ui_mode_from_settings()
            except Exception:
                pass
            self._deferred_sections_hydrated = True
            self._schedule_additional_settings_reload(force=True)
            _log_startup_winws2_control_metric(
                "showEvent.hydrate_deferred_sections",
                (_time.perf_counter() - _t_hydrate) * 1000,
            )
            return

        _t_adv = _time.perf_counter()
        self._schedule_additional_settings_reload()
        _log_startup_winws2_control_metric(
            "showEvent.load_additional_settings",
            (_time.perf_counter() - _t_adv) * 1000,
        )

    def _open_preset_setup_page(self) -> None:
        self._open_preset_setup_callback()

    def _build_ui(self):
        _t_total = _time.perf_counter()
        self.top_summary = ControlTopSummaryWidget(
            language=self._ui_language,
            mode_value="Zapret 2",
            initial_icon_delay_ms=STARTUP_DEFERRED_SECTIONS_AFTER_INTERACTIVE_MS,
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

        _log_startup_winws2_control_metric("_build_ui.total", (_time.perf_counter() - _t_total) * 1000)

    def _build_deferred_sections(self) -> None:
        self.add_spacing(8)
        from ui.widgets.win11_controls import Win11ToggleRow

        deferred_widgets = build_winws2_pages_deferred_sections(
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            setting_card_group_cls=SettingCardGroup,
            push_setting_card_cls=PushSettingCard,
            win11_toggle_row_cls=Win11ToggleRow,
            on_open_profile_ui_mode_dialog=self._open_profile_ui_mode_dialog,
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

        self.profile_ui_mode_label = deferred_widgets.profile_ui_mode_label
        self.profile_ui_mode_caption = deferred_widgets.profile_ui_mode_caption
        self.profile_ui_mode_btn = deferred_widgets.profile_ui_mode_btn

        self.program_settings_section_label = deferred_widgets.program_settings_section_label
        self.program_settings_card = deferred_widgets.program_settings_card
        self.auto_dpi_toggle = deferred_widgets.auto_dpi_toggle
        self.hide_to_tray_toggle = deferred_widgets.hide_to_tray_toggle
        self.defender_toggle = deferred_widgets.defender_toggle
        self.max_block_toggle = deferred_widgets.max_block_toggle
        self.add_spacing(8)
        self.add_spacing(16)
        self.add_widget(self.program_settings_card)
        enable_setting_card_group_auto_height(self.program_settings_card)

        self.additional_settings_section_label = None
        self.discord_restart_toggle = deferred_widgets.discord_restart_toggle
        self.wssize_toggle = deferred_widgets.wssize_toggle
        self.debug_log_toggle = deferred_widgets.debug_log_toggle
        self.blobs_action_card = deferred_widgets.blobs_action_card
        self.blobs_open_btn = deferred_widgets.blobs_open_btn
        self.additional_settings_card = deferred_widgets.additional_settings_card
        self.additional_settings_notice = deferred_widgets.additional_settings_notice
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
        self.extra_section_label = deferred_widgets.extra_section_label
        self.extra_card = deferred_widgets.extra_card
        self.test_card = deferred_widgets.test_card
        self.folder_card = deferred_widgets.folder_card
        self.docs_card = deferred_widgets.docs_card
        self.test_btn = self.test_card.button
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
        runtime = self._refresh_runtime
        if not force and not runtime.additional_settings_dirty:
            return
        if not self.isVisible():
            runtime.additional_settings_dirty = True
            self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)
            return
        worker = runtime.additional_settings_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                pass

        request_id = runtime.next_additional_settings_request_id()
        worker = create_control_additional_settings_worker(
            request_id,
            self._profile,
            launch_method=ZAPRET2_MODE,
            parent=self,
        )
        runtime.additional_settings_worker = worker
        worker.loaded.connect(self._on_additional_settings_loaded)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_additional_settings_loaded(self, request_id: int, state: dict) -> None:
        if not self._refresh_runtime.accept_additional_settings_result(request_id):
            return
        plan = zapret2_page_runtime.build_additional_settings_state(state if isinstance(state, dict) else {})
        self._apply_additional_settings_state(plan)

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        self._request_additional_settings_save("discord_restart", bool(enabled), launch_method=ZAPRET2_MODE)

    def _on_wssize_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("wssize", bool(enabled), launch_method=ZAPRET2_MODE)

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        self._request_additional_settings_save("debug_log", bool(enabled), launch_method=ZAPRET2_MODE)

    def _request_additional_settings_save(self, setting: str, enabled: bool, *, launch_method: str) -> None:
        runtime = self._refresh_runtime
        runtime.mark_additional_settings_written()
        worker = runtime.additional_settings_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    runtime.additional_settings_save_pending = (setting, bool(enabled), launch_method)
                    return
            except Exception:
                return
        request_id = runtime.next_additional_settings_save_request_id()
        worker = create_control_additional_settings_save_worker(
            request_id,
            self._profile,
            launch_method=launch_method,
            setting=setting,
            enabled=bool(enabled),
            parent=self,
        )
        runtime.additional_settings_save_worker = worker
        worker.saved.connect(self._on_additional_settings_save_finished)
        worker.failed.connect(self._on_additional_settings_save_failed)
        worker.finished.connect(lambda w=worker: self._on_additional_settings_save_worker_finished(w))
        worker.start()

    def _on_additional_settings_save_finished(self, request_id: int, _setting: str, _enabled: bool) -> None:
        if request_id != self._refresh_runtime.additional_settings_save_request_id:
            return

    def _on_additional_settings_save_failed(self, request_id: int, _setting: str, error: str) -> None:
        if request_id != self._refresh_runtime.additional_settings_save_request_id:
            return
        InfoBar.warning(title="Ошибка", content=f"Не удалось сохранить настройку: {error}", parent=self.window())

    def _on_additional_settings_save_worker_finished(self, worker) -> None:
        runtime = self._refresh_runtime
        if runtime.additional_settings_save_worker is worker:
            runtime.additional_settings_save_worker = None
        worker.deleteLater()
        pending = runtime.additional_settings_save_pending
        runtime.additional_settings_save_pending = None
        if pending is not None and not self._cleanup_in_progress:
            self._request_additional_settings_save(
                str(pending[0]),
                bool(pending[1]),
                launch_method=str(pending[2]),
            )

    # ==================== Profile UI mode: Basic/Advanced ====================

    def _sync_profile_ui_mode_from_settings(self) -> None:
        sync_profile_ui_mode_label(language=self._ui_language, profile_ui_mode_label=self.profile_ui_mode_label)

    def _open_profile_ui_mode_dialog(self) -> None:
        self._sync_profile_ui_mode_from_settings()

    def _on_profile_ui_mode_selected(self, mode: str) -> None:
        _ = mode
        plan = zapret2_page_runtime.build_profile_ui_mode_change_plan(
            wanted_mode="basic",
            current_mode="basic",
        )
        if plan.refresh_mode_label_after:
            self._sync_profile_ui_mode_from_settings()

    def _sync_program_settings(self) -> None:
        self._request_program_settings_load()

    def _attach_program_settings_runtime(self) -> None:
        self._program_settings.attach_program_settings_runtime(
            self,
            apply_snapshot_fn=self._apply_program_settings_snapshot,
        )
        self._sync_program_settings()

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

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("auto_dpi", bool(enabled))

    def _on_hide_to_tray_toggled(self, enabled: bool) -> None:
        self._request_program_settings_save("hide_to_tray", bool(enabled))

    def _update_stop_winws_button_text(self):
        plan = zapret2_page_runtime.build_stop_button_plan(language=self._ui_language)
        self.stop_winws_btn.setText(plan.text)

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
        defer_initial_state = not self._startup_can_apply_initial_ui_state()
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
            emit_initial=not defer_initial_state,
        )
        if defer_initial_state:
            self._wait_for_startup_interactive_before_initial_ui_state()

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        changed = set(changed_fields or ())
        presets_changed = "active_preset_revision" in changed
        summary_changed = (
            not changed
            or "current_strategy_summary" in changed
            or "preset_content_revision" in changed
            or "subscription_is_premium" in changed
            or "subscription_days_remaining" in changed
        )
        if summary_changed:
            if self._startup_can_refresh_top_summary():
                self._refresh_top_summary(state)
            else:
                self._wait_for_startup_interactive_before_top_summary()
        if "mode_revision" in changed:
            self._sync_profile_ui_mode_from_settings()
        if presets_changed:
            if self._startup_can_refresh_top_summary():
                try:
                    self._apply_selected_preset_name_fast()
                except Exception:
                    pass
            else:
                self._wait_for_startup_interactive_before_top_summary()
            self._refresh_runtime.additional_settings_dirty = True
            if self.isVisible() and self._deferred_sections_hydrated:
                self._schedule_additional_settings_reload(force=True)
            else:
                self.run_when_page_ready(self._apply_pending_mode_refresh_if_ready)
        if not changed or "last_status_message" in changed:
            self._refresh_last_status_message(state)
        self.set_loading(bool(state.launch_busy), str(state.launch_busy_text or ""))
        self.update_status(
            state.launch_phase or ("running" if state.launch_running else "stopped"),
            str(state.launch_last_error or ""),
        )
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
        plan = zapret2_page_runtime.build_status_plan(
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
            profile_ui_mode_btn=self.profile_ui_mode_btn,
            blobs_open_btn=self.blobs_open_btn,
            test_card=self.test_card,
            folder_card=self.folder_card,
            docs_card=self.docs_card,
            profile_ui_mode_caption=self.profile_ui_mode_caption,
            additional_settings_notice=self.additional_settings_notice,
            program_settings_card=self.program_settings_card,
            auto_dpi_toggle=self.auto_dpi_toggle,
            hide_to_tray_toggle=self.hide_to_tray_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
            additional_settings_card=self.additional_settings_card,
            blobs_action_card=self.blobs_action_card,
            discord_restart_toggle=self.discord_restart_toggle,
            wssize_toggle=self.wssize_toggle,
            debug_log_toggle=self.debug_log_toggle,
            update_stop_button_text=self._update_stop_winws_button_text,
            sync_profile_ui_mode_from_settings=self._sync_profile_ui_mode_from_settings,
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
        self._stop_defender_admin_check_worker()
        self._stop_external_open_url_worker()
        cleanup_control_page_subscriptions(self)
