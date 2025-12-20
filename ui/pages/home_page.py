# ui/pages/home_page.py
"""Главная страница - обзор состояния системы"""

from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QSizePolicy, QProgressBar
)
from PyQt6.QtGui import QFont
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, StatusIndicator, ActionButton
from log import log


class AutostartCheckWorker(QThread):
    """Быстрая фоновая проверка статуса автозапуска"""
    finished = pyqtSignal(bool)  # True если автозапуск включён
    
    def run(self):
        try:
            result = self._check_autostart()
            self.finished.emit(result)
        except Exception as e:
            log(f"AutostartCheckWorker error: {e}", "WARNING")
            self.finished.emit(False)
    
    def _check_autostart(self) -> bool:
        """Быстрая проверка наличия автозапуска через реестр"""
        try:
            from autostart.registry_check import AutostartRegistryChecker
            return AutostartRegistryChecker.is_autostart_enabled()
        except Exception:
            return False


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


class StatusCard(QFrame):
    """Большая карточка статуса на главной странице"""

    clicked = pyqtSignal()  # Сигнал клика по карточке

    def __init__(self, icon_name: str, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # Курсор "рука" при наведении
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        
        # Верхняя строка: иконка + заголовок
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)
        
        # Иконка (объёмная с градиентом)
        self.icon_label = QLabel()
        try:
            from ui.fluent_icons import fluent_pixmap
            self.icon_label.setPixmap(fluent_pixmap(icon_name, 28))
        except:
            self.icon_label.setPixmap(qta.icon(icon_name, color='#60cdff').pixmap(28, 28))
        self.icon_label.setFixedSize(32, 32)
        top_layout.addWidget(self.icon_label)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
                font-weight: 500;
            }
        """)
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # Значение (большой текст)
        self.value_label = QLabel("—")
        self.value_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.value_label)
        
        # Дополнительная информация
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
            }
        """)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        layout.addStretch()
        
        # Стиль карточки (Acrylic / Glass эффект)
        self.setStyleSheet("""
            QFrame#statusCard {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            }
            QFrame#statusCard:hover {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
    def set_value(self, value: str, info: str = ""):
        """Устанавливает текстовое значение"""
        # Скрываем иконки, показываем текст
        if hasattr(self, 'icons_container'):
            self.icons_container.hide()
        self.value_label.show()
        self.value_label.setText(value)
        self.info_label.setText(info)
    
    def set_value_with_icons(self, categories_data: list, info: str = ""):
        """
        Устанавливает значение с иконками категорий.
        
        Args:
            categories_data: список кортежей (icon_name, icon_color, is_active)
            info: текст подписи
        """
        # Создаём контейнер для иконок если его нет
        if not hasattr(self, 'icons_container'):
            self.icons_container = QWidget()
            self.icons_layout = QHBoxLayout(self.icons_container)
            self.icons_layout.setContentsMargins(0, 0, 0, 0)
            self.icons_layout.setSpacing(4)
            # Вставляем после value_label
            self.layout().insertWidget(2, self.icons_container)
        
        # Очищаем старые иконки
        while self.icons_layout.count():
            item = self.icons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Скрываем текстовый label, показываем иконки
        self.value_label.hide()
        self.icons_container.show()
        
        # Добавляем иконки категорий
        active_count = 0
        for icon_name, icon_color, is_active in categories_data:
            if is_active:
                active_count += 1
                icon_label = QLabel()
                try:
                    pixmap = qta.icon(icon_name, color=icon_color).pixmap(20, 20)
                    icon_label.setPixmap(pixmap)
                except:
                    pixmap = qta.icon('fa5s.globe', color='#60cdff').pixmap(20, 20)
                    icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(22, 22)
                icon_label.setToolTip(icon_name.split('.')[-1].replace('-', ' ').title())
                self.icons_layout.addWidget(icon_label)
        
        # Если слишком много - показываем +N
        if active_count > 10:
            # Оставляем первые 9 + счётчик
            while self.icons_layout.count() > 9:
                item = self.icons_layout.takeAt(9)
                if item.widget():
                    item.widget().deleteLater()
            
            extra_label = QLabel(f"+{active_count - 9}")
            extra_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.6);
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 6px;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
            """)
            self.icons_layout.addWidget(extra_label)
        
        self.icons_layout.addStretch()
        self.info_label.setText(info)
        
    def set_status_color(self, status: str):
        """Меняет цвет иконки по статусу"""
        colors = {
            'running': '#6ccb5f',
            'stopped': '#ff6b6b',
            'warning': '#ffc107',
            'neutral': '#60cdff',
        }
        color = colors.get(status, colors['neutral'])
        # Для простоты меняем только цвет value_label
        self.value_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 18px;
                font-weight: 600;
            }}
        """)

    def mousePressEvent(self, event):
        """Обработка клика по карточке"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HomePage(BasePage):
    """Главная страница - обзор состояния"""

    # Сигналы для навигации на другие страницы
    navigate_to_control = pyqtSignal()
    navigate_to_strategies = pyqtSignal()
    navigate_to_autostart = pyqtSignal()
    navigate_to_premium = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Главная", "Обзор состояния Zapret", parent)

        self._autostart_worker = None
        self._build_ui()
        self._connect_card_signals()
    
    def showEvent(self, event):
        """При показе страницы обновляем статус автозапуска"""
        super().showEvent(event)
        # Запускаем проверку автозапуска в фоне с небольшой задержкой
        QTimer.singleShot(100, self._check_autostart_status)
    
    def _check_autostart_status(self):
        """Запускает фоновую проверку статуса автозапуска"""
        if self._autostart_worker is not None and self._autostart_worker.isRunning():
            return
        
        self._autostart_worker = AutostartCheckWorker()
        self._autostart_worker.finished.connect(self._on_autostart_checked)
        self._autostart_worker.start()
    
    def _on_autostart_checked(self, enabled: bool):
        """Обработчик результата проверки автозапуска"""
        self.update_autostart_status(enabled)
        
    def _build_ui(self):
        # Сетка карточек статуса
        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Карточка статуса DPI
        self.dpi_status_card = StatusCard("fa5s.shield-alt", "Статус Zapret")
        self.dpi_status_card.set_value("Проверка...", "Определение состояния")
        cards_layout.addWidget(self.dpi_status_card, 0, 0)
        
        # Карточка стратегии
        self.strategy_card = StatusCard("fa5s.cog", "Текущая стратегия")
        self.strategy_card.set_value("Не выбрана", "Выберите стратегию обхода")
        cards_layout.addWidget(self.strategy_card, 0, 1)
        
        # Карточка автозапуска
        self.autostart_card = StatusCard("fa5s.rocket", "Автозапуск")
        self.autostart_card.set_value("Отключён", "Запускайте вручную")
        cards_layout.addWidget(self.autostart_card, 1, 0)
        
        # Карточка подписки
        self.subscription_card = StatusCard("fa5s.star", "Подписка")
        self.subscription_card.set_value("Free", "Базовые функции")
        cards_layout.addWidget(self.subscription_card, 1, 1)
        
        cards_widget = QWidget(self.content)  # ✅ Явный родитель
        cards_widget.setLayout(cards_layout)
        self.add_widget(cards_widget)
        
        self.add_spacing(8)
        
        # Быстрые действия
        self.add_section_title("Быстрые действия")
        
        actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        # Кнопка запуска
        self.start_btn = ActionButton("Запустить", "fa5s.play", accent=True)
        actions_layout.addWidget(self.start_btn)
        
        # Кнопка остановки
        self.stop_btn = ActionButton("Остановить", "fa5s.stop")
        self.stop_btn.setVisible(False)
        actions_layout.addWidget(self.stop_btn)
        
        # Кнопка теста
        self.test_btn = ActionButton("Тест соединения", "fa5s.wifi")
        actions_layout.addWidget(self.test_btn)
        
        # Кнопка папки
        self.folder_btn = ActionButton("Открыть папку", "fa5s.folder-open")
        actions_layout.addWidget(self.folder_btn)
        
        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        self.add_widget(actions_card)
        
        self.add_spacing(8)
        
        # Статусная строка
        self.add_section_title("Статус")
        
        status_card = SettingsCard()
        self.status_indicator = StatusIndicator()
        self.status_indicator.set_status("Готов к работе", "neutral")
        status_card.add_widget(self.status_indicator)
        self.add_widget(status_card)
        
        # Индикатор загрузки (бегающая полоска)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(PROGRESS_STYLE)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setVisible(False)
        self.add_widget(self.progress_bar)

        self.add_spacing(12)

        # Блок Premium
        self._build_premium_block()

    def _connect_card_signals(self):
        """Подключает клики по карточкам к сигналам навигации"""
        self.dpi_status_card.clicked.connect(self.navigate_to_control.emit)
        self.strategy_card.clicked.connect(self.navigate_to_strategies.emit)
        self.autostart_card.clicked.connect(self.navigate_to_autostart.emit)
        self.subscription_card.clicked.connect(self.navigate_to_premium.emit)
        
    def update_dpi_status(self, is_running: bool, strategy_name: str = None):
        """Обновляет отображение статуса DPI"""
        if is_running:
            self.dpi_status_card.set_value("Запущен", "Обход блокировок активен")
            self.dpi_status_card.set_status_color('running')
            self.start_btn.setVisible(False)
            self.stop_btn.setVisible(True)
        else:
            self.dpi_status_card.set_value("Остановлен", "Нажмите Запустить")
            self.dpi_status_card.set_status_color('stopped')
            self.start_btn.setVisible(True)
            self.stop_btn.setVisible(False)
            
        if strategy_name:
            # Пробуем показать иконки категорий для Direct режима
            self._update_strategy_card_with_icons(strategy_name)
    
    def _update_strategy_card_with_icons(self, strategy_name: str):
        """Обновляет карточку стратегии с иконками категорий"""
        try:
            from strategy_menu import get_strategy_launch_method, get_direct_strategy_selections
            from strategy_menu.strategies_registry import registry
            
            # Для Direct режимов показываем иконки
            if get_strategy_launch_method() in ("direct", "direct_orchestra"):
                selections = get_direct_strategy_selections()
                
                # Собираем данные о категориях: (icon_name, icon_color, is_active)
                categories_data = []
                active_count = 0
                
                for cat_key in registry.get_all_category_keys():
                    cat_info = registry.get_category_info(cat_key)
                    if cat_info:
                        strat_id = selections.get(cat_key, "none")
                        is_active = strat_id and strat_id != "none"
                        
                        if is_active:
                            active_count += 1
                            categories_data.append((
                                cat_info.icon_name or 'fa5s.globe',
                                cat_info.icon_color or '#60cdff',
                                True
                            ))
                
                if active_count > 0:
                    self.strategy_card.set_value_with_icons(
                        categories_data, 
                        f"Активно {active_count} категорий"
                    )
                    return
            
            # Fallback - текстовое отображение для BAT режима
            display_name = self._truncate_strategy_name(strategy_name)
            self.strategy_card.set_value(display_name, "Активная стратегия")
            
        except Exception as e:
            from log import log
            log(f"Ошибка обновления карточки стратегии: {e}", "DEBUG")
            # Fallback на текст
            display_name = self._truncate_strategy_name(strategy_name)
            self.strategy_card.set_value(display_name, "Активная стратегия")
    
    def _truncate_strategy_name(self, name: str, max_items: int = 2) -> str:
        """Обрезает длинное название стратегии для карточки"""
        if not name or name in ("Не выбрана", "Прямой запуск"):
            return name
        
        # Определяем разделитель - поддерживаем и " • " (Direct режим) и ", " (старый формат)
        separator = " • " if " • " in name else ", "
        
        # Если это список категорий
        if separator in name:
            parts = name.split(separator)
            # Проверяем есть ли "+N ещё" в конце
            extra = ""
            if parts and (parts[-1].startswith("+") or "ещё" in parts[-1]):
                # Извлекаем число из "+N ещё"
                last_part = parts[-1]
                if last_part.startswith("+"):
                    # Формат "+2 ещё"
                    extra_num = int(''.join(filter(str.isdigit, last_part))) or 0
                    parts = parts[:-1]
                    extra_num += len(parts) - max_items
                    if extra_num > 0:
                        extra = f"+{extra_num}"
            elif len(parts) > max_items:
                extra = f"+{len(parts) - max_items}"
                
            if len(parts) > max_items:
                return separator.join(parts[:max_items]) + (f" {extra}" if extra else "")
            elif extra:
                return separator.join(parts) + f" {extra}"
                
        return name
            
    def update_autostart_status(self, enabled: bool):
        """Обновляет отображение статуса автозапуска"""
        if enabled:
            self.autostart_card.set_value("Включён", "Запускается с Windows")
            self.autostart_card.set_status_color('running')
        else:
            self.autostart_card.set_value("Отключён", "Запускайте вручную")
            self.autostart_card.set_status_color('neutral')
            
    def update_subscription_status(self, is_premium: bool, days: int = None):
        """Обновляет отображение статуса подписки"""
        if is_premium:
            if days:
                self.subscription_card.set_value("Premium", f"Осталось {days} дней")
            else:
                self.subscription_card.set_value("Premium", "Все функции доступны")
            self.subscription_card.set_status_color('running')
        else:
            self.subscription_card.set_value("Free", "Базовые функции")
            self.subscription_card.set_status_color('neutral')
            
    def set_status(self, text: str, status: str = "neutral"):
        """Устанавливает текст статусной строки"""
        self.status_indicator.set_status(text, status)
    
    def set_loading(self, loading: bool, text: str = ""):
        """Показывает/скрывает индикатор загрузки и блокирует кнопки"""
        self.progress_bar.setVisible(loading)
        
        # Блокируем/разблокируем кнопки
        self.start_btn.setEnabled(not loading)
        self.stop_btn.setEnabled(not loading)
        
        # Обновляем статус если есть текст
        if loading and text:
            self.status_indicator.set_status(text, "neutral")
        
    def _build_premium_block(self):
        """Создает блок Premium на главной странице"""
        premium_card = SettingsCard()
        
        premium_layout = QHBoxLayout()
        premium_layout.setSpacing(16)
        
        # Иконка звезды
        star_label = QLabel()
        star_label.setPixmap(qta.icon('fa5s.star', color='#ffc107').pixmap(32, 32))
        star_label.setFixedSize(40, 40)
        premium_layout.addWidget(star_label)
        
        # Текст
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title = QLabel("Zapret Premium")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        text_layout.addWidget(title)
        
        desc = QLabel("Дополнительные темы, приоритетная поддержка и VPN-сервис")
        desc.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
        """)
        desc.setWordWrap(True)
        text_layout.addWidget(desc)
        
        premium_layout.addLayout(text_layout, 1)
        
        # Кнопка Premium
        self.premium_link_btn = ActionButton("Подробнее", "fa5s.arrow-right")
        self.premium_link_btn.setFixedHeight(36)
        premium_layout.addWidget(self.premium_link_btn)
        
        premium_card.add_layout(premium_layout)
        self.add_widget(premium_card)

