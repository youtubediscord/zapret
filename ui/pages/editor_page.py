# ui/pages/editor_page.py
"""Страница редактора стратегий"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QComboBox,
    QScrollArea, QFrame, QDialog, 
    QDialogButtonBox, QFormLayout, QMessageBox
)
from PyQt6.QtGui import QFont
import qtawesome as qta

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log


class StrategyEditorDialog(QDialog):
    """Диалог для редактирования/создания стратегии"""
    
    def __init__(self, parent=None, strategy_data=None, category="tcp", is_new=True):
        super().__init__(parent)
        self.strategy_data = strategy_data or {}
        self.category = category
        self.is_new = is_new
        self.result_data = None
        
        self.setWindowTitle("Новая стратегия" if is_new else "Редактирование стратегии")
        self.setMinimumSize(550, 480)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 8px;
                color: #ffffff;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        
        self._build_ui()
        self._load_data()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Форма
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # ID
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("уникальный_id (латиница, цифры, _)")
        if not self.is_new:
            self.id_edit.setEnabled(False)
        form_layout.addRow("ID:", self.id_edit)
        
        # Название
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название стратегии")
        form_layout.addRow("Название:", self.name_edit)
        
        # Описание
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Краткое описание")
        form_layout.addRow("Описание:", self.desc_edit)
        
        # Автор
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Ваше имя")
        form_layout.addRow("Автор:", self.author_edit)
        
        # Метка
        self.label_combo = QComboBox()
        self.label_combo.addItem("Без метки", None)
        self.label_combo.addItem("⭐ Рекомендовано", "recommended")
        self.label_combo.addItem("🎮 Для игр", "game")
        self.label_combo.addItem("⚠️ Осторожно", "caution")
        self.label_combo.addItem("🔬 Экспериментально", "experimental")
        self.label_combo.addItem("✅ Стабильно", "stable")
        form_layout.addRow("Метка:", self.label_combo)
        
        # Блобы
        self.blobs_edit = QLineEdit()
        self.blobs_edit.setPlaceholderText("tls_google, tls4 (через запятую)")
        form_layout.addRow("Блобы:", self.blobs_edit)
        
        layout.addLayout(form_layout)
        
        # Аргументы
        args_label = QLabel("Аргументы командной строки:")
        args_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
        layout.addWidget(args_label)
        
        self.args_edit = ScrollBlockingPlainTextEdit()
        self.args_edit.setPlaceholderText(
            "Введите аргументы для winws...\n"
            "Пример: --payload=tls_client_hello --out-range=-d10 --lua-desync=fake:blob=tls_google"
        )
        self.args_edit.setStyleSheet("""
            QPlainTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        self.args_edit.setMinimumHeight(100)
        layout.addWidget(self.args_edit, 1)
        
        # Подсказка
        hint = QLabel("💡 Пользовательские стратегии сохраняются отдельно и не будут перезаписаны при обновлении")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: #ffffff;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #60cdff;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: #000000;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #7dd7ff;
            }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_data(self):
        if not self.strategy_data:
            return
        
        self.id_edit.setText(self.strategy_data.get('id', ''))
        self.name_edit.setText(self.strategy_data.get('name', ''))
        self.desc_edit.setText(self.strategy_data.get('description', ''))
        self.author_edit.setText(self.strategy_data.get('author', ''))
        self.args_edit.setPlainText(self.strategy_data.get('args', ''))
        
        blobs = self.strategy_data.get('blobs', [])
        if blobs:
            self.blobs_edit.setText(', '.join(blobs))
        
        label = self.strategy_data.get('label')
        for i in range(self.label_combo.count()):
            if self.label_combo.itemData(i) == label:
                self.label_combo.setCurrentIndex(i)
                break
    
    def _on_save(self):
        strategy_id = self.id_edit.text().strip()
        name = self.name_edit.text().strip()
        args = self.args_edit.toPlainText().strip()
        
        if not strategy_id:
            QMessageBox.warning(self, "Ошибка", "Введите ID стратегии")
            return
        
        if not all(c.isalnum() or c == '_' for c in strategy_id):
            QMessageBox.warning(self, "Ошибка", "ID может содержать только латиницу, цифры и _")
            return
        
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название")
            return
        
        blobs_text = self.blobs_edit.text().strip()
        blobs = [b.strip() for b in blobs_text.split(',') if b.strip()] if blobs_text else []
        
        self.result_data = {
            'id': strategy_id,
            'name': name,
            'description': self.desc_edit.text().strip(),
            'author': self.author_edit.text().strip() or 'user',
            'label': self.label_combo.currentData(),
            'blobs': blobs,
            'args': args
        }
        
        self.accept()
    
    def get_result(self):
        return self.result_data


class EditorPage(BasePage):
    """Страница редактора стратегий"""
    
    strategies_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Редактор стратегий", "Создание и редактирование пользовательских стратегий", parent)
        self.current_category = "tcp"
        self.strategies = {}
        self._build_ui()
        
    def _build_ui(self):
        # Выбор категории
        self.add_section_title("Категория")
        
        cat_card = SettingsCard()
        cat_layout = QHBoxLayout()
        cat_layout.setSpacing(12)
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("TCP (YouTube, Discord, сайты)", "tcp")
        self.category_combo.addItem("UDP (QUIC, игры)", "udp")
        self.category_combo.addItem("HTTP порт 80", "http80")
        self.category_combo.addItem("Discord Voice", "discord_voice")
        self.category_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                selection-background-color: rgba(96, 205, 255, 0.3);
                color: #ffffff;
            }
        """)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        cat_layout.addWidget(self.category_combo, 1)
        
        refresh_btn = ActionButton("Обновить", "fa5s.sync-alt")
        refresh_btn.clicked.connect(self._load_strategies)
        cat_layout.addWidget(refresh_btn)
        
        cat_card.add_layout(cat_layout)
        self.add_widget(cat_card)
        
        self.add_spacing(16)
        
        # Действия
        self.add_section_title("Действия")
        
        actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        self.add_btn = ActionButton("Новая стратегия", "fa5s.plus", accent=True)
        self.add_btn.clicked.connect(self._add_strategy)
        actions_layout.addWidget(self.add_btn)
        
        self.edit_btn = ActionButton("Редактировать", "fa5s.edit")
        self.edit_btn.clicked.connect(self._edit_strategy)
        self.edit_btn.setEnabled(False)
        actions_layout.addWidget(self.edit_btn)
        
        self.delete_btn = ActionButton("Удалить", "fa5s.trash-alt")
        self.delete_btn.clicked.connect(self._delete_strategy)
        self.delete_btn.setEnabled(False)
        actions_layout.addWidget(self.delete_btn)
        
        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        self.add_widget(actions_card)
        
        self.add_spacing(16)
        
        # Поиск
        search_card = SettingsCard()
        search_layout = QHBoxLayout()
        
        search_icon = QLabel()
        search_icon.setPixmap(qta.icon('fa5s.search', color='#888').pixmap(16, 16))
        search_layout.addWidget(search_icon)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск стратегий...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 13px;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_strategies)
        search_layout.addWidget(self.search_edit, 1)
        
        search_card.add_layout(search_layout)
        self.add_widget(search_card)
        
        self.add_spacing(16)
        
        # Список стратегий
        self.add_section_title("Стратегии")
        
        self.list_card = SettingsCard()
        list_layout = QVBoxLayout()
        list_layout.setSpacing(0)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.strategies_list = QListWidget()
        self.strategies_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background: rgba(96, 205, 255, 0.15);
                color: #60cdff;
            }
        """)
        self.strategies_list.setMinimumHeight(300)
        self.strategies_list.currentItemChanged.connect(self._on_strategy_selected)
        self.strategies_list.itemDoubleClicked.connect(self._edit_strategy)
        list_layout.addWidget(self.strategies_list)
        
        self.list_card.add_layout(list_layout)
        self.add_widget(self.list_card)
        
        self.add_spacing(12)
        
        # Статус
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        self.add_widget(self.status_label)
        
        # Загружаем стратегии
        self._load_strategies()
    
    def _on_category_changed(self, index):
        self.current_category = self.category_combo.currentData()
        self._load_strategies()
    
    def _load_strategies(self):
        try:
            from strategy_menu.strategies.strategy_loader import load_category_strategies
            
            self.strategies = load_category_strategies(self.current_category)
            self._populate_list()
            
            self.status_label.setText(f"✅ Загружено {len(self.strategies)} стратегий")
            
        except Exception as e:
            log(f"Ошибка загрузки стратегий: {e}", "ERROR")
            self.status_label.setText(f"❌ Ошибка: {e}")
    
    def _populate_list(self):
        self.strategies_list.clear()
        search_text = self.search_edit.text().lower()
        
        # Сортируем: user сначала
        sorted_items = sorted(
            self.strategies.items(),
            key=lambda x: (0 if x[1].get('_source') == 'user' else 1, x[1].get('name', '').lower())
        )
        
        for strategy_id, data in sorted_items:
            name = data.get('name', strategy_id)
            
            if search_text and search_text not in name.lower() and search_text not in strategy_id.lower():
                continue
            
            source = data.get('_source', 'builtin')
            icon = "👤" if source == 'user' else "📦"
            
            label = data.get('label')
            label_icon = ""
            if label == 'recommended':
                label_icon = " ⭐"
            elif label == 'caution':
                label_icon = " ⚠️"
            elif label == 'game':
                label_icon = " 🎮"
            elif label == 'stable':
                label_icon = " ✅"
            
            item = QListWidgetItem(f"{icon} {name}{label_icon}")
            item.setData(Qt.ItemDataRole.UserRole, strategy_id)
            
            if source == 'user':
                item.setForeground(Qt.GlobalColor.cyan)
            
            self.strategies_list.addItem(item)
    
    def _filter_strategies(self):
        self._populate_list()
    
    def _on_strategy_selected(self, current, previous):
        if not current:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        
        strategy_id = current.data(Qt.ItemDataRole.UserRole)
        data = self.strategies.get(strategy_id, {})
        
        is_user = data.get('_source') == 'user'
        self.edit_btn.setEnabled(is_user)
        self.delete_btn.setEnabled(is_user)
    
    def _add_strategy(self):
        dialog = StrategyEditorDialog(
            self.window(),
            strategy_data=None,
            category=self.current_category,
            is_new=True
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._save_strategy(result, is_new=True)
    
    def _edit_strategy(self):
        current = self.strategies_list.currentItem()
        if not current:
            return
        
        strategy_id = current.data(Qt.ItemDataRole.UserRole)
        data = self.strategies.get(strategy_id, {})
        
        if data.get('_source') != 'user':
            QMessageBox.information(
                self.window(), "Информация",
                "Встроенные стратегии нельзя редактировать.\n"
                "Создайте новую на их основе."
            )
            return
        
        dialog = StrategyEditorDialog(
            self.window(),
            strategy_data=data,
            category=self.current_category,
            is_new=False
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._save_strategy(result, is_new=False)
    
    def _delete_strategy(self):
        current = self.strategies_list.currentItem()
        if not current:
            return
        
        strategy_id = current.data(Qt.ItemDataRole.UserRole)
        data = self.strategies.get(strategy_id, {})
        
        if data.get('_source') != 'user':
            return
        
        reply = QMessageBox.question(
            self.window(),
            "Удаление",
            f"Удалить стратегию '{data.get('name', strategy_id)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from strategy_menu.strategies.strategy_loader import delete_user_strategy
                
                success, error = delete_user_strategy(self.current_category, strategy_id)
                
                if success:
                    self._load_strategies()
                    self._clear_cache()
                    self.strategies_changed.emit()
                else:
                    QMessageBox.warning(self.window(), "Ошибка", f"Не удалось удалить: {error}")
                    
            except Exception as e:
                log(f"Ошибка удаления: {e}", "ERROR")
    
    def _save_strategy(self, data: dict, is_new: bool):
        try:
            from strategy_menu.strategies.strategy_loader import save_user_strategy
            
            success, error = save_user_strategy(self.current_category, data)
            
            if success:
                self._load_strategies()
                self._clear_cache()
                self.strategies_changed.emit()
            else:
                QMessageBox.warning(self.window(), "Ошибка", f"Не удалось сохранить: {error}")
                
        except Exception as e:
            log(f"Ошибка сохранения: {e}", "ERROR")
    
    def _clear_cache(self):
        try:
            from strategy_menu.strategies_registry import _strategies_cache, _imported_types
            
            if self.current_category in _strategies_cache:
                del _strategies_cache[self.current_category]
            if self.current_category in _imported_types:
                _imported_types.discard(self.current_category)
                
        except Exception as e:
            log(f"Ошибка очистки кэша: {e}", "WARNING")

