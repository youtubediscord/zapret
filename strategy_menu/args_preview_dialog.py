"""
Компактное окно информации о стратегии - Windows 11 Fluent Design
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTextEdit, QPushButton, QWidget,
                            QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, 
                          pyqtSignal, QRectF)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QBrush, QPen

from log import log


class ArgsPreviewDialog(QDialog):
    """Компактное окно информации о стратегии - Fluent Design"""

    closed = pyqtSignal()
    rating_changed = pyqtSignal(str, str)  # strategy_id, new_rating (или None)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(150)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.init_ui()
        self.setWindowOpacity(0.0)
        
    def init_ui(self):
        """Инициализация компактного интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Контейнер
        self.container = QWidget()
        self.container.setObjectName("fluentContainer")
        
        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(8)
        
        # === Заголовок ===
        header = QHBoxLayout()
        header.setSpacing(8)
        
        self.title_label = QLabel()
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        header.addWidget(self.title_label, 1)
        
        # Кнопка закрытия
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_dialog)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,0.5);
                border: none;
                font-size: 18px;
                font-weight: 400;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: #fff;
            }
        """)
        header.addWidget(close_btn)
        container_layout.addLayout(header)
        
        # === Автор ===
        self.author_label = QLabel()
        self.author_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        self.author_label.hide()
        container_layout.addWidget(self.author_label)
        
        # === Информационная строка ===
        self.info_panel = QLabel()
        self.info_panel.setWordWrap(True)
        self.info_panel.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.7);
                font-size: 11px;
                padding: 6px 10px;
                background: rgba(255,255,255,0.04);
                border-radius: 6px;
            }
        """)
        self.info_panel.hide()
        container_layout.addWidget(self.info_panel)
        
        # === Аргументы ===
        self.args_widget = QWidget()
        args_layout = QVBoxLayout(self.args_widget)
        args_layout.setContentsMargins(0, 4, 0, 0)
        args_layout.setSpacing(6)
        
        # Заголовок аргументов
        args_header = QHBoxLayout()
        args_title = QLabel("Аргументы запуска:")
        args_title.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 11px;")
        args_header.addWidget(args_title)
        args_header.addStretch()
        
        self.copy_button = QPushButton("Копировать")
        self.copy_button.setFixedHeight(22)
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self.copy_args)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.7);
                border: none;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: #fff;
            }
        """)
        args_header.addWidget(self.copy_button)
        args_layout.addLayout(args_header)
        
        # Текст аргументов
        self.args_text = QTextEdit()
        self.args_text.setReadOnly(True)
        self.args_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 6px;
                color: rgba(255,255,255,0.7);
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 10px;
                padding: 8px;
            }
            QScrollBar:vertical {
                width: 4px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                border-radius: 2px;
            }
        """)
        self.args_text.setMinimumHeight(60)
        self.args_text.setMaximumHeight(120)
        args_layout.addWidget(self.args_text)
        
        container_layout.addWidget(self.args_widget)
        
        # === Метка стратегии ===
        self.label_widget = QLabel()
        self.label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_widget.hide()
        container_layout.addWidget(self.label_widget)
        
        # === Кнопки оценки ===
        rating_widget = QWidget()
        rating_layout = QHBoxLayout(rating_widget)
        rating_layout.setContentsMargins(0, 4, 0, 0)
        rating_layout.setSpacing(8)
        
        rating_label = QLabel("Оценить:")
        rating_label.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        rating_layout.addWidget(rating_label)
        rating_layout.addStretch()
        
        self.working_button = QPushButton("РАБОЧАЯ")
        self.working_button.setFixedHeight(26)
        self.working_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.working_button.clicked.connect(lambda: self._toggle_rating('working'))
        rating_layout.addWidget(self.working_button)
        
        self.broken_button = QPushButton("НЕРАБОЧАЯ")
        self.broken_button.setFixedHeight(26)
        self.broken_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.broken_button.clicked.connect(lambda: self._toggle_rating('broken'))
        rating_layout.addWidget(self.broken_button)
        
        container_layout.addWidget(rating_widget)
        
        # === Подсказка ===
        hint = QLabel("ESC — закрыть")
        hint.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(hint)
        
        main_layout.addWidget(self.container)
        self.setFixedWidth(420)
        
        # Обновляем стили кнопок
        self._update_rating_buttons()
        
    def paintEvent(self, event):
        """Рисуем Fluent фон"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.container.geometry()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 12, 12)
        
        # Градиент фона
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(48, 48, 48, 252))
        gradient.setColorAt(1, QColor(36, 36, 36, 252))
        painter.fillPath(path, QBrush(gradient))
        
        # Рамка
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1))
        painter.drawPath(path)
        
    def set_strategy_data(self, strategy_data, strategy_id=None, source_widget=None, category_key=None):
        """Устанавливает данные стратегии"""
        self.current_strategy_id = strategy_id
        self.current_category_key = category_key
        self.source_widget = source_widget
        
        # Заголовок
        name = strategy_data.get('name', strategy_id or 'Стратегия')
        self.title_label.setText(name)
        
        # Автор
        author = strategy_data.get('author')
        if author and author != 'unknown':
            self.author_label.setText(f"Автор: {author}")
            self.author_label.show()
        else:
            self.author_label.hide()
        
        # Инфо панель
        info_parts = []
        if strategy_id:
            info_parts.append(f"<span style='color:#60cdff'>ID:</span> {strategy_id}")
        version = strategy_data.get('version')
        if version:
            info_parts.append(f"<span style='color:#4ade80'>v{version}</span>")
        provider = strategy_data.get('provider', 'universal')
        provider_names = {'universal': 'All', 'rostelecom': 'Ростелеком', 'mts': 'МТС', 
                         'megafon': 'МегаФон', 'beeline': 'Билайн'}
        info_parts.append(f"<span style='color:#a78bfa'>{provider_names.get(provider, provider)}</span>")
        
        if info_parts:
            self.info_panel.setText(" • ".join(info_parts))
            self.info_panel.show()
        else:
            self.info_panel.hide()
        
        # Аргументы
        args = strategy_data.get('args', '')
        if args:
            self.args_text.setPlainText(args[:500] + ('...' if len(args) > 500 else ''))
            self.original_args = args
            self.args_widget.show()
        else:
            self.args_widget.hide()
            self.original_args = ""
        
        # Метка
        from .constants import LABEL_TEXTS, LABEL_COLORS
        label = strategy_data.get('label')
        if label and label in LABEL_TEXTS:
            self.label_widget.setText(LABEL_TEXTS[label])
            self.label_widget.setStyleSheet(f"""
                QLabel {{
                    color: {LABEL_COLORS[label]};
                    font-weight: 600;
                    font-size: 11px;
                    padding: 4px 12px;
                    border: 1px solid {LABEL_COLORS[label]};
                    border-radius: 4px;
                }}
            """)
            self.label_widget.show()
        else:
            self.label_widget.hide()
        
        self._update_rating_buttons()
        self.adjustSize()
    
    def _get_rating_button_style(self, is_active, rating_type):
        """Стиль кнопки оценки"""
        if rating_type == 'working':
            color = '#4ade80'
        else:
            color = '#f87171'
        
        if is_active:
            return f"""
                QPushButton {{
                    background: {color};
                    color: #000;
                    border: none;
                    border-radius: 4px;
                    padding: 0 12px;
                    font-size: 10px;
                    font-weight: 600;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: rgba(255,255,255,0.06);
                    color: rgba(255,255,255,0.6);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 4px;
                    padding: 0 12px;
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.1);
                    color: {color};
                    border-color: {color};
                }}
            """
    
    def _update_rating_buttons(self):
        """Обновляет кнопки оценки"""
        if not hasattr(self, 'current_strategy_id') or not self.current_strategy_id:
            self.working_button.setStyleSheet(self._get_rating_button_style(False, 'working'))
            self.broken_button.setStyleSheet(self._get_rating_button_style(False, 'broken'))
            return

        from strategy_menu import get_strategy_rating
        category_key = getattr(self, 'current_category_key', None)
        current_rating = get_strategy_rating(self.current_strategy_id, category_key)

        self.working_button.setStyleSheet(self._get_rating_button_style(current_rating == 'working', 'working'))
        self.broken_button.setStyleSheet(self._get_rating_button_style(current_rating == 'broken', 'broken'))
    
    def _toggle_rating(self, rating):
        """Переключает оценку"""
        if not hasattr(self, 'current_strategy_id') or not self.current_strategy_id:
            return

        from strategy_menu import toggle_strategy_rating
        category_key = getattr(self, 'current_category_key', None)
        new_rating = toggle_strategy_rating(self.current_strategy_id, rating, category_key)
        self._update_rating_buttons()
        # Уведомляем об изменении рейтинга
        self.rating_changed.emit(self.current_strategy_id, new_rating or "")
    
    def copy_args(self):
        """Копирует аргументы"""
        if hasattr(self, 'original_args'):
            QApplication.clipboard().setText(self.original_args)
            self.copy_button.setText("✓ Скопировано")
            self.copy_button.setStyleSheet("""
                QPushButton {
                    background: rgba(74, 222, 128, 0.2);
                    color: #4ade80;
                    border: none;
                    border-radius: 4px;
                    padding: 0 10px;
                    font-size: 11px;
                }
            """)
            QTimer.singleShot(1500, self._reset_copy_button)
    
    def _reset_copy_button(self):
        self.copy_button.setText("Копировать")
        self.copy_button.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.7);
                border: none;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: #fff;
            }
        """)
    
    def show_animated(self, pos=None):
        if pos:
            self.move(pos)
        self.show()
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
    
    def close_dialog(self):
        self.hide_animated()
    
    def hide_animated(self):
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(self._on_hide_finished)
        self.opacity_animation.start()
    
    def _on_hide_finished(self):
        try:
            self.opacity_animation.finished.disconnect(self._on_hide_finished)
        except:
            pass
        self.hide()
        self.closed.emit()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_dialog()
        else:
            super().keyPressEvent(event)


class StrategyPreviewManager:
    """Менеджер окна предпросмотра"""

    _instance = None
    _rating_change_callbacks = []  # Callback'и для уведомления об изменении рейтинга

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.preview_dialog = None
            cls._instance._rating_change_callbacks = []
        return cls._instance

    def add_rating_change_callback(self, callback):
        """Добавляет callback для уведомления об изменении рейтинга"""
        if callback not in self._rating_change_callbacks:
            self._rating_change_callbacks.append(callback)

    def remove_rating_change_callback(self, callback):
        """Удаляет callback"""
        if callback in self._rating_change_callbacks:
            self._rating_change_callbacks.remove(callback)

    def _on_rating_changed(self, strategy_id, new_rating):
        """Вызывается при изменении рейтинга стратегии"""
        for callback in self._rating_change_callbacks:
            try:
                callback(strategy_id, new_rating)
            except Exception as e:
                log(f"Ошибка в callback рейтинга: {e}", "ERROR")

    def show_preview(self, widget, strategy_id, strategy_data, category_key=None):
        # Проверяем что старый диалог ещё существует и не удалён Qt
        try:
            if self.preview_dialog is not None:
                # Проверяем что C++ объект не удалён
                try:
                    if self.preview_dialog.isVisible():
                        self.preview_dialog.close()
                except RuntimeError:
                    # C++ объект уже удалён
                    pass
                self.preview_dialog = None
        except RuntimeError:
            self.preview_dialog = None

        self.preview_dialog = ArgsPreviewDialog(widget)
        self.preview_dialog.closed.connect(self._on_preview_closed)
        self.preview_dialog.rating_changed.connect(self._on_rating_changed)
        self.preview_dialog.set_strategy_data(strategy_data, strategy_id, source_widget=widget, category_key=category_key)

        cursor_pos = widget.mapToGlobal(widget.rect().center())

        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            if cursor_pos.x() + self.preview_dialog.width() > screen_rect.right():
                cursor_pos.setX(screen_rect.right() - self.preview_dialog.width() - 10)
            if cursor_pos.y() + 300 > screen_rect.bottom():
                cursor_pos.setY(screen_rect.bottom() - 300)

        self.preview_dialog.show_animated(cursor_pos)
    
    def _on_preview_closed(self):
        if self.preview_dialog is not None:
            try:
                self.preview_dialog.deleteLater()
            except RuntimeError:
                pass  # C++ объект уже удалён
            self.preview_dialog = None
    
    def cleanup(self):
        if self.preview_dialog is not None:
            try:
                self.preview_dialog.close()
                self.preview_dialog.deleteLater()
            except RuntimeError:
                pass  # C++ объект уже удалён
            self.preview_dialog = None


preview_manager = StrategyPreviewManager()
