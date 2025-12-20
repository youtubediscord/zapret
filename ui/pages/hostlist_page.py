# ui/pages/hostlist_page.py
"""Страница управления хостлистами"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy)
from PyQt6.QtGui import QFont
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton
from log import log


class HostlistPage(BasePage):
    """Страница управления хостлистами"""
    
    def __init__(self, parent=None):
        super().__init__("Hostlist", "Управление списками доменов для обхода блокировок", parent)
        self._build_ui()
        
    def _build_ui(self):
        """Строит UI страницы"""
        
        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            "Хостлисты содержат домены, для которых применяется обход блокировок.\n"
            "Вы можете добавлять свои домены или использовать готовые списки."
        )
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)
        
        # Кнопки действий
        actions_card = SettingsCard("Действия")
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        
        # Открыть папку
        open_row = QWidget()
        open_layout = QHBoxLayout(open_row)
        open_layout.setContentsMargins(0, 0, 0, 0)
        
        open_icon = QLabel()
        open_icon.setPixmap(qta.icon('fa5s.folder-open', color='#60cdff').pixmap(18, 18))
        open_layout.addWidget(open_icon)
        
        open_text = QLabel("Открыть папку хостлистов")
        open_text.setStyleSheet("color: #ffffff; font-size: 13px;")
        open_layout.addWidget(open_text, 1)
        
        self.open_hostlist_btn = ActionButton("Открыть", "fa5s.external-link-alt")
        self.open_hostlist_btn.setFixedHeight(32)
        self.open_hostlist_btn.clicked.connect(self._open_hostlist_folder)
        open_layout.addWidget(self.open_hostlist_btn)
        
        actions_layout.addWidget(open_row)
        
        # Перестроить хостлисты
        rebuild_row = QWidget()
        rebuild_layout = QHBoxLayout(rebuild_row)
        rebuild_layout.setContentsMargins(0, 0, 0, 0)
        
        rebuild_icon = QLabel()
        rebuild_icon.setPixmap(qta.icon('fa5s.sync-alt', color='#ff9800').pixmap(18, 18))
        rebuild_layout.addWidget(rebuild_icon)
        
        rebuild_text_layout = QVBoxLayout()
        rebuild_text_layout.setSpacing(2)
        rebuild_title = QLabel("Перестроить хостлисты")
        rebuild_title.setStyleSheet("color: #ffffff; font-size: 13px;")
        rebuild_text_layout.addWidget(rebuild_title)
        rebuild_desc = QLabel("Обновляет списки из встроенной базы")
        rebuild_desc.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        rebuild_text_layout.addWidget(rebuild_desc)
        rebuild_layout.addLayout(rebuild_text_layout, 1)
        
        self.rebuild_btn = ActionButton("Перестроить", "fa5s.sync-alt")
        self.rebuild_btn.setFixedHeight(32)
        self.rebuild_btn.clicked.connect(self._rebuild_hostlists)
        rebuild_layout.addWidget(self.rebuild_btn)
        
        actions_layout.addWidget(rebuild_row)
        
        actions_card.add_layout(actions_layout)
        self.layout.addWidget(actions_card)
        
        # Информация о файлах
        info_card = SettingsCard("Информация")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        self.files_info_label = QLabel("Загрузка информации...")
        self.files_info_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        self.files_info_label.setWordWrap(True)
        info_layout.addWidget(self.files_info_label)
        
        info_card.add_layout(info_layout)
        self.layout.addWidget(info_card)
        
        # Загружаем информацию
        QTimer.singleShot(100, self._load_info)
        
        self.layout.addStretch()
        
    def _open_hostlist_folder(self):
        """Открывает папку хостлистов"""
        try:
            from config import LISTS_FOLDER
            import os
            os.startfile(LISTS_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось открыть папку:\n{e}")
            
    def _rebuild_hostlists(self):
        """Перестраивает хостлисты"""
        try:
            from utils.hostlists_manager import startup_hostlists_check
            startup_hostlists_check()
                
            QMessageBox.information(self.window(), "Готово", "Хостлисты обновлены")
            self._load_info()
            
        except Exception as e:
            log(f"Ошибка перестроения: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось перестроить:\n{e}")
            
    def _load_info(self):
        """Загружает информацию о файлах"""
        try:
            from config import LISTS_FOLDER
            import os
            
            if not os.path.exists(LISTS_FOLDER):
                self.files_info_label.setText("Папка хостлистов не найдена")
                return
                
            files = [f for f in os.listdir(LISTS_FOLDER) if f.endswith('.txt')]
            total_lines = 0
            
            for f in files[:10]:  # Ограничиваем для скорости
                try:
                    path = os.path.join(LISTS_FOLDER, f)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        total_lines += sum(1 for _ in file)
                except:
                    pass
                    
            info = f"📁 Папка: {LISTS_FOLDER}\n"
            info += f"📄 Файлов: {len(files)}\n"
            info += f"📝 Примерно строк: {total_lines:,}"
            
            self.files_info_label.setText(info)
            
        except Exception as e:
            self.files_info_label.setText(f"Ошибка загрузки информации: {e}")

