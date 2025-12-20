# ui/pages/ipset_page.py
"""Страница управления IP-сетами"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QMessageBox)
from PyQt6.QtGui import QFont
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton
from log import log


class IpsetPage(BasePage):
    """Страница управления IP-сетами"""
    
    def __init__(self, parent=None):
        super().__init__("IPset", "Управление IP-адресами и подсетями", parent)
        self._build_ui()
        
    def _build_ui(self):
        """Строит UI страницы"""
        
        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            "IP-сеты содержат IP-адреса и подсети для обхода блокировок по IP.\n"
            "Используются когда блокировка происходит на уровне IP-адресов."
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
        
        open_text = QLabel("Открыть папку IP-сетов")
        open_text.setStyleSheet("color: #ffffff; font-size: 13px;")
        open_layout.addWidget(open_text, 1)
        
        self.open_ipset_btn = ActionButton("Открыть", "fa5s.external-link-alt")
        self.open_ipset_btn.setFixedHeight(32)
        self.open_ipset_btn.clicked.connect(self._open_ipset_folder)
        open_layout.addWidget(self.open_ipset_btn)
        
        actions_layout.addWidget(open_row)
        
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
        
    def _open_ipset_folder(self):
        """Открывает папку IP-сетов"""
        try:
            from config import LISTS_FOLDER
            import os
            os.startfile(LISTS_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось открыть папку:\n{e}")
            
    def _load_info(self):
        """Загружает информацию о файлах"""
        try:
            from config import LISTS_FOLDER
            import os
            
            if not os.path.exists(LISTS_FOLDER):
                self.files_info_label.setText("Папка не найдена")
                return
                
            # Ищем файлы с IP
            ipset_files = [f for f in os.listdir(LISTS_FOLDER) 
                          if f.endswith('.txt') and ('ip' in f.lower() or 'subnet' in f.lower())]
            
            total_ips = 0
            for f in ipset_files[:10]:
                try:
                    path = os.path.join(LISTS_FOLDER, f)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        total_ips += sum(1 for line in file if line.strip() and not line.startswith('#'))
                except:
                    pass
                    
            info = f"📁 Папка: {LISTS_FOLDER}\n"
            info += f"📄 IP-файлов: {len(ipset_files)}\n"
            info += f"🌐 Примерно IP/подсетей: {total_ips:,}"
            
            self.files_info_label.setText(info)
            
        except Exception as e:
            self.files_info_label.setText(f"Ошибка загрузки информации: {e}")

