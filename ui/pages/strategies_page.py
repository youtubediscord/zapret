# ui/pages/strategies_page.py
"""Страница выбора стратегий"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize, QFileSystemWatcher, QThread
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QFrame, QScrollArea, QPushButton,
                             QSizePolicy, QMessageBox, QApplication,
                             QButtonGroup, QStackedWidget)
from PyQt6.QtGui import QFont, QTextOption, QPainter, QColor, QPen
import qtawesome as qta
import os
import shlex
import math

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log


class ScrollBlockingScrollArea(QScrollArea):
    """QScrollArea который не пропускает прокрутку к родителю"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Запрещаем перетаскивание окна при взаимодействии
        self.setProperty("noDrag", True)
    
    def wheelEvent(self, event):
        scrollbar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        
        # Если прокручиваем вверх и уже в начале - блокируем
        if delta > 0 and scrollbar.value() == scrollbar.minimum():
            event.accept()
            return
        
        # Если прокручиваем вниз и уже в конце - блокируем
        if delta < 0 and scrollbar.value() == scrollbar.maximum():
            event.accept()
            return
        
        super().wheelEvent(event)
        event.accept()


class Win11Spinner(QWidget):
    """Спиннер в стиле Windows 11 - кольцо с бегущей точкой"""
    
    def __init__(self, size=20, color="#60cdff", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._size = size
        self._color = QColor(color)
        self._angle = 0
        self._arc_length = 90  # Длина дуги в градусах
        
        # Таймер для анимации
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        
    def start(self):
        """Запускает анимацию"""
        self._timer.start(16)  # ~60 FPS
        self.show()
        
    def stop(self):
        """Останавливает анимацию"""
        self._timer.stop()
        self.hide()
        
    def _rotate(self):
        self._angle = (self._angle + 6) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем фоновое кольцо (серое)
        pen = QPen(QColor(255, 255, 255, 30))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        margin = 3
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        painter.drawEllipse(rect)
        
        # Рисуем активную дугу (голубая)
        pen.setColor(self._color)
        painter.setPen(pen)
        
        # Qt рисует углы против часовой стрелки, начиная с 3 часов
        # Конвертируем в формат Qt: угол * 16 (Qt использует 1/16 градуса)
        start_angle = int((90 - self._angle) * 16)  # Начинаем с 12 часов
        span_angle = int(-self._arc_length * 16)  # По часовой стрелке
        
        painter.drawArc(rect, start_angle, span_angle)


class StatusIndicator(QWidget):
    """Индикатор статуса: галочка или спиннер"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Стек для переключения между галочкой и спиннером
        self.stack = QStackedWidget()
        self.stack.setFixedSize(20, 20)
        
        # Галочка
        self.check_icon = QLabel()
        self.check_icon.setPixmap(qta.icon('fa5s.check-circle', color='#6ccb5f').pixmap(20, 20))
        self.check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.check_icon)
        
        # Спиннер
        self.spinner = Win11Spinner(20, "#60cdff")
        self.stack.addWidget(self.spinner)
        
        layout.addWidget(self.stack)
        
        # По умолчанию показываем галочку
        self.stack.setCurrentWidget(self.check_icon)
        
    def show_loading(self):
        """Показывает спиннер загрузки"""
        self.stack.setCurrentWidget(self.spinner)
        self.spinner.start()
        
    def show_success(self):
        """Показывает галочку успеха"""
        self.spinner.stop()
        self.stack.setCurrentWidget(self.check_icon)


class CommandLineWidget(QFrame):
    """Виджет командной строки - всегда развернутый"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.command_line = ""
        self.formatted_command = ""
        self._build_ui()
        
    def _build_ui(self):
        self.setStyleSheet("""
            CommandLineWidget {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        
        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # Иконка терминала
        terminal_icon = QLabel()
        terminal_icon.setPixmap(qta.icon('fa5s.terminal', color='#60cdff').pixmap(14, 14))
        header_layout.addWidget(terminal_icon)
        
        title = QLabel("Командная строка")
        title.setStyleSheet("color: #60cdff; font-weight: 600; font-size: 12px;")
        header_layout.addWidget(title)
        
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        header_layout.addWidget(self.info_label)
        
        header_layout.addStretch()
        
        # Кнопки
        btn_style = """
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: #fff;
            }
        """
        
        copy_btn = QPushButton("CMD")
        copy_btn.setToolTip("Копировать для CMD")
        copy_btn.setStyleSheet(btn_style)
        copy_btn.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(copy_btn)
        self.copy_btn = copy_btn
        
        copy_ps = QPushButton("PS")
        copy_ps.setToolTip("Копировать для PowerShell")
        copy_ps.setStyleSheet(btn_style)
        copy_ps.clicked.connect(self._copy_formatted)
        header_layout.addWidget(copy_ps)
        
        layout.addLayout(header_layout)
        
        # Текстовое поле - всегда видно
        self.text_edit = ScrollBlockingTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 9))
        self.text_edit.setMinimumHeight(140)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: #1a1a1a;
                color: #d4d4d4;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.text_edit.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        layout.addWidget(self.text_edit, 1)  # stretch=1 чтобы занимало доступное место
            
    def generate_command(self):
        """Генерирует командную строку"""
        try:
            from strategy_menu import get_strategy_launch_method

            if get_strategy_launch_method() not in ("direct", "direct_orchestra"):
                self.text_edit.setPlainText("Командная строка доступна только в режиме Zapret 2")
                self.info_label.setText("BAT режим")
                return
                
            from strategy_menu.strategy_lists_separated import combine_strategies
            from strategy_menu.apply_filters import apply_all_filters
            from strategy_menu import get_direct_strategy_selections, get_default_selections
            from config import WINWS2_EXE, WINDIVERT_FILTER
            
            # Получаем выборы
            try:
                category_selections = get_direct_strategy_selections()
            except:
                category_selections = get_default_selections()
                
            if not category_selections:
                self.text_edit.setPlainText("Нет выбранных стратегий")
                return
                
            # Комбинируем стратегии
            combined = combine_strategies(**category_selections)
            args = shlex.split(combined['args'], posix=False)
            
            # Разрешаем пути
            exe_dir = os.path.dirname(WINWS2_EXE)
            work_dir = os.path.dirname(exe_dir)
            lists_dir = os.path.join(work_dir, "lists")
            bin_dir = os.path.join(work_dir, "bin")
            
            resolved_args = self._resolve_paths(args, lists_dir, bin_dir, WINDIVERT_FILTER)
            resolved_args = apply_all_filters(resolved_args, lists_dir)
            
            # Формируем команду
            cmd_parts = [WINWS2_EXE] + resolved_args
            full_cmd_parts = []
            for arg in cmd_parts:
                if ' ' in arg and not (arg.startswith('"') and arg.endswith('"')):
                    full_cmd_parts.append(f'"{arg}"')
                else:
                    full_cmd_parts.append(arg)
                    
            self.command_line = ' '.join(full_cmd_parts)
            self.formatted_command = self._format_for_display(full_cmd_parts)
            
            # Показываем в text_edit
            self.text_edit.setPlainText(self.formatted_command)
            self.info_label.setText(f"{len(self.command_line)} симв. | {len(resolved_args)} арг.")
            
        except Exception as e:
            log(f"Ошибка генерации команды: {e}", "ERROR")
            self.text_edit.setPlainText(f"Ошибка: {e}")
            
    def _resolve_paths(self, args, lists_dir, bin_dir, filter_dir):
        """Разрешает пути в аргументах"""
        resolved = []
        
        for arg in args:
            if arg.startswith("--wf-raw-part="):
                value = arg.split("=", 1)[1]
                if value.startswith("@"):
                    filename = value[1:].strip('"')
                    if not os.path.isabs(filename):
                        full_path = os.path.join(filter_dir, filename)
                        resolved.append(f'--wf-raw-part=@{full_path}')
                    else:
                        resolved.append(f'--wf-raw-part=@{filename}')
                else:
                    resolved.append(arg)
                    
            elif any(arg.startswith(p) for p in ["--hostlist=", "--ipset=", "--hostlist-exclude=", "--ipset-exclude="]):
                prefix, filename = arg.split("=", 1)
                filename = filename.strip('"')
                if not os.path.isabs(filename):
                    resolved.append(f'{prefix}={os.path.join(lists_dir, filename)}')
                else:
                    resolved.append(arg)
                    
            elif any(arg.startswith(p) for p in [
                "--dpi-desync-fake-tls=", "--dpi-desync-fake-quic=", "--dpi-desync-fake-syndata=",
                "--dpi-desync-fake-unknown-udp=", "--dpi-desync-split-seqovl-pattern=",
                "--dpi-desync-fake-http=", "--dpi-desync-fake-unknown=", "--dpi-desync-fakedsplit-pattern="
            ]):
                prefix, filename = arg.split("=", 1)
                if not filename.startswith("0x") and not filename.startswith("!") and not filename.startswith("^") and not os.path.isabs(filename):
                    resolved.append(f'{prefix}={os.path.join(bin_dir, filename.strip(chr(34)))}')
                else:
                    resolved.append(arg)
            else:
                resolved.append(arg)
                
        return resolved
        
    def _format_for_display(self, cmd_parts):
        """Форматирует для отображения с переносами"""
        if not cmd_parts:
            return ""
            
        lines = []
        current_line = []
        
        for i, arg in enumerate(cmd_parts):
            if i == 0:
                lines.append(arg)
                continue
                
            should_break = (
                arg == "--new" or
                arg.startswith("--filter-") or
                arg.startswith("--blob=") or
                arg.startswith("--lua-init=") or
                arg.startswith("--wf-")
            )
            
            if should_break:
                if current_line:
                    lines.append("  " + " ".join(current_line) + " `")
                    current_line = []
                if arg == "--new":
                    lines.append("  --new `")
                else:
                    current_line.append(arg)
            else:
                current_line.append(arg)
                
        if current_line:
            lines.append("  " + " ".join(current_line))
            
        if lines and lines[-1].endswith(" `"):
            lines[-1] = lines[-1][:-2]
            
        return "\n".join(lines)
        
    def _copy_to_clipboard(self):
        """Копирует однострочную команду"""
        if not self.command_line:
            self.generate_command()
        if self.command_line:
            QApplication.clipboard().setText(self.command_line)
            old_text = self.copy_btn.text()
            self.copy_btn.setText("✓")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText(old_text))
            
    def _copy_formatted(self):
        """Копирует форматированную команду"""
        if not self.formatted_command:
            self.generate_command()
        if self.formatted_command:
            QApplication.clipboard().setText(self.formatted_command)


class ResetActionButton(QPushButton):
    """Кнопка сброса с двойным подтверждением и анимацией"""

    reset_confirmed = pyqtSignal()

    def __init__(self, text: str = "Сбросить", confirm_text: str = "Подтвердить?", parent=None):
        super().__init__(text, parent)
        self._default_text = text
        self._confirm_text = confirm_text
        self._pending = False
        self._hovered = False
        self._icon_offset = 0.0
        
        # Иконка
        self._update_icon()
        self.setIconSize(QSize(16, 16))
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Таймер сброса состояния
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset_state)
        
        # Анимация иконки (качание)
        self._shake_timer = QTimer(self)
        self._shake_timer.timeout.connect(self._animate_shake)
        self._shake_step = 0
        
        self._update_style()
        
    def _update_icon(self, rotation: int = 0):
        """Обновляет иконку с опциональным углом поворота"""
        color = '#4ade80' if self._pending else 'white'
        icon_name = 'fa5s.trash-alt' if self._pending else 'fa5s.broom'
        if rotation != 0:
            self.setIcon(qta.icon(icon_name, color=color, rotated=rotation))
        else:
            self.setIcon(qta.icon(icon_name, color=color))
        
    def _update_style(self):
        """Обновляет стили кнопки"""
        if self._pending:
            # Состояние подтверждения - зеленоватый цвет
            if self._hovered:
                bg = "rgba(74, 222, 128, 0.35)"
            else:
                bg = "rgba(74, 222, 128, 0.25)"
            text_color = "#4ade80"
            border = "1px solid rgba(74, 222, 128, 0.5)"
        else:
            # Обычное состояние
            if self._hovered:
                bg = "rgba(255, 255, 255, 0.15)"
            else:
                bg = "rgba(255, 255, 255, 0.08)"
            text_color = "#ffffff"
            border = "none"
            
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: {border};
                border-radius: 4px;
                color: {text_color};
                padding: 0 16px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }}
        """)
        
    def _animate_shake(self):
        """Анимация качания иконки"""
        self._shake_step += 1
        if self._shake_step > 8:
            self._shake_timer.stop()
            self._shake_step = 0
            self._update_icon(0)  # Возвращаем в нормальное положение
            return
            
        # Качаем иконку влево-вправо (углы поворота)
        rotations = [0, -15, 15, -12, 12, -8, 8, -4, 0]
        rotation = rotations[min(self._shake_step, len(rotations) - 1)]
        
        # Обновляем иконку с поворотом
        self._update_icon(rotation)
        
    def _start_shake_animation(self):
        """Запускает анимацию качания"""
        self._shake_step = 0
        self._shake_timer.start(50)
        
    def _reset_state(self):
        """Сбрасывает состояние кнопки"""
        self._pending = False
        self.setText(self._default_text)
        self._update_icon()
        self._update_style()
        self._shake_timer.stop()
        
    def mousePressEvent(self, event):
        """Обработка клика"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._pending:
                # Второй клик - подтверждение
                self._reset_timer.stop()
                self._pending = False
                self.setText("✓ Сброшено")
                self._update_icon()
                self._update_style()
                self.reset_confirmed.emit()
                # Вернуть исходное состояние через 1.5 сек
                QTimer.singleShot(1500, self._reset_state)
            else:
                # Первый клик - переход в режим подтверждения
                self._pending = True
                self.setText(self._confirm_text)
                self._update_icon()
                self._update_style()
                self._start_shake_animation()
                # Сбросить через 3 секунды если не подтверждено
                self._reset_timer.start(3000)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)


class StrategiesPage(QWidget):
    """Страница стратегий - поддерживает оба режима: direct и bat"""
    
    launch_method_changed = pyqtSignal(str)
    strategy_selected = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self._strategy_widget = None
        self._bat_table = None
        self._initialized = False
        self._current_mode = None
        self.cmd_widget = None
        self._file_watcher = None
        self._watcher_active = False
        
        # Таймер для проверки статуса процесса
        self._process_check_timer = QTimer(self)
        self._process_check_timer.timeout.connect(self._check_process_status)
        self._process_check_attempts = 0
        self._max_check_attempts = 30  # 30 попыток * 200мс = 6 секунд максимум
        
        # Абсолютный таймаут для защиты от зависания спиннера
        self._absolute_timeout_timer = QTimer(self)
        self._absolute_timeout_timer.setSingleShot(True)
        self._absolute_timeout_timer.timeout.connect(self._on_absolute_timeout)
        
        self._build_ui()
        
    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Заголовок страницы
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(32, 24, 32, 16)
        
        title = QLabel("Стратегии")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 28px;
                font-weight: 600;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }
        """)
        header_layout.addWidget(title)
        
        subtitle = QLabel("Настройка методов обхода блокировок")
        subtitle.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 13px;
            }
        """)
        header_layout.addWidget(subtitle)

        # Кнопка для добавления своего сайта
        from config.telegram_links import open_telegram_link
        add_site_btn = ActionButton("Добавить свой сайт", "fa5b.telegram")
        add_site_btn.clicked.connect(lambda: open_telegram_link("zaprethelp", post=18408))
        header_layout.addWidget(add_site_btn)
        
        self.main_layout.addWidget(header)
        
        # Текущая стратегия
        current_widget = QWidget()
        current_widget.setStyleSheet("background-color: transparent;")
        current_layout = QHBoxLayout(current_widget)
        current_layout.setContentsMargins(32, 0, 32, 16)
        
        self.status_indicator = StatusIndicator()
        current_layout.addWidget(self.status_indicator)
        
        current_prefix = QLabel("Текущая:")
        current_prefix.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 14px;")
        current_layout.addWidget(current_prefix)
        
        # Контейнер для иконок активных стратегий
        self.current_strategy_container = QWidget()
        self.current_strategy_container.setStyleSheet("background: transparent;")
        self.current_icons_layout = QHBoxLayout(self.current_strategy_container)
        self.current_icons_layout.setContentsMargins(0, 0, 0, 0)
        self.current_icons_layout.setSpacing(4)
        
        # Включаем отслеживание мыши для красивого тултипа
        self.current_strategy_container.setMouseTracking(True)
        self.current_strategy_container.installEventFilter(self)
        self._has_hidden_strategies = False  # Флаг для показа тултипа
        self._tooltip_strategies_data = []
        current_layout.addWidget(self.current_strategy_container)
        
        # Текстовый лейбл (для fallback и BAT режима)
        self.current_strategy_label = QLabel("Не выбрана")
        self.current_strategy_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        current_layout.addWidget(self.current_strategy_label)
        
        current_layout.addStretch()
        
        # Счётчик избранных стратегий
        self.favorites_count_label = QLabel("")
        self.favorites_count_label.setStyleSheet("""
            QLabel {
                color: #ffc107;
                font-size: 13px;
                font-weight: 600;
                padding: 4px 12px;
                background: rgba(255, 193, 7, 0.1);
                border-radius: 12px;
            }
        """)
        self.favorites_count_label.hide()
        current_layout.addWidget(self.favorites_count_label)
        
        self.main_layout.addWidget(current_widget)
        
        # Прокручиваемая область для всего контента
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { 
                background: rgba(255,255,255,0.03); 
                width: 8px; 
                border-radius: 4px;
            }
            QScrollBar::handle:vertical { 
                background: rgba(255,255,255,0.15); 
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { 
                background: rgba(255,255,255,0.25); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        # Контейнер для контента (меняется в зависимости от режима)
        self.content_container = QWidget()
        self.content_container.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_container)
        # Уменьшаем горизонтальные отступы, чтобы сблизить колонку сайтов и таблицу стратегий
        self.content_layout.setContentsMargins(14, 0, 14, 20)
        self.content_layout.setSpacing(12)
        
        # Плейсхолдер загрузки
        self.loading_label = QLabel("⏳ Загрузка...")
        self.loading_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.loading_label)
        
        self.scroll_area.setWidget(self.content_container)
        self.main_layout.addWidget(self.scroll_area, 1)
        
        # Совместимость со старым кодом
        self.select_strategy_btn = QPushButton()
        self.select_strategy_btn.hide()
        
        self.category_selections = {}
        
    def showEvent(self, event):
        """При показе страницы загружаем стратегии"""
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            # Загружаем контент сразу, без задержки
            QTimer.singleShot(0, self._load_content)
            
    def _clear_content(self):
        """Очищает контент"""
        # Удаляем все виджеты из content_layout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._strategy_widget = None
        self._bat_table = None
        self.cmd_widget = None
        self.loading_label = None
            
    def _load_content(self):
        """Загружает контент в зависимости от режима"""
        try:
            from strategy_menu import get_strategy_launch_method
            mode = get_strategy_launch_method()
            
            # Если режим не изменился и контент уже загружен - пропускаем
            if mode == self._current_mode and (self._strategy_widget or self._bat_table):
                return
                
            self._current_mode = mode
            self._clear_content()
            
            if mode in ("direct", "direct_orchestra"):
                self.stop_watching()  # Останавливаем мониторинг для экономии ресурсов
                self._load_direct_mode()
            else:
                self._load_bat_mode()
                self.start_watching()  # Запускаем мониторинг для bat режима
                
        except Exception as e:
            log(f"Ошибка загрузки контента: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            
            self._clear_content()
            error_label = QLabel(f"❌ Ошибка загрузки: {e}")
            error_label.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(error_label)
            
    def _load_direct_mode(self):
        """Загружает интерфейс для direct режима (Zapret 2)"""
        try:
            from strategy_menu.categories_tab_panel import CategoriesTabPanel
            from strategy_menu.strategies_registry import registry
            from strategy_menu import get_direct_strategy_selections, get_default_selections
            
            # Заголовок секции
            section_header = QLabel("Выберите стратегию для каждого типа трафика")
            section_header.setStyleSheet("""
                QLabel {
                    color: #60cdff;
                    font-size: 14px;
                    font-weight: 600;
                    padding-bottom: 8px;
                }
            """)
            self.content_layout.addWidget(section_header)
            
            # Панель действий
            actions_card = SettingsCard()
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(8)
            
            reload_btn = ActionButton("Обновить", "fa5s.sync-alt")
            reload_btn.clicked.connect(self._reload_strategies)
            actions_layout.addWidget(reload_btn)
            
            folder_btn = ActionButton("Папка", "fa5s.folder-open")
            folder_btn.clicked.connect(self._open_folder)
            actions_layout.addWidget(folder_btn)
            
            self._clear_btn = ResetActionButton("Выключить", confirm_text="Всё удалится")
            self._clear_btn.reset_confirmed.connect(self._clear_all)
            actions_layout.addWidget(self._clear_btn)

            self._reset_btn = ResetActionButton("Сбросить", confirm_text="По умолчанию")
            self._reset_btn.reset_confirmed.connect(self._reset_to_defaults)
            actions_layout.addWidget(self._reset_btn)
            
            # Кнопка перезапуска с анимацией
            self._restart_btn = ActionButton("Перезапустить", "fa5s.redo-alt")
            self._restart_btn.clicked.connect(self._restart_dpi)
            actions_layout.addWidget(self._restart_btn)
            
            # Анимация вращения для кнопки перезапуска
            self._restart_icon_normal = qta.icon('fa5s.redo-alt', color='white')
            self._restart_spin_animation = qta.Spin(self._restart_btn, interval=10, step=8)
            self._restart_icon_spinning = qta.icon('fa5s.redo-alt', color='#60cdff', animation=self._restart_spin_animation)
            
            actions_layout.addStretch()
            actions_card.add_layout(actions_layout)
            self.content_layout.addWidget(actions_card)
            
            # Загружаем выборы из реестра
            try:
                self.category_selections = get_direct_strategy_selections()
                log(f"Загружены выборы стратегий из реестра: {len(self.category_selections)} категорий", "DEBUG")
            except Exception as e:
                log(f"Ошибка загрузки выборов из реестра: {e}, используем значения по умолчанию", "WARNING")
                self.category_selections = get_default_selections()
            
            # Создаём панель с вкладками категорий (с кнопкой добавления)
            self._strategy_widget = CategoriesTabPanel(show_add_button=True)
            self._strategy_widget._tab_category_keys = []
            self._strategy_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._strategy_widget.add_category_clicked.connect(self._show_add_category_dialog)
            self._strategy_widget.edit_category_clicked.connect(self._show_edit_category_dialog)
            
            # Получаем данные из реестра
            tab_tooltips = registry.get_tab_tooltips_dict()
            
            self._category_tab_indices = {}
            # Получаем ВСЕ категории (больше не скрываем, только блокируем)
            category_keys = registry.get_all_category_keys_sorted()
            
            # Очищаем существующие вкладки
            self._strategy_widget.clear()
            self._strategy_widget._tab_category_keys = []
            
            # Создаём вкладки для ВСЕХ категорий (по порядку)
            for idx, category_key in enumerate(category_keys):
                category_info = registry.get_category_info(category_key)
                if not category_info:
                    continue
                
                # Всегда используем full_name, иконки добавляются через icon_name
                display_name = category_info.full_name
                
                # Заглушка с сохранённым category_key
                placeholder = QWidget()
                placeholder.setProperty("category_key", category_key)
                p_layout = QVBoxLayout(placeholder)
                p_layout.setContentsMargins(20, 20, 20, 20)
                p_layout.addWidget(QLabel("⏳ Нажмите для загрузки..."))
                p_layout.addStretch()
                
                # Добавляем вкладку и сохраняем индекс
                actual_index = self._strategy_widget.addTab(placeholder, display_name, category_key)
                self._category_tab_indices[category_key] = actual_index
                
                if category_key in tab_tooltips:
                    self._strategy_widget.setTabToolTip(actual_index, tab_tooltips[category_key])
            
            self._strategy_widget.currentChanged.connect(self._on_tab_changed)
            self._strategy_widget.setMinimumHeight(500)  # Увеличенная высота блока стратегий
            self.content_layout.addWidget(self._strategy_widget, 1)  # stretch=1 - растягивается при увеличении окна

            # Подписываемся на изменение рейтингов для обновления подсветки
            self._setup_rating_callback()

            # Отступ перед командной строкой
            self.content_layout.addSpacing(20)

            # Виджет командной строки (отдельный блок внизу)
            self.cmd_widget = CommandLineWidget()
            self.cmd_widget.setMinimumHeight(200)  # Увеличенная высота
            self.cmd_widget.setMaximumHeight(250)  # Ограничение максимальной высоты
            self.content_layout.addWidget(self.cmd_widget, 0)  # stretch=0 - не растягивается, остаётся внизу

            # Обновляем цвета иконок всех вкладок на основе выборов
            self._strategy_widget.update_all_tab_icons(self.category_selections)

            # Выбираем первую вкладку и загружаем сразу
            if self._strategy_widget.count() > 0:
                self._strategy_widget.blockSignals(True)
                self._strategy_widget.setCurrentIndex(0)
                self._strategy_widget.blockSignals(False)
                self._load_category_tab(0)
            
            # Добавляем кнопку "+" в конец списка категорий
            self._strategy_widget.add_add_button()
            
            # Обновляем отображение и командную строку сразу
            self._update_current_strategies_display()
            self._generate_command_line()

            # ✅ Обновляем отображение фильтров на странице DPI Settings
            self._update_dpi_filters_display()

            log("Direct режим загружен", "INFO")
            
        except Exception as e:
            log(f"Ошибка загрузки direct режима: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            raise

    def _load_bat_mode(self):
        """Загружает интерфейс для bat режима (Zapret 1)"""
        try:
            from strategy_menu.strategy_table_widget_favorites import StrategyTableWithFavoritesFilter
            
            # Получаем strategy_manager
            strategy_manager = None
            if hasattr(self.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.strategy_manager
            elif hasattr(self.parent_app, 'parent_app') and hasattr(self.parent_app.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.parent_app.strategy_manager
            
            # Создаём таблицу - минималистичный дизайн
            self._bat_table = StrategyTableWithFavoritesFilter(strategy_manager=strategy_manager, parent=self)
            self._bat_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._bat_table.setMinimumHeight(500)  # Увеличенная высота
            
            # Подключаем сигнал автоприменения
            if hasattr(self._bat_table, 'strategy_applied'):
                self._bat_table.strategy_applied.connect(self._on_bat_strategy_applied)
            
            # Подключаем сигнал изменения избранных
            if hasattr(self._bat_table, 'favorites_changed'):
                self._bat_table.favorites_changed.connect(self._update_favorites_count)
            
            self.content_layout.addWidget(self._bat_table, 1)

            # Виджет превью командной строки
            self._cmd_preview_widget = self._create_cmd_preview_widget()
            self.content_layout.addWidget(self._cmd_preview_widget)

            # Подключаем обновление превью при выборе стратегии
            if hasattr(self._bat_table, 'table') and hasattr(self._bat_table.table, 'itemSelectionChanged'):
                self._bat_table.table.itemSelectionChanged.connect(self._update_cmd_preview)

            # Загружаем локальные стратегии сразу
            if strategy_manager:
                self._load_bat_strategies()
                # Асинхронно применяем последнюю выбранную стратегию из реестра
                QTimer.singleShot(300, self._auto_select_last_bat_strategy)
            else:
                log("strategy_manager недоступен для bat режима", "WARNING")

            log("Bat режим загружен", "INFO")
            
        except Exception as e:
            log(f"Ошибка загрузки bat режима: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            raise
            
    def _load_bat_strategies(self):
        """Загружает список bat стратегий"""
        try:
            if not self._bat_table:
                return
                
            strategy_manager = None
            if hasattr(self.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.strategy_manager
            elif hasattr(self.parent_app, 'parent_app') and hasattr(self.parent_app.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.parent_app.strategy_manager
                
            if strategy_manager:
                strategies = strategy_manager.get_local_strategies_only()
                if strategies:
                    self._bat_table.populate_strategies(strategies)
                    self._update_favorites_count()
                    log(f"Загружено {len(strategies)} bat стратегий", "DEBUG")
                else:
                    log("Нет локальных bat стратегий", "WARNING")
                    
        except Exception as e:
            log(f"Ошибка загрузки bat стратегий: {e}", "ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
    
    def _update_favorites_count(self):
        """Обновляет счётчик избранных стратегий"""
        try:
            from strategy_menu import get_favorite_strategies
            favorites = get_favorite_strategies("bat")
            count = len(favorites) if favorites else 0

            if count > 0:
                self.favorites_count_label.setText(f"★ {count} избранных")
                self.favorites_count_label.show()
            else:
                self.favorites_count_label.hide()
        except Exception as e:
            log(f"Ошибка обновления счётчика избранных: {e}", "DEBUG")
            self.favorites_count_label.hide()

    def _create_cmd_preview_widget(self) -> QWidget:
        """Создаёт виджет для превью командной строки"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(8)

        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        label = QLabel("Командная строка:")
        label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
                font-weight: 500;
            }
        """)
        header_layout.addWidget(label)

        # Кнопка копирования
        copy_btn = QPushButton()
        copy_btn.setIcon(qta.icon('fa5s.copy', color='#60cdff'))
        copy_btn.setFixedSize(24, 24)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
            }
        """)
        copy_btn.setToolTip("Копировать команду")
        copy_btn.clicked.connect(self._copy_cmd_to_clipboard)
        header_layout.addWidget(copy_btn)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Текстовое поле для команды
        self._cmd_preview_text = ScrollBlockingTextEdit()
        self._cmd_preview_text.setReadOnly(True)
        self._cmd_preview_text.setMinimumHeight(80)
        self._cmd_preview_text.setMaximumHeight(150)
        self._cmd_preview_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                color: #b0b0b0;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        self._cmd_preview_text.setPlaceholderText("Выберите стратегию для просмотра команды...")
        self._cmd_preview_text.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self._cmd_preview_text)

        return widget

    def _update_cmd_preview(self):
        """Обновляет превью командной строки для выбранной стратегии"""
        try:
            if not hasattr(self, '_cmd_preview_text') or not self._cmd_preview_text:
                return

            if not self._bat_table:
                return

            # Получаем выбранную стратегию (возвращает tuple: id, name)
            selected = self._bat_table.get_selected_strategy()
            if not selected or not selected[0]:
                self._cmd_preview_text.setPlainText("")
                return

            strategy_id, strategy_name = selected

            # Получаем полную информацию о стратегии из менеджера
            strategy_manager = None
            if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.strategy_manager
            elif hasattr(self, 'parent_app') and hasattr(self.parent_app, 'parent_app'):
                if hasattr(self.parent_app.parent_app, 'strategy_manager'):
                    strategy_manager = self.parent_app.parent_app.strategy_manager

            if not strategy_manager:
                self._cmd_preview_text.setPlainText(f"# Менеджер стратегий не доступен")
                return

            strategies = strategy_manager.get_strategies_list()
            strategy_info = strategies.get(strategy_id, {})
            file_path = strategy_info.get('file_path', '')

            if not file_path:
                self._cmd_preview_text.setPlainText(f"# Файл стратегии не найден: {strategy_name}")
                return

            # Полный путь к BAT файлу
            from config import BAT_FOLDER
            full_path = os.path.join(BAT_FOLDER, file_path)

            if not os.path.exists(full_path):
                self._cmd_preview_text.setPlainText(f"# Файл не существует: {full_path}")
                return

            # Парсим BAT файл
            from utils.bat_parser import parse_bat_file

            parsed = parse_bat_file(full_path, debug=False)
            if not parsed:
                self._cmd_preview_text.setPlainText(f"# Не удалось распарсить: {file_path}")
                return

            exe_path, args = parsed

            # Формируем командную строку для отображения
            if exe_path is None:
                # Новый формат - показываем winws.exe + аргументы
                cmd_parts = ["winws.exe"] + args
            else:
                # Старый формат
                cmd_parts = [os.path.basename(exe_path)] + args

            # Форматируем для удобного чтения (каждый --new на новой строке)
            formatted_cmd = self._format_cmd_for_display(cmd_parts)

            self._cmd_preview_text.setPlainText(formatted_cmd)

        except Exception as e:
            log(f"Ошибка обновления превью команды: {e}", "DEBUG")
            if hasattr(self, '_cmd_preview_text') and self._cmd_preview_text:
                self._cmd_preview_text.setPlainText(f"# Ошибка: {e}")

    def _format_cmd_for_display(self, cmd_parts: list) -> str:
        """Форматирует командную строку для удобного отображения"""
        lines = []
        current_line = []

        for part in cmd_parts:
            if part == '--new':
                # Сохраняем текущую строку
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                lines.append('--new')
            else:
                current_line.append(part)

        # Добавляем последнюю строку
        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def _copy_cmd_to_clipboard(self):
        """Копирует командную строку в буфер обмена"""
        try:
            if hasattr(self, '_cmd_preview_text') and self._cmd_preview_text:
                text = self._cmd_preview_text.toPlainText()
                if text:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(text)
                    log("Команда скопирована в буфер обмена", "INFO")
        except Exception as e:
            log(f"Ошибка копирования команды: {e}", "DEBUG")

    def _auto_select_last_bat_strategy(self):
        """Автоматически выбирает и применяет последнюю BAT-стратегию из реестра (асинхронно)"""
        try:
            if not self._bat_table:
                log("BAT таблица не готова для автовыбора", "DEBUG")
                return
            
            # Проверяем что таблица заполнена стратегиями
            if not hasattr(self._bat_table, 'strategies_map') or not self._bat_table.strategies_map:
                log("BAT таблица пустая, стратегии ещё не загружены", "DEBUG")
                return
            
            from config.reg import get_last_bat_strategy
            from strategy_menu import get_strategy_launch_method
            
            # Проверяем что мы всё ещё в BAT режиме
            if get_strategy_launch_method() != "bat":
                log("Режим уже не BAT, пропускаем автовыбор", "DEBUG")
                return
            
            # Получаем последнюю BAT-стратегию из реестра (отдельный ключ реестра)
            last_strategy_name = get_last_bat_strategy()
            
            if not last_strategy_name or last_strategy_name == "Автостарт DPI отключен":
                log("Нет сохранённой последней стратегии или автозапуск отключён", "DEBUG")
                self.current_strategy_label.setText("Не выбрана")
                return
            
            log(f"🔄 Автоматически применяется последняя BAT-стратегия: {last_strategy_name}", "INFO")
            
            # Программно выбираем стратегию в таблице
            # Это автоматически вызовет _on_item_selected → strategy_applied сигнал → _on_bat_strategy_applied
            self._bat_table.select_strategy_by_name(last_strategy_name)
            
            # Обновляем отображение текущей стратегии (дополнительно, на случай если сигнал не сработал)
            self.current_strategy_label.setText(f"🎯 {last_strategy_name}")
            
        except Exception as e:
            log(f"Ошибка автовыбора BAT-стратегии: {e}", "WARNING")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            # При ошибке показываем "Не выбрана"
            self.current_strategy_label.setText("Не выбрана")
            
    def start_watching(self):
        """Запускает мониторинг .bat файлов (только для bat режима)"""
        try:
            if self._watcher_active:
                return  # Уже активен
            
            from config import BAT_FOLDER
            
            if not os.path.exists(BAT_FOLDER):
                log(f"Папка bat не найдена для мониторинга: {BAT_FOLDER}", "WARNING")
                return
            
            # Создаём watcher если его нет
            if not self._file_watcher:
                self._file_watcher = QFileSystemWatcher()
                self._file_watcher.directoryChanged.connect(self._on_bat_folder_changed)
                self._file_watcher.fileChanged.connect(self._on_bat_file_changed)
            
            # Мониторим папку (для добавления/удаления файлов)
            self._file_watcher.addPath(BAT_FOLDER)
            
            # Мониторим все существующие .bat файлы (для изменения содержимого)
            self._add_bat_files_to_watcher(BAT_FOLDER)
            
            self._watcher_active = True
            log(f"✅ Мониторинг .bat файлов запущен", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка запуска мониторинга: {e}", "WARNING")
    
    def stop_watching(self):
        """Останавливает мониторинг .bat файлов (экономия ресурсов в direct режиме)"""
        try:
            if not self._watcher_active:
                return  # Уже остановлен
            
            if self._file_watcher:
                # Удаляем все пути из мониторинга
                directories = self._file_watcher.directories()
                files = self._file_watcher.files()
                
                if directories:
                    self._file_watcher.removePaths(directories)
                if files:
                    self._file_watcher.removePaths(files)
            
            self._watcher_active = False
            log(f"⏸️ Мониторинг .bat файлов остановлен", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка остановки мониторинга: {e}", "DEBUG")
    
    def _add_bat_files_to_watcher(self, folder_path: str):
        """Добавляет все .bat файлы в мониторинг"""
        try:
            if not os.path.exists(folder_path):
                return
            
            bat_files = [
                os.path.join(folder_path, f) 
                for f in os.listdir(folder_path) 
                if f.lower().endswith('.bat')
            ]
            
            if bat_files:
                self._file_watcher.addPaths(bat_files)
                log(f"Добавлено {len(bat_files)} .bat файлов в мониторинг", "DEBUG")
                
        except Exception as e:
            log(f"Ошибка добавления файлов в мониторинг: {e}", "DEBUG")
    
    def _on_bat_folder_changed(self, path: str):
        """Обработчик изменений в папке .bat файлов (добавление/удаление)"""
        try:
            log(f"Обнаружены изменения в папке: {path}", "DEBUG")
            
            # При изменении папки нужно обновить список отслеживаемых файлов
            self._update_watched_files(path)
            
            # Обновляем список стратегий с небольшой задержкой
            QTimer.singleShot(500, self._refresh_bat_strategies)
            
        except Exception as e:
            log(f"Ошибка обработки изменений в папке: {e}", "ERROR")
    
    def _on_bat_file_changed(self, path: str):
        """Обработчик изменений в .bat файле (изменение содержимого)"""
        try:
            log(f"Обнаружены изменения в файле: {os.path.basename(path)}", "DEBUG")
            
            # Обновляем список стратегий с небольшой задержкой
            QTimer.singleShot(500, self._refresh_bat_strategies)
            
        except Exception as e:
            log(f"Ошибка обработки изменений в файле: {e}", "ERROR")
    
    def _update_watched_files(self, folder_path: str):
        """Обновляет список отслеживаемых файлов"""
        try:
            if not self._file_watcher:
                return
            
            # Удаляем все текущие файлы из мониторинга
            current_files = self._file_watcher.files()
            if current_files:
                self._file_watcher.removePaths(current_files)
            
            # Добавляем актуальный список файлов
            self._add_bat_files_to_watcher(folder_path)
            
        except Exception as e:
            log(f"Ошибка обновления отслеживаемых файлов: {e}", "DEBUG")
    
    def _refresh_bat_strategies(self):
        """Обновляет список bat стратегий"""
        try:
            if self._current_mode != 'bat':
                return
            
            # Получаем strategy_manager
            strategy_manager = None
            if hasattr(self.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.strategy_manager
            elif hasattr(self.parent_app, 'parent_app') and hasattr(self.parent_app.parent_app, 'strategy_manager'):
                strategy_manager = self.parent_app.parent_app.strategy_manager
            
            if not strategy_manager:
                log("strategy_manager не найден для обновления", "WARNING")
                return
            
            # Обновляем кэш стратегий
            strategies = strategy_manager.refresh_strategies()
            log(f"Обновлено {len(strategies)} bat стратегий", "INFO")
            
            # Обновляем список отслеживаемых файлов (на случай добавления/удаления)
            from config import BAT_FOLDER
            if os.path.exists(BAT_FOLDER):
                self._update_watched_files(BAT_FOLDER)
            
            # Обновляем таблицу
            if self._bat_table and strategies:
                self._bat_table.populate_strategies(strategies)
                self._update_favorites_count()
                log("Таблица стратегий обновлена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка обновления bat стратегий: {e}", "ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
    
    def _show_add_category_dialog(self):
        """Показывает диалог добавления категории"""
        try:
            from ui.dialogs.add_category_dialog import AddCategoryDialog
            
            dialog = AddCategoryDialog(self)
            dialog.category_added.connect(self._on_category_added)
            dialog.category_updated.connect(self._on_category_updated)
            dialog.category_deleted.connect(self._on_category_deleted)
            dialog.exec()
            
        except Exception as e:
            log(f"Ошибка открытия диалога добавления категории: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
    
    def _show_edit_category_dialog(self, category_key: str):
        """Показывает диалог редактирования категории"""
        try:
            from ui.dialogs.add_category_dialog import AddCategoryDialog
            from strategy_menu.strategies_registry import registry
            
            # Получаем данные категории
            category_info = registry.get_category_info(category_key)
            if not category_info:
                log(f"Категория '{category_key}' не найдена", "WARNING")
                return
            
            # Преобразуем CategoryInfo в словарь
            category_data = {
                'key': category_info.key,
                'full_name': category_info.full_name,
                'description': category_info.description,
                'tooltip': category_info.tooltip,
                'color': category_info.color,
                'default_strategy': category_info.default_strategy,
                'ports': category_info.ports,
                'protocol': getattr(category_info, 'protocol', 'TCP'),
                'order': category_info.order,
                'command_order': category_info.command_order,
                'needs_new_separator': category_info.needs_new_separator,
                'command_group': category_info.command_group,
                'icon_name': category_info.icon_name,
                'icon_color': category_info.icon_color,
                'base_filter': category_info.base_filter,
                'strategy_type': category_info.strategy_type,
                'requires_all_ports': getattr(category_info, 'requires_all_ports', False),
                'strip_payload': getattr(category_info, 'strip_payload', False)
            }
            
            dialog = AddCategoryDialog(self, category_data=category_data)
            dialog.category_updated.connect(self._on_category_updated)
            dialog.category_deleted.connect(self._on_category_deleted)
            dialog.exec()
            
        except Exception as e:
            log(f"Ошибка открытия диалога редактирования категории: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
    
    def _on_category_added(self, category_data: dict):
        """Обработчик добавления новой категории"""
        try:
            from strategy_menu.strategies_registry import reload_categories
            
            # Перезагружаем категории
            reload_categories()
            log(f"Категории перезагружены после добавления '{category_data.get('key')}'", "INFO")
            
            # Перезагружаем страницу
            self._reload_strategies()
            
        except Exception as e:
            log(f"Ошибка после добавления категории: {e}", "ERROR")
    
    def _on_category_updated(self, category_data: dict):
        """Обработчик обновления категории"""
        try:
            from strategy_menu.strategies_registry import reload_categories
            
            # Перезагружаем категории
            reload_categories()
            log(f"Категории перезагружены после обновления '{category_data.get('key')}'", "INFO")
            
            # Перезагружаем страницу
            self._reload_strategies()
            
        except Exception as e:
            log(f"Ошибка после обновления категории: {e}", "ERROR")
    
    def _on_category_deleted(self, category_key: str):
        """Обработчик удаления категории"""
        try:
            from strategy_menu.strategies_registry import reload_categories
            
            # Перезагружаем категории
            reload_categories()
            log(f"Категории перезагружены после удаления '{category_key}'", "INFO")
            
            # Перезагружаем страницу
            self._reload_strategies()
            
        except Exception as e:
            log(f"Ошибка после удаления категории: {e}", "ERROR")
    
    def _on_bat_strategy_applied(self, strategy_id: str, strategy_name: str):
        """Обработчик автоприменения bat стратегии"""
        self.strategy_selected.emit(strategy_id, strategy_name)
        
        # Показываем спиннер загрузки
        self.show_loading()
        
        # Запускаем абсолютный таймаут защиты (10 секунд)
        # Если за это время процесс не запустится - принудительно покажем галочку
        self._absolute_timeout_timer.start(10000)
        log("🛡️ Запущен таймаут защиты спиннера (10 секунд)", "DEBUG")
        
        # Автоматически запускаем стратегию через dpi_controller
        try:
            app = self.parent_app
            if hasattr(app, 'dpi_controller') and app.dpi_controller:
                # Сохраняем последнюю BAT-стратегию (отдельный ключ реестра)
                from config.reg import set_last_bat_strategy
                set_last_bat_strategy(strategy_name)
                
                # Запускаем BAT стратегию
                app.dpi_controller.start_dpi_async(selected_mode=strategy_name)
                log(f"BAT стратегия запущена: {strategy_name}", "INFO")
                
                # Обновляем лейбл текущей стратегии
                self.current_strategy_label.setText(f"🎯 {strategy_name}")
                if hasattr(app, 'current_strategy_label'):
                    app.current_strategy_label.setText(strategy_name)
                if hasattr(app, 'current_strategy_name'):
                    app.current_strategy_name = strategy_name
                
                # Запускаем мониторинг реального статуса процесса
                self._start_process_monitoring()
            else:
                self._stop_absolute_timeout()
                self.show_success()
        except Exception as e:
            log(f"Ошибка применения BAT стратегии: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self._stop_absolute_timeout()
            self.show_success()  # При ошибке тоже убираем спиннер
        
    def reload_for_mode_change(self):
        """Перезагружает страницу при смене режима"""
        self.stop_watching()  # Останавливаем мониторинг при смене режима
        self._stop_process_monitoring()  # Останавливаем мониторинг процесса (+ абсолютный таймаут)
        self._stop_absolute_timeout()  # Дополнительная защита
        self._current_mode = None
        self._initialized = False
        self._clear_content()
        
        # Сбрасываем текущую стратегию при переключении режима
        self.current_strategy_label.setText("⏳ Загрузка...")
        self.current_strategy_label.show()
        self.current_strategy_container.hide()
        
        # Показываем спиннер загрузки
        self.show_loading()
        
        # Добавляем плейсхолдер
        self.loading_label = QLabel("⏳ Загрузка...")
        self.loading_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.loading_label)
        
        # Загружаем с небольшой задержкой для плавности UI
        QTimer.singleShot(100, self._load_content)

    def _on_tab_changed(self, index):
        """При смене вкладки загружаем контент (direct режим)"""
        self._load_category_tab(index)

    def _load_category_tab(self, index):
        """Асинхронная загрузка контента вкладки категории (direct режим)"""
        if not self._strategy_widget:
            return

        widget = self._strategy_widget.widget(index)
        if not widget:
            return

        # Получаем category_key из property или из списка
        category_key = widget.property("category_key")
        if not category_key and hasattr(self._strategy_widget, '_tab_category_keys'):
            keys = self._strategy_widget._tab_category_keys
            if 0 <= index < len(keys):
                category_key = keys[index]

        if not category_key:
            log(f"Не удалось получить category_key для вкладки {index}", "WARNING")
            return

        # Проверяем, загружена ли уже вкладка
        if hasattr(widget, '_loaded') and widget._loaded:
            return

        # Проверяем, не загружается ли уже
        if hasattr(widget, '_loading') and widget._loading:
            return

        widget._loading = True

        # Показываем спиннер загрузки
        self._show_loading_indicator(widget)

        # Запускаем асинхронную загрузку
        from strategy_menu.workers import CategoryTabLoader

        loader = CategoryTabLoader(category_key)
        thread = QThread()
        loader.moveToThread(thread)

        thread.started.connect(loader.run)
        loader.finished.connect(lambda cat, strats, favs, sel:
                               self._on_category_loaded(widget, index, cat, strats, favs, sel))
        loader.error.connect(lambda cat, err:
                            self._on_category_error(widget, cat, err))
        loader.finished.connect(thread.quit)
        loader.finished.connect(loader.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Сохраняем ссылки чтобы не удалились раньше времени
        widget._loader_thread = thread
        widget._loader = loader

        thread.start()

    def _show_loading_indicator(self, widget):
        """Показывает спиннер загрузки на вкладке"""
        # Очищаем существующий контент
        old_layout = widget.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            old_layout = QVBoxLayout(widget)

        old_layout.setContentsMargins(0, 0, 0, 0)
        old_layout.setSpacing(0)

        # Создаем контейнер со спиннером
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner = Win11Spinner(size=24, color="#60cdff")
        container_layout.addWidget(spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        old_layout.addWidget(container)

    def _on_category_loaded(self, widget, index, category_key, strategies_dict, favorites_list, current_selection):
        """Callback после успешной загрузки данных категории"""
        widget._loading = False

        if not strategies_dict:
            widget._loaded = True
            return

        # Строим UI в главном потоке
        self._build_category_ui(widget, index, category_key, strategies_dict, favorites_list, current_selection)

    def _on_category_error(self, widget, category_key, error_msg):
        """Callback при ошибке загрузки категории"""
        widget._loading = False
        log(f"Ошибка загрузки категории {category_key}: {error_msg}", "ERROR")

    def _build_category_ui(self, widget, index, category_key, strategies_dict, favorites_list, current_selection):
        """Создаёт UI элементы категории из загруженных данных"""
        try:
            from strategy_menu.widgets_favorites import FavoriteCompactStrategyItem

            favorites_set = set(favorites_list)

            # Разделяем на избранные и остальные
            favorite_strategies = {k: v for k, v in strategies_dict.items() if k in favorites_set}
            regular_strategies = {k: v for k, v in strategies_dict.items() if k not in favorites_set}

            # Очищаем виджет
            old_layout = widget.layout()
            if old_layout:
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            else:
                old_layout = QVBoxLayout(widget)

            old_layout.setContentsMargins(0, 0, 0, 0)
            old_layout.setSpacing(0)

            # Создаём scroll area
            scroll = ScrollBlockingScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet("QScrollArea{background:transparent;border:none}QScrollBar:vertical{background:rgba(255,255,255,0.05);width:6px}QScrollBar::handle:vertical{background:rgba(255,255,255,0.2);border-radius:3px}")

            content = QWidget()
            content.setStyleSheet("background:transparent")
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(8, 8, 8, 8)
            content_layout.setSpacing(4)

            log(f"Категория {category_key}: текущий выбор = {current_selection}", "DEBUG")

            # Создаём группу радиокнопок
            button_group = QButtonGroup(content)
            button_group.setExclusive(True)

            # === ИЗБРАННЫЕ (вверху) ===
            if favorite_strategies:
                fav_header = QLabel(f"★ Избранные ({len(favorite_strategies)})")
                fav_header.setStyleSheet("""
                    QLabel {
                        color: #ffc107;
                        font-size: 11px;
                        font-weight: 600;
                        padding: 6px 10px;
                        background: rgba(255, 193, 7, 0.08);
                        border-radius: 4px;
                        margin-bottom: 4px;
                    }
                """)
                content_layout.addWidget(fav_header)

                for strategy_id, strategy_data in favorite_strategies.items():
                    item = FavoriteCompactStrategyItem(
                        strategy_id=strategy_id,
                        strategy_data=strategy_data,
                        category_key=category_key,
                        parent=content
                    )
                    button_group.addButton(item.radio)
                    if strategy_id == current_selection:
                        item.radio.setChecked(True)
                    item.clicked.connect(lambda sid=strategy_id, cat=category_key:
                                       self._on_strategy_item_clicked(cat, sid))
                    item.favoriteToggled.connect(lambda sid, is_fav, cat=category_key, idx=index:
                                                self._on_favorite_toggled_direct(cat, idx))
                    content_layout.addWidget(item)

            # === ОСТАЛЬНЫЕ СТРАТЕГИИ ===
            if regular_strategies:
                if favorite_strategies:
                    # Разделитель
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setStyleSheet("background: rgba(255, 255, 255, 0.08); margin: 8px 0;")
                    content_layout.addWidget(separator)

                for strategy_id, strategy_data in regular_strategies.items():
                    item = FavoriteCompactStrategyItem(
                        strategy_id=strategy_id,
                        strategy_data=strategy_data,
                        category_key=category_key,
                        parent=content
                    )
                    button_group.addButton(item.radio)
                    if strategy_id == current_selection:
                        item.radio.setChecked(True)
                    item.clicked.connect(lambda sid=strategy_id, cat=category_key:
                                       self._on_strategy_item_clicked(cat, sid))
                    item.favoriteToggled.connect(lambda sid, is_fav, cat=category_key, idx=index:
                                                self._on_favorite_toggled_direct(cat, idx))
                    content_layout.addWidget(item)

            content_layout.addStretch()
            scroll.setWidget(content)
            old_layout.addWidget(scroll)

            widget._loaded = True
            widget._category_key = category_key
            log(f"Загружена категория: {category_key}", "DEBUG")

        except Exception as e:
            log(f"Ошибка построения UI категории {category_key}: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
    
    def _on_favorite_toggled_direct(self, category_key, tab_index):
        """Обработчик изменения избранного в Direct режиме - перезагружает вкладку"""
        if not self._strategy_widget:
            return

        widget = self._strategy_widget.widget(tab_index)
        if widget:
            widget._loaded = False
            widget._loading = False  # Сбрасываем флаг загрузки
            self._load_category_tab(tab_index)

    def _setup_rating_callback(self):
        """Подписывается на изменение рейтингов стратегий"""
        try:
            from strategy_menu.args_preview_dialog import preview_manager
            preview_manager.add_rating_change_callback(self._on_rating_changed)
        except Exception as e:
            log(f"Ошибка подписки на callback рейтинга: {e}", "WARNING")

    def _on_rating_changed(self, strategy_id, new_rating):
        """Обновляет подсветку при изменении рейтинга стратегии"""
        if not self._strategy_widget:
            return

        # Перезагружаем текущую вкладку для обновления подсветки
        current_index = self._strategy_widget.currentIndex()
        if current_index >= 0:
            widget = self._strategy_widget.widget(current_index)
            if widget:
                widget._loaded = False
                self._load_category_tab(current_index)

    def _update_dpi_filters_display(self):
        """Обновляет отображение фильтров на странице DPI Settings"""
        try:
            from strategy_menu.strategy_lists_separated import calculate_required_filters

            # Вычисляем нужные фильтры по текущим выбранным категориям
            filters = calculate_required_filters(self.category_selections)

            # Обновляем UI на странице DPI Settings
            app = self.parent_app
            if hasattr(app, 'dpi_settings_page') and app.dpi_settings_page:
                app.dpi_settings_page.update_filter_display(filters)
        except Exception as e:
            log(f"Ошибка обновления отображения фильтров: {e}", "WARNING")

    def disable_categories_for_filter(self, filter_key: str, categories_to_disable: list):
        """
        Отключает категории при ручном выключении фильтра.

        Вызывается из DpiSettingsPage когда пользователь отключает фильтр.
        Устанавливает стратегию "none" для всех зависимых категорий.

        Args:
            filter_key: Ключ фильтра (например 'tcp_443')
            categories_to_disable: Список ключей категорий для отключения
        """
        if not categories_to_disable:
            return

        log(f"Отключаю {len(categories_to_disable)} категорий из-за отключения фильтра {filter_key}", "INFO")

        try:
            from strategy_menu import save_direct_strategy_selection, combine_strategies
            from strategy_menu.strategies_registry import registry

            # Получаем все ключи категорий для определения индексов вкладок
            all_keys = registry.get_all_category_keys()

            # Отключаем каждую категорию
            for category_key in categories_to_disable:
                save_direct_strategy_selection(category_key, "none")
                self.category_selections[category_key] = "none"
                log(f"  → Отключена категория: {category_key}", "DEBUG")

            # Обновляем UI вкладок (делаем иконки серыми)
            self._refresh_all_tab_colors()

            # Перезагружаем содержимое вкладок для отключённых категорий
            self._reload_category_tabs(categories_to_disable, all_keys)

            # Обновляем отображение текущих стратегий
            self._update_current_strategies_display()

            # Обновляем отображение фильтров (теперь с меньшим количеством активных)
            self._update_dpi_filters_display()

            # Обновляем командную строку
            if self.cmd_widget:
                self.cmd_widget.generate_command()

            # Проверяем, остались ли активные стратегии
            if not self._has_any_active_strategy():
                log("⚠️ Все стратегии отключены - останавливаем DPI", "INFO")
                app = self.parent_app
                if hasattr(app, 'dpi_controller') and app.dpi_controller:
                    app.dpi_controller.stop_dpi_async()
                return

            # Перезапускаем DPI с новыми настройками
            combined = combine_strategies(**self.category_selections)
            combined_data = {
                'id': 'DIRECT_MODE',
                'name': 'Прямой запуск (Запрет 2)',
                'is_combined': True,
                'args': combined['args'],
                'selections': self.category_selections.copy()
            }

            app = self.parent_app
            if hasattr(app, 'dpi_controller') and app.dpi_controller:
                app.dpi_controller.start_dpi_async(selected_mode=combined_data)

        except Exception as e:
            log(f"Ошибка отключения категорий: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def _reload_category_tabs(self, category_keys: list, all_keys: list):
        """Перезагружает содержимое вкладок для указанных категорий"""
        if not self._strategy_widget:
            return

        for category_key in category_keys:
            try:
                # Находим индекс вкладки по ключу категории
                if category_key in all_keys:
                    tab_index = all_keys.index(category_key)
                    widget = self._strategy_widget.widget(tab_index)
                    if widget:
                        # Сбрасываем флаг загрузки и перезагружаем
                        widget._loaded = False
                        self._load_category_tab(tab_index)
                        log(f"Перезагружена вкладка: {category_key}", "DEBUG")
            except Exception as e:
                log(f"Ошибка перезагрузки вкладки {category_key}: {e}", "WARNING")

    def _refresh_all_tab_colors(self):
        """Обновляет цвета иконок всех вкладок по текущим выборам"""
        if not self._strategy_widget:
            return

        try:
            from strategy_menu.strategies_registry import registry
            all_keys = registry.get_all_category_keys()

            for i, category_key in enumerate(all_keys):
                strategy_id = self.category_selections.get(category_key, "none")
                is_inactive = (strategy_id == "none" or not strategy_id)
                self._strategy_widget.update_tab_icon_color(i, is_inactive=is_inactive)
        except Exception as e:
            log(f"Ошибка обновления цветов вкладок: {e}", "WARNING")

    def _has_any_active_strategy(self, selections: dict = None) -> bool:
        """Проверяет, есть ли хотя бы одна активная стратегия (не 'none')"""
        if selections is None:
            selections = self.category_selections
        
        for strategy_id in selections.values():
            if strategy_id and strategy_id != "none":
                return True
        return False
    
    def _on_strategy_item_clicked(self, category_key: str, strategy_id: str):
        """Обработчик клика по стратегии - сразу применяет и перезапускает winws2"""
        try:
            from strategy_menu import save_direct_strategy_selection, combine_strategies
            from strategy_menu.strategy_lists_separated import calculate_required_filters

            # Сохраняем выбор в реестр (для Direct режима selections сохраняются отдельно)
            save_direct_strategy_selection(category_key, strategy_id)
            self.category_selections[category_key] = strategy_id
            log(f"Выбрана стратегия: {category_key} = {strategy_id}", "INFO")

            # Обновляем цвет иконки вкладки (серая если none, цветная если активна)
            current_tab_index = self._strategy_widget.currentIndex()
            is_inactive = (strategy_id == "none" or not strategy_id)
            self._strategy_widget.update_tab_icon_color(current_tab_index, is_inactive=is_inactive)

            # Обновляем отображение текущих стратегий (читаем из реестра)
            self._update_current_strategies_display()

            # ✅ Обновляем отображение фильтров на странице DPI Settings
            self._update_dpi_filters_display()

            # Обновляем командную строку сразу
            if self.cmd_widget:
                self.cmd_widget.generate_command()
            
            # Проверяем, есть ли хотя бы одна активная стратегия
            if not self._has_any_active_strategy():
                log("⚠️ Нет активных стратегий - останавливаем DPI", "INFO")
                # Останавливаем DPI если все стратегии "none"
                app = self.parent_app
                if hasattr(app, 'dpi_controller') and app.dpi_controller:
                    app.dpi_controller.stop_dpi_async()
                    if hasattr(app, 'current_strategy_label'):
                        app.current_strategy_label.setText("Не выбрана")
                    if hasattr(app, 'current_strategy_name'):
                        app.current_strategy_name = None
                self.show_success()
                return
            
            # Показываем спиннер загрузки
            self.show_loading()
            
            # Создаём комбинированную стратегию
            combined = combine_strategies(**self.category_selections)
            
            # Создаем объект для запуска Direct режима (Запрет 2)
            combined_data = {
                'id': 'DIRECT_MODE',
                'name': 'Прямой запуск (Запрет 2)',
                'is_combined': True,
                'args': combined['args'],
                'selections': self.category_selections.copy()
            }
            
            # Перезапускаем winws2.exe с новыми настройками
            app = self.parent_app
            if hasattr(app, 'dpi_controller') and app.dpi_controller:
                app.dpi_controller.start_dpi_async(selected_mode=combined_data)
                log(f"Применена стратегия: {category_key} = {strategy_id}", "DEBUG")
                
                # Обновляем UI
                if hasattr(app, 'current_strategy_label'):
                    app.current_strategy_label.setText("Прямой запуск (Запрет 2)")
                if hasattr(app, 'current_strategy_name'):
                    app.current_strategy_name = "Прямой запуск (Запрет 2)"
                
                # Запускаем мониторинг реального статуса процесса
                self._start_process_monitoring()
            else:
                # Если нет dpi_controller - сразу показываем галочку
                self.show_success()
            
            self.strategy_selected.emit("combined", "Прямой запуск (Запрет 2)")
            
        except Exception as e:
            log(f"Ошибка применения: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            self.show_success()  # При ошибке тоже убираем спиннер
            
    def _reload_strategies(self):
        """Перезагружает стратегии (direct режим)"""
        try:
            from strategy_menu.strategies_registry import registry
            registry.reload_strategies()
            
            self.stop_watching()  # Останавливаем мониторинг при перезагрузке
            self._current_mode = None
            self._initialized = False
            self._clear_content()
            
            self.loading_label = QLabel("⏳ Перезагрузка...")
            self.loading_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
            self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(self.loading_label)
            
            # Загружаем сразу
            QTimer.singleShot(0, self._load_content)
            
        except Exception as e:
            log(f"Ошибка перезагрузки: {e}", "ERROR")
            
    def _open_folder(self):
        """Открывает папку стратегий"""
        try:
            from config import STRATEGIES_FOLDER
            import os
            os.startfile(STRATEGIES_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            
    def _clear_all(self):
        """Сбрасывает все стратегии в 'none' и останавливает DPI"""
        try:
            from strategy_menu import save_direct_strategy_selections
            from strategy_menu.strategies_registry import registry

            # Устанавливаем все стратегии в "none"
            none_selections = {key: "none" for key in registry.get_all_category_keys()}
            save_direct_strategy_selections(none_selections)
            self.category_selections = none_selections

            # ✅ Обновляем отображение фильтров (теперь все должны быть выключены)
            self._update_dpi_filters_display()

            # Останавливаем DPI, так как нет активных стратегий
            app = self.parent_app
            if hasattr(app, 'dpi_controller') and app.dpi_controller:
                app.dpi_controller.stop_dpi_async()
                log("DPI остановлен после сброса стратегий", "INFO")
                if hasattr(app, 'current_strategy_label'):
                    app.current_strategy_label.setText("Не выбрана")
                if hasattr(app, 'current_strategy_name'):
                    app.current_strategy_name = None

            # Перезагружаем интерфейс (командная строка обновится внутри _load_direct_mode)
            self._reload_strategies()

            log("Все стратегии выключены (установлены в 'none')", "INFO")

        except Exception as e:
            log(f"Ошибка выключения стратегий: {e}", "ERROR")

    def _reset_to_defaults(self):
        """Сбрасывает настройки реестра к значениям по умолчанию"""
        try:
            from config.reg import reg_delete_all_values
            from strategy_menu import DIRECT_STRATEGY_KEY, invalidate_direct_selections_cache

            # Удаляем все значения из реестра (стратегии будут браться по умолчанию)
            reg_delete_all_values(DIRECT_STRATEGY_KEY)
            invalidate_direct_selections_cache()

            log("Настройки стратегий очищены из реестра", "INFO")

            # Перезагружаем интерфейс (теперь загрузятся значения по умолчанию)
            self._reload_strategies()

            # Перезапускаем DPI с настройками по умолчанию
            app = self.parent_app
            if hasattr(app, 'dpi_controller') and app.dpi_controller:
                from strategy_menu import get_direct_strategy_selections, combine_strategies

                # Загружаем настройки по умолчанию
                self.category_selections = get_direct_strategy_selections()

                # Проверяем, есть ли активные стратегии
                if self._has_any_active_strategy(self.category_selections):
                    combined = combine_strategies(**self.category_selections)
                    combined_data = {
                        'id': 'DIRECT_MODE',
                        'name': 'Прямой запуск (Запрет 2)',
                        'is_combined': True,
                        'args': combined['args'],
                        'selections': self.category_selections.copy()
                    }
                    app.dpi_controller.start_dpi_async(selected_mode=combined_data)
                    log("DPI перезапущен с настройками по умолчанию", "INFO")
                else:
                    app.dpi_controller.stop_dpi_async()
                    log("DPI остановлен (нет активных стратегий по умолчанию)", "INFO")

        except Exception as e:
            log(f"Ошибка сброса к значениям по умолчанию: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def _restart_dpi(self):
        """Перезапускает winws.exe (останавливает и сразу запускает) асинхронно"""
        try:
            app = self.parent_app
            if not app or not hasattr(app, 'dpi_controller'):
                log("DPI контроллер не найден", "ERROR")
                return
            
            # В Direct режимах проверяем наличие активных стратегий
            from strategy_menu import get_strategy_launch_method, get_direct_strategy_selections
            if get_strategy_launch_method() in ("direct", "direct_orchestra"):
                selections = get_direct_strategy_selections()
                if not self._has_any_active_strategy(selections):
                    log("⚠️ Нет активных стратегий - перезапуск невозможен", "WARNING")
                    QMessageBox.warning(
                        self,
                        "Нет стратегий",
                        "Выберите хотя бы одну стратегию для запуска."
                    )
                    return
            
            # Запускаем анимацию вращения иконки
            self._start_restart_animation()
            
            # Проверяем, запущен ли процесс
            if not app.dpi_starter.check_process_running_wmi(silent=True):
                log("🔄 DPI не запущен, просто запускаем...", "INFO")
                self._start_dpi_after_stop()
                return
                
            log("🔄 Перезапуск DPI...", "INFO")
            
            # Асинхронно останавливаем
            app.dpi_controller.stop_dpi_async()
            
            # Запускаем таймер для проверки остановки и перезапуска
            self._restart_check_count = 0
            self._restart_timer = QTimer(self)
            self._restart_timer.timeout.connect(self._check_stopped_and_restart)
            self._restart_timer.start(300)  # Проверяем каждые 300мс
            
        except Exception as e:
            self._stop_restart_animation()
            log(f"Ошибка перезапуска DPI: {e}", "ERROR")
    
    def _check_stopped_and_restart(self):
        """Проверяет остановку DPI и запускает заново"""
        try:
            app = self.parent_app
            self._restart_check_count += 1
            
            # Максимум 30 проверок (9 секунд)
            if self._restart_check_count > 30:
                self._restart_timer.stop()
                log("⚠️ Таймаут ожидания остановки DPI", "WARNING")
                # Всё равно пробуем запустить
                self._start_dpi_after_stop()
                return
            
            # Проверяем, остановлен ли процесс
            if not app.dpi_starter.check_process_running_wmi(silent=True):
                self._restart_timer.stop()
                # Небольшая пауза и запуск
                QTimer.singleShot(200, self._start_dpi_after_stop)
                
        except Exception as e:
            self._restart_timer.stop()
            self._stop_restart_animation()
            log(f"Ошибка проверки остановки: {e}", "ERROR")
    
    def _start_dpi_after_stop(self):
        """Запускает DPI после остановки"""
        try:
            app = self.parent_app
            if not app or not hasattr(app, 'dpi_controller'):
                self._stop_restart_animation()
                return
                
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if launch_method in ("direct", "direct_orchestra"):
                # Прямой запуск - берём текущие настройки и формируем правильный формат
                from strategy_menu import get_direct_strategy_selections
                from strategy_menu.strategy_lists_separated import combine_strategies

                selections = get_direct_strategy_selections()

                # Проверяем, есть ли хотя бы одна активная стратегия
                if not self._has_any_active_strategy(selections):
                    log("⚠️ Нет активных стратегий - запуск отменён", "WARNING")
                    self._stop_restart_animation()
                    return

                combined = combine_strategies(**selections)
                
                # Формируем данные в правильном формате для start_dpi_async
                selected_mode = {
                    'is_combined': True,
                    'name': combined.get('description', 'Перезапуск'),
                    'args': combined.get('args', ''),
                    'category_strategies': combined.get('category_strategies', {})
                }
                app.dpi_controller.start_dpi_async(selected_mode=selected_mode)
            else:
                # BAT режим
                app.dpi_controller.start_dpi_async()
                
            log("✅ DPI перезапущен", "INFO")
            
            # Останавливаем анимацию через небольшую задержку для визуального эффекта
            QTimer.singleShot(800, self._stop_restart_animation)
            
        except Exception as e:
            self._stop_restart_animation()
            log(f"Ошибка запуска DPI после перезапуска: {e}", "ERROR")
    
    def _start_restart_animation(self):
        """Запускает анимацию вращения иконки перезапуска"""
        if hasattr(self, '_restart_btn') and hasattr(self, '_restart_icon_spinning'):
            self._restart_btn.setIcon(self._restart_icon_spinning)
            self._restart_spin_animation.start()
    
    def _stop_restart_animation(self):
        """Останавливает анимацию вращения иконки перезапуска"""
        if hasattr(self, '_restart_btn') and hasattr(self, '_restart_icon_normal'):
            self._restart_spin_animation.stop()
            self._restart_btn.setIcon(self._restart_icon_normal)
            
    def _generate_command_line(self):
        """Генерирует командную строку"""
        if self.cmd_widget:
            self.cmd_widget.generate_command()
            
    def _show_cmd(self):
        """Разворачивает/сворачивает виджет командной строки"""
        if hasattr(self, 'cmd_widget') and self.cmd_widget:
            self.cmd_widget.generate_command()
            
    def _apply_strategy(self):
        """Применяет выбранную стратегию (direct режим)"""
        try:
            from strategy_menu import combine_strategies, save_direct_strategy_selections
            
            save_direct_strategy_selections(self.category_selections)
            combined = combine_strategies(**self.category_selections)
            self.strategy_selected.emit("combined", "Прямой запуск")
            
            log("Стратегия применена", "INFO")
            
        except Exception as e:
            log(f"Ошибка применения: {e}", "ERROR")
            QMessageBox.critical(self.window(), "Ошибка", f"Не удалось применить стратегию:\n{e}")
        
    def _update_current_strategies_display(self):
        """Обновляет отображение списка активных стратегий с Font Awesome иконками"""
        try:
            from strategy_menu import get_strategy_launch_method, get_direct_strategy_selections
            from strategy_menu.strategies_registry import registry

            if get_strategy_launch_method() not in ("direct", "direct_orchestra"):
                self.current_strategy_label.setToolTip("")
                self.current_strategy_label.show()
                self.current_strategy_container.hide()
                self._has_hidden_strategies = False
                self._tooltip_strategies_data = []
                return
            
            selections = get_direct_strategy_selections()
            
            # Собираем только активные (не "none") стратегии
            tooltip_data = []  # Данные для красивого тултипа: (icon_name, icon_color, cat_name, strat_name)
            icons_data = []    # Данные для иконок: (icon_name, icon_color, strategy_name)
            
            for cat_key in registry.get_all_category_keys():
                strat_id = selections.get(cat_key)
                if strat_id and strat_id != "none":
                    cat_info = registry.get_category_info(cat_key)
                    if not cat_info:
                        continue
                    
                    strategy_name = registry.get_strategy_name_safe(cat_key, strat_id)
                    icon_name = cat_info.icon_name or 'fa5s.globe'
                    icon_color = cat_info.icon_color or '#60cdff'
                    cat_full = cat_info.full_name
                    
                    icons_data.append((icon_name, icon_color, strategy_name))
                    tooltip_data.append((icon_name, icon_color, cat_full, strategy_name))
            
            # Сохраняем данные для тултипа
            self._tooltip_strategies_data = tooltip_data
            
            if icons_data:
                # Очищаем старые иконки
                while self.current_icons_layout.count():
                    item = self.current_icons_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                
                # Скрываем текстовый лейбл, показываем иконки
                self.current_strategy_label.hide()
                self.current_strategy_container.show()
                
                # Добавляем все иконки
                for icon_name, icon_color, strat_name in icons_data:
                    icon_label = QLabel()
                    try:
                        pixmap = qta.icon(icon_name, color=icon_color).pixmap(16, 16)
                        icon_label.setPixmap(pixmap)
                    except:
                        pixmap = qta.icon('fa5s.globe', color='#60cdff').pixmap(16, 16)
                        icon_label.setPixmap(pixmap)
                    icon_label.setFixedSize(18, 18)
                    icon_label.setToolTip(f"{strat_name}")
                    self.current_icons_layout.addWidget(icon_label)

                self._has_hidden_strategies = len(icons_data) > 3  # Тултип если > 3
                
            else:
                # Нет активных стратегий
                self.current_strategy_container.hide()
                self.current_strategy_label.show()
                self.current_strategy_label.setText("Не выбрана")
                self.current_strategy_label.setToolTip("")
                self._has_hidden_strategies = False
                
        except Exception as e:
            log(f"Ошибка обновления отображения: {e}", "ERROR")
    
    def eventFilter(self, obj, event):
        """Обработчик событий для красивого тултипа"""
        if obj == self.current_strategy_container:
            from PyQt6.QtCore import QEvent
            
            if event.type() == QEvent.Type.Enter:
                # При наведении показываем красивый тултип если есть стратегии
                if self._has_hidden_strategies and hasattr(self, '_tooltip_strategies_data') and self._tooltip_strategies_data:
                    self._show_strategies_tooltip()
                    
            elif event.type() == QEvent.Type.Leave:
                # При уходе скрываем тултип
                self._hide_strategies_tooltip()
        
        return super().eventFilter(obj, event)
    
    def _show_strategies_tooltip(self):
        """Показывает красивый тултип со списком стратегий"""
        try:
            from ui.widgets.strategies_tooltip import strategies_tooltip_manager
            
            if hasattr(self, '_tooltip_strategies_data') and self._tooltip_strategies_data:
                strategies_tooltip_manager.show(self._tooltip_strategies_data, follow=True)
        except Exception as e:
            log(f"Ошибка показа тултипа стратегий: {e}", "DEBUG")
    
    def _hide_strategies_tooltip(self):
        """Скрывает тултип стратегий"""
        try:
            from ui.widgets.strategies_tooltip import strategies_tooltip_manager
            strategies_tooltip_manager.hide(delay=150)
        except Exception as e:
            pass
            
    def update_current_strategy(self, name: str):
        """Обновляет отображение текущей стратегии"""
        try:
            from strategy_menu import get_strategy_launch_method
            if get_strategy_launch_method() in ("direct", "direct_orchestra"):
                self._update_current_strategies_display()
            elif name and name != "Автостарт DPI отключен":
                self.current_strategy_label.setText(name)
            else:
                self.current_strategy_label.setText("Не выбрана")
        except:
            if name and name != "Автостарт DPI отключен":
                self.current_strategy_label.setText(name)
            else:
                self.current_strategy_label.setText("Не выбрана")

    def show_loading(self):
        """Показывает спиннер загрузки при перезапуске DPI"""
        if hasattr(self, 'status_indicator'):
            self.status_indicator.show_loading()
            
    def show_success(self):
        """Показывает галочку после успешного запуска DPI"""
        if hasattr(self, 'status_indicator'):
            self.status_indicator.show_success()
    
    def _start_process_monitoring(self):
        """Запускает мониторинг статуса процесса winws/winws2"""
        self._process_check_attempts = 0
        if not self._process_check_timer.isActive():
            # Небольшая задержка перед первой проверкой - даем процессу время на инициализацию
            QTimer.singleShot(300, lambda: self._process_check_timer.start(200))
            log("🔍 Начат мониторинг запуска процесса", "DEBUG")
    
    def _stop_process_monitoring(self):
        """Останавливает мониторинг процесса"""
        if self._process_check_timer.isActive():
            self._process_check_timer.stop()
            log("⏹️ Мониторинг запуска процесса остановлен", "DEBUG")
        self._stop_absolute_timeout()
    
    def _stop_absolute_timeout(self):
        """Останавливает абсолютный таймаут защиты"""
        if self._absolute_timeout_timer.isActive():
            self._absolute_timeout_timer.stop()
            log("🛡️ Таймаут защиты спиннера остановлен", "DEBUG")
    
    def _on_absolute_timeout(self):
        """Вызывается при превышении абсолютного таймаута"""
        log("⏱️ ТАЙМАУТ: Превышено время ожидания запуска (10 секунд)", "WARNING")
        log("⚠️ Процесс мог зависнуть или запускается слишком долго", "WARNING")
        
        # Принудительно останавливаем мониторинг и показываем галочку
        self._stop_process_monitoring()
        self.show_success()
        
        # Показываем уведомление пользователю
        try:
            QMessageBox.warning(
                self,
                "Долгий запуск",
                "Процесс запускается дольше обычного.\n\n"
                "Проверьте логи и статус процесса.\n"
                "Возможно потребуется перезапуск."
            )
        except:
            pass
    
    def _check_process_status(self):
        """Проверяет реальный статус процесса winws/winws2"""
        try:
            self._process_check_attempts += 1
            
            # Получаем dpi_starter
            app = self.parent_app
            if not app or not hasattr(app, 'dpi_starter'):
                log("dpi_starter не найден для проверки процесса", "DEBUG")
                self._stop_process_monitoring()
                self.show_success()  # Показываем галочку по умолчанию
                return
            
            # Проверяем запущен ли процесс через быстрый psutil метод (~1-10ms)
            is_running = app.dpi_starter.check_process_running_wmi(silent=True)
            
            if is_running:
                # Процесс реально запущен - показываем галочку
                log(f"✅ Процесс winws подтвержден как запущенный (попытка {self._process_check_attempts})", "INFO")
                self._stop_process_monitoring()  # Это автоматически остановит и абсолютный таймаут
                self.show_success()
                return
            
            # Проверяем лимит попыток
            if self._process_check_attempts >= self._max_check_attempts:
                log(f"⚠️ Превышено максимальное время ожидания запуска процесса ({self._max_check_attempts * 0.2:.1f}с)", "WARNING")
                self._stop_process_monitoring()  # Это автоматически остановит и абсолютный таймаут
                self.show_success()  # Всё равно показываем галочку
                return
                
        except Exception as e:
            log(f"Ошибка проверки статуса процесса: {e}", "DEBUG")
            self._stop_process_monitoring()  # Это автоматически остановит и абсолютный таймаут
            self.show_success()
    
    def closeEvent(self, event):
        """Очистка ресурсов при закрытии"""
        try:
            self.stop_watching()
            self._stop_process_monitoring()
            self._stop_absolute_timeout()
            
            if self._file_watcher:
                self._file_watcher.directoryChanged.disconnect()
                self._file_watcher.fileChanged.disconnect()
                self._file_watcher.deleteLater()
                self._file_watcher = None
                log("File watcher очищен", "DEBUG")
        except Exception as e:
            log(f"Ошибка очистки ресурсов: {e}", "DEBUG")
        
        super().closeEvent(event)


# Для совместимости
Win11ComboBox = QComboBox
