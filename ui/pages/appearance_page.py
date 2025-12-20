# ui/pages/appearance_page.py
"""Страница настроек оформления - темы"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QScrollArea, QCheckBox, QSlider
)
from PyQt6.QtGui import QWheelEvent
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton


class PreciseSlider(QSlider):
    """Слайдер с точным управлением колёсиком мыши (1 шаг за скролл)"""

    def wheelEvent(self, event: QWheelEvent):
        # Определяем направление скролла
        delta = event.angleDelta().y()
        if delta > 0:
            self.setValue(self.value() + 1)
        elif delta < 0:
            self.setValue(self.value() - 1)
        event.accept()


# Цвета для превью тем
THEME_COLORS = {
    "Темная синяя": "#4c8ee7",
    "Темная бирюзовая": "#38b2cd",
    "Темная янтарная": "#eaa23e",
    "Темная розовая": "#e879b2",
    "Светлая синяя": "#4488d9",
    "Светлая бирюзовая": "#30b9ce",
    "РКН Тян": "#6375c6",
    "РКН Тян 2": "#ba7dba",
    "AMOLED Синяя": "#3e94ff",
    "AMOLED Зеленая": "#4cd993",
    "AMOLED Фиолетовая": "#b28ef6",
    "AMOLED Красная": "#eb6c6c",
    "Полностью черная": "#0a0a0a",
}


class ThemeCard(QFrame):
    """Карточка выбора темы"""
    
    clicked = pyqtSignal(str)  # Сигнал клика с именем темы
    
    def __init__(self, name: str, color: str, is_premium: bool = False, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.is_premium = is_premium
        self._selected = False
        self._hovered = False
        self._enabled = True
        
        self.setFixedSize(100, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("themeCard")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Цветовой прямоугольник
        self.color_widget = QWidget()
        self.color_widget.setFixedHeight(36)
        self.color_widget.setStyleSheet(f"""
            background-color: {color};
            border-radius: 4px;
        """)
        layout.addWidget(self.color_widget)
        
        # Название
        name_layout = QHBoxLayout()
        name_layout.setSpacing(4)
        
        # Сокращаем длинные названия
        display_name = name
        if len(name) > 12:
            display_name = name[:11] + "…"
        
        self.name_label = QLabel(display_name)
        self.name_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9);
            font-size: 10px;
        """)
        self.name_label.setToolTip(name)
        name_layout.addWidget(self.name_label)
        
        if is_premium:
            premium_icon = QLabel()
            premium_icon.setPixmap(qta.icon('fa5s.star', color='#ffc107').pixmap(10, 10))
            premium_icon.setToolTip("Премиум-тема")
            name_layout.addWidget(premium_icon)
            
        name_layout.addStretch()
        layout.addLayout(name_layout)
        
        self._update_style()
        
    def _update_style(self):
        if not self._enabled:
            # Disabled состояние - затемнённый вид
            border = "1px solid rgba(255, 255, 255, 0.05)"
            bg = "rgba(255, 255, 255, 0.02)"
            text_color = "rgba(255, 255, 255, 0.3)"
        elif self._selected:
            border = "2px solid #60cdff"
            bg = "rgba(96, 205, 255, 0.15)"
            text_color = "rgba(255, 255, 255, 0.9)"
        elif self._hovered:
            border = "1px solid rgba(255, 255, 255, 0.3)"
            bg = "rgba(255, 255, 255, 0.1)"
            text_color = "rgba(255, 255, 255, 0.9)"
        else:
            border = "1px solid rgba(255, 255, 255, 0.1)"
            bg = "rgba(255, 255, 255, 0.04)"
            text_color = "rgba(255, 255, 255, 0.9)"
            
        self.setStyleSheet(f"""
            QFrame#themeCard {{
                background-color: {bg};
                border: {border};
                border-radius: 6px;
            }}
        """)
        
        # Обновляем цвет текста
        self.name_label.setStyleSheet(f"color: {text_color}; font-size: 10px;")
        
        # Затемняем превью цвета если disabled
        if hasattr(self, 'color_widget'):
            if self._enabled:
                self.color_widget.setStyleSheet(f"""
                    background-color: {self.color};
                    border-radius: 4px;
                """)
            else:
                self.color_widget.setStyleSheet(f"""
                    background-color: {self.color};
                    border-radius: 4px;
                    opacity: 0.3;
                """)
        
    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()
        
    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ForbiddenCursor)
        self._update_style()
        
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._enabled:
            self.clicked.emit(self.name)
        super().mousePressEvent(event)


class AppearancePage(BasePage):
    """Страница настроек оформления"""

    # Сигнал смены темы
    theme_changed = pyqtSignal(str)
    # Сигнал изменения состояния гирлянды
    garland_changed = pyqtSignal(bool)
    # Сигнал изменения состояния снежинок
    snowflakes_changed = pyqtSignal(bool)
    # Сигнал изменения состояния эффекта размытия
    blur_effect_changed = pyqtSignal(bool)
    # Сигнал изменения прозрачности окна (0-100)
    opacity_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("Оформление", "Настройка внешнего вида приложения", parent)

        self._theme_cards = {}  # name -> ThemeCard
        self._current_theme = None
        self._is_premium = False
        self._garland_checkbox = None
        self._snowflakes_checkbox = None
        self._wall_animation_checkbox = None
        self._blur_effect_checkbox = None
        self._opacity_slider = None
        self._opacity_label = None

        self._build_ui()
        
    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # СТАНДАРТНЫЕ ТЕМЫ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Стандартные темы")
        
        standard_card = SettingsCard()
        
        standard_layout = QVBoxLayout()
        standard_layout.setSpacing(12)
        
        # Описание
        desc = QLabel("Выберите тему оформления для приложения.")
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        desc.setWordWrap(True)
        standard_layout.addWidget(desc)
        
        # Галерея стандартных тем
        standard_themes_layout = QGridLayout()
        standard_themes_layout.setSpacing(8)
        
        standard_themes = [
            ("Темная синяя", False),
            ("Темная бирюзовая", False),
            ("Темная янтарная", False),
            ("Темная розовая", False),
            ("Светлая синяя", False),
            ("Светлая бирюзовая", False),
        ]
        
        for i, (name, is_premium) in enumerate(standard_themes):
            color = THEME_COLORS.get(name, "#333333")
            card = ThemeCard(name, color, is_premium=is_premium)
            card.clicked.connect(self._on_theme_clicked)
            row = i // 4
            col = i % 4
            standard_themes_layout.addWidget(card, row, col)
            self._theme_cards[name] = card
            
        standard_layout.addLayout(standard_themes_layout)
        standard_card.add_layout(standard_layout)
        
        self.add_widget(standard_card)
        
        self.add_spacing(16)
        
        # ═══════════════════════════════════════════════════════════
        # ПРЕМИУМ ТЕМЫ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Премиум темы")
        
        premium_card = SettingsCard()
        
        premium_layout = QVBoxLayout()
        premium_layout.setSpacing(12)
        
        premium_desc = QLabel(
            "Дополнительные темы доступны подписчикам Zapret Premium. "
            "Включая AMOLED темы и уникальные стили."
        )
        premium_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        premium_desc.setWordWrap(True)
        premium_layout.addWidget(premium_desc)
        
        # Галерея премиум тем
        premium_themes_layout = QGridLayout()
        premium_themes_layout.setSpacing(8)
        
        premium_themes = [
            ("РКН Тян", True),
            ("РКН Тян 2", True),
            ("AMOLED Синяя", True),
            ("AMOLED Зеленая", True),
            ("AMOLED Фиолетовая", True),
            ("AMOLED Красная", True),
            ("Полностью черная", True),
        ]
        
        for i, (name, is_premium) in enumerate(premium_themes):
            color = THEME_COLORS.get(name, "#333333")
            card = ThemeCard(name, color, is_premium=is_premium)
            card.clicked.connect(self._on_theme_clicked)
            card.set_enabled(False)  # По умолчанию заблокированы до проверки премиума
            row = i // 4
            col = i % 4
            premium_themes_layout.addWidget(card, row, col)
            self._theme_cards[name] = card
            
        premium_layout.addLayout(premium_themes_layout)
        
        # Кнопка подписки
        from ui.sidebar import ActionButton
        sub_btn_layout = QHBoxLayout()
        
        self.subscription_btn = ActionButton("Управление подпиской", "fa5s.star")
        self.subscription_btn.setFixedHeight(36)
        sub_btn_layout.addWidget(self.subscription_btn)
        
        sub_btn_layout.addStretch()
        premium_layout.addLayout(sub_btn_layout)
        
        premium_card.add_layout(premium_layout)
        self.add_widget(premium_card)
        
        self.add_spacing(16)
        
        # ═══════════════════════════════════════════════════════════
        # НОВОГОДНЕЕ ОФОРМЛЕНИЕ (Premium)
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Новогоднее оформление")
        
        garland_card = SettingsCard()
        
        garland_layout = QVBoxLayout()
        garland_layout.setSpacing(12)
        
        # Описание
        garland_desc = QLabel(
            "Праздничная гирлянда с мерцающими огоньками в верхней части окна. "
            "Доступно только для подписчиков Premium."
        )
        garland_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        garland_desc.setWordWrap(True)
        garland_layout.addWidget(garland_desc)
        
        # Переключатель
        garland_row = QHBoxLayout()
        garland_row.setSpacing(12)
        
        garland_icon = QLabel()
        garland_icon.setPixmap(qta.icon('fa5s.holly-berry', color='#ff6b6b').pixmap(20, 20))
        garland_row.addWidget(garland_icon)
        
        garland_label = QLabel("Новогодняя гирлянда")
        garland_label.setStyleSheet("color: #ffffff; font-size: 13px;")
        garland_row.addWidget(garland_label)
        
        premium_badge = QLabel("⭐ Premium")
        premium_badge.setStyleSheet("""
            color: #ffc107;
            font-size: 10px;
            font-weight: bold;
            background-color: rgba(255, 193, 7, 0.15);
            padding: 2px 6px;
            border-radius: 4px;
        """)
        garland_row.addWidget(premium_badge)
        
        garland_row.addStretch()
        
        self._garland_checkbox = QCheckBox()
        self._garland_checkbox.setEnabled(False)  # Включается только при премиуме
        self._garland_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QCheckBox::indicator:checked {
                background-color: #4cd964;
                border-color: #4cd964;
            }
            QCheckBox::indicator:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #5ce06e;
            }
            QCheckBox::indicator:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self._garland_checkbox.stateChanged.connect(self._on_garland_changed)
        garland_row.addWidget(self._garland_checkbox)
        
        garland_layout.addLayout(garland_row)
        
        garland_card.add_layout(garland_layout)
        self.add_widget(garland_card)
        
        # ═══════════════════════════════════════════════════════════
        # СНЕЖИНКИ (Premium)
        # ═══════════════════════════════════════════════════════════
        snowflakes_card = SettingsCard()
        
        snowflakes_layout = QVBoxLayout()
        snowflakes_layout.setSpacing(12)
        
        # Описание
        snowflakes_desc = QLabel(
            "Мягко падающие снежинки по всему окну. "
            "Создаёт уютную зимнюю атмосферу."
        )
        snowflakes_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        snowflakes_desc.setWordWrap(True)
        snowflakes_layout.addWidget(snowflakes_desc)
        
        # Переключатель
        snowflakes_row = QHBoxLayout()
        snowflakes_row.setSpacing(12)
        
        snowflakes_icon = QLabel()
        snowflakes_icon.setPixmap(qta.icon('fa5s.snowflake', color='#87ceeb').pixmap(20, 20))
        snowflakes_row.addWidget(snowflakes_icon)
        
        snowflakes_label = QLabel("Снежинки")
        snowflakes_label.setStyleSheet("color: #ffffff; font-size: 13px;")
        snowflakes_row.addWidget(snowflakes_label)
        
        snowflakes_badge = QLabel("⭐ Premium")
        snowflakes_badge.setStyleSheet("""
            color: #ffc107;
            font-size: 10px;
            font-weight: bold;
            background-color: rgba(255, 193, 7, 0.15);
            padding: 2px 6px;
            border-radius: 4px;
        """)
        snowflakes_row.addWidget(snowflakes_badge)
        
        snowflakes_row.addStretch()
        
        self._snowflakes_checkbox = QCheckBox()
        self._snowflakes_checkbox.setEnabled(False)  # Включается только при премиуме
        self._snowflakes_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QCheckBox::indicator:checked {
                background-color: #87ceeb;
                border-color: #87ceeb;
            }
            QCheckBox::indicator:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #9dd5f0;
            }
            QCheckBox::indicator:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self._snowflakes_checkbox.stateChanged.connect(self._on_snowflakes_changed)
        snowflakes_row.addWidget(self._snowflakes_checkbox)
        
        snowflakes_layout.addLayout(snowflakes_row)
        
        snowflakes_card.add_layout(snowflakes_layout)
        self.add_widget(snowflakes_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ЭФФЕКТ РАЗМЫТИЯ (Acrylic/Mica)
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Эффект окна")

        blur_card = SettingsCard()

        blur_layout = QVBoxLayout()
        blur_layout.setSpacing(12)

        # Описание
        blur_desc = QLabel(
            "Матовое размытие фона окна (Acrylic). "
            "Позволяет видеть размытое содержимое за окном. "
            "Требует Windows 10 1803+ или Windows 11."
        )
        blur_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        blur_desc.setWordWrap(True)
        blur_layout.addWidget(blur_desc)

        # Переключатель
        blur_row = QHBoxLayout()
        blur_row.setSpacing(12)

        blur_icon = QLabel()
        blur_icon.setPixmap(qta.icon('fa5s.magic', color='#60cdff').pixmap(20, 20))
        blur_row.addWidget(blur_icon)

        blur_label = QLabel("Размытие фона (Acrylic)")
        blur_label.setStyleSheet("color: #ffffff; font-size: 13px;")
        blur_row.addWidget(blur_label)

        blur_row.addStretch()

        self._blur_effect_checkbox = QCheckBox()
        self._blur_effect_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QCheckBox::indicator:checked {
                background-color: #60cdff;
                border-color: #60cdff;
            }
            QCheckBox::indicator:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #7dd8ff;
            }
            QCheckBox::indicator:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self._blur_effect_checkbox.stateChanged.connect(self._on_blur_effect_changed)
        blur_row.addWidget(self._blur_effect_checkbox)

        blur_layout.addLayout(blur_row)

        # Предупреждение о совместимости
        from ui.theme import BlurEffect
        if not BlurEffect.is_supported():
            warning_label = QLabel("⚠️ Эффект недоступен на вашей системе")
            warning_label.setStyleSheet("color: #ff9800; font-size: 10px;")
            blur_layout.addWidget(warning_label)
            self._blur_effect_checkbox.setEnabled(False)

        blur_card.add_layout(blur_layout)
        self.add_widget(blur_card)

        # ═══════════════════════════════════════════════════════════
        # ПРОЗРАЧНОСТЬ ОКНА
        # ═══════════════════════════════════════════════════════════
        opacity_card = SettingsCard()

        opacity_layout = QVBoxLayout()
        opacity_layout.setSpacing(12)

        # Описание
        opacity_desc = QLabel(
            "Настройка прозрачности всего окна приложения. "
            "При 0% окно полностью прозрачное, при 100% — непрозрачное."
        )
        opacity_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        opacity_desc.setWordWrap(True)
        opacity_layout.addWidget(opacity_desc)

        # Строка с иконкой, названием и значением
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(12)

        opacity_icon = QLabel()
        opacity_icon.setPixmap(qta.icon('fa5s.adjust', color='#60cdff').pixmap(20, 20))
        opacity_row.addWidget(opacity_icon)

        opacity_title = QLabel("Прозрачность окна")
        opacity_title.setStyleSheet("color: #ffffff; font-size: 13px;")
        opacity_row.addWidget(opacity_title)

        opacity_row.addStretch()

        self._opacity_label = QLabel("100%")
        self._opacity_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px; min-width: 40px;")
        self._opacity_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_row.addWidget(self._opacity_label)

        opacity_layout.addLayout(opacity_row)

        # Слайдер
        self._opacity_slider = PreciseSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(10)  # Минимум 10% чтобы окно не стало невидимым
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setSingleStep(1)
        self._opacity_slider.setPageStep(5)  # Page Up/Down меняет на 5%
        self._opacity_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self._opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #60cdff;
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #7dd8ff;
            }
            QSlider::sub-page:horizontal {
                background: #60cdff;
                border-radius: 2px;
            }
        """)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self._opacity_slider)

        opacity_card.add_layout(opacity_layout)
        self.add_widget(opacity_card)

        self.add_spacing(16)

        # ═══════════════════════════════════════════════════════════
        # ПРОИЗВОДИТЕЛЬНОСТЬ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Производительность")
        
        wall_card = SettingsCard()
        
        wall_layout = QVBoxLayout()
        wall_layout.setSpacing(12)
        
        # Описание
        wall_desc = QLabel(
            "Анимация разрушения стены на загрузочном экране. "
            "Отключите для ускорения запуска на слабых системах."
        )
        wall_desc.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        wall_desc.setWordWrap(True)
        wall_layout.addWidget(wall_desc)
        
        # Переключатель
        wall_row = QHBoxLayout()
        wall_row.setSpacing(12)
        
        wall_icon = QLabel()
        wall_icon.setPixmap(qta.icon('fa5s.cubes', color='#ff6666').pixmap(20, 20))
        wall_row.addWidget(wall_icon)
        
        wall_label = QLabel("Анимация кирпичей")
        wall_label.setStyleSheet("color: #ffffff; font-size: 13px;")
        wall_row.addWidget(wall_label)
        
        wall_row.addStretch()
        
        self._wall_animation_checkbox = QCheckBox()
        self._wall_animation_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QCheckBox::indicator:checked {
                background-color: #4cd964;
                border-color: #4cd964;
            }
            QCheckBox::indicator:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #5ce06e;
            }
        """)
        self._wall_animation_checkbox.stateChanged.connect(self._on_wall_animation_changed)
        wall_row.addWidget(self._wall_animation_checkbox)
        
        wall_layout.addLayout(wall_row)
        
        wall_card.add_layout(wall_layout)
        self.add_widget(wall_card)
        
    def _on_wall_animation_changed(self, state):
        """Обработчик изменения состояния анимации стены"""
        enabled = state == Qt.CheckState.Checked.value

        # Сохраняем в реестр
        from config import set_wall_animation_enabled
        set_wall_animation_enabled(enabled)

        from log import log
        log(f"Анимация стены {'включена' if enabled else 'отключена'}", "DEBUG")

    def _on_blur_effect_changed(self, state):
        """Обработчик изменения состояния эффекта размытия"""
        enabled = state == Qt.CheckState.Checked.value

        # Сохраняем в реестр
        from config.reg import set_blur_effect_enabled
        set_blur_effect_enabled(enabled)

        # Уведомляем главное окно
        self.blur_effect_changed.emit(enabled)

        from log import log
        log(f"Эффект размытия {'включён' if enabled else 'выключен'}", "DEBUG")

    def _on_opacity_changed(self, value: int):
        """Обработчик изменения прозрачности окна"""
        # Обновляем лейбл
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

        # Сохраняем в реестр
        from config.reg import set_window_opacity
        set_window_opacity(value)

        # Уведомляем главное окно
        self.opacity_changed.emit(value)

        from log import log
        log(f"Прозрачность окна: {value}%", "DEBUG")

    def _on_snowflakes_changed(self, state):
        """Обработчик изменения состояния снежинок"""
        enabled = state == Qt.CheckState.Checked.value
        
        # Сохраняем в реестр
        from config.reg import set_snowflakes_enabled
        set_snowflakes_enabled(enabled)
        
        # Уведомляем главное окно
        self.snowflakes_changed.emit(enabled)
        
    def _on_garland_changed(self, state):
        """Обработчик изменения состояния гирлянды"""
        enabled = state == Qt.CheckState.Checked.value
        
        # Сохраняем в реестр
        from config.reg import set_garland_enabled
        set_garland_enabled(enabled)
        
        # Эмитим сигнал
        self.garland_changed.emit(enabled)
        
    def _on_theme_clicked(self, theme_name: str):
        """Обработчик клика по карточке темы"""
        # Проверяем, является ли тема премиум и заблокирована ли она
        card = self._theme_cards.get(theme_name)
        if card and card.is_premium and not self._is_premium:
            # Просто игнорируем клик - карточка уже визуально disabled
            return
            
        # Устанавливаем выбранную тему
        self._select_theme(theme_name)
        
        # Эмитим сигнал смены темы
        self.theme_changed.emit(theme_name)
        
    def _select_theme(self, theme_name: str):
        """Визуально выделяет выбранную тему"""
        # Снимаем выделение со старой темы
        if self._current_theme and self._current_theme in self._theme_cards:
            self._theme_cards[self._current_theme].set_selected(False)
            
        # Выделяем новую тему
        if theme_name in self._theme_cards:
            self._theme_cards[theme_name].set_selected(True)
            self._current_theme = theme_name
            
    def set_current_theme(self, theme_name: str):
        """Устанавливает текущую тему (без эмита сигнала)"""
        # Очищаем название от суффиксов
        clean_name = theme_name
        suffixes = [" (заблокировано)", " (AMOLED Premium)", " (Pure Black Premium)"]
        for suffix in suffixes:
            clean_name = clean_name.replace(suffix, "")
            
        self._select_theme(clean_name)
        
    def set_premium_status(self, is_premium: bool):
        """Устанавливает статус премиум-подписки"""
        self._is_premium = is_premium
        
        # Обновляем состояние карточек премиум тем
        premium_themes = ["РКН Тян", "РКН Тян 2", "AMOLED Синяя", "AMOLED Зеленая", 
                         "AMOLED Фиолетовая", "AMOLED Красная", "Полностью черная"]
        
        for name in premium_themes:
            if name in self._theme_cards:
                # Включаем/выключаем карточки в зависимости от премиум статуса
                self._theme_cards[name].set_enabled(is_premium)
        
        # Включаем/выключаем чекбоксы новогоднего оформления
        from config.reg import get_garland_enabled, get_snowflakes_enabled, get_blur_effect_enabled
        from config import get_wall_animation_enabled

        # Загружаем настройку анимации стены (не зависит от премиума)
        if self._wall_animation_checkbox:
            self._wall_animation_checkbox.blockSignals(True)
            self._wall_animation_checkbox.setChecked(get_wall_animation_enabled())
            self._wall_animation_checkbox.blockSignals(False)

        # Загружаем настройку эффекта размытия (не зависит от премиума)
        if self._blur_effect_checkbox and self._blur_effect_checkbox.isEnabled():
            self._blur_effect_checkbox.blockSignals(True)
            self._blur_effect_checkbox.setChecked(get_blur_effect_enabled())
            self._blur_effect_checkbox.blockSignals(False)
        
        if self._garland_checkbox:
            self._garland_checkbox.setEnabled(is_premium)
            self._garland_checkbox.blockSignals(True)
            if is_premium:
                # При появлении премиума - восстанавливаем сохранённое состояние
                self._garland_checkbox.setChecked(get_garland_enabled())
            else:
                # При потере премиума - выключаем визуально
                self._garland_checkbox.setChecked(False)
            self._garland_checkbox.blockSignals(False)
                
        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.setEnabled(is_premium)
            self._snowflakes_checkbox.blockSignals(True)
            if is_premium:
                # При появлении премиума - восстанавливаем сохранённое состояние
                self._snowflakes_checkbox.setChecked(get_snowflakes_enabled())
            else:
                # При потере премиума - выключаем визуально
                self._snowflakes_checkbox.setChecked(False)
            self._snowflakes_checkbox.blockSignals(False)
                
        # Если нет премиума и гирлянда включена - выключаем
        if not is_premium and self._garland_checkbox and self._garland_checkbox.isChecked():
            self._garland_checkbox.blockSignals(True)
            self._garland_checkbox.setChecked(False)
            self._garland_checkbox.blockSignals(False)
            from config.reg import set_garland_enabled
            set_garland_enabled(False)
            self.garland_changed.emit(False)
            
        # Если нет премиума и снежинки включены - выключаем
        if not is_premium and self._snowflakes_checkbox and self._snowflakes_checkbox.isChecked():
            self._snowflakes_checkbox.blockSignals(True)
            self._snowflakes_checkbox.setChecked(False)
            self._snowflakes_checkbox.blockSignals(False)
            from config.reg import set_snowflakes_enabled
            set_snowflakes_enabled(False)
            self.snowflakes_changed.emit(False)
            
    def set_garland_state(self, enabled: bool):
        """Устанавливает состояние чекбокса гирлянды (без эмита сигнала)"""
        if self._garland_checkbox:
            self._garland_checkbox.blockSignals(True)
            self._garland_checkbox.setChecked(enabled)
            self._garland_checkbox.blockSignals(False)
    
    def set_snowflakes_state(self, enabled: bool):
        """Устанавливает состояние чекбокса снежинок (без эмита сигнала)"""
        if self._snowflakes_checkbox:
            self._snowflakes_checkbox.blockSignals(True)
            self._snowflakes_checkbox.setChecked(enabled)
            self._snowflakes_checkbox.blockSignals(False)

    def set_blur_effect_state(self, enabled: bool):
        """Устанавливает состояние чекбокса эффекта размытия (без эмита сигнала)"""
        if self._blur_effect_checkbox:
            self._blur_effect_checkbox.blockSignals(True)
            self._blur_effect_checkbox.setChecked(enabled)
            self._blur_effect_checkbox.blockSignals(False)

    def set_opacity_value(self, value: int):
        """Устанавливает значение слайдера прозрачности (без эмита сигнала)"""
        if self._opacity_slider:
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(value)
            self._opacity_slider.blockSignals(False)
        if self._opacity_label:
            self._opacity_label.setText(f"{value}%")

    def update_themes(self, themes: list, current_theme: str = None):
        """Обновляет текущую выбранную тему (для совместимости)"""
        if current_theme:
            self.set_current_theme(current_theme)
