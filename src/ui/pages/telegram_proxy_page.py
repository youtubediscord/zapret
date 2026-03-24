# ui/pages/telegram_proxy_page.py
"""Telegram WebSocket Proxy — UI page.

Provides controls for starting/stopping the proxy, mode selection,
port configuration, and quick-setup deep link for Telegram.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget, QLineEdit,
)
from PyQt6.QtGui import QGuiApplication

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens
from log import log

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        SpinBox, InfoBar, InfoBarPosition,
        SegmentedWidget, ComboBox,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QSpinBox as SpinBox, QComboBox as ComboBox
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    InfoBar = None
    SegmentedWidget = None
    _HAS_FLUENT = True

if TYPE_CHECKING:
    from main import LupiDPIApp

# Lazy import to avoid circular deps
_proxy_manager = None


def _get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        from telegram_proxy.manager import TelegramProxyManager
        _proxy_manager = TelegramProxyManager()
    return _proxy_manager


# How often (ms) the GUI reads new log lines from the ring buffer
_LOG_REFRESH_MS = 500

def _load_upstream_presets() -> list[dict]:
    """Load SOCKS5 proxy presets from build secrets. Returns list with "Ручной ввод" first."""
    manual = [{"name": "Ручной ввод", "host": "", "port": 0, "username": "", "password": ""}]
    try:
        from config._build_secrets import PROXY_PRESETS
        if isinstance(PROXY_PRESETS, list) and PROXY_PRESETS:
            return manual + PROXY_PRESETS
    except ImportError:
        pass
    return manual


def _load_mtproxy_link() -> str:
    """Load MTProxy link from build secrets. Returns empty string if missing."""
    try:
        from config._build_secrets import MTPROXY_LINK
        return MTPROXY_LINK or ""
    except ImportError:
        return ""



class _StatusDot(QWidget):
    """Small colored circle indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#4CAF50") if self._active else QColor("#888888")
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 10, 10)
        p.end()


class TelegramProxyPage(BasePage):
    """Telegram WebSocket Proxy settings page."""

    def __init__(self, parent=None):
        super().__init__(
            "Telegram Proxy",
            "Маршрутизация трафика Telegram через WebSocket для обхода ЗАМЕДЛЕНИЯ (не поддерживает полный блок) по IP",
            parent,
        )
        self.parent_app = parent
        self._setup_ui()
        self._connect_signals()
        # Load settings AFTER range is set (see _setup_ui)
        QTimer.singleShot(0, self._load_settings)
        # Log refresh timer — drains ring buffer every 500ms
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._flush_log_buffer)
        self._log_timer.start(_LOG_REFRESH_MS)
        # Auto-start if enabled
        QTimer.singleShot(500, self._auto_start_check)

    def _setup_ui(self):
        # ── Tabs (SegmentedWidget) ──
        if SegmentedWidget is not None:
            self._pivot = SegmentedWidget(self)
        else:
            self._pivot = None

        self._stacked = QStackedWidget(self)

        # -- Panel 0: Settings --
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self._build_settings_panel(settings_layout)
        self._stacked.addWidget(settings_panel)

        # -- Panel 1: Logs --
        logs_panel = QWidget()
        logs_layout = QVBoxLayout(logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)

        self._build_logs_panel(logs_layout)
        self._stacked.addWidget(logs_panel)

        # -- Panel 2: Diagnostics --
        diag_panel = QWidget()
        diag_layout = QVBoxLayout(diag_panel)
        diag_layout.setContentsMargins(0, 0, 0, 0)
        diag_layout.setSpacing(8)

        self._build_diag_panel(diag_layout)
        self._stacked.addWidget(diag_panel)

        # Wire up tabs
        if self._pivot is not None:
            self._pivot.addItem("settings", "Настройки", lambda: self._switch_tab(0))
            self._pivot.addItem("logs", "Логи", lambda: self._switch_tab(1))
            self._pivot.addItem("diag", "Диагностика", lambda: self._switch_tab(2))
            self._pivot.setCurrentItem("settings")
            self.add_widget(self._pivot)

        self.add_widget(self._stacked)
        self._switch_tab(0)

    def _switch_tab(self, index: int):
        self._stacked.setCurrentIndex(index)
        if self._pivot is not None:
            keys = ["settings", "logs", "diag"]
            if 0 <= index < len(keys):
                self._pivot.setCurrentItem(keys[index])

    def _build_settings_panel(self, layout: QVBoxLayout):
        # -- Status card --
        self._status_card = SettingsCard()

        status_header = QHBoxLayout()
        self._status_dot = _StatusDot()
        self._status_label = StrongBodyLabel("Остановлен")
        status_header.addWidget(self._status_dot)
        status_header.addWidget(self._status_label)
        status_header.addStretch()

        self._btn_toggle = ActionButton("Запустить")
        self._btn_toggle.setFixedWidth(140)
        self._btn_toggle.clicked.connect(self._on_toggle_proxy)
        status_header.addWidget(self._btn_toggle)
        self._status_card.add_layout(status_header)

        self._stats_label = CaptionLabel("")
        self._status_card.add_widget(self._stats_label)
        layout.addWidget(self._status_card)

        # -- Quick setup card --
        layout.addWidget(StrongBodyLabel("Быстрая настройка Telegram"))
        self._setup_card = SettingsCard()

        setup_desc = CaptionLabel(
            "Нажмите кнопку ниже - Telegram автоматически добавит прокси. "
            "Настройка требуется один раз.\nЕсли Telegram не открывается попробуйте скопировать ссылку и отправить в любой чат Telegram или кому-то в ЛС — после чего нажмите на отправленную ссылку и подтвердите добавление прокси в Telegram клиент.\nРекомендуем полностью ПЕРЕЗАПУСТИТЬ клиент для более корректного работа прокси после включения Zapret 2 GUI!"
        )
        setup_desc.setWordWrap(True)
        self._setup_card.add_widget(setup_desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_open_tg = ActionButton("Добавить прокси в Telegram")
        self._btn_open_tg.setToolTip("Откроет ссылку для автоматической настройки прокси")
        self._btn_open_tg.clicked.connect(self._on_open_in_telegram)
        btn_row.addWidget(self._btn_open_tg)

        self._btn_copy_link = ActionButton("Скопировать ссылку")
        self._btn_copy_link.clicked.connect(self._on_copy_link)
        btn_row.addWidget(self._btn_copy_link)

        btn_row.addStretch()
        self._setup_card.add_layout(btn_row)

        layout.addWidget(self._setup_card)

        # -- Settings card --
        layout.addWidget(StrongBodyLabel("Настройки"))
        self._settings_card = SettingsCard()

        # Host + Port setting
        host_port_row = QHBoxLayout()
        host_label = BodyLabel("Адрес:")
        host_port_row.addWidget(host_label)
        self._host_edit = QLineEdit("127.0.0.1")
        self._host_edit.setFixedWidth(150)
        self._host_edit.setPlaceholderText("127.0.0.1")
        self._host_edit.setToolTip(
            "IP-адрес для прослушивания. 127.0.0.1 — только локально, "
            "0.0.0.0 или IP вашей сети — доступ с других устройств (телефон и т.д.)"
        )
        host_port_row.addWidget(self._host_edit)

        host_port_row.addSpacing(16)

        port_label = BodyLabel("Порт:")
        host_port_row.addWidget(port_label)
        self._port_spin = SpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(1353)
        self._port_spin.setFixedWidth(100)
        host_port_row.addWidget(self._port_spin)
        host_port_row.addStretch()
        self._settings_card.add_layout(host_port_row)

        # Auto-start toggle
        from ui.pages.dpi_settings_page import Win11ToggleRow
        self._autostart_toggle = Win11ToggleRow(
            "mdi.play-circle-outline",
            "Автозапуск прокси",
            "Запускать прокси автоматически при старте программы",
        )
        self._autostart_toggle.toggle.setChecked(True)
        self._settings_card.add_widget(self._autostart_toggle)

        # Auto-open deep link toggle
        self._auto_deeplink_toggle = Win11ToggleRow(
            "mdi.telegram",
            "Авто-настройка Telegram",
            "При первом запуске прокси автоматически открыть ссылку настройки в Telegram",
        )
        self._auto_deeplink_toggle.toggle.setChecked(True)
        self._settings_card.add_widget(self._auto_deeplink_toggle)

        layout.addWidget(self._settings_card)

        # -- Upstream proxy card --
        layout.addWidget(StrongBodyLabel("Внешний прокси (upstream)"))
        self._upstream_card = SettingsCard()

        upstream_desc = CaptionLabel(
            "SOCKS5 прокси-сервер для DC заблокированных вашим провайдером.\n"
            "Используется как резервный канал когда WSS relay и прямое подключение не работают."
        )
        upstream_desc.setWordWrap(True)
        self._upstream_card.add_widget(upstream_desc)

        # Enable toggle (reuse Win11ToggleRow already imported above)
        self._upstream_toggle = Win11ToggleRow(
            "mdi.server-network",
            "Использовать внешний прокси",
            "Маршрутизировать заблокированные DC через внешний SOCKS5 прокси",
        )
        self._upstream_toggle.toggle.setChecked(False)
        self._upstream_card.add_widget(self._upstream_toggle)

        # Preset selector (loaded from private JSON at runtime)
        self._upstream_presets = _load_upstream_presets()
        has_presets = len(self._upstream_presets) > 1

        # ComboBox for preset selection (hidden if no presets file)
        self._upstream_preset_widget = QWidget()
        preset_layout = QHBoxLayout(self._upstream_preset_widget)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.addWidget(BodyLabel("Прокси:"))
        self._upstream_preset_combo = ComboBox()
        self._upstream_preset_combo.setFixedWidth(250)
        for preset in self._upstream_presets:
            self._upstream_preset_combo.addItem(preset["name"])
        # Default to first real preset (index 1) if presets exist
        if has_presets:
            self._upstream_preset_combo.setCurrentIndex(1)
        preset_layout.addStretch()
        self._upstream_preset_widget.setVisible(has_presets)
        self._upstream_card.add_widget(self._upstream_preset_widget)

        # Manual input container (always visible if no presets, otherwise only for "Ручной ввод")
        self._upstream_manual_widget = QWidget()
        manual_layout = QVBoxLayout(self._upstream_manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        # Host + Port row
        upstream_hp_row = QHBoxLayout()
        upstream_hp_row.addWidget(BodyLabel("Хост:"))
        self._upstream_host_edit = QLineEdit("")
        self._upstream_host_edit.setFixedWidth(200)
        self._upstream_host_edit.setPlaceholderText("192.168.1.100 или proxy.example.com")
        upstream_hp_row.addWidget(self._upstream_host_edit)
        upstream_hp_row.addSpacing(16)
        upstream_hp_row.addWidget(BodyLabel("Порт:"))
        self._upstream_port_spin = SpinBox()
        self._upstream_port_spin.setRange(1, 65535)
        self._upstream_port_spin.setValue(1080)
        self._upstream_port_spin.setFixedWidth(100)
        upstream_hp_row.addWidget(self._upstream_port_spin)
        upstream_hp_row.addStretch()
        manual_layout.addLayout(upstream_hp_row)

        # Username + Password row
        upstream_auth_row = QHBoxLayout()
        upstream_auth_row.addWidget(BodyLabel("Логин:"))
        self._upstream_user_edit = QLineEdit("")
        self._upstream_user_edit.setFixedWidth(150)
        self._upstream_user_edit.setPlaceholderText("username")
        upstream_auth_row.addWidget(self._upstream_user_edit)
        upstream_auth_row.addSpacing(16)
        upstream_auth_row.addWidget(BodyLabel("Пароль:"))
        self._upstream_pass_edit = QLineEdit("")
        self._upstream_pass_edit.setFixedWidth(150)
        self._upstream_pass_edit.setPlaceholderText("password")
        self._upstream_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        upstream_auth_row.addWidget(self._upstream_pass_edit)
        upstream_auth_row.addStretch()
        manual_layout.addLayout(upstream_auth_row)

        # If no presets file → always show manual fields; with presets → hide (preset selected)
        self._upstream_manual_widget.setVisible(not has_presets)
        self._upstream_card.add_widget(self._upstream_manual_widget)

        # Mode toggle (fallback vs always) — default ON
        self._upstream_mode_toggle = Win11ToggleRow(
            "mdi.swap-horizontal",
            "Весь трафик через прокси",
            "Если выключено — только заблокированные DC. Если включено — весь трафик Telegram.",
        )
        self._upstream_mode_toggle.toggle.setChecked(True)
        self._upstream_card.add_widget(self._upstream_mode_toggle)

        layout.addWidget(self._upstream_card)

        # -- MTProxy card (shown only if link exists in private config) --
        self._mtproxy_link = _load_mtproxy_link()
        self._mtproxy_card = SettingsCard()
        mtproxy_desc = CaptionLabel(
            "Также доступен MTProxy (белые списки). Нажмите для добавления в Telegram."
        )
        mtproxy_desc.setWordWrap(True)
        self._mtproxy_card.add_widget(mtproxy_desc)

        self._btn_mtproxy = ActionButton("Добавить MTProxy в Telegram")
        self._btn_mtproxy.setToolTip("Откроет ссылку для добавления MTProxy")
        self._btn_mtproxy.clicked.connect(self._on_open_mtproxy)
        self._mtproxy_card.add_widget(self._btn_mtproxy)
        self._mtproxy_card.setVisible(bool(self._mtproxy_link))

        layout.addWidget(self._mtproxy_card)

        # -- Instructions card --
        layout.addWidget(StrongBodyLabel("Ручная настройка"))
        self._instructions_card = SettingsCard()

        instr1 = CaptionLabel("Если автоматическая настройка не сработала:")
        instr1.setWordWrap(True)
        self._instructions_card.add_widget(instr1)

        instr2 = CaptionLabel("  Telegram -> Настройки -> Продвинутые -> Тип соединения -> Прокси")
        instr2.setWordWrap(True)
        self._instructions_card.add_widget(instr2)

        self._manual_host_port_label = CaptionLabel("  Тип: SOCKS5  |  Хост: 127.0.0.1  |  Порт: 1353")
        self._manual_host_port_label.setWordWrap(True)
        self._instructions_card.add_widget(self._manual_host_port_label)

        layout.addWidget(self._instructions_card)
        layout.addStretch()

    def _build_logs_panel(self, layout: QVBoxLayout):
        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._btn_copy_logs = ActionButton("Копировать все")
        self._btn_copy_logs.clicked.connect(self._on_copy_all_logs)
        toolbar.addWidget(self._btn_copy_logs)

        self._btn_open_log_file = ActionButton("Открыть файл лога")
        self._btn_open_log_file.clicked.connect(self._on_open_log_file)
        toolbar.addWidget(self._btn_open_log_file)

        self._btn_clear_logs = ActionButton("Очистить")
        self._btn_clear_logs.clicked.connect(self._on_clear_logs)
        toolbar.addWidget(self._btn_clear_logs)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Log text widget — no height limit, no trimming
        self._log_edit = ScrollBlockingPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText("Лог подключений появится здесь...")
        layout.addWidget(self._log_edit)

    def _build_diag_panel(self, layout: QVBoxLayout):
        desc = CaptionLabel(
            "Проверка соединений к Telegram DC, WSS relay эндпоинтов (kws1-kws5), "
            "SOCKS5 прокси и определение типа блокировки."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._btn_run_diag = ActionButton("Запустить диагностику")
        self._btn_run_diag.clicked.connect(self._on_run_diagnostics)
        toolbar.addWidget(self._btn_run_diag)

        self._btn_copy_diag = ActionButton("Копировать результат")
        self._btn_copy_diag.clicked.connect(self._on_copy_diag)
        toolbar.addWidget(self._btn_copy_diag)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._diag_edit = ScrollBlockingPlainTextEdit()
        self._diag_edit.setReadOnly(True)
        self._diag_edit.setPlaceholderText("Нажмите 'Запустить диагностику'...")
        layout.addWidget(self._diag_edit)

    def _on_run_diagnostics(self):
        """Run network diagnostics in a background thread."""
        self._btn_run_diag.setEnabled(False)
        self._btn_run_diag.setText("Тестирование...")
        self._diag_edit.clear()
        self._diag_edit.appendPlainText("Запуск диагностики Telegram DC...\n")

        self._diag_result = None  # shared with thread
        self._diag_thread_done = False
        # Capture proxy port from UI before spawning thread
        self._diag_proxy_port = self._port_spin.value()

        import threading
        t = threading.Thread(target=self._run_diag_tests, daemon=True)
        t.start()

        # Poll for result every 200ms
        self._diag_poll_timer = QTimer(self)
        self._diag_poll_timer.timeout.connect(self._poll_diag)
        self._diag_poll_timer.start(200)

    def _poll_diag(self):
        """Check if diag thread has new results."""
        if self._diag_result is not None:
            self._diag_edit.setPlainText(self._diag_result)
            sb = self._diag_edit.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        if self._diag_thread_done:
            self._diag_poll_timer.stop()
            self._diag_finished()

    # ── Direct DC test targets (including media IPs) ──
    _DC_TARGETS = [
        ("149.154.167.220", "WSS relay",    "—"),
        ("149.154.167.50",  "DC2",          "kws2"),
        ("149.154.167.41",  "DC2",          "kws2"),
        ("149.154.167.91",  "DC4",          "kws4"),
        ("149.154.175.53",  "DC1",          "—"),
        ("149.154.175.55",  "DC1",          "—"),
        ("149.154.175.100", "DC3 (->DC1)",  "—"),
        ("91.108.56.134",   "DC5",          "—"),
        ("91.108.56.149",   "DC5",          "—"),
        ("91.105.192.100",  "DC203 CDN",    "—"),
        # Media DCs
        ("149.154.167.151", "DC2 media",    "—"),
        ("149.154.167.222", "DC2 media",    "—"),
        ("149.154.175.52",  "DC1 media",    "—"),
        ("91.108.56.102",   "DC5 media",    "—"),
    ]

    # ── WSS relay probe targets: kws (Web K) + zws (Web Z) ──
    _WSS_PROBE_TARGETS = [
        ("149.154.167.220", "kws1.web.telegram.org", 1),
        ("149.154.167.220", "kws2.web.telegram.org", 2),
        ("149.154.167.220", "kws3.web.telegram.org", 3),
        ("149.154.167.220", "kws4.web.telegram.org", 4),
        ("149.154.167.220", "kws5.web.telegram.org", 5),
        ("149.154.167.220", "zws2.web.telegram.org", 2),
        ("149.154.167.220", "zws4.web.telegram.org", 4),
    ]

    def _run_diag_tests(self):
        """Background thread: test all Telegram DCs, WSS relay, and proxy in parallel."""
        import concurrent.futures
        import time

        t0 = time.time()
        results: list[str] = []

        # Read proxy port from UI (set before thread start via _on_run_diagnostics)
        proxy_port = getattr(self, "_diag_proxy_port", 1353)

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
            # ── Phase 1: Direct DC tests ──
            dc_futures = {
                ex.submit(self._test_single_ip, ip, dc, wss): (ip, dc)
                for ip, dc, wss in self._DC_TARGETS
            }

            # ── Phase 2: WSS relay probe (parallel with Phase 1) ──
            wss_futures = [
                ex.submit(self._test_wss_relay, ip, domain, dc)
                for ip, domain, dc in self._WSS_PROBE_TARGETS
            ]

            # ── Phase 0: WSS relay reachability (parallel with everything) ──
            from telegram_proxy.wss_proxy import check_relay_reachable
            relay_f = ex.submit(check_relay_reachable, timeout=5.0)

            # ── Phase 3: SNI + HTTP + proxy + winws2 + upstream (parallel) ──
            sni_f = ex.submit(self._test_sni_vs_ip)
            http_f = ex.submit(self._test_http_port80)
            proxy_f = ex.submit(self._test_proxy_liveness, "127.0.0.1", proxy_port)
            winws2_f = ex.submit(self._check_winws2_running)

            # Upstream proxy test (if configured)
            upstream_f = None
            try:
                from config.reg import (get_tg_proxy_upstream_enabled,
                                         get_tg_proxy_upstream_host,
                                         get_tg_proxy_upstream_port)
                if get_tg_proxy_upstream_enabled():
                    up_host = get_tg_proxy_upstream_host()
                    up_port = get_tg_proxy_upstream_port()
                    if up_host and up_port > 0:
                        upstream_f = ex.submit(self._test_upstream_proxy, up_host, up_port)
            except Exception:
                pass

            # ── Collect relay result first ──
            relay_result = relay_f.result()
            results.append("=" * 76)
            results.append("  ДОСТУПНОСТЬ WSS RELAY")
            results.append("=" * 76)
            results.append("  149.154.167.220:443 (web.telegram.org)")
            if relay_result["reachable"]:
                results.append(f"  TCP+TLS: OK ({relay_result['ms']:.0f}ms)")
            else:
                results.append(f"  TCP+TLS: TIMEOUT ({relay_result['ms']:.0f}ms) <- ЗАБЛОКИРОВАН")
                results.append("  ! WSS relay недоступен — прокси не сможет проксировать через WSS.")
                # Check zapret status
                try:
                    zapret_status = winws2_f.result(timeout=0.1)
                except Exception:
                    zapret_status = None
                if zapret_status is not None:
                    results.append(f"  Zapret запущен: {'ДА' if zapret_status else 'НЕТ'}")
                if relay_result["error"]:
                    results.append(f"  Ошибка: {relay_result['error']}")
            self._diag_result = "\n".join(results)

            results.append("")

            # Collect DC results with live update
            results.append("=" * 76)
            results.append("  ПРЯМЫЕ ПОДКЛЮЧЕНИЯ К TELEGRAM DC")
            results.append("=" * 76)
            results.append(f"{'IP':<20} {'DC':<12} {'TCP':>8}  {'TLS':>8}  {'Статус'}")
            results.append("-" * 76)

            dc_lines: list[str] = []
            for f in concurrent.futures.as_completed(dc_futures):
                line = f.result()
                dc_lines.append(line)
                self._diag_result = "\n".join(results + dc_lines)

            results.extend(dc_lines)

            # SNI + HTTP
            results.append("")
            results.append("  Определение типа блокировки:")
            results.append(f"  {sni_f.result()}")
            results.append(f"  {http_f.result()}")
            self._diag_result = "\n".join(results)

            # Collect WSS results
            wss_results = [f.result() for f in wss_futures]

            results.append("")
            results.append("=" * 76)
            results.append("  WSS RELAY — ДОСТУПНОСТЬ ЭНДПОИНТОВ (149.154.167.220)")
            results.append("=" * 76)
            results.append(f"{'DC':<6} {'Endpoint':<32} {'TCP':>6}  {'TLS':>6}  {'WS':>6}  {'Результат'}")
            results.append("-" * 76)

            for r in sorted(wss_results, key=lambda x: x["dc"]):
                tcp = f"{r['tcp_ms']:.0f}ms" if r["tcp_ms"] is not None else "—"
                tls = f"{r['tls_ms']:.0f}ms" if r["tls_ms"] is not None else "—"
                ws = f"{r['ws_ms']:.0f}ms" if r["ws_ms"] is not None else "—"
                if r["status"] == "OK":
                    status = "OK (101)"
                elif r["status"] == "WS_REDIRECT":
                    status = f"{r['http_code']} (редирект)"
                elif r["status"] == "TLS_FAIL":
                    status = "TLS FAIL"
                elif r["status"] == "TCP_FAIL":
                    status = "TCP FAIL"
                elif r["status"] == "TIMEOUT":
                    status = "TIMEOUT"
                else:
                    status = r.get("error", r["status"])[:30]
                results.append(
                    f"DC{r['dc']:<4} {r['domain']:<32} {tcp:>6}  {tls:>6}  {ws:>6}  {status}"
                )
            self._diag_result = "\n".join(results)

            # Collect proxy + winws2
            proxy_result = proxy_f.result()
            winws2_running = winws2_f.result()

            results.append("")
            results.append("=" * 76)
            results.append(f"  ПРОКСИ (127.0.0.1:{proxy_port})")
            results.append("=" * 76)
            if proxy_result["status"] == "OK":
                results.append(
                    f"  SOCKS5: OK (tcp {proxy_result['tcp_ms']:.0f}ms, "
                    f"socks {proxy_result['socks_ms']:.0f}ms)"
                )
            elif proxy_result["status"] == "NOT_RUNNING":
                results.append("  SOCKS5: НЕ ЗАПУЩЕН (порт закрыт)")
            else:
                results.append(f"  SOCKS5: {proxy_result['status']} — {proxy_result.get('error', '')}")

            # Upstream proxy results
            if upstream_f is not None:
                upstream_result = upstream_f.result()
                up_host = upstream_result.get("host", "?")
                up_port = upstream_result.get("port", 0)
                results.append("")
                results.append("=" * 76)
                results.append(f"  UPSTREAM PROXY ({up_host}:{up_port})")
                results.append("=" * 76)
                if upstream_result["status"] == "OK":
                    results.append(
                        f"  SOCKS5: OK (tcp {upstream_result['tcp_ms']:.0f}ms, "
                        f"handshake {upstream_result['handshake_ms']:.0f}ms)"
                    )
                elif upstream_result["status"] == "NOT_RUNNING":
                    results.append("  SOCKS5: НЕ ЗАПУЩЕН (порт закрыт)")
                elif upstream_result["status"] == "TIMEOUT":
                    results.append("  SOCKS5: TIMEOUT (не удалось подключиться)")
                else:
                    results.append(
                        f"  SOCKS5: {upstream_result['status']} — "
                        f"{upstream_result.get('error', '')}"
                    )

        elapsed = time.time() - t0

        # ── Summary ──
        results.append("")
        results.append("=" * 76)
        results.append("  ИТОГ")
        results.append("=" * 76)
        summary = self._build_summary(dc_lines, wss_results, proxy_result, winws2_running)
        results.append(summary)
        results.append(f"\nВремя тестирования: {elapsed:.1f}s")

        self._diag_result = "\n".join(results)
        self._diag_thread_done = True

    def _test_wss_relay(self, ip: str, domain: str, dc: int) -> dict:
        """Probe WSS endpoint: TCP -> TLS -> HTTP Upgrade -> check 101/302."""
        import socket, ssl, base64, os, time

        result = {
            "ip": ip, "domain": domain, "dc": dc,
            "tcp_ms": None, "tls_ms": None, "ws_ms": None,
            "status": "UNKNOWN", "http_code": None,
            "redirect_to": None, "error": None,
        }

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4)
        t0 = time.time()
        try:
            s.connect((ip, 443))
            result["tcp_ms"] = (time.time() - t0) * 1000
        except Exception as e:
            s.close()
            result["status"] = "TCP_FAIL"
            result["error"] = str(e)
            return result

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        t1 = time.time()
        try:
            ss = ctx.wrap_socket(s, server_hostname=domain)
            result["tls_ms"] = (time.time() - t1) * 1000
        except Exception as e:
            s.close()
            result["status"] = "TLS_FAIL"
            result["error"] = str(e)
            return result

        ws_key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET /apiws HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: binary\r\n"
            f"Origin: https://web.telegram.org\r\n"
            f"\r\n"
        )
        ss.settimeout(5)
        t2 = time.time()
        try:
            ss.sendall(request.encode())
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = ss.recv(512)
                if not chunk:
                    break
                response += chunk
                if len(response) > 4096:
                    break
            result["ws_ms"] = (time.time() - t2) * 1000
            ss.close()

            lines = response.split(b"\r\n")
            status_line = lines[0].decode("utf-8", errors="replace")
            parts = status_line.split(" ", 2)
            http_code = int(parts[1]) if len(parts) >= 2 else 0
            result["http_code"] = http_code

            # Parse Location header for redirects
            for line in lines[1:]:
                decoded = line.decode("utf-8", errors="replace")
                if decoded.lower().startswith("location:"):
                    result["redirect_to"] = decoded.split(":", 1)[1].strip()
                    break

            if http_code == 101:
                result["status"] = "OK"
            elif http_code in (301, 302, 303, 307, 308):
                result["status"] = "WS_REDIRECT"
                result["error"] = status_line
            else:
                result["status"] = "WS_FAIL"
                result["error"] = status_line
            return result

        except socket.timeout:
            ss.close()
            result["status"] = "TIMEOUT"
            result["error"] = "WS upgrade timeout"
            return result
        except Exception as e:
            try:
                ss.close()
            except Exception:
                pass
            result["status"] = "WS_FAIL"
            result["error"] = str(e)
            return result

    @staticmethod
    def _test_proxy_liveness(host: str, port: int) -> dict:
        """Verify SOCKS5 proxy accepts connections and can CONNECT to relay."""
        import socket, struct, time

        result = {
            "status": "UNKNOWN", "tcp_ms": None,
            "socks_ms": None, "error": None,
        }

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        t0 = time.time()
        try:
            s.connect((host, port))
            result["tcp_ms"] = (time.time() - t0) * 1000
        except ConnectionRefusedError:
            s.close()
            result["status"] = "NOT_RUNNING"
            result["error"] = "порт закрыт (прокси не запущен)"
            return result
        except socket.timeout:
            s.close()
            result["status"] = "TIMEOUT"
            result["error"] = "TCP timeout"
            return result
        except Exception as e:
            s.close()
            result["status"] = "REFUSED"
            result["error"] = str(e)
            return result

        t1 = time.time()
        try:
            # SOCKS5 greeting: version=5, nmethods=1, no-auth
            s.sendall(b"\x05\x01\x00")
            reply = s.recv(2)
            if len(reply) < 2 or reply[0] != 5 or reply[1] != 0:
                s.close()
                result["status"] = "SOCKS_ERROR"
                result["error"] = f"unexpected greeting: {reply.hex()}"
                return result

            # SOCKS5 CONNECT to relay IP 149.154.167.220:443
            ip_bytes = bytes([149, 154, 167, 220])
            port_bytes = struct.pack(">H", 443)
            s.sendall(b"\x05\x01\x00\x01" + ip_bytes + port_bytes)

            reply = s.recv(10)
            result["socks_ms"] = (time.time() - t1) * 1000
            s.close()

            if len(reply) >= 2 and reply[0] == 5 and reply[1] == 0:
                result["status"] = "OK"
            else:
                code = reply[1] if len(reply) >= 2 else -1
                errors = {
                    1: "general failure", 2: "not allowed",
                    3: "network unreachable", 4: "host unreachable",
                    5: "connection refused (relay unreachable)",
                }
                result["status"] = "SOCKS_ERROR"
                result["error"] = errors.get(code, f"code={code}")
            return result

        except socket.timeout:
            s.close()
            result["status"] = "TIMEOUT"
            result["error"] = "SOCKS5 timeout"
            return result
        except Exception as e:
            s.close()
            result["status"] = "SOCKS_ERROR"
            result["error"] = str(e)
            return result

    @staticmethod
    def _test_upstream_proxy(host: str, port: int) -> dict:
        """Test upstream SOCKS5 proxy connectivity."""
        import socket, time

        result = {
            "host": host, "port": port,
            "status": "NOT_RUNNING", "tcp_ms": 0, "handshake_ms": 0,
        }
        try:
            t0 = time.monotonic()
            sock = socket.create_connection((host, port), timeout=5.0)
            result["tcp_ms"] = (time.monotonic() - t0) * 1000

            # SOCKS5 greeting: VER=5, NMETHODS=1, NO_AUTH
            t1 = time.monotonic()
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(2)
            if len(reply) == 2 and reply[0] == 5 and reply[1] == 0:
                result["handshake_ms"] = (time.monotonic() - t1) * 1000
                result["status"] = "OK"
            else:
                result["status"] = "SOCKS_ERROR"
                result["error"] = f"Bad reply: {reply.hex()}"
            sock.close()
        except socket.timeout:
            result["status"] = "TIMEOUT"
            result["error"] = "Connection timeout"
        except ConnectionRefusedError:
            result["status"] = "NOT_RUNNING"
            result["error"] = "Connection refused"
        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = str(e)
        return result

    def _test_single_ip(self, ip: str, dc: str, wss: str) -> str:
        import socket, ssl, time

        # TCP connect
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        t0 = time.time()
        try:
            s.connect((ip, 443))
            tcp_ms = (time.time() - t0) * 1000
        except Exception:
            s.close()
            return f"{ip:<20} {dc:<12} {'FAIL':>8}  {'—':>8}  TCP не подключается"

        # TLS handshake
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        t1 = time.time()
        try:
            ss = ctx.wrap_socket(s, server_hostname="telegram.org")
            tls_ms = (time.time() - t1) * 1000
            ss.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {tls_ms:>6.0f}ms  OK"
        except ssl.SSLError as e:
            tls_ms = (time.time() - t1) * 1000
            s.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {tls_ms:>6.0f}ms  BLOCKED ({e.reason})"
        except socket.timeout:
            s.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {'5000':>6}ms  TIMEOUT"
        except Exception as e:
            s.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {'—':>8}  {type(e).__name__}"

    def _test_sni_vs_ip(self) -> str:
        """Test if blocking is SNI-based or IP-based."""
        import socket, ssl, time

        ip = "149.154.167.50"  # DC2
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((ip, 443))
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            t0 = time.time()
            ss = ctx.wrap_socket(s, server_hostname="example.com")
            ms = (time.time() - t0) * 1000
            ss.close()
            return f"TLS с чужим SNI (example.com → {ip}): OK ({ms:.0f}ms) → блокировка по SNI"
        except ssl.SSLError:
            s.close()
            return f"TLS с чужим SNI (example.com → {ip}): BLOCKED → блокировка по IP (не SNI)"
        except socket.timeout:
            s.close()
            return f"TLS с чужим SNI (example.com → {ip}): TIMEOUT → блокировка по IP (не SNI)"
        except Exception as e:
            s.close()
            return f"TLS с чужим SNI: {type(e).__name__}"

    def _test_http_port80(self) -> str:
        """Test HTTP on port 80 (no TLS)."""
        import socket, time

        ip = "149.154.167.50"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            t0 = time.time()
            s.connect((ip, 80))
            s.send(b"GET / HTTP/1.0\r\nHost: test\r\n\r\n")
            s.settimeout(3)
            data = s.recv(1024)
            ms = (time.time() - t0) * 1000
            s.close()
            return f"HTTP {ip}:80 → {len(data)} байт ({ms:.0f}ms) — НЕ блокируется"
        except socket.timeout:
            s.close()
            return f"HTTP {ip}:80 → TIMEOUT — блокируется"
        except Exception as e:
            s.close()
            return f"HTTP {ip}:80 → {type(e).__name__}"

    def _build_summary(
        self,
        dc_lines: list[str],
        wss_results: list[dict],
        proxy_result: dict,
        winws2_running: bool,
    ) -> str:
        """Build honest summary from all test phases."""

        # ── Parse direct DC test results ──
        dc_status: dict[str, str] = {}
        # Check longest names first to avoid "DC2" matching "DC203 CDN" or "DC2 media"
        dc_names_ordered = ("DC203 CDN", "DC5 media", "DC5", "DC4", "DC3 (->DC1)", "DC2 media", "DC2", "DC1 media", "DC1")
        for line in dc_lines:
            for dc_name in dc_names_ordered:
                if dc_name in line:
                    if line.strip().endswith("OK"):
                        dc_status.setdefault(dc_name, "OK")
                    elif "BLOCKED" in line or "TIMEOUT" in line or "FAIL" in line:
                        dc_status[dc_name] = "BLOCKED"
                    break  # one DC per line, stop after first match

        blocked = sum(1 for v in dc_status.values() if v == "BLOCKED")
        ok_count = sum(1 for v in dc_status.values() if v == "OK")

        # ── WSS relay results ──
        wss_ok_dcs = {r["dc"] for r in wss_results if r["status"] == "OK"}
        wss_redirect_dcs = {r["dc"] for r in wss_results if r["status"] == "WS_REDIRECT"}
        relay_ok = len(wss_ok_dcs) > 0

        # ── Proxy status ──
        proxy_running = proxy_result["status"] == "OK"
        proxy_not_running = proxy_result["status"] == "NOT_RUNNING"

        summary: list[str] = []

        # Section 1: Blocking type
        summary.append("── Тип блокировки ──")
        summary.append(f"  Доступно: {ok_count}  |  Заблокировано: {blocked}")
        if blocked == 0 and ok_count > 0:
            summary.append("  Блокировки не обнаружено")
        elif blocked > 0:
            summary.append("  Тип: блокировка TLS к IP Telegram (DPI)")
            summary.append("  (подробности в секции 'Определение типа блокировки' выше)")

        # Section 2: Per-DC status with WSS info
        summary.append("")
        summary.append("── Статус дата-центров ──")
        for dc_name in ("DC1", "DC1 media", "DC2", "DC2 media", "DC3 (->DC1)", "DC4", "DC5", "DC5 media", "DC203 CDN"):
            direct = dc_status.get(dc_name, "—")
            # Extract DC number for WSS matching
            dc_num = None
            # Match DC1, DC2, etc. but also "DC2 media", "DC3 (->DC1)"
            dc_digits = ""
            for ch in dc_name[2:]:
                if ch.isdigit():
                    dc_digits += ch
                else:
                    break
            if dc_digits and len(dc_digits) <= 2:  # DC1-DC5, not DC203
                dc_num = int(dc_digits)

            if dc_num and dc_num in wss_ok_dcs:
                wss_info = "WSS relay"
            elif dc_num and dc_num in wss_redirect_dcs:
                wss_info = "нет relay"
            elif dc_name == "DC203 CDN":
                wss_info = "TCP (CDN)"
            else:
                wss_info = "—"

            if direct == "OK":
                icon = "+"
            elif direct == "BLOCKED" and dc_num in wss_ok_dcs:
                icon = "~"  # blocked but WSS bypasses
            else:
                icon = "x"

            summary.append(f"  [{icon}] {dc_name:<10} напрямую: {direct:<10} прокси: {wss_info}")

        # Section 3: WSS relay
        summary.append("")
        summary.append("── WSS relay (149.154.167.220) ──")
        if relay_ok:
            ok_list = ", ".join(f"kws{dc}" for dc in sorted(wss_ok_dcs))
            summary.append(f"  Доступен: {ok_list}")
        else:
            summary.append("  Недоступен")
        if wss_redirect_dcs:
            redir_list = ", ".join(f"kws{dc}" for dc in sorted(wss_redirect_dcs))
            summary.append(f"  Редирект (нет relay): {redir_list}")

        # Section 4: Proxy + winws2
        summary.append("")
        summary.append("── Сервисы ──")
        if proxy_running:
            summary.append("  Прокси: запущен")
        elif proxy_not_running:
            summary.append("  Прокси: не запущен")
        else:
            summary.append(f"  Прокси: ошибка ({proxy_result.get('error', '?')})")
        summary.append(f"  winws2: {'запущен' if winws2_running else 'не запущен'}")

        # Section 5: Honest recommendations
        summary.append("")
        summary.append("── Рекомендации ──")

        if blocked == 0 and ok_count > 0:
            summary.append("  Telegram доступен напрямую, прокси не требуется.")
            return "\n".join(summary)

        # WSS-capable DCs
        bypassed_dcs = {
            dc_name for dc_name, status in dc_status.items()
            if status == "BLOCKED"
            and dc_name.startswith("DC") and dc_name[2:].isdigit()
            and int(dc_name[2:]) in wss_ok_dcs
        }
        blocked_no_wss = {
            dc_name for dc_name, status in dc_status.items()
            if status == "BLOCKED"
            and dc_name not in bypassed_dcs
        }

        if bypassed_dcs and relay_ok:
            if proxy_running:
                summary.append(
                    f"  [+] {', '.join(sorted(bypassed_dcs))}: "
                    f"заблокированы напрямую, обходятся через WSS прокси"
                )
            else:
                summary.append(
                    f"  [~] {', '.join(sorted(bypassed_dcs))}: "
                    f"WSS relay доступен, но прокси не запущен"
                )

        if blocked_no_wss:
            no_wss_names = ", ".join(sorted(blocked_no_wss))
            summary.append(
                f"  [!] {no_wss_names}: заблокированы, WSS relay нет — "
                f"часть контента (эмодзи, стикеры) может не загружаться"
            )
            if winws2_running:
                summary.append(
                    f"  [~] winws2 запущен — {no_wss_names} могут работать через zapret"
                )
            else:
                summary.append(
                    f"  [!] Для {no_wss_names} запустите winws2/zapret на главной странице"
                )

        if proxy_not_running:
            summary.append("  [!] Прокси не запущен — запустите его на этой странице")

        if not relay_ok and blocked > 0:
            summary.append("  [x] WSS relay недоступен — прокси не будет работать")
            if not winws2_running:
                summary.append("  [!] Запустите winws2/zapret или используйте VPN")

        return "\n".join(summary)

    @staticmethod
    def _check_winws2_running() -> bool:
        """Check if winws2.exe or winws.exe process is running."""
        try:
            import subprocess
            for exe in ("winws2.exe", "winws.exe"):
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                if exe in result.stdout.lower():
                    return True
            return False
        except Exception:
            return False

    def _update_diag(self, text: str):
        self._diag_edit.setPlainText(text)
        sb = self._diag_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _diag_finished(self):
        self._btn_run_diag.setEnabled(True)
        self._btn_run_diag.setText("Запустить диагностику")

    def _on_copy_diag(self):
        text = self._diag_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard and text:
            clipboard.setText(text)
            if _HAS_FLUENT and InfoBar is not None:
                try:
                    InfoBar.success(
                        title="Скопировано",
                        content="Результат диагностики",
                        parent=self,
                        duration=2000,
                        position=InfoBarPosition.TOP,
                    )
                except Exception:
                    pass

    def _connect_signals(self):
        mgr = _get_proxy_manager()
        mgr.status_changed.connect(self._on_status_changed)
        mgr.stats_updated.connect(self._on_stats_updated)

        self._autostart_toggle.toggled.connect(self._on_autostart_changed)
        self._port_spin.valueChanged.connect(self._on_port_changed)
        self._host_edit.editingFinished.connect(self._on_host_changed)

        # Upstream proxy signals
        self._upstream_toggle.toggled.connect(self._on_upstream_changed)
        self._upstream_preset_combo.currentIndexChanged.connect(self._on_upstream_preset_changed)
        self._upstream_host_edit.editingFinished.connect(self._on_upstream_host_changed)
        self._upstream_port_spin.valueChanged.connect(self._on_upstream_port_changed)
        self._upstream_user_edit.editingFinished.connect(self._on_upstream_user_changed)
        self._upstream_pass_edit.editingFinished.connect(self._on_upstream_pass_changed)
        self._upstream_mode_toggle.toggled.connect(self._on_upstream_mode_changed)

    def _load_settings(self):
        """Load settings from registry."""
        try:
            from config.reg import get_tg_proxy_port, get_tg_proxy_autostart, get_tg_proxy_host
            port = get_tg_proxy_port()
            if port is None or port < 1024 or port > 65535:
                port = 1353
            self._port_spin.blockSignals(True)
            self._port_spin.setValue(port)
            self._port_spin.blockSignals(False)

            host = get_tg_proxy_host()
            self._host_edit.blockSignals(True)
            self._host_edit.setText(host)
            self._host_edit.blockSignals(False)

            self._autostart_toggle.toggle.setChecked(get_tg_proxy_autostart())
            self._update_manual_instructions()

            # Load upstream proxy settings
            from config.reg import (get_tg_proxy_upstream_enabled, get_tg_proxy_upstream_host,
                                     get_tg_proxy_upstream_port, get_tg_proxy_upstream_mode,
                                     get_tg_proxy_upstream_user, get_tg_proxy_upstream_pass)
            self._upstream_toggle.toggle.setChecked(get_tg_proxy_upstream_enabled())

            # Determine which preset matches saved host/port (or fall back to manual)
            saved_host = get_tg_proxy_upstream_host()
            saved_port = get_tg_proxy_upstream_port()
            preset_idx = 0  # default: manual
            for i, preset in enumerate(self._upstream_presets):
                if i == 0:
                    continue  # skip "Ручной ввод"
                if preset["host"] == saved_host and preset["port"] == saved_port:
                    preset_idx = i
                    break

            self._upstream_preset_combo.blockSignals(True)
            self._upstream_preset_combo.setCurrentIndex(preset_idx)
            self._upstream_preset_combo.blockSignals(False)

            # Fill manual fields
            self._upstream_host_edit.setText(saved_host)
            upstream_port = saved_port
            if upstream_port > 0:
                self._upstream_port_spin.blockSignals(True)
                self._upstream_port_spin.setValue(upstream_port)
                self._upstream_port_spin.blockSignals(False)
            self._upstream_user_edit.setText(get_tg_proxy_upstream_user())
            self._upstream_pass_edit.setText(get_tg_proxy_upstream_pass())

            # Show/hide manual fields (always visible if no presets file)
            has_presets = len(self._upstream_presets) > 1
            self._upstream_manual_widget.setVisible(not has_presets or preset_idx == 0)

            self._upstream_mode_toggle.toggle.setChecked(
                get_tg_proxy_upstream_mode() == "always"
            )
        except Exception as e:
            log(f"TelegramProxyPage: load settings error: {e}", "WARNING")
            self._port_spin.blockSignals(True)
            self._port_spin.setValue(1353)
            self._port_spin.blockSignals(False)
            self._host_edit.blockSignals(True)
            self._host_edit.setText("127.0.0.1")
            self._host_edit.blockSignals(False)

    def _auto_start_check(self):
        """Auto-start proxy if autostart is enabled."""
        try:
            from config.reg import get_tg_proxy_autostart
            if get_tg_proxy_autostart():
                self._start_proxy()
                self._try_auto_deeplink()
        except Exception:
            pass

    def _try_auto_deeplink(self):
        """Open tg:// deep link automatically on first start."""
        try:
            from config.reg import reg
            from config import REGISTRY_PATH
            done = reg(REGISTRY_PATH, "TgProxyDeeplinkDone")
            if done:
                return
            reg(REGISTRY_PATH, "TgProxyDeeplinkDone", 1)
            QTimer.singleShot(2000, self._on_open_in_telegram)
            self._append_log_line("Auto-opening Telegram proxy setup link...")
        except Exception:
            pass

    # -- Log display (throttled via QTimer, no trimming) --

    def _flush_log_buffer(self):
        """Called every 500ms by QTimer. Drains new lines from ProxyLogger."""
        mgr = _get_proxy_manager()
        new_lines = mgr.proxy_logger.drain()
        if not new_lines:
            return

        self._log_edit.setUpdatesEnabled(False)
        try:
            for line in new_lines:
                self._log_edit.appendPlainText(line)
        finally:
            self._log_edit.setUpdatesEnabled(True)

        # Auto-scroll to bottom
        sb = self._log_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _append_log_line(self, msg: str):
        """Append a single line to the log."""
        mgr = _get_proxy_manager()
        mgr.proxy_logger.log(msg)

    # -- Log tab buttons --

    def _on_copy_all_logs(self):
        text = self._log_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard and text:
            clipboard.setText(text)
            if _HAS_FLUENT and InfoBar is not None:
                try:
                    InfoBar.success(
                        title="Скопировано",
                        content=f"{len(text.splitlines())} строк",
                        parent=self,
                        duration=2000,
                        position=InfoBarPosition.TOP,
                    )
                except Exception:
                    pass

    def _on_open_log_file(self):
        import os, subprocess
        mgr = _get_proxy_manager()
        path = mgr.proxy_logger.log_file_path
        if os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            self._append_log_line(f"Log file not found: {path}")

    def _on_clear_logs(self):
        self._log_edit.clear()

    # -- Handlers --

    def _on_toggle_proxy(self):
        mgr = _get_proxy_manager()
        if mgr.is_running:
            self._stop_proxy()
        else:
            self._start_proxy()

    def _start_proxy(self):
        mgr = _get_proxy_manager()
        port = self._port_spin.value()
        host = self._host_edit.text().strip() or "127.0.0.1"

        # Build upstream config from registry
        upstream_config = None
        try:
            from telegram_proxy.wss_proxy import UpstreamProxyConfig
            from config.reg import (get_tg_proxy_upstream_enabled, get_tg_proxy_upstream_host,
                                     get_tg_proxy_upstream_port, get_tg_proxy_upstream_mode,
                                     get_tg_proxy_upstream_user, get_tg_proxy_upstream_pass)
            if get_tg_proxy_upstream_enabled():
                up_host = get_tg_proxy_upstream_host()
                up_port = get_tg_proxy_upstream_port()
                if up_host and up_port > 0:
                    upstream_config = UpstreamProxyConfig(
                        enabled=True, host=up_host, port=up_port,
                        mode=get_tg_proxy_upstream_mode(),
                        username=get_tg_proxy_upstream_user(),
                        password=get_tg_proxy_upstream_pass(),
                    )
        except Exception as e:
            log(f"Failed to build upstream config: {e}", "WARNING")

        ok = mgr.start_proxy(port=port, mode="socks5", host=host,
                              upstream_config=upstream_config)
        if ok:
            try:
                from config.reg import set_tg_proxy_enabled
                set_tg_proxy_enabled(True)
            except Exception:
                pass
            self._check_relay_after_start()

    def _check_relay_after_start(self):
        """Check relay reachability after proxy starts. Runs check in background.

        Logic:
        1. TLS check (port 443) — if OK → update status "Relay OK"
        2. If TLS fails → check TCP port 80 (HTTP) to distinguish:
           - Port 80 works + TLS fails = something breaks TLS (likely zapret desync)
           - Port 80 also fails = ISP blocks the IP entirely
        3. Update status label + show InfoBar warning if needed
        """
        # Show "checking..." in status
        mgr = _get_proxy_manager()
        if mgr.is_running:
            self._status_label.setText(
                f"Работает на {mgr.host}:{mgr.port} — проверка relay..."
            )

        def _do_check():
            try:
                from telegram_proxy.wss_proxy import check_relay_reachable
                result = check_relay_reachable(timeout=5.0)

                if result["reachable"]:
                    self._relay_diag = {"status": "ok", "ms": result["ms"]}
                else:
                    # TLS failed — check port 80 to determine cause
                    http_ok = self._check_relay_http()

                    # Determine if zapret is running
                    zapret_running = False
                    try:
                        app = self.window()
                        if hasattr(app, 'app') and hasattr(app.app, 'dpi_starter'):
                            zapret_running = app.app.dpi_starter.check_process_running_wmi(silent=True)
                    except Exception:
                        pass

                    self._relay_diag = {
                        "status": "fail",
                        "http_ok": http_ok,
                        "zapret_running": zapret_running,
                    }

                from PyQt6.QtCore import QMetaObject, Qt as QtNS
                QMetaObject.invokeMethod(
                    self, "_apply_relay_result",
                    QtNS.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                log(f"Relay check error: {e}", "WARNING")
        threading.Thread(target=_do_check, daemon=True).start()

    @staticmethod
    def _check_relay_http(relay_ip: str = "149.154.167.220", timeout: float = 5.0) -> bool:
        """Quick TCP check to relay on port 80 (HTTP). Returns True if port 80 responds."""
        import socket
        try:
            sock = socket.create_connection((relay_ip, 80), timeout=timeout)
            sock.close()
            return True
        except Exception:
            return False

    @pyqtSlot()
    def _apply_relay_result(self):
        """Update status label and show warning based on relay check. GUI thread only."""
        diag = getattr(self, "_relay_diag", {})
        mgr = _get_proxy_manager()

        if not mgr.is_running:
            return

        base = f"Работает на {mgr.host}:{mgr.port}"

        if diag.get("status") == "ok":
            ms = diag.get("ms", 0)
            self._status_label.setText(f"{base} — Relay OK ({ms:.0f}ms)")
            return

        # Relay check failed — update status + show warning
        http_ok = diag.get("http_ok", False)
        zapret_running = diag.get("zapret_running", False)

        if http_ok and zapret_running:
            # Сценарий 1: IP доступен, TLS ломается, Zapret запущен
            self._status_label.setText(f"{base} — Relay: стратегия Zapret ломает TLS")
            title = "Стратегия Zapret ломает Telegram прокси"
            content = (
                "Что происходит: IP relay (149.154.167.220) доступен, "
                "но текущая стратегия Zapret применяет desync к TLS "
                "и ломает подключение прокси.\n"
                "Что делать: смените стратегию Zapret на другую, "
                "или выключите Zapret и перезапустите прокси."
            )
        elif http_ok and not zapret_running:
            # Сценарий 2: IP доступен, TLS не проходит, Zapret выключен
            self._status_label.setText(f"{base} — Relay: TLS не проходит")
            title = "TLS к relay не проходит"
            content = (
                "Что происходит: IP relay (149.154.167.220) доступен по HTTP, "
                "но TLS (порт 443) не проходит.\n"
                "Что делать: если Zapret только что выключен — "
                "перезапустите прокси (нажмите Остановить → Запустить).\n"
                "Если после перезапуска проблема осталась — "
                "ваш провайдер блокирует TLS к Telegram. "
                "Настройте 'Внешний прокси' ниже."
            )
        elif zapret_running:
            # Сценарий 3: IP недоступен, Zapret запущен
            self._status_label.setText(f"{base} — Relay: недоступен, Zapret запущен")
            title = "Relay недоступен — возможно мешает Zapret"
            content = (
                "Что происходит: relay (149.154.167.220) не отвечает "
                "ни по HTTP, ни по TLS. Zapret запущен.\n"
                "Что делать: выключите Zapret и перезапустите прокси.\n"
                "Если без Zapret relay тоже недоступен — "
                "ваш провайдер блокирует IP Telegram. "
                "Настройте 'Внешний прокси' ниже."
            )
        else:
            # Сценарий 4: IP недоступен, Zapret выключен = провайдер блокирует
            self._status_label.setText(f"{base} — Relay: заблокирован провайдером")
            title = "Провайдер блокирует Telegram"
            content = (
                "Что происходит: relay (149.154.167.220) полностью недоступен — "
                "ваш провайдер блокирует IP Telegram.\n"
                "Прокси не сможет работать напрямую.\n"
                "Что делать: включите 'Внешний прокси' в настройках ниже "
                "и выберите один из доступных прокси-серверов."
            )

        if InfoBar is not None:
            InfoBar.warning(
                title, content,
                duration=-1,
                position=InfoBarPosition.TOP,
                parent=self,
            )

    def _stop_proxy(self):
        mgr = _get_proxy_manager()
        mgr.stop_proxy()
        try:
            from config.reg import set_tg_proxy_enabled
            set_tg_proxy_enabled(False)
        except Exception:
            pass

    def _on_status_changed(self, running: bool):
        self._status_dot.set_active(running)
        if running:
            mgr = _get_proxy_manager()
            self._status_label.setText(f"Работает на {mgr.host}:{mgr.port}")
            self._btn_toggle.setText("Остановить")
        else:
            self._status_label.setText("Остановлен")
            self._btn_toggle.setText("Запустить")
            self._stats_label.setText("")

        self._port_spin.setEnabled(not running)
        self._host_edit.setEnabled(not running)

    def _on_stats_updated(self, stats):
        if stats is None:
            return

        def _fmt_bytes(n: int) -> str:
            if n < 1024:
                return f"{n} B"
            if n < 1024 * 1024:
                return f"{n / 1024:.1f} KB"
            if n < 1024 * 1024 * 1024:
                return f"{n / (1024 * 1024):.1f} MB"
            return f"{n / (1024 * 1024 * 1024):.2f} GB"

        def _fmt_speed(n: int, secs: float) -> str:
            if secs <= 0:
                return "0 B/s"
            rate = n / secs
            if rate < 1024:
                return f"{rate:.0f} B/s"
            if rate < 1024 * 1024:
                return f"{rate / 1024:.1f} KB/s"
            return f"{rate / (1024 * 1024):.1f} MB/s"

        uptime = stats.uptime_seconds
        mins, secs = divmod(int(uptime), 60)
        hrs, mins = divmod(mins, 60)
        uptime_str = f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"

        now_sent = stats.bytes_sent
        now_recv = stats.bytes_received
        prev_sent = getattr(self, '_prev_bytes_sent', 0)
        prev_recv = getattr(self, '_prev_bytes_received', 0)
        delta_sent = now_sent - prev_sent
        delta_recv = now_recv - prev_recv
        self._prev_bytes_sent = now_sent
        self._prev_bytes_received = now_recv
        interval = 2.0

        recv_zero = getattr(stats, 'recv_zero_count', 0)
        recv_zero_str = f"  |  recv=0: {recv_zero}" if recv_zero > 0 else ""

        self._stats_label.setText(
            f"Подключения: {stats.active_connections} акт. / {stats.total_connections} всего  |  "
            f"↑ {_fmt_bytes(now_sent)} ({_fmt_speed(delta_sent, interval)})  "
            f"↓ {_fmt_bytes(now_recv)} ({_fmt_speed(delta_recv, interval)})  |  "
            f"Uptime: {uptime_str}{recv_zero_str}"
        )

    def _on_autostart_changed(self, checked: bool):
        try:
            from config.reg import set_tg_proxy_autostart
            set_tg_proxy_autostart(checked)
        except Exception:
            pass

    def _on_port_changed(self, port: int):
        try:
            from config.reg import set_tg_proxy_port
            set_tg_proxy_port(port)
        except Exception:
            pass
        self._update_manual_instructions()

    def _on_host_changed(self):
        host = self._host_edit.text().strip()
        if not self._validate_host(host):
            self._host_edit.setText("127.0.0.1")
            host = "127.0.0.1"
        try:
            from config.reg import set_tg_proxy_host
            set_tg_proxy_host(host)
        except Exception:
            pass
        self._update_manual_instructions()

    # -- Upstream proxy handlers --

    def _on_upstream_changed(self, checked: bool):
        try:
            from config.reg import set_tg_proxy_upstream_enabled
            set_tg_proxy_upstream_enabled(checked)
        except Exception:
            pass

    def _on_upstream_preset_changed(self, index: int):
        """Handle preset ComboBox selection. Auto-fill fields and save to registry."""
        if index < 0 or index >= len(self._upstream_presets):
            return
        preset = self._upstream_presets[index]
        is_manual = (index == 0)
        self._upstream_manual_widget.setVisible(is_manual)

        if not is_manual:
            # Auto-fill from preset and save to registry
            self._upstream_host_edit.setText(preset["host"])
            self._upstream_port_spin.blockSignals(True)
            self._upstream_port_spin.setValue(preset["port"])
            self._upstream_port_spin.blockSignals(False)
            self._upstream_user_edit.setText(preset["username"])
            self._upstream_pass_edit.setText(preset["password"])
            self._save_upstream_fields(
                preset["host"], preset["port"],
                preset["username"], preset["password"],
            )

    def _save_upstream_fields(self, host: str, port: int, user: str, password: str):
        """Save all upstream proxy fields to registry."""
        try:
            from config.reg import (set_tg_proxy_upstream_host, set_tg_proxy_upstream_port,
                                     set_tg_proxy_upstream_user, set_tg_proxy_upstream_pass)
            set_tg_proxy_upstream_host(host)
            set_tg_proxy_upstream_port(port)
            set_tg_proxy_upstream_user(user)
            set_tg_proxy_upstream_pass(password)
        except Exception:
            pass

    def _on_upstream_host_changed(self):
        try:
            from config.reg import set_tg_proxy_upstream_host
            set_tg_proxy_upstream_host(self._upstream_host_edit.text().strip())
        except Exception:
            pass

    def _on_upstream_port_changed(self, port: int):
        try:
            from config.reg import set_tg_proxy_upstream_port
            set_tg_proxy_upstream_port(port)
        except Exception:
            pass

    def _on_upstream_user_changed(self):
        try:
            from config.reg import set_tg_proxy_upstream_user
            set_tg_proxy_upstream_user(self._upstream_user_edit.text().strip())
        except Exception:
            pass

    def _on_upstream_pass_changed(self):
        try:
            from config.reg import set_tg_proxy_upstream_pass
            set_tg_proxy_upstream_pass(self._upstream_pass_edit.text())
        except Exception:
            pass

    def _on_upstream_mode_changed(self, checked: bool):
        try:
            from config.reg import set_tg_proxy_upstream_mode
            set_tg_proxy_upstream_mode("always" if checked else "fallback")
        except Exception:
            pass

    def _on_open_mtproxy(self):
        """Open MTProxy deep link in browser."""
        link = self._mtproxy_link
        if not link:
            return
        try:
            webbrowser.open(link)
            self._append_log_line("Opened MTProxy link")
        except Exception as e:
            self._append_log_line(f"Failed to open MTProxy link: {e}")

    @staticmethod
    def _validate_host(host: str) -> bool:
        """Accept valid IPv4 address or 0.0.0.0."""
        if not host:
            return False
        parts = host.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    def _update_manual_instructions(self):
        """Update manual instructions label with current host/port."""
        host = self._host_edit.text().strip() or "127.0.0.1"
        port = self._port_spin.value()
        self._manual_host_port_label.setText(
            f"  Тип: SOCKS5  |  Хост: {host}  |  Порт: {port}"
        )

    def _get_proxy_url(self) -> str:
        """Build tg://socks deep link with current host and port."""
        host = self._host_edit.text().strip() or "127.0.0.1"
        port = self._port_spin.value()
        return f"tg://socks?server={host}&port={port}"

    def _on_open_in_telegram(self):
        """Open tg://socks deep link to auto-configure Telegram."""
        url = self._get_proxy_url()
        try:
            webbrowser.open(url)
            self._append_log_line(f"Opened deep link: {url}")
        except Exception as e:
            self._append_log_line(f"Failed to open link: {e}")

    def _on_copy_link(self):
        """Copy proxy deep link to clipboard."""
        url = self._get_proxy_url()
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(url)
            self._append_log_line(f"Copied to clipboard: {url}")
            if _HAS_FLUENT and InfoBar is not None:
                try:
                    InfoBar.success(
                        title="Скопировано",
                        content=url,
                        parent=self,
                        duration=2000,
                        position=InfoBarPosition.TOP,
                    )
                except Exception:
                    pass

    # -- Hosts auto-management on tab show --

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_telegram_hosts()

    def _ensure_telegram_hosts(self):
        """Check/add Telegram entries in Windows hosts file (background thread)."""
        import threading
        threading.Thread(
            target=self._ensure_telegram_hosts_worker,
            daemon=True,
        ).start()

    @staticmethod
    def _ensure_telegram_hosts_worker():
        try:
            from telegram_proxy.telegram_hosts import ensure_telegram_hosts
            ensure_telegram_hosts()
        except Exception as e:
            log(f"Telegram hosts check error: {e}", "WARNING")

    def cleanup(self):
        """Called on app exit."""
        self._log_timer.stop()
        mgr = _get_proxy_manager()
        mgr.cleanup()
