"""Strategy Scanner page — brute-force DPI bypass strategy selection.

Can be used as a standalone page or embedded as a tab inside BlockCheck.
Tests strategies one by one through winws2 + HTTPS probe.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QMenu

from blockcheck.strategy_scan_page_controller import StrategyScanPageController
from blockcheck.strategy_scan_worker import StrategyScanWorker
from ui.pages.base_page import BasePage
from ui.page_dependencies import require_page_app_context
from blockcheck.ui.strategy_scan_page_build import (
    build_strategy_scan_control_section,
    build_strategy_scan_log_section,
    build_strategy_scan_results_section,
)
from blockcheck.ui.strategy_scan_page_results_workflow import (
    add_strategy_result_row,
    append_scan_log,
    apply_finished_scan,
    apply_force_stop_status,
    apply_phase_change,
    apply_strategy_started_progress,
)
from blockcheck.ui.strategy_scan_page_runtime_helpers import (
    apply_language_plan_ui,
    apply_log_expand_state,
    prepare_strategy_scan_support,
    set_support_status,
)
from ui.popup_menu import exec_popup_menu
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        ComboBox, CaptionLabel, BodyLabel,
        ProgressBar,
        TableWidget, PushButton, LineEdit, RoundMenu,
    )
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    RoundMenu = None
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox,
        QTableWidget as TableWidget,
        QPushButton as PushButton,
        QLineEdit as LineEdit,
        QProgressBar as ProgressBar,
    )

from ui.compat_widgets import (
    SettingsCard, ActionButton, InfoBarHelper,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class StrategyScanPage(BasePage):
    """Strategy Scanner — brute-force DPI bypass strategy testing."""

    back_clicked = pyqtSignal()

    def __init__(self, parent=None, *, embedded: bool = False):
        self._embedded = bool(embedded)
        super().__init__(
            title=tr_catalog("page.strategy_scan.title", default="Подбор стратегии"),
            subtitle=tr_catalog("page.strategy_scan.subtitle",
                                default="Автоматический перебор стратегий обхода DPI"),
            parent=parent,
            title_key="page.strategy_scan.title",
            subtitle_key="page.strategy_scan.subtitle",
        )
        self.setObjectName("StrategyScanPage")

        self._worker: StrategyScanWorker | None = None
        self._result_rows: list[dict] = []
        self._scan_target: str = ""
        self._scan_protocol: str = "tcp_https"
        self._scan_udp_games_scope: str = "all"
        self._scan_mode: str = "quick"
        self._scan_cursor: int = 0
        self._run_log_file: Path | None = None
        self._quick_domain_btn: ActionButton | None = None
        self._target_label: QLabel | None = None
        self._games_scope_label: QLabel | None = None
        self._games_scope_combo = None
        self._udp_scope_hint_label: QLabel | None = None
        self._actions_title_label = None
        self._actions_bar = None
        self._prepare_support_btn = None
        self._support_status_label = None
        self._cleanup_in_progress = False

        self._build_ui()
        if self._embedded:
            try:
                if self.title_label is not None:
                    self.title_label.setVisible(False)
                if self.subtitle_label is not None:
                    self.subtitle_label.setVisible(False)
            except Exception:
                pass
            try:
                self.vBoxLayout.setContentsMargins(0, 8, 0, 0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        if not self._embedded:
            # ── Back button ──
            back_row = QHBoxLayout()
            back_btn = ActionButton(
                tr_catalog("page.strategy_scan.back", default="Назад"),
                icon_name="fa5s.arrow-left",
            )
            back_btn.clicked.connect(self._on_back)
            back_row.addWidget(back_btn)
            back_row.addStretch()
            self.add_widget(self._wrap_layout(back_row))

        # ── Control Card ──
        control_widgets = build_strategy_scan_control_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            has_fluent=HAS_FLUENT,
            combo_cls=ComboBox,
            caption_label_cls=CaptionLabel,
            body_label_cls=BodyLabel,
            progress_bar_cls=ProgressBar,
            push_button_cls=PushButton,
            line_edit_cls=LineEdit,
            parent=self.content,
            on_protocol_changed=self._on_protocol_changed,
            on_udp_games_scope_changed=self._on_udp_games_scope_changed,
            on_show_quick_domains_menu=self._show_quick_domains_menu,
            on_start=self._on_start,
            on_stop=self._on_stop,
        )
        self._control_card = control_widgets.control_card
        self._protocol_combo = control_widgets.protocol_combo
        self._games_scope_label = control_widgets.games_scope_label
        self._games_scope_combo = control_widgets.games_scope_combo
        self._mode_combo = control_widgets.mode_combo
        self._target_label = control_widgets.target_label
        self._target_input = control_widgets.target_input
        self._quick_domain_btn = control_widgets.quick_domain_btn
        self._udp_scope_hint_label = control_widgets.udp_scope_hint_label
        self._progress_bar = control_widgets.progress_bar
        self._status_label = control_widgets.status_label
        self._actions_title_label = control_widgets.actions_title_label
        self._actions_bar = control_widgets.actions_bar
        self._start_btn = control_widgets.start_btn
        self._stop_btn = control_widgets.stop_btn

        self.add_widget(self._control_card)
        self.add_widget(self._actions_title_label)
        self.add_widget(self._actions_bar)

        # ── Warning Card ──
        self._warning_card = SettingsCard(
            tr_catalog("page.strategy_scan.warning_title", default="Внимание")
        )
        warning_text = BodyLabel() if HAS_FLUENT else QLabel()
        warning_text.setText(tr_catalog(
            "page.strategy_scan.warning_text",
            default="Во время сканирования текущий обход DPI будет остановлен. "
                    "Каждая стратегия тестируется отдельно через winws2. "
                    "После завершения можно перезапустить обход.",
        ))
        warning_text.setWordWrap(True)
        self._warning_card.add_widget(warning_text)
        self.add_widget(self._warning_card)

        # ── Results Table Card ──
        results_widgets = build_strategy_scan_results_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            table_cls=TableWidget,
        )
        self._results_card = results_widgets.results_card
        self._table = results_widgets.table
        self.add_widget(self._results_card)

        # ── Log Card ──
        self._log_expanded = False
        log_widgets = build_strategy_scan_log_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            has_fluent=HAS_FLUENT,
            push_button_cls=PushButton,
            parent=self.content,
            on_toggle_log_expand=self._toggle_log_expand,
            on_prepare_support=self._prepare_support_from_strategy_scan,
        )
        self._log_card = log_widgets.log_card
        self._expand_log_btn = log_widgets.expand_log_btn
        self._support_status_label = log_widgets.support_status_label
        self._prepare_support_btn = log_widgets.prepare_support_btn
        self._log_edit = log_widgets.log_edit
        self.add_widget(self._log_card)

        self._on_protocol_changed(self._protocol_combo.currentIndex())

    # ------------------------------------------------------------------
    # Log expand / collapse
    # ------------------------------------------------------------------

    def _toggle_log_expand(self):
        """Развернуть/свернуть лог на всю страницу."""
        self._log_expanded = not self._log_expanded
        apply_log_expand_state(
            expanded=self._log_expanded,
            language=self._ui_language,
            control_card=self._control_card,
            warning_card=self._warning_card,
            results_card=self._results_card,
            log_edit=self._log_edit,
            expand_log_btn=self._expand_log_btn,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_layout(layout: QHBoxLayout) -> QWidget:
        """Wrap a layout in a transparent QWidget for add_widget()."""
        w = QWidget()
        w.setLayout(layout)
        w.setStyleSheet("background: transparent;")
        return w

    def _on_protocol_changed(self, _index: int) -> None:
        """Adjust target input defaults when protocol changes."""
        selection = StrategyScanPageController.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        plan = StrategyScanPageController.build_protocol_ui_plan(
            scan_protocol=selection.scan_protocol,
            current_value=self._target_input.text(),
        )

        if self._games_scope_label is not None:
            self._games_scope_label.setVisible(plan.is_udp_games)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setVisible(plan.is_udp_games)
            self._games_scope_combo.setEnabled(plan.is_udp_games)

        if self._target_label is not None:
            self._target_label.setVisible(plan.show_target_controls)
        self._target_input.setVisible(plan.show_target_controls)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setVisible(plan.show_target_controls)

        self._target_input.setText(plan.normalized_target)
        self._target_input.setPlaceholderText(plan.placeholder_text)
        self._refresh_udp_scope_hint()

    def _on_udp_games_scope_changed(self, _index: int) -> None:
        """Update UDP scope helper text after combo change."""
        self._refresh_udp_scope_hint()

    def _refresh_udp_scope_hint(self) -> None:
        """Refresh compact helper label with resolved UDP ipset sources."""
        if self._udp_scope_hint_label is None:
            return

        selection = StrategyScanPageController.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        hint_plan = StrategyScanPageController.build_udp_scope_hint_plan(
            scan_protocol=selection.scan_protocol,
            udp_games_scope=selection.udp_games_scope,
            scope_all_label=tr_catalog("page.strategy_scan.udp_scope_all", default="Все ipset (по умолчанию)"),
            scope_games_only_label=tr_catalog("page.strategy_scan.udp_scope_games_only", default="Только игровые ipset"),
        )
        self._udp_scope_hint_label.setText(hint_plan.text)
        self._udp_scope_hint_label.setToolTip(hint_plan.tooltip)
        self._udp_scope_hint_label.setVisible(hint_plan.visible)

    def _show_quick_domains_menu(self) -> None:
        """Open popup menu with predefined targets for selected protocol."""
        if self._quick_domain_btn is None:
            return

        if HAS_FLUENT and RoundMenu is not None:
            menu = RoundMenu(parent=self)
        else:
            menu = QMenu(self)
        selection = StrategyScanPageController.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        menu_plan = StrategyScanPageController.build_quick_target_menu_plan(
            scan_protocol=selection.scan_protocol,
            current_value=self._target_input.text(),
        )

        for option in menu_plan.options:
            action = QAction(option, menu)
            action.setCheckable(True)
            action.setChecked(option == menu_plan.current_value)
            action.triggered.connect(
                lambda checked=False, selected_target=option: self._on_pick_quick_domain(selected_target)
            )
            menu.addAction(action)

        if not menu.actions():
            return

        exec_popup_menu(
            menu,
            self._quick_domain_btn.mapToGlobal(self._quick_domain_btn.rect().bottomLeft()),
            owner=self,
        )

    def _on_pick_quick_domain(self, domain: str) -> None:
        """Fill the domain field from quick picker."""
        if not domain:
            return
        self._target_input.setText(domain)
        try:
            self._target_input.setFocus(Qt.FocusReason.OtherFocusReason)
            self._target_input.selectAll()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = tokens
        _ = force
        pass  # Table colors are set per-cell, no global refresh needed

    def _apply_language_plan(self, language: str) -> None:
        apply_language_plan_ui(
            language=language,
            log_expanded=self._log_expanded,
            control_card=self._control_card,
            results_card=self._results_card,
            log_card=self._log_card,
            expand_log_btn=self._expand_log_btn,
            warning_card=self._warning_card,
            start_btn=self._start_btn,
            stop_btn=self._stop_btn,
            actions_title_label=self._actions_title_label,
            prepare_support_btn=self._prepare_support_btn,
            protocol_combo=self._protocol_combo,
            games_scope_label=self._games_scope_label,
            games_scope_combo=self._games_scope_combo,
            quick_domain_btn=self._quick_domain_btn,
        )

    # ------------------------------------------------------------------
    # Navigation cleanup
    # ------------------------------------------------------------------

    def _on_back(self):
        """Navigate back without interrupting background scan."""
        self.back_clicked.emit()

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self):
        if self._worker and self._worker.is_running:
            return
        self._cleanup_in_progress = False

        selection = StrategyScanPageController.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex(),
        )

        start_plan = StrategyScanPageController.plan_scan_start(
            raw_target_input=self._target_input.text(),
            scan_protocol=selection.scan_protocol,
            udp_games_scope=selection.udp_games_scope,
            mode=selection.mode,
            previous_target=self._scan_target,
            previous_protocol=self._scan_protocol,
            previous_scope=self._scan_udp_games_scope,
            result_rows_count=len(self._result_rows),
            table_row_count=self._table.rowCount(),
            starting_status_text=tr_catalog("page.strategy_scan.starting", default="Запуск сканирования..."),
        )
        self._target_input.setText(start_plan.target)

        if not start_plan.keep_current_results:
            self._table.setRowCount(0)
            self._result_rows.clear()
            self._log_edit.clear()
        self._set_support_status("")

        self._scan_target = start_plan.target
        self._scan_protocol = start_plan.scan_protocol
        self._scan_udp_games_scope = start_plan.udp_games_scope
        self._scan_mode = start_plan.mode
        self._scan_cursor = start_plan.scan_cursor
        log_state = StrategyScanPageController.start_run_log(
            target=start_plan.target,
            mode=start_plan.mode,
            scan_protocol=start_plan.scan_protocol,
            resume_index=self._scan_cursor,
            udp_games_scope=start_plan.udp_games_scope,
        )
        self._run_log_file = log_state.path

        self._apply_interaction_plan(StrategyScanPageController.build_running_interaction_plan())
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(self._scan_cursor)
        self._status_label.setText(start_plan.status_text)

        # Create and start worker
        self._worker = StrategyScanWorker(
            target=start_plan.target,
            mode=start_plan.mode,
            start_index=self._scan_cursor,
            scan_protocol=start_plan.scan_protocol,
            udp_games_scope=start_plan.udp_games_scope,
            parent=self,
        )
        self._worker.strategy_started.connect(self._on_strategy_started)
        self._worker.strategy_result.connect(self._on_strategy_result)
        self._worker.scan_log.connect(self._on_log)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.scan_finished.connect(self._on_finished)
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
            expected_worker = self._worker
        else:
            expected_worker = None
        self._stop_btn.setEnabled(False)
        self._status_label.setText(
            tr_catalog("page.strategy_scan.stopping", default="Остановка...")
        )
        QTimer.singleShot(5000, lambda worker=expected_worker: self._force_stop(worker))

    def _force_stop(self, expected_worker=None):
        apply_force_stop_status(
            worker=self._worker,
            expected_worker=expected_worker,
            status_label=self._status_label,
            run_log_file=self._run_log_file,
            set_support_status=self._set_support_status,
        )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_strategy_started(self, name: str, index: int, total: int):
        if self._cleanup_in_progress:
            return
        apply_strategy_started_progress(
            strategy_name=name,
            index=index,
            total=total,
            result_rows=self._result_rows,
            progress_bar=self._progress_bar,
            status_label=self._status_label,
            scan_cursor=self._scan_cursor,
        )

    def _on_strategy_result(self, result):
        """Add a row to the results table."""
        if self._cleanup_in_progress:
            return
        stored_row = add_strategy_result_row(
            table=self._table,
            result=result,
            scan_cursor=self._scan_cursor,
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            push_button_cls=PushButton,
            on_apply_strategy=self._on_apply_strategy,
        )
        self._result_rows.append(dict(stored_row))
        self._scan_cursor += 1
        self._progress_bar.setValue(self._scan_cursor)
        StrategyScanPageController.save_resume_state(
            self._scan_target,
            self._scan_protocol,
            self._scan_cursor,
            self._scan_udp_games_scope,
        )

    def _on_log(self, message: str):
        if self._cleanup_in_progress:
            return
        append_scan_log(
            log_edit=self._log_edit,
            run_log_file=self._run_log_file,
            message=message,
        )

    def _on_phase_changed(self, phase: str):
        if self._cleanup_in_progress:
            return
        apply_phase_change(
            status_label=self._status_label,
            run_log_file=self._run_log_file,
            phase=phase,
        )

    def _on_finished(self, report):
        """Handle scan completion."""
        if self._cleanup_in_progress:
            return
        worker = self._worker
        self._worker = None
        apply_finished_scan(
            report,
            worker=worker,
            reset_ui=self._reset_ui,
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            scan_udp_games_scope=self._scan_udp_games_scope,
            scan_mode=self._scan_mode,
            scan_cursor=self._scan_cursor,
            result_rows=self._result_rows,
            progress_bar=self._progress_bar,
            status_label=self._status_label,
            run_log_file=self._run_log_file,
            set_support_status=self._set_support_status,
            window=self.window(),
        )

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def _on_apply_strategy(self, strategy_args: str, strategy_name: str):
        """Copy the working strategy into the selected source preset."""
        try:
            result = StrategyScanPageController.apply_strategy(
                app_context=require_page_app_context(
                    self,
                    parent=self.parent(),
                    error_message="AppContext is required for StrategyScanPage",
                ),
                strategy_args=strategy_args,
                strategy_name=strategy_name,
                scan_target=self._scan_target,
                scan_protocol=self._scan_protocol,
                scan_udp_games_scope=self._scan_udp_games_scope,
            )
            message_plan = StrategyScanPageController.build_apply_success_plan(result)

            InfoBarHelper.success(
                self.window(),
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception as e:
            logger.warning("Failed to apply strategy: %s", e)
            try:
                message_plan = StrategyScanPageController.build_apply_error_plan(str(e))
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog(message_plan.title_key, default=message_plan.title_default),
                    message_plan.body_text,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _apply_interaction_plan(self, plan) -> None:
        self._start_btn.setEnabled(plan.start_enabled)
        self._stop_btn.setEnabled(plan.stop_enabled)
        self._protocol_combo.setEnabled(plan.protocol_enabled)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(plan.games_scope_enabled)
        self._mode_combo.setEnabled(plan.mode_enabled)
        self._target_input.setEnabled(plan.target_enabled)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(plan.quick_domain_enabled)

    def _reset_ui(self):
        selection = StrategyScanPageController.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        self._apply_interaction_plan(
            StrategyScanPageController.build_idle_interaction_plan(
                is_udp_games=selection.scan_protocol == "udp_games",
            )
        )

    def _set_support_status(self, text: str) -> None:
        set_support_status(self._support_status_label, text)

    def _prepare_support_from_strategy_scan(self) -> None:
        prepare_strategy_scan_support(
            cleanup_in_progress=self._cleanup_in_progress,
            run_log_file=self._run_log_file,
            stored_scan_protocol=self._scan_protocol,
            stored_scan_target=self._scan_target,
            raw_protocol_value=self._protocol_combo.currentData() if self._protocol_combo is not None else None,
            raw_target_input=self._target_input.text(),
            raw_protocol_label=self._protocol_combo.currentText() if self._protocol_combo is not None else "",
            raw_mode_label=self._mode_combo.currentText() if self._mode_combo is not None else "",
            stored_mode=self._scan_mode,
            window=self.window(),
            support_status_label=self._support_status_label,
        )

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        try:
            self._apply_language_plan(language)
            self._refresh_udp_scope_hint()
        except Exception:
            pass

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        if self._worker is not None:
            try:
                self._worker.stop()
            except Exception:
                pass
            if not self._worker.is_running:
                try:
                    self._worker.deleteLater()
                except Exception:
                    pass
                self._worker = None
