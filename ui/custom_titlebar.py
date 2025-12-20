# ui/custom_titlebar.py
"""
Кастомный titlebar для окна со скругленными углами и узкой рамкой.
"""
from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal, QEvent, QObject
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, 
    QSizePolicy, QApplication, QMenuBar, QSpacerItem,
    QScrollArea, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QSpinBox, QSlider, QAbstractButton, QAbstractScrollArea,
    QScrollBar, QAbstractItemView
)
from PyQt6.QtGui import QIcon, QFont, QMouseEvent, QPainter, QColor, QPen

import qtawesome as qta


# ============================================================================
# DRAGGABLE CONTENT AREA - позволяет перетаскивать окно за пустые области
# ============================================================================

class DraggableWidget(QWidget):
    """
    Виджет, который позволяет перетаскивать окно при клике на пустую область.
    Используется как обёртка для contentArea.
    Также устанавливает event filter на дочерние виджеты для перехвата событий.
    """
    
    # Типы виджетов, которые НЕ должны инициировать перетаскивание
    INTERACTIVE_TYPES = (
        QAbstractButton,  # Все кнопки
        QLineEdit,        # Поля ввода
        QTextEdit,        # Текстовые редакторы
        QComboBox,        # Выпадающие списки
        QCheckBox,        # Чекбоксы
        QSpinBox,         # Числовые поля
        QSlider,          # Слайдеры
        QScrollBar,       # Скроллбары
        QAbstractItemView,  # Списки, таблицы и т.д.
    )
    
    # Имена классов которые являются кликабельными
    INTERACTIVE_CLASS_NAMES = {
        "Win11RadioOption", "Win11ToggleRow", "Win11NumberRow",
        "AutostartOptionCard", "ThemeCard", "StatusCard"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_window_pos = None
        self._main_window = None
        self._installed_filters = set()  # Отслеживаем виджеты с установленными фильтрами
    
    def _get_main_window(self):
        """Находит главное окно (QMainWindow или FramelessWindow)"""
        if self._main_window:
            return self._main_window
        
        widget = self.parent()
        while widget:
            # Проверяем, является ли виджет главным окном
            if hasattr(widget, 'isMaximized') and hasattr(widget, 'move'):
                # Дополнительная проверка - это должен быть верхнеуровневый виджет
                if widget.isWindow():
                    self._main_window = widget
                    return widget
            widget = widget.parent() if hasattr(widget, 'parent') else None
        return None
    
    # ObjectNames которые являются контейнерами (разрешают перетаскивание)
    CONTAINER_NAMES = {"settingscard", "contentarea", "sidenavbar", "maincontainer"}
    
    # ObjectNames которые блокируют перетаскивание (кликабельные элементы)
    CLICKABLE_NAMES = {"themecard", "statuscard", "dnscard", "changelogcard", "updatestatuscard", "autostartoption"}
    
    def _is_interactive_widget(self, widget) -> bool:
        """Проверяет, является ли виджет интерактивным (не для перетаскивания)"""
        if widget is None:
            return False
        
        # Проверяем сам виджет
        if isinstance(widget, self.INTERACTIVE_TYPES):
            return True
        
        # Проверяем имя класса
        class_name = widget.__class__.__name__
        if class_name in self.INTERACTIVE_CLASS_NAMES:
            return True
        
        # Проверяем, есть ли у виджета свойство clickable или noDrag
        if widget.property("clickable") or widget.property("noDrag"):
            return True
        
        # Проверяем objectName
        name = widget.objectName().lower() if widget.objectName() else ""
        
        # Явно кликабельные карточки
        if name in self.CLICKABLE_NAMES:
            return True
        
        # Общие интерактивные паттерны (но НЕ контейнеры)
        if name not in self.CONTAINER_NAMES:
            if any(x in name for x in ["btn", "button", "toggle", "switch", "input", "edit", "radio"]):
                return True
        
        # Проверяем родителей до 5 уровней
        current = widget.parent() if hasattr(widget, 'parent') else None
        depth = 0
        while current and depth < 5:
            if isinstance(current, self.INTERACTIVE_TYPES):
                return True
            
            # Проверяем имя класса родителя
            parent_class = current.__class__.__name__
            if parent_class in self.INTERACTIVE_CLASS_NAMES:
                return True
            
            # Проверяем objectName родителей
            pname = current.objectName().lower() if current.objectName() else ""
            
            # Если родитель - кликабельная карточка
            if pname in self.CLICKABLE_NAMES:
                return True
            
            # Если родитель - контейнер, не блокируем
            if pname in self.CONTAINER_NAMES:
                current = current.parent() if hasattr(current, 'parent') else None
                depth += 1
                continue
            
            # Проверяем паттерны для кнопок
            if any(x in pname for x in ["btn", "button", "toggle", "switch", "radio"]):
                return True
            
            # Проверяем property
            if current.property("clickable") or current.property("noDrag"):
                return True
            
            current = current.parent() if hasattr(current, 'parent') else None
            depth += 1
        
        return False
    
    def _start_drag(self, global_pos: QPoint):
        """Начинает перетаскивание окна"""
        main_window = self._get_main_window()
        if main_window:
            self._is_dragging = True
            self._drag_start_pos = global_pos
            self._drag_window_pos = main_window.pos()
            return True
        return False
    
    def _do_drag(self, global_pos: QPoint):
        """Выполняет перетаскивание окна"""
        if not self._is_dragging or self._drag_start_pos is None:
            return False
        
        main_window = self._get_main_window()
        if not main_window:
            return False
        
        # Если окно максимизировано - сначала восстанавливаем
        if main_window.isMaximized():
            old_width = main_window.width()
            main_window.showNormal()
            
            # Пересчитываем позицию чтобы курсор остался на окне
            new_width = main_window.width()
            ratio = 0.5  # Центрируем окно под курсором
            new_x = int(global_pos.x() - new_width * ratio)
            new_y = int(global_pos.y() - 20)
            
            main_window.move(new_x, new_y)
            self._drag_start_pos = global_pos
            self._drag_window_pos = main_window.pos()
        else:
            # Обычное перемещение
            delta = global_pos - self._drag_start_pos
            new_pos = self._drag_window_pos + delta
            main_window.move(new_pos)
        
        return True
    
    def _end_drag(self):
        """Завершает перетаскивание окна"""
        was_dragging = self._is_dragging
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_window_pos = None
        return was_dragging
    
    def _is_in_resize_zone(self, global_pos: QPoint) -> bool:
        """Проверяет, находится ли курсор в зоне изменения размера окна"""
        main_window = self._get_main_window()
        if not main_window or main_window.isMaximized():
            return False
        
        # Если у окна есть resize handles, проверяем их
        if hasattr(main_window, '_resize_handles'):
            for handle in main_window._resize_handles:
                if handle.isVisible():
                    # Проверяем, находится ли курсор в области handle
                    handle_global_rect = handle.geometry()
                    handle_global_rect.moveTo(main_window.mapToGlobal(handle_global_rect.topLeft()))
                    if handle_global_rect.contains(global_pos):
                        return True
        
        # Дополнительная проверка по краям окна (fallback)
        window_rect = main_window.geometry()
        local_pos = main_window.mapFromGlobal(global_pos)
        margin = getattr(main_window, 'RESIZE_MARGIN', 14)
        
        # Проверяем близость к краям
        near_left = local_pos.x() < margin
        near_right = local_pos.x() > (window_rect.width() - margin)
        near_top = local_pos.y() < margin
        near_bottom = local_pos.y() > (window_rect.height() - margin)
        
        return near_left or near_right or near_top or near_bottom
    
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Фильтр событий для перехвата кликов на пустых областях дочерних виджетов"""
        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = event
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                # ✅ НЕ перехватываем события в зоне resize
                if self._is_in_resize_zone(mouse_event.globalPosition().toPoint()):
                    return False
                
                # Находим виджет под курсором в watched
                if isinstance(watched, QWidget):
                    child = watched.childAt(mouse_event.pos())
                    target = child if child else watched
                    
                    # Если это НЕ интерактивный виджет - начинаем перетаскивание
                    if not self._is_interactive_widget(target):
                        if self._start_drag(mouse_event.globalPosition().toPoint()):
                            return True  # Событие обработано
        
        elif event.type() == QEvent.Type.MouseMove:
            if self._is_dragging:
                mouse_event = event
                self._do_drag(mouse_event.globalPosition().toPoint())
                return True  # Событие обработано
        
        elif event.type() == QEvent.Type.MouseButtonRelease:
            mouse_event = event
            if mouse_event.button() == Qt.MouseButton.LeftButton:
                if self._end_drag():
                    return True  # Событие обработано
        
        return False  # Передаём событие дальше
    
    def _install_filter_recursive(self, widget: QWidget):
        """Рекурсивно устанавливает event filter на виджет и его потомков"""
        if widget in self._installed_filters:
            return
        
        # Не устанавливаем на интерактивные виджеты
        if isinstance(widget, self.INTERACTIVE_TYPES):
            return
        
        widget.installEventFilter(self)
        self._installed_filters.add(widget)
        
        # Рекурсивно для детей
        for child in widget.findChildren(QWidget):
            if child not in self._installed_filters:
                if not isinstance(child, self.INTERACTIVE_TYPES):
                    child.installEventFilter(self)
                    self._installed_filters.add(child)
    
    def showEvent(self, event):
        """При показе виджета устанавливаем event filter на всех потомков"""
        super().showEvent(event)
        # Отложенная установка фильтров (после полной инициализации)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._install_filters_delayed)
    
    def _install_filters_delayed(self):
        """Отложенная установка фильтров"""
        self._install_filter_recursive(self)
    
    def childEvent(self, event):
        """При добавлении новых детей устанавливаем на них фильтр"""
        super().childEvent(event)
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self._install_filter_recursive(child))
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # ✅ НЕ перехватываем события в зоне resize
            if self._is_in_resize_zone(event.globalPosition().toPoint()):
                super().mousePressEvent(event)
                return
            
            # Находим виджет под курсором
            child = self.childAt(event.pos())
            
            # Если клик по интерактивному элементу - пропускаем
            if child and self._is_interactive_widget(child):
                super().mousePressEvent(event)
                return
            
            # Начинаем перетаскивание
            if self._start_drag(event.globalPosition().toPoint()):
                event.accept()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._do_drag(event.globalPosition().toPoint()):
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._end_drag():
                event.accept()
                return
        super().mouseReleaseEvent(event)


# Стили для встроенного меню в titlebar
MENUBAR_STYLE = """
QMenuBar {
    background-color: transparent;
    color: #ffffff;
    border: none;
    padding: 0px;
    spacing: 0px;
    font-size: 11px;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QMenuBar::item {
    background-color: transparent;
    color: #ffffff;
    padding: 4px 10px;
    border-radius: 4px;
    margin: 2px 1px;
}

QMenuBar::item:selected {
    background-color: rgba(255, 255, 255, 0.1);
}

QMenuBar::item:pressed {
    background-color: rgba(255, 255, 255, 0.15);
}

QMenu {
    background-color: #2b2b2b;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
    color: #ffffff;
}

QMenu::item:selected {
    background-color: rgba(255, 255, 255, 0.1);
}

QMenu::separator {
    height: 1px;
    background-color: #3d3d3d;
    margin: 4px 8px;
}

QMenu::indicator {
    width: 16px;
    height: 16px;
    margin-left: 4px;
}
"""


class TitleBarButton(QPushButton):
    """Кнопка для titlebar с hover эффектом"""

    def __init__(self, icon_name: str, hover_color: str = "#555555", parent=None, border_radius: str = "0px"):
        super().__init__(parent)
        self.hover_color = hover_color
        self.normal_color = "transparent"
        self._hovered = False
        self._border_radius = border_radius

        # Устанавливаем иконку
        self.setIcon(qta.icon(icon_name, color='white'))
        self.setIconSize(QSize(12, 12))

        # Фиксированный размер кнопки
        self.setFixedSize(36, 28)

        self._update_style()

    def _update_style(self):
        bg_color = self.hover_color if self._hovered else self.normal_color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                {self._border_radius}
            }}
        """)
        
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)


class CloseButton(TitleBarButton):
    """Специальная кнопка закрытия с красным hover и скруглённым углом"""

    def __init__(self, parent=None):
        # Скругляем только верхний правый угол (10px как у окна)
        super().__init__('fa5s.times', '#e81123', parent, border_radius="border-top-right-radius: 10px;")


class MinimizeButton(TitleBarButton):
    """Кнопка сворачивания"""

    def __init__(self, parent=None):
        super().__init__('fa5s.minus', '#555555', parent, border_radius="border-radius: 0px;")


class MaximizeButton(TitleBarButton):
    """Кнопка максимизации/восстановления"""

    def __init__(self, parent=None):
        super().__init__('fa5s.square', '#555555', parent, border_radius="border-radius: 0px;")
        self._is_maximized = False
        
    def set_maximized(self, maximized: bool):
        self._is_maximized = maximized
        icon_name = 'fa5s.clone' if maximized else 'fa5s.square'
        self.setIcon(qta.icon(icon_name, color='white'))


class CustomTitleBar(QWidget):
    """
    Кастомный titlebar для Frameless окна.
    Поддерживает перетаскивание, сворачивание, разворачивание и закрытие.
    Включает встроенный menubar.
    """
    
    # Сигналы
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    drag_started = pyqtSignal()  # Начало перемещения (для отключения Acrylic)
    drag_ended = pyqtSignal()    # Конец перемещения (для включения Acrylic)
    
    def __init__(self, parent=None, title: str = "Zapret 2 GUI", show_icon: bool = True):
        super().__init__(parent)
        self.parent_window = parent
        self._drag_pos = None
        self._window_pos = None
        self._is_moving = False
        self._menubar = None
        
        # Высота titlebar (узкая рамка)
        self.setFixedHeight(32)
        self.setObjectName("customTitleBar")
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)
        
        # Иконка приложения (слева)
        if show_icon:
            self.icon_label = QLabel()
            self.icon_label.setFixedSize(20, 20)
            layout.addWidget(self.icon_label)
        
        # Растягиваемый спейсер слева от заголовка
        layout.addStretch(1)
        
        # Заголовок (по центру)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setStyleSheet("""
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Растягиваемый спейсер справа от заголовка
        layout.addStretch(1)
        
        # Контейнер для кнопок управления окном (с явным родителем!)
        buttons_widget = QWidget(self)  # ✅ Родитель = self
        buttons_widget.setObjectName("titleBarButtons")
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)
        self.buttons_widget = buttons_widget  # Используется для расчёта зоны resize
        
        # Кнопки
        self.minimize_btn = MinimizeButton(self)
        self.maximize_btn = MaximizeButton(self)
        self.close_btn = CloseButton(self)
        
        # Подключаем сигналы
        self.minimize_btn.clicked.connect(self._on_minimize)
        self.maximize_btn.clicked.connect(self._on_maximize)
        self.close_btn.clicked.connect(self._on_close)
        
        buttons_layout.addWidget(self.minimize_btn)
        buttons_layout.addWidget(self.maximize_btn)
        buttons_layout.addWidget(self.close_btn)
        
        layout.addWidget(buttons_widget)
        
        # Стиль titlebar
        self._apply_style()
        
    def set_menubar(self, menubar: QMenuBar):
        """Сохраняет ссылку на menubar (теперь он добавляется отдельно под titlebar)"""
        self._menubar = menubar
        
    def _apply_style(self, bg_color: str = "rgba(32, 32, 32, 0.98)", text_color: str = "#ffffff"):
        self.setStyleSheet(f"""
            QWidget#customTitleBar {{
                background-color: {bg_color};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QWidget#titleBarButtons {{
                background-color: transparent;
            }}
        """)
        self.title_label.setStyleSheet(f"""
            QLabel#titleLabel {{
                color: {text_color};
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)
        
    def set_theme_colors(self, bg_color: str = "#1a1a1a", text_color: str = "#ffffff"):
        """Обновляет цвета titlebar в соответствии с темой"""
        self._apply_style(bg_color, text_color)
        
        # Обновляем стили menubar
        if self._menubar:
            is_light = text_color == "#000000"
            
            if is_light:
                # Светлая тема
                menu_style = """
                QMenuBar {
                    background-color: transparent;
                    color: #000000;
                    border: none;
                    padding: 0px;
                    spacing: 0px;
                    font-size: 11px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QMenuBar::item {
                    background-color: transparent;
                    color: #000000;
                    padding: 4px 10px;
                    border-radius: 4px;
                    margin: 2px 1px;
                }
                QMenuBar::item:selected {
                    background-color: rgba(0, 0, 0, 0.1);
                }
                QMenuBar::item:pressed {
                    background-color: rgba(0, 0, 0, 0.15);
                }
                QMenu {
                    background-color: #f5f5f5;
                    border: 1px solid #cccccc;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 24px 6px 12px;
                    border-radius: 4px;
                    color: #000000;
                }
                QMenu::item:selected {
                    background-color: rgba(0, 0, 0, 0.1);
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #cccccc;
                    margin: 4px 8px;
                }
                """
            else:
                # Тёмная тема
                menu_bg = "#000000" if bg_color == "#000000" else "#2b2b2b"
                border_color = "#1a1a1a" if bg_color == "#000000" else "#3d3d3d"
                
                menu_style = f"""
                QMenuBar {{
                    background-color: transparent;
                    color: {text_color};
                    border: none;
                    padding: 0px;
                    spacing: 0px;
                    font-size: 11px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    color: {text_color};
                    padding: 4px 10px;
                    border-radius: 4px;
                    margin: 2px 1px;
                }}
                QMenuBar::item:selected {{
                    background-color: rgba(255, 255, 255, 0.1);
                }}
                QMenuBar::item:pressed {{
                    background-color: rgba(255, 255, 255, 0.15);
                }}
                QMenu {{
                    background-color: {menu_bg};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 6px 24px 6px 12px;
                    border-radius: 4px;
                    color: {text_color};
                }}
                QMenu::item:selected {{
                    background-color: rgba(255, 255, 255, 0.1);
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: {border_color};
                    margin: 4px 8px;
                }}
                """
            
            self._menubar.setStyleSheet(menu_style)
        
    def set_title(self, title: str):
        """Устанавливает заголовок окна"""
        self.title_label.setText(title)
        
    def set_icon(self, icon: QIcon):
        """Устанавливает иконку окна"""
        if hasattr(self, 'icon_label'):
            pixmap = icon.pixmap(QSize(16, 16))
            self.icon_label.setPixmap(pixmap)
            
    def set_maximized_state(self, maximized: bool):
        """Обновляет состояние кнопки максимизации"""
        self.maximize_btn.set_maximized(maximized)
        
    def _on_minimize(self):
        self.minimize_clicked.emit()
        if self.parent_window:
            self.parent_window.showMinimized()
            
    def _on_maximize(self):
        self.maximize_clicked.emit()
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self.maximize_btn.set_maximized(False)
            else:
                self.parent_window.showMaximized()
                self.maximize_btn.set_maximized(True)
                
    def _on_close(self):
        self.close_clicked.emit()
        if self.parent_window:
            self.parent_window.close()
            
    # Перетаскивание окна
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Не перетаскиваем если клик по кнопкам
            child = self.childAt(event.pos())
            if child and isinstance(child, TitleBarButton):
                event.ignore()
                return
            
            self._drag_pos = event.globalPosition().toPoint()
            self._window_pos = self.parent_window.pos()
            self._is_moving = True
            self.drag_started.emit()  # Отключаем Acrylic для производительности
            event.accept()
            
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_moving and self._drag_pos is not None:
            # Если окно максимизировано, сначала восстанавливаем
            if self.parent_window.isMaximized():
                # Вычисляем относительную позицию клика
                old_width = self.parent_window.width()
                relative_x = self._drag_pos.x() - self.parent_window.x()
                
                self.parent_window.showNormal()
                self.maximize_btn.set_maximized(False)
                
                # Пересчитываем позицию после восстановления
                new_width = self.parent_window.width()
                ratio = new_width / old_width
                self._window_pos = QPoint(
                    int(self._drag_pos.x() - relative_x * ratio),
                    self._drag_pos.y() - 16  # половина высоты titlebar
                )
            
            # Вычисляем новую позицию
            delta = event.globalPosition().toPoint() - self._drag_pos
            new_pos = self._window_pos + delta
            self.parent_window.move(new_pos)
            event.accept()
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        was_moving = self._is_moving
        self._is_moving = False
        self._drag_pos = None
        self._window_pos = None
        if was_moving:
            self.drag_ended.emit()  # Включаем Acrylic обратно
        event.accept()
        
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Двойной клик для максимизации/восстановления"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            self._on_maximize()


class ResizeHandle(QWidget):
    """Полупрозрачный оверлей для изменения размера по краям окна"""
    
    def __init__(self, window, edge: str, thickness: int):
        super().__init__(window)
        self.window = window
        self.edge = edge
        self.thickness = thickness
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")
        self._set_cursor()
    
    def _set_cursor(self):
        cursors = {
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'top-left': Qt.CursorShape.SizeFDiagCursor,
            'bottom-right': Qt.CursorShape.SizeFDiagCursor,
            'top-right': Qt.CursorShape.SizeBDiagCursor,
            'bottom-left': Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(self.edge, Qt.CursorShape.ArrowCursor))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window._start_resize(self.edge, event.globalPosition().toPoint())
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self.window._is_resizing:
            self.window._perform_resize(event.globalPosition().toPoint())
            event.accept()
        else:
            event.ignore()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window._end_resize()
            event.accept()
    
    def enterEvent(self, event):
        self.window._highlight_resize_handle(self, True)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.window._highlight_resize_handle(self, False)
        if not self.window._is_resizing:
            self.window.unsetCursor()
        super().leaveEvent(event)


class FramelessWindowMixin:
    """
    Миксин для добавления функционала frameless окна.
    Использует прозрачные оверлеи по краям для изменения размера.
    Позволяет перетаскивать окно за любое пустое место.
    """
    
    RESIZE_MARGIN = 6
    
    # Интерактивные виджеты, которые НЕ должны перетаскивать окно
    INTERACTIVE_WIDGETS = (
        'QPushButton', 'QToolButton', 'QLineEdit', 'QTextEdit', 'QPlainTextEdit',
        'QComboBox', 'QSpinBox', 'QDoubleSpinBox', 'QSlider', 'QScrollBar',
        'QCheckBox', 'QRadioButton', 'QTabBar', 'QTableWidget', 'QTableView',
        'QListWidget', 'QListView', 'QTreeWidget', 'QTreeView', 'QMenu',
        'QMenuBar', 'TitleBarButton', 'ActionButton', 'SettingsCard',
        'CompactStrategyItem', 'FavoriteCompactStrategyItem', 'RippleButton',
        'DualActionRippleButton', 'HoverTextButton', 'ResizeHandle',
        'QScrollArea', 'QAbstractScrollArea', 'QProgressBar', 'ClickableLabel',
        'AnimatedToggle', 'ToggleSwitch', 'SideNavBar', 'NavButton',
        'AutostartOptionCard',  # Карточки автозапуска
        'Win11RadioOption', 'Win11ToggleRow', 'Win11NumberRow',  # DPI настройки
    )
    
    def init_frameless(self, resize_target=None):
        """Инициализация frameless режима"""
        self._resize_handles = []
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._is_resizing = False
        self._was_maximized = False
        
        # Состояние перетаскивания окна
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_window_pos = None
        
        self._create_resize_handles()
    
    def _create_resize_handles(self):
        edges = [
            'left', 'right', 'top', 'bottom',
            'top-left', 'top-right', 'bottom-left', 'bottom-right'
        ]
        thickness = self.RESIZE_MARGIN
        
        for edge in edges:
            handle = ResizeHandle(self, edge, thickness)
            handle.raise_()
            self._resize_handles.append(handle)
        
        self._update_resize_handles()
        self._set_handles_visible(True)
    
    def _update_resize_handles(self):
        if not self._resize_handles:
            return
        
        margin = self.RESIZE_MARGIN
        w = self.width()
        h = self.height()
        corner = max(int(margin * 2.0), margin + 12)
        corner = min(corner, w // 2, h // 2)

        protected_width = 0
        if hasattr(self, 'title_bar'):
            buttons_widget = getattr(self.title_bar, 'buttons_widget', None)
            if buttons_widget is not None:
                protected_width = buttons_widget.width()
                if protected_width <= 0:
                    protected_width = buttons_widget.sizeHint().width()
                protected_width = max(protected_width, 0) + 4  # небольшой отступ
        available_top_right = max(0, w - protected_width)
        
        for handle in self._resize_handles:
            edge = handle.edge
            if edge == 'left':
                handle.setGeometry(0, corner, margin, max(1, h - 2 * corner))
            elif edge == 'right':
                handle.setGeometry(w - margin, corner, margin, max(1, h - 2 * corner))
            elif edge == 'top':
                handle.setGeometry(corner, 0, max(1, w - 2 * corner), margin)
            elif edge == 'bottom':
                handle.setGeometry(corner, h - (margin + 4), max(1, w - 2 * corner), margin + 4)
            elif edge == 'top-left':
                handle.setGeometry(0, 0, corner, corner)
            elif edge == 'top-right':
                if protected_width > 0 and available_top_right > 0:
                    handle_width = min(corner, available_top_right)
                    x_start = max(0, available_top_right - handle_width)
                    handle.setGeometry(x_start, 0, handle_width, corner)
                elif protected_width > 0:
                    # Нет свободного места слева от кнопок управления
                    handle.setGeometry(0, 0, 0, 0)
                else:
                    handle.setGeometry(w - corner, 0, corner, corner)
            elif edge == 'bottom-left':
                handle.setGeometry(0, h - corner, corner, corner)
            elif edge == 'bottom-right':
                handle.setGeometry(w - corner, h - corner, corner, corner)
            handle.raise_()
    
    def resizeEvent(self, event):
        self._update_resize_handles()
        QWidget.resizeEvent(self, event)
    
    def _start_resize(self, edge, global_pos):
        self._resize_edge = edge
        self._resize_start_pos = global_pos
        self._resize_start_geometry = self.geometry()
        self._is_resizing = True
        self._update_cursor(edge)
    
    def _perform_resize(self, global_pos):
        if not self._is_resizing or not self._resize_edge:
            return
        delta = global_pos - self._resize_start_pos
        geo = self._resize_start_geometry

        new_x = geo.x()
        new_y = geo.y()
        new_w = geo.width()
        new_h = geo.height()
        min_w = self.minimumWidth()
        min_h = self.minimumHeight()

        edge = self._resize_edge

        if 'left' in edge:
            new_w = max(min_w, geo.width() - delta.x())
            if new_w != min_w:
                new_x = geo.x() + delta.x()
        if 'right' in edge:
            new_w = max(min_w, geo.width() + delta.x())
        if 'top' in edge:
            new_h = max(min_h, geo.height() - delta.y())
            if new_h != min_h:
                new_y = geo.y() + delta.y()
        if 'bottom' in edge:
            new_h = max(min_h, geo.height() + delta.y())

        self.setGeometry(new_x, new_y, new_w, new_h)
        # ✅ Явно обновляем позиции resize handles во время изменения размера
        self._update_resize_handles()
    
    def _end_resize(self):
        self._is_resizing = False
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self.unsetCursor()
    
    def _update_cursor(self, edge):
        cursors = {
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'top-left': Qt.CursorShape.SizeFDiagCursor,
            'bottom-right': Qt.CursorShape.SizeFDiagCursor,
            'top-right': Qt.CursorShape.SizeBDiagCursor,
            'bottom-left': Qt.CursorShape.SizeBDiagCursor,
        }
        if edge:
            self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))
    
    def _highlight_resize_handle(self, handle: ResizeHandle, highlight: bool):
        if highlight:
            if '-' in handle.edge:
                handle.setStyleSheet("""
                    background: rgba(96,205,255,0.18);
                    border-radius: 12px;
                """)
            else:
                handle.setStyleSheet("background: rgba(96,205,255,0.10);")
        else:
            handle.setStyleSheet("background: transparent;")

    def _is_interactive_widget(self, widget):
        """Проверяет, является ли виджет интерактивным (не должен перетаскивать окно)"""
        if widget is None:
            return False
        
        class_name = widget.__class__.__name__
        
        # Проверяем по имени класса
        if class_name in self.INTERACTIVE_WIDGETS:
            return True
        
        # Проверяем родительские классы
        for parent_class in type(widget).__mro__:
            if parent_class.__name__ in self.INTERACTIVE_WIDGETS:
                return True
        
        # Проверяем objectName на специальные виджеты
        obj_name = widget.objectName() if hasattr(widget, 'objectName') else ''
        if obj_name and any(x in obj_name.lower() for x in ['button', 'btn', 'edit', 'combo', 'scroll']):
            return True
        
        return False
    
    def _find_interactive_parent(self, widget):
        """Ищет интерактивный виджет среди родителей"""
        current = widget
        depth = 0
        max_depth = 10  # Ограничиваем глубину поиска
        
        while current is not None and depth < max_depth:
            if self._is_interactive_widget(current):
                return current
            current = current.parent() if hasattr(current, 'parent') else None
            depth += 1
        
        return None

    def mousePressEvent(self, event):
        """Начало перетаскивания окна за пустое место"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Если идёт ресайз - не перетаскиваем
            if getattr(self, '_is_resizing', False):
                QWidget.mousePressEvent(self, event)
                return
            
            # Находим виджет под курсором
            child = self.childAt(event.pos())
            
            # Проверяем, не кликнули ли на интерактивный элемент
            if child and self._find_interactive_parent(child):
                QWidget.mousePressEvent(self, event)
                return
            
            # Начинаем перетаскивание
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_window_pos = self.pos()
            event.accept()
            return
        
        QWidget.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        # Перетаскивание окна
        if getattr(self, '_is_dragging', False) and self._drag_start_pos is not None:
            # Если окно максимизировано - сначала восстанавливаем
            if self.isMaximized():
                old_width = self.width()
                relative_x = self._drag_start_pos.x() - self.x()
                
                self.showNormal()
                
                # Обновляем titlebar если есть
                if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'maximize_btn'):
                    self.title_bar.maximize_btn.set_maximized(False)
                
                new_width = self.width()
                ratio = new_width / old_width if old_width > 0 else 1
                self._drag_window_pos = QPoint(
                    int(self._drag_start_pos.x() - relative_x * ratio),
                    self._drag_start_pos.y() - 20
                )
            
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_pos = self._drag_window_pos + delta
            self.move(new_pos)
            event.accept()
            return
        
        # Ресайз окна
        if getattr(self, '_is_resizing', False):
            self._perform_resize(event.globalPosition().toPoint())
            event.accept()
            return
        
        QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Завершение перетаскивания
            if getattr(self, '_is_dragging', False):
                self._is_dragging = False
                self._drag_start_pos = None
                self._drag_window_pos = None
                event.accept()
                return
            
            # Завершение ресайза
            if getattr(self, '_is_resizing', False):
                self._end_resize()
                event.accept()
                return
        
        QWidget.mouseReleaseEvent(self, event)
    
    def _set_handles_visible(self, visible: bool):
        if not hasattr(self, '_resize_handles'):
            return
        for handle in self._resize_handles:
            handle.setVisible(visible)
        
    def showMaximized(self):
        """Переопределяем для обновления стилей при максимизации"""
        self._was_maximized = True
        self._update_border_radius(False)
        self._set_handles_visible(False)
        super().showMaximized()
        
    def showNormal(self):
        """Переопределяем для восстановления скругленных углов"""
        self._was_maximized = False
        self._update_border_radius(True)
        self._set_handles_visible(True)
        super().showNormal()
        
    def _update_border_radius(self, enable_radius: bool):
        """Обновляет стили скругленных углов"""
        if not hasattr(self, 'container') or not hasattr(self, 'title_bar'):
            return
            
        radius = 10 if enable_radius else 0
        
        # Получаем текущие цвета из стиля контейнера
        current_style = self.container.styleSheet()
        
        # Обновляем радиус в стиле контейнера
        import re
        
        # Извлекаем текущие цвета
        bg_match = re.search(r'background-color:\s*([^;]+);', current_style)
        border_match = re.search(r'border:\s*([^;]+);', current_style)
        
        bg_color = bg_match.group(1).strip() if bg_match else "rgba(30, 30, 30, 240)"
        border_style = border_match.group(1).strip() if border_match else "1px solid rgba(80, 80, 80, 200)"
        
        self.container.setStyleSheet(f"""
            QFrame#mainContainer {{
                background-color: {bg_color};
                border-radius: {radius}px;
                border: {border_style};
            }}
        """)
        
        # Обновляем titlebar
        title_radius = radius if enable_radius else 0
        self.title_bar.setStyleSheet(f"""
            QWidget#customTitleBar {{
                background-color: rgba(26, 26, 26, 240);
                border-top-left-radius: {title_radius}px;
                border-top-right-radius: {title_radius}px;
            }}
            QWidget#titleBarButtons {{
                background-color: transparent;
            }}
        """)


def apply_rounded_corners_style(widget: QWidget, radius: int = 10):
    """
    Применяет стиль со скругленными углами к виджету.
    
    Args:
        widget: Виджет для применения стиля
        radius: Радиус скругления углов
    """
    current_style = widget.styleSheet()
    
    rounded_style = f"""
        QWidget#mainContainer {{
            background-color: #2b2b2b;
            border-radius: {radius}px;
            border: 1px solid #3d3d3d;
        }}
    """
    
    widget.setStyleSheet(current_style + rounded_style)

