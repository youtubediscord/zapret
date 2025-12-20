# ui/pages/blobs_page.py
"""Страница управления блобами (Zapret 2 / Direct режим)"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QMessageBox, QLineEdit,
    QPushButton, QFileDialog, QDialog, QFormLayout,
    QComboBox, QSizePolicy
)
from PyQt6.QtGui import QFont
import qtawesome as qta
import os

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton
from log import log


class BlobItemWidget(QFrame):
    """Виджет одного блоба в списке"""
    
    deleted = pyqtSignal(str)  # имя блоба
    
    def __init__(self, name: str, info: dict, parent=None):
        super().__init__(parent)
        self.blob_name = name
        self.blob_info = info
        # Политика размера: предпочитает минимальную ширину
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()
        
    def _build_ui(self):
        self.setStyleSheet("""
            BlobItemWidget {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                padding: 8px;
            }
            BlobItemWidget:hover {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Иконка типа
        icon_label = QLabel()
        if self.blob_info.get("type") == "hex":
            icon_label.setPixmap(qta.icon('fa5s.hashtag', color='#ffc107').pixmap(16, 16))
        else:
            icon_label.setPixmap(qta.icon('fa5s.file', color='#60cdff').pixmap(16, 16))
        layout.addWidget(icon_label)
        
        # Информация о блобе
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Имя + метка пользовательского
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        
        name_label = QLabel(self.blob_name)
        name_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
        name_layout.addWidget(name_label)
        
        if self.blob_info.get("is_user"):
            user_badge = QLabel("пользовательский")
            user_badge.setStyleSheet("""
                QLabel {
                    color: #ffc107;
                    font-size: 10px;
                    background: rgba(255, 193, 7, 0.15);
                    padding: 2px 6px;
                    border-radius: 3px;
                }
            """)
            name_layout.addWidget(user_badge)
        
        name_layout.addStretch()
        info_layout.addLayout(name_layout)
        
        # Описание
        desc = self.blob_info.get("description", "")
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
            desc_label.setWordWrap(True)
            info_layout.addWidget(desc_label)
        
        # Значение (путь или hex)
        value = self.blob_info.get("value", "")
        if value:
            if value.startswith("@"):
                # Показываем только имя файла для путей
                display_value = os.path.basename(value[1:])
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value
            
            value_label = QLabel(display_value)
            value_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px; font-family: Consolas;")
            info_layout.addWidget(value_label)
        
        layout.addLayout(info_layout, 1)
        
        # Статус существования файла
        if self.blob_info.get("type") == "file":
            if self.blob_info.get("exists", True):
                status = QLabel("✓")
                status.setStyleSheet("color: #6ccb5f; font-size: 14px;")
                status.setToolTip("Файл найден")
            else:
                status = QLabel("✗")
                status.setStyleSheet("color: #ff6b6b; font-size: 14px;")
                status.setToolTip("Файл не найден")
            layout.addWidget(status)
        
        # Кнопка удаления (только для пользовательских)
        if self.blob_info.get("is_user"):
            delete_btn = QPushButton()
            delete_btn.setIcon(qta.icon('fa5s.trash-alt', color='#ff6b6b'))
            delete_btn.setFixedSize(28, 28)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 107, 107, 0.1);
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 107, 107, 0.25);
                }
            """)
            delete_btn.clicked.connect(self._on_delete)
            layout.addWidget(delete_btn)
            
    def _on_delete(self):
        """Запрос на удаление блоба"""
        reply = QMessageBox.question(
            self.window(),
            "Удаление блоба",
            f"Удалить пользовательский блоб '{self.blob_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.deleted.emit(self.blob_name)


class AddBlobDialog(QDialog):
    """Диалог добавления нового блоба в стиле Windows 11"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить блоб")
        self.setFixedWidth(420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        
    def _build_ui(self):
        # Основной контейнер с тенью
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        container = QFrame()
        container.setObjectName("dialogContainer")
        container.setStyleSheet("""
            QFrame#dialogContainer {
                background: #2d2d2d;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # Заголовок с кнопкой закрытия
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 8)
        
        title = QLabel("Добавить блоб")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
        """)
        header.addWidget(title)
        header.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                color: rgba(255, 255, 255, 0.6);
                font-size: 18px;
                font-weight: 400;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }
        """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        
        layout.addLayout(header)
        
        # Стили для полей ввода
        input_style = """
            QLineEdit, QComboBox {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 13px;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid rgba(96, 205, 255, 0.6);
                background: rgba(255, 255, 255, 0.06);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.35);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.5);
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #2d2d2d;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                selection-background-color: rgba(96, 205, 255, 0.2);
                outline: none;
            }
        """
        
        label_style = "color: rgba(255, 255, 255, 0.7); font-size: 12px; margin-bottom: 4px;"
        
        # Имя блоба
        name_label = QLabel("Имя")
        name_label.setStyleSheet(label_style)
        layout.addWidget(name_label)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Латиница, цифры, подчеркивания")
        self.name_edit.setStyleSheet(input_style)
        self.name_edit.setFixedHeight(32)
        layout.addWidget(self.name_edit)
        
        # Тип
        type_label = QLabel("Тип")
        type_label.setStyleSheet(label_style)
        layout.addWidget(type_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("Файл (.bin)", "file")
        self.type_combo.addItem("Hex значение", "hex")
        self.type_combo.setStyleSheet(input_style)
        self.type_combo.setFixedHeight(32)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)
        
        # Значение
        value_label = QLabel("Значение")
        value_label.setStyleSheet(label_style)
        layout.addWidget(value_label)
        
        self.value_widget = QWidget()
        value_layout = QHBoxLayout(self.value_widget)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(6)
        
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Путь к файлу")
        self.value_edit.setStyleSheet(input_style)
        self.value_edit.setFixedHeight(32)
        value_layout.addWidget(self.value_edit, 1)
        
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedSize(32, 32)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }
        """)
        self.browse_btn.clicked.connect(self._browse_file)
        value_layout.addWidget(self.browse_btn)
        
        layout.addWidget(self.value_widget)
        
        # Описание
        desc_label = QLabel("Описание (опционально)")
        desc_label.setStyleSheet(label_style)
        layout.addWidget(desc_label)
        
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Краткое описание блоба")
        self.desc_edit.setStyleSheet(input_style)
        self.desc_edit.setFixedHeight(32)
        layout.addWidget(self.desc_edit)
        
        # Отступ перед кнопками
        layout.addSpacing(8)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedHeight(28)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 0 16px;
                color: rgba(255, 255, 255, 0.8);
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Добавить")
        save_btn.setFixedHeight(28)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #60cdff;
                border: none;
                border-radius: 4px;
                padding: 0 20px;
                color: #000000;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background: #4fc3f7;
            }
            QPushButton:pressed {
                background: #29b6f6;
            }
        """)
        save_btn.clicked.connect(self._save)
        buttons_layout.addWidget(save_btn)
        
        layout.addLayout(buttons_layout)
        main_layout.addWidget(container)
    
    def mousePressEvent(self, event):
        """Перетаскивание окна"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Перетаскивание окна"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        
    def _on_type_changed(self, index):
        """Переключение типа блоба"""
        blob_type = self.type_combo.currentData()
        self.browse_btn.setVisible(blob_type == "file")
        if blob_type == "hex":
            self.value_edit.setPlaceholderText("Hex значение (например: 0x0E0E0F0E)")
        else:
            self.value_edit.setPlaceholderText("Путь к .bin файлу")
            
    def _browse_file(self):
        """Выбор файла"""
        from config import BIN_FOLDER
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл блоба",
            BIN_FOLDER,
            "Binary files (*.bin);;All files (*.*)"
        )
        if file_path:
            # Если файл в BIN_FOLDER - сохраняем относительный путь
            if file_path.startswith(BIN_FOLDER):
                file_path = os.path.relpath(file_path, BIN_FOLDER)
            self.value_edit.setText(file_path)
            
    def _save(self):
        """Валидация и сохранение"""
        name = self.name_edit.text().strip()
        value = self.value_edit.text().strip()
        
        # Валидация имени
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите имя блоба")
            return
            
        import re
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            QMessageBox.warning(
                self, "Ошибка", 
                "Имя должно начинаться с буквы и содержать только латиницу, цифры и подчеркивания"
            )
            return
            
        # Валидация значения
        if not value:
            QMessageBox.warning(self, "Ошибка", "Введите значение блоба")
            return
            
        blob_type = self.type_combo.currentData()
        if blob_type == "hex" and not value.startswith("0x"):
            QMessageBox.warning(self, "Ошибка", "Hex значение должно начинаться с 0x")
            return
            
        self.accept()
        
    def get_data(self) -> dict:
        """Возвращает данные нового блоба"""
        return {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentData(),
            "value": self.value_edit.text().strip(),
            "description": self.desc_edit.text().strip()
        }


class BlobsPage(BasePage):
    """Страница управления блобами"""
    
    def __init__(self, parent=None):
        super().__init__("Блобы", "Управление бинарными данными для стратегий", parent)
        self._build_ui()
        
    def _build_ui(self):
        """Строит UI страницы"""
        
        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            "Блобы — это бинарные данные (файлы .bin или hex-значения), "
            "используемые в стратегиях для имитации TLS/QUIC пакетов.\n"
            "Вы можете добавлять свои блобы для кастомных стратегий."
        )
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)
        
        # Панель действий
        actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        # Кнопка добавления
        self.add_btn = ActionButton("Добавить блоб", "fa5s.plus")
        self.add_btn.clicked.connect(self._add_blob)
        actions_layout.addWidget(self.add_btn)
        
        # Кнопка перезагрузки
        self.reload_btn = ActionButton("Обновить", "fa5s.sync-alt")
        self.reload_btn.clicked.connect(self._reload_blobs)
        actions_layout.addWidget(self.reload_btn)
        
        # Открыть папку bin
        self.open_folder_btn = ActionButton("Папка bin", "fa5s.folder-open")
        self.open_folder_btn.clicked.connect(self._open_bin_folder)
        actions_layout.addWidget(self.open_folder_btn)
        
        # Открыть JSON
        self.open_json_btn = ActionButton("Открыть JSON", "fa5s.file-code")
        self.open_json_btn.clicked.connect(self._open_json)
        actions_layout.addWidget(self.open_json_btn)
        
        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        
        # Счётчик под кнопками
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px; padding-top: 4px;")
        actions_card.add_widget(self.count_label)
        
        self.layout.addWidget(actions_card)
        
        # Фильтр поиска
        filter_card = SettingsCard()
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_icon = QLabel()
        filter_icon.setPixmap(qta.icon('fa5s.search', color='#808080').pixmap(14, 14))
        filter_layout.addWidget(filter_icon)
        
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Фильтр по имени...")
        self.filter_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        self.filter_edit.textChanged.connect(self._filter_blobs)
        filter_layout.addWidget(self.filter_edit, 1)
        
        filter_card.add_layout(filter_layout)
        self.layout.addWidget(filter_card)
        
        # Контейнер для блобов
        self.blobs_container = QWidget()
        self.blobs_container.setStyleSheet("background: transparent;")
        self.blobs_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.blobs_layout = QVBoxLayout(self.blobs_container)
        self.blobs_layout.setContentsMargins(0, 0, 0, 0)
        self.blobs_layout.setSpacing(6)
        
        self.layout.addWidget(self.blobs_container)
        
        # Загружаем блобы
        QTimer.singleShot(100, self._load_blobs)
        
    def _load_blobs(self):
        """Загружает и отображает список блобов"""
        try:
            from strategy_menu.strategies.blobs import get_blobs_info
            
            # Очищаем контейнер
            while self.blobs_layout.count():
                item = self.blobs_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            blobs_info = get_blobs_info()
            
            # Разделяем на пользовательские и системные
            user_blobs = {k: v for k, v in blobs_info.items() if v.get("is_user")}
            system_blobs = {k: v for k, v in blobs_info.items() if not v.get("is_user")}
            
            # Секция пользовательских блобов
            if user_blobs:
                user_header = QLabel(f"★ Пользовательские ({len(user_blobs)})")
                user_header.setStyleSheet("""
                    QLabel {
                        color: #ffc107;
                        font-size: 12px;
                        font-weight: 600;
                        padding: 8px 4px 4px 4px;
                    }
                """)
                self.blobs_layout.addWidget(user_header)
                
                for name, info in sorted(user_blobs.items()):
                    item = BlobItemWidget(name, info)
                    item.deleted.connect(self._delete_blob)
                    self.blobs_layout.addWidget(item)
            
            # Секция системных блобов
            if system_blobs:
                system_header = QLabel(f"Системные ({len(system_blobs)})")
                system_header.setStyleSheet("""
                    QLabel {
                        color: rgba(255, 255, 255, 0.5);
                        font-size: 12px;
                        font-weight: 600;
                        padding: 12px 4px 4px 4px;
                    }
                """)
                self.blobs_layout.addWidget(system_header)
                
                for name, info in sorted(system_blobs.items()):
                    item = BlobItemWidget(name, info)
                    self.blobs_layout.addWidget(item)
            
            # Обновляем счётчик
            total = len(blobs_info)
            user_count = len(user_blobs)
            self.count_label.setText(f"{total} блобов ({user_count} пользовательских)")
            
        except Exception as e:
            log(f"Ошибка загрузки блобов: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            
            error_label = QLabel(f"❌ Ошибка загрузки: {e}")
            error_label.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            self.blobs_layout.addWidget(error_label)
            
    def _filter_blobs(self, text: str):
        """Фильтрует блобы по тексту"""
        text = text.lower()
        for i in range(self.blobs_layout.count()):
            item = self.blobs_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, BlobItemWidget):
                    # Показываем если имя или описание содержит текст
                    match = (text in widget.blob_name.lower() or 
                            text in widget.blob_info.get("description", "").lower())
                    widget.setVisible(match)
                elif isinstance(widget, QLabel):
                    # Заголовки секций - показываем всегда
                    pass
                    
    def _add_blob(self):
        """Открывает диалог добавления блоба"""
        dialog = AddBlobDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                from strategy_menu.strategies.blobs import save_user_blob
                
                if save_user_blob(data["name"], data["type"], data["value"], data["description"]):
                    log(f"Добавлен блоб: {data['name']}", "INFO")
                    self._load_blobs()  # Перезагружаем список
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось сохранить блоб")
                    
            except Exception as e:
                log(f"Ошибка добавления блоба: {e}", "ERROR")
                QMessageBox.warning(self, "Ошибка", f"Не удалось добавить блоб:\n{e}")
                
    def _delete_blob(self, name: str):
        """Удаляет пользовательский блоб"""
        try:
            from strategy_menu.strategies.blobs import delete_user_blob
            
            if delete_user_blob(name):
                log(f"Удалён блоб: {name}", "INFO")
                self._load_blobs()  # Перезагружаем список
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить блоб '{name}'")
                
        except Exception as e:
            log(f"Ошибка удаления блоба: {e}", "ERROR")
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить блоб:\n{e}")
            
    def _reload_blobs(self):
        """Перезагружает блобы из JSON"""
        try:
            from strategy_menu.strategies.blobs import reload_blobs
            reload_blobs()
            self._load_blobs()
            log("Блобы перезагружены", "INFO")
        except Exception as e:
            log(f"Ошибка перезагрузки блобов: {e}", "ERROR")
            
    def _open_bin_folder(self):
        """Открывает папку bin"""
        try:
            from config import BIN_FOLDER
            os.startfile(BIN_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку:\n{e}")
            
    def _open_json(self):
        """Открывает файл blobs.json в редакторе"""
        try:
            from config import INDEXJSON_FOLDER
            json_path = os.path.join(INDEXJSON_FOLDER, "blobs.json")
            os.startfile(json_path)
        except Exception as e:
            log(f"Ошибка открытия JSON: {e}", "ERROR")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл:\n{e}")

