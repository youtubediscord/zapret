# ui/pages/network_page.py
"""Страница сетевых настроек - DNS, hosts, proxy"""

from __future__ import annotations
import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QRadioButton, QButtonGroup, QLineEdit, QCheckBox,
    QMessageBox, QProgressBar
)
import qtawesome as qta

from .base_page import BasePage
from .dpi_settings_page import Win11ToggleRow
from ui.sidebar import SettingsCard, ActionButton
from log import log
from dns import DNS_PROVIDERS

if TYPE_CHECKING:
    from main import LupiDPIApp

# Стиль для красивого индикатора выбора
RADIO_STYLE = """
    QRadioButton {
        spacing: 0px;
    }
    QRadioButton::indicator {
        width: 16px;
        height: 16px;
        border-radius: 8px;
    }
    QRadioButton::indicator:unchecked {
        background-color: rgba(255, 255, 255, 0.08);
        border: 2px solid rgba(255, 255, 255, 0.25);
    }
    QRadioButton::indicator:unchecked:hover {
        border-color: rgba(255, 255, 255, 0.4);
    }
    QRadioButton::indicator:checked {
        background-color: #4fc3f7;
        border: 2px solid #4fc3f7;
    }
    QRadioButton::indicator:checked::after {
        background-color: white;
    }
"""


class DNSProviderCard(SettingsCard):
    """Компактная карточка DNS провайдера"""
    
    selected = pyqtSignal(str, dict)  # name, data
    
    STYLE_DEFAULT = """
        #dnsCard {
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
        }
    """
    STYLE_SELECTED = """
        #dnsCard {
            background-color: rgba(79, 195, 247, 0.12);
            border: 1px solid rgba(79, 195, 247, 0.4);
            border-radius: 10px;
        }
    """
    INDICATOR_OFF = """
        background-color: rgba(255, 255, 255, 0.08);
        border: 2px solid rgba(255, 255, 255, 0.25);
        border-radius: 8px;
    """
    INDICATOR_ON = """
        background-color: #4fc3f7;
        border: 2px solid #4fc3f7;
        border-radius: 8px;
    """
    
    def __init__(self, name: str, data: dict, is_current: bool = False, parent=None):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.is_current = is_current
        self._is_selected = False
        self.setObjectName("dnsCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self.setStyleSheet(self.STYLE_DEFAULT)
        
    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)
        
        # Индикатор выбора
        self.indicator = QFrame()
        self.indicator.setFixedSize(16, 16)
        self.indicator.setStyleSheet(self.INDICATOR_OFF)
        layout.addWidget(self.indicator)
        
        # Иконка провайдера
        icon_color = self.data.get('color', '#4fc3f7')
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(
            self.data.get('icon', 'fa5s.server'), 
            color=icon_color
        ).pixmap(18, 18))
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)
        
        # Название
        name_label = QLabel(self.name)
        name_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        layout.addWidget(name_label)
        
        # Описание
        desc_label = QLabel(f"· {self.data.get('desc', '')}")
        desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # IP адрес
        ip_label = QLabel(self.data['ipv4'][0])
        ip_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px; font-family: monospace;")
        layout.addWidget(ip_label)
        
        self.add_layout(layout)
    
    def set_selected(self, selected: bool):
        """Устанавливает визуальное состояние выбора"""
        self._is_selected = selected
        if selected:
            self.indicator.setStyleSheet(self.INDICATOR_ON)
            self.setStyleSheet(self.STYLE_SELECTED)
        else:
            self.indicator.setStyleSheet(self.INDICATOR_OFF)
            self.setStyleSheet(self.STYLE_DEFAULT)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.name, self.data)
        super().mousePressEvent(event)


class AdapterCard(SettingsCard):
    """Компактная карточка сетевого адаптера"""
    
    def __init__(self, name: str, dns_info: dict, parent=None):
        super().__init__(parent)
        self.adapter_name = name
        self.dns_info = dns_info
        self.dns_label = None  # Сохраняем ссылку для обновления
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)
        
        # Кастомный чекбокс через иконку
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.hide()  # Скрываем стандартный чекбокс
        
        # Иконка-чекбокс
        self.check_icon = QLabel()
        self.check_icon.setFixedSize(20, 20)
        self.check_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_check_icon()
        self.check_icon.mousePressEvent = lambda e: self._toggle_checkbox()
        layout.addWidget(self.check_icon)
        
        # Связываем изменение чекбокса с обновлением иконки
        self.checkbox.stateChanged.connect(self._update_check_icon)
        
        # Иконка
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.network-wired', color='#4fc3f7').pixmap(16, 16))
        layout.addWidget(icon_label)
        
        # Название
        name_label = QLabel(self.adapter_name)
        name_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # Текущий DNS (первичный + вторичный)
        current_dns = self._normalize_dns_list(self.dns_info.get("ipv4", []))
        if current_dns:
            primary = current_dns[0]
            secondary = current_dns[1] if len(current_dns) > 1 else None
            if secondary:
                dns_text = f"{primary}, {secondary}"
            else:
                dns_text = primary
        else:
            dns_text = "DHCP"
        
        self.dns_label = QLabel(dns_text)
        self.dns_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-family: monospace;")
        layout.addWidget(self.dns_label)
        
        self.add_layout(layout)
    
    @staticmethod
    def _normalize_dns_list(value) -> list:
        """Нормализует DNS в список адресов"""
        if isinstance(value, str):
            return [x.strip() for x in value.replace(',', ' ').split() if x.strip()]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    result.extend([x.strip() for x in item.replace(',', ' ').split() if x.strip()])
                else:
                    result.append(str(item))
            return result
        return []
    
    def update_dns_display(self, dns_list):
        """Обновляет отображение текущего DNS"""
        if self.dns_label:
            if isinstance(dns_list, str):
                dns_list = self._normalize_dns_list(dns_list)
            elif isinstance(dns_list, list):
                dns_list = self._normalize_dns_list(dns_list)
            
            if dns_list:
                primary = dns_list[0]
                secondary = dns_list[1] if len(dns_list) > 1 else None
                if secondary:
                    dns_text = f"{primary}, {secondary}"
                else:
                    dns_text = primary
            else:
                dns_text = "DHCP"
            
            self.dns_label.setText(dns_text)
    
    def _toggle_checkbox(self):
        """Переключает состояние чекбокса"""
        self.checkbox.setChecked(not self.checkbox.isChecked())
    
    def _update_check_icon(self, state=None):
        """Обновляет иконку чекбокса"""
        if self.checkbox.isChecked():
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-marked', color='#4fc3f7').pixmap(18, 18))
        else:
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-blank-outline', color='rgba(255, 255, 255, 0.3)').pixmap(18, 18))


class NetworkPage(BasePage):
    """Страница сетевых настроек с интегрированным DNS"""

    adapters_loaded = pyqtSignal(list)
    dns_info_loaded = pyqtSignal(dict)
    test_completed = pyqtSignal(list)  # Результаты теста соединения
    
    def __init__(self, parent=None):
        super().__init__("Сеть", "Настройки DNS и доступа к сервисам", parent)
        
        self._dns_manager = None
        self._adapters = []
        self._dns_info = {}
        self._is_loading = True
        self._selected_provider = None
        self._ui_built = False  # Флаг чтобы UI строился только один раз
        self._force_dns_active = False
        
        self.dns_cards = {}
        self.adapter_cards = []
        
        self._build_ui()
        self._start_loading()
        
    def _build_ui(self):
        """Строит интерфейс страницы"""
        
        # ═══════════════════════════════════════════════════════════════
        # ПРИНУДИТЕЛЬНЫЙ DNS
        # ═══════════════════════════════════════════════════════════════
        self._build_force_dns_card()
        
        self.add_spacing(12)
        
        # ═══════════════════════════════════════════════════════════════
        # DNS СЕРВЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title("DNS Серверы")
        
        # Индикатор загрузки
        self.loading_card = SettingsCard()
        loading_layout = QVBoxLayout()
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.loading_label = QLabel("⏳ Загрузка...")
        self.loading_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(2)
        self.loading_bar.setMaximumWidth(150)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet("""
            QProgressBar { background-color: rgba(255, 255, 255, 0.1); border: none; border-radius: 1px; }
            QProgressBar::chunk { background-color: #4fc3f7; border-radius: 1px; }
        """)
        loading_layout.addWidget(self.loading_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.loading_card.add_layout(loading_layout)
        self.add_widget(self.loading_card)
        
        # Контейнер для DNS карточек
        self.dns_cards_container = QWidget()
        self.dns_cards_layout = QVBoxLayout(self.dns_cards_container)
        self.dns_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.dns_cards_layout.setSpacing(4)
        self.dns_cards_container.hide()
        self.add_widget(self.dns_cards_container)
        
        self.add_spacing(6)
        
        # Пользовательский DNS
        self.custom_card = SettingsCard()
        self.custom_card.setObjectName("dnsCard")
        self.custom_card.setStyleSheet(DNSProviderCard.STYLE_DEFAULT)
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(10, 6, 12, 6)
        custom_layout.setSpacing(8)
        
        # Индикатор
        self.custom_indicator = QFrame()
        self.custom_indicator.setFixedSize(16, 16)
        self.custom_indicator.setStyleSheet(DNSProviderCard.INDICATOR_OFF)
        custom_layout.addWidget(self.custom_indicator)
        
        custom_label = QLabel("Свой:")
        custom_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        custom_layout.addWidget(custom_label)
        
        self.custom_primary = QLineEdit()
        self.custom_primary.setPlaceholderText("8.8.8.8")
        self.custom_primary.setFixedWidth(110)
        self.custom_primary.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px;
                padding: 4px 8px;
                color: #ffffff;
                font-size: 11px;
                font-family: monospace;
            }
            QLineEdit:focus { border-color: #4fc3f7; }
        """)
        self.custom_primary.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_primary)
        
        self.custom_secondary = QLineEdit()
        self.custom_secondary.setPlaceholderText("8.8.4.4")
        self.custom_secondary.setFixedWidth(110)
        self.custom_secondary.setStyleSheet(self.custom_primary.styleSheet())
        self.custom_secondary.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_secondary)
        
        self.custom_apply_btn = ActionButton("OK", "fa5s.check")
        self.custom_apply_btn.setFixedSize(70, 26)
        self.custom_apply_btn.clicked.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_apply_btn)
        
        custom_layout.addStretch()
        
        self.custom_card.add_layout(custom_layout)
        self.custom_card.hide()
        self.add_widget(self.custom_card)
        
        self.add_spacing(12)
        
        # ═══════════════════════════════════════════════════════════════
        # СЕТЕВЫЕ АДАПТЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title("Сетевые адаптеры")
        
        # Контейнер для адаптеров
        self.adapters_container = QWidget()
        self.adapters_layout = QVBoxLayout(self.adapters_container)
        self.adapters_layout.setContentsMargins(0, 0, 0, 0)
        self.adapters_layout.setSpacing(4)
        self.adapters_container.hide()
        self.add_widget(self.adapters_container)
        
        self.add_spacing(12)
        
        # ═══════════════════════════════════════════════════════════════
        # ДИАГНОСТИКА
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title("Утилиты")
        
        tools_card = SettingsCard()
        tools_layout = QHBoxLayout()
        tools_layout.setContentsMargins(10, 8, 12, 8)
        tools_layout.setSpacing(8)
        
        self.test_btn = ActionButton("Тест соединения", "fa5s.wifi")
        self.test_btn.setFixedHeight(28)
        self.test_btn.clicked.connect(self._test_connection)
        tools_layout.addWidget(self.test_btn)
        
        self.dns_flush_btn = ActionButton("Сбросить DNS кэш", "fa5s.sync")
        self.dns_flush_btn.setFixedHeight(28)
        self.dns_flush_btn.clicked.connect(self._flush_dns_cache)
        tools_layout.addWidget(self.dns_flush_btn)
        
        tools_layout.addStretch()
        
        tools_card.add_layout(tools_layout)
        self.add_widget(tools_card)
        
        # Подключаем сигналы
        self.adapters_loaded.connect(self._on_adapters_loaded)
        self.dns_info_loaded.connect(self._on_dns_info_loaded)
    
    def _start_loading(self):
        """Запускает асинхронную загрузку данных"""
        thread = threading.Thread(target=self._load_data, daemon=True)
        thread.start()
    
    def _load_data(self):
        """Загружает данные в фоне"""
        try:
            from dns.dns_core import DNSManager, _normalize_alias, refresh_exclusion_cache
            
            refresh_exclusion_cache()
            self._dns_manager = DNSManager()
            
            all_adapters = self._dns_manager.get_network_adapters_fast(
                include_ignored=True,
                include_disconnected=True
            )
            
            filtered = [
                (name, desc) for name, desc in all_adapters
                if not self._dns_manager.should_ignore_adapter(name, desc)
            ]
            
            self._adapters = filtered
            self.adapters_loaded.emit(filtered)
            
            adapter_names = [name for name, _ in all_adapters]
            dns_info = self._dns_manager.get_all_dns_info_fast(adapter_names)
            
            self._dns_info = dns_info
            self.dns_info_loaded.emit(dns_info)
            
        except Exception as e:
            log(f"Ошибка загрузки DNS данных: {e}", "ERROR")
    
    def _on_adapters_loaded(self, adapters):
        self._adapters = adapters
        if self._dns_info and not self._ui_built:
            self._build_dynamic_ui()
    
    def _on_dns_info_loaded(self, dns_info):
        self._dns_info = dns_info
        if self._adapters and not self._ui_built:
            self._build_dynamic_ui()
    
    def _build_dynamic_ui(self):
        """Строит UI после загрузки данных"""
        if self._ui_built:
            return
        self._ui_built = True
        
        from dns.dns_core import _normalize_alias
        
        self._is_loading = False
        self.loading_card.hide()
        self.dns_cards_container.show()
        self.custom_card.show()
        self.adapters_container.show()
        
        # Получаем текущий DNS
        current_dns = []
        if self._adapters:
            first_adapter = self._adapters[0][0]
            clean = _normalize_alias(first_adapter)
            dns_data = self._dns_info.get(clean, {"ipv4": []})
            current_dns = dns_data.get("ipv4", [])
        
        # Добавляем "Автоматически (DHCP)"
        auto_card = SettingsCard()
        auto_card.setObjectName("dnsCard")
        auto_card.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_card.setStyleSheet(DNSProviderCard.STYLE_DEFAULT)
        auto_layout = QHBoxLayout()
        auto_layout.setContentsMargins(10, 6, 12, 6)
        auto_layout.setSpacing(10)
        
        self.auto_indicator = QFrame()
        self.auto_indicator.setFixedSize(16, 16)
        self.auto_indicator.setStyleSheet(DNSProviderCard.INDICATOR_OFF)
        auto_layout.addWidget(self.auto_indicator)
        
        auto_icon = QLabel()
        auto_icon.setPixmap(qta.icon('fa5s.sync', color='#78909c').pixmap(16, 16))
        auto_layout.addWidget(auto_icon)
        
        auto_label = QLabel("Автоматически (DHCP)")
        auto_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        auto_layout.addWidget(auto_label)
        
        auto_layout.addStretch()
        
        auto_card.add_layout(auto_layout)
        auto_card.mousePressEvent = lambda e: self._select_auto_dns()
        self.dns_cards_layout.addWidget(auto_card)
        self.auto_card = auto_card
        
        # Добавляем провайдеров
        for category, providers in DNS_PROVIDERS.items():
            cat_label = QLabel(category)
            cat_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.35);
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                padding: 8px 0 4px 4px;
            """)
            self.dns_cards_layout.addWidget(cat_label)
            
            for name, data in providers.items():
                is_current = self._is_current_dns(data['ipv4'], current_dns)
                card = DNSProviderCard(name, data, is_current)
                card.selected.connect(self._on_dns_selected)
                self.dns_cards[name] = card
                
                if is_current:
                    card.set_selected(True)
                    self._selected_provider = name
                
                self.dns_cards_layout.addWidget(card)
        
        # Адаптеры
        for name, desc in self._adapters:
            clean = _normalize_alias(name)
            dns_data = self._dns_info.get(clean, {"ipv4": []})
            
            card = AdapterCard(name, dns_data)
            self.adapter_cards.append(card)
            self.adapters_layout.addWidget(card)
    
    def _is_current_dns(self, provider_ips: list, current_ips: list) -> bool:
        return (len(provider_ips) > 0 and 
                len(current_ips) > 0 and 
                provider_ips[0] == current_ips[0])
    
    def _clear_selection(self):
        """Сбрасывает все выделения"""
        for card in self.dns_cards.values():
            card.set_selected(False)
        
        if hasattr(self, 'auto_indicator'):
            self.auto_indicator.setStyleSheet(DNSProviderCard.INDICATOR_OFF)
            if hasattr(self, 'auto_card'):
                self.auto_card.setStyleSheet(DNSProviderCard.STYLE_DEFAULT)
        
        self.custom_indicator.setStyleSheet(DNSProviderCard.INDICATOR_OFF)
        self.custom_card.setStyleSheet(DNSProviderCard.STYLE_DEFAULT)
    
    def _on_dns_selected(self, name: str, data: dict):
        """Обработчик выбора DNS - сразу применяем"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        self._clear_selection()
        self.dns_cards[name].set_selected(True)
        self._selected_provider = name
        
        # Применяем
        self._apply_provider_dns_quick(name, data)
    
    def _select_auto_dns(self):
        """Выбор автоматического DNS"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        self._clear_selection()
        self.auto_indicator.setStyleSheet(DNSProviderCard.INDICATOR_ON)
        self.auto_card.setStyleSheet(DNSProviderCard.STYLE_SELECTED)
        self._selected_provider = None
        
        # Применяем
        self._apply_auto_dns_quick()
    
    def _get_selected_adapters(self) -> list:
        """Возвращает выбранные адаптеры"""
        return [card.adapter_name for card in self.adapter_cards if card.checkbox.isChecked()]
    
    def _apply_auto_dns_quick(self):
        """Быстрое применение автоматического DNS (IPv4 + IPv6)"""
        if not self._dns_manager:
            return
        
        adapters = self._get_selected_adapters()
        if not adapters:
            return
        
        success = 0
        for adapter in adapters:
            # Сбрасываем и IPv4, и IPv6
            ok_v4, _ = self._dns_manager.set_auto_dns(adapter, "IPv4")
            ok_v6, _ = self._dns_manager.set_auto_dns(adapter, "IPv6")
            if ok_v4 and ok_v6:
                success += 1
        
        self._dns_manager.flush_dns_cache()
        
        if success == len(adapters):
            log(f"DNS: Автоматический (IPv4+IPv6) применён к {success} адаптерам", "INFO")
        
        # Обновляем отображение DNS у адаптеров
        self._refresh_adapters_dns()
    
    def _apply_provider_dns_quick(self, name: str, data: dict):
        """Быстрое применение DNS провайдера"""
        if not self._dns_manager:
            return
        
        adapters = self._get_selected_adapters()
        if not adapters:
            return
        
        ipv4 = data['ipv4']
        success = 0
        
        for adapter in adapters:
            ok, _ = self._dns_manager.set_custom_dns(
                adapter, 
                ipv4[0], 
                ipv4[1] if len(ipv4) > 1 else None,
                "IPv4"
            )
            if ok:
                success += 1
        
        self._dns_manager.flush_dns_cache()
        
        if success == len(adapters):
            log(f"DNS: {name} применён к {success} адаптерам", "INFO")
        
        # Обновляем отображение DNS у адаптеров
        self._refresh_adapters_dns()
    
    def _apply_custom_dns_quick(self):
        """Быстрое применение пользовательского DNS"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        if not self._dns_manager:
            return
        
        primary = self.custom_primary.text().strip()
        if not primary:
            return
        
        secondary = self.custom_secondary.text().strip() or None
        
        self._clear_selection()
        self.custom_indicator.setStyleSheet(DNSProviderCard.INDICATOR_ON)
        self.custom_card.setStyleSheet(DNSProviderCard.STYLE_SELECTED)
        
        adapters = self._get_selected_adapters()
        if not adapters:
            return
        
        success = 0
        for adapter in adapters:
            ok, _ = self._dns_manager.set_custom_dns(adapter, primary, secondary, "IPv4")
            if ok:
                success += 1
        
        self._dns_manager.flush_dns_cache()
        
        if success == len(adapters):
            log(f"DNS: {primary} применён к {success} адаптерам", "INFO")
        
        # Обновляем отображение DNS у адаптеров
        self._refresh_adapters_dns()
    
    def _refresh_adapters_dns(self):
        """Обновляет отображение DNS у всех адаптеров"""
        try:
            if not self._dns_manager:
                log("DNS Manager не инициализирован", "DEBUG")
                return
            
            if not self.adapter_cards:
                log("Нет карточек адаптеров для обновления", "DEBUG")
                return
            
            from dns.dns_core import _normalize_alias
            
            # Собираем имена адаптеров
            adapter_names = [card.adapter_name for card in self.adapter_cards]
            
            # Получаем свежую информацию о DNS
            dns_info = self._dns_manager.get_all_dns_info_fast(adapter_names)
            
            # Обновляем каждый адаптер
            for card in self.adapter_cards:
                clean_name = _normalize_alias(card.adapter_name)
                adapter_dns = dns_info.get(clean_name, {}).get("ipv4", [])
                card.update_dns_display(adapter_dns)
                
            log("DNS информация адаптеров обновлена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка обновления DNS адаптеров: {e}", "WARNING")
            import traceback
            log(traceback.format_exc(), "DEBUG")
    
    def _build_force_dns_card(self):
        """Строит виджет принудительного DNS в стиле DPI страницы"""
        from dns import DNSForceManager, ensure_default_force_dns
        
        ensure_default_force_dns()
        manager = DNSForceManager()
        self._force_dns_active = manager.is_force_dns_enabled()
        
        # Секция DNS
        self.add_section_title("DNS")
        
        # Карточка
        self.force_dns_card = SettingsCard("Принудительно прописывает DNS.SB + OpenDNS для обхода блокировок")
        dns_layout = QVBoxLayout()
        dns_layout.setSpacing(8)
        
        # Toggle row в стиле Win11
        self.force_dns_toggle = Win11ToggleRow(
            "fa5s.shield-alt",
            "Принудительный DNS",
            "Устанавливает DNS.SB + OpenDNS на активные адаптеры",
            "#60cdff"
        )
        self.force_dns_toggle.setChecked(self._force_dns_active)
        self.force_dns_toggle.toggled.connect(self._on_force_dns_toggled)
        dns_layout.addWidget(self.force_dns_toggle)
        
        # Статус
        self.force_dns_status_label = QLabel("")
        self.force_dns_status_label.setStyleSheet("color: rgba(255, 255, 255, 0.55); font-size: 11px;")
        dns_layout.addWidget(self.force_dns_status_label)
        
        self.force_dns_card.add_layout(dns_layout)
        self.add_widget(self.force_dns_card)
        
        # Обновляем статус
        self._update_force_dns_status(self._force_dns_active)
        self._update_dns_selection_state()
    
    def _on_force_dns_toggled(self, enabled: bool):
        """Обработчик переключения принудительного DNS"""
        try:
            from dns import DNSForceManager
            manager = DNSForceManager()
            
            current_state = manager.is_force_dns_enabled()
            if enabled == current_state:
                self._update_force_dns_status(enabled)
                self._update_dns_selection_state()
                return
            
            if enabled:
                success, ok_count, total, message = manager.enable_force_dns(include_disconnected=False)
                log(message, "DNS")
                
                if success:
                    self._force_dns_active = True
                    self._update_force_dns_status(True, f"{ok_count}/{total} адаптеров")
                else:
                    self._set_force_dns_toggle(False)
                    self._update_force_dns_status(False, "Не удалось включить")
            else:
                success, message = manager.disable_force_dns()
                log(message, "DNS")

                if success:
                    self._force_dns_active = False
                    self._update_force_dns_status(False, "DNS сброшен на авто")
                else:
                    self._set_force_dns_toggle(True)
                    self._update_force_dns_status(True, "Не удалось отключить")
            
            self._update_dns_selection_state()
            self._refresh_adapters_dns()
                    
        except Exception as e:
            log(f"Ошибка переключения Force DNS: {e}", "ERROR")
            self._set_force_dns_toggle(not enabled)
            self._update_force_dns_status(not enabled, "Ошибка применения")
    
    def _set_force_dns_toggle(self, checked: bool):
        """Устанавливает состояние переключателя без триггера сигналов"""
        self.force_dns_toggle.toggle.blockSignals(True)
        self.force_dns_toggle.setChecked(checked)
        self.force_dns_toggle.toggle.blockSignals(False)
    
    def _update_force_dns_status(self, enabled: bool, details: str = ""):
        """Обновляет текст статуса для принудительного DNS"""
        if not hasattr(self, "force_dns_status_label"):
            return
        
        status = "Принудительный DNS включен" if enabled else "Принудительный DNS отключен"
        if details:
            status = f"{status} ({details})"
        self.force_dns_status_label.setText(status)
    
    def _update_dns_selection_state(self):
        """Обновляет состояние выбора DNS в зависимости от Force DNS"""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        
        is_blocked = self._force_dns_active
        
        # Применяем эффект прозрачности к DNS карточкам (делает серыми и иконки тоже)
        if hasattr(self, 'dns_cards_container'):
            if is_blocked:
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(0.35)
                self.dns_cards_container.setGraphicsEffect(effect)
            else:
                self.dns_cards_container.setGraphicsEffect(None)
        
        if hasattr(self, 'custom_card'):
            if is_blocked:
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(0.35)
                self.custom_card.setGraphicsEffect(effect)
            else:
                self.custom_card.setGraphicsEffect(None)
    
    def _highlight_force_dns(self):
        """Подсвечивает карточку принудительного DNS при попытке изменить DNS"""
        if not hasattr(self, 'force_dns_card'):
            return
        
        from PyQt6.QtCore import QTimer
        
        # Применяем яркий стиль
        highlight_style = """
            SettingsCard {
                background-color: rgba(96, 205, 255, 0.2);
                border: 2px solid #60cdff;
                border-radius: 10px;
            }
        """
        original_style = self.force_dns_card.styleSheet()
        self.force_dns_card.setStyleSheet(highlight_style)
        
        # Возвращаем оригинальный стиль через 700мс
        QTimer.singleShot(700, lambda: self.force_dns_card.setStyleSheet(original_style))
    
    def _flush_dns_cache(self):
        """Сбрасывает DNS кэш"""
        try:
            from dns.dns_core import DNSManager
            manager = DNSManager()
            manager.flush_dns_cache()
            QMessageBox.information(self, "Готово", "DNS кэш очищен")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось очистить кэш: {e}")

    def _test_connection(self):
        """Тестирует соединение с интернетом"""
        import subprocess

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Проверка...")

        # Подключаем сигнал (однократно)
        try:
            self.test_completed.disconnect()
        except TypeError:
            pass
        self.test_completed.connect(self._on_test_complete)

        def run_test():
            results = []
            test_hosts = [
                ("Google DNS", "8.8.8.8"),
                ("Cloudflare DNS", "1.1.1.1"),
                ("google.com", "google.com"),
                ("youtube.com", "youtube.com"),
            ]

            for name, host in test_hosts:
                try:
                    # ping с таймаутом 2 секунды
                    result = subprocess.run(
                        ["ping", "-n", "1", "-w", "2000", host],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    success = result.returncode == 0
                    results.append((name, host, success))
                except Exception:
                    results.append((name, host, False))

            return results

        def thread_func():
            results = run_test()
            self.test_completed.emit(results)

        thread = threading.Thread(target=thread_func, daemon=True)
        thread.start()

    def _on_test_complete(self, results: list):
        """Вызывается из главного потока после завершения теста"""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Тест соединения")

        # Формируем отчёт
        report_lines = []
        all_ok = True
        for name, host, success in results:
            status = "✓" if success else "✗"
            report_lines.append(f"{status} {name} ({host})")
            if not success:
                all_ok = False

        report = "\n".join(report_lines)

        if all_ok:
            QMessageBox.information(self, "Тест соединения", f"Все проверки пройдены:\n\n{report}")
        else:
            QMessageBox.warning(self, "Тест соединения", f"Некоторые проверки не пройдены:\n\n{report}")
    
