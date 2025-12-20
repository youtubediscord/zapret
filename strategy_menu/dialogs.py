# strategy_menu/dialogs.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextBrowser, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from log import log
from .constants import LABEL_TEXTS, LABEL_COLORS

class StrategyInfoDialog(QDialog):
    """Отдельное окно для отображения подробной информации о стратегии."""
    
    def __init__(self, parent=None, strategy_manager=None):
        super().__init__(parent)
        self.strategy_manager = strategy_manager
        self.setWindowTitle("Информация о стратегии")
        self.resize(700, 500)
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса окна информации."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Заголовок
        self.strategy_title = QLabel("Информация о стратегии")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.strategy_title.setFont(title_font)
        self.strategy_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.strategy_title)
        
        # Детальная информация
        self.strategy_info = QTextBrowser()
        self.strategy_info.setOpenExternalLinks(True)
        self.strategy_info.setStyleSheet(
            "background-color: #333333; color: #ffffff; font-size: 9pt;"
        )
        layout.addWidget(self.strategy_info)
        
        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        close_button.setMaximumWidth(100)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def display_strategy_info(self, strategy_id, strategy_name):
        """Отображает информацию о выбранной стратегии."""
        try:
            strategies = self.strategy_manager.get_strategies_list()
            if strategy_id in strategies:
                strategy_info = strategies[strategy_id]
                
                # Устанавливаем заголовок
                title_text = strategy_info.get('name') or strategy_id
                
                # Добавляем метку
                label = strategy_info.get('label') or None
                if label and label in LABEL_TEXTS:
                    title_text += f" [{LABEL_TEXTS[label]}]"
                    label_color = LABEL_COLORS.get(label, "#000000")
                    self.strategy_title.setStyleSheet(f"color: {label_color};")
                else:
                    self.strategy_title.setStyleSheet("")
                
                self.strategy_title.setText(title_text)
                
                # Формируем HTML
                html = self._format_strategy_info_html(strategy_info, label)
                self.strategy_info.setHtml(html)
            else:
                self.strategy_info.setHtml(
                    "<p style='color:red; text-align: center;'>Информация не найдена</p>"
                )
        except Exception as e:
            log(f"Ошибка при получении информации: {str(e)}", level="❌ ERROR")
            self.strategy_info.setHtml(
                f"<p style='color:red; text-align: center;'>Ошибка: {str(e)}</p>"
            )
    
    def _format_strategy_info_html(self, strategy_info, label):
        """Форматирует HTML для отображения информации о стратегии."""
        html = """<style>
            body {font-family: Arial; margin: 5px; color: #ffffff; 
                  background-color: #333333; font-size: 9pt;}
        </style>"""
        
        # Метка
        if label and label in LABEL_TEXTS:
            html += f"""<p style='text-align: center; padding: 5px; 
                background-color: {LABEL_COLORS.get(label, '#000000')}; 
                color: white; font-weight: bold; font-size: 10pt; 
                border-radius: 3px;'>{LABEL_TEXTS[label]}</p>"""
        
        # Описание
        description = strategy_info.get('description') or 'Описание отсутствует'
        html += f"<h4>Описание</h4><p>{description}</p>"
        
        # Основная информация
        html += "<h4>Информация</h4><table style='width: 100%;'>"
        
        provider = strategy_info.get('provider') or 'universal'
        html += f"<tr><td><b>Провайдер:</b></td><td>{provider}</td></tr>"
        
        version = strategy_info.get('version') or 'неизвестно'
        html += f"<tr><td><b>Версия:</b></td><td>{version}</td></tr>"
        
        author = strategy_info.get('author') or 'неизвестно'
        html += f"<tr><td><b>Автор:</b></td><td>{author}</td></tr>"
        
        date = strategy_info.get('date') or strategy_info.get('updated') or 'неизвестно'
        html += f"<tr><td><b>Дата:</b></td><td>{date}</td></tr>"
        
        html += "</table>"
        
        # Технические параметры
        html += "<h4>Технические параметры</h4>"
        
        ports = strategy_info.get('ports', [])
        if ports:
            ports_str = ", ".join(map(str, ports)) if isinstance(ports, list) else str(ports)
            html += f"<p><b>Порты:</b> {ports_str}</p>"
        
        host_lists = strategy_info.get('host_lists', [])
        if host_lists and not (isinstance(host_lists, list) and 'ВСЕ САЙТЫ' in host_lists):
            html += "<p><b>Списки хостов:</b> "
            if isinstance(host_lists, list):
                html += ", ".join(host_lists[:3])
                if len(host_lists) > 3:
                    html += f" и еще {len(host_lists) - 3}"
            else:
                html += str(host_lists)
            html += "</p>"
        elif 'ВСЕ САЙТЫ' in str(host_lists):
            html += "<p><b>Режим:</b> <span style='color:#00ff00;'>• ВСЕ САЙТЫ</span></p>"
        
        return html