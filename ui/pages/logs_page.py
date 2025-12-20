# ui/pages/logs_page.py
"""Страница просмотра логов в реальном времени"""

from PyQt6.QtCore import Qt, QThread, QTimer, QVariantAnimation, QEasingCurve, pyqtSignal, QObject, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QApplication, QMessageBox,
    QSplitter, QTextEdit, QStackedWidget, QLineEdit, QFrame
)
from PyQt6.QtGui import QFont, QColor, QTextCharFormat
import qtawesome as qta
import os
import glob
import re
import threading
import queue
import html

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log, global_logger, LOG_FILE, cleanup_old_logs
from log_tail import LogTailWorker
from config import LOGS_FOLDER, MAX_LOG_FILES, MAX_DEBUG_LOG_FILES
from strategy_menu.strategy_runner import get_current_runner

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
                    elif not self._running:
                        break

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
                QThread.msleep(100)

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
        super().__init__("Логи", "Просмотр логов приложения в реальном времени", parent)
        
        # Отключаем горизонтальную прокрутку страницы
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._thread = None
        self._worker = None
        self.current_log_file = getattr(global_logger, "log_file", LOG_FILE)
        self._error_pattern = re.compile('|'.join(ERROR_PATTERNS))
        self._exclude_pattern = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

        # Winws output worker
        self._winws_thread = None
        self._winws_worker = None
        self._winws_lines_count = 0

        # Таймер для обновления статуса winws
        self._winws_status_timer = QTimer(self)
        self._winws_status_timer.timeout.connect(self._update_winws_status)

        self._build_ui()
        
    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # Переключатель табов (ЛОГИ / ОТПРАВКА)
        # ═══════════════════════════════════════════════════════════
        tabs_container = QWidget()
        tabs_layout = QHBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 8)
        tabs_layout.setSpacing(0)

        # Стиль для кнопок табов
        tab_style_active = """
            QPushButton {
                background-color: transparent;
                color: #60cdff;
                border: none;
                border-bottom: 2px solid #60cdff;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
        """
        tab_style_inactive = """
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                color: rgba(255, 255, 255, 0.8);
            }
        """

        self.tab_logs_btn = QPushButton()
        self.tab_logs_btn.setIcon(qta.icon('fa5s.file-alt', color='#60cdff'))
        self.tab_logs_btn.setText(" ЛОГИ")
        self.tab_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_logs_btn.setStyleSheet(tab_style_active)
        self.tab_logs_btn.clicked.connect(lambda: self._switch_tab(0))
        tabs_layout.addWidget(self.tab_logs_btn)

        self.tab_send_btn = QPushButton()
        self.tab_send_btn.setIcon(qta.icon('fa5s.paper-plane', color='#888888'))
        self.tab_send_btn.setText(" ОТПРАВКА")
        self.tab_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_send_btn.setStyleSheet(tab_style_inactive)
        self.tab_send_btn.clicked.connect(lambda: self._switch_tab(1))
        tabs_layout.addWidget(self.tab_send_btn)

        tabs_layout.addStretch()

        # Сохраняем стили для переключения
        self._tab_style_active = tab_style_active
        self._tab_style_inactive = tab_style_inactive

        self.add_widget(tabs_container)

        # ═══════════════════════════════════════════════════════════
        # Стек страниц (ЛОГИ / ОТПРАВКА)
        # ═══════════════════════════════════════════════════════════
        self.stacked_widget = QStackedWidget()

        # Страница 1: Логи
        logs_page = QWidget()
        logs_layout = QVBoxLayout(logs_page)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(16)

        self._build_logs_tab(logs_layout)

        # Страница 2: Отправка
        send_page = QWidget()
        send_layout = QVBoxLayout(send_page)
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(16)

        self._build_send_tab(send_layout)

        self.stacked_widget.addWidget(logs_page)
        self.stacked_widget.addWidget(send_page)

        self.add_widget(self.stacked_widget)

    def _switch_tab(self, index: int):
        """Переключает между табами"""
        self.stacked_widget.setCurrentIndex(index)

        if index == 0:
            self.tab_logs_btn.setStyleSheet(self._tab_style_active)
            self.tab_logs_btn.setIcon(qta.icon('fa5s.file-alt', color='#60cdff'))
            self.tab_send_btn.setStyleSheet(self._tab_style_inactive)
            self.tab_send_btn.setIcon(qta.icon('fa5s.paper-plane', color='#888888'))
        else:
            self.tab_logs_btn.setStyleSheet(self._tab_style_inactive)
            self.tab_logs_btn.setIcon(qta.icon('fa5s.file-alt', color='#888888'))
            self.tab_send_btn.setStyleSheet(self._tab_style_active)
            self.tab_send_btn.setIcon(qta.icon('fa5s.paper-plane', color='#60cdff'))
            # Обновляем видимость индикатора оркестратора
            self._update_orchestra_indicator()

    def _build_logs_tab(self, parent_layout):
        """Строит вкладку с логами"""
        # ═══════════════════════════════════════════════════════════
        # Панель управления (выбор файла + кнопки в 2 ряда)
        # ═══════════════════════════════════════════════════════════
        controls_card = SettingsCard("Управление логами")
        controls_main = QVBoxLayout()
        controls_main.setSpacing(12)
        
        # Ряд 1: выбор файла + кнопка обновления
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        self.log_combo = QComboBox()
        self.log_combo.setMinimumWidth(350)
        self.log_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 12px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border-color: rgba(255, 255, 255, 0.15);
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(45, 45, 48, 0.95);
                color: rgba(255, 255, 255, 0.8);
                selection-background-color: rgba(96, 205, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: rgba(96, 205, 255, 0.15);
                color: #60cdff;
            }
        """)
        self.log_combo.currentIndexChanged.connect(self._on_log_selected)
        row1.addWidget(self.log_combo, 1)
        
        self.refresh_btn = QPushButton()
        self._refresh_icon_normal = qta.icon('fa5s.sync-alt', color='#ffffff')
        self._refresh_spin_animation = qta.Spin(self.refresh_btn, interval=10, step=8)
        self._refresh_icon_spinning = qta.icon('fa5s.sync-alt', color='#60cdff', animation=self._refresh_spin_animation)
        self.refresh_btn.setIcon(self._refresh_icon_normal)
        self.refresh_btn.setFixedSize(36, 36)
        self.refresh_btn.setToolTip("Обновить список файлов")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.refresh_btn.clicked.connect(self._refresh_logs_list)
        row1.addWidget(self.refresh_btn)
        
        controls_main.addLayout(row1)
        
        # Ряд 2: кнопки действий
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        
        self.copy_btn = ActionButton("Копировать", "fa5s.copy")
        self.copy_btn.clicked.connect(self._copy_log)
        row2.addWidget(self.copy_btn)
        
        self.clear_btn = ActionButton("Очистить", "fa5s.eraser")
        self.clear_btn.clicked.connect(self._clear_view)
        row2.addWidget(self.clear_btn)
        
        self.folder_btn = ActionButton("Папка", "fa5s.folder-open")
        self.folder_btn.clicked.connect(self._open_folder)
        row2.addWidget(self.folder_btn)

        row2.addStretch()
        
        # Информационная строка
        self.info_label = QLabel()
        self.info_label.setStyleSheet("""
            QLabel {
                color: #60cdff;
                font-size: 11px;
            }
        """)
        row2.addWidget(self.info_label)
        
        controls_main.addLayout(row2)
        
        controls_card.add_layout(controls_main)
        parent_layout.addWidget(controls_card)

        # ═══════════════════════════════════════════════════════════
        # Область логов
        # ═══════════════════════════════════════════════════════════
        log_card = SettingsCard("Содержимое")
        log_layout = QVBoxLayout()
        
        # Текстовое поле для логов (блокирует провал прокрутки)
        self.log_text = ScrollBlockingTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(260)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
            }
            QScrollBar:vertical {
                background: #2d2d30;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #5a5a5a;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6a6a6a;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        # Статистика внизу лог-карточки
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 10px;
                padding-top: 4px;
            }
        """)
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
        warning_icon.setPixmap(qta.icon('fa5s.exclamation-triangle', color='#ff6b6b').pixmap(16, 16))
        errors_header.addWidget(warning_icon)
        
        # Заголовок
        errors_title = QLabel("Ошибки и предупреждения")
        errors_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
        """)
        errors_header.addWidget(errors_title)
        errors_header.addSpacing(16)
        
        self.errors_count_label = QLabel("Ошибок: 0")
        self.errors_count_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        errors_header.addWidget(self.errors_count_label)
        
        errors_header.addStretch()
        
        self.clear_errors_btn = ActionButton("Очистить", "fa5s.trash")
        self.clear_errors_btn.clicked.connect(self._clear_errors)
        errors_header.addWidget(self.clear_errors_btn)
        
        errors_layout.addLayout(errors_header)
        
        # Текстовое поле для ошибок (блокирует провал прокрутки)
        self.errors_text = ScrollBlockingTextEdit()
        self.errors_text.setReadOnly(True)
        self.errors_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.errors_text.setFont(QFont("Consolas", 9))
        self.errors_text.setFixedHeight(100)
        self.errors_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a1a1a;
                color: #ff8888;
                border: 1px solid #5a2a2a;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background: #2d2d30;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #5a3a3a;
                border-radius: 5px;
                min-height: 30px;
            }
        """)
        errors_layout.addWidget(self.errors_text)

        errors_card.add_layout(errors_layout)
        parent_layout.addWidget(errors_card)

        # ═══════════════════════════════════════════════════════════
        # Панель вывода winws.exe
        # ═══════════════════════════════════════════════════════════
        winws_card = SettingsCard()
        winws_layout = QVBoxLayout()

        # Заголовок с иконкой
        winws_header = QHBoxLayout()

        # Иконка терминала
        terminal_icon = QLabel()
        terminal_icon.setPixmap(qta.icon('fa5s.terminal', color='#60cdff').pixmap(16, 16))
        winws_header.addWidget(terminal_icon)

        # Заголовок
        winws_title = QLabel("Вывод winws.exe")
        winws_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
        """)
        winws_header.addWidget(winws_title)
        winws_header.addSpacing(16)

        # Статус процесса
        self.winws_status_label = QLabel("Процесс не запущен")
        self.winws_status_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
            }
        """)
        winws_header.addWidget(self.winws_status_label)

        winws_header.addStretch()

        # Кнопка очистки
        self.clear_winws_btn = ActionButton("Очистить", "fa5s.trash")
        self.clear_winws_btn.clicked.connect(self._clear_winws_output)
        winws_header.addWidget(self.clear_winws_btn)

        winws_layout.addLayout(winws_header)

        # Текстовое поле для вывода winws
        self.winws_text = ScrollBlockingTextEdit()
        self.winws_text.setReadOnly(True)
        self.winws_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.winws_text.setFont(QFont("Consolas", 9))
        self.winws_text.setFixedHeight(150)
        self.winws_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                color: #00ff88;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background: #2d2d30;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #4a4a6a;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5a5a7a;
            }
        """)
        winws_layout.addWidget(self.winws_text)

        winws_card.add_layout(winws_layout)
        parent_layout.addWidget(winws_card)

        # Счётчик ошибок
        self._errors_count = 0

        # Инициализация
        self._refresh_logs_list()
        self._update_stats()

    def _build_send_tab(self, parent_layout):
        """Строит вкладку отправки лога"""
        import time
        import platform

        # ═══════════════════════════════════════════════════════════
        # Форма отправки
        # ═══════════════════════════════════════════════════════════
        send_card = SettingsCard("Отправка лога в техподдержку")
        send_layout = QVBoxLayout()
        send_layout.setSpacing(16)

        # Индикатор режима оркестратора (скрыт по умолчанию)
        self.orchestra_mode_container = QWidget()
        orchestra_layout = QHBoxLayout(self.orchestra_mode_container)
        orchestra_layout.setContentsMargins(12, 8, 12, 8)
        orchestra_layout.setSpacing(8)

        orchestra_icon = QLabel()
        orchestra_icon.setPixmap(qta.icon('fa5s.brain', color='#a855f7').pixmap(16, 16))
        orchestra_layout.addWidget(orchestra_icon)

        orchestra_text = QLabel("Режим оркестратора активен — будут отправлены 2 файла")
        orchestra_text.setStyleSheet("color: #a855f7; font-size: 12px; font-weight: 600; background: transparent;")
        orchestra_layout.addWidget(orchestra_text)
        orchestra_layout.addStretch()

        self.orchestra_mode_container.setStyleSheet("""
            QWidget {
                background-color: rgba(168, 85, 247, 0.15);
                border-radius: 8px;
            }
        """)
        self.orchestra_mode_container.setVisible(False)
        send_layout.addWidget(self.orchestra_mode_container)

        # Описание
        desc_label = QLabel(
            "Опишите проблему и оставьте контакты для обратной связи (необязательно):"
        )
        desc_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px;")
        desc_label.setWordWrap(True)
        send_layout.addWidget(desc_label)

        # Поле "Описание проблемы"
        problem_header = QLabel("Описание проблемы:")
        problem_header.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 600;")
        send_layout.addWidget(problem_header)

        self.problem_text = QTextEdit()
        self.problem_text.setPlaceholderText(
            "Опишите, что не работает или какая ошибка возникает."
        )
        self.problem_text.setMaximumHeight(150)
        self.problem_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid #60cdff;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: #60cdff;
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        send_layout.addWidget(self.problem_text)

        # Поле "Telegram для связи"
        tg_header = QLabel("Telegram для связи (необязательно):")
        tg_header.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 600;")
        send_layout.addWidget(tg_header)

        self.tg_contact = QLineEdit()
        self.tg_contact.setPlaceholderText("@username или ссылка на профиль")
        self.tg_contact.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #60cdff;
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        send_layout.addWidget(self.tg_contact)

        # Информация
        info_container = QWidget()
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 8, 0, 8)

        info_icon = QLabel()
        info_icon.setPixmap(qta.icon('fa5s.info-circle', color='#60cdff').pixmap(14, 14))
        info_layout.addWidget(info_icon)

        info_text = QLabel(
            "Ваши данные будут отправлены только в канал техподдержки.\n"
            "Лог файл поможет разработчикам найти и исправить проблему."
        )
        info_text.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text, 1)

        send_layout.addWidget(info_container)

        # Кнопка отправки
        buttons_row = QHBoxLayout()

        self.send_log_btn = ActionButton("Отправить лог", "fa5s.paper-plane")
        self.send_log_btn.clicked.connect(self._do_send_log)
        buttons_row.addWidget(self.send_log_btn)

        buttons_row.addStretch()

        # Статус отправки
        self.send_status_label = QLabel()
        self.send_status_label.setStyleSheet("color: #60cdff; font-size: 11px;")
        buttons_row.addWidget(self.send_status_label)

        send_layout.addLayout(buttons_row)

        send_card.add_layout(send_layout)
        parent_layout.addWidget(send_card)

        # Растяжка чтобы форма была вверху
        parent_layout.addStretch()

    def _is_orchestra_mode(self) -> bool:
        """Проверяет, активен ли режим оркестратора"""
        try:
            from strategy_menu import get_strategy_launch_method
            return get_strategy_launch_method() == "orchestra"
        except Exception:
            return False

    def _get_orchestra_log_path(self) -> str:
        """
        Возвращает путь к логу оркестратора.

        Приоритет:
        1. Текущий активный лог (если оркестратор запущен)
        2. Последний сохранённый лог из истории
        """
        try:
            app = QApplication.instance()
            if app and hasattr(app, 'activeWindow'):
                main_window = app.activeWindow()
                if main_window and hasattr(main_window, 'orchestra_runner') and main_window.orchestra_runner:
                    runner = main_window.orchestra_runner

                    # 1. Пробуем текущий активный лог
                    if runner.current_log_id and runner.debug_log_path:
                        if os.path.exists(runner.debug_log_path):
                            return runner.debug_log_path

                    # 2. Если текущего нет - берём последний из истории
                    logs = runner.get_log_history()
                    if logs:
                        # Логи отсортированы по дате (новые первые)
                        latest_log = logs[0]
                        log_path = os.path.join(LOGS_FOLDER, latest_log['filename'])
                        if os.path.exists(log_path):
                            return log_path

        except Exception as e:
            log(f"Ошибка получения пути лога оркестратора: {e}", "DEBUG")

        # 3. Fallback: ищем любой orchestra_*.log в папке логов
        try:
            import glob as glob_module
            pattern = os.path.join(LOGS_FOLDER, "orchestra_*.log")
            log(f"Поиск лога оркестратора (fallback): {pattern}", "DEBUG")
            files = sorted(glob_module.glob(pattern), key=os.path.getmtime, reverse=True)
            log(f"Найдено файлов: {len(files)}", "DEBUG")
            if files:
                log(f"Найден лог оркестратора (fallback): {os.path.basename(files[0])}", "DEBUG")
                return files[0]
        except Exception as e:
            log(f"Ошибка fallback поиска лога: {e}", "DEBUG")

        log("Лог оркестратора не найден для отправки", "WARNING")
        return None

    def _update_orchestra_indicator(self):
        """Обновляет видимость индикатора режима оркестратора"""
        is_orchestra = self._is_orchestra_mode()
        self.orchestra_mode_container.setVisible(is_orchestra)

    def _do_send_log(self):
        """Отправляет лог в Telegram (из вкладки отправки)"""
        import time
        import platform

        try:
            settings = QSettings("Zapret2", "GUI")
            now = time.time()
            interval = 1 * 60  # 1 минута

            # Проверяем интервал
            last = settings.value("last_full_log_send", 0.0, type=float)

            if now - last < interval:
                remaining = int((interval - (now - last)) // 60) + 1
                QMessageBox.information(self, "Отправка логов",
                    f"Лог отправлялся недавно.\n"
                    f"Следующая отправка возможна через {remaining} мин.")
                return

            # Проверяем настройки бота
            from tgram.tg_log_bot import check_bot_connection

            if not check_bot_connection():
                QMessageBox.warning(self, "Бот не настроен",
                    "Бот для отправки логов не настроен или недоступен.\n\n"
                    "Для настройки обратитесь к разработчику.")
                return

            # Получаем данные из формы
            problem = self.problem_text.toPlainText().strip()
            telegram = self.tg_contact.text().strip()

            # Запоминаем время отправки
            settings.setValue("last_full_log_send", now)

            # Подготовка к отправке
            from tgram.tg_log_full import TgSendWorker
            from tgram.tg_log_delta import get_client_id
            from config.build_info import APP_VERSION

            # Используем текущий лог файл
            LOG_PATH = global_logger.log_file if hasattr(global_logger, 'log_file') else None

            if not LOG_PATH or not os.path.exists(LOG_PATH):
                QMessageBox.warning(self, "Ошибка", "Файл лога не найден")
                return

            # Проверяем режим оркестратора
            is_orchestra = self._is_orchestra_mode()
            orchestra_log_path = self._get_orchestra_log_path() if is_orchestra else None

            # Формируем подпись
            log_filename = os.path.basename(LOG_PATH)

            caption = f"📋 Ручная отправка лога\n"
            if is_orchestra:
                caption += f"🧠 Режим: Оркестратор\n"
            caption += f"📁 Файл: {log_filename}\n"
            caption += f"Zapret2 v{APP_VERSION}\n"
            caption += f"ID: {get_client_id()}\n"
            caption += f"Host: {platform.node()}\n"
            caption += f"Time: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"

            if problem:
                caption += f"\n🔴 Проблема:\n{problem}\n"

            if telegram:
                caption += f"\n📱 Telegram: {telegram}\n"

            self.send_log_btn.setEnabled(False)

            # Если режим оркестратора - отправляем 2 файла
            if is_orchestra and orchestra_log_path:
                self.send_status_label.setText("📤 Отправка 2 файлов (оркестратор)...")
                self._send_orchestra_logs(LOG_PATH, orchestra_log_path, caption, problem, telegram)
            else:
                self.send_status_label.setText("📤 Отправка лога...")
                self._send_single_log(LOG_PATH, caption)

        except Exception as e:
            log(f"Ошибка отправки лога: {e}", "ERROR")
            self.send_log_btn.setEnabled(True)
            self.send_status_label.setText("❌ Ошибка")
            QMessageBox.warning(self, "Ошибка", f"Не удалось отправить лог:\n{e}")

    def _send_single_log(self, log_path: str, caption: str):
        """Отправляет один файл лога"""
        from tgram.tg_log_full import TgSendWorker

        self._send_thread = QThread(self)
        self._send_worker = TgSendWorker(log_path, caption, use_log_bot=True)
        self._send_worker.moveToThread(self._send_thread)
        self._send_thread.started.connect(self._send_worker.run)

        def _on_done(ok: bool, extra_wait: float, error_msg: str = ""):
            self.send_log_btn.setEnabled(True)

            if ok:
                self.send_status_label.setText("✅ Лог отправлен!")
                self.send_status_label.setStyleSheet("color: #4ade80; font-size: 11px;")
                self.problem_text.clear()
                self.tg_contact.clear()
            else:
                short_error = error_msg[:50] + "..." if error_msg and len(error_msg) > 50 else error_msg
                self.send_status_label.setText(f"❌ {short_error or 'Ошибка отправки'}")
                self.send_status_label.setStyleSheet("color: #f87171; font-size: 11px;")
                if extra_wait > 0:
                    QMessageBox.warning(self, "Слишком часто",
                        f"Слишком частые запросы.\n"
                        f"Повторите через {int(extra_wait/60)} минут.")
                elif error_msg:
                    QMessageBox.warning(self, "Ошибка отправки",
                        f"Не удалось отправить лог.\n\n"
                        f"Причина: {error_msg}")
                else:
                    QMessageBox.warning(self, "Ошибка",
                        "Не удалось отправить лог.\n\n"
                        "Проверьте подключение к интернету.")

            self._send_worker.deleteLater()
            self._send_thread.quit()
            self._send_thread.wait()

        self._send_worker.finished.connect(_on_done)
        self._send_thread.start()

    def _send_orchestra_logs(self, app_log_path: str, orchestra_log_path: str, caption: str, problem: str, telegram: str):
        """Отправляет два файла: лог приложения и лог оркестратора в топик 43927"""
        import time
        import platform
        from tgram.tg_log_full import TgSendWorker
        from tgram.tg_log_delta import get_client_id
        from config.build_info import APP_VERSION

        # Топик для логов оркестратора
        ORCHESTRA_TOPIC_ID = 43927

        # Счётчик успешных отправок
        self._orchestra_send_success = 0
        self._orchestra_send_total = 2
        self._orchestra_errors = []

        def _check_complete():
            """Проверяет завершение отправки всех файлов"""
            if self._orchestra_send_success + len(self._orchestra_errors) >= self._orchestra_send_total:
                self.send_log_btn.setEnabled(True)

                if self._orchestra_send_success == self._orchestra_send_total:
                    self.send_status_label.setText("✅ 2 файла отправлены!")
                    self.send_status_label.setStyleSheet("color: #4ade80; font-size: 11px;")
                    self.problem_text.clear()
                    self.tg_contact.clear()
                elif self._orchestra_send_success > 0:
                    self.send_status_label.setText(f"⚠️ Отправлено {self._orchestra_send_success} из 2")
                    self.send_status_label.setStyleSheet("color: #fbbf24; font-size: 11px;")
                else:
                    self.send_status_label.setText("❌ Ошибка отправки")
                    self.send_status_label.setStyleSheet("color: #f87171; font-size: 11px;")
                    if self._orchestra_errors:
                        QMessageBox.warning(self, "Ошибка отправки",
                            f"Не удалось отправить логи.\n\n"
                            f"Ошибки:\n" + "\n".join(self._orchestra_errors[:3]))

        # 1. Отправляем лог оркестратора (сырой debug) в топик 43927
        orchestra_filename = os.path.basename(orchestra_log_path)
        orchestra_caption = f"🧠 Лог оркестратора (debug)\n"
        orchestra_caption += f"📁 Файл: {orchestra_filename}\n"
        orchestra_caption += f"Zapret2 v{APP_VERSION}\n"
        orchestra_caption += f"ID: {get_client_id()}\n"
        orchestra_caption += f"Host: {platform.node()}\n"
        orchestra_caption += f"Time: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        if problem:
            orchestra_caption += f"\n🔴 Проблема:\n{problem}\n"
        if telegram:
            orchestra_caption += f"\n📱 Telegram: {telegram}\n"

        self._send_thread1 = QThread(self)
        self._send_worker1 = TgSendWorker(orchestra_log_path, orchestra_caption, use_log_bot=True, topic_id=ORCHESTRA_TOPIC_ID)
        self._send_worker1.moveToThread(self._send_thread1)
        self._send_thread1.started.connect(self._send_worker1.run)

        def _on_orchestra_done(ok: bool, extra_wait: float, error_msg: str = ""):
            if ok:
                self._orchestra_send_success += 1
            else:
                self._orchestra_errors.append(f"Лог оркестратора: {error_msg or 'неизвестная ошибка'}")

            self._send_worker1.deleteLater()
            self._send_thread1.quit()
            self._send_thread1.wait()
            _check_complete()

        self._send_worker1.finished.connect(_on_orchestra_done)
        self._send_thread1.start()

        # 2. Отправляем лог приложения в тот же топик 43927
        app_filename = os.path.basename(app_log_path)
        app_caption = f"📋 Лог приложения\n"
        app_caption += f"🧠 Режим: Оркестратор (файл 2/2)\n"
        app_caption += f"📁 Файл: {app_filename}\n"
        app_caption += f"Zapret2 v{APP_VERSION}\n"
        app_caption += f"ID: {get_client_id()}\n"
        app_caption += f"Host: {platform.node()}\n"
        app_caption += f"Time: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        if problem:
            app_caption += f"\n🔴 Проблема:\n{problem}\n"
        if telegram:
            app_caption += f"\n📱 Telegram: {telegram}\n"

        self._send_thread2 = QThread(self)
        self._send_worker2 = TgSendWorker(app_log_path, app_caption, use_log_bot=True, topic_id=ORCHESTRA_TOPIC_ID)
        self._send_worker2.moveToThread(self._send_thread2)
        self._send_thread2.started.connect(self._send_worker2.run)

        def _on_app_done(ok: bool, extra_wait: float, error_msg: str = ""):
            if ok:
                self._orchestra_send_success += 1
            else:
                self._orchestra_errors.append(f"Лог приложения: {error_msg or 'неизвестная ошибка'}")

            self._send_worker2.deleteLater()
            self._send_thread2.quit()
            self._send_thread2.wait()
            _check_complete()

        self._send_worker2.finished.connect(_on_app_done)
        self._send_thread2.start()
        
    def showEvent(self, event):
        """При показе страницы запускаем мониторинг"""
        super().showEvent(event)
        self._start_tail_worker()
        self._start_winws_output_worker()
        # Таймер для проверки статуса каждые 2 секунды
        self._winws_status_timer.start(2000)

    def hideEvent(self, event):
        """При скрытии страницы останавливаем мониторинг"""
        super().hideEvent(event)
        self._stop_tail_worker()
        self._stop_winws_output_worker()
        self._winws_status_timer.stop()
        
    def _refresh_logs_list(self):
        """Обновляет список доступных лог-файлов"""
        # Запускаем анимацию вращения
        self.refresh_btn.setIcon(self._refresh_icon_spinning)
        self._refresh_spin_animation.start()
        
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        
        try:
            # Очищаем старые логи перед обновлением списка
            deleted, errors, total = cleanup_old_logs(LOGS_FOLDER, MAX_LOG_FILES)
            if deleted > 0:
                log(f"🗑️ Удалено старых логов: {deleted} из {total}", "INFO")
            if errors:
                log(f"⚠️ Ошибки при удалении логов: {errors[:3]}", "DEBUG")
            
            # Получаем оба формата логов
            log_files = []
            log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt")))
            log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
            log_files.sort(key=os.path.getmtime, reverse=True)
            
            current_log = getattr(global_logger, "log_file", LOG_FILE)
            current_index = 0
            
            for i, log_path in enumerate(log_files):
                filename = os.path.basename(log_path)
                size_kb = os.path.getsize(log_path) / 1024
                
                # Помечаем текущий лог
                if log_path == current_log:
                    display = f"📍 {filename} ({size_kb:.1f} KB) - ТЕКУЩИЙ"
                    current_index = i
                else:
                    display = f"{filename} ({size_kb:.1f} KB)"
                
                self.log_combo.addItem(display, log_path)
            
            self.log_combo.setCurrentIndex(current_index)
            
        except Exception as e:
            log(f"Ошибка обновления списка логов: {e}", "ERROR")
        finally:
            self.log_combo.blockSignals(False)
            # Останавливаем анимацию через небольшую задержку для визуального эффекта
            QTimer.singleShot(500, self._stop_refresh_animation)
    
    def _stop_refresh_animation(self):
        """Останавливает анимацию кнопки обновления"""
        self._refresh_spin_animation.stop()
        self.refresh_btn.setIcon(self._refresh_icon_normal)
            
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
            self._worker = LogTailWorker(self.current_log_file)
            self._worker.moveToThread(self._thread)
            
            self._thread.started.connect(self._worker.run)
            self._worker.new_lines.connect(self._append_text)
            self._worker.finished.connect(self._thread.quit)
            
            self._thread.start()
        except Exception as e:
            log(f"Ошибка запуска log tail worker: {e}", "ERROR")
            
    def _stop_tail_worker(self, blocking: bool = False):
        """Останавливает worker (неблокирующий по умолчанию)"""
        try:
            if self._worker:
                self._worker.stop()
            if self._thread and self._thread.isRunning():
                self._thread.quit()
                if blocking:
                    # Блокирующий режим только при закрытии приложения
                    if not self._thread.wait(2000):
                        log("⚠ Log tail worker не завершился, принудительно завершаем", "WARNING")
                        try:
                            self._thread.terminate()
                            self._thread.wait(500)
                        except:
                            pass
                # Неблокирующий режим - поток остановится сам
        except Exception as e:
            log(f"Ошибка остановки log tail worker: {e}", "DEBUG")

    def _start_winws_output_worker(self):
        """Запускает worker для чтения вывода winws"""
        self._stop_winws_output_worker()

        # Получаем текущий runner и процесс
        runner = get_current_runner()
        if not runner:
            self.winws_status_label.setText("Процесс не запущен")
            self.winws_status_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; }")
            return

        process = runner.get_process()
        if not process:
            self.winws_status_label.setText("Процесс не запущен")
            self.winws_status_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; }")
            return

        # Обновляем статус
        strategy_info = runner.get_current_strategy_info()
        strategy_name = strategy_info.get('name', 'winws')
        # Обрезаем длинные названия стратегий
        if len(strategy_name) > 35:
            strategy_name = strategy_name[:32] + "..."
        pid = strategy_info.get('pid', '?')
        self.winws_status_label.setText(f"PID: {pid} | {strategy_name}")
        self.winws_status_label.setStyleSheet("QLabel { color: #60cdff; font-size: 11px; }")

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
            formatted = f'<span style="color: #ff6b6b;">{safe_text}</span>'
        else:
            # stdout показываем зелёным
            formatted = f'<span style="color: #00ff88;">{safe_text}</span>'

        self.winws_text.append(formatted)

        # Автопрокрутка
        scrollbar = self.winws_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_winws_process_ended(self, exit_code: int):
        """Обработчик завершения процесса winws"""
        if exit_code == 0:
            self.winws_status_label.setText(f"Процесс завершён (код: {exit_code})")
            self.winws_status_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; }")
        else:
            self.winws_status_label.setText(f"Процесс завершён с ошибкой (код: {exit_code})")
            self.winws_status_label.setStyleSheet("QLabel { color: #ff6b6b; font-size: 11px; }")

    def _update_winws_status(self):
        """Периодически проверяет статус процесса winws"""
        runner = get_current_runner()

        # Проверяем есть ли запущенный процесс
        if runner and runner.is_running():
            # Если worker не работает, запускаем его
            if not self._winws_thread or not self._winws_thread.isRunning():
                self._start_winws_output_worker()
        else:
            # Процесс не запущен - обновляем статус если worker не работает
            if not self._winws_thread or not self._winws_thread.isRunning():
                self.winws_status_label.setText("Процесс не запущен")
                self.winws_status_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; }")

    def _clear_winws_output(self):
        """Очищает поле вывода winws"""
        self.winws_text.clear()
        self._winws_lines_count = 0
        self.info_label.setText("🧹 Вывод winws очищен")

    def _append_text(self, text: str):
        """Добавляет текст в лог"""
        # Разбиваем на строки (может прийти несколько строк сразу)
        lines = text.split('\n')
        
        for line in lines:
            clean_line = line.rstrip()
            if not clean_line:
                continue
                
            # Добавляем в основной лог
            self.log_text.append(clean_line)
            
            # Проверяем на ошибки — добавляем ТОЛЬКО эту строку
            # Но исключаем ложные срабатывания
            if self._error_pattern.search(clean_line) and not self._exclude_pattern.search(clean_line):
                self._add_error(clean_line)
        
        # Автопрокрутка вниз
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _copy_log(self):
        """Копирует содержимое лога в буфер"""
        text = self.log_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.info_label.setText("✅ Скопировано в буфер обмена")
        else:
            self.info_label.setText("⚠️ Лог пуст")
            
    def _clear_view(self):
        """Очищает вид (не файл)"""
        self.log_text.clear()
        self.info_label.setText("🧹 Вид очищен")
        
    def _open_folder(self):
        """Открывает папку с логами"""
        try:
            import subprocess
            subprocess.run(['explorer', LOGS_FOLDER], check=False)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            
    def _update_stats(self):
        """Обновляет статистику"""
        try:
            # Считаем оба формата логов
            # Основные логи приложения
            app_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt"))
            app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
            # Debug логи winws2
            debug_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_winws2_debug_*.log"))

            all_files = app_logs + debug_logs
            total_size = sum(os.path.getsize(f) for f in all_files) / 1024 / 1024

            self.stats_label.setText(
                f"📊 Логи: {len(app_logs)} (макс {MAX_LOG_FILES}) | "
                f"🔧 Debug: {len(debug_logs)} (макс {MAX_DEBUG_LOG_FILES}) | "
                f"💾 Размер: {total_size:.2f} MB"
            )
        except Exception as e:
            self.stats_label.setText(f"Ошибка статистики: {e}")
            
    def _add_error(self, text: str):
        """Добавляет ошибку в панель ошибок"""
        self._errors_count += 1
        self.errors_count_label.setText(f"Ошибок: {self._errors_count}")
        
        # Добавляем текст с временной меткой
        self.errors_text.append(text)
        
        # Автопрокрутка
        scrollbar = self.errors_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _clear_errors(self):
        """Очищает панель ошибок"""
        self.errors_text.clear()
        self._errors_count = 0
        self.errors_count_label.setText("Ошибок: 0")
        self.info_label.setText("🧹 Ошибки очищены")
            
    def cleanup(self):
        """Очистка при закрытии - блокирующий режим"""
        self._stop_tail_worker(blocking=True)
        self._stop_winws_output_worker(blocking=True)

