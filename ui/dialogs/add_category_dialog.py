# ui/dialogs/add_category_dialog.py
"""
Диалог добавления пользовательской категории (сервиса/сайта).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QFormLayout, QFrame,
    QWidget, QSpinBox, QCheckBox, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont
import qtawesome as qta

from log import log


class CompactInput(QLineEdit):
    """Компактное поле ввода"""
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(32)
        self.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                background: rgba(96, 205, 255, 0.1);
            }
        """)


class CompactCombo(QComboBox):
    """Компактный комбобокс"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.06);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QComboBox:focus {
                background: rgba(96, 205, 255, 0.1);
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background: #252525;
                color: white;
                selection-background-color: rgba(96, 205, 255, 0.2);
                border: none;
            }
        """)


class DeleteButton(QPushButton):
    """Кнопка удаления с двойным подтверждением и анимацией корзины"""
    
    delete_confirmed = pyqtSignal()
    
    def __init__(self, text: str = "Удалить", parent=None):
        super().__init__(text, parent)
        self._default_text = text
        self._confirm_text = "Точно?"
        self._pending = False
        self._hovered = False
        
        # Иконка
        self._update_icon()
        self.setIconSize(QSize(14, 14))
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Таймер сброса состояния
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset_state)
        
        # Анимация иконки (качание)
        self._shake_timer = QTimer(self)
        self._shake_timer.timeout.connect(self._animate_shake)
        self._shake_step = 0
        
        self._update_style()
        
    def _update_icon(self, rotation: int = 0):
        """Обновляет иконку с опциональным углом поворота"""
        color = '#ff6b6b' if self._pending else 'white'
        if rotation != 0:
            self.setIcon(qta.icon('fa5s.trash-alt', color=color, rotated=rotation))
        else:
            self.setIcon(qta.icon('fa5s.trash-alt', color=color))
        
    def _update_style(self):
        """Обновляет стили кнопки"""
        if self._pending:
            # Состояние подтверждения - красный цвет
            if self._hovered:
                bg = "rgba(255, 107, 107, 0.45)"
            else:
                bg = "rgba(255, 107, 107, 0.35)"
            text_color = "#ff6b6b"
            border = "1px solid rgba(255, 107, 107, 0.6)"
        else:
            # Обычное состояние
            if self._hovered:
                bg = "rgba(209, 52, 56, 0.9)"
            else:
                bg = "#d13438"
            text_color = "#ffffff"
            border = "none"
            
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: {border};
                border-radius: 4px;
                color: {text_color};
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }}
        """)
        
    def _animate_shake(self):
        """Анимация качания иконки"""
        self._shake_step += 1
        if self._shake_step > 8:
            self._shake_timer.stop()
            self._shake_step = 0
            self._update_icon(0)
            return
            
        # Качаем иконку влево-вправо
        rotations = [0, -15, 15, -12, 12, -8, 8, -4, 0]
        rotation = rotations[min(self._shake_step, len(rotations) - 1)]
        self._update_icon(rotation)
        
    def _start_shake_animation(self):
        """Запускает анимацию качания"""
        self._shake_step = 0
        self._shake_timer.start(50)
        
    def _reset_state(self):
        """Сбрасывает состояние кнопки"""
        self._pending = False
        self.setText(self._default_text)
        self._update_icon()
        self._update_style()
        self._shake_timer.stop()
        
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        """Обработка клика"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._pending:
                # Второй клик - подтверждение
                self._reset_timer.stop()
                self._pending = False
                self.setText("✓ Удалено")
                self._update_icon()
                self._update_style()
                self.delete_confirmed.emit()
            else:
                # Первый клик - переход в режим подтверждения
                self._pending = True
                self.setText(self._confirm_text)
                self._update_icon()
                self._update_style()
                self._start_shake_animation()
                # Автосброс через 3 секунды
                self._reset_timer.start(3000)
        super().mousePressEvent(event)


class AddCategoryDialog(QDialog):
    """Диалог добавления/редактирования категории"""
    
    category_added = pyqtSignal(dict)
    category_updated = pyqtSignal(dict)
    category_deleted = pyqtSignal(str)  # key категории
    
    def __init__(self, parent=None, category_data=None):
        """
        Args:
            parent: Родительский виджет
            category_data: Данные категории для редактирования (None = создание новой)
        """
        super().__init__(parent)
        self.category_data = category_data
        self.is_edit_mode = category_data is not None
        
        title = "Редактировать категорию" if self.is_edit_mode else "Добавить категорию"
        self.setWindowTitle(title)
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog {
                background: #1a1a1a;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.8);
                font-size: 11px;
            }
            QCheckBox {
                color: rgba(255, 255, 255, 0.8);
                font-size: 11px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: none;
                background: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background: #60cdff;
            }
        """)
        
        self._build_ui()
        
        # Заполняем поля если редактируем
        if self.is_edit_mode:
            self._populate_fields()
        else:
            # Устанавливаем strategy_type по умолчанию на основе протокола
            self._on_protocol_changed(self.protocol_combo.currentText())
        
        self.adjustSize()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Заголовок
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_name = 'fa5s.edit' if self.is_edit_mode else 'fa5s.plus-circle'
        icon_label.setPixmap(qta.icon(icon_name, color='#60cdff').pixmap(20, 20))
        header.addWidget(icon_label)
        
        title_text = "Редактирование категории" if self.is_edit_mode else "Новая категория"
        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title.setStyleSheet("color: white;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        
        # === ОСНОВНЫЕ ПОЛЯ ===
        basic_frame = QFrame()
        basic_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border: none;
                border-radius: 6px;
            }
        """)
        basic_layout = QGridLayout(basic_frame)
        basic_layout.setContentsMargins(12, 10, 12, 10)
        basic_layout.setSpacing(8)
        basic_layout.setColumnStretch(1, 1)
        
        # Ключ
        basic_layout.addWidget(QLabel("Ключ:"), 0, 0)
        self.key_input = CompactInput("mysite_tcp")
        self.key_input.setToolTip("Уникальный ID (латиница, цифры, _)")
        # Блокируем изменение ключа при редактировании
        if self.is_edit_mode:
            self.key_input.setReadOnly(True)
            self.key_input.setStyleSheet(self.key_input.styleSheet() + """
                QLineEdit[readOnly="true"] {
                    background: rgba(255, 255, 255, 0.03);
                    color: rgba(255, 255, 255, 0.5);
                }
            """)
        basic_layout.addWidget(self.key_input, 0, 1)
        
        # Название
        basic_layout.addWidget(QLabel("Название:"), 1, 0)
        self.name_input = CompactInput("Мой сайт")
        basic_layout.addWidget(self.name_input, 1, 1)
        
        # Лейбл ошибки (скрыт по умолчанию)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff6b6b; font-size: 10px; padding: 2px 0;")
        self.error_label.setVisible(False)
        basic_layout.addWidget(self.error_label, 2, 0, 1, 2)
        
        layout.addWidget(basic_frame)
        
        # === ФИЛЬТР ===
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border: none;
                border-radius: 6px;
            }
        """)
        filter_layout = QGridLayout(filter_frame)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(8)
        filter_layout.setColumnStretch(1, 1)
        
        # Заголовок секции
        filter_title = QLabel("⚙ Фильтр")
        filter_title.setStyleSheet("color: #60cdff; font-weight: 600; font-size: 11px;")
        filter_layout.addWidget(filter_title, 0, 0, 1, 2)
        
        # Протокол и порты в одной строке
        proto_ports = QHBoxLayout()
        proto_ports.setSpacing(8)
        
        self.protocol_combo = CompactCombo()
        self.protocol_combo.addItems(["TCP", "UDP"])
        self.protocol_combo.setFixedWidth(70)
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        proto_ports.addWidget(self.protocol_combo)
        
        self.ports_input = CompactInput("80, 443")
        self.ports_input.setToolTip("Порты через запятую или диапазон")
        proto_ports.addWidget(self.ports_input)
        
        filter_layout.addWidget(QLabel("Протокол/порты:"), 1, 0)
        proto_widget = QWidget()
        proto_widget.setLayout(proto_ports)
        filter_layout.addWidget(proto_widget, 1, 1)
        
        # Тип фильтра
        filter_layout.addWidget(QLabel("Тип:"), 2, 0)
        self.filter_type_combo = CompactCombo()
        self.filter_type_combo.addItems(["hostlist", "ipset", "hostlist-domains"])
        self.filter_type_combo.setToolTip("hostlist - домены, ipset - IP адреса")
        filter_layout.addWidget(self.filter_type_combo, 2, 1)
        
        # Файл списка
        filter_layout.addWidget(QLabel("Файл:"), 3, 0)
        self.list_file_input = CompactInput("my-sites.txt")
        self.list_file_input.setToolTip("Файл в папке lists/")
        filter_layout.addWidget(self.list_file_input, 3, 1)
        
        layout.addWidget(filter_frame)
        
        # === СТРАТЕГИЯ ===
        strat_frame = QFrame()
        strat_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border: none;
                border-radius: 6px;
            }
        """)
        strat_layout = QGridLayout(strat_frame)
        strat_layout.setContentsMargins(12, 10, 12, 10)
        strat_layout.setSpacing(8)
        strat_layout.setColumnStretch(1, 1)
        
        strat_title = QLabel("🎯 Стратегия")
        strat_title.setStyleSheet("color: #60cdff; font-weight: 600; font-size: 11px;")
        strat_layout.addWidget(strat_title, 0, 0, 1, 2)
        
        # Тип стратегий и стратегия по умолчанию
        strat_layout.addWidget(QLabel("Тип:"), 1, 0)
        self.strategy_type_combo = CompactCombo()
        self.strategy_type_combo.addItems(["tcp", "udp", "http80"])
        strat_layout.addWidget(self.strategy_type_combo, 1, 1)
        
        strat_layout.addWidget(QLabel("По умолчанию:"), 2, 0)
        self.default_strategy_input = CompactInput("other_seqovl")
        strat_layout.addWidget(self.default_strategy_input, 2, 1)
        
        layout.addWidget(strat_frame)
        
        # === ВНЕШНИЙ ВИД ===
        look_frame = QFrame()
        look_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border: none;
                border-radius: 6px;
            }
        """)
        look_layout = QGridLayout(look_frame)
        look_layout.setContentsMargins(12, 10, 12, 10)
        look_layout.setSpacing(8)
        look_layout.setColumnStretch(1, 1)
        
        look_title = QLabel("🎨 Вид")
        look_title.setStyleSheet("color: #60cdff; font-weight: 600; font-size: 11px;")
        look_layout.addWidget(look_title, 0, 0, 1, 2)
        
        # Иконка и цвет
        icon_color = QHBoxLayout()
        icon_color.setSpacing(8)
        
        self.icon_combo = CompactCombo()
        self._populate_icons()
        self.icon_combo.setFixedWidth(140)
        icon_color.addWidget(self.icon_combo)
        
        self.color_input = CompactInput("#60cdff")
        self.color_input.setFixedWidth(80)
        self.color_input.setToolTip("Цвет иконки (HEX)")
        icon_color.addWidget(self.color_input)
        icon_color.addStretch()
        
        look_layout.addWidget(QLabel("Иконка/цвет:"), 1, 0)
        icon_widget = QWidget()
        icon_widget.setLayout(icon_color)
        look_layout.addWidget(icon_widget, 1, 1)
        
        # Порядок
        order_layout = QHBoxLayout()
        order_layout.setSpacing(8)
        
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 999)
        self.order_spin.setValue(100)
        self.order_spin.setFixedWidth(70)
        self.order_spin.setFixedHeight(32)
        self.order_spin.setStyleSheet("""
            QSpinBox {
                background: rgba(255, 255, 255, 0.06);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QSpinBox:focus {
                background: rgba(96, 205, 255, 0.1);
            }
        """)
        order_layout.addWidget(self.order_spin)
        order_layout.addStretch()
        
        look_layout.addWidget(QLabel("Порядок:"), 2, 0)
        order_widget = QWidget()
        order_widget.setLayout(order_layout)
        look_layout.addWidget(order_widget, 2, 1)
        
        layout.addWidget(look_frame)
        
        # === ОПЦИИ ===
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)
        
        self.requires_all_ports_check = QCheckBox("Все порты")
        self.requires_all_ports_check.setToolTip("Требует агрессивного режима")
        options_layout.addWidget(self.requires_all_ports_check)
        
        self.strip_payload_check = QCheckBox("Strip payload")
        self.strip_payload_check.setToolTip("Убирать payload (для IPset)")
        options_layout.addWidget(self.strip_payload_check)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # === КНОПКИ ===
        layout.addSpacing(4)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Кнопка удаления (только в режиме редактирования)
        if self.is_edit_mode:
            self.delete_btn = DeleteButton("Удалить")
            self.delete_btn.delete_confirmed.connect(self._delete_category)
            buttons_layout.addWidget(self.delete_btn)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 20px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        buttons_layout.addStretch()
        
        save_btn = QPushButton("  Сохранить")
        save_btn.setIcon(qta.icon('fa5s.check', color='white'))
        save_btn.setFixedHeight(34)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 20px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #1a86d9;
            }
        """)
        save_btn.clicked.connect(self._save_category)
        buttons_layout.addWidget(save_btn)
        
        layout.addLayout(buttons_layout)
        
    def _populate_icons(self):
        """Заполняет список иконок"""
        icons = [
            ("fa5s.globe", "🌐 Сайт"),
            ("fa5s.gamepad", "🎮 Игра"),
            ("fa5s.video", "📹 Видео"),
            ("fa5s.music", "🎵 Музыка"),
            ("fa5s.comments", "💬 Чат"),
            ("fa5s.cloud", "☁️ Облако"),
            ("fa5s.server", "🖥️ Сервер"),
            ("fa5s.shield-alt", "🛡️ VPN"),
            ("fa5s.download", "⬇️ Загрузка"),
            ("fa5s.shopping-cart", "🛒 Магазин"),
            ("fa5s.code", "💻 Код"),
            ("fa5b.chrome", "🌐 Браузер"),
        ]
        
        for icon_name, display_name in icons:
            self.icon_combo.addItem(display_name, icon_name)
    
    def _on_protocol_changed(self, protocol: str):
        """Автоматически обновляет strategy_type при изменении протокола"""
        if protocol == "UDP":
            self.strategy_type_combo.setCurrentText("udp")
        elif protocol == "TCP":
            self.strategy_type_combo.setCurrentText("tcp")
    
    def _show_error(self, message: str):
        """Показывает ошибку в лейбле"""
        self.error_label.setText(f"⚠ {message}")
        self.error_label.setVisible(True)
        # Автоскрытие через 3 секунды
        QTimer.singleShot(3000, lambda: self.error_label.setVisible(False))
    
    def _populate_fields(self):
        """Заполняет поля данными существующей категории"""
        if not self.category_data:
            return
        
        data = self.category_data
        
        # Основные поля
        self.key_input.setText(data.get('key', ''))
        self.name_input.setText(data.get('full_name', ''))
        
        # Фильтр
        protocol = data.get('protocol', 'TCP')
        self.protocol_combo.setCurrentText(protocol)
        self.ports_input.setText(data.get('ports', '443'))
        
        # Парсим base_filter для определения типа и файла
        base_filter = data.get('base_filter', '')
        if '--hostlist=' in base_filter:
            self.filter_type_combo.setCurrentText('hostlist')
            # Извлекаем имя файла
            parts = base_filter.split('--hostlist=')
            if len(parts) > 1:
                filename = parts[1].split()[0]
                self.list_file_input.setText(filename)
        elif '--ipset=' in base_filter:
            self.filter_type_combo.setCurrentText('ipset')
            parts = base_filter.split('--ipset=')
            if len(parts) > 1:
                filename = parts[1].split()[0]
                self.list_file_input.setText(filename)
        elif '--hostlist-domains=' in base_filter:
            self.filter_type_combo.setCurrentText('hostlist-domains')
            parts = base_filter.split('--hostlist-domains=')
            if len(parts) > 1:
                domain = parts[1].split()[0]
                self.list_file_input.setText(domain)
        
        # Стратегия
        strategy_type = data.get('strategy_type', 'tcp')
        self.strategy_type_combo.setCurrentText(strategy_type)
        self.default_strategy_input.setText(data.get('default_strategy', 'other_seqovl'))
        
        # Внешний вид
        icon_name = data.get('icon_name', 'fa5s.globe')
        for i in range(self.icon_combo.count()):
            if self.icon_combo.itemData(i) == icon_name:
                self.icon_combo.setCurrentIndex(i)
                break
        
        self.color_input.setText(data.get('icon_color', '#60cdff'))
        self.order_spin.setValue(data.get('order', 100))
        
        # Опции
        self.requires_all_ports_check.setChecked(data.get('requires_all_ports', False))
        self.strip_payload_check.setChecked(data.get('strip_payload', False))
            
    def _build_base_filter(self):
        """Строит base_filter"""
        protocol = self.protocol_combo.currentText()
        ports_raw = self.ports_input.text().strip() or "443"
        # Убираем все пробелы из портов
        ports = ports_raw.replace(" ", "")
        filter_type = self.filter_type_combo.currentText()
        list_file = self.list_file_input.text().strip() or "my-sites.txt"
        
        proto_filter = f"--filter-{'udp' if protocol == 'UDP' else 'tcp'}={ports}"
        
        if filter_type == "hostlist":
            list_filter = f"--hostlist={list_file}"
        elif filter_type == "ipset":
            list_filter = f"--ipset={list_file}"
        else:
            domain = list_file.replace('.txt', '').replace('hostlist-', '')
            list_filter = f"--hostlist-domains={domain}"
            
        return f"{proto_filter} {list_filter}"
        
    def _save_category(self):
        """Сохраняет категорию"""
        key = self.key_input.text().strip()
        name = self.name_input.text().strip()
        
        if not key:
            self._show_error("Введите ключ категории")
            self.key_input.setFocus()
            return
            
        if not all(c.isalnum() or c == '_' for c in key):
            self._show_error("Ключ: только латиница, цифры и _")
            self.key_input.setFocus()
            return
            
        if not name:
            self._show_error("Введите название")
            self.name_input.setFocus()
            return
        
        # Нормализуем порты: убираем все пробелы
        ports_raw = self.ports_input.text().strip() or "443"
        ports_normalized = ports_raw.replace(" ", "")
            
        category_data = {
            "key": key,
            "full_name": name,
            "description": f"{name} ({ports_normalized})",
            "tooltip": f"🌐 {name}\nПорты: {ports_normalized}",
            "color": self.color_input.text().strip() or "#60cdff",
            "default_strategy": self.default_strategy_input.text().strip() or "other_seqovl",
            "ports": ports_normalized,
            "protocol": self.protocol_combo.currentText(),
            "order": self.order_spin.value(),
            "command_order": self.order_spin.value(),
            "needs_new_separator": True,
            "command_group": "user",
            "icon_name": self.icon_combo.currentData() or "fa5s.globe",
            "icon_color": self.color_input.text().strip() or "#60cdff",
            "base_filter": self._build_base_filter(),
            "strategy_type": self.strategy_type_combo.currentText(),
            "requires_all_ports": self.requires_all_ports_check.isChecked(),
            "strip_payload": self.strip_payload_check.isChecked()
        }
        
        try:
            from strategy_menu.strategies.strategy_loader import save_user_category
            from config import LISTS_FOLDER
            import os
            
            success, error = save_user_category(category_data)
            if success:
                action = "обновлена" if self.is_edit_mode else "сохранена"
                log(f"Категория '{key}' {action}", "INFO")
                
                # Испускаем соответствующий сигнал
                if self.is_edit_mode:
                    self.category_updated.emit(category_data)
                else:
                    self.category_added.emit(category_data)
                
                # Создаём файл списка автоматически если его нет (только при создании)
                if not self.is_edit_mode:
                    list_file = self.list_file_input.text().strip() or "my-sites.txt"
                    list_path = os.path.join(LISTS_FOLDER, list_file)
                    
                    if not os.path.exists(list_path):
                        try:
                            os.makedirs(LISTS_FOLDER, exist_ok=True)
                            with open(list_path, 'w', encoding='utf-8') as f:
                                f.write(f"# Список для категории: {name}\n")
                                f.write("# Добавьте домены, по одному на строку\n")
                                f.write("# Пример:\n")
                                f.write("# example.com\n")
                                f.write("# subdomain.example.org\n")
                            log(f"Создан файл списка: {list_path}", "INFO")
                        except Exception as e:
                            log(f"Не удалось создать файл {list_path}: {e}", "WARNING")
                
                self.accept()
            else:
                self._show_error(error)
                
        except Exception as e:
            log(f"Ошибка сохранения: {e}", "ERROR")
            self._show_error(str(e))
    
    def _delete_category(self):
        """Удаляет категорию (вызывается после подтверждения через анимацию)"""
        key = self.key_input.text().strip()
        
        try:
            from strategy_menu.strategies.strategy_loader import delete_user_category
            
            success, error = delete_user_category(key)
            
            if success:
                log(f"Категория '{key}' удалена", "INFO")
                self.category_deleted.emit(key)
                # Закрываем диалог через небольшую задержку чтобы было видно "✓ Удалено"
                QTimer.singleShot(500, self.accept)
            else:
                self._show_error(error)
                # Сбрасываем кнопку
                if hasattr(self, 'delete_btn'):
                    self.delete_btn._reset_state()
                
        except Exception as e:
            log(f"Ошибка удаления: {e}", "ERROR")
            self._show_error(str(e))
            if hasattr(self, 'delete_btn'):
                self.delete_btn._reset_state()
