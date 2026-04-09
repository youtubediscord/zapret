"""Strategy Scanner page — brute-force DPI bypass strategy selection.

Can be used as a standalone page or embedded as a tab inside BlockCheck.
Tests strategies one by one through winws2 + HTTPS probe.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QHeaderView, QMenu
import qtawesome as qta

from blockcheck.strategy_scan_page_controller import StrategyScanPageController
from blockcheck.strategy_scan_worker import StrategyScanWorker
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.popup_menu import exec_popup_menu
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        ComboBox, CaptionLabel, BodyLabel,
        ProgressBar,
        TableWidget, PushButton, LineEdit, RoundMenu,
        SettingCardGroup, PushSettingCard, PrimaryPushSettingCard,
    )
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    RoundMenu = None
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    PrimaryPushSettingCard = None  # type: ignore[assignment]
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox,
        QTableWidget as TableWidget,
        QPushButton as PushButton,
        QLineEdit as LineEdit,
        QProgressBar as ProgressBar,
    )

from ui.compat_widgets import (
    SettingsCard, ActionButton, PrimaryActionButton, InfoBarHelper,
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
        self._controller = StrategyScanPageController()
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
        self._actions_group = None
        self._start_action_card = None
        self._stop_action_card = None
        self._prepare_support_btn = None
        self._support_status_label = None

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
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
        self._control_card = SettingsCard(
            tr_catalog("page.strategy_scan.control", default="Управление сканированием")
        )

        # Row 1: protocol + mode + target
        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)

        protocol_label = CaptionLabel(
            tr_catalog("page.strategy_scan.protocol", default="Протокол:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.protocol", default="Протокол:"))
        settings_row.addWidget(protocol_label)

        self._protocol_combo = ComboBox()
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_tcp", default="TCP/HTTPS"),
            userData="tcp_https",
        )
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_stun", default="STUN Voice (Discord/Telegram)"),
            userData="stun_voice",
        )
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_games", default="UDP Games (Roblox/Amazon/Steam)"),
            userData="udp_games",
        )
        self._protocol_combo.setCurrentIndex(0)
        self._protocol_combo.setFixedWidth(150)
        self._protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        settings_row.addWidget(self._protocol_combo)

        self._games_scope_label = CaptionLabel(
            tr_catalog("page.strategy_scan.udp_scope", default="Охват UDP:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.udp_scope", default="Охват UDP:"))
        settings_row.addWidget(self._games_scope_label)

        self._games_scope_combo = ComboBox()
        self._games_scope_combo.addItem(
            tr_catalog("page.strategy_scan.udp_scope_all", default="Все ipset (по умолчанию)"),
            userData="all",
        )
        self._games_scope_combo.addItem(
            tr_catalog("page.strategy_scan.udp_scope_games_only", default="Только игровые ipset"),
            userData="games_only",
        )
        self._games_scope_combo.setCurrentIndex(0)
        self._games_scope_combo.setFixedWidth(220)
        self._games_scope_combo.currentIndexChanged.connect(self._on_udp_games_scope_changed)
        settings_row.addWidget(self._games_scope_combo)

        settings_row.addSpacing(16)

        mode_label = CaptionLabel(
            tr_catalog("page.strategy_scan.mode", default="Режим:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.mode", default="Режим:"))
        settings_row.addWidget(mode_label)

        self._mode_combo = ComboBox()
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_quick", default="Быстрый (30)"), "quick"
        )
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_standard", default="Стандартный (80)"), "standard"
        )
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_full", default="Полный (все)"), "full"
        )
        self._mode_combo.setCurrentIndex(0)
        self._mode_combo.setFixedWidth(180)
        settings_row.addWidget(self._mode_combo)

        settings_row.addSpacing(16)

        target_label = CaptionLabel(
            tr_catalog("page.strategy_scan.target", default="Цель:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.target", default="Цель:"))
        self._target_label = target_label
        settings_row.addWidget(target_label)

        self._target_input = LineEdit()
        self._target_input.setText(
            tr_catalog("page.strategy_scan.target.default", default="discord.com")
        )
        self._target_input.setPlaceholderText(
            tr_catalog("page.strategy_scan.target.placeholder", default="discord.com")
        )
        self._target_input.setFixedWidth(200)
        self._target_input.setFixedHeight(33)
        settings_row.addWidget(self._target_input)

        self._quick_domain_btn = ActionButton(
            tr_catalog("page.strategy_scan.quick_domains", default="Быстрый выбор"),
            icon_name="fa5s.list",
        )
        self._quick_domain_btn.setToolTip(
            tr_catalog(
                "page.strategy_scan.quick_domains_hint",
                default="Выберите домен из готового списка",
            )
        )
        self._quick_domain_btn.clicked.connect(self._show_quick_domains_menu)
        settings_row.addWidget(self._quick_domain_btn)

        settings_row.addStretch()
        self._control_card.add_layout(settings_row)

        self._udp_scope_hint_label = CaptionLabel("") if HAS_FLUENT else QLabel("")
        self._udp_scope_hint_label.setWordWrap(True)
        self._control_card.add_widget(self._udp_scope_hint_label)

        # Progress bar (determinate)
        self._progress_bar = ProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._control_card.add_widget(self._progress_bar)

        # Status label
        self._status_label = CaptionLabel(
            tr_catalog("page.strategy_scan.ready", default="Готово к сканированию")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.ready", default="Готово к сканированию"))
        self._control_card.add_widget(self._status_label)

        self.add_widget(self._control_card)

        if SettingCardGroup is not None and PushSettingCard is not None and PrimaryPushSettingCard is not None and HAS_FLUENT:
            actions_group = SettingCardGroup(
                tr_catalog("page.strategy_scan.actions.title", default="Действия"),
                self.content,
            )
            self._actions_group = actions_group

            self._start_action_card = PrimaryPushSettingCard(
                tr_catalog("page.strategy_scan.start", default="Начать сканирование"),
                qta.icon("fa5s.search", color="#4CAF50"),
                tr_catalog("page.strategy_scan.start", default="Начать сканирование"),
                tr_catalog(
                    "page.strategy_scan.action.start.description",
                    default="Запустить автоматический перебор стратегий обхода DPI для выбранной цели.",
                ),
            )
            self._start_action_card.clicked.connect(self._on_start)
            self._start_btn = self._start_action_card.button
            actions_group.addSettingCard(self._start_action_card)

            self._stop_action_card = PushSettingCard(
                tr_catalog("page.strategy_scan.stop", default="Остановить"),
                qta.icon("fa5s.stop", color="#ff9800"),
                tr_catalog("page.strategy_scan.stop", default="Остановить"),
                tr_catalog(
                    "page.strategy_scan.action.stop.description",
                    default="Остановить текущее сканирование стратегий и вернуть страницу в обычный режим.",
                ),
            )
            self._stop_action_card.clicked.connect(self._on_stop)
            self._stop_btn = self._stop_action_card.button
            self._stop_action_card.setEnabled(False)
            actions_group.addSettingCard(self._stop_action_card)

            self.add_widget(actions_group)
        else:
            # Row 2: buttons
            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)

            self._start_btn = PrimaryActionButton(
                tr_catalog("page.strategy_scan.start", default="Начать сканирование"),
                icon_name="fa5s.search",
            )
            self._start_btn.clicked.connect(self._on_start)
            btn_row.addWidget(self._start_btn)

            self._stop_btn = ActionButton(
                tr_catalog("page.strategy_scan.stop", default="Остановить"),
                icon_name="fa5s.stop",
            )
            self._stop_btn.setEnabled(False)
            self._stop_btn.clicked.connect(self._on_stop)
            btn_row.addWidget(self._stop_btn)

            btn_row.addStretch()
            self._control_card.add_layout(btn_row)

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
        self._results_card = SettingsCard(
            tr_catalog("page.strategy_scan.results", default="Результаты")
        )

        self._table = TableWidget()
        self._table.setColumnCount(5)
        headers = [
            "#",
            tr_catalog("page.strategy_scan.col_strategy", default="Стратегия"),
            tr_catalog("page.strategy_scan.col_status", default="Статус"),
            tr_catalog("page.strategy_scan.col_time", default="Время (мс)"),
            tr_catalog("page.strategy_scan.col_action", default="Действие"),
        ]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        self._table.setMinimumHeight(250)
        self._table.verticalHeader().setVisible(False)

        try:
            header = self._table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self._table.setColumnWidth(0, 50)
        except Exception:
            pass

        self._results_card.add_widget(self._table)
        self.add_widget(self._results_card)

        # ── Log Card ──
        self._log_card = SettingsCard(
            tr_catalog("page.strategy_scan.log", default="Подробный лог")
        )

        # Кнопка "Развернуть / Свернуть" в заголовке лог-карточки
        self._log_expanded = False
        self._expand_log_btn = PushButton()
        self._expand_log_btn.setText("Развернуть")
        self._expand_log_btn.setFixedWidth(120)
        self._expand_log_btn.clicked.connect(self._toggle_log_expand)
        log_header = QHBoxLayout()
        self._support_status_label = CaptionLabel("") if HAS_FLUENT else QLabel("")
        self._support_status_label.setWordWrap(True)
        log_header.addWidget(self._support_status_label, 1)
        log_header.addStretch()
        self._prepare_support_btn = ActionButton(
            tr_catalog(
                "page.strategy_scan.prepare_support",
                default="Подготовить обращение",
            ),
            icon_name="fa5b.github",
        )
        self._prepare_support_btn.clicked.connect(self._prepare_support_from_strategy_scan)
        log_header.addWidget(self._prepare_support_btn)
        log_header.addWidget(self._expand_log_btn)
        self._log_card.add_layout(log_header)

        self._log_edit = ScrollBlockingTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(180)
        self._log_edit.setMaximumHeight(300)
        self._log_edit.setFont(QFont("Consolas", 9))
        self._log_card.add_widget(self._log_edit)
        self.add_widget(self._log_card)

        self._on_protocol_changed(self._protocol_combo.currentIndex())

    # ------------------------------------------------------------------
    # Log expand / collapse
    # ------------------------------------------------------------------

    def _toggle_log_expand(self):
        """Развернуть/свернуть лог на всю страницу."""
        self._log_expanded = not self._log_expanded
        plan = self._controller.build_log_expand_plan(
            expanded=self._log_expanded,
            language=self._ui_language,
        )

        self._control_card.setVisible(plan.control_visible)
        self._warning_card.setVisible(plan.warning_visible)
        self._results_card.setVisible(plan.results_visible)
        self._log_edit.setMinimumHeight(plan.log_min_height)
        self._log_edit.setMaximumHeight(plan.log_max_height)
        self._expand_log_btn.setText(plan.button_text)

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
        selection = self._controller.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        plan = self._controller.build_protocol_ui_plan(
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

        selection = self._controller.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        hint_plan = self._controller.build_udp_scope_hint_plan(
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
        selection = self._controller.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        menu_plan = self._controller.build_quick_target_menu_plan(
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
        plan = self._controller.build_language_plan(
            language=language,
            log_expanded=self._log_expanded,
        )
        self._control_card.set_title(plan.control_title)
        self._results_card.set_title(plan.results_title)
        self._log_card.set_title(plan.log_title)
        self._expand_log_btn.setText(plan.expand_log_text)
        self._warning_card.set_title(plan.warning_title)
        self._start_btn.setText(plan.start_text)
        self._stop_btn.setText(plan.stop_text)
        try:
            title_label = getattr(getattr(self, "_actions_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(tr_catalog("page.strategy_scan.actions.title", default="Действия"))
        except Exception:
            pass
        if self._start_action_card is not None:
            self._start_action_card.setTitle(plan.start_text)
            self._start_action_card.setContent(
                tr_catalog(
                    "page.strategy_scan.action.start.description",
                    default="Запустить автоматический перебор стратегий обхода DPI для выбранной цели.",
                )
            )
        if self._stop_action_card is not None:
            self._stop_action_card.setTitle(plan.stop_text)
            self._stop_action_card.setContent(
                tr_catalog(
                    "page.strategy_scan.action.stop.description",
                    default="Остановить текущее сканирование стратегий и вернуть страницу в обычный режим.",
                )
            )
        if self._prepare_support_btn is not None:
            self._prepare_support_btn.setText(plan.prepare_support_text)
        self._protocol_combo.setItemText(0, plan.protocol_items[0])
        self._protocol_combo.setItemText(1, plan.protocol_items[1])
        self._protocol_combo.setItemText(2, plan.protocol_items[2])
        if self._games_scope_label is not None:
            self._games_scope_label.setText(plan.udp_scope_label)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setItemText(0, plan.udp_scope_items[0])
            self._games_scope_combo.setItemText(1, plan.udp_scope_items[1])
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setText(plan.quick_domains_text)
            self._quick_domain_btn.setToolTip(plan.quick_domains_tooltip)

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

        selection = self._controller.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex(),
        )

        start_plan = self._controller.plan_scan_start(
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
        log_state = self._controller.start_run_log(
            target=start_plan.target,
            mode=start_plan.mode,
            scan_protocol=start_plan.scan_protocol,
            resume_index=self._scan_cursor,
            udp_games_scope=start_plan.udp_games_scope,
        )
        self._run_log_file = log_state.path

        self._apply_interaction_plan(self._controller.build_running_interaction_plan())
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
        self._stop_btn.setEnabled(False)
        self._status_label.setText(
            tr_catalog("page.strategy_scan.stopping", default="Остановка...")
        )
        # Force-reset UI if worker doesn't finish in 5s
        QTimer.singleShot(5000, self._force_stop)

    def _force_stop(self):
        if self._worker and self._worker.is_running:
            self._reset_ui()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_strategy_started(self, name: str, index: int, total: int):
        progress_plan = self._controller.build_progress_plan(
            strategy_name=name,
            index=index,
            total=total,
            result_rows=self._result_rows,
        )
        if progress_plan.total > 0:
            self._progress_bar.setRange(0, progress_plan.total)
        if self._progress_bar.value() < self._scan_cursor:
            self._progress_bar.setValue(self._scan_cursor)
        self._status_label.setText(progress_plan.status_text)

    def _on_strategy_result(self, result):
        """Add a row to the results table."""
        from PyQt6.QtWidgets import QTableWidgetItem

        row_plan = self._controller.build_result_presentation(
            result,
            scan_cursor=self._scan_cursor,
        )
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)

        # #
        num_item = QTableWidgetItem(row_plan.number_text)
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 0, num_item)

        # Strategy name
        name_item = QTableWidgetItem(row_plan.strategy_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        name_item.setToolTip(row_plan.strategy_tooltip)
        self._table.setItem(row_idx, 1, name_item)

        # Status
        status_item = QTableWidgetItem(row_plan.status_text)
        if row_plan.status_tone == "success":
            status_item.setForeground(QColor("#52c477"))
        elif row_plan.status_tone == "timeout":
            status_item.setForeground(QColor("#888888"))
        else:
            status_item.setForeground(QColor("#e05454"))
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setToolTip(row_plan.status_tooltip)
        self._table.setItem(row_idx, 2, status_item)

        # Time
        time_item = QTableWidgetItem(row_plan.time_text)
        time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 3, time_item)

        # Action button (only for successful strategies)
        if row_plan.can_apply:
            apply_btn = PushButton()
            apply_btn.setText(tr_catalog("page.strategy_scan.apply", default="Применить"))
            apply_btn.setFixedHeight(26)
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.clicked.connect(
                lambda checked=False, args=result.strategy_args, name=result.strategy_name:
                    self._on_apply_strategy(args, name)
            )
            self._table.setCellWidget(row_idx, 4, apply_btn)

        # Track result and update progress after test completes
        self._result_rows.append(dict(row_plan.stored_row))
        self._scan_cursor += 1
        self._progress_bar.setValue(self._scan_cursor)
        self._controller.save_resume_state(
            self._scan_target,
            self._scan_protocol,
            self._scan_cursor,
            self._scan_udp_games_scope,
        )

        # Scroll to latest
        self._table.scrollToBottom()

    def _on_log(self, message: str):
        self._log_edit.append(message)
        self._controller.append_run_log(self._run_log_file, message)

    def _on_phase_changed(self, phase: str):
        self._status_label.setText(phase)
        self._controller.append_run_log(self._run_log_file, f"[PHASE] {phase}")

    def _on_finished(self, report):
        """Handle scan completion."""
        self._reset_ui()
        finish_plan = self._controller.finalize_scan_report(
            report,
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            scan_udp_games_scope=self._scan_udp_games_scope,
            scan_mode=self._scan_mode,
            scan_cursor=self._scan_cursor,
            result_rows=self._result_rows,
        )

        if finish_plan.total_available > 0:
            self._progress_bar.setRange(0, finish_plan.total_available)

        self._status_label.setText(finish_plan.status_text)
        self._progress_bar.setValue(min(finish_plan.total_count, self._progress_bar.maximum()))
        if finish_plan.log_message:
            self._controller.append_run_log(self._run_log_file, finish_plan.log_message)

        if finish_plan.support_status_code == "ready_after_error":
            self._set_support_status(
                tr_catalog(
                    "page.strategy_scan.support_ready_after_error",
                    default="Можно подготовить обращение по логам ошибки",
                )
            )
            return

        self._set_support_status(
            tr_catalog(
                "page.strategy_scan.support_ready",
                default="Можно подготовить обращение по этому сканированию",
            )
        )

        try:
            notification_plan = self._controller.build_finish_notification_plan(
                finish_plan,
                scan_protocol=self._scan_protocol,
            )
            if notification_plan.kind == "warning" and notification_plan.title_key:
                title_text = tr_catalog(
                    notification_plan.title_key,
                    default=notification_plan.title_default,
                )
                body_text = (
                    notification_plan.body_text
                    or tr_catalog(
                        notification_plan.body_key,
                        default=notification_plan.body_default,
                    )
                )
                InfoBarHelper.warning(
                    self.window(),
                    title_text,
                    body_text,
                )
            elif notification_plan.kind == "success" and notification_plan.title_key:
                InfoBarHelper.success(
                    self.window(),
                    tr_catalog(
                        notification_plan.title_key,
                        default=notification_plan.title_default,
                    ),
                    notification_plan.body_text,
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def _on_apply_strategy(self, strategy_args: str, strategy_name: str):
        """Copy the working strategy into the selected source preset."""
        try:
            result = self._controller.apply_strategy(
                strategy_args=strategy_args,
                strategy_name=strategy_name,
                scan_target=self._scan_target,
                scan_protocol=self._scan_protocol,
                scan_udp_games_scope=self._scan_udp_games_scope,
            )
            message_plan = self._controller.build_apply_success_plan(result)

            InfoBarHelper.success(
                self.window(),
                tr_catalog(message_plan.title_key, default=message_plan.title_default),
                message_plan.body_text,
            )
        except Exception as e:
            logger.warning("Failed to apply strategy: %s", e)
            try:
                message_plan = self._controller.build_apply_error_plan(str(e))
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
        if self._start_action_card is not None:
            self._start_action_card.setEnabled(plan.start_enabled)
        if self._stop_action_card is not None:
            self._stop_action_card.setEnabled(plan.stop_enabled)
        self._protocol_combo.setEnabled(plan.protocol_enabled)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(plan.games_scope_enabled)
        self._mode_combo.setEnabled(plan.mode_enabled)
        self._target_input.setEnabled(plan.target_enabled)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(plan.quick_domain_enabled)

    def _reset_ui(self):
        selection = self._controller.build_selection_state(
            protocol_value=self._protocol_combo.currentData(),
            udp_scope_value=self._games_scope_combo.currentData() if self._games_scope_combo is not None else "all",
            mode_index=self._mode_combo.currentIndex() if self._mode_combo is not None else 0,
        )
        self._apply_interaction_plan(
            self._controller.build_idle_interaction_plan(
                is_udp_games=selection.scan_protocol == "udp_games",
            )
        )

    def _set_support_status(self, text: str) -> None:
        if self._support_status_label is None:
            return
        self._support_status_label.setText(str(text or "").strip())

    def _prepare_support_from_strategy_scan(self) -> None:
        support_context = self._controller.build_support_context(
            stored_scan_protocol=self._scan_protocol,
            stored_scan_target=self._scan_target,
            raw_protocol_value=self._protocol_combo.currentData() if self._protocol_combo is not None else None,
            raw_target_input=self._target_input.text(),
            raw_protocol_label=self._protocol_combo.currentText() if self._protocol_combo is not None else "",
            raw_mode_label=self._mode_combo.currentText() if self._mode_combo is not None else "",
            stored_mode=self._scan_mode,
        )

        try:
            feedback = self._controller.prepare_support(
                run_log_file=self._run_log_file,
                target=support_context.target,
                protocol_label=support_context.protocol_label,
                mode_label=support_context.mode_label,
                scan_protocol=support_context.scan_protocol,
            )
            result = feedback.result
            if result.zip_path:
                logger.info("Prepared Strategy Scan support archive: %s", result.zip_path)

            message_plan = self._controller.build_support_success_plan(feedback)
            self._set_support_status(message_plan.status_text)

            try:
                InfoBarHelper.success(
                    self.window(),
                    tr_catalog(message_plan.title_key, default=message_plan.title_default),
                    message_plan.body_text,
                )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Failed to prepare strategy-scan support bundle: %s", exc)
            message_plan = self._controller.build_support_error_plan(str(exc))
            self._set_support_status(message_plan.status_text)
            try:
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog(message_plan.title_key, default=message_plan.title_default),
                    message_plan.body_text,
                )
            except Exception:
                pass

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
