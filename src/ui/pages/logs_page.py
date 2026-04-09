# ui/pages/logs_page.py
"""Страница просмотра логов в реальном времени"""

from PyQt6.QtCore import Qt, QThread, QTimer, QVariantAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QApplication,
    QSplitter, QTextEdit, QStackedWidget, QLineEdit, QFrame
)
try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        PushButton as FluentPushButton,
        ComboBox,
        SegmentedWidget, ToolButton, InfoBar,
    )
    _FLUENT_OK = True
except ImportError:
    ComboBox = QComboBox
    InfoBar = None
    _FLUENT_OK = False
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QPixmap, QPainter, QTransform, QIcon
import qtawesome as qta
import os
import re
import threading
import queue
import html

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.compat_widgets import SettingsCard, ActionButton, set_tooltip
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from log import log
from log.logs_page_controller import LogsPageController
from log_tail import LogTailWorker

# Паттерны для определения РЕАЛЬНЫХ ошибок (строгие)
ERROR_PATTERNS = [
    r'\[❌ ERROR\]',           # Наш формат ошибок
    r'\[❌ CRITICAL\]',        # Критические ошибки
    r'AttributeError:',        # Python ошибки атрибутов
    r'TypeError:',             # Python ошибки типов
    r'ValueError:',            # Python ошибки значений
    r'KeyError:',              # Python ошибки ключей
    r'ImportError:',           # Python ошибки импорта
    r'ModuleNotFoundError:',   # Python модуль не найден
    r'FileNotFoundError:',     # Файл не найден
    r'PermissionError:',       # Ошибка доступа
    r'OSError:',               # Ошибка ОС
    r'RuntimeError:',          # Ошибка выполнения
    r'UnboundLocalError:',     # Переменная не определена
    r'NameError:',             # Имя не определено
    r'IndexError:',            # Индекс за пределами
    r'ZeroDivisionError:',     # Деление на ноль
    r'RecursionError:',        # Переполнение рекурсии
    r'🔴 CRASH',               # Краш репорты
]

# Паттерны для ИСКЛЮЧЕНИЯ (не ошибки, хотя содержат ключевые слова)
EXCLUDE_PATTERNS = [
    r'Faulthandler enabled',   # Информация о включении faulthandler
    r'Crash handler установлен', # Информация об установке обработчика
    r'connection error:.*HTTPSConnectionPool',  # Сетевые ошибки VPS (не критично)
    r'connection error:.*HTTPConnectionPool',   # Сетевые ошибки VPS (не критично)
    r'\[POOL\].*ошибка',       # Ошибки пула серверов (fallback работает)
    r'Theme error:.*NoneType', # Ошибки темы при инициализации (временные)
]


class WinwsOutputWorker(QObject):
    """Worker для чтения stdout/stderr от процесса winws"""
    new_output = pyqtSignal(str, str)  # (text, stream_type: 'stdout' | 'stderr')
    process_ended = pyqtSignal(int)     # exit_code
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = False
        self._process = None

    def set_process(self, process):
        """Устанавливает процесс для мониторинга"""
        self._process = process

    def run(self):
        """Читает вывод процесса в реальном времени"""
        self._running = True

        if not self._process:
            self.finished.emit()
            return

        def read_stream(stream, stream_type):
            """Читает поток в отдельном потоке"""
            try:
                while self._running and self._process.poll() is None:
                    line = stream.readline()
                    if line:
                        try:
                            text = line.decode('utf-8', errors='replace').rstrip()
                        except:
                            text = str(line).rstrip()
                        if text:
                            self.new_output.emit(text, stream_type)
                    else:
                        if not self._running:
                            break
                        # Protect from busy-loop when pipe returns empty chunk.
                        QThread.msleep(25)

                # Читаем оставшееся после завершения
                remaining = stream.read()
                if remaining:
                    try:
                        text = remaining.decode('utf-8', errors='replace').rstrip()
                    except:
                        text = str(remaining).rstrip()
                    if text:
                        for line in text.split('\n'):
                            if line.strip():
                                self.new_output.emit(line.strip(), stream_type)
            except Exception as e:
                log(f"Ошибка чтения {stream_type}: {e}", "DEBUG")

        # Запускаем чтение stdout и stderr в отдельных потоках
        stdout_thread = None
        stderr_thread = None

        if self._process.stdout:
            stdout_thread = threading.Thread(
                target=read_stream,
                args=(self._process.stdout, 'stdout'),
                daemon=True
            )
            stdout_thread.start()

        if self._process.stderr:
            stderr_thread = threading.Thread(
                target=read_stream,
                args=(self._process.stderr, 'stderr'),
                daemon=True
            )
            stderr_thread.start()

        # Ждём завершения процесса
        try:
            while self._running and self._process.poll() is None:
                QThread.msleep(200)

            # Ждём завершения потоков чтения
            if stdout_thread and stdout_thread.is_alive():
                stdout_thread.join(timeout=1.0)
            if stderr_thread and stderr_thread.is_alive():
                stderr_thread.join(timeout=1.0)

            if self._process.returncode is not None:
                self.process_ended.emit(self._process.returncode)

        except Exception as e:
            log(f"Ошибка мониторинга процесса: {e}", "DEBUG")

        self._running = False
        self.finished.emit()

    def stop(self):
        """Останавливает worker"""
        self._running = False


class LogsPage(BasePage):
    """Страница просмотра логов"""
    
    def __init__(self, parent=None):
        super().__init__(
            "Логи",
            "Просмотр логов приложения в реальном времени",
            parent,
            title_key="page.logs.title",
            subtitle_key="page.logs.subtitle",
        )
        
        # Отключаем горизонтальную прокрутку страницы
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._thread = None
        self._worker = None
        self._controller = LogsPageController()
        self.current_log_file = self._controller.get_current_log_file()
        self._error_pattern = re.compile('|'.join(ERROR_PATTERNS))
        self._exclude_pattern = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

        self._tokens = get_theme_tokens()

        # Theme-dependent colors used in runtime status/output updates.
        self._winws_stdout_color = "#00ff88"
        self._winws_stderr_color = "#ff6b6b"
        self._winws_status_neutral = self._tokens.fg_muted
        self._winws_status_running = self._tokens.accent_hex
        self._winws_status_error = self._tokens.fg

        # References for theme refresh (icons/labels created as locals).
        self._warning_icon_label = None
        self._terminal_icon_label = None
        self._info_icon_label = None
        self._orchestra_icon_label = None
        self._orchestra_text_label = None
        self._send_status_text = ""
        self._send_status_tone = "neutral"

        # Winws output worker
        self._winws_thread = None
        self._winws_worker = None
        self._winws_lines_count = 0

        # Error panel height tuning (avoid large empty block when no errors).
        self._errors_text_min_height = 52
        self._errors_text_max_height = 140

        # Таймер для обновления статуса winws
        self._winws_status_timer = QTimer(self)
        self._winws_status_timer.timeout.connect(self._update_winws_status)

        self._logs_tab_initialized = False
        self._send_tab_initialized = False

        # qtawesome animations (e.g. qta.Spin) are not QAbstractAnimation; track state ourselves.
        self._refresh_spin_active = False
        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        try:
            self._apply_page_theme(force=True)
        except Exception:
            pass

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        self._tokens = tokens

        # Controls — log_combo is now a Fluent ComboBox; no manual stylesheet needed
        # Tabs — Pivot handles its own theme

        if hasattr(self, "refresh_btn"):
            self._refresh_icon_normal = qta.icon('fa5s.sync-alt', color=tokens.fg)
            if not bool(getattr(self, "_refresh_spin_active", False)):
                self.refresh_btn.setIcon(self._refresh_icon_normal)

        # info_label is now a CaptionLabel (Fluent) — no manual style needed

        # Log area
        editor_bg = tokens.surface_bg
        editor_fg = tokens.fg
        if hasattr(self, "log_text"):
            self.log_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {editor_bg};"
                f" color: {editor_fg};"
                f" border: 1px solid {tokens.surface_border};"
                " border-radius: 6px;"
                " padding: 12px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " line-height: 1.4;"
                " }"
            )

        # stats_label is now a CaptionLabel (Fluent) — no manual style needed

        # Errors panel
        err_fg = "rgba(220, 38, 38, 0.92)" if tokens.is_light else "rgba(248, 113, 113, 0.95)"
        err_bg = "rgba(220, 38, 38, 0.08)" if tokens.is_light else "rgba(248, 113, 113, 0.10)"
        err_border = "rgba(220, 38, 38, 0.25)" if tokens.is_light else "rgba(248, 113, 113, 0.25)"

        if self._warning_icon_label is not None:
            try:
                self._warning_icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color=err_fg).pixmap(16, 16))
            except Exception:
                pass

        # errors_count_label is now a CaptionLabel (Fluent) — no manual style needed

        if hasattr(self, "errors_text"):
            self.errors_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {err_bg};"
                f" color: {err_fg};"
                f" border: 1px solid {err_border};"
                " border-radius: 6px;"
                " padding: 8px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " }"
            )

        # winws panel
        if self._terminal_icon_label is not None:
            try:
                self._terminal_icon_label.setPixmap(qta.icon('fa5s.terminal', color=tokens.accent_hex).pixmap(16, 16))
            except Exception:
                pass

        self._winws_stdout_color = "rgba(21, 128, 61, 0.92)" if tokens.is_light else "#00ff88"
        self._winws_stderr_color = err_fg
        self._winws_status_neutral = tokens.fg_muted
        self._winws_status_running = tokens.accent_hex
        self._winws_status_error = err_fg

        if hasattr(self, "winws_text"):
            self.winws_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {editor_bg};"
                f" color: {editor_fg};"
                f" border: 1px solid {tokens.surface_border};"
                " border-radius: 6px;"
                " padding: 8px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " }"
            )
            self._refresh_winws_status_style_only()

        # Send tab (exists only after lazy init)
        if self._info_icon_label is not None:
            try:
                self._info_icon_label.setPixmap(qta.icon('fa5s.info-circle', color=tokens.accent_hex).pixmap(14, 14))
            except Exception:
                pass

        # Orchestra mode indicator (Send tab, lazy-init)
        if self._orchestra_icon_label is not None:
            try:
                self._render_orchestra_banner_style(tokens)
            except Exception:
                pass

        # send_status_label shows the result of opening support links/folders
        try:
            self._render_send_status_label(tokens)
        except Exception:
            pass

    def _render_orchestra_banner_style(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        if getattr(self, "orchestra_mode_container", None) is None:
            return

        accent = "#7c3aed" if theme_tokens.is_light else "#a855f7"
        bg = "rgba(124, 58, 237, 0.12)" if theme_tokens.is_light else "rgba(168, 85, 247, 0.15)"

        if self._orchestra_icon_label is not None:
            self._orchestra_icon_label.setPixmap(qta.icon('fa5s.brain', color=accent).pixmap(16, 16))
        if self._orchestra_text_label is not None:
            self._orchestra_text_label.setStyleSheet(
                f"color: {accent}; font-size: 12px; font-weight: 600; background: transparent;"
            )
        self.orchestra_mode_container.setStyleSheet(
            "QWidget {"
            f" background-color: {bg};"
            " border-radius: 8px;"
            " }"
        )

    def _render_send_status_label(self, tokens=None) -> None:
        label = getattr(self, "send_status_label", None)
        if label is None:
            return

        theme_tokens = tokens or get_theme_tokens()
        text = str(getattr(self, "_send_status_text", "") or "")
        tone = str(getattr(self, "_send_status_tone", "neutral") or "neutral").strip().lower()

        label.setText(text)
        if not text:
            label.setStyleSheet("")
            return

        color = theme_tokens.accent_hex
        if tone == "error":
            color = "#f87171" if not theme_tokens.is_light else "#dc2626"
        label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _update_tab_styles(self) -> None:
        """No-op — Pivot manages its own indicator."""

    def _refresh_winws_status_style_only(self) -> None:
        try:
            cur = (self.winws_status_label.text() or "").strip()
        except Exception:
            cur = ""
        if not cur:
            self._set_winws_status("neutral", "")
            return

        if "PID:" in cur:
            self._set_winws_status("running", cur)
            return

        if "ошиб" in cur.lower():
            self._set_winws_status("error", cur)
            return

        self._set_winws_status("neutral", cur)

    def _set_winws_status(self, kind: str, text: str) -> None:
        if kind == "running":
            color = self._winws_status_running
        elif kind == "error":
            color = self._winws_status_error
        else:
            color = self._winws_status_neutral

        self.winws_status_label.setText(text)
        self.winws_status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        
    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # Переключатель табов (ЛОГИ / ОТПРАВКА) — Fluent Pivot
        # ═══════════════════════════════════════════════════════════
        if _FLUENT_OK:
            self.tabs_pivot = SegmentedWidget()
            self.tabs_pivot.addItem(
                routeKey="logs",
                text=" " + tr_catalog("page.logs.tab.logs", default="ЛОГИ"),
                onClick=lambda: self._switch_tab(0),
            )
            self.tabs_pivot.addItem(
                routeKey="send",
                text=" " + tr_catalog("page.logs.tab.send", default="ОТПРАВКА"),
                onClick=lambda: self._switch_tab(1),
            )
            self.tabs_pivot.setCurrentItem("logs")
            self.tabs_pivot.setItemFontSize(13)
            self.add_widget(self.tabs_pivot)
        else:
            # Fallback без Fluent
            tabs_container = QWidget()
            tabs_layout = QHBoxLayout(tabs_container)
            tabs_layout.setContentsMargins(0, 0, 0, 8)
            tabs_layout.setSpacing(0)
            self.tab_logs_btn = QPushButton(" " + tr_catalog("page.logs.tab.logs", default="ЛОГИ"))
            self.tab_logs_btn.clicked.connect(lambda: self._switch_tab(0))
            tabs_layout.addWidget(self.tab_logs_btn)
            self.tab_send_btn = QPushButton(" " + tr_catalog("page.logs.tab.send", default="ОТПРАВКА"))
            self.tab_send_btn.clicked.connect(lambda: self._switch_tab(1))
            tabs_layout.addWidget(self.tab_send_btn)
            tabs_layout.addStretch()
            self.add_widget(tabs_container)

        # ═══════════════════════════════════════════════════════════
        # Стек страниц (ЛОГИ / ОТПРАВКА)
        # ═══════════════════════════════════════════════════════════
        self.stacked_widget = QStackedWidget()

        # Страница 1: Логи
        self._logs_page = QWidget()
        logs_layout = QVBoxLayout(self._logs_page)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(16)

        self._build_logs_tab(logs_layout)

        # Страница 2: Отправка (лениво создаётся при первом переходе)
        self._send_page = QWidget()
        send_layout = QVBoxLayout(self._send_page)
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(16)
        self._send_layout = send_layout

        self.stacked_widget.addWidget(self._logs_page)
        self.stacked_widget.addWidget(self._send_page)

        self.add_widget(self.stacked_widget)

        # Apply token-driven styles once widgets exist.
        self._apply_page_theme()

    def _switch_tab(self, index: int):
        """Переключает между табами"""
        if index == 1 and not self._send_tab_initialized:
            self._send_tab_initialized = True
            try:
                self._build_send_tab(self._send_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки отправки: {e}", "ERROR")

        self.stacked_widget.setCurrentIndex(index)

        # Sync Pivot indicator
        if _FLUENT_OK and hasattr(self, "tabs_pivot"):
            key = "send" if index == 1 else "logs"
            try:
                self.tabs_pivot.setCurrentItem(key)
            except Exception:
                pass

        if index == 1:
            # Обновляем видимость индикатора оркестратора
            self._update_orchestra_indicator()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        logs_text = " " + tr_catalog("page.logs.tab.logs", language=language, default="ЛОГИ")
        send_text = " " + tr_catalog("page.logs.tab.send", language=language, default="ОТПРАВКА")

        if _FLUENT_OK and hasattr(self, "tabs_pivot"):
            try:
                self.tabs_pivot.setItemText("logs", logs_text)
                self.tabs_pivot.setItemText("send", send_text)
            except Exception:
                pass

        if hasattr(self, "tab_logs_btn") and self.tab_logs_btn is not None:
            try:
                self.tab_logs_btn.setText(logs_text)
            except Exception:
                pass
        if hasattr(self, "tab_send_btn") and self.tab_send_btn is not None:
            try:
                self.tab_send_btn.setText(send_text)
            except Exception:
                pass

        if self.is_deferred_ui_build_pending():
            return

        self._retranslate_logs_tab()
        if self._send_tab_initialized:
            self._retranslate_send_tab()
            self._render_send_status_label()

    def _set_card_title(self, card: SettingsCard, text: str) -> None:
        try:
            item = card.main_layout.itemAt(0)
            widget = item.widget() if item else None
            if widget is not None and hasattr(widget, "setText"):
                widget.setText(text)
        except Exception:
            pass

    def _retranslate_logs_tab(self) -> None:
        try:
            self._set_card_title(
                self.controls_card,
                tr_catalog("page.logs.card.controls", language=self._ui_language, default="Управление логами"),
            )
            self._set_card_title(
                self.log_card,
                tr_catalog("page.logs.card.content", language=self._ui_language, default="Содержимое"),
            )
        except Exception:
            pass

        try:
            set_tooltip(
                self.refresh_btn,
                tr_catalog("page.logs.tooltip.refresh", language=self._ui_language, default="Обновить список файлов"),
            )
        except Exception:
            pass

        try:
            self.copy_btn.setText(tr_catalog("page.logs.button.copy", language=self._ui_language, default="Копировать"))
            self.clear_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.folder_btn.setText(tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка"))
            self.errors_title_label.setText(tr_catalog("page.logs.errors.title", language=self._ui_language, default="Ошибки и предупреждения"))
            self.clear_errors_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.clear_winws_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.errors_count_label.setText(
                tr_catalog("page.logs.errors.count", language=self._ui_language, default="Ошибок: {count}").format(
                    count=max(0, int(self._errors_count))
                )
            )
            self._refresh_winws_title()
        except Exception:
            pass

    def _retranslate_send_tab(self) -> None:
        try:
            self._set_card_title(
                self.send_card,
                tr_catalog("page.logs.send.card.title", language=self._ui_language, default="Поддержка через GitHub Discussions"),
            )
            self._orchestra_text_label.setText(
                tr_catalog(
                    "page.logs.send.orchestra.active",
                    language=self._ui_language,
                    default="В режиме оркестратора проверьте основной лог и файл orchestra_*.log",
                )
            )
            self.send_desc_label.setText(
                tr_catalog(
                    "page.logs.send.desc",
                    language=self._ui_language,
                    default="Нажмите кнопку, чтобы собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
                )
            )
            self.send_info_label.setText(
                tr_catalog(
                    "page.logs.send.info",
                    language=self._ui_language,
                    default="Будет создан архив в папке logs/support_bundles. Шаблон обращения автоматически попадёт в буфер обмена.",
                )
            )
            self.send_log_btn.setText(
                tr_catalog("page.logs.send.button.send", language=self._ui_language, default="Подготовить обращение")
            )
            self.open_logs_folder_btn.setText(
                tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка")
            )
        except Exception:
            pass

    def _build_logs_tab(self, parent_layout):
        """Строит вкладку с логами"""
        # ═══════════════════════════════════════════════════════════
        # Панель управления (выбор файла + кнопки в 2 ряда)
        # ═══════════════════════════════════════════════════════════
        controls_card = SettingsCard(
            tr_catalog("page.logs.card.controls", language=self._ui_language, default="Управление логами")
        )
        self.controls_card = controls_card
        controls_main = QVBoxLayout()
        controls_main.setSpacing(12)
        
        # Ряд 1: выбор файла + кнопка обновления
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        self.log_combo = ComboBox()
        self.log_combo.setMinimumWidth(350)
        self.log_combo.currentIndexChanged.connect(self._on_log_selected)
        row1.addWidget(self.log_combo, 1)
        
        _RefreshBtn = ToolButton if _FLUENT_OK else QPushButton
        self.refresh_btn = _RefreshBtn()
        tokens = get_theme_tokens()
        self._refresh_icon_normal = qta.icon('fa5s.sync-alt', color=tokens.fg)
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(33)  # ~30 fps
        self._spin_angle = 0
        self._spin_timer.timeout.connect(self._on_spin_tick)
        self.refresh_btn.setIcon(self._refresh_icon_normal)
        self.refresh_btn.setFixedSize(36, 36)
        set_tooltip(
            self.refresh_btn,
            tr_catalog("page.logs.tooltip.refresh", language=self._ui_language, default="Обновить список файлов"),
        )
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._refresh_logs_list)
        row1.addWidget(self.refresh_btn)
        
        controls_main.addLayout(row1)
        
        # Ряд 2: кнопки действий
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        
        self.copy_btn = ActionButton(
            tr_catalog("page.logs.button.copy", language=self._ui_language, default="Копировать"),
            "fa5s.copy",
        )
        self.copy_btn.clicked.connect(self._copy_log)
        row2.addWidget(self.copy_btn)

        self.clear_btn = ActionButton(
            tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"),
            "fa5s.eraser",
        )
        self.clear_btn.clicked.connect(self._clear_view)
        row2.addWidget(self.clear_btn)

        self.folder_btn = ActionButton(
            tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка"),
            "fa5s.folder-open",
        )
        self.folder_btn.clicked.connect(self._open_folder)
        row2.addWidget(self.folder_btn)

        row2.addStretch()
        
        # Информационная строка
        self.info_label = (CaptionLabel if _FLUENT_OK else QLabel)()
        row2.addWidget(self.info_label)
        
        controls_main.addLayout(row2)
        
        controls_card.add_layout(controls_main)
        parent_layout.addWidget(controls_card)

        # ═══════════════════════════════════════════════════════════
        # Область логов
        # ═══════════════════════════════════════════════════════════
        log_card = SettingsCard(
            tr_catalog("page.logs.card.content", language=self._ui_language, default="Содержимое")
        )
        self.log_card = log_card
        log_layout = QVBoxLayout()
        
        # Текстовое поле для логов (блокирует провал прокрутки)
        self.log_text = ScrollBlockingTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(260)
        log_layout.addWidget(self.log_text)
        
        # Статистика внизу лог-карточки
        self.stats_label = (CaptionLabel if _FLUENT_OK else QLabel)()
        log_layout.addWidget(self.stats_label)
        
        log_card.add_layout(log_layout)
        parent_layout.addWidget(log_card)

        # ═══════════════════════════════════════════════════════════
        # Панель ошибок
        # ═══════════════════════════════════════════════════════════
        errors_card = SettingsCard()  # Без заголовка - добавим свой с иконкой
        errors_layout = QVBoxLayout()
        
        # Заголовок с иконкой и кнопкой очистки
        errors_header = QHBoxLayout()
        
        # Иконка предупреждения
        warning_icon = QLabel()
        self._warning_icon_label = warning_icon
        errors_header.addWidget(warning_icon)
        
        # Заголовок
        self.errors_title_label = (StrongBodyLabel if _FLUENT_OK else QLabel)(
            tr_catalog("page.logs.errors.title", language=self._ui_language, default="Ошибки и предупреждения")
        )
        errors_header.addWidget(self.errors_title_label)
        errors_header.addSpacing(8)

        self.errors_count_label = (CaptionLabel if _FLUENT_OK else QLabel)(
            tr_catalog("page.logs.errors.count", language=self._ui_language, default="Ошибок: {count}").format(count=0)
        )
        errors_header.addWidget(self.errors_count_label)
        
        errors_header.addStretch()
        
        self.clear_errors_btn = ActionButton(
            tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"),
            "fa5s.trash",
        )
        self.clear_errors_btn.clicked.connect(self._clear_errors)
        errors_header.addWidget(self.clear_errors_btn)
        
        errors_layout.addLayout(errors_header)
        
        # Текстовое поле для ошибок (блокирует провал прокрутки)
        self.errors_text = ScrollBlockingTextEdit()
        self.errors_text.setReadOnly(True)
        self.errors_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.errors_text.setFont(QFont("Consolas", 9))
        self.errors_text.setMinimumHeight(self._errors_text_min_height)
        self.errors_text.setMaximumHeight(self._errors_text_max_height)
        self.errors_text.document().contentsChanged.connect(self._update_errors_text_height)
        self._update_errors_text_height()
        errors_layout.addWidget(self.errors_text)

        errors_card.add_layout(errors_layout)
        self.errors_card = errors_card
        parent_layout.addWidget(errors_card)

        # ═══════════════════════════════════════════════════════════
        # Панель вывода winws
        # ═══════════════════════════════════════════════════════════
        winws_card = SettingsCard()
        winws_layout = QVBoxLayout()

        # Заголовок с иконкой
        winws_header = QHBoxLayout()

        # Иконка терминала
        terminal_icon = QLabel()
        self._terminal_icon_label = terminal_icon
        winws_header.addWidget(terminal_icon)

        # Заголовок
        self.winws_title_label = (StrongBodyLabel if _FLUENT_OK else QLabel)(
            tr_catalog(
                "page.logs.winws.title_template",
                language=self._ui_language,
                default="Вывод {exe_name}",
            ).format(exe_name="winws.exe")
        )
        winws_header.addWidget(self.winws_title_label)
        winws_header.addSpacing(16)

        # Статус процесса
        self.winws_status_label = (CaptionLabel if _FLUENT_OK else QLabel)(
            tr_catalog("page.logs.winws.status.not_running", language=self._ui_language, default="Процесс не запущен")
        )
        winws_header.addWidget(self.winws_status_label)

        winws_header.addStretch()

        # Кнопка очистки
        self.clear_winws_btn = ActionButton(
            tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"),
            "fa5s.trash",
        )
        self.clear_winws_btn.clicked.connect(self._clear_winws_output)
        winws_header.addWidget(self.clear_winws_btn)

        winws_layout.addLayout(winws_header)

        # Текстовое поле для вывода winws
        self.winws_text = ScrollBlockingTextEdit()
        self.winws_text.setReadOnly(True)
        self.winws_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.winws_text.setFont(QFont("Consolas", 9))
        self.winws_text.setFixedHeight(150)
        winws_layout.addWidget(self.winws_text)

        winws_card.add_layout(winws_layout)
        self.winws_card = winws_card
        parent_layout.addWidget(winws_card)

        # Счётчик ошибок
        self._errors_count = 0
        try:
            self.stats_label.setText(
                tr_catalog("page.logs.stats.loading", language=self._ui_language, default="📊 Загрузка...")
            )
        except Exception:
            pass

        self._refresh_winws_title()

    def _build_send_tab(self, parent_layout):
        """Строит вкладку поддержки по логам."""

        # ═══════════════════════════════════════════════════════════
        # Форма отправки
        # ═══════════════════════════════════════════════════════════
        send_card = SettingsCard(
            tr_catalog("page.logs.send.card.title", language=self._ui_language, default="Поддержка через GitHub Discussions")
        )
        self.send_card = send_card
        send_layout = QVBoxLayout()
        send_layout.setSpacing(16)

        # Индикатор режима оркестратора (скрыт по умолчанию)
        self.orchestra_mode_container = QWidget()
        orchestra_layout = QHBoxLayout(self.orchestra_mode_container)
        orchestra_layout.setContentsMargins(12, 8, 12, 8)
        orchestra_layout.setSpacing(8)

        orchestra_icon = QLabel()
        try:
            from qfluentwidgets import isDarkTheme as _idt
            _orch_clr_init = "#a855f7" if _idt() else "#7c3aed"
        except Exception:
            _orch_clr_init = "#a855f7"
        orchestra_icon.setPixmap(qta.icon('fa5s.brain', color=_orch_clr_init).pixmap(16, 16))
        self._orchestra_icon_label = orchestra_icon
        orchestra_layout.addWidget(orchestra_icon)

        orchestra_text = (BodyLabel if _FLUENT_OK else QLabel)(
            tr_catalog(
                "page.logs.send.orchestra.active",
                language=self._ui_language,
                default="В режиме оркестратора проверьте основной лог и файл orchestra_*.log",
            )
        )
        orchestra_text.setStyleSheet(f"color: {_orch_clr_init}; font-size: 12px; font-weight: 600; background: transparent;")
        self._orchestra_text_label = orchestra_text
        orchestra_layout.addWidget(orchestra_text)
        orchestra_layout.addStretch()

        _orch_bg = "rgba(124, 58, 237, 0.12)" if _orch_clr_init == "#7c3aed" else "rgba(168, 85, 247, 0.15)"
        self.orchestra_mode_container.setStyleSheet(
            "QWidget {"
            f" background-color: {_orch_bg};"
            " border-radius: 8px;"
            " }"
        )
        self.orchestra_mode_container.setVisible(False)
        send_layout.addWidget(self.orchestra_mode_container)

        # Описание
        self.send_desc_label = (BodyLabel if _FLUENT_OK else QLabel)(
            tr_catalog(
                "page.logs.send.desc",
                language=self._ui_language,
                default="Нажмите кнопку, чтобы собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
            )
        )
        self.send_desc_label.setWordWrap(True)
        send_layout.addWidget(self.send_desc_label)

        # Информация
        info_container = QWidget()
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 8, 0, 8)

        info_icon = QLabel()
        self._info_icon_label = info_icon
        info_layout.addWidget(info_icon)

        self.send_info_label = (CaptionLabel if _FLUENT_OK else QLabel)(
            tr_catalog(
                "page.logs.send.info",
                language=self._ui_language,
                default="Будет создан архив в папке logs/support_bundles. Шаблон обращения автоматически попадёт в буфер обмена.",
            )
        )
        self.send_info_label.setWordWrap(True)
        info_layout.addWidget(self.send_info_label, 1)

        send_layout.addWidget(info_container)

        # Кнопки поддержки
        buttons_row = QHBoxLayout()

        self.send_log_btn = ActionButton(
            tr_catalog("page.logs.send.button.send", language=self._ui_language, default="Подготовить обращение"),
            "fa5b.github",
        )
        self.send_log_btn.clicked.connect(self._prepare_support_from_logs)
        buttons_row.addWidget(self.send_log_btn)

        self.open_logs_folder_btn = ActionButton(
            tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка"),
            "fa5s.folder-open",
        )
        self.open_logs_folder_btn.clicked.connect(self._open_folder)
        buttons_row.addWidget(self.open_logs_folder_btn)

        buttons_row.addStretch()

        # Статус отправки
        self.send_status_label = (CaptionLabel if _FLUENT_OK else QLabel)()
        buttons_row.addWidget(self.send_status_label)

        send_layout.addLayout(buttons_row)

        send_card.add_layout(send_layout)
        parent_layout.addWidget(send_card)

        # Растяжка чтобы форма была вверху
        parent_layout.addStretch()

        # Send tab is lazily built; apply current theme now.
        self._retranslate_send_tab()
        self._apply_page_theme(force=True)

    def _is_orchestra_mode(self) -> bool:
        """Проверяет, активен ли режим оркестратора"""
        return self._get_launch_method() == "orchestra"

    def _get_launch_method(self) -> str:
        """Возвращает текущий метод запуска"""
        try:
            from strategy_menu import get_strategy_launch_method
            return (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            return ""

    def _get_orchestra_runner(self):
        """Возвращает orchestra_runner из главного окна"""
        try:
            app = self.window()
            runner = getattr(app, 'orchestra_runner', None) if app else None
            if runner:
                return runner
        except Exception:
            pass

        try:
            qapp = QApplication.instance()
            if qapp:
                active_window_getter = getattr(qapp, 'activeWindow', None)
                main_window = active_window_getter() if callable(active_window_getter) else None
                runner = getattr(main_window, 'orchestra_runner', None) if main_window else None
                if runner:
                    return runner

                for widget in qapp.topLevelWidgets():
                    runner = getattr(widget, 'orchestra_runner', None)
                    if runner:
                        return runner
        except Exception:
            pass

        return None

    def _refresh_winws_title(self):
        """Обновляет заголовок панели вывода по текущему методу запуска"""
        if not hasattr(self, "winws_title_label"):
            return

        try:
            exe_name = self._controller.resolve_winws_exe_name(self._get_launch_method())
        except Exception:
            exe_name = "winws.exe"

        self.winws_title_label.setText(
            tr_catalog(
                "page.logs.winws.title_template",
                language=self._ui_language,
                default="Вывод {exe_name}",
            ).format(exe_name=exe_name)
        )

    def _get_running_runner_source(self):
        """
        Возвращает источник активного процесса.

        Returns:
            Tuple[str|None, runner|None] где source:
            - "orchestra" для OrchestraRunner
            - "direct" для StrategyRunner
            - None если процесс не запущен
        """
        return self._controller.get_running_runner_source(
            self._get_launch_method(),
            self._get_orchestra_runner(),
        )

    def _get_runner_pid(self, runner):
        """Возвращает PID для любого типа runner'а"""
        return self._controller.get_runner_pid(runner)

    def _get_orchestra_log_path(self) -> str:
        """
        Возвращает путь к логу оркестратора.

        Приоритет:
        1. Текущий активный лог (если оркестратор запущен)
        2. Последний сохранённый лог из истории
        """
        return self._controller.get_orchestra_log_path(self._get_orchestra_runner())

    def _update_orchestra_indicator(self):
        """Обновляет видимость индикатора режима оркестратора"""
        is_orchestra = self._is_orchestra_mode()
        self.orchestra_mode_container.setVisible(is_orchestra)

    def _prepare_support_from_logs(self):
        try:
            result = self._controller.prepare_support_bundle(
                current_log_file=self.current_log_file,
                orchestra_runner=self._get_orchestra_runner(),
            )

            if result.zip_path:
                log(f"Подготовлен архив поддержки: {result.zip_path}", "INFO")

            status_parts: list[str] = []
            if result.zip_path:
                status_parts.append("ZIP готов")
            if result.copied_to_clipboard:
                status_parts.append("шаблон скопирован")
            if result.discussions_opened:
                status_parts.append("GitHub открыт")
            if result.bundle_folder_opened:
                status_parts.append("папка открыта")

            if status_parts:
                self._send_status_text = " • ".join(status_parts)
                self._send_status_tone = "success"
            else:
                self._send_status_text = "Подготовка завершена"
                self._send_status_tone = "success"
            self._render_send_status_label()

            if InfoBar:
                archive_name = os.path.basename(result.zip_path) if result.zip_path else "архив не создан"
                content = f"Архив: {archive_name}\n"
                content += "Шаблон обращения скопирован в буфер обмена." if result.copied_to_clipboard else "Шаблон не удалось скопировать в буфер обмена."
                InfoBar.success(
                    title="Поддержка подготовлена",
                    content=content,
                    parent=self.window(),
                    duration=5000,
                )
        except Exception as e:
            log(f"Ошибка подготовки обращения из логов: {e}", "ERROR")
            self._send_status_text = "Ошибка подготовки"
            self._send_status_tone = "error"
            self._render_send_status_label()
            if InfoBar:
                InfoBar.warning(
                    title="Ошибка",
                    content=f"Не удалось подготовить обращение:\n{e}",
                    parent=self.window(),
                )
        
    def showEvent(self, event):
        """При показе страницы запускаем мониторинг"""
        super().showEvent(event)

        # Spontaneous showEvent = система восстановила окно (из трея/свёрнутого).
        # Не перезапускаем workers/таймеры при простом восстановлении окна.
        if event.spontaneous():
            return
        if not self._logs_tab_initialized:
            self._logs_tab_initialized = True
            # Делаем тяжелые операции после первого показа страницы, чтобы UI не "подвисал" при переходе.
            QTimer.singleShot(0, lambda: self._refresh_logs_list(run_cleanup=False))
            QTimer.singleShot(0, self._update_stats)
        self._start_tail_worker()
        self._start_winws_output_worker()
        # Таймер для проверки статуса каждые 3 секунды
        self._winws_status_timer.start(3000)

    def hideEvent(self, event):
        """При скрытии страницы останавливаем мониторинг"""
        super().hideEvent(event)
        self._stop_tail_worker()
        self._stop_winws_output_worker()
        self._winws_status_timer.stop()
        
    def _refresh_logs_list(self, *, run_cleanup: bool = True):
        """Обновляет список доступных лог-файлов"""
        # Запускаем анимацию вращения
        self._refresh_spin_active = True
        self._spin_angle = 0
        self._spin_timer.start()
        
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        
        try:
            state = self._controller.list_logs(run_cleanup=run_cleanup)
            if run_cleanup and state.cleanup_deleted > 0:
                log(f"🗑️ Удалено старых логов: {state.cleanup_deleted} из {state.cleanup_total}", "INFO")
            if run_cleanup and state.cleanup_errors:
                log(f"⚠️ Ошибки при удалении логов: {state.cleanup_errors[:3]}", "DEBUG")

            current_index = 0

            for entry in state.entries:
                if entry["is_current"]:
                    current_index = entry["index"]
                self.log_combo.addItem(entry["display"], userData=entry["path"])
            
            self.log_combo.setCurrentIndex(current_index)
            
        except Exception as e:
            log(f"Ошибка обновления списка логов: {e}", "ERROR")
        finally:
            self.log_combo.blockSignals(False)
            # Останавливаем анимацию через небольшую задержку для визуального эффекта
            QTimer.singleShot(500, self._stop_refresh_animation)
    
    def _stop_refresh_animation(self):
        """Останавливает анимацию кнопки обновления"""
        self._refresh_spin_active = False
        self._spin_timer.stop()
        self.refresh_btn.setIcon(self._refresh_icon_normal)

    def _on_spin_tick(self):
        """Вращает иконку обновления через QTransform (работает с ToolButton)."""
        self._spin_angle = (self._spin_angle + 12) % 360
        try:
            tokens = get_theme_tokens()
            src = qta.icon('fa5s.sync-alt', color=tokens.accent_hex).pixmap(22, 22)
            dst = QPixmap(22, 22)
            dst.fill(Qt.GlobalColor.transparent)
            painter = QPainter(dst)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            t = QTransform().translate(11, 11).rotate(self._spin_angle).translate(-11, -11)
            painter.setTransform(t)
            painter.drawPixmap(0, 0, src)
            painter.end()
            self.refresh_btn.setIcon(QIcon(dst))
        except Exception:
            pass
            
    def _on_log_selected(self, index):
        """Обработчик выбора лог-файла"""
        if index < 0:
            return
            
        log_path = self.log_combo.itemData(index)
        if log_path and log_path != self.current_log_file:
            self.current_log_file = log_path
            self._start_tail_worker()
            
    def _start_tail_worker(self):
        """Запускает worker для чтения лога"""
        self._stop_tail_worker()

        if not self.current_log_file or not os.path.exists(self.current_log_file):
            return

        self.log_text.clear()
        self.info_label.setText(f"📄 {os.path.basename(self.current_log_file)}")

        try:
            self._thread = QThread(self)
            # Initial history: limit to recent tail to keep the page snappy on huge logs.
            self._worker = LogTailWorker(
                self.current_log_file,
                poll_interval=0.6,
                initial_chunk_chars=65536,
                initial_max_bytes=1024 * 1024,
            )
            self._worker.moveToThread(self._thread)

            self._thread.started.connect(self._worker.run)
            self._worker.new_lines.connect(self._append_text)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._on_tail_thread_finished)
            self._thread.finished.connect(self._thread.deleteLater)

            self._thread.start()
        except Exception as e:
            log(f"Ошибка запуска log tail worker: {e}", "ERROR")

    def _on_tail_thread_finished(self):
        """Очищает ссылки на thread/worker после завершения, чтобы не дергать удалённые Qt-объекты."""
        self._thread = None
        self._worker = None
            
    def _stop_tail_worker(self, blocking: bool = False):
        """Останавливает worker (неблокирующий по умолчанию)"""
        worker = getattr(self, "_worker", None)
        thread = getattr(self, "_thread", None)

        if worker:
            try:
                worker.stop()
            except RuntimeError:
                # Qt-объект уже удалён
                self._worker = None
                worker = None

        if not thread:
            return

        try:
            running = bool(thread.isRunning())
        except RuntimeError:
            # Qt-объект уже удалён
            self._thread = None
            return

        if not running:
            return

        thread.quit()
        if not blocking:
            return

        # Блокирующий режим только при закрытии приложения
        if not thread.wait(2000):
            log("⚠ Log tail worker не завершился, принудительно завершаем", "WARNING")
            try:
                thread.terminate()
                thread.wait(500)
            except Exception:
                pass

    def _start_winws_output_worker(self):
        """Запускает worker для чтения вывода winws"""
        self._stop_winws_output_worker()
        self._refresh_winws_title()

        source, runner = self._get_running_runner_source()
        if source == "orchestra" and runner:
            # В оркестраторе stdout уже читает OrchestraRunner._read_output,
            # поэтому тут только обновляем статус, без второго reader'а.
            pid = self._get_runner_pid(runner)
            self._set_winws_status("running", f"PID: {pid} | Оркестратор")
            return

        if source != "direct" or not runner:
            self._set_winws_status(
                "neutral",
                tr_catalog("page.logs.winws.status.not_running", language=self._ui_language, default="Процесс не запущен"),
            )
            return

        process = runner.get_process()
        if not process:
            self._set_winws_status(
                "neutral",
                tr_catalog("page.logs.winws.status.not_running", language=self._ui_language, default="Процесс не запущен"),
            )
            return

        # Обновляем статус
        strategy_info = {}
        try:
            get_info = getattr(runner, 'get_current_strategy_info', None)
            if callable(get_info):
                info_value = get_info()
                if isinstance(info_value, dict):
                    strategy_info = info_value
        except Exception:
            pass

        strategy_name = strategy_info.get('name', 'winws')
        # Обрезаем длинные названия стратегий
        if len(strategy_name) > 35:
            strategy_name = strategy_name[:32] + "..."
        pid = strategy_info.get('pid') or self._get_runner_pid(runner)
        self._set_winws_status("running", f"PID: {pid} | {strategy_name}")

        try:
            self._winws_thread = QThread(self)
            self._winws_worker = WinwsOutputWorker()
            self._winws_worker.set_process(process)
            self._winws_worker.moveToThread(self._winws_thread)

            self._winws_thread.started.connect(self._winws_worker.run)
            self._winws_worker.new_output.connect(self._append_winws_output)
            self._winws_worker.process_ended.connect(self._on_winws_process_ended)
            self._winws_worker.finished.connect(self._winws_thread.quit)

            self._winws_thread.start()
        except Exception as e:
            log(f"Ошибка запуска winws output worker: {e}", "ERROR")

    def _stop_winws_output_worker(self, blocking: bool = False):
        """Останавливает worker чтения вывода winws (неблокирующий по умолчанию)"""
        try:
            if self._winws_worker:
                self._winws_worker.stop()
            if self._winws_thread and self._winws_thread.isRunning():
                self._winws_thread.quit()
                if blocking:
                    # Блокирующий режим только при закрытии приложения
                    if not self._winws_thread.wait(2000):
                        log("⚠ Winws output worker не завершился, принудительно завершаем", "WARNING")
                        try:
                            self._winws_thread.terminate()
                            self._winws_thread.wait(500)
                        except:
                            pass
                # Неблокирующий режим - поток остановится сам
        except Exception as e:
            log(f"Ошибка остановки winws output worker: {e}", "DEBUG")

    def _append_winws_output(self, text: str, stream_type: str):
        """Добавляет вывод winws в текстовое поле"""
        self._winws_lines_count += 1

        # Экранируем HTML-символы
        safe_text = html.escape(text)

        # Форматируем текст в зависимости от потока
        if stream_type == 'stderr':
            # stderr показываем красным
            formatted = f'<span style="color: {self._winws_stderr_color};">{safe_text}</span>'
        else:
            # stdout показываем зелёным
            formatted = f'<span style="color: {self._winws_stdout_color};">{safe_text}</span>'

        self.winws_text.append(formatted)

        # Автопрокрутка
        scrollbar = self.winws_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_winws_process_ended(self, exit_code: int):
        """Обработчик завершения процесса winws"""
        if exit_code == 0:
            self._set_winws_status(
                "neutral",
                tr_catalog(
                    "page.logs.winws.status.ended_template",
                    language=self._ui_language,
                    default="Процесс завершён (код: {code})",
                ).format(code=exit_code),
            )
        else:
            self._set_winws_status(
                "error",
                tr_catalog(
                    "page.logs.winws.status.ended_error_template",
                    language=self._ui_language,
                    default="Процесс завершён с ошибкой (код: {code})",
                ).format(code=exit_code),
            )

    def _update_winws_status(self):
        """Периодически проверяет статус процесса winws"""
        self._refresh_winws_title()
        source, runner = self._get_running_runner_source()

        if source == "orchestra" and runner:
            # Для оркестратора всегда останавливаем worker чтения stdout,
            # чтобы не конкурировать с внутренним reader'ом orchestra_runner.
            if self._winws_thread and self._winws_thread.isRunning():
                self._stop_winws_output_worker()

            pid = self._get_runner_pid(runner)
            self._set_winws_status("running", f"PID: {pid} | Оркестратор")
            return

        if source == "direct" and runner:
            # Если worker не работает, запускаем его
            if not self._winws_thread or not self._winws_thread.isRunning():
                self._start_winws_output_worker()
            return

        # Процесс не запущен - обновляем статус если worker не работает
        if not self._winws_thread or not self._winws_thread.isRunning():
            self._set_winws_status(
                "neutral",
                tr_catalog("page.logs.winws.status.not_running", language=self._ui_language, default="Процесс не запущен"),
            )

    def _clear_winws_output(self):
        """Очищает поле вывода winws"""
        self.winws_text.clear()
        self._winws_lines_count = 0
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.winws_cleared",
                language=self._ui_language,
                default="🧹 Вывод winws очищен",
            )
        )

    def _append_text(self, text: str):
        """Добавляет текст в лог"""
        if not text:
            return

        # Быстро вставляем текст одним куском (append по строкам сильно тормозит на больших логах).
        try:
            scrollbar = self.log_text.verticalScrollBar()
            was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 2)
        except Exception:
            was_at_bottom = True

        try:
            self.log_text.setUpdatesEnabled(False)
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(text)
            self.log_text.setTextCursor(cursor)
        finally:
            try:
                self.log_text.setUpdatesEnabled(True)
            except Exception:
                pass

        # Проверяем на ошибки только по новым строкам
        try:
            for line in text.splitlines():
                clean_line = (line or "").rstrip()
                if not clean_line:
                    continue
                if self._error_pattern.search(clean_line) and not self._exclude_pattern.search(clean_line):
                    self._add_error(clean_line)
        except Exception:
            pass

        if was_at_bottom:
            try:
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except Exception:
                pass
        
    def _copy_log(self):
        """Копирует содержимое лога в буфер"""
        text = self.log_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.info_label.setText(
                tr_catalog(
                    "page.logs.info.copied",
                    language=self._ui_language,
                    default="✅ Скопировано в буфер обмена",
                )
            )
        else:
            self.info_label.setText(
                tr_catalog(
                    "page.logs.info.empty",
                    language=self._ui_language,
                    default="⚠️ Лог пуст",
                )
            )
            
    def _clear_view(self):
        """Очищает вид (не файл)"""
        self.log_text.clear()
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.view_cleared",
                language=self._ui_language,
                default="🧹 Вид очищен",
            )
        )
        
    def _open_folder(self):
        """Открывает папку с логами"""
        try:
            self._controller.open_logs_folder()
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            
    def _update_stats(self):
        """Обновляет статистику"""
        try:
            stats = self._controller.build_stats()

            self.stats_label.setText(
                tr_catalog(
                    "page.logs.stats.template",
                    language=self._ui_language,
                    default="📊 Логи: {logs} (макс {max_logs}) | 🔧 Debug: {debug} (макс {max_debug}) | 💾 Размер: {size:.2f} MB",
                ).format(
                    logs=stats.app_logs,
                    max_logs=stats.max_logs,
                    debug=stats.debug_logs,
                    max_debug=stats.max_debug_logs,
                    size=stats.total_size_mb,
                )
            )
        except Exception as e:
            self.stats_label.setText(f"Ошибка статистики: {e}")

    def _update_errors_text_height(self):
        """Подстраивает высоту панели ошибок под содержимое."""
        if not hasattr(self, "errors_text") or self.errors_text is None:
            return

        try:
            is_empty = not bool(self.errors_text.toPlainText().strip())
        except Exception:
            is_empty = True

        if is_empty:
            target_height = self._errors_text_min_height
        else:
            try:
                document_height = int(self.errors_text.document().size().height())
            except Exception:
                document_height = self._errors_text_min_height

            frame_height = int(self.errors_text.frameWidth()) * 2
            content_padding = 16
            target_height = document_height + frame_height + content_padding
            target_height = max(self._errors_text_min_height, min(self._errors_text_max_height, target_height))

        if self.errors_text.height() != target_height:
            self.errors_text.setFixedHeight(target_height)
            
    def _add_error(self, text: str):
        """Добавляет ошибку в панель ошибок"""
        self._errors_count += 1
        self.errors_count_label.setText(
            tr_catalog("page.logs.errors.count", language=self._ui_language, default="Ошибок: {count}").format(
                count=self._errors_count
            )
        )
        
        # Добавляем текст с временной меткой
        self.errors_text.append(text)
        self._update_errors_text_height()
        
        # Автопрокрутка
        scrollbar = self.errors_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _clear_errors(self):
        """Очищает панель ошибок"""
        self.errors_text.clear()
        self._errors_count = 0
        self.errors_count_label.setText(
            tr_catalog("page.logs.errors.count", language=self._ui_language, default="Ошибок: {count}").format(count=0)
        )
        self._update_errors_text_height()
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.errors_cleared",
                language=self._ui_language,
                default="🧹 Ошибки очищены",
            )
        )
            
    def cleanup(self):
        """Очистка при закрытии - блокирующий режим"""
        self._stop_tail_worker(blocking=True)
        self._stop_winws_output_worker(blocking=True)
