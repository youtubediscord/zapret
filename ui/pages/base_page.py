# ui/pages/base_page.py
"""Базовый класс для страниц"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy, QPlainTextEdit, QTextEdit
from PyQt6.QtGui import QFont


class ScrollBlockingPlainTextEdit(QPlainTextEdit):
    """QPlainTextEdit который не пропускает прокрутку к родителю"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Запрещаем перетаскивание окна при взаимодействии с редактором
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


class ScrollBlockingTextEdit(QTextEdit):
    """QTextEdit который не пропускает прокрутку к родителю"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Запрещаем перетаскивание окна при взаимодействии с редактором
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


class BasePage(QScrollArea):
    """Базовый класс для страниц контента"""
    
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.parent_app = parent
        
        # Настройка ScrollArea
        self.setWidgetResizable(True)
        # ✅ Отключаем горизонтальный скролл - контент должен вписываться в ширину
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 0.05);
                width: 14px;
                border-radius: 7px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 7px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        # Контейнер контента (с явным родителем!)
        self.content = QWidget(self)  # ✅ Родитель = self (QScrollArea)
        self.content.setStyleSheet("background-color: transparent;")
        # ✅ Политика размера: предпочитает минимальную ширину, не растягивается бесконечно
        self.content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setWidget(self.content)
        
        # Основной layout
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(32, 24, 32, 24)
        self.layout.setSpacing(16)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # ✅ Ограничиваем ширину контента чтобы не выходил за границы
        self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMaximumSize)
        
        # Заголовок страницы
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 28px;
                font-weight: 600;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
                padding-bottom: 4px;
            }
        """)
        self.layout.addWidget(self.title_label)
        
        # Подзаголовок
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.6);
                    font-size: 13px;
                    padding-bottom: 16px;
                }
            """)
            self.subtitle_label.setWordWrap(True)
            self.layout.addWidget(self.subtitle_label)
        
    def add_widget(self, widget: QWidget, stretch: int = 0):
        """Добавляет виджет на страницу"""
        self.layout.addWidget(widget, stretch)
        
    def add_spacing(self, height: int = 16):
        """Добавляет вертикальный отступ"""
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        spacer = QSpacerItem(0, height, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.layout.addItem(spacer)
        
    def add_section_title(self, text: str, return_widget: bool = False):
        """Добавляет заголовок секции"""
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.8);
                font-size: 13px;
                font-weight: 600;
                padding-top: 8px;
                padding-bottom: 4px;
            }
        """)
        self.layout.addWidget(label)
        if return_widget:
            return label

