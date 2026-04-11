"""BlockCheck page — network blocking analysis and DPI detection UI."""

from __future__ import annotations

import qtawesome as qta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from blockcheck.page_controller import BlockcheckPageController
from ui.pages.blockcheck_domain_chip import DomainChip
from ui.pages.blockcheck_page_domains_build import build_blockcheck_domains_ui
from ui.pages.blockcheck_page_sections_build import build_actions_section, build_results_section
from ui.pages.blockcheck_page_log_build import build_log_card_section
from ui.pages.blockcheck_page_summary_build import build_dpi_summary_section
from ui.pages.blockcheck_page_helpers import (
    add_domain_chip,
    build_family_tooltip,
    build_target_detail_text,
    collect_extra_domains,
    format_result_detail,
    load_domain_chips,
    remove_domain_chip,
    result_family_label,
    sort_results_by_family,
    truncate_detail,
)
from ui.pages.blockcheck_worker import BlockcheckWorker
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.text_catalog import tr as tr_catalog

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
    SegmentedWidget,
)

from ui.compat_widgets import SettingsCard, InfoBarHelper, CheckBox, QuickActionsBar

# ---------------------------------------------------------------------------
# DPI badge colors
# ---------------------------------------------------------------------------

_DPI_BADGE_COLORS = {
    "none": ("#52c477", "#1a3a24"),
    "dns_fake": ("#e0a854", "#3a2e1a"),
    "http_inject": ("#e07854", "#3a221a"),
    "isp_page": ("#e05454", "#3a1a1a"),
    "tls_dpi": ("#e05454", "#3a1a1a"),
    "tls_mitm": ("#e05454", "#3a1a1a"),
    "tcp_reset": ("#e07854", "#3a221a"),
    "tcp_16_20": ("#e0a854", "#3a2e1a"),
    "stun_block": ("#e0a854", "#3a2e1a"),
    "full_block": ("#e05454", "#3a1a1a"),
}

_DPI_LABELS_RU = {
    "none": "DPI не обнаружен",
    "dns_fake": "DNS подмена",
    "http_inject": "HTTP инъекция",
    "isp_page": "Страница-заглушка ISP",
    "tls_dpi": "TLS DPI (RST/EOF)",
    "tls_mitm": "TLS MITM прокси",
    "tcp_reset": "TCP RST",
    "tcp_16_20": "TCP блок 16-20KB",
    "stun_block": "STUN/UDP блокировка",
    "full_block": "Полная блокировка",
}

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

    def __init__(self, parent=None):
        super().__init__(
            title=tr_catalog("page.blockcheck.title", default="BlockCheck"),
            subtitle=tr_catalog("page.blockcheck.subtitle",
                                default="Автоматический анализ блокировок и диагностика сети"),
            parent=parent,
            title_key="page.blockcheck.title",
            subtitle_key="page.blockcheck.subtitle",
        )
        self.setObjectName("BlockcheckPage")

        self._worker: BlockcheckWorker | None = None
        self._last_report = None
        self._run_log_file: str | None = None
        self._tab_widgets: list[QWidget] = []
        self._strategy_tab_page = None
        self._diagnostics_tab_page = None
        self._dns_spoofing_tab_page = None
        self.connection_page = None
        self.dns_check_page = None
        self._active_tab_index: int = 0
        self._pending_tab_key: str | None = None
        self._pending_diagnostics_start_focus = False
        self._tabs_pivot = None
        self._domains_section_label: QLabel | None = None
        self._tcp_section_label: QLabel | None = None
        self._tcp_table = None
        self._runtime_warnings_seen: set[str] = set()
        self._actions_title_label = None
        self._actions_bar = None
        self._prepare_support_btn = None
        self._support_status_label = None
        self._build_ui()
        try:
            self.set_ui_language(self._ui_language)
        except Exception:
            pass

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
        # ── Tabs (BlockCheck / Strategy scan / Diagnostics / DNS spoofing) ──
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

        # ── Control Card ──
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
        self._skip_failed_cb.setToolTip(
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

        # ── Custom Domains Card ──
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

        # Load persisted user domains
        self._load_domain_chips()

        # ── Results Table Card ──
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

        # ── DPI Summary Card (hidden until tests complete) ──
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

        # ── Log Card ──
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

        # Strategy scan tab (lazy-created)
        self._switch_tab(0)

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
        try:
            from ui.pages.strategy_scan_page import StrategyScanPage
            self._strategy_tab_page = StrategyScanPage(parent=self, embedded=True)
            self._strategy_tab_page.setVisible(False)
            self.add_widget(self._strategy_tab_page)
            try:
                self._strategy_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create embedded strategy tab: %s", e)

    def _ensure_diagnostics_tab(self):
        """Create embedded connection diagnostics tab on first open."""
        if self._diagnostics_tab_page is not None:
            return
        try:
            from ui.pages.connection_page import ConnectionTestPage

            self._diagnostics_tab_page = ConnectionTestPage(parent=self.parent_app)
            self._diagnostics_tab_page.setVisible(False)
            self.add_widget(self._diagnostics_tab_page)
            self.connection_page = self._diagnostics_tab_page

            try:
                self._diagnostics_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create diagnostics tab: %s", e)

    def _ensure_dns_spoofing_tab(self):
        """Create embedded DNS spoofing tab on first open."""
        if self._dns_spoofing_tab_page is not None:
            return
        try:
            from ui.pages.dns_check_page import DNSCheckPage

            self._dns_spoofing_tab_page = DNSCheckPage(parent=self.parent_app)
            self._dns_spoofing_tab_page.setVisible(False)
            self.add_widget(self._dns_spoofing_tab_page)
            self.dns_check_page = self._dns_spoofing_tab_page

            try:
                self._dns_spoofing_tab_page.set_ui_language(self._ui_language)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to create DNS spoofing tab: %s", e)

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

    def _switch_tab(self, index: int) -> None:
        """Switch between BlockCheck, strategy scan and diagnostics tabs."""
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

    def _apply_pending_diagnostics_start_focus(self) -> None:
        if not self._pending_diagnostics_start_focus:
            return
        self._ensure_diagnostics_tab()
        page = getattr(self, "connection_page", None)
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

    def _start_run_log(self, mode: str, extra_domains: list[str]) -> None:
        """Create a dedicated history log for current blockcheck run."""
        state = BlockcheckPageController.start_run_log(mode, extra_domains)
        self._run_log_file = state.path
        if not state.created:
            logger.warning("Failed to create blockcheck run log")

    def _append_run_log(self, message: str) -> None:
        """Append line(s) to current blockcheck run log."""
        BlockcheckPageController.append_run_log(self._run_log_file, message)

    def _on_start(self):
        if self._worker and self._worker.is_running:
            return

        # Get mode from combo
        mode = self._mode_combo.currentData()
        if mode is None:
            mode = "full"

        # Clear previous results
        self._table.setRowCount(0)
        if self._tcp_table is not None:
            self._tcp_table.setRowCount(0)
            self._tcp_table.setVisible(False)
        if self._tcp_section_label is not None:
            self._tcp_section_label.setVisible(False)
        self._dpi_card.setVisible(False)
        self._log_edit.clear()
        self._last_report = None
        self._runtime_warnings_seen.clear()
        self._set_support_status("")

        # UI state
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._mode_combo.setEnabled(False)
        self._skip_failed_cb.setEnabled(False)
        self._progress_bar.setVisible(True)
        if hasattr(self._progress_bar, 'start'):
            self._progress_bar.start()
        self._status_label.setText(
            tr_catalog("page.blockcheck.running", default="Запуск тестов...")
        )

        extra = self._get_extra_domains()
        self._start_run_log(mode, extra)

        # Create worker (QObject on main thread) — work runs in daemon thread
        skip_failed = self._skip_failed_cb.isChecked()
        self._worker = BlockcheckWorker(
            mode=mode, extra_domains=extra or None,
            skip_preflight_failed=skip_failed, parent=self,
        )
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.test_result.connect(self._on_test_result)
        self._worker.target_complete.connect(self._on_target_complete)
        self._worker.log_message.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_open_strategy_scan(self):
        """Legacy handler kept for compatibility with old button bindings."""
        self.switch_to_tab(self.TAB_STRATEGY_SCAN)

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
        self._stop_btn.setEnabled(False)
        self._status_label.setText(
            tr_catalog("page.blockcheck.stopping", default="Остановка...")
        )

        # If worker doesn't finish in 5s, just reset UI (daemon thread dies with app)
        QTimer.singleShot(5000, self._force_stop)

    def _force_stop(self):
        if self._worker and self._worker.is_running:
            # Daemon thread will die when app exits; just reset the UI
            self._reset_ui()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_phase_changed(self, phase: str):
        self._status_label.setText(phase)
        self._append_run_log(f"[PHASE] {phase}")

    def _on_test_result(self, result):
        """Update table with individual test result."""
        pass  # Table is updated on target_complete for better UX

    def _on_target_complete(self, target_result):
        """Add/update a row in the results table for a completed target."""
        from blockcheck.models import TestStatus, TestType

        name = target_result.name
        tests = target_result.tests

        if str(target_result.value).startswith("TCP:"):
            self._update_tcp_table(target_result)
            return

        # Find or create row
        row = self._find_row(name)
        if row == -1:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, self._make_item(name))

        # HTTP
        http_tests = [t for t in tests if t.test_type == TestType.HTTP]
        if http_tests:
            self._set_dualstack_status_cell(row, 1, http_tests)

        # TLS 1.2
        tls12 = [t for t in tests if t.test_type == TestType.TLS_12]
        tls13 = [t for t in tests if t.test_type == TestType.TLS_13]
        if tls12:
            # If TLS 1.2 fails but TLS 1.3 works — it's DPI blocking SNI (not an error)
            tls13_ok = any(r.status == TestStatus.OK for r in tls13)
            tls12_all_fail = all(r.status != TestStatus.OK for r in tls12)
            if tls12_all_fail and tls13_ok:
                r12_detail = build_family_tooltip(tls12)
                r12_detail += "\nDPI блокирует SNI в TLS 1.2; сайт работает через TLS 1.3"
                item = self._make_item("DPI 1.2")
                item.setForeground(QColor("#e0a854"))
                item.setToolTip(r12_detail)
                self._table.setItem(row, 2, item)
            else:
                self._set_dualstack_status_cell(row, 2, tls12)

        # TLS 1.3
        if tls13:
            self._set_dualstack_status_cell(row, 3, tls13)

        # DNS / ISP evidence
        dns_tests = [
            t for t in tests
            if t.test_type in (TestType.DNS_UDP, TestType.DNS_DOH)
        ]
        isp_tests = [t for t in tests if t.test_type == TestType.ISP_PAGE]
        if dns_tests:
            self._set_status_cell(row, 4, dns_tests[0])
        elif isp_tests:
            self._set_status_cell(row, 4, isp_tests[0])

        # DPI classification
        from blockcheck.models import DPIClassification
        cls = target_result.classification
        if cls != DPIClassification.NONE:
            label = _DPI_LABELS_RU.get(cls.value, cls.value)
            item = self._make_item(label)
            color = _DPI_BADGE_COLORS.get(cls.value, ("#e0a854", "#3a2e1a"))
            item.setForeground(QColor(color[0]))
            self._table.setItem(row, 5, item)
        else:
            self._table.setItem(row, 5, self._make_item("—"))

        # Ping
        ping = [t for t in tests if t.test_type == TestType.PING]
        if ping:
            self._set_dualstack_status_cell(row, 6, ping)

        # STUN (show in HTTP column for STUN targets)
        stun = [t for t in tests if t.test_type == TestType.STUN]
        if stun and not http_tests:
            self._set_status_cell(row, 1, stun[0])

        detail_text = build_target_detail_text(tests)
        detail_cell = self._make_item(truncate_detail(detail_text))
        detail_cell.setForeground(QColor("#9aa0a6"))
        detail_cell.setToolTip(detail_text)
        self._table.setItem(row, 7, detail_cell)

    def _on_log(self, message: str):
        self._log_edit.append(message)
        self._append_run_log(message)

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
        self._last_report = report
        self._reset_ui()

        if report is None:
            self._append_run_log("ERROR: Blockcheck execution failed")
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
        self._append_run_log(f"\nCompleted in {elapsed:.1f}s")
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
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._mode_combo.setEnabled(True)
        self._skip_failed_cb.setEnabled(True)
        self._progress_bar.setVisible(False)
        if hasattr(self._progress_bar, 'stop'):
            self._progress_bar.stop()

    def _set_support_status(self, text: str) -> None:
        if self._support_status_label is None:
            return
        self._support_status_label.setText(str(text or "").strip())

    def _prepare_support_from_blockcheck(self) -> None:
        mode_label = self._mode_combo.currentText() if self._mode_combo is not None else "BlockCheck"
        extra_domains = self._get_extra_domains()

        try:
            feedback = BlockcheckPageController.prepare_support(
                run_log_file=self._run_log_file,
                mode_label=mode_label,
                extra_domains=extra_domains,
            )
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
        except Exception as exc:
            logger.warning("Failed to prepare BlockCheck support bundle: %s", exc)
            self._set_support_status("Ошибка подготовки")
            try:
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog("page.blockcheck.error", default="Ошибка выполнения"),
                    f"Не удалось подготовить обращение:\n{exc}",
                )
            except Exception:
                pass

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

    def _find_row(self, name: str) -> int:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.text() == name:
                return row
        return -1

    def _find_tcp_row(self, target_id: str) -> int:
        if self._tcp_table is None:
            return -1
        for row in range(self._tcp_table.rowCount()):
            item = self._tcp_table.item(row, 0)
            if item and item.text() == target_id:
                return row
        return -1

    @staticmethod
    def _result_display_rank(result) -> int:
        from blockcheck.models import TestStatus

        if result.status == TestStatus.FAIL:
            return 0
        if result.status == TestStatus.ERROR:
            return 1
        if result.status == TestStatus.TIMEOUT:
            return 2
        if result.status == TestStatus.UNSUPPORTED:
            return 3
        return 4

    def _set_dualstack_status_cell(self, row: int, col: int, results: list) -> None:
        from blockcheck.models import TestStatus

        if not results:
            return

        if len(results) == 1:
            self._set_status_cell(row, col, results[0])
            return

        sorted_results = sort_results_by_family(results)
        ok_results = [r for r in sorted_results if r.status == TestStatus.OK]
        non_ok_results = [r for r in sorted_results if r.status != TestStatus.OK]

        if ok_results and non_ok_results:
            item = self._make_item("MIXED")
            item.setForeground(QColor("#e0a854"))
        elif ok_results:
            best_ok = min(ok_results, key=lambda r: r.time_ms or 999999.0)
            text = "OK"
            if best_ok.time_ms:
                text += f" ({best_ok.time_ms:.0f}ms)"
            item = self._make_item(text)
            item.setForeground(QColor("#52c477"))
        elif all(r.status == TestStatus.TIMEOUT for r in sorted_results):
            item = self._make_item("TIMEOUT")
            item.setForeground(QColor("#e0a854"))
        elif all(r.status == TestStatus.UNSUPPORTED for r in sorted_results):
            item = self._make_item("UNSUP")
            item.setForeground(QColor("#e0a854"))
        else:
            primary = sorted(non_ok_results, key=self._result_display_rank)[0] if non_ok_results else sorted_results[0]
            text = primary.error_code or "FAIL"
            item = self._make_item(text)
            item.setForeground(QColor("#e05454"))

        item.setToolTip(build_family_tooltip(sorted_results))
        self._table.setItem(row, col, item)

    def _build_target_detail_text(self, tests: list) -> str:
        from blockcheck.models import TestStatus, TestType

        ordered_types = [
            ("HTTP", TestType.HTTP),
            ("TLS1.2", TestType.TLS_12),
            ("TLS1.3", TestType.TLS_13),
            ("ISP", TestType.ISP_PAGE),
            ("DNS", TestType.DNS_UDP),
            ("DNS", TestType.DNS_DOH),
            ("Ping", TestType.PING),
        ]

        per_type: dict[TestType, list] = {}
        for t in tests:
            per_type.setdefault(t.test_type, []).append(t)

        parts: list[str] = []
        for label, test_type in ordered_types:
            candidates = sort_results_by_family(per_type.get(test_type, []))
            if not candidates:
                continue

            if len(candidates) == 1:
                chosen = candidates[0]
                if chosen.status == TestStatus.OK and test_type not in (TestType.TLS_12, TestType.TLS_13):
                    continue
                parts.append(f"{label}: {format_result_detail(chosen)}")
                continue

            has_non_ok = any(r.status != TestStatus.OK for r in candidates)
            if not has_non_ok and test_type not in (TestType.TLS_12, TestType.TLS_13):
                continue

            family_chunks = [
                f"{result_family_label(r)} {format_result_detail(r)}"
                for r in candidates
            ]
            parts.append(f"{label}: {' ; '.join(family_chunks)}")

        if not parts:
            return "OK"

        return " | ".join(parts)

    @staticmethod
    def _tcp_status_text_and_color(result) -> tuple[str, str]:
        from blockcheck.models import TestStatus

        if result.status == TestStatus.OK:
            return "OK", "#52c477"
        if result.status == TestStatus.TIMEOUT:
            return "TIMEOUT", "#e0a854"
        if result.error_code == "TCP_16_20":
            return "DETECTED", "#e05454"
        if result.status == TestStatus.UNSUPPORTED:
            return "UNSUP", "#e0a854"
        if result.status == TestStatus.ERROR:
            return "ERROR", "#e05454"
        return (result.error_code or "FAIL"), "#e05454"

    def _update_tcp_table(self, target_result) -> None:
        from blockcheck.models import TestType

        if self._tcp_table is None:
            return

        tcp_tests = sorted(
            [t for t in target_result.tests if t.test_type == TestType.TCP_16_20],
            key=lambda t: (t.raw_data or {}).get("target_id") or t.target_name or "",
        )
        if not tcp_tests:
            return

        if self._tcp_section_label is not None:
            self._tcp_section_label.setVisible(True)
        self._tcp_table.setVisible(True)

        for test in tcp_tests:
            raw = test.raw_data or {}
            target_id = str(raw.get("target_id") or test.target_name or "-")
            asn_raw = str(raw.get("asn") or "").strip()
            provider = str(raw.get("provider") or "-")

            if asn_raw:
                asn_text = asn_raw.upper() if asn_raw.upper().startswith("AS") else f"AS{asn_raw}"
            else:
                asn_text = "-"

            row = self._find_tcp_row(target_id)
            if row == -1:
                row = self._tcp_table.rowCount()
                self._tcp_table.insertRow(row)

            self._tcp_table.setItem(row, 0, self._make_item(target_id))
            self._tcp_table.setItem(row, 1, self._make_item(asn_text))
            self._tcp_table.setItem(row, 2, self._make_item(provider))

            status_text, color = self._tcp_status_text_and_color(test)
            status_item = self._make_item(status_text)
            status_item.setForeground(QColor(color))
            status_item.setToolTip(format_result_detail(test))
            self._tcp_table.setItem(row, 3, status_item)

            detail_text = format_result_detail(test)
            bytes_received = raw.get("bytes_received")
            if isinstance(bytes_received, int) and bytes_received > 0:
                detail_text += f" | {bytes_received}B"
            detail_item = self._make_item(truncate_detail(detail_text))
            detail_item.setForeground(QColor("#9aa0a6"))
            detail_item.setToolTip(detail_text)
            self._tcp_table.setItem(row, 4, detail_item)

    def _make_item(self, text: str):
        from PyQt6.QtWidgets import QTableWidgetItem
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _set_status_cell(self, row: int, col: int, result):
        from blockcheck.models import TestStatus

        if result.status == TestStatus.OK:
            text = "OK"
            if result.time_ms:
                text += f" ({result.time_ms:.0f}ms)"
            item = self._make_item(text)
            item.setForeground(QColor("#52c477"))
        elif result.status == TestStatus.UNSUPPORTED:
            item = self._make_item("UNSUP")
            item.setForeground(QColor("#e0a854"))
        elif result.status == TestStatus.TIMEOUT:
            item = self._make_item("TIMEOUT")
            item.setForeground(QColor("#e0a854"))
        else:
            text = result.error_code or "FAIL"
            item = self._make_item(text)
            item.setForeground(QColor("#e05454"))

        item.setToolTip(result.detail)
        self._table.setItem(row, col, item)

    def _update_dpi_summary(self, report):
        """Show DPI summary card after tests complete."""
        from blockcheck.models import DPIClassification

        self._dpi_card.setVisible(True)

        # Find worst DPI classification
        all_cls = [tr.classification for tr in report.targets]
        dpi_types = [c for c in all_cls if c != DPIClassification.NONE]

        if not dpi_types:
            cls_value = "none"
        else:
            # Priority: full_block > tls_dpi > tls_mitm > isp_page > etc
            priority = [
                DPIClassification.FULL_BLOCK,
                DPIClassification.TLS_MITM,
                DPIClassification.TLS_DPI,
                DPIClassification.ISP_PAGE,
                DPIClassification.HTTP_INJECT,
                DPIClassification.TCP_16_20,
                DPIClassification.TCP_RESET,
                DPIClassification.DNS_FAKE,
                DPIClassification.STUN_BLOCK,
            ]
            worst = DPIClassification.NONE
            for p in priority:
                if p in dpi_types:
                    worst = p
                    break
            cls_value = worst.value if worst != DPIClassification.NONE else dpi_types[0].value

        # Badge
        label = _DPI_LABELS_RU.get(cls_value, cls_value)
        fg, bg = _DPI_BADGE_COLORS.get(cls_value, ("#e0a854", "#3a2e1a"))
        dark = isDarkTheme()
        badge_bg = bg if dark else fg
        badge_fg = "#ffffff" if dark else "#ffffff"
        self._dpi_badge.setText(label)
        self._dpi_badge.setStyleSheet(
            f"background: {badge_bg}; color: {badge_fg}; "
            f"font-weight: 600; font-size: 13px; border-radius: 8px; padding: 6px 16px;"
        )

        # Detail
        details = []
        for tr in report.targets:
            if tr.classification != DPIClassification.NONE:
                details.append(f"{tr.name}: {_DPI_LABELS_RU.get(tr.classification.value, tr.classification.value)}")

        # Preflight summary (append before setText)
        if report.preflight:
            pf_passed = sum(1 for p in report.preflight if p.verdict.value == "passed")
            pf_warned = sum(1 for p in report.preflight if p.verdict.value == "warning")
            pf_failed = sum(1 for p in report.preflight if p.verdict.value == "failed")
            pf_text = f"Preflight: {pf_passed} OK"
            if pf_warned:
                pf_text += f", {pf_warned} предупр."
            if pf_failed:
                pf_text += f", {pf_failed} ошибок"
                failed_domains = [
                    p.domain for p in report.preflight if p.verdict.value == "failed"
                ]
                if failed_domains:
                    pf_text += f"\nПроблемные: {', '.join(failed_domains[:5])}"
                    if len(failed_domains) > 5:
                        pf_text += f" (+{len(failed_domains) - 5})"
            details.append(pf_text)

        if details:
            self._dpi_detail.setText("\n".join(details))
        else:
            self._dpi_detail.setText(
                tr_catalog("page.blockcheck.no_dpi", default="DPI не обнаружен на проверенных ресурсах")
            )

        # DNS summary
        if report.dns_integrity:
            dns_total = len(report.dns_integrity)
            comparable = [
                d for d in report.dns_integrity
                if d.is_comparable or bool(d.udp_ips and d.doh_ips)
            ]
            dns_ok = sum(1 for d in comparable if d.is_consistent and not d.is_stub)
            dns_fake = [d for d in comparable if (not d.is_consistent) or d.is_stub]
            dns_stubs = [d for d in report.dns_integrity if d.is_stub]
            dns_unknown = dns_total - len(comparable)

            if comparable:
                dns_text = f"DNS: {dns_ok}/{len(comparable)} OK (сравнимо)"
                if dns_fake:
                    dns_text += f"\nDNS подмена/аномалия: {len(dns_fake)}"
            else:
                dns_text = "DNS: нет сравнимых результатов (DoH недоступен)"

            if dns_unknown > 0:
                dns_text += f"\nБез сравнения DoH: {dns_unknown}"
            if dns_stubs:
                dns_text += f"\nDNS заглушки: {', '.join(d.domain for d in dns_stubs)}"
            self._dns_summary.setText(dns_text)
        else:
            self._dns_summary.setText("")

        # Recommendations
        recs = self._generate_recommendations(report)
        self._recommendation.setText(recs)

    @staticmethod
    def _generate_recommendations(report) -> str:
        """Generate recommendations based on test results."""
        from blockcheck.models import DPIClassification, TestStatus, TestType

        recs = []
        cls_set = {tr.classification for tr in report.targets}

        if DPIClassification.DNS_FAKE in cls_set:
            recs.append("DNS подменяется — используйте DoH/DoT или шифрованный DNS")
        if DPIClassification.TLS_DPI in cls_set:
            recs.append("TLS DPI обнаружен — включите обход DPI (zapret)")
        if DPIClassification.TLS_MITM in cls_set:
            recs.append("MITM прокси — проверьте сертификаты и VPN/прокси настройки")
        if DPIClassification.ISP_PAGE in cls_set or DPIClassification.HTTP_INJECT in cls_set:
            recs.append("HTTP инъекция/страница ISP — используйте HTTPS и обход DPI")
        if DPIClassification.TCP_16_20 in cls_set:
            recs.append("TCP блок 16-20KB — включите фрагментацию пакетов")
        if DPIClassification.STUN_BLOCK in cls_set:
            recs.append("STUN/UDP заблокирован — голосовые звонки могут не работать")
        if DPIClassification.FULL_BLOCK in cls_set:
            recs.append("Полная блокировка — попробуйте VPN или прокси")

        # Detect TLS 1.2 blocked + TLS 1.3 works pattern
        tls12_fail_13_ok = False
        for tr in report.targets:
            t12 = [t for t in tr.tests if t.test_type == TestType.TLS_12]
            t13 = [t for t in tr.tests if t.test_type == TestType.TLS_13]
            if t12 and t13 and t12[0].status != TestStatus.OK and t13[0].status == TestStatus.OK:
                tls12_fail_13_ok = True
                break
        if tls12_fail_13_ok:
            recs.append("TLS 1.2 блокируется (DPI видит SNI), но TLS 1.3 работает — сайты доступны через современные браузеры")

        if not recs:
            core_https_has_failures = False
            for tr in report.targets:
                for t in tr.tests:
                    if t.test_type in (TestType.HTTP, TestType.TLS_12, TestType.TLS_13) and t.status != TestStatus.OK:
                        core_https_has_failures = True
                        break
                if core_https_has_failures:
                    break

            if core_https_has_failures:
                recs.append(
                    "Есть проблемы доступа (TIMEOUT/FAIL), но сигнатура DPI не определена — "
                    "проверьте сеть/VPN/прокси и повторите тест"
                )
            else:
                recs.append("Блокировки не обнаружены — всё работает нормально")

        return "\n".join(f"• {r}" for r in recs)

    # ------------------------------------------------------------------
    # Custom domains
    # ------------------------------------------------------------------

    def _load_domain_chips(self):
        """Load persisted user domains and create chips."""
        load_domain_chips(
            load_domains_fn=BlockcheckPageController.load_user_domains,
            add_chip_fn=self._add_chip,
        )

    def _on_add_domain(self):
        """Add a domain from the input field."""
        text = self._domain_input.text().strip()
        if not text:
            return
        try:
            normalized = BlockcheckPageController.add_user_domain(text)
            if normalized:
                self._add_chip(normalized)
                self._domain_input.clear()
            else:
                # Already exists
                try:
                    InfoBarHelper.warning(
                        self.window(),
                        tr_catalog("page.blockcheck.domain_exists_title", default="Домен уже добавлен"),
                        text,
                    )
                except Exception:
                    pass
                self._domain_input.clear()
        except Exception as e:
            logger.warning("Failed to add domain: %s", e)

    def _on_remove_domain(self, domain: str):
        """Remove a domain chip and delete from persistence."""
        try:
            BlockcheckPageController.remove_user_domain(domain)
        except Exception:
            pass
        remove_domain_chip(
            domain=domain,
            flow_layout=self._domains_flow_layout,
            chip_cls=DomainChip,
        )

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
        if self._worker and self._worker.is_running:
            try:
                self._worker.stop()
            except Exception:
                pass

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
            self._start_btn.setToolTip(
                tr_catalog(
                    "page.blockcheck.action.start.description",
                    language=language,
                    default="Запустить анализ блокировок и проверку DPI для выбранного режима.",
                )
            )
            self._stop_btn.setToolTip(
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
