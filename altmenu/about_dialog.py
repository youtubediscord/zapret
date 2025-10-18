from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QMessageBox, QTabWidget, QWidget,
    QScrollArea, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QFont, QPixmap

from config import APP_VERSION
from config.urls import INFO_URL, BOLVAN_URL


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        from tgram import get_client_id

        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(600, 500)
        
        # Получаем текущую тему и цвета
        self.theme_info = self._get_current_theme_info(parent)
        
        # Применяем стили в зависимости от темы
        self._apply_theme_styles()
        
        cid = get_client_id()

        # Корневой layout
        vbox = QVBoxLayout(self)

        # Заголовок с версией
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 5)
        
        title = QLabel(f"<h2 style='margin: 0;'>🚀 Zapret GUI</h2>")
        version_label = QLabel(f"<span>Версия: <b>{APP_VERSION}</b></span>")
        
        header_layout.addWidget(title)
        header_layout.addWidget(version_label)
        
        # ID устройства
        id_frame = QFrame()
        id_frame.setFrameStyle(QFrame.Shape.Box)
        id_frame.setStyleSheet(self._get_id_frame_style())
        
        id_layout = QHBoxLayout(id_frame)
        id_label = QLabel(f"🔑 ID устройства: <code style='font-family: monospace; padding: 2px 4px; border-radius: 3px;'>{cid}</code>")
        id_layout.addWidget(id_label)
        
        header_layout.addWidget(id_frame)
        vbox.addWidget(header_widget)

        # Табы
        tabs = QTabWidget()
        
        # Вкладка "Основная информация"
        info_tab = self._create_info_tab()
        tabs.addTab(info_tab, "ℹ️ Информация")
        
        # Вкладка "Телеграм каналы"
        channels_tab = self._create_channels_tab()
        tabs.addTab(channels_tab, "💬 Телеграм")
        
        vbox.addWidget(tabs)

        # Нижняя панель с кнопками
        bottom_frame = QFrame()
        bottom_frame.setFrameStyle(QFrame.Shape.NoFrame)
        bottom_layout = QHBoxLayout(bottom_frame)
        
        btn_copy = QPushButton("📋 Копировать ID")
        btn_copy.setObjectName("copyBtn")
        btn_copy.setStyleSheet(self._get_button_style("copy"))
        btn_copy.clicked.connect(lambda: self._copy_cid(cid))
        bottom_layout.addWidget(btn_copy)
        
        bottom_layout.addStretch()
        
        btn_close = QPushButton("✖ Закрыть")
        btn_close.setStyleSheet(self._get_button_style("close"))
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        
        vbox.addWidget(bottom_frame)

    def _get_current_theme_info(self, parent):
        """Получает информацию о текущей теме"""
        theme_info = {
            'name': 'default',
            'is_dark': True,
            'is_amoled': False,
            'is_pure_black': False,
            'button_color': '0, 125, 242',
            'status_color': '#ffffff',
            'accent_color': '#0088cc'
        }
        
        try:
            # Пытаемся получить theme_manager из родителя
            if parent and hasattr(parent, 'theme_manager'):
                from ui.theme import THEMES
                theme_manager = parent.theme_manager
                current_theme = theme_manager.current_theme
                
                theme_info['name'] = current_theme
                
                # Определяем тип темы
                theme_info['is_dark'] = (
                    current_theme.startswith("Темная") or 
                    current_theme.startswith("AMOLED") or
                    current_theme == "Полностью черная" or
                    current_theme == "РКН Тян"
                )
                
                theme_info['is_amoled'] = current_theme.startswith("AMOLED")
                theme_info['is_pure_black'] = current_theme == "Полностью черная"
                
                # Получаем цвета из темы
                if current_theme in THEMES:
                    theme_data = THEMES[current_theme]
                    theme_info['button_color'] = theme_data.get('button_color', '0, 125, 242')
                    theme_info['status_color'] = theme_data.get('status_color', '#ffffff')
                    
                    # Преобразуем RGB в hex для accent_color
                    try:
                        rgb = [int(x.strip()) for x in theme_info['button_color'].split(',')]
                        theme_info['accent_color'] = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                    except:
                        theme_info['accent_color'] = '#0088cc'
                        
        except Exception as e:
            from log import log
            log(f"Ошибка получения информации о теме: {e}", "WARNING")
            
        return theme_info

    def _apply_theme_styles(self):
        """Применяет стили диалога в зависимости от темы"""
        if self.theme_info['is_pure_black']:
            # Стили для полностью черной темы
            self.setStyleSheet(self._get_pure_black_styles())
        elif self.theme_info['is_amoled']:
            # Стили для AMOLED тем
            self.setStyleSheet(self._get_amoled_styles())
        elif self.theme_info['is_dark']:
            # Стили для темных тем
            self.setStyleSheet(self._get_dark_theme_styles())
        else:
            # Стили для светлых тем
            self.setStyleSheet(self._get_light_theme_styles())

    def _get_pure_black_styles(self):
        """Стили для полностью черной темы"""
        return f"""
            QDialog {{
                background-color: #000000;
                color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid #333333;
                background-color: #000000;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: #1a1a1a;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: #2a2a2a;
                border-bottom: 2px solid #666666;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #0a0a0a;
                color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }}
            QLabel {{
                color: #ffffff;
            }}
            QLabel a {{
                color: #888888;
                text-decoration: none;
            }}
            QLabel a:hover {{
                color: #aaaaaa;
                text-decoration: underline;
            }}
        """

    def _get_amoled_styles(self):
        """Стили для AMOLED тем"""
        accent = self.theme_info['accent_color']
        return f"""
            QDialog {{
                background-color: #000000;
                color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid #222222;
                background-color: #000000;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: #000000;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #222222;
            }}
            QTabBar::tab:selected {{
                background-color: #111111;
                border-bottom: 2px solid {accent};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #222222;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #000000;
                color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }}
            QLabel {{
                color: #ffffff;
            }}
            QLabel a {{
                color: {accent};
                text-decoration: none;
            }}
            QLabel a:hover {{
                text-decoration: underline;
            }}
        """

    def _get_dark_theme_styles(self):
        """Стили для обычных темных тем"""
        accent = self.theme_info['accent_color']
        return f"""
            QDialog {{
                background-color: #2b2b2b;
                color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid #3c3c3c;
                background-color: #353535;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: #353535;
                border-bottom: 2px solid {accent};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #2b2b2b;
                color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }}
            QLabel {{
                color: #ffffff;
            }}
            QLabel a {{
                color: {accent};
                text-decoration: none;
            }}
            QLabel a:hover {{
                text-decoration: underline;
            }}
        """

    def _get_light_theme_styles(self):
        """Стили для светлых тем"""
        accent = self.theme_info['accent_color']
        return f"""
            QDialog {{
                background-color: #f5f5f5;
                color: #333333;
            }}
            QTabWidget::pane {{
                border: 1px solid #d0d0d0;
                background-color: white;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: #e8e8e8;
                color: #333333;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                border-bottom: 2px solid {accent};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
                color: #333333;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #333333;
            }}
            QLabel {{
                color: #333333;
            }}
            QLabel a {{
                color: {accent};
                text-decoration: none;
            }}
            QLabel a:hover {{
                text-decoration: underline;
            }}
        """

    def _get_id_frame_style(self):
        """Стиль для фрейма с ID"""
        if self.theme_info['is_pure_black']:
            return """
                QFrame {
                    background-color: #1a1a1a;
                    border: 1px solid #333333;
                    border-radius: 4px;
                    padding: 5px;
                }
            """
        elif self.theme_info['is_amoled']:
            return """
                QFrame {
                    background-color: #111111;
                    border: 1px solid #222222;
                    border-radius: 4px;
                    padding: 5px;
                }
            """
        elif self.theme_info['is_dark']:
            return """
                QFrame {
                    background-color: #3c3c3c;
                    border: 1px solid #4a4a4a;
                    border-radius: 4px;
                    padding: 5px;
                }
            """
        else:
            return """
                QFrame {
                    background-color: #e8f4fd;
                    border: 1px solid #bee5eb;
                    border-radius: 4px;
                    padding: 5px;
                }
            """

    def _get_button_style(self, button_type):
        """Получает стиль для кнопки в зависимости от типа и темы"""
        if self.theme_info['is_pure_black']:
            if button_type == "copy":
                return """
                    QPushButton {
                        background-color: #2a2a2a;
                        color: white;
                        border: 1px solid #444444;
                        padding: 6px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-height: 30px;
                    }
                    QPushButton:hover {
                        background-color: #3a3a3a;
                        border: 1px solid #555555;
                    }
                """
            else:
                return """
                    QPushButton {
                        background-color: #1a1a1a;
                        color: white;
                        border: 1px solid #333333;
                        padding: 6px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-height: 30px;
                    }
                    QPushButton:hover {
                        background-color: #2a2a2a;
                        border: 1px solid #444444;
                    }
                """
        elif self.theme_info['is_dark']:
            color = self.theme_info['button_color']
            return f"""
                QPushButton {{
                    background-color: rgb({color});
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    background-color: rgba({color}, 0.8);
                }}
            """
        else:
            color = self.theme_info['button_color']
            return f"""
                QPushButton {{
                    background-color: rgb({color});
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    background-color: rgba({color}, 0.8);
                }}
            """

    def _create_info_tab(self):
        """Создает вкладку с основной информацией"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        info_html = f"""
        <style>
            p {{ margin: 8px 0; line-height: 1.6; }}
        </style>
        <p>📖 <a href="{INFO_URL}">Руководство пользователя</a></p>
        <p>👨‍💻 Автор GUI: <a href="https://t.me/bypassblock">@bypassblock</a></p>
        <p>🔧 Автор Zapret: <a href="{BOLVAN_URL}">bol-van (GitHub)</a></p>
        <p>💬 Поддержка: <a href="https://t.me/youtubenotwork">@youtubenotwork</a></p>
        <br>
        <p style="font-size: 11px;">
        Zapret GUI - это графический интерфейс для утилиты обхода блокировок.<br>
        Программа помогает настроить и управлять параметрами обхода.
        </p>
        """
        
        info_label = QLabel(info_html)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setOpenExternalLinks(True)
        info_label.setWordWrap(True)
        
        layout.addWidget(info_label)
        layout.addStretch()
        
        return widget

    def _create_channels_tab(self):
        """Создает вкладку с телеграм каналами"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        
        # Создаем область прокрутки
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Папка с чатами
        folder_group = self._create_link_group("📂 Папка с чатами", [
            ("Все наши каналы одним списком", "https://t.me/addlist/xjPs164MI7AxZWE6")
        ])
        layout.addWidget(folder_group)
        
        # Основные каналы
        main_channels = self._create_link_group("💬 Основные каналы", [
            ("👅 Основная группа", "https://t.me/bypassblock/399"),
            ("🧩 Группа по блокировкам", "https://t.me/youtubenotwork"),
            ("😹 Android и VPN сервисы", "https://t.me/zapretyoutubediscordvpn"),
            ("🤖 Популярные моды APK", "https://t.me/androidawesome"),
            ("🔗 Переходник (все каналы)", "https://t.me/runetvpnyoutubediscord")
        ])
        layout.addWidget(main_channels)
        
        # О Zapret
        zapret_channels = self._create_link_group("📦 О Zapret", [
            ("☺️ Скачать Zapret (все версии)", "https://t.me/zapretnetdiscordyoutube"),
            ("ℹ️ Скачать Blockcheck", "https://t.me/zapretblockcheck"),
            ("😒 Дорожная карта", "https://t.me/approundmap"),
            ("❓ Помощь с настройками", "https://t.me/zaprethelp"),
            ("😷 Вирусы в Запрете?", "https://t.me/zapretvirus")
        ])
        layout.addWidget(zapret_channels)
        
        # Боты
        bots_group = self._create_link_group("🤖 Боты", [
            ("☺️ ИИ помощник по обходу", "https://t.me/zapretbypass_bot"),
            ("💵 Платный VPN от команды", "https://t.me/zapretvpns_bot")
        ])
        layout.addWidget(bots_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        return widget

    def _create_link_group(self, title, links):
        """Создает группу ссылок"""
        group = QGroupBox(title)
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        hover_bg = "#f0f8ff" if not self.theme_info['is_dark'] else "#2a2a2a"
        if self.theme_info['is_pure_black']:
            hover_bg = "#1a1a1a"
        elif self.theme_info['is_amoled']:
            hover_bg = "#111111"
        
        for text, url in links:
            link_label = QLabel(f'<a href="{url}">{text}</a>')
            link_label.setTextFormat(Qt.TextFormat.RichText)
            link_label.setOpenExternalLinks(True)
            link_label.setStyleSheet(f"""
                QLabel {{
                    padding: 4px 8px;
                    background-color: transparent;
                    border-radius: 3px;
                }}
                QLabel:hover {{
                    background-color: {hover_bg};
                }}
            """)
            layout.addWidget(link_label)
        
        group.setLayout(layout)
        return group

    def _copy_cid(self, cid: str):
        """Копирует CID в clipboard и показывает уведомление"""
        QGuiApplication.clipboard().setText(cid)
        msg = QMessageBox(self)
        msg.setWindowTitle("Успешно")
        msg.setText("ID устройства скопирован в буфер обмена")
        msg.setIcon(QMessageBox.Icon.Information)
        
        # Применяем стиль к MessageBox в зависимости от темы
        if self.theme_info['is_dark']:
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2b2b2b;
                    color: white;
                }
                QPushButton {
                    min-width: 80px;
                    background-color: #3c3c3c;
                    color: white;
                    border: 1px solid #4a4a4a;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)
        
        msg.exec()
