"""BlockCheck page — network blocking analysis and DPI detection UI."""

from __future__ import annotations

import logging
import time

import qtawesome as qta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

import blockcheck.page_runtime as blockcheck_page_runtime
from blockcheck.ui.domain_chip import DomainChip
from blockcheck.ui.domains_build import build_blockcheck_domains_ui
from blockcheck.ui.sections_build import build_actions_section, build_results_section
from blockcheck.ui.log_build import build_log_card_section
from blockcheck.ui.summary_content import (
    build_dpi_summary_content,
)
from blockcheck.ui.summary_build import build_dpi_summary_section
from blockcheck.ui.helpers import (
    add_domain_chip,
    collect_extra_domains,
    remove_domain_chip,
)
from blockcheck.ui.page_results_workflow import (
    update_target_result_table,
)
from blockcheck.page_run_workflow import (
    cleanup_blockcheck_worker,
    request_blockcheck_stop,
    reset_blockcheck_running_ui,
    start_blockcheck_page_run,
)
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from app.ui_texts import tr as tr_catalog

from qfluentwidgets import (
    ComboBox,
    CaptionLabel,
    BodyLabel,
    StrongBodyLabel,
    IndeterminateProgressBar,
    isDarkTheme,
    themeColor,
    TableWidget,
    PushButton,
    LineEdit,
    CheckBox,
    SegmentedWidget,
)

from ui.fluent_widgets import SettingsCard, InfoBarHelper, QuickActionsBar, set_tooltip
from log.log import log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class BlockcheckPage(BasePage):
    """BlockCheck — network blocking analysis and DPI detection."""

    TAB_BLOCKCHECK = "blockcheck"
    TAB_STRATEGY_SCAN = "strategy_scan"
    TAB_DIAGNOSTICS = "diagnostics"
    TAB_DNS_SPOOFING = "dns_spoofing"
    TAB_ORDER = (
        TAB_BLOCKCHECK,
        TAB_STRATEGY_SCAN,
        TAB_DIAGNOSTICS,
        TAB_DNS_SPOOFING,
    )
    TAB_ALIASES = {
        "connection": TAB_DIAGNOSTICS,
        "dns": TAB_DNS_SPOOFING,
    }

    def __init__(
        self,
        parent=None,
        *,
        blockcheck_feature,
        diagnostics_feature,
        dns_feature,
        create_strategy_scan_worker,
    ):
        super().__init__(
            title=tr_catalog("page.blockcheck.title", default="BlockCheck"),
            subtitle=tr_catalog("page.blockcheck.subtitle",
                                default="Автоматический анализ блокировок и диагностика сети"),
            parent=parent,
            title_key="page.blockcheck.title",
            subtitle_key="page.blockcheck.subtitle",
        )
        self.setObjectName("BlockcheckPage")

        self._blockcheck = blockcheck_feature
        self._diagnostics = diagnostics_feature
        self._dns = dns_feature
        self._create_strategy_scan_worker = create_strategy_scan_worker
        self._worker = None
        self._last_report = None
        self._run_log_file: str | None = None
        self._tab_widgets: list[QWidget] = []
        self._strategy_tab_page = None
        self._diagnostics_tab_page = None
        self._dns_spoofing_tab_page = None
        self._active_tab_index: int = 0
        self._pending_tab_key: str | None = None
        self._pending_diagnostics_start_focus = False
        self._cleanup_in_progress = False
        self._tabs_pivot = None
        self._domains_section_label: QLabel | None = None
        self._tcp_section_label: QLabel | None = None
        self._tcp_table = None
        self._runtime_warnings_seen: set[str] = set()
        self._actions_title_label = None
        self._actions_bar = None
        self._prepare_support_btn = None
        self._support_status_label = None
        self._initial_state = blockcheck_page_runtime.BlockcheckPageInitialStatePlan(user_domains=())
        self._initial_state_runtime = OneShotWorkerRuntime()
        self._initial_state_load_started_at = 0.0
        self._run_runtime = OneShotWorkerRuntime()
        self._support_prepare_runtime = OneShotWorkerRuntime()
        self._support_prepare_pending: dict[str, object] | None = None
        self._support_prepare_start_scheduled = False
        self._user_domain_action_runtime = OneShotWorkerRuntime()
        self._user_domain_action_pending: list[dict[str, str]] = []
        self._user_domain_action_start_scheduled = False
        self._build_ui()
        self._request_page_initial_state_load()
        try:
            self.set_ui_language(self._ui_language)
        except Exception:
            pass

    def create_initial_state_worker(self, request_id: int):
        return self._blockcheck.create_page_initial_state_worker(request_id, parent=self)

    def create_support_prepare_worker(
        self,
        request_id: int,
        *,
        run_log_file: str | None,
        mode_label: str,
        extra_domains: list[str],
    ):
        return self._blockcheck.create_blockcheck_support_prepare_worker(
            request_id,
            run_log_file=run_log_file,
            mode_label=mode_label,
            extra_domains=extra_domains,
            parent=self,
        )

    def create_user_domain_action_worker(self, request_id: int, *, action: str, domain: str):
        return self._blockcheck.create_user_domain_action_worker(
            request_id,
            action=action,
            domain=domain,
            parent=self,
        )

    def _request_page_initial_state_load(self) -> None:
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
        self._log_ui_timing("blockcheck_ui.initial_state.load", self._initial_state_load_started_at)
        self._initial_state = initial_state
        self._apply_initial_domain_chips(tuple(getattr(initial_state, "user_domains", ()) or ()))

    def _on_initial_state_failed(self, request_id: int, error: str) -> None:
        if not self._initial_state_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Не удалось загрузить начальное состояние BlockCheck: {error}", "WARNING")

    def _apply_pending_tab_if_ready(self) -> None:
        pending_tab_key = str(getattr(self, "_pending_tab_key", "") or "").strip().lower()
        if pending_tab_key:
            if not self.is_page_ready():
                return
            self._pending_tab_key = None
            self._switch_tab(self.TAB_ORDER.index(self._normalize_tab_key(pending_tab_key)))

        if self.is_page_ready():
            self._apply_pending_diagnostics_start_focus()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        total_started_at = time.perf_counter()
        # ── Tabs (BlockCheck / Strategy scan / Diagnostics / DNS spoofing) ──
        section_started_at = time.perf_counter()
        self._tabs_pivot = SegmentedWidget(self)
        self._tabs_pivot.addItem(
            self.TAB_BLOCKCHECK,
            tr_catalog("page.blockcheck.tab.blockcheck", default="BlockCheck"),
            lambda: self.switch_to_tab(self.TAB_BLOCKCHECK),
        )
        self._tabs_pivot.addItem(
            self.TAB_STRATEGY_SCAN,
            tr_catalog("page.blockcheck.tab.strategy_scan", default="Подбор стратегии"),
            lambda: self.switch_to_tab(self.TAB_STRATEGY_SCAN),
        )
        self._tabs_pivot.addItem(
            self.TAB_DIAGNOSTICS,
            tr_catalog("page.blockcheck.tab.diagnostics", default="Диагностика"),
            lambda: self.switch_to_tab(self.TAB_DIAGNOSTICS),
        )
        self._tabs_pivot.addItem(
            self.TAB_DNS_SPOOFING,
            tr_catalog("page.blockcheck.tab.dns_spoofing", default="DNS подмена"),
            lambda: self.switch_to_tab(self.TAB_DNS_SPOOFING),
        )
        self._tabs_pivot.setCurrentItem(self.TAB_BLOCKCHECK)
        self._tabs_pivot.setItemFontSize(13)
        self.add_widget(self._tabs_pivot)
        self._log_ui_timing("blockcheck_ui.tabs.build", section_started_at)

        # ── Control Card ──
        section_started_at = time.perf_counter()
        self._control_card = SettingsCard(
            tr_catalog("page.blockcheck.control", default="Управление")
        )

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        # Mode combo
        mode_label = CaptionLabel(
            tr_catalog("page.blockcheck.mode", default="Режим:")
        )
        ctrl_row.addWidget(mode_label)

        self._mode_combo = ComboBox()
        self._mode_combo.addItem(
            tr_catalog("page.blockcheck.mode_quick", default="Быстрая"), "quick"
        )
        self._mode_combo.addItem(
            tr_catalog("page.blockcheck.mode_full", default="Полная"), "full"
        )
        self._mode_combo.addItem(
            tr_catalog("page.blockcheck.mode_dpi", default="Только DPI"), "dpi_only"
        )
        self._mode_combo.setCurrentIndex(1)  # Default: full
        self._mode_combo.setFixedWidth(160)
        ctrl_row.addWidget(self._mode_combo)

        ctrl_row.addStretch()

        # Preflight skip checkbox
        self._skip_failed_cb = CheckBox(
            tr_catalog("page.blockcheck.skip_failed",
                       default="Пропускать проблемные домены")
        )
        self._skip_failed_cb.setChecked(False)
        set_tooltip(
            self._skip_failed_cb,
            "Если включено, домены с провалившимся preflight "
            "(DNS-заглушка, ISP-инъекция) будут пропущены в основном блокчеке"
        )
        ctrl_row.addWidget(self._skip_failed_cb)

        self._control_card.add_layout(ctrl_row)

        # Progress
        self._progress_bar = IndeterminateProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._control_card.add_widget(self._progress_bar)

        # Status label
        self._status_label = CaptionLabel(
            tr_catalog("page.blockcheck.ready", default="Готово")
        )
        self._control_card.add_widget(self._status_label)
        self._add_tab_widget(self._control_card)
        self._log_ui_timing("blockcheck_ui.control_card.build", section_started_at)

        section_started_at = time.perf_counter()
        actions_widgets = build_actions_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            strong_body_label_cls=StrongBodyLabel,
            quick_actions_bar_cls=QuickActionsBar,
            content_parent=self.content,
            push_button_cls=PushButton,
            qta_module=qta,
            on_start=self._on_start,
            on_stop=self._on_stop,
        )
        self._actions_title_label = actions_widgets.title_label
        self._actions_bar = actions_widgets.actions_bar
        self._start_btn = actions_widgets.start_button
        self._stop_btn = actions_widgets.stop_button

        self._add_tab_widget(self._actions_title_label)
        self._add_tab_widget(self._actions_bar)
        self._log_ui_timing("blockcheck_ui.actions.build", section_started_at)

        # ── Custom Domains Card ──
        section_started_at = time.perf_counter()
        domains_widgets = build_blockcheck_domains_ui(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            settings_card_cls=SettingsCard,
            qhbox_layout_cls=QHBoxLayout,
            qwidget_cls=QWidget,
            line_edit_cls=LineEdit,
            push_button_cls=PushButton,
            qta_module=qta,
            theme_color_fn=themeColor,
            on_add=self._on_add_domain,
        )
        self._domains_card = domains_widgets.card
        self._domain_input = domains_widgets.input_edit
        self._add_domain_btn = domains_widgets.add_button
        self._domains_flow = domains_widgets.flow_widget
        self._domains_flow_layout = domains_widgets.flow_layout

        self._add_tab_widget(self._domains_card)
        self._log_ui_timing("blockcheck_ui.domains_card.build", section_started_at)

        # Load persisted user domains
        section_started_at = time.perf_counter()
        self._apply_initial_domain_chips(self._initial_state.user_domains)
        self._log_ui_timing("blockcheck_ui.domain_chips.apply", section_started_at)

        # ── Results Table Card ──
        section_started_at = time.perf_counter()
        results_widgets = build_results_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            settings_card_cls=SettingsCard,
            strong_body_label_cls=StrongBodyLabel,
            table_widget_cls=TableWidget,
        )
        self._results_card = results_widgets.results_card
        self._domains_section_label = results_widgets.domains_section_label
        self._table = results_widgets.results_table
        self._tcp_section_label = results_widgets.tcp_section_label
        self._tcp_table = results_widgets.tcp_table
        self._add_tab_widget(self._results_card)
        self._log_ui_timing("blockcheck_ui.results_section.build", section_started_at)

        # ── DPI Summary Card (hidden until tests complete) ──
        section_started_at = time.perf_counter()
        dpi_widgets = build_dpi_summary_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            settings_card_cls=SettingsCard,
            qlabel_cls=QLabel,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            qt_namespace=Qt,
        )
        self._dpi_card = dpi_widgets.card
        self._dpi_badge = dpi_widgets.badge
        self._dpi_detail = dpi_widgets.detail
        self._dns_summary = dpi_widgets.dns_summary
        self._recommendation = dpi_widgets.recommendation
        self._add_tab_widget(self._dpi_card)
        self._log_ui_timing("blockcheck_ui.dpi_summary.build", section_started_at)

        # ── Log Card ──
        section_started_at = time.perf_counter()
        self._log_expanded = False
        log_widgets = build_log_card_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            settings_card_cls=SettingsCard,
            qhbox_layout_cls=QHBoxLayout,
            caption_label_cls=CaptionLabel,
            push_button_cls=PushButton,
            qta_module=qta,
            theme_color_fn=themeColor,
            text_edit_cls=ScrollBlockingTextEdit,
            qfont_cls=QFont,
            on_toggle_expand=self._toggle_log_expand,
            on_prepare_support=self._prepare_support_from_blockcheck,
        )
        self._log_card = log_widgets.card
        self._expand_log_btn = log_widgets.expand_button
        self._support_status_label = log_widgets.support_status_label
        self._prepare_support_btn = log_widgets.prepare_support_button
        self._log_edit = log_widgets.log_edit
        self._add_tab_widget(self._log_card)
        self._log_ui_timing("blockcheck_ui.log_card.build", section_started_at)

        # Strategy scan tab (lazy-created)
        section_started_at = time.perf_counter()
        self._switch_tab(0)
        self._log_ui_timing("blockcheck_ui.initial_tab.switch", section_started_at)
        self._log_ui_timing("blockcheck_ui.build.total", total_started_at)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = tokens
        _ = force
        """Update DPI badge colors and chip styles on theme change."""
        if self._last_report:
            self._update_dpi_summary(self._last_report)
        # Refresh chip styles
        for i in range(self._domains_flow_layout.count()):
            item = self._domains_flow_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), DomainChip):
                item.widget()._apply_chip_style()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _add_tab_widget(self, widget: QWidget) -> None:
        """Add a widget to BlockCheck tab content list."""
        self._tab_widgets.append(widget)
        self.add_widget(widget)

    def _ensure_strategy_tab(self):
        """Create embedded strategy-scan tab on first open."""
        if self._strategy_tab_page is not None:
            return
        started_at = time.perf_counter()
        try:
            from blockcheck.ui.strategy_scan_page import StrategyScanPage
            self._strategy_tab_page = StrategyScanPage(
                parent=self,
                embedded=True,
                blockcheck_feature=self._blockcheck,
                create_strategy_scan_worker=self._create_strategy_scan_worker,
            )
            self._strategy_tab_page.setVisible(False)
            self.add_widget(self._strategy_tab_page)
            try:
                self._strategy_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create embedded strategy tab: %s", e)
        finally:
            self._log_ui_timing("blockcheck_ui.strategy_tab.build", started_at)

    def _ensure_diagnostics_tab(self):
        """Create embedded connection diagnostics tab on first open."""
        if self._diagnostics_tab_page is not None:
            return
        started_at = time.perf_counter()
        try:
            from diagnostics.ui.page import ConnectionTestPage

            self._diagnostics_tab_page = ConnectionTestPage(
                parent=self,
                diagnostics_feature=self._diagnostics,
            )
            self._diagnostics_tab_page.setVisible(False)
            self.add_widget(self._diagnostics_tab_page)

            try:
                self._diagnostics_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create diagnostics tab: %s", e)
        finally:
            self._log_ui_timing("blockcheck_ui.diagnostics_tab.build", started_at)

    def _ensure_dns_spoofing_tab(self):
        """Create embedded DNS spoofing tab on first open."""
        if self._dns_spoofing_tab_page is not None:
            return
        started_at = time.perf_counter()
        try:
            from dns.ui.dns_check_page import DNSCheckPage

            self._dns_spoofing_tab_page = DNSCheckPage(
                parent=self,
                dns_feature=self._dns,
            )
            self._dns_spoofing_tab_page.setVisible(False)
            self.add_widget(self._dns_spoofing_tab_page)

            try:
                self._dns_spoofing_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create DNS spoofing tab: %s", e)
        finally:
            self._log_ui_timing("blockcheck_ui.dns_spoofing_tab.build", started_at)

    @classmethod
    def _normalize_tab_key(cls, key: str | None) -> str:
        raw_key = str(key or "").strip().lower()
        if raw_key in cls.TAB_ORDER:
            return raw_key
        return cls.TAB_ALIASES.get(raw_key, cls.TAB_BLOCKCHECK)

    def switch_to_tab(self, key: str) -> None:
        """External API: switch to one of BlockCheck tabs."""
        normalized = self._normalize_tab_key(key)
        if not self.is_page_ready():
            self._pending_tab_key = normalized
            self.run_when_page_ready(self._apply_pending_tab_if_ready)
            return
        self._pending_tab_key = None
        self._switch_tab(self.TAB_ORDER.index(normalized))

    def request_diagnostics_start_focus(self) -> None:
        self._pending_diagnostics_start_focus = True
        if not self.is_page_ready():
            self.run_when_page_ready(self._apply_pending_diagnostics_start_focus)
            return
        self._apply_pending_diagnostics_start_focus()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        _ = payload
        normalized = str(command or "").strip().lower()
        if normalized == "stop_runtime_conflicting_checks":
            return self.request_runtime_conflicting_stop()
        return False

    def request_runtime_conflicting_stop(self) -> bool:
        """Останавливает проверки BlockCheck перед ручным запуском основного DPI."""
        stopped = False
        if self._worker and self._worker.is_running:
            self._on_stop()
            stopped = True

        strategy_page = self._strategy_tab_page
        request_stop = getattr(strategy_page, "request_runtime_conflicting_stop", None)
        if callable(request_stop):
            stopped = bool(request_stop()) or stopped

        return stopped

    def _switch_tab(self, index: int) -> None:
        """Switch between BlockCheck, strategy scan and diagnostics tabs."""
        started_at = time.perf_counter()
        if not self.TAB_ORDER:
            return
        index = max(0, min(int(index), len(self.TAB_ORDER) - 1))
        tab_key = self.TAB_ORDER[index]
        self._active_tab_index = index

        if self._tabs_pivot is not None:
            try:
                self._tabs_pivot.setCurrentItem(tab_key)
            except Exception:
                pass

        if tab_key == self.TAB_STRATEGY_SCAN:
            self._ensure_strategy_tab()
        elif tab_key == self.TAB_DIAGNOSTICS:
            self._ensure_diagnostics_tab()
        elif tab_key == self.TAB_DNS_SPOOFING:
            self._ensure_dns_spoofing_tab()

        show_blockcheck = tab_key == self.TAB_BLOCKCHECK
        for widget in self._tab_widgets:
            widget.setVisible(show_blockcheck)

        if self._strategy_tab_page is not None:
            self._strategy_tab_page.setVisible(tab_key == self.TAB_STRATEGY_SCAN)

        if self._diagnostics_tab_page is not None:
            self._diagnostics_tab_page.setVisible(tab_key == self.TAB_DIAGNOSTICS)

        if self._dns_spoofing_tab_page is not None:
            self._dns_spoofing_tab_page.setVisible(tab_key == self.TAB_DNS_SPOOFING)

        if tab_key == self.TAB_DIAGNOSTICS:
            self._apply_pending_diagnostics_start_focus()
        self._log_ui_timing(f"blockcheck_ui.switch_tab.{tab_key}", started_at)

    def _apply_pending_diagnostics_start_focus(self) -> None:
        if not self._pending_diagnostics_start_focus:
            return
        self._ensure_diagnostics_tab()
        page = self._diagnostics_tab_page
        if page is None:
            return
        request_focus = getattr(page, "request_start_focus", None)
        if not callable(request_focus):
            return
        self._pending_diagnostics_start_focus = False
        request_focus()

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self):
        if self._worker and self._worker.is_running:
            return
        self._cleanup_in_progress = False

        mode = self._mode_combo.currentData()
        if mode is None:
            mode = "full"
        self._last_report = None
        extra = self._get_extra_domains()

        run_state = start_blockcheck_page_run(
            blockcheck_feature=self._blockcheck,
            mode=mode,
            extra_domains=extra,
            skip_preflight_failed=self._skip_failed_cb.isChecked(),
            parent=self,
            run_runtime=self._run_runtime,
            table=self._table,
            tcp_table=self._tcp_table,
            tcp_section_label=self._tcp_section_label,
            dpi_card=self._dpi_card,
            log_edit=self._log_edit,
            start_button=self._start_btn,
            stop_button=self._stop_btn,
            mode_combo=self._mode_combo,
            skip_failed_checkbox=self._skip_failed_cb,
            progress_bar=self._progress_bar,
            status_label=self._status_label,
            runtime_warnings_seen=self._runtime_warnings_seen,
            set_support_status=self._set_support_status,
            tr_fn=tr_catalog,
            on_phase_changed=self._on_phase_changed,
            on_test_result=self._on_test_result,
            on_target_complete=self._on_target_complete,
            on_log=self._on_log,
            on_run_log_started=self._on_run_log_started,
            on_finished=self._on_finished,
        )
        self._worker = run_state.worker
        self._run_log_file = run_state.run_log_file

    def _on_run_log_started(self, run_log_file) -> None:
        if self._cleanup_in_progress:
            return
        self._run_log_file = run_log_file

    def _on_stop(self):
        request_blockcheck_stop(
            worker=self._worker,
            stop_button=self._stop_btn,
            status_label=self._status_label,
            force_stop=self._force_stop,
            tr_fn=tr_catalog,
        )

    def _force_stop(self, expected_worker=None):
        if expected_worker is None:
            return
        if self._worker is expected_worker and self._worker.is_running:
            warning_text = tr_catalog(
                "page.blockcheck.stopping_slow",
                default="Остановка занимает больше времени, ждём завершения фоновой проверки...",
            )
            self._status_label.setText(warning_text)
            self._set_support_status(
                tr_catalog(
                    "page.blockcheck.support_wait_stop",
                    default="Подождите завершения остановки перед новым запуском",
                )
            )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_phase_changed(self, phase: str):
        if self._cleanup_in_progress:
            return
        self._status_label.setText(phase)

    def _on_test_result(self, result):
        """Update table with individual test result."""
        if self._cleanup_in_progress:
            return
        pass  # Table is updated on target_complete for better UX

    def _on_target_complete(self, target_result):
        """Add/update a row in the results table for a completed target."""
        if self._cleanup_in_progress:
            return
        update_target_result_table(
            target_result=target_result,
            table=self._table,
            tcp_table=self._tcp_table,
            tcp_section_label=self._tcp_section_label,
        )

    def _on_log(self, message: str):
        if self._cleanup_in_progress:
            return
        self._log_edit.append(message)

        text = str(message or "").strip()
        if text.startswith("WARNING:"):
            warning_text = text[len("WARNING:"):].strip() or text
            if warning_text not in self._runtime_warnings_seen:
                self._runtime_warnings_seen.add(warning_text)
                try:
                    InfoBarHelper.warning(
                        self.window(),
                        tr_catalog("page.blockcheck.warning", default="Предупреждение"),
                        warning_text,
                    )
                except Exception:
                    pass

    def _on_finished(self, report):
        """Handle test completion."""
        if self._cleanup_in_progress:
            return
        worker = self._worker
        self._worker = None
        if worker is not None:
            try:
                worker.deleteLater()
            except Exception:
                pass
        self._last_report = report
        self._reset_ui()
        was_cancelled = bool(report is not None and getattr(report, "cancelled", False))

        if report is None:
            self._status_label.setText(
                tr_catalog("page.blockcheck.error", default="Ошибка выполнения")
            )
            self._set_support_status(
                tr_catalog(
                    "page.blockcheck.support_ready_after_error",
                    default="Можно подготовить обращение по логам ошибки",
                )
            )
            return

        elapsed = report.elapsed_seconds
        if was_cancelled:
            self._status_label.setText(
                tr_catalog("page.blockcheck.cancelled", default="Отменено") + f" ({elapsed:.1f}s)"
            )
            self._set_support_status(
                tr_catalog(
                    "page.blockcheck.support_ready_after_cancel",
                    default="Можно подготовить обращение по частичным логам отменённого запуска",
                )
            )
        else:
            self._status_label.setText(
                tr_catalog("page.blockcheck.done", default="Готово") + f" ({elapsed:.1f}s)"
            )
            self._set_support_status(
                tr_catalog(
                    "page.blockcheck.support_ready",
                    default="Можно подготовить обращение по этому запуску",
                )
            )

        # Re-update all targets with final classifications
        for tr in report.targets:
            self._on_target_complete(tr)

        if was_cancelled:
            self._dpi_card.setVisible(False)
            try:
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog("page.blockcheck.cancelled", default="Отменено"),
                    tr_catalog(
                        "page.blockcheck.cancelled.info",
                        default="Проверка остановлена пользователем. Показаны частичные результаты.",
                    ),
                )
            except Exception:
                pass
            return

        # Show DPI summary
        self._update_dpi_summary(report)

        try:
            InfoBarHelper.success(
                self.window(),
                tr_catalog("page.blockcheck.done", default="Готово"),
                f"{len(report.targets)} целей проверено за {elapsed:.1f}s",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _reset_ui(self):
        reset_blockcheck_running_ui(
            start_button=self._start_btn,
            stop_button=self._stop_btn,
            mode_combo=self._mode_combo,
            skip_failed_checkbox=self._skip_failed_cb,
            progress_bar=self._progress_bar,
        )

    def _set_support_status(self, text: str) -> None:
        if self._support_status_label is None:
            return
        self._support_status_label.setText(str(text or "").strip())

    def _prepare_support_from_blockcheck(self) -> None:
        mode_label = self._mode_combo.currentText() if self._mode_combo is not None else "BlockCheck"
        extra_domains = self._get_extra_domains()
        self._request_support_prepare(
            run_log_file=self._run_log_file,
            mode_label=mode_label,
            extra_domains=extra_domains,
        )

    def _request_support_prepare(
        self,
        *,
        run_log_file: str | None,
        mode_label: str,
        extra_domains: list[str],
    ) -> None:
        payload = {
            "run_log_file": run_log_file,
            "mode_label": str(mode_label or ""),
            "extra_domains": list(extra_domains or []),
        }
        if (
            self._support_prepare_runtime.is_running()
            or self.__dict__.get("_support_prepare_start_scheduled", False)
        ):
            self._support_prepare_pending = dict(payload)
            self._set_support_status("Подготовка уже идёт...")
            return

        self._set_support_status("Подготовка обращения...")
        if self._prepare_support_btn is not None:
            self._prepare_support_btn.setEnabled(False)
        self._start_support_prepare_worker(payload)

    def _start_support_prepare_worker(self, payload: dict) -> None:
        def worker_factory(request_id: int):
            return self.create_support_prepare_worker(
                request_id,
                run_log_file=payload.get("run_log_file"),
                mode_label=str(payload.get("mode_label") or ""),
                extra_domains=list(payload.get("extra_domains") or []),
            )

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_support_prepare_finished)
            worker.failed.connect(self._on_support_prepare_failed)

        self._support_prepare_runtime.start_qthread_worker(
            worker_factory=worker_factory,
            bind_worker=bind_worker,
            on_finished=self._on_support_prepare_runtime_finished,
        )

    def _on_support_prepare_finished(self, request_id: int, feedback) -> None:
        if not self._support_prepare_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        result = feedback.result
        if result.zip_path:
            logger.info("Prepared BlockCheck support archive: %s", result.zip_path)

        self._set_support_status(feedback.status_text)

        try:
            InfoBarHelper.success(
                self.window(),
                tr_catalog(
                    "page.blockcheck.support_prepared_title",
                    default="Обращение подготовлено",
                ),
                feedback.info_text,
            )
        except Exception:
            pass

    def _on_support_prepare_failed(self, request_id: int, error: str) -> None:
        if not self._support_prepare_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        logger.warning("Failed to prepare BlockCheck support bundle: %s", error)
        self._set_support_status("Ошибка подготовки")
        try:
            InfoBarHelper.warning(
                self.window(),
                tr_catalog("page.blockcheck.error", default="Ошибка выполнения"),
                f"Не удалось подготовить обращение:\n{error}",
            )
        except Exception:
            pass

    def _on_support_prepare_runtime_finished(self, _worker) -> None:
        pending = self.__dict__.get("_support_prepare_pending")
        if pending is not None and not self._cleanup_in_progress:
            self._schedule_support_prepare_worker_start(dict(pending or {}))
            return
        if self._prepare_support_btn is not None and not self._cleanup_in_progress:
            self._prepare_support_btn.setEnabled(True)

    def _schedule_support_prepare_worker_start(self, payload: dict) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._support_prepare_pending = dict(payload or {})
        if self.__dict__.get("_support_prepare_start_scheduled", False):
            return
        self._support_prepare_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_support_prepare_worker_start)

    def _run_scheduled_support_prepare_worker_start(self) -> None:
        self._support_prepare_start_scheduled = False
        pending = self.__dict__.get("_support_prepare_pending")
        self._support_prepare_pending = None
        if pending is None or self.__dict__.get("_cleanup_in_progress", False):
            return
        self._set_support_status("Подготовка обращения...")
        if self._prepare_support_btn is not None:
            self._prepare_support_btn.setEnabled(False)
        self._start_support_prepare_worker(dict(pending or {}))

    def _toggle_log_expand(self):
        """Развернуть/свернуть лог на всю страницу."""
        self._log_expanded = not self._log_expanded

        if self._log_expanded:
            self._control_card.setVisible(False)
            self._domains_card.setVisible(False)
            self._results_card.setVisible(False)
            self._dpi_card.setVisible(False)
            self._log_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self._log_edit.setMinimumHeight(400)
            self._expand_log_btn.setText("Свернуть")
        else:
            self._control_card.setVisible(True)
            self._domains_card.setVisible(True)
            self._results_card.setVisible(True)
            # dpi_card visibility depends on whether results exist
            if self._last_report and self._last_report.targets:
                self._dpi_card.setVisible(True)
            self._log_edit.setMinimumHeight(180)
            self._log_edit.setMaximumHeight(300)
            self._expand_log_btn.setText("Развернуть")

    def _update_dpi_summary(self, report):
        """Show DPI summary card after tests complete."""
        self._dpi_card.setVisible(True)
        content = build_dpi_summary_content(
            report=report,
            is_dark=isDarkTheme(),
            no_dpi_text=tr_catalog("page.blockcheck.no_dpi", default="DPI не обнаружен на проверенных ресурсах"),
        )
        self._dpi_badge.setText(content.badge_label)
        self._dpi_badge.setStyleSheet(
            f"background: {content.badge_bg}; color: {content.badge_fg}; "
            f"font-weight: 600; font-size: 13px; border-radius: 8px; padding: 6px 16px;"
        )
        self._dpi_detail.setText(content.detail_text)
        self._dns_summary.setText(content.dns_summary_text)
        self._recommendation.setText(content.recommendation_text)

    # ------------------------------------------------------------------
    # Custom domains
    # ------------------------------------------------------------------

    def _apply_initial_domain_chips(self, domains: tuple[str, ...]) -> None:
        """Create chips from a backend-prepared domain list."""
        started_at = time.perf_counter()
        existing = set(self._get_extra_domains())
        for domain in tuple(domains or ()):
            if domain in existing:
                continue
            self._add_chip(domain)
            existing.add(domain)
        self._log_ui_timing("blockcheck_ui.domain_chips.apply.total", started_at)

    @staticmethod
    def _log_ui_timing(label: str, started_at: float) -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass

    def _on_add_domain(self):
        """Add a domain from the input field."""
        text = self._domain_input.text().strip()
        if not text:
            return
        self._request_user_domain_action("add", text)

    def _on_remove_domain(self, domain: str):
        """Remove a domain chip and delete from persistence."""
        self._request_user_domain_action("remove", domain)

    def _request_user_domain_action(self, action: str, domain: str) -> None:
        payload = {
            "action": str(action or "").strip().lower(),
            "domain": str(domain or "").strip(),
        }
        if not payload["action"] or not payload["domain"]:
            return
        if (
            self._user_domain_action_runtime.is_running()
            or self.__dict__.get("_user_domain_action_start_scheduled", False)
        ):
            self._user_domain_action_pending.append(payload)
            return
        self._start_user_domain_action_worker(payload)

    def _start_user_domain_action_worker(self, payload: dict[str, str]) -> None:
        def worker_factory(request_id: int):
            return self.create_user_domain_action_worker(
                request_id,
                action=str(payload.get("action") or ""),
                domain=str(payload.get("domain") or ""),
            )

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_user_domain_action_finished)
            worker.failed.connect(self._on_user_domain_action_failed)

        self._user_domain_action_runtime.start_qthread_worker(
            worker_factory=worker_factory,
            bind_worker=bind_worker,
            on_finished=self._on_user_domain_action_runtime_finished,
        )

    def _on_user_domain_action_finished(self, request_id: int, action: str, result, context) -> None:
        if not self._user_domain_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        context = dict(context or {})
        if action == "add":
            text = str(context.get("domain") or "")
            normalized = str(result or "").strip()
            if normalized:
                self._add_chip(normalized)
            else:
                try:
                    InfoBarHelper.warning(
                        self.window(),
                        tr_catalog("page.blockcheck.domain_exists_title", default="Домен уже добавлен"),
                        text,
                    )
                except Exception:
                    pass
            self._domain_input.clear()
            return
        if action == "remove":
            remove_domain_chip(
                domain=str(result or context.get("domain") or ""),
                flow_layout=self._domains_flow_layout,
                chip_cls=DomainChip,
            )

    def _on_user_domain_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if not self._user_domain_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        logger.warning("Failed to %s BlockCheck domain: %s", action, error)

    def _on_user_domain_action_runtime_finished(self, _worker) -> None:
        if self._user_domain_action_pending and not self._cleanup_in_progress:
            pending = self._user_domain_action_pending.pop(0)
            self._schedule_user_domain_action_worker_start(dict(pending or {}))

    def _schedule_user_domain_action_worker_start(self, payload: dict[str, str]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = {
            "action": str((payload or {}).get("action") or "").strip().lower(),
            "domain": str((payload or {}).get("domain") or "").strip(),
        }
        if self.__dict__.get("_user_domain_action_start_scheduled", False):
            self._user_domain_action_pending.append(queued)
            return
        self._user_domain_action_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_user_domain_action_worker_start(value))

    def _run_scheduled_user_domain_action_worker_start(self, payload: dict[str, str]) -> None:
        self._user_domain_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_user_domain_action_worker(payload)

    def _add_chip(self, domain: str):
        """Add a chip widget for a domain."""
        add_domain_chip(
            domain=domain,
            flow_widget=self._domains_flow,
            flow_layout=self._domains_flow_layout,
            chip_cls=DomainChip,
            on_removed=self._on_remove_domain,
        )

    def _get_extra_domains(self) -> list[str]:
        """Collect domains from chips to pass to worker."""
        return collect_extra_domains(
            flow_layout=self._domains_flow_layout,
            chip_cls=DomainChip,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._initial_state_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blockcheck initial state worker",
        )
        self._initial_state_runtime.cancel()
        self._support_prepare_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blockcheck support prepare worker",
        )
        self._support_prepare_runtime.cancel()
        self._support_prepare_pending = None
        self._support_prepare_start_scheduled = False
        self._user_domain_action_pending.clear()
        self._user_domain_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blockcheck user domain action worker",
        )
        self._user_domain_action_runtime.cancel()
        self._run_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blockcheck run worker",
        )
        self._run_runtime.cancel()
        self._worker = cleanup_blockcheck_worker(self._worker)

        for page in (self._strategy_tab_page, self._diagnostics_tab_page, self._dns_spoofing_tab_page):
            if page is None:
                continue
            cleanup_handler = getattr(page, "cleanup", None)
            if callable(cleanup_handler):
                try:
                    cleanup_handler()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        try:
            if self._tabs_pivot is not None:
                self._tabs_pivot.setItemText(
                    self.TAB_BLOCKCHECK,
                    tr_catalog("page.blockcheck.tab.blockcheck", language=language, default="BlockCheck"),
                )
                self._tabs_pivot.setItemText(
                    self.TAB_STRATEGY_SCAN,
                    tr_catalog("page.blockcheck.tab.strategy_scan", language=language, default="Подбор стратегии"),
                )
                self._tabs_pivot.setItemText(
                    self.TAB_DIAGNOSTICS,
                    tr_catalog("page.blockcheck.tab.diagnostics", language=language, default="Диагностика"),
                )
                self._tabs_pivot.setItemText(
                    self.TAB_DNS_SPOOFING,
                    tr_catalog("page.blockcheck.tab.dns_spoofing", language=language, default="DNS подмена"),
                )
            self._control_card.set_title(tr_catalog("page.blockcheck.control", language=language, default="Управление"))
            self._domains_card.set_title(tr_catalog("page.blockcheck.custom_domains", language=language, default="Пользовательские домены"))
            self._results_card.set_title(tr_catalog("page.blockcheck.results", language=language, default="Результаты"))
            self._log_card.set_title(tr_catalog("page.blockcheck.log", language=language, default="Подробный лог"))

            if self._domains_section_label is not None:
                self._domains_section_label.setText(
                    tr_catalog(
                        "page.blockcheck.domains_section",
                        language=language,
                        default="Часть 1: Проверка доменов (TLS + HTTP injection)",
                    )
                )
            if self._tcp_section_label is not None:
                self._tcp_section_label.setText(
                    tr_catalog(
                        "page.blockcheck.tcp_section",
                        language=language,
                        default="Часть 2: Проверка TCP 16-20KB",
                    )
                )

            self._table.setHorizontalHeaderLabels([
                tr_catalog("page.blockcheck.col_target", language=language, default="Цель"),
                "HTTP",
                "TLS 1.2",
                "TLS 1.3",
                tr_catalog("page.blockcheck.col_dns_isp", language=language, default="DNS/ISP"),
                "DPI",
                "Ping",
                tr_catalog("page.blockcheck.col_details", language=language, default="Детали"),
            ])

            if self._tcp_table is not None:
                self._tcp_table.setHorizontalHeaderLabels([
                    "ID",
                    "ASN",
                    tr_catalog("page.blockcheck.col_provider", language=language, default="Провайдер"),
                    tr_catalog("page.blockcheck.col_status", language=language, default="Статус"),
                    tr_catalog("page.blockcheck.col_error_details", language=language, default="Ошибка / Детали"),
                ])

            self._start_btn.setText(tr_catalog("page.blockcheck.start", language=language, default="Запустить"))
            self._stop_btn.setText(tr_catalog("page.blockcheck.stop", language=language, default="Остановить"))
            if self._actions_title_label is not None:
                self._actions_title_label.setText(
                    tr_catalog("page.blockcheck.actions.title", language=language, default="Действия")
                )
            set_tooltip(
                self._start_btn,
                tr_catalog(
                    "page.blockcheck.action.start.description",
                    language=language,
                    default="Запустить анализ блокировок и проверку DPI для выбранного режима.",
                )
            )
            set_tooltip(
                self._stop_btn,
                tr_catalog(
                    "page.blockcheck.action.stop.description",
                    language=language,
                    default="Остановить текущую проверку и вернуть страницу в обычный режим.",
                )
            )
            self._skip_failed_cb.setText(tr_catalog("page.blockcheck.skip_failed", language=language, default="Пропускать проблемные домены"))
            self._add_domain_btn.setText(tr_catalog("page.blockcheck.add_domain", language=language, default="Добавить"))
            self._domain_input.setPlaceholderText(tr_catalog("page.blockcheck.domain_placeholder", language=language, default="example.com"))
            if self._prepare_support_btn is not None:
                self._prepare_support_btn.setText(
                    tr_catalog(
                        "page.blockcheck.prepare_support",
                        language=language,
                        default="Подготовить обращение",
                    )
                )
            if self._strategy_tab_page is not None:
                self._strategy_tab_page.set_ui_language(language)
            if self._diagnostics_tab_page is not None:
                self._diagnostics_tab_page.set_ui_language(language)
            if self._dns_spoofing_tab_page is not None:
                self._dns_spoofing_tab_page.set_ui_language(language)
        except Exception:
            pass
