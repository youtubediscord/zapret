"""Strategy Scanner page — brute-force DPI bypass strategy selection.

Can be used as a standalone page or embedded as a tab inside BlockCheck.
Tests strategies one by one through winws2 + HTTPS probe.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from settings.mode import ENGINE_WINWS2

from ui.pages.base_page import BasePage
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
from blockcheck.strategy_scan_run_workflow import (
    cleanup_strategy_scan_worker,
    delete_strategy_scan_worker_later,
    request_strategy_scan_stop,
    start_strategy_scan_run,
    start_strategy_scan_worker,
)
from blockcheck.ui.strategy_scan_page_runtime_helpers import (
    apply_language_plan_ui,
    apply_log_expand_state,
    set_support_status,
)
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.popup_menu import exec_popup_menu
from app.ui_texts import tr as tr_catalog
from qfluentwidgets import (
    ComboBox,
    CaptionLabel,
    BodyLabel,
    ProgressBar,
    TableWidget,
    PushButton,
    LineEdit,
    RoundMenu,
    Action,
)

from ui.fluent_widgets import (
    SettingsCard, InfoBarHelper, set_tooltip,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class StrategyScanPage(BasePage):
    """Strategy Scanner — brute-force DPI bypass strategy testing."""

    def __init__(self, parent=None, *, embedded: bool = False, blockcheck_feature, runtime_feature):
        self._embedded = bool(embedded)
        super().__init__(
            title=tr_catalog("page.blockcheck_public.title", default="Подбор стратегии"),
            subtitle=tr_catalog("page.blockcheck_public.subtitle",
                                default="Автоматический перебор стратегий обхода DPI"),
            parent=parent,
            title_key="page.blockcheck_public.title",
            subtitle_key="page.blockcheck_public.subtitle",
        )
        self.setObjectName("StrategyScanPage")

        self._blockcheck = blockcheck_feature
        self._runtime_feature = runtime_feature
        self._worker = None
        self._result_rows: list[dict] = []
        self._scan_target: str = ""
        self._scan_protocol: str = "tcp_https"
        self._scan_udp_games_scope: str = "all"
        self._scan_mode: str = "quick"
        self._scan_cursor: int = 0
        self._run_log_file: Path | None = None
        self._quick_domain_btn: PushButton | None = None
        self._target_label: QLabel | None = None
        self._games_scope_label: QLabel | None = None
        self._games_scope_combo = None
        self._udp_scope_hint_label: QLabel | None = None
        self._actions_title_label = None
        self._actions_bar = None
        self._prepare_support_btn = None
        self._support_status_label = None
        self._cleanup_in_progress = False
        self._strategy_apply_worker = None
        self._strategy_apply_request_id = 0
        self._support_prepare_worker = None
        self._support_prepare_request_id = 0
        self._quick_targets_runtime = OneShotWorkerRuntime()
        self._strategy_scan_resume_save_runtime = OneShotWorkerRuntime()
        self._strategy_scan_resume_save_pending = None
        self._strategy_scan_finalize_runtime = OneShotWorkerRuntime()

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

    def create_support_prepare_worker(
        self,
        request_id: int,
        *,
        run_log_file,
        target: str,
        protocol_label: str,
        mode_label: str,
        scan_protocol: str,
    ):
        return self._blockcheck.create_strategy_scan_support_prepare_worker(
            request_id,
            run_log_file=run_log_file,
            target=target,
            protocol_label=protocol_label,
            mode_label=mode_label,
            scan_protocol=scan_protocol,
            parent=self,
        )

    def create_quick_targets_worker(self, request_id: int, *, scan_protocol: str, current_value: str):
        return self._blockcheck.create_strategy_scan_quick_targets_worker(
            request_id,
            scan_protocol=scan_protocol,
            current_value=current_value,
            parent=self,
        )

    def create_strategy_scan_resume_save_worker(
        self,
        request_id: int,
        *,
        scan_target: str,
        scan_protocol: str,
        next_index: int,
        udp_games_scope: str,
    ):
        return self._blockcheck.create_strategy_scan_resume_save_worker(
            request_id,
            scan_target=scan_target,
            scan_protocol=scan_protocol,
            next_index=next_index,
            udp_games_scope=udp_games_scope,
            parent=self,
        )

    def create_strategy_scan_finalize_worker(self, request_id: int, *, report):
        return self._blockcheck.create_strategy_scan_finalize_worker(
            request_id,
            report=report,
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            scan_udp_games_scope=self._scan_udp_games_scope,
            scan_mode=self._scan_mode,
            scan_cursor=self._scan_cursor,
            result_rows=list(self._result_rows),
            parent=self,
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Control Card ──
        control_widgets = build_strategy_scan_control_section(
            tr_fn=lambda key, default: tr_catalog(key, default=default),
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
            tr_catalog("page.blockcheck_public.warning_title", default="Внимание")
        )
        warning_text = BodyLabel()
        warning_text.setText(tr_catalog(
            "page.blockcheck_public.warning_text",
            default="Во время сканирования текущий обход DPI будет остановлен. "
                    f"Каждая стратегия тестируется отдельно через {ENGINE_WINWS2}. "
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
            blockcheck_feature=self._blockcheck,
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
        selection = self._blockcheck.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        plan = self._blockcheck.build_protocol_ui_plan(
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

        selection = self._blockcheck.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        hint_plan = self._blockcheck.build_udp_scope_hint_plan(
            scan_protocol=selection.scan_protocol,
            udp_games_scope=selection.udp_games_scope,
            scope_all_label=tr_catalog("page.blockcheck_public.udp_scope_all", default="Все ipset (по умолчанию)"),
            scope_games_only_label=tr_catalog("page.blockcheck_public.udp_scope_games_only", default="Только игровые ipset"),
        )
        self._udp_scope_hint_label.setText(hint_plan.text)
        set_tooltip(self._udp_scope_hint_label, hint_plan.tooltip)
        self._udp_scope_hint_label.setVisible(hint_plan.visible)

    def _show_quick_domains_menu(self) -> None:
        """Open popup menu with predefined targets for selected protocol."""
        if self._quick_domain_btn is None:
            return

        selection = self._blockcheck.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        self._request_quick_targets_menu(
            scan_protocol=selection.scan_protocol,
            current_value=self._target_input.text(),
        )

    def _request_quick_targets_menu(self, *, scan_protocol: str, current_value: str) -> None:
        if self._quick_targets_runtime.is_running():
            return

        def worker_factory(request_id: int):
            return self.create_quick_targets_worker(
                request_id,
                scan_protocol=scan_protocol,
                current_value=current_value,
            )

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_quick_targets_loaded)
            worker.failed.connect(self._on_quick_targets_failed)

        self._quick_targets_runtime.start_qthread_worker(
            worker_factory=worker_factory,
            bind_worker=bind_worker,
        )

    def _on_quick_targets_loaded(self, request_id: int, menu_plan) -> None:
        if not self._quick_targets_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._open_quick_targets_menu(menu_plan)

    def _on_quick_targets_failed(self, request_id: int, error: str) -> None:
        if not self._quick_targets_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        logger.warning("Failed to load quick targets: %s", error)

    def _open_quick_targets_menu(self, menu_plan) -> None:
        if self._quick_domain_btn is None:
            return
        menu = RoundMenu(parent=self)
        for option in menu_plan.options:
            action = Action(option, menu)
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
            blockcheck_feature=self._blockcheck,
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
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self):
        if self._worker and self._worker.is_running:
            return
        self._cleanup_in_progress = False

        run_result = start_strategy_scan_run(
            blockcheck_feature=self._blockcheck,
            runtime_feature=self._runtime_feature,
            raw_target_input=self._target_input.text(),
            raw_protocol_value=self._protocol_combo.currentData(),
            raw_udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex(),
            previous_target=self._scan_target,
            previous_protocol=self._scan_protocol,
            previous_scope=self._scan_udp_games_scope,
            result_rows_count=len(self._result_rows),
            table_row_count=self._table.rowCount(),
            starting_status_text=tr_catalog("page.blockcheck_public.starting", default="Запуск сканирования..."),
            parent=self,
            on_run_log_started=self._on_run_log_started,
            on_strategy_started=self._on_strategy_started,
            on_strategy_result=self._on_strategy_result,
            on_log=self._on_log,
            on_phase_changed=self._on_phase_changed,
            on_finished=self._on_finished,
        )
        self._target_input.setText(run_result.target)

        if not run_result.keep_current_results:
            self._table.setRowCount(0)
            self._result_rows.clear()
            self._log_edit.clear()
        self._set_support_status("")

        self._scan_target = run_result.target
        self._scan_protocol = run_result.scan_protocol
        self._scan_udp_games_scope = run_result.udp_games_scope
        self._scan_mode = run_result.mode
        self._scan_cursor = run_result.scan_cursor
        self._run_log_file = None
        self._worker = run_result.worker

        self._apply_interaction_plan(self._blockcheck.build_running_interaction_plan())
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(self._scan_cursor)
        self._status_label.setText(run_result.status_text)
        start_strategy_scan_worker(self._worker)

    def _on_stop(self):
        request_strategy_scan_stop(
            worker=self._worker,
            schedule_stop_check=lambda expected_worker:
            QTimer.singleShot(5000, lambda worker=expected_worker: self._force_stop(worker)),
        )
        self._stop_btn.setEnabled(False)
        self._status_label.setText(
            tr_catalog("page.blockcheck_public.stopping", default="Остановка...")
        )

    def _force_stop(self, expected_worker=None):
        apply_force_stop_status(
            worker=self._worker,
            expected_worker=expected_worker,
            status_label=self._status_label,
            set_support_status=self._set_support_status,
        )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_run_log_started(self, run_log_file) -> None:
        if self._cleanup_in_progress:
            return
        self._run_log_file = run_log_file

    def _on_strategy_started(self, name: str, index: int, total: int):
        if self._cleanup_in_progress:
            return
        apply_strategy_started_progress(
            blockcheck_feature=self._blockcheck,
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
            blockcheck_feature=self._blockcheck,
            table=self._table,
            result=result,
            scan_cursor=self._scan_cursor,
            tr_fn=lambda key, default: tr_catalog(key, default=default),
            push_button_cls=PushButton,
            on_apply_strategy=self._on_apply_strategy,
        )
        self._result_rows.append(dict(stored_row))
        self._scan_cursor = int(self._scan_cursor) + 1
        self._request_strategy_scan_resume_save(
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            udp_games_scope=self._scan_udp_games_scope,
            next_index=self._scan_cursor,
        )
        self._progress_bar.setValue(self._scan_cursor)

    def _request_strategy_scan_resume_save(
        self,
        *,
        scan_target: str,
        scan_protocol: str,
        udp_games_scope: str,
        next_index: int,
    ) -> None:
        payload = {
            "scan_target": scan_target,
            "scan_protocol": scan_protocol,
            "udp_games_scope": udp_games_scope,
            "next_index": int(next_index),
        }
        if self._strategy_scan_resume_save_runtime.is_running():
            self._strategy_scan_resume_save_pending = payload
            return

        self._strategy_scan_resume_save_pending = None
        self._start_strategy_scan_resume_save_worker(payload)

    def _start_strategy_scan_resume_save_worker(self, payload: dict) -> None:
        if self._cleanup_in_progress:
            return

        def worker_factory(request_id: int):
            return self.create_strategy_scan_resume_save_worker(request_id, **payload)

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_strategy_scan_resume_save_finished)
            worker.failed.connect(self._on_strategy_scan_resume_save_failed)

        self._strategy_scan_resume_save_runtime.start_qthread_worker(
            worker_factory=worker_factory,
            bind_worker=bind_worker,
            on_finished=self._on_strategy_scan_resume_save_runtime_finished,
        )

    def _on_strategy_scan_resume_save_finished(self, request_id: int, _result) -> None:
        if not self._strategy_scan_resume_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return

    def _on_strategy_scan_resume_save_failed(self, request_id: int, error: str) -> None:
        if not self._strategy_scan_resume_save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        logger.warning("Failed to save strategy-scan resume progress: %s", error)

    def _on_strategy_scan_resume_save_runtime_finished(self, _worker) -> None:
        pending = self.__dict__.get("_strategy_scan_resume_save_pending")
        if pending is not None and not self._cleanup_in_progress:
            self._strategy_scan_resume_save_pending = None
            self._start_strategy_scan_resume_save_worker(pending)

    def _on_log(self, message: str):
        if self._cleanup_in_progress:
            return
        append_scan_log(
            log_edit=self._log_edit,
            message=message,
        )

    def _on_phase_changed(self, phase: str):
        if self._cleanup_in_progress:
            return
        apply_phase_change(
            status_label=self._status_label,
            phase=phase,
        )

    def _on_finished(self, report):
        """Handle scan completion."""
        if self._cleanup_in_progress:
            return
        worker = self._worker
        self._worker = None
        delete_strategy_scan_worker_later(worker)
        self._request_strategy_scan_finalize(report)

    def _request_strategy_scan_finalize(self, report) -> None:
        if self._strategy_scan_finalize_runtime.is_running():
            return

        def worker_factory(request_id: int):
            return self.create_strategy_scan_finalize_worker(request_id, report=report)

        def bind_worker(worker) -> None:
            worker.completed.connect(self._on_strategy_scan_finalize_finished)
            worker.failed.connect(self._on_strategy_scan_finalize_failed)

        self._strategy_scan_finalize_runtime.start_qthread_worker(
            worker_factory=worker_factory,
            bind_worker=bind_worker,
        )

    def _on_strategy_scan_finalize_finished(self, request_id: int, finish_plan) -> None:
        if not self._strategy_scan_finalize_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        apply_finished_scan(
            blockcheck_feature=self._blockcheck,
            finish_plan=finish_plan,
            reset_ui=self._reset_ui,
            scan_protocol=self._scan_protocol,
            progress_bar=self._progress_bar,
            status_label=self._status_label,
            set_support_status=self._set_support_status,
            parent_widget=self.window(),
        )

    def _on_strategy_scan_finalize_failed(self, request_id: int, error: str) -> None:
        if not self._strategy_scan_finalize_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        logger.warning("Failed to finalize strategy scan: %s", error)
        self._reset_ui()
        self._status_label.setText(
            tr_catalog("page.blockcheck_public.scan_finish_error", default="Ошибка завершения сканирования")
        )
        self._set_support_status(
            tr_catalog(
                "page.blockcheck_public.support_ready_after_error",
                default="Можно подготовить обращение по логам ошибки",
            )
        )

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def _on_apply_strategy(self, strategy_args: str, strategy_name: str):
        """Copy the working strategy into the selected source preset."""
        self._request_strategy_apply(strategy_args, strategy_name)

    def create_strategy_apply_worker(self, request_id: int, *, strategy_args: str, strategy_name: str):
        return self._blockcheck.create_strategy_apply_worker(
            request_id,
            strategy_args=strategy_args,
            strategy_name=strategy_name,
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            scan_udp_games_scope=self._scan_udp_games_scope,
            parent=self,
        )

    def _request_strategy_apply(self, strategy_args: str, strategy_name: str) -> None:
        worker = self.__dict__.get("_strategy_apply_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return

        self._strategy_apply_request_id += 1
        request_id = self._strategy_apply_request_id
        worker = self.create_strategy_apply_worker(
            request_id,
            strategy_args=strategy_args,
            strategy_name=strategy_name,
        )
        self._strategy_apply_worker = worker
        worker.completed.connect(self._on_strategy_apply_finished)
        worker.failed.connect(self._on_strategy_apply_failed)
        worker.finished.connect(lambda w=worker: self._on_strategy_apply_worker_finished(w))
        worker.start()

    def _on_strategy_apply_finished(self, request_id: int, result) -> None:
        if request_id != self._strategy_apply_request_id or self._cleanup_in_progress:
            return
        message_plan = self._blockcheck.build_apply_success_plan(result)

        InfoBarHelper.success(
            self.window(),
            tr_catalog(message_plan.title_key, default=message_plan.title_default),
            message_plan.body_text,
        )

    def _on_strategy_apply_failed(self, request_id: int, error: str) -> None:
        if request_id != self._strategy_apply_request_id or self._cleanup_in_progress:
            return
        logger.warning("Failed to apply strategy: %s", error)
        try:
            message_plan = self._blockcheck.build_apply_error_plan(str(error))
            InfoBarHelper.warning(
                self.window(),
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception:
            pass

    def _on_strategy_apply_worker_finished(self, worker) -> None:
        if self.__dict__.get("_strategy_apply_worker") is worker:
            self._strategy_apply_worker = None
        worker.deleteLater()

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
        selection = self._blockcheck.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        self._apply_interaction_plan(
            self._blockcheck.build_idle_interaction_plan(
                is_udp_games=selection.scan_protocol == "udp_games",
            )
        )

    def _set_support_status(self, text: str) -> None:
        set_support_status(self._support_status_label, text)

    def _prepare_support_from_strategy_scan(self) -> None:
        if self._cleanup_in_progress:
            return
        support_context = self._blockcheck.build_support_context(
            stored_scan_protocol=self._scan_protocol,
            stored_scan_target=self._scan_target,
            raw_protocol_value=self._protocol_combo.currentData() if self._protocol_combo is not None else None,
            raw_target_input=self._target_input.text(),
            raw_protocol_label=self._protocol_combo.currentText() if self._protocol_combo is not None else "",
            raw_mode_label=self._mode_combo.currentText() if self._mode_combo is not None else "",
            stored_mode=self._scan_mode,
        )
        self._request_support_prepare(
            run_log_file=self._run_log_file,
            target=support_context.target,
            protocol_label=support_context.protocol_label,
            mode_label=support_context.mode_label,
            scan_protocol=support_context.scan_protocol,
        )

    def _request_support_prepare(
        self,
        *,
        run_log_file,
        target: str,
        protocol_label: str,
        mode_label: str,
        scan_protocol: str,
    ) -> None:
        worker = self.__dict__.get("_support_prepare_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    self._set_support_status("Подготовка уже идёт...")
                    return
            except Exception:
                return

        self._support_prepare_request_id += 1
        request_id = self._support_prepare_request_id
        self._set_support_status("Подготовка обращения...")
        if self._prepare_support_btn is not None:
            self._prepare_support_btn.setEnabled(False)

        worker = self.create_support_prepare_worker(
            request_id,
            run_log_file=run_log_file,
            target=target,
            protocol_label=protocol_label,
            mode_label=mode_label,
            scan_protocol=scan_protocol,
        )
        self._support_prepare_worker = worker
        worker.completed.connect(self._on_support_prepare_finished)
        worker.failed.connect(self._on_support_prepare_failed)
        worker.finished.connect(lambda w=worker: self._on_support_prepare_worker_finished(w))
        worker.start()

    def _on_support_prepare_finished(self, request_id: int, feedback) -> None:
        if request_id != self._support_prepare_request_id or self._cleanup_in_progress:
            return
        result = feedback.result
        if result.zip_path:
            logger.info("Prepared Strategy Scan support archive: %s", result.zip_path)

        message_plan = self._blockcheck.build_support_success_plan(feedback)
        self._set_support_status(message_plan.status_text)

        try:
            InfoBarHelper.success(
                self.window(),
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception:
            pass

    def _on_support_prepare_failed(self, request_id: int, error: str) -> None:
        if request_id != self._support_prepare_request_id or self._cleanup_in_progress:
            return
        logger.warning("Failed to prepare strategy-scan support bundle: %s", error)
        message_plan = self._blockcheck.build_support_error_plan(str(error))
        self._set_support_status(message_plan.status_text)
        try:
            InfoBarHelper.warning(
                self.window(),
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception:
            pass

    def _on_support_prepare_worker_finished(self, worker) -> None:
        if self.__dict__.get("_support_prepare_worker") is worker:
            self._support_prepare_worker = None
        try:
            worker.deleteLater()
        except Exception:
            pass
        if not self._cleanup_in_progress and self._prepare_support_btn is not None:
            self._prepare_support_btn.setEnabled(True)

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
        worker = self.__dict__.get("_strategy_apply_worker")
        if worker is not None:
            try:
                worker.quit()
            except Exception:
                pass
            self._strategy_apply_worker = None
        support_worker = self.__dict__.get("_support_prepare_worker")
        if support_worker is not None:
            try:
                support_worker.quit()
            except Exception:
                pass
            self._support_prepare_worker = None
        self._quick_targets_runtime.stop(
            blocking=False,
            warning_prefix="strategy scan quick targets worker",
        )
        self._quick_targets_runtime.cancel()
        self._strategy_scan_resume_save_pending = None
        self._strategy_scan_resume_save_runtime.stop(
            blocking=False,
            warning_prefix="strategy scan resume save worker",
        )
        self._strategy_scan_resume_save_runtime.cancel()
        self._strategy_scan_finalize_runtime.stop(
            blocking=False,
            warning_prefix="strategy scan finalize worker",
        )
        self._strategy_scan_finalize_runtime.cancel()
        self._worker = cleanup_strategy_scan_worker(self._worker)
