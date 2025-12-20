# ui/pages/about_page.py
"""Страница О программе - справка, обновления, информация"""

import os
import webbrowser
import subprocess
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton
from log import log


class AboutPage(BasePage):
    """Страница О программе"""
    
    def __init__(self, parent=None):
        super().__init__("О программе", "Справка, обновления и информация", parent)
        
        self._build_ui()
        
    def _build_ui(self):
        from config import APP_VERSION
        
        # Информация о версии
        self.add_section_title("Версия")
        
        version_card = SettingsCard()
        version_card.setStyleSheet("""
            QFrame#settingsCard {
                background-color: rgba(255, 255, 255, 0.04);
                border: none;
                border-radius: 8px;
            }
        """)
        
        version_layout = QHBoxLayout()
        version_layout.setSpacing(16)
        
        # Иконка
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.shield-alt', color='#60cdff').pixmap(40, 40))
        icon_label.setFixedSize(48, 48)
        version_layout.addWidget(icon_label)
        
        # Текст
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel("Zapret 2 GUI")
        name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: 600;
            }
        """)
        text_layout.addWidget(name_label)
        
        version_label = QLabel(f"Версия {APP_VERSION}")
        version_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
        """)
        text_layout.addWidget(version_label)
        
        version_layout.addLayout(text_layout, 1)
        
        # Кнопка обновления
        self.update_btn = ActionButton("Проверить обновления", "fa5s.sync-alt")
        self.update_btn.setFixedHeight(36)
        version_layout.addWidget(self.update_btn)
        
        version_card.add_layout(version_layout)
        self.add_widget(version_card)
        
        self.add_spacing(16)
        
        # Подписка
        self.add_section_title("Подписка")
        
        sub_card = SettingsCard()
        sub_card.setStyleSheet("""
            QFrame#settingsCard {
                background-color: rgba(255, 255, 255, 0.04);
                border: none;
                border-radius: 8px;
            }
        """)
        
        sub_layout = QVBoxLayout()
        sub_layout.setSpacing(12)
        
        # Статус подписки
        sub_status_layout = QHBoxLayout()
        sub_status_layout.setSpacing(8)
        
        self.sub_status_icon = QLabel()
        self.sub_status_icon.setPixmap(qta.icon('fa5s.user', color='#888888').pixmap(18, 18))
        self.sub_status_icon.setFixedSize(22, 22)
        sub_status_layout.addWidget(self.sub_status_icon)
        
        self.sub_status_label = QLabel("Free версия")
        self.sub_status_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500;")
        sub_status_layout.addWidget(self.sub_status_label, 1)
        
        sub_layout.addLayout(sub_status_layout)
        
        sub_desc = QLabel(
            "Подписка Zapret Premium открывает доступ к дополнительным темам, "
            "приоритетной поддержке и VPN-сервису."
        )
        sub_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        sub_desc.setWordWrap(True)
        sub_layout.addWidget(sub_desc)
        
        sub_btns = QHBoxLayout()
        sub_btns.setSpacing(8)
        
        self.premium_btn = ActionButton("Premium и VPN", "fa5s.star", accent=True)
        self.premium_btn.setFixedHeight(36)
        sub_btns.addWidget(self.premium_btn)
        
        sub_btns.addStretch()
        sub_layout.addLayout(sub_btns)
        
        sub_card.add_layout(sub_layout)
        self.add_widget(sub_card)
        
        self.add_spacing(16)
        
        # Ссылки - разбиты на 3 отдельных виджета
        self.add_section_title("Ссылки")
        
        # --- Виджет 1: Документация ---
        docs_card = self._create_links_card("Документация")
        docs_layout = docs_card.layout()
        
        self._add_link_item(docs_layout, "fa5s.folder-open", "Папка с инструкциями", 
                           "Открыть локальную папку help", self._open_help_folder)
        
        self._add_link_item(docs_layout, "fa5b.github", "Wiki на GitHub", 
                           "Документация и руководства", self._open_wiki)
        
        self.add_widget(docs_card)
        self.add_spacing(8)
        
        # --- Виджет 2: Поддержка ---
        support_card = self._create_links_card("Поддержка")
        support_layout = support_card.layout()
        
        self._add_link_item(support_layout, "fa5b.telegram", "Telegram канал поддержки", 
                           "Помощь и вопросы по использованию", self._open_telegram)
        
        self._add_link_item(support_layout, "fa5b.discord", "Discord сервер", 
                           "Сообщество и живое общение", self._open_discord)
        
        self.add_widget(support_card)
        self.add_spacing(8)
        
        # --- Виджет 3: Новости и исходный код ---
        news_card = self._create_links_card("Новости и исходный код")
        news_layout = news_card.layout()
        
        self._add_link_item(news_layout, "fa5b.telegram", "Telegram канал", 
                           "Новости и обновления", self._open_telegram_news)
        
        self._add_link_item(news_layout, "fa5b.github", "GitHub", 
                           "Исходный код и багрепорты", self._open_github)
        
        self.add_widget(news_card)
    
    def _create_links_card(self, title: str) -> QFrame:
        """Создаёт карточку для группы ссылок без рамки с собственным фоном"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Заголовок секции
        header = QLabel(title)
        header.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                padding: 0px 4px 8px 4px;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(header)
        
        return card
    
    def _add_link_item(self, layout, icon_name, title, desc, callback):
        """Добавляет кликабельный элемент ссылки без рамок"""
        # Используем QPushButton для надежной обработки кликов
        link_widget = QPushButton()
        link_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        link_widget.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                border: none;
                border-radius: 6px; 
                padding: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.08);
            }
        """)
        link_widget.clicked.connect(callback)
        
        link_layout = QHBoxLayout(link_widget)
        link_layout.setContentsMargins(0, 0, 0, 0)
        link_layout.setSpacing(12)
        
        # Прозрачная иконка без рамки
        link_icon = QLabel()
        link_icon.setPixmap(qta.icon(icon_name, color='#60cdff').pixmap(20, 20))
        link_icon.setFixedSize(24, 24)
        link_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        link_layout.addWidget(link_icon)
        
        link_text_layout = QVBoxLayout()
        link_text_layout.setSpacing(0)
        link_text_layout.setContentsMargins(0, 0, 0, 0)

        link_title = QLabel(title)
        link_title.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 500;")
        link_title.setFixedHeight(16)
        link_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        link_text_layout.addWidget(link_title)

        link_desc = QLabel(desc)
        link_desc.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 10px;")
        link_desc.setFixedHeight(14)
        link_desc.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        link_text_layout.addWidget(link_desc)
        
        link_layout.addLayout(link_text_layout, 1)
        layout.addWidget(link_widget)
        
    def update_subscription_status(self, is_premium: bool, days: int = None):
        """Обновляет отображение статуса подписки"""
        if is_premium:
            self.sub_status_icon.setPixmap(qta.icon('fa5s.star', color='#ffc107').pixmap(18, 18))
            if days:
                self.sub_status_label.setText(f"Premium (осталось {days} дней)")
            else:
                self.sub_status_label.setText("Premium активен")
        else:
            self.sub_status_icon.setPixmap(qta.icon('fa5s.user', color='#888888').pixmap(18, 18))
            self.sub_status_label.setText("Free версия")
    
    def _open_help_folder(self):
        """Открывает папку help с инструкциями"""
        try:
            from config import HELP_FOLDER
            if os.path.exists(HELP_FOLDER):
                subprocess.Popen(f'explorer "{HELP_FOLDER}"')
                log(f"Открыта папка: {HELP_FOLDER}", "INFO")
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.window(), "Ошибка", "Папка с инструкциями не найдена")
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
    
    def _open_wiki(self):
        """Открывает Wiki на GitHub"""
        try:
            url = "https://github.com/youtubediscord/zapret"
            webbrowser.open(url)
            log(f"Открыта Wiki: {url}", "INFO")
        except Exception as e:
            log(f"Ошибка открытия Wiki: {e}", "ERROR")
    
    def _open_telegram(self):
        """Открывает Telegram канал поддержки"""
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("zaprethelp")
            log("Открыт Telegram: zaprethelp", "INFO")
        except Exception as e:
            log(f"Ошибка открытия Telegram: {e}", "ERROR")

    def _open_telegram_news(self):
        """Открывает Telegram канал новостей"""
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("bypassblock")
            log("Открыт Telegram: bypassblock", "INFO")
        except Exception as e:
            log(f"Ошибка открытия Telegram: {e}", "ERROR")
    
    def _open_discord(self):
        """Открывает Discord сервер"""
        try:
            url = "https://discord.gg/kkcBDG2uws"
            webbrowser.open(url)
            log(f"Открыт Discord: {url}", "INFO")
        except Exception as e:
            log(f"Ошибка открытия Discord: {e}", "ERROR")
    
    def _open_github(self):
        """Открывает GitHub репозиторий"""
        try:
            url = "https://github.com/youtubediscord/zapret"
            webbrowser.open(url)
            log(f"Открыт GitHub: {url}", "INFO")
        except Exception as e:
            log(f"Ошибка открытия GitHub: {e}", "ERROR")

