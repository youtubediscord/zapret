# strategy_menu/strategy_table_widget.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QEvent
from PyQt6.QtGui import QCursor

from log import log
from .table_builder import StrategyTableBuilder
from .hover_tooltip import tooltip_manager


class StrategyTableWidget(QWidget):
    """Виджет таблицы стратегий - минималистичный"""
    
    # Сигналы
    strategy_selected = pyqtSignal(str, str)
    strategy_applied = pyqtSignal(str, str)
    favorites_changed = pyqtSignal()  # Сигнал об изменении избранных
    
    def __init__(self, strategy_manager=None, parent=None):
        super().__init__(parent)
        self.strategy_manager = strategy_manager
        self.strategies_map = {}
        self.strategies_data = {}
        self.selected_strategy_id = None
        self.selected_strategy_name = None
        self._last_hover_row = -1
        self.category_key = "bat"  # По умолчанию для BAT режима

        self._init_ui()
        self._setup_rating_callback()
    
    def _init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Подсказка
        hint = QLabel("💡 Клик - применить • Удержание - информация")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px; padding: 6px 8px;")
        layout.addWidget(hint)
        
        # Статус
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px; padding: 4px 8px;")
        self.status_label.setFixedHeight(24)
        layout.addWidget(self.status_label)
        
        # Таблица
        self.table = StrategyTableBuilder.create_strategies_table()
        self.table.currentItemChanged.connect(self._on_item_selected)
        self.table.setEnabled(False)
        
        # Отслеживание мыши для hover tooltip
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        
        # Контекстное меню по ПКМ
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Двойной клик для показа информации
        self.table.doubleClicked.connect(self._on_double_click)
        
        layout.addWidget(self.table)
    
    def eventFilter(self, obj, event):
        """Фильтр событий для отслеживания hover"""
        if obj == self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                pos = event.pos()
                item = self.table.itemAt(pos)
                
                if item:
                    row = item.row()
                    if row != self._last_hover_row and row in self.strategies_map:
                        self._last_hover_row = row
                        strategy_id = self.strategies_map[row]['id']
                        
                        if strategy_id in self.strategies_data:
                            # Показываем tooltip
                            global_pos = self.table.viewport().mapToGlobal(pos)
                            global_pos.setX(global_pos.x() + 20)
                            global_pos.setY(global_pos.y() + 15)
                            
                            tooltip_manager.show_tooltip(
                                global_pos,
                                self.strategies_data[strategy_id],
                                strategy_id,
                                delay=500
                            )
                else:
                    if self._last_hover_row != -1:
                        self._last_hover_row = -1
                        tooltip_manager.hide_tooltip(delay=100)
                        
            elif event.type() == QEvent.Type.Leave:
                self._last_hover_row = -1
                tooltip_manager.hide_tooltip(delay=150)
                
            elif event.type() == QEvent.Type.MouseButtonPress:
                tooltip_manager.hide_immediately()
                
        return super().eventFilter(obj, event)
    
    def populate_strategies(self, strategies, category_key="bat"):
        """Заполняет таблицу стратегиями"""
        self.strategies_data = strategies
        self.category_key = category_key  # Сохраняем category_key

        self.strategies_map = StrategyTableBuilder.populate_table(
            self.table,
            strategies,
            self.strategy_manager,
            favorite_callback=self._on_favorite_toggled,
            category_key=category_key
        )

        self.table.setEnabled(True)

        count = len(strategies)
        self.set_status(f"✅ {count} стратегий")
    
    def _on_favorite_toggled(self, strategy_id, is_favorite):
        """Обработчик переключения избранного через звезду"""
        # Перезаполняем таблицу чтобы избранные переместились вверх
        self.populate_strategies(self.strategies_data, self.category_key)
        # Уведомляем об изменении
        self.favorites_changed.emit()
    
    def _show_context_menu(self, pos: QPoint):
        """Показывает превью аргументов стратегии при ПКМ"""
        tooltip_manager.hide_immediately()

        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        if row not in self.strategies_map:
            return

        strategy_id = self.strategies_map[row]['id']

        # Показываем превью аргументов
        self._show_args_preview(strategy_id, pos)
    
    def _on_double_click(self, index):
        """Обработчик двойного клика - показ информации"""
        tooltip_manager.hide_immediately()
        row = index.row()
        if row in self.strategies_map:
            strategy_id = self.strategies_map[row]['id']
            self._show_strategy_info(strategy_id)
    
    def _show_strategy_info(self, strategy_id):
        """Показывает окно с информацией о стратегии"""
        if strategy_id not in self.strategies_data:
            return

        strategy_data = self.strategies_data[strategy_id]

        try:
            from .args_preview_dialog import preview_manager
            preview_manager.show_preview(self, strategy_id, strategy_data, category_key=self.category_key)
        except Exception as e:
            log(f"Ошибка показа информации о стратегии: {e}", "ERROR")

    def _show_args_preview(self, strategy_id, pos: QPoint):
        """Показывает превью аргументов стратегии (при ПКМ)"""
        import os
        from config import BAT_FOLDER
        from utils.bat_parser import parse_bat_file

        if strategy_id not in self.strategies_data:
            return

        strategy_data = self.strategies_data[strategy_id]
        file_path = strategy_data.get('file_path', '')

        if not file_path:
            return

        full_path = os.path.join(BAT_FOLDER, file_path)

        if not os.path.exists(full_path):
            return

        # Парсим файл
        parsed = parse_bat_file(full_path, debug=False)
        if not parsed:
            return

        exe_path, args = parsed

        # Формируем текст для превью
        if exe_path is None:
            cmd_parts = ["winws.exe"] + args
        else:
            cmd_parts = [os.path.basename(exe_path)] + args

        # Форматируем: каждый --new на новой строке
        lines = []
        current_line = []

        for part in cmd_parts:
            if part == '--new':
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                lines.append('--new')
            else:
                current_line.append(part)

        if current_line:
            lines.append(' '.join(current_line))

        preview_text = '\n'.join(lines)

        # Показываем через args_preview_dialog
        from .args_preview_dialog import preview_manager
        preview_manager.show_preview(self, strategy_id, strategy_data, category_key=self.category_key)

    def set_status(self, message, status_type="info"):
        """Устанавливает статус"""
        colors = {
            "info": "rgba(255, 255, 255, 0.5)",
            "success": "#4ade80",
            "warning": "#fbbf24",
            "error": "#f87171"
        }
        color = colors.get(status_type, colors["info"])
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                padding: 4px 8px;
            }}
        """)
    
    def _on_item_selected(self, current, previous):
        """Обработчик выбора - автоприменение"""
        tooltip_manager.hide_immediately()
        
        if current is None:
            self.selected_strategy_id = None
            self.selected_strategy_name = None
            return
        
        row = current.row()
        
        if row < 0 or row not in self.strategies_map:
            self.selected_strategy_id = None
            self.selected_strategy_name = None
            return
        
        self.selected_strategy_id = self.strategies_map[row]['id']
        self.selected_strategy_name = self.strategies_map[row]['name']
        
        # Эмитируем сигналы
        self.strategy_selected.emit(self.selected_strategy_id, self.selected_strategy_name)
        self.strategy_applied.emit(self.selected_strategy_id, self.selected_strategy_name)
        self.set_status(f"✅ {self.selected_strategy_name}", "success")
    
    def select_strategy_by_name(self, strategy_name):
        """Выбирает стратегию по имени"""
        for row, info in self.strategies_map.items():
            if info['name'] == strategy_name:
                self.table.selectRow(row)
                break
    
    def get_selected_strategy(self):
        """Возвращает ID и имя выбранной стратегии"""
        return self.selected_strategy_id, self.selected_strategy_name
    
    def hideEvent(self, event):
        """При скрытии виджета скрываем tooltip"""
        tooltip_manager.hide_immediately()
        super().hideEvent(event)

    def _setup_rating_callback(self):
        """Подписываемся на изменение рейтингов"""
        from .args_preview_dialog import preview_manager
        preview_manager.add_rating_change_callback(self._on_rating_changed)

    def _on_rating_changed(self, strategy_id, new_rating):
        """Обновляет таблицу при изменении рейтинга стратегии"""
        if strategy_id in self.strategies_data:
            # Перезаполняем таблицу для обновления цветов
            self.populate_strategies(self.strategies_data, self.category_key)
