"""Strategy Scanner page — brute-force DPI bypass strategy selection.

Can be used as a standalone page or embedded as a tab inside BlockCheck.
Tests strategies one by one through winws2 + HTTPS probe.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QHeaderView, QMenu

from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        ComboBox, CaptionLabel, BodyLabel,
        ProgressBar, qconfig,
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
    SettingsCard, ActionButton, PrimaryActionButton, InfoBarHelper,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker (QObject, runs StrategyScanner in a daemon thread)
# ---------------------------------------------------------------------------

class StrategyScanWorker(QObject):
    """Bridges StrategyScanner (sync, bg thread) to Qt signals (main thread)."""

    strategy_started = pyqtSignal(str, int, int)   # name, index, total
    strategy_result = pyqtSignal(object)            # StrategyProbeResult
    scan_log = pyqtSignal(str)                      # log line
    phase_changed = pyqtSignal(str)                 # phase description
    scan_finished = pyqtSignal(object)              # StrategyScanReport

    def __init__(
        self,
        target: str,
        mode: str = "quick",
        start_index: int = 0,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
        parent=None,
    ):
        super().__init__(parent)
        self._target = target
        self._mode = mode
        self._scan_protocol = scan_protocol
        self._udp_games_scope = udp_games_scope
        try:
            self._start_index = max(0, int(start_index))
        except Exception:
            self._start_index = 0
        self._scanner = None
        self._cancelled = False
        self._bg_thread: threading.Thread | None = None

    def start(self):
        self._cancelled = False
        self._bg_thread = threading.Thread(
            target=self._run_in_thread, daemon=True, name="strategy-scan-worker",
        )
        self._bg_thread.start()

    def _run_in_thread(self):
        try:
            from blockcheck.strategy_scanner import StrategyScanner
            self._scanner = StrategyScanner(
                target=self._target,
                mode=self._mode,
                start_index=self._start_index,
                callback=self,
                scan_protocol=self._scan_protocol,
                udp_games_scope=self._udp_games_scope,
            )
            report = self._scanner.run()
            self.scan_finished.emit(report)
        except Exception as e:
            logger.exception("StrategyScanWorker crashed")
            self.scan_log.emit(f"ERROR: {e}")
            self.scan_finished.emit(None)

    def stop(self):
        self._cancelled = True
        if self._scanner:
            self._scanner.cancel()

    @property
    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()

    # --- StrategyScanCallback implementation (called from bg thread) ---
    def on_strategy_started(self, name, index, total):
        self.strategy_started.emit(name, index, total)

    def on_strategy_result(self, result):
        self.strategy_result.emit(result)

    def on_log(self, message):
        self.scan_log.emit(message)

    def on_phase(self, phase):
        self.phase_changed.emit(phase)

    def is_cancelled(self):
        return self._cancelled


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
        self._quick_domains_cache: list[str] | None = None
        self._quick_stun_targets_cache: list[str] | None = None
        self._target_label: QLabel | None = None
        self._games_scope_label: QLabel | None = None
        self._games_scope_combo = None
        self._udp_scope_hint_label: QLabel | None = None

        self._build_ui()
        self._connect_theme()

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
        log_header.addStretch()
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

        if self._log_expanded:
            # Скрываем остальные карточки
            self._control_card.setVisible(False)
            self._warning_card.setVisible(False)
            self._results_card.setVisible(False)
            # Убираем потолок высоты лога
            self._log_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self._log_edit.setMinimumHeight(400)
            self._expand_log_btn.setText("Свернуть")
        else:
            # Восстанавливаем карточки
            self._control_card.setVisible(True)
            self._warning_card.setVisible(True)
            self._results_card.setVisible(True)
            # Восстанавливаем ограничения
            self._log_edit.setMinimumHeight(180)
            self._log_edit.setMaximumHeight(300)
            self._expand_log_btn.setText("Развернуть")

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

    @staticmethod
    def _resume_state_path() -> Path:
        """Path to persisted strategy-scan resume state."""
        try:
            from config import APPDATA_DIR
            base_dir = Path(APPDATA_DIR)
        except Exception:
            try:
                from config import MAIN_DIRECTORY
                base_dir = Path(MAIN_DIRECTORY)
            except Exception:
                base_dir = Path.cwd()
        return base_dir / "strategy_scan_resume.json"

    @staticmethod
    def _target_key(
        target: str,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
    ) -> str:
        """Normalized key for per-target+protocol(+scope) resume state."""
        normalized_target = (target or "").strip().lower()
        normalized_protocol = (scan_protocol or "tcp_https").strip().lower() or "tcp_https"
        if not normalized_target:
            return ""

        if normalized_protocol == "udp_games":
            scope = (udp_games_scope or "all").strip().lower()
            if scope not in {"all", "games_only"}:
                scope = "all"
            return f"{normalized_protocol}|{scope}|{normalized_target}"

        return f"{normalized_protocol}|{normalized_target}"

    def _scan_protocol_from_combo(self) -> str:
        """Current scan protocol from UI combo."""
        data = self._protocol_combo.currentData()
        raw = str(data or "").strip().lower()
        if raw == "stun_voice":
            return "stun_voice"
        if raw == "udp_games":
            return "udp_games"
        return "tcp_https"

    @staticmethod
    def _normalize_udp_games_scope(scope: str) -> str:
        """Normalize UDP games scope key."""
        raw = (scope or "").strip().lower()
        if raw in {"games_only", "games", "only_games", "targeted"}:
            return "games_only"
        return "all"

    def _udp_games_scope_from_combo(self) -> str:
        """Current UDP games scope selection from UI combo."""
        if self._games_scope_combo is None:
            return "all"
        data = self._games_scope_combo.currentData()
        return self._normalize_udp_games_scope(str(data or "all"))

    @staticmethod
    def _default_target_for_protocol(scan_protocol: str) -> str:
        protocol = (scan_protocol or "").strip().lower()
        if protocol == "stun_voice":
            return "stun.l.google.com:19302"
        if protocol == "udp_games":
            return "stun.cloudflare.com:3478"
        return "discord.com"

    @staticmethod
    def _stun_target_parts(value: str, default_port: int = 3478) -> tuple[str, int]:
        """Parse STUN input into (host, port). Supports [IPv6]:port."""
        raw = (value or "").strip()
        if not raw:
            return "", default_port

        if raw.upper().startswith("STUN:"):
            raw = raw[5:].strip()

        raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
        raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if not raw:
            return "", default_port

        if raw.startswith("["):
            right = raw.find("]")
            if right > 1:
                host = raw[1:right].strip()
                rest = raw[right + 1 :].strip()
                if rest.startswith(":"):
                    try:
                        port = int(rest[1:])
                        if 1 <= port <= 65535:
                            return host, port
                    except ValueError:
                        pass
                return host, default_port

        if raw.count(":") == 1:
            host, port_str = raw.rsplit(":", 1)
            host = host.strip()
            if host:
                try:
                    port = int(port_str)
                    if 1 <= port <= 65535:
                        return host, port
                except ValueError:
                    pass
                return host, default_port

        # Likely IPv6 literal without brackets, or host without explicit port.
        return raw, default_port

    @staticmethod
    def _format_stun_target(host: str, port: int) -> str:
        host = (host or "").strip()
        if not host:
            return ""
        if ":" in host and not host.startswith("["):
            return f"[{host}]:{int(port)}"
        return f"{host}:{int(port)}"

    @staticmethod
    def _resolve_games_ipset_paths(udp_games_scope: str = "all") -> list[str]:
        """Resolve ipset paths for UDP games profile.

        Preference:
        1) Use ipset-all.txt if available (broad all-at-once coverage).
        2) Fallback to all available ipset-*.txt files.
        """

        scope = (udp_games_scope or "all").strip().lower()
        if scope not in {"all", "games_only"}:
            scope = "all"

        explicit_game_files = (
            "ipset-roblox.txt",
            "ipset-amazon.txt",
            "ipset-steam.txt",
            "ipset-epicgames.txt",
            "ipset-epic.txt",
            "ipset-lol-ru.txt",
            "ipset-lol-euw.txt",
            "ipset-tankix.txt",
        )

        list_dirs: list[Path] = []

        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            list_dirs.extend(
                [
                    Path(appdata) / "ZapretTwoDev" / "lists",
                    Path(appdata) / "ZapretTwo" / "lists",
                ]
            )

        try:
            from config import APPDATA_DIR, get_zapret_userdata_dir

            app_channel_dir = (APPDATA_DIR or "").strip()
            if app_channel_dir:
                list_dirs.append(Path(app_channel_dir) / "lists")

            user_data_dir = (get_zapret_userdata_dir() or "").strip()
            if user_data_dir:
                list_dirs.append(Path(user_data_dir) / "lists")
        except Exception:
            pass

        try:
            from config import MAIN_DIRECTORY

            list_dirs.append(Path(MAIN_DIRECTORY) / "lists")
        except Exception:
            list_dirs.append(Path.cwd() / "lists")

        files: list[str] = []
        seen: set[str] = set()
        for base_dir in list_dirs:
            if scope == "all":
                ipset_all = base_dir / "ipset-all.txt"
                key_all = str(ipset_all)
                if key_all not in seen:
                    seen.add(key_all)
                    if ipset_all.exists():
                        return [str(ipset_all)]

            for filename in explicit_game_files:
                candidate = base_dir / filename
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if candidate.exists():
                    files.append(str(candidate))

            if scope == "games_only":
                continue

            try:
                for candidate in sorted(base_dir.glob("ipset-*.txt")):
                    key = str(candidate)
                    if key in seen:
                        continue
                    seen.add(key)
                    if candidate.exists():
                        files.append(str(candidate))
            except OSError:
                continue

        if files:
            return files

        if scope == "games_only":
            return ["lists/ipset-roblox.txt"]
        return ["lists/ipset-all.txt"]

    @staticmethod
    def _normalize_target_domain(value: str) -> str:
        """Normalize manual input to a plain host name."""
        raw = (value or "").strip()
        if not raw:
            return ""
        try:
            from blockcheck.targets import _normalize_domain
            return _normalize_domain(raw)
        except Exception:
            return raw.lower()

    def _normalize_target_input(self, value: str, scan_protocol: str) -> str:
        """Normalize target input according to selected scan protocol."""
        protocol = (scan_protocol or "").strip().lower()
        if protocol in {"stun_voice", "udp_games"}:
            host, port = self._stun_target_parts(value)
            if not host:
                return ""
            return self._format_stun_target(host, port)
        return self._normalize_target_domain(value)

    def _on_protocol_changed(self, _index: int) -> None:
        """Adjust target input defaults when protocol changes."""
        protocol = self._scan_protocol_from_combo()
        current = self._target_input.text()

        is_udp_games = protocol == "udp_games"
        if self._games_scope_label is not None:
            self._games_scope_label.setVisible(is_udp_games)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setVisible(is_udp_games)
            self._games_scope_combo.setEnabled(is_udp_games)

        show_target_controls = protocol != "udp_games"
        if self._target_label is not None:
            self._target_label.setVisible(show_target_controls)
        self._target_input.setVisible(show_target_controls)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setVisible(show_target_controls)

        if protocol in {"stun_voice", "udp_games"} and current and ":" not in current and not current.upper().startswith("STUN:"):
            # When switching from TCP mode, a plain domain is usually not a STUN endpoint.
            current = ""

        normalized = self._normalize_target_input(current, protocol)
        if not normalized:
            normalized = self._default_target_for_protocol(protocol)

        self._target_input.setText(normalized)
        self._target_input.setPlaceholderText(self._default_target_for_protocol(protocol))
        self._refresh_udp_scope_hint()

    def _on_udp_games_scope_changed(self, _index: int) -> None:
        """Update UDP scope helper text after combo change."""
        self._refresh_udp_scope_hint()

    def _refresh_udp_scope_hint(self) -> None:
        """Refresh compact helper label with resolved UDP ipset sources."""
        if self._udp_scope_hint_label is None:
            return

        protocol = self._scan_protocol_from_combo()
        if protocol != "udp_games":
            self._udp_scope_hint_label.setVisible(False)
            return

        scope = self._udp_games_scope_from_combo()
        paths = self._resolve_games_ipset_paths(scope)

        if scope == "games_only":
            scope_label = tr_catalog("page.strategy_scan.udp_scope_games_only", default="Только игровые ipset")
        else:
            scope_label = tr_catalog("page.strategy_scan.udp_scope_all", default="Все ipset (по умолчанию)")

        short_names = [Path(p).name or p for p in paths]
        preview = ", ".join(short_names[:4])
        if len(short_names) > 4:
            preview += f", ... (+{len(short_names) - 4})"

        hint = (
            f"UDP scope: {scope_label} | "
            f"ipset files: {len(paths)} | {preview}"
        )
        self._udp_scope_hint_label.setText(hint)
        self._udp_scope_hint_label.setToolTip("\n".join(paths))
        self._udp_scope_hint_label.setVisible(True)

    def _load_quick_domains(self) -> list[str]:
        """Load and cache quick domain choices for strategy scan."""
        if self._quick_domains_cache is not None:
            return list(self._quick_domains_cache)

        try:
            from blockcheck.targets import load_domains
            raw_domains = load_domains()
        except Exception:
            raw_domains = []

        normalized_domains: list[str] = []
        seen: set[str] = set()
        for raw in raw_domains:
            domain = self._normalize_target_domain(str(raw))
            if not domain or domain in seen:
                continue
            seen.add(domain)
            normalized_domains.append(domain)

        self._quick_domains_cache = normalized_domains
        return list(self._quick_domains_cache)

    def _load_quick_stun_targets(self) -> list[str]:
        """Load and cache quick STUN endpoint choices."""
        if self._quick_stun_targets_cache is not None:
            return list(self._quick_stun_targets_cache)

        try:
            from blockcheck.targets import get_default_stun_targets
            raw_targets = get_default_stun_targets()
        except Exception:
            raw_targets = []

        targets: list[str] = []
        seen: set[str] = set()
        for item in raw_targets:
            value = str(item.get("value", ""))
            normalized = self._normalize_target_input(value, "stun_voice")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            targets.append(normalized)

        self._quick_stun_targets_cache = targets
        return list(self._quick_stun_targets_cache)

    def _show_quick_domains_menu(self) -> None:
        """Open popup menu with predefined targets for selected protocol."""
        if self._quick_domain_btn is None:
            return

        if HAS_FLUENT and RoundMenu is not None:
            menu = RoundMenu(parent=self)
        else:
            menu = QMenu(self)
        protocol = self._scan_protocol_from_combo()
        current = self._normalize_target_input(self._target_input.text(), protocol)
        options = self._load_quick_domains() if protocol == "tcp_https" else self._load_quick_stun_targets()

        for option in options:
            action = QAction(option, menu)
            action.setCheckable(True)
            action.setChecked(option == current)
            action.triggered.connect(
                lambda checked=False, selected_target=option: self._on_pick_quick_domain(selected_target)
            )
            menu.addAction(action)

        if not menu.actions():
            return

        menu.exec(self._quick_domain_btn.mapToGlobal(self._quick_domain_btn.rect().bottomLeft()))

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

    def _load_resume_state(self) -> dict:
        """Load persisted resume state (per-domain map) from disk."""
        path = self._resume_state_path()
        empty_state = {"domains": {}}
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return empty_state

            domains = data.get("domains")
            if isinstance(domains, dict):
                cleaned_domains = {}
                for raw_key, raw_value in domains.items():
                    raw_key_str = str(raw_key).strip().lower()
                    if not raw_key_str:
                        continue
                    if "|" in raw_key_str:
                        parts = raw_key_str.split("|")
                        if len(parts) == 2 and parts[0] == "udp_games":
                            key = f"udp_games|all|{parts[1]}"
                        else:
                            key = raw_key_str
                    else:
                        # Legacy target-only key -> assume TCP/HTTPS protocol.
                        key = self._target_key(raw_key_str, "tcp_https")
                    if not key:
                        continue
                    if isinstance(raw_value, dict):
                        raw_index = raw_value.get("next_index", 0)
                    else:
                        raw_index = raw_value
                    try:
                        next_index = max(0, int(raw_index))
                    except Exception:
                        next_index = 0
                    cleaned_domains[key] = {"next_index": next_index}
                return {"domains": cleaned_domains}

            # Legacy one-target schema fallback: {"target": ..., "next_index": ...}
            key = self._target_key(str(data.get("target", "") or ""))
            try:
                next_index = max(0, int(data.get("next_index", 0) or 0))
            except Exception:
                next_index = 0
            if key and next_index > 0:
                return {"domains": {key: {"next_index": next_index}}}
            return empty_state
        except Exception:
            return empty_state

    def _write_resume_state(self, state: dict) -> None:
        """Write persisted resume state to disk."""
        path = self._resume_state_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _get_resume_index(self, target: str, scan_protocol: str, udp_games_scope: str = "all") -> int:
        """Get persisted cursor for a specific target/protocol pair."""
        key = self._target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return 0
        state = self._load_resume_state()
        domains = state.get("domains", {})
        entry = domains.get(key, {})

        if not entry and (scan_protocol or "").strip().lower() == "udp_games":
            # Legacy key compatibility (before UDP scope key segment).
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            entry = domains.get(legacy_key, {})

        if not entry and (scan_protocol or "").strip().lower() == "tcp_https":
            # Legacy key compatibility (old schema had target-only keys).
            legacy_key = (target or "").strip().lower()
            entry = domains.get(legacy_key, {})
        try:
            return max(0, int(entry.get("next_index", 0) or 0))
        except Exception:
            return 0

    def _save_resume_state(
        self,
        target: str,
        scan_protocol: str,
        next_index: int,
        udp_games_scope: str = "all",
    ) -> None:
        """Persist resume cursor for a specific target/protocol pair."""
        key = self._target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = self._load_resume_state()
        domains = state.setdefault("domains", {})
        domains[key] = {"next_index": max(0, int(next_index))}
        self._write_resume_state(state)

    def _clear_resume_state(self, target: str, scan_protocol: str, udp_games_scope: str = "all") -> None:
        """Clear persisted resume cursor for a specific target/protocol pair."""
        key = self._target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = self._load_resume_state()
        domains = state.get("domains", {})
        if key in domains:
            del domains[key]

        if (scan_protocol or "").strip().lower() == "udp_games":
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            if legacy_key in domains:
                del domains[legacy_key]

        # Remove legacy key as well when clearing TCP target state.
        if (scan_protocol or "").strip().lower() == "tcp_https":
            legacy_key = (target or "").strip().lower()
            if legacy_key in domains:
                del domains[legacy_key]

        if domains:
            state["domains"] = domains
            self._write_resume_state(state)
        else:
            path = self._resume_state_path()
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    @staticmethod
    def _sanitize_slug(value: str, fallback: str) -> str:
        """Sanitize a value for use in log filenames."""
        raw = (value or "").strip().lower()
        cleaned = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw)
        cleaned = cleaned.strip("_")
        return cleaned or fallback

    @staticmethod
    def _resolve_log_dir() -> Path:
        """Resolve active logs directory (same folder as main app logs)."""
        try:
            from config import LOGS_FOLDER
            log_dir = Path(LOGS_FOLDER)
        except Exception:
            log_dir = Path.cwd() / "logs"

        try:
            from log import global_logger
            active_log = getattr(global_logger, "log_file", None)
            if isinstance(active_log, str) and active_log.strip():
                resolved_dir = Path(active_log).parent
                if str(resolved_dir):
                    log_dir = resolved_dir
        except Exception:
            pass

        return log_dir

    def _make_run_log_path(
        self,
        target: str,
        mode: str,
        scan_protocol: str,
        udp_games_scope: str = "all",
    ) -> Path:
        """Build per-run strategy-scan log path in logs folder."""
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_mode = self._sanitize_slug(mode, "mode")
        safe_protocol = self._sanitize_slug(scan_protocol, "protocol")
        safe_scope = self._sanitize_slug(udp_games_scope, "scope")
        safe_target = self._sanitize_slug(target, "target")
        scope_suffix = f"_{safe_scope}" if scan_protocol == "udp_games" else ""
        # Keep blockcheck_run_ prefix so Logs page/cleanup picks it up automatically.
        filename = (
            f"blockcheck_run_{ts}_strategy_scan_{safe_mode}_{safe_protocol}"
            f"{scope_suffix}_{safe_target}.log"
        )
        return self._resolve_log_dir() / filename

    def _start_run_log(
        self,
        target: str,
        mode: str,
        scan_protocol: str,
        resume_index: int,
        udp_games_scope: str = "all",
    ) -> None:
        """Create dedicated log file for current strategy-scan run."""
        primary_path = self._make_run_log_path(
            target=target,
            mode=mode,
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
        )
        candidates = [primary_path]

        try:
            from config import APPDATA_DIR
            candidates.append(Path(APPDATA_DIR) / "logs" / primary_path.name)
        except Exception:
            pass

        candidates.append(Path.cwd() / "logs" / primary_path.name)

        last_error = None
        tried: set[Path] = set()
        for path in candidates:
            if path in tried:
                continue
            tried.add(path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8-sig") as f:
                    f.write(f"=== Strategy Scan Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n")
                    f.write(f"Mode: {mode}\n")
                    f.write(f"Protocol: {scan_protocol}\n")
                    if scan_protocol == "udp_games":
                        f.write(f"UDP games scope: {udp_games_scope}\n")
                    f.write(f"Target: {target}\n")
                    f.write(f"Resume index: {max(0, int(resume_index))}\n")
                    f.write("=" * 70 + "\n\n")
                self._run_log_file = path
                return
            except Exception as e:
                last_error = e

        logger.warning("Failed to create strategy-scan run log: %s", last_error)
        self._run_log_file = None

    def _append_run_log(self, message: str) -> None:
        """Append line(s) to current strategy-scan run log."""
        if self._run_log_file is None:
            return
        try:
            text = str(message or "")
            if not text.endswith("\n"):
                text += "\n"
            with self._run_log_file.open("a", encoding="utf-8-sig") as f:
                f.write(text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _connect_theme(self):
        if HAS_FLUENT:
            qconfig.themeChanged.connect(lambda _: self._apply_theme())

    def _apply_theme(self):
        pass  # Table colors are set per-cell, no global refresh needed

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

        prev_target = self._scan_target
        prev_protocol = self._scan_protocol
        prev_scope = self._scan_udp_games_scope
        prev_target_key = self._target_key(prev_target, prev_protocol, prev_scope)

        scan_protocol = self._scan_protocol_from_combo()
        scan_games_scope = self._udp_games_scope_from_combo() if scan_protocol == "udp_games" else "all"

        target = self._normalize_target_input(self._target_input.text(), scan_protocol)
        if not target:
            target = self._default_target_for_protocol(scan_protocol)
        self._target_input.setText(target)
        target_key = self._target_key(target, scan_protocol, scan_games_scope)

        _MODE_MAP = {0: "quick", 1: "standard", 2: "full"}
        mode = _MODE_MAP.get(self._mode_combo.currentIndex(), "quick")

        resume_next_index = self._get_resume_index(target, scan_protocol, scan_games_scope)
        resume_available = resume_next_index > 0

        keep_current_results = (
            resume_available
            and prev_protocol == scan_protocol
            and prev_scope == scan_games_scope
            and prev_target_key == target_key
            and len(self._result_rows) == resume_next_index
            and self._table.rowCount() == len(self._result_rows)
        )

        if not keep_current_results:
            self._table.setRowCount(0)
            self._result_rows.clear()
            self._log_edit.clear()

        self._scan_target = target
        self._scan_protocol = scan_protocol
        self._scan_udp_games_scope = scan_games_scope
        self._scan_mode = mode
        self._scan_cursor = resume_next_index if resume_available else 0
        self._start_run_log(
            target=target,
            mode=mode,
            scan_protocol=scan_protocol,
            resume_index=self._scan_cursor,
            udp_games_scope=scan_games_scope,
        )

        # UI state
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._protocol_combo.setEnabled(False)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(False)
        self._mode_combo.setEnabled(False)
        self._target_input.setEnabled(False)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(self._scan_cursor)

        if resume_available:
            self._status_label.setText(
                f"Возобновление сканирования с [{self._scan_cursor + 1}]..."
            )
        else:
            self._status_label.setText(
                tr_catalog("page.strategy_scan.starting", default="Запуск сканирования...")
            )

        # Create and start worker
        self._worker = StrategyScanWorker(
            target=target,
            mode=mode,
            start_index=self._scan_cursor,
            scan_protocol=scan_protocol,
            udp_games_scope=scan_games_scope,
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
        if total > 0:
            self._progress_bar.setRange(0, total)
        if self._progress_bar.value() < self._scan_cursor:
            self._progress_bar.setValue(self._scan_cursor)
        working = sum(1 for r in self._result_rows if r.get("success"))
        self._status_label.setText(
            f"[{index + 1}/{total}] {name}  |  {working} рабочих"
        )

    def _on_strategy_result(self, result):
        """Add a row to the results table."""
        from PyQt6.QtWidgets import QTableWidgetItem

        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)

        # #
        num_item = QTableWidgetItem(str(self._scan_cursor + 1))
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 0, num_item)

        # Strategy name
        name_item = QTableWidgetItem(result.strategy_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tip_parts = [result.strategy_args]
        if result.error:
            tip_parts.append(f"\n--- Ошибка ---\n{result.error}")
        name_item.setToolTip("".join(tip_parts))
        self._table.setItem(row_idx, 1, name_item)

        # Status
        if result.success:
            status_item = QTableWidgetItem("OK")
            status_item.setForeground(QColor("#52c477"))
        elif "timeout" in result.error.lower():
            status_item = QTableWidgetItem("TIMEOUT")
            status_item.setForeground(QColor("#888888"))
        else:
            status_item = QTableWidgetItem("FAIL")
            status_item.setForeground(QColor("#e05454"))
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setToolTip(result.error if result.error else "OK")
        self._table.setItem(row_idx, 2, status_item)

        # Time
        time_text = f"{result.time_ms:.0f}" if result.time_ms > 0 else "—"
        time_item = QTableWidgetItem(time_text)
        time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 3, time_item)

        # Action button (only for successful strategies)
        if result.success:
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
        self._result_rows.append({
            "id": getattr(result, "strategy_id", ""),
            "name": result.strategy_name,
            "args": result.strategy_args,
            "success": result.success,
        })
        self._scan_cursor += 1
        self._progress_bar.setValue(self._scan_cursor)
        self._save_resume_state(
            self._scan_target,
            self._scan_protocol,
            self._scan_cursor,
            self._scan_udp_games_scope,
        )

        # Scroll to latest
        self._table.scrollToBottom()

    def _on_log(self, message: str):
        self._log_edit.append(message)
        self._append_run_log(message)

    def _on_phase_changed(self, phase: str):
        self._status_label.setText(phase)
        self._append_run_log(f"[PHASE] {phase}")

    def _on_finished(self, report):
        """Handle scan completion."""
        self._reset_ui()

        if report is None:
            if self._scan_cursor > 0:
                self._save_resume_state(
                    self._scan_target,
                    self._scan_protocol,
                    self._scan_cursor,
                    self._scan_udp_games_scope,
                )
            self._status_label.setText(
                tr_catalog("page.strategy_scan.error", default="Ошибка сканирования")
            )
            self._append_run_log("ERROR: Strategy scan execution failed")
            return

        total_available = max(0, int(getattr(report, "total_available", 0) or 0))
        if total_available > 0:
            self._progress_bar.setRange(0, total_available)

        if report.cancelled:
            if self._scan_cursor > 0:
                self._save_resume_state(
                    self._scan_target,
                    self._scan_protocol,
                    self._scan_cursor,
                    self._scan_udp_games_scope,
                )
            else:
                self._clear_resume_state(
                    self._scan_target,
                    self._scan_protocol,
                    self._scan_udp_games_scope,
                )
        else:
            full_scan_completed = (
                self._scan_mode == "full"
                and total_available > 0
                and report.total_tested >= total_available
            )
            if full_scan_completed:
                self._clear_resume_state(
                    self._scan_target,
                    self._scan_protocol,
                    self._scan_udp_games_scope,
                )
            else:
                self._save_resume_state(
                    self._scan_target,
                    self._scan_protocol,
                    report.total_tested,
                    self._scan_udp_games_scope,
                )

        working = sum(1 for r in self._result_rows if r.get("success"))
        total = max(self._scan_cursor, report.total_tested)
        elapsed = report.elapsed_seconds

        if report.cancelled:
            status = f"Отменено. Протестировано: {total}, рабочих: {working} ({elapsed:.1f}s)"
        else:
            status = f"Готово. Протестировано: {total}, рабочих: {working} ({elapsed:.1f}s)"

        self._status_label.setText(status)
        self._progress_bar.setValue(min(total, self._progress_bar.maximum()))
        self._append_run_log(f"\n{status}")

        try:
            if report.baseline_accessible:
                if self._scan_protocol in {"stun_voice", "udp_games"}:
                    if self._scan_protocol == "udp_games":
                        baseline_title_default = "UDP уже доступен"
                    else:
                        baseline_title_default = "STUN уже доступен"
                    baseline_title = tr_catalog(
                        "page.strategy_scan.baseline_ok_title_stun",
                        default=baseline_title_default,
                    )
                    baseline_text = tr_catalog(
                        "page.strategy_scan.baseline_ok_text_stun",
                        default="STUN/UDP уже доступен без обхода DPI — результаты могут быть ложноположительными",
                    )
                else:
                    baseline_title = tr_catalog(
                        "page.strategy_scan.baseline_ok_title",
                        default="Домен уже доступен",
                    )
                    baseline_text = tr_catalog(
                        "page.strategy_scan.baseline_ok_text",
                        default="Домен доступен без обхода DPI — результаты могут быть ложноположительными",
                    )
                InfoBarHelper.warning(
                    self.window(),
                    baseline_title,
                    baseline_text,
                )
            elif working > 0:
                InfoBarHelper.success(
                    self.window(),
                    tr_catalog("page.strategy_scan.found", default="Найдены рабочие стратегии"),
                    f"{working} из {total}",
                )
            else:
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog("page.strategy_scan.not_found", default="Рабочих стратегий не найдено"),
                    tr_catalog("page.strategy_scan.try_full",
                               default="Попробуйте полный режим сканирования"),
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def _on_apply_strategy(self, strategy_args: str, strategy_name: str):
        """Copy the working strategy into the selected source preset."""
        try:
            from core.services import get_direct_flow_coordinator
            from preset_zapret2 import PresetManager, get_preset_path

            selected_name = (get_direct_flow_coordinator().get_selected_preset_name("direct_zapret2") or "").strip()
            if not selected_name:
                InfoBarHelper.warning(
                    self.window(),
                    "Ошибка",
                    "Не удалось определить выбранный пресет",
                )
                return
            preset_path = get_preset_path(selected_name)

            target = self._scan_target or self._default_target_for_protocol(self._scan_protocol)

            # Generate blob definitions required by this strategy
            blob_lines = self._generate_blob_lines_for_apply(strategy_args)

            if self._scan_protocol == "stun_voice":
                target_host, target_port = self._stun_target_parts(target)
                if not target_host:
                    target_host = "stun.l.google.com"
                    target_port = 19302

                new_strategy_lines = [
                    "--wf-udp-out=443-65535",
                    "--filter-l7=stun,discord",
                    "--payload=stun,discord_ip_discovery",
                    strategy_args,
                ]
                applied_target = f"voice (probe: {self._format_stun_target(target_host, target_port)})"
            elif self._scan_protocol == "udp_games":
                games_ipset_paths = self._resolve_games_ipset_paths(self._scan_udp_games_scope)
                probe_host, probe_port = self._stun_target_parts(target)
                if not probe_host:
                    probe_host = "stun.cloudflare.com"
                    probe_port = 3478

                new_strategy_lines = [
                    "--wf-udp-out=443,50000-65535",
                    "--filter-udp=443,50000-65535",
                    *[f"--ipset={path}" for path in games_ipset_paths],
                    strategy_args,
                ]
                shown_paths = ", ".join(games_ipset_paths[:3])
                if len(games_ipset_paths) > 3:
                    shown_paths += f", ... (+{len(games_ipset_paths) - 3})"
                applied_target = (
                    f"Games UDP ipsets ({shown_paths}), "
                    f"probe {self._format_stun_target(probe_host, probe_port)}"
                )
            else:
                normalized_target = self._normalize_target_domain(target) or "discord.com"
                new_strategy_lines = [
                    "--filter-tcp=443",
                    f"--hostlist-domains={normalized_target}",
                    "--out-range=-d8",
                    strategy_args,
                ]
                applied_target = normalized_target

            try:
                existing_content = preset_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                existing_content = ""

            updated_content = self._prepend_strategy_block(
                existing_content=existing_content,
                strategy_lines=new_strategy_lines,
                blob_lines=blob_lines,
            )

            preset_path.write_text(updated_content, encoding="utf-8")
            try:
                from core.services import get_direct_flow_coordinator

                get_direct_flow_coordinator().refresh_selected_runtime("direct_zapret2")
            except Exception as e:
                log(f"Не удалось обновить generated launch config после apply strategy: {e}", "DEBUG")

            InfoBarHelper.success(
                self.window(),
                tr_catalog("page.strategy_scan.applied", default="Стратегия добавлена"),
                f"{strategy_name} добавлена в пресет для {applied_target}",
            )
        except Exception as e:
            logger.warning("Failed to apply strategy: %s", e)
            try:
                InfoBarHelper.warning(
                    self.window(),
                    "Ошибка",
                    str(e),
                )
            except Exception:
                pass

    @staticmethod
    def _generate_blob_lines_for_apply(strategy_args: str) -> list[str]:
        """Generate --blob= lines for blobs referenced in strategy_args."""
        try:
            from launcher_common.blobs import find_used_blobs, get_blobs
            used = find_used_blobs(strategy_args)
            if not used:
                return []
            blobs = get_blobs()
            return [f"--blob={name}:{blobs[name]}" for name in sorted(used) if name in blobs]
        except Exception:
            return []

    @staticmethod
    def _prepend_strategy_block(existing_content: str, strategy_lines: list[str], blob_lines: list[str]) -> str:
        """Insert a strategy block before the first existing strategy block."""
        normalized = (existing_content or "").replace("\r\n", "\n").replace("\r", "\n")
        all_lines = normalized.split("\n")

        first_filter_idx = len(all_lines)
        filter_prefixes = ("--filter-tcp", "--filter-udp", "--filter-l7")
        for idx, raw_line in enumerate(all_lines):
            if raw_line.strip().startswith(filter_prefixes):
                first_filter_idx = idx
                break

        prefix_lines = all_lines[:first_filter_idx]
        body_lines = all_lines[first_filter_idx:]

        while prefix_lines and not prefix_lines[-1].strip():
            prefix_lines.pop()

        prefix_set = {line.strip() for line in prefix_lines if line.strip()}
        missing_blob_lines = [line for line in blob_lines if line.strip() and line.strip() not in prefix_set]
        if missing_blob_lines:
            if prefix_lines and prefix_lines[-1].strip():
                prefix_lines.append("")
            prefix_lines.extend(missing_blob_lines)

        cleaned_strategy_lines = [line.strip() for line in strategy_lines if line and line.strip()]

        if prefix_lines and prefix_lines[-1].strip():
            prefix_lines.append("")

        result_lines = list(prefix_lines)
        result_lines.extend(cleaned_strategy_lines)

        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)

        if body_lines:
            result_lines.extend(["", "--new", ""])
            result_lines.extend(body_lines)

        return "\n".join(result_lines).rstrip("\n") + "\n"

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _reset_ui(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._protocol_combo.setEnabled(True)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(self._scan_protocol_from_combo() == "udp_games")
        self._mode_combo.setEnabled(True)
        self._target_input.setEnabled(True)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        try:
            self._control_card.set_title(
                tr_catalog("page.strategy_scan.control", language=language,
                           default="Управление сканированием"))
            self._results_card.set_title(
                tr_catalog("page.strategy_scan.results", language=language,
                           default="Результаты"))
            self._log_card.set_title(
                tr_catalog("page.strategy_scan.log", language=language,
                           default="Подробный лог"))
            self._expand_log_btn.setText(
                tr_catalog("page.strategy_scan.collapse_log", language=language,
                           default="Свернуть")
                if self._log_expanded else
                tr_catalog("page.strategy_scan.expand_log", language=language,
                           default="Развернуть")
            )
            self._warning_card.set_title(
                tr_catalog("page.strategy_scan.warning_title", language=language,
                           default="Внимание"))
            self._start_btn.setText(
                tr_catalog("page.strategy_scan.start", language=language,
                           default="Начать сканирование"))
            self._stop_btn.setText(
                tr_catalog("page.strategy_scan.stop", language=language,
                           default="Остановить"))
            self._protocol_combo.setItemText(
                0,
                tr_catalog("page.strategy_scan.protocol_tcp", language=language, default="TCP/HTTPS"),
            )
            self._protocol_combo.setItemText(
                1,
                tr_catalog(
                    "page.strategy_scan.protocol_stun",
                    language=language,
                    default="STUN Voice (Discord/Telegram)",
                ),
            )
            self._protocol_combo.setItemText(
                2,
                tr_catalog(
                    "page.strategy_scan.protocol_games",
                    language=language,
                    default="UDP Games (Roblox/Amazon/Steam)",
                ),
            )
            if self._games_scope_label is not None:
                self._games_scope_label.setText(
                    tr_catalog("page.strategy_scan.udp_scope", language=language, default="Охват UDP:")
                )
            if self._games_scope_combo is not None:
                self._games_scope_combo.setItemText(
                    0,
                    tr_catalog(
                        "page.strategy_scan.udp_scope_all",
                        language=language,
                        default="Все ipset (по умолчанию)",
                    ),
                )
                self._games_scope_combo.setItemText(
                    1,
                    tr_catalog(
                        "page.strategy_scan.udp_scope_games_only",
                        language=language,
                        default="Только игровые ipset",
                    ),
                )
            if self._quick_domain_btn is not None:
                self._quick_domain_btn.setText(
                    tr_catalog("page.strategy_scan.quick_domains", language=language,
                               default="Быстрый выбор"))
                self._quick_domain_btn.setToolTip(
                    tr_catalog("page.strategy_scan.quick_domains_hint", language=language,
                               default="Выберите домен из готового списка"))
            self._refresh_udp_scope_hint()
        except Exception:
            pass
