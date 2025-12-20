# ui/pages/control_page.py
"""Страница управления - запуск/остановка DPI"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, SettingsRow, ActionButton, StatusIndicator, PulsingDot


# Стиль для индикатора загрузки (бегающая полоска)
PROGRESS_STYLE = """
QProgressBar {
    background-color: rgba(255, 255, 255, 0.05);
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.3 #60cdff,
        stop:0.5 #60cdff,
        stop:0.7 #60cdff,
        stop:1 transparent
    );
    border-radius: 2px;
}
"""


class BigActionButton(ActionButton):
    """Большая кнопка действия"""
    
    def __init__(self, text: str, icon_name: str = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, accent, parent)
        self.setFixedHeight(48)
        self.setIconSize(QSize(20, 20))
        
    def _update_style(self):
        if self.accent:
            # Акцентная кнопка - голубая
            if self._hovered:
                bg = "rgba(96, 205, 255, 0.9)"
            else:
                bg = "#60cdff"
            text_color = "#000000"
        else:
            # Обычная кнопка - нейтральная
            if self._hovered:
                bg = "rgba(255, 255, 255, 0.15)"
            else:
                bg = "rgba(255, 255, 255, 0.08)"
            text_color = "#ffffff"
            
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: 6px;
                color: {text_color};
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }}
        """)


class StopButton(BigActionButton):
    """Кнопка остановки (нейтральная)"""
    
    def _update_style(self):
        # Нейтральная серая кнопка
        if self._hovered:
            bg = "rgba(255, 255, 255, 0.15)"
        else:
            bg = "rgba(255, 255, 255, 0.08)"
            
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }}
        """)


class ControlPage(BasePage):
    """Страница управления DPI"""
    
    def __init__(self, parent=None):
        super().__init__("Управление", "Запуск и остановка обхода блокировок", parent)
        
        self._build_ui()
        
    def _build_ui(self):
        # Статус работы
        self.add_section_title("Статус работы")
        
        status_card = SettingsCard()
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)
        
        # Пульсирующая точка статуса
        self.status_dot = PulsingDot()
        status_layout.addWidget(self.status_dot)
        
        # Текст статуса
        status_text_layout = QVBoxLayout()
        status_text_layout.setSpacing(2)
        
        self.status_title = QLabel("Проверка...")
        self.status_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
            }
        """)
        status_text_layout.addWidget(self.status_title)
        
        self.status_desc = QLabel("Определение состояния процесса")
        self.status_desc.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
        """)
        status_text_layout.addWidget(self.status_desc)
        
        status_layout.addLayout(status_text_layout, 1)
        status_card.add_layout(status_layout)
        self.add_widget(status_card)
        
        self.add_spacing(16)
        
        # Управление
        self.add_section_title("Управление Zapret")
        
        control_card = SettingsCard()
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.start_btn = BigActionButton("Запустить Zapret", "fa5s.play", accent=True)
        buttons_layout.addWidget(self.start_btn)
        
        # Кнопка остановки только winws.exe
        self.stop_winws_btn = StopButton("Остановить только winws.exe", "fa5s.stop")
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)
        
        # Кнопка полного выхода (остановка + закрытие программы)
        self.stop_and_exit_btn = StopButton("Остановить и закрыть программу", "fa5s.power-off")
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)
        
        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)
        
        self.add_widget(control_card)
        
        self.add_spacing(16)
        
        # Текущая стратегия
        self.add_section_title("Текущая стратегия")
        
        strategy_card = SettingsCard()
        
        strategy_layout = QHBoxLayout()
        strategy_layout.setSpacing(12)
        
        self.strategy_icon = QLabel()
        try:
            from ui.fluent_icons import fluent_pixmap
            self.strategy_icon.setPixmap(fluent_pixmap('fa5s.cog', 20))
        except:
            self.strategy_icon.setPixmap(qta.icon('fa5s.cog', color='#60cdff').pixmap(20, 20))
        self.strategy_icon.setFixedSize(24, 24)
        strategy_layout.addWidget(self.strategy_icon)
        
        strategy_text_layout = QVBoxLayout()
        strategy_text_layout.setSpacing(2)
        
        self.strategy_label = QLabel("Не выбрана")
        self.strategy_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        strategy_text_layout.addWidget(self.strategy_label)
        
        self.strategy_desc = QLabel("Выберите стратегию в разделе «Стратегии»")
        self.strategy_desc.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
            }
        """)
        strategy_text_layout.addWidget(self.strategy_desc)
        
        strategy_layout.addLayout(strategy_text_layout, 1)
        strategy_card.add_layout(strategy_layout)
        
        self.add_widget(strategy_card)
        
        self.add_spacing(16)
        
        # Дополнительные действия
        self.add_section_title("Дополнительно")
        
        extra_card = SettingsCard()
        
        extra_layout = QHBoxLayout()
        extra_layout.setSpacing(8)
        
        self.test_btn = ActionButton("Тест соединения", "fa5s.wifi")
        extra_layout.addWidget(self.test_btn)
        
        self.folder_btn = ActionButton("Открыть папку", "fa5s.folder-open")
        extra_layout.addWidget(self.folder_btn)
        
        extra_layout.addStretch()
        extra_card.add_layout(extra_layout)
        
        self.add_widget(extra_card)
        
        # Индикатор загрузки (бегающая полоска)
        self.add_spacing(16)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(PROGRESS_STYLE)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setVisible(False)
        self.add_widget(self.progress_bar)
        
        # Метка статуса загрузки
        self.loading_label = QLabel("")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
                padding-top: 4px;
            }
        """)
        self.loading_label.setVisible(False)
        self.add_widget(self.loading_label)
        
    def set_loading(self, loading: bool, text: str = ""):
        """Показывает/скрывает индикатор загрузки и блокирует кнопки"""
        self.progress_bar.setVisible(loading)
        self.loading_label.setVisible(loading and bool(text))
        self.loading_label.setText(text)
        
        # Блокируем/разблокируем кнопки
        self.start_btn.setEnabled(not loading)
        self.stop_winws_btn.setEnabled(not loading)
        self.stop_and_exit_btn.setEnabled(not loading)
        
        # Обновляем стиль заблокированных кнопок
        if loading:
            disabled_style = """
                QPushButton {
                    background: rgba(255, 255, 255, 0.03);
                    border: none;
                    border-radius: 6px;
                    color: rgba(255, 255, 255, 0.3);
                    padding: 0 24px;
                    font-size: 14px;
                    font-weight: 600;
                    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                }
            """
            self.start_btn.setStyleSheet(disabled_style)
            self.stop_winws_btn.setStyleSheet(disabled_style)
            self.stop_and_exit_btn.setStyleSheet(disabled_style)
        else:
            # Восстанавливаем стили
            self.start_btn._update_style()
            self.stop_winws_btn._update_style()
            self.stop_and_exit_btn._update_style()
        
    def update_status(self, is_running: bool):
        """Обновляет отображение статуса"""
        if is_running:
            self.status_title.setText("Zapret работает")
            self.status_desc.setText("Обход блокировок активен")
            self.status_dot.set_color('#6ccb5f')
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(True)
            self.stop_and_exit_btn.setVisible(True)
        else:
            self.status_title.setText("Zapret остановлен")
            self.status_desc.setText("Нажмите «Запустить» для активации")
            self.status_dot.set_color('#ff6b6b')
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
            
    def update_strategy(self, name: str):
        """Обновляет отображение текущей стратегии"""
        if name and name != "Автостарт DPI отключен":
            self.strategy_label.setText(name)
            self.strategy_desc.setText("Активная стратегия обхода")
        else:
            self.strategy_label.setText("Не выбрана")
            self.strategy_desc.setText("Выберите стратегию в разделе «Стратегии»")

