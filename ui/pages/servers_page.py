# ui/pages/servers_page.py
"""Страница мониторинга серверов обновлений в стиле Windows 11"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QPointF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QFrame, QGraphicsOpacityEffect
)
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QPainterPath, QPen, QBrush
import qtawesome as qta
import time
from datetime import datetime

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton
from config import APP_VERSION, CHANNEL
from log import log
from updater.telegram_updater import TELEGRAM_CHANNELS
from config.telegram_links import open_telegram_link


# ═══════════════════════════════════════════════════════════════════════════════
# TOGGLE SWITCH С ТЕКСТОМ ОТКЛ/ВКЛ
# ═══════════════════════════════════════════════════════════════════════════════

class Win11ToggleSwitch(QWidget):
    """Toggle switch с текстом Откл./Вкл. и цветовой индикацией"""
    
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._position = 0.0  # 0.0 = выкл, 1.0 = вкл
        self._hover = False
        
        self.setFixedSize(100, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Анимация позиции
        self._animation = QPropertyAnimation(self, b"position")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Анимация цвета
        self._color_blend = 0.0  # Инициализируем ДО создания анимации
        self._color_animation = QPropertyAnimation(self, b"color_blend")
        self._color_animation.setDuration(200)
        self._color_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def _get_position(self):
        return self._position
    
    def _set_position(self, value):
        self._position = value
        self.update()
    
    position = pyqtProperty(float, _get_position, _set_position)
    
    def _get_color_blend(self):
        return self._color_blend
    
    def _set_color_blend(self, value):
        self._color_blend = value
        self.update()
    
    color_blend = pyqtProperty(float, _get_color_blend, _set_color_blend)
    
    def isChecked(self) -> bool:
        return self._checked
    
    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._animate()
            
    def _animate(self):
        # Анимация позиции
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if self._checked else 0.0)
        self._animation.start()
        
        # Анимация цвета
        self._color_animation.stop()
        self._color_animation.setStartValue(self._color_blend)
        self._color_animation.setEndValue(1.0 if self._checked else 0.0)
        self._color_animation.start()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self._animate()
            self.toggled.emit(self._checked)
            
    def enterEvent(self, event):
        self._hover = True
        self.update()
        
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        w, h = self.width(), self.height()
        
        # Цвета
        off_color = QColor(180, 70, 70)   # Красный (выкл)
        on_color = QColor(76, 175, 80)    # Зелёный (вкл)
        
        # Интерполяция цвета фона
        r = int(off_color.red() + (on_color.red() - off_color.red()) * self._color_blend)
        g = int(off_color.green() + (on_color.green() - off_color.green()) * self._color_blend)
        b = int(off_color.blue() + (on_color.blue() - off_color.blue()) * self._color_blend)
        current_color = QColor(r, g, b)
        
        if self._hover:
            current_color = current_color.lighter(115)
        
        # Фон (pill shape)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(current_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), h/2, h/2)
        
        # Ползунок (knob)
        knob_width = 46
        knob_height = h - 4
        knob_x = 2 + (w - knob_width - 4) * self._position
        knob_y = 2
        
        knob_color = QColor(255, 255, 255)
        if self._hover:
            knob_color = QColor(245, 245, 245)
        
        painter.setBrush(QBrush(knob_color))
        painter.drawRoundedRect(QRectF(knob_x, knob_y, knob_width, knob_height), knob_height/2, knob_height/2)
        
        # Текст на ползунке
        painter.setPen(QPen(QColor(40, 40, 40)))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        text = "ВКЛ" if self._checked else "Откл."
        text_rect = QRectF(knob_x, knob_y, knob_width, knob_height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


# ═══════════════════════════════════════════════════════════════════════════════
# АНИМИРОВАННАЯ ПОЛОСКА В СТИЛЕ WINDOWS 11
# ═══════════════════════════════════════════════════════════════════════════════

class Win11ProgressBar(QWidget):
    """Анимированная полоска прогресса в стиле Windows 11"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)  # Увеличена высота для видимости
        self.setMinimumHeight(3)
        self._progress = 0.0
        self._animation_offset = 0.0
        self._is_indeterminate = False
        
        # Анимация для indeterminate режима
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        
        self.setStyleSheet("background: rgba(96, 205, 255, 0.1);")
        
    def _get_animation_offset(self):
        return self._animation_offset
    
    def _set_animation_offset(self, value):
        self._animation_offset = value
        self.update()
    
    animation_offset = pyqtProperty(float, _get_animation_offset, _set_animation_offset)
    
    def start_indeterminate(self):
        """Запускает бесконечную анимацию"""
        self._is_indeterminate = True
        self._anim_timer.start(16)  # ~60 FPS
        
    def stop(self):
        """Останавливает анимацию"""
        self._is_indeterminate = False
        self._anim_timer.stop()
        self._animation_offset = 0
        self.update()
        
    def set_progress(self, value: float):
        """Устанавливает прогресс (0.0 - 1.0)"""
        self._progress = max(0.0, min(1.0, value))
        self.update()
        
    def _animate(self):
        """Анимирует полоску"""
        self._animation_offset += 0.015
        if self._animation_offset > 2.0:
            self._animation_offset = 0.0
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Фон (виден когда нет анимации)
        painter.fillRect(0, 0, w, h, QColor(96, 205, 255, 30))
        
        if self._is_indeterminate:
            # Бегущая полоска (стиль Windows 11)
            bar_width = int(w * 0.3)
            offset = self._animation_offset
            
            # Позиция полоски с ease-in-out
            if offset < 1.0:
                # Ускорение в начале
                t = offset
                pos = t * t * (3.0 - 2.0 * t)  # smoothstep
            else:
                # Замедление в конце
                t = offset - 1.0
                pos = 1.0 + t * t * (3.0 - 2.0 * t) * 0.3
            
            x = int((pos - 0.15) * (w + bar_width)) - bar_width
            
            # Градиент для полоски
            gradient = QLinearGradient(x, 0, x + bar_width, 0)
            gradient.setColorAt(0.0, QColor(96, 205, 255, 0))
            gradient.setColorAt(0.3, QColor(96, 205, 255, 255))
            gradient.setColorAt(0.7, QColor(96, 205, 255, 255))
            gradient.setColorAt(1.0, QColor(96, 205, 255, 0))
            
            painter.fillRect(x, 0, bar_width, h, gradient)
        else:
            # Обычный прогресс
            if self._progress > 0:
                progress_width = int(w * self._progress)
                painter.fillRect(0, 0, progress_width, h, QColor(96, 205, 255))


class UpdateStatusCard(QFrame):
    """Карточка статуса обновлений в стиле Windows 11 Update"""
    
    check_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateStatusCard")
        self._is_checking = False
        
        self._build_ui()
        
    def _build_ui(self):
        self.setStyleSheet("""
            QFrame#updateStatusCard {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Контент
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)
        
        # Иконка (крупная, анимированная) - размер увеличен для вращения без обрезки
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_icon_idle()
        content_layout.addWidget(self.icon_label)
        
        # Текст
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        self.title_label = QLabel("Проверка обновлений")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
        """)
        text_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("Нажмите для проверки доступных обновлений")
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 12px;
            }
        """)
        text_layout.addWidget(self.subtitle_label)
        
        content_layout.addLayout(text_layout, 1)
        
        # Кнопка
        self.check_btn = QPushButton("Проверить обновления")
        self.check_btn.setFixedHeight(32)
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(self._on_check_clicked)
        self.check_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #ffffff;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.12);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.04);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.03);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        content_layout.addWidget(self.check_btn)
        
        main_layout.addWidget(content)
        
        # Анимированная полоска снизу
        self.progress_bar = Win11ProgressBar()
        main_layout.addWidget(self.progress_bar)
        
        # Анимация иконки с плавным стартом и завершением
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._rotate_icon)
        self._rotation_angle = 0.0
        self._rotation_speed = 0.0  # Начинаем с 0
        self._rotation_tick = 0
        self._rotation_stopping = False  # Флаг плавного завершения
        
    def _set_icon_idle(self):
        """Устанавливает обычную иконку (центрируется в 64x64)"""
        from PyQt6.QtGui import QPixmap, QPainter
        
        base = qta.icon('fa5s.sync-alt', color='#60cdff').pixmap(48, 48)
        final = QPixmap(64, 64)
        final.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(final)
        painter.drawPixmap(8, 8, base)  # Центрируем 48x48 в 64x64
        painter.end()
        
        self.icon_label.setPixmap(final)
        
    def _set_icon_checking(self):
        """Сбрасывает параметры анимации и показывает начальный кадр"""
        self._rotation_angle = 0.0
        self._rotation_speed = 0.0  # Начинаем с 0 для плавного старта
        self._rotation_tick = 0
        self._rotation_stopping = False
        # Показываем начальный кадр
        self._set_icon_idle()
        
    def _rotate_icon(self):
        """Вращает иконку с плавным стартом и завершением"""
        self._rotation_tick += 1

        if self._rotation_stopping:
            # Режим завершения: замедляемся и доворачиваем до 360°
            self._rotation_speed = max(0.3, self._rotation_speed * 0.96)  # Плавное замедление (60fps)
            self._rotation_angle += self._rotation_speed

            # Проверяем, близко ли к полному обороту (360°)
            if self._rotation_angle >= 360:
                # Анимация завершена - останавливаем и показываем статичную иконку
                self._rotation_timer.stop()
                self._rotation_angle = 0.0
                self._set_icon_idle()
                return
        else:
            # Режим ускорения: плавный ease-in от 0 до 8°/тик за 90 тиков (~1.5 сек при 60fps)
            if self._rotation_speed < 8.0:
                # Ease-in квадратичный для плавного старта
                progress = min(self._rotation_tick / 90.0, 1.0)
                self._rotation_speed = 8.0 * (progress ** 2)

            self._rotation_angle = (self._rotation_angle + self._rotation_speed) % 360

        # Вращаем через QPainter (не через QPixmap.transformed - тот меняет размер)
        from PyQt6.QtGui import QPixmap, QPainter

        base_pixmap = qta.icon('fa5s.sync-alt', color='#60cdff').pixmap(48, 48)

        # Создаём целевой pixmap 64x64
        final = QPixmap(64, 64)
        final.fill(Qt.GlobalColor.transparent)

        painter = QPainter(final)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Перемещаем центр координат в центр pixmap, вращаем, рисуем
        painter.translate(32, 32)
        painter.rotate(self._rotation_angle)  # По часовой стрелке
        painter.drawPixmap(-24, -24, base_pixmap)
        painter.end()

        self.icon_label.setPixmap(final)
        
    def _on_check_clicked(self):
        self.check_clicked.emit()
        
    def start_checking(self):
        """Начинает состояние проверки"""
        self._is_checking = True
        self.check_btn.setEnabled(False)
        self.title_label.setText("Проверка обновлений...")
        self.subtitle_label.setText("Подождите, идёт проверка серверов")
        self.progress_bar.start_indeterminate()
        
        # Сначала сбрасываем параметры анимации, потом запускаем таймер
        self._set_icon_checking()
        self._rotation_timer.start(16)  # 16мс = 60 FPS 🔥
        
    def stop_checking(self, found_update: bool = False, version: str = ""):
        """Завершает состояние проверки"""
        self._is_checking = False
        self.check_btn.setEnabled(True)
        self.progress_bar.stop()
        
        # Запускаем плавное завершение анимации (довернуть до 360°)
        if self._rotation_timer.isActive():
            self._rotation_stopping = True
            # Таймер сам остановится когда дойдёт до 360°
        else:
            self._set_icon_idle()
        
        if found_update:
            self.title_label.setText(f"Доступно обновление v{version}")
            self.subtitle_label.setText("Установите обновление ниже или проверьте ещё раз")
        else:
            self.title_label.setText("Обновлений нет")
            self.subtitle_label.setText(f"Установлена последняя версия {APP_VERSION}")
        
        # Кнопка всегда видна для повторной проверки
        self.check_btn.setText("ПРОВЕРИТЬ СНОВА")
        self.check_btn.show()
        self.check_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #ffffff;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.04);
            }
        """)
            
    def set_error(self, message: str):
        """Показывает ошибку"""
        self._is_checking = False
        self.check_btn.setEnabled(True)
        self.progress_bar.stop()
        self._rotation_timer.stop()
        
        from PyQt6.QtGui import QPixmap, QPainter
        base = qta.icon('fa5s.exclamation-triangle', color='#e74c3c').pixmap(48, 48)
        final = QPixmap(64, 64)
        final.fill(Qt.GlobalColor.transparent)
        painter = QPainter(final)
        painter.drawPixmap(8, 8, base)
        painter.end()
        self.icon_label.setPixmap(final)
        
        self.title_label.setText("Ошибка проверки")
        self.subtitle_label.setText(message[:60])
        self.check_btn.setText("Повторить")


# ═══════════════════════════════════════════════════════════════════════════════
# ВОРКЕРЫ
# ═══════════════════════════════════════════════════════════════════════════════

class ServerCheckWorker(QThread):
    """Воркер для проверки статуса серверов"""
    
    server_checked = pyqtSignal(str, dict)
    all_complete = pyqtSignal()
    
    def __init__(self, update_pool_stats: bool = False, telegram_only: bool = False):
        super().__init__()
        self._update_pool_stats = update_pool_stats
        self._telegram_only = telegram_only  # Если True - проверяем только Telegram
        self._first_online_server_id = None
    
    def run(self):
        from updater.github_release import check_rate_limit
        from updater.server_pool import get_server_pool
        import requests
        import time as _time

        pool = get_server_pool()
        self._first_online_server_id = None
        
        # 1. Telegram Bot (основной источник) — опрашиваем только текущий канал
        try:
            from updater.telegram_updater import is_telegram_available, get_telegram_version_info
            
            if is_telegram_available():
                start_time = _time.time()
                tg_channel = 'test' if CHANNEL in ('dev', 'test') else 'stable'
                tg_info = get_telegram_version_info(tg_channel)
                response_time = _time.time() - start_time
                
                stable_version = tg_info.get('version') if tg_channel == 'stable' and tg_info else '—'
                test_version = tg_info.get('version') if tg_channel == 'test' and tg_info else '—'
                
                if tg_info and tg_info.get('version'):
                    tg_status = {
                        'status': 'online',
                        'response_time': response_time,
                        'stable_version': stable_version,
                        'test_version': test_version,
                        'is_current': True,
                    }
                    self._first_online_server_id = 'telegram'

                    # ✅ Сохраняем версию от Telegram в кэш all_versions
                    # чтобы VersionCheckWorker использовал её для сравнения
                    from updater.update_cache import set_cached_all_versions, get_cached_all_versions
                    all_versions = get_cached_all_versions() or {}
                    all_versions[tg_channel] = {
                        'version': tg_info['version'],
                        'release_notes': tg_info.get('release_notes', ''),
                    }
                    set_cached_all_versions(all_versions, f"Telegram @{TELEGRAM_CHANNELS.get(tg_channel, tg_channel)}")
                else:
                    tg_status = {
                        'status': 'error',
                        'response_time': response_time,
                        'error': 'Версия не найдена',
                        'is_current': False,
                    }
            else:
                tg_status = {
                    'status': 'offline',
                    'response_time': 0,
                    'error': 'Бот не настроен',
                    'is_current': False,
                }
            
            self.server_checked.emit('Telegram Bot', tg_status)
            _time.sleep(0.1)
        except Exception as e:
            self.server_checked.emit('Telegram Bot', {
                'status': 'error',
                'error': str(e)[:40],
                'is_current': False,
            })
        
        # Если режим telegram_only - пропускаем VPS и GitHub
        if self._telegram_only:
            self.all_complete.emit()
            return
        
        # 2. VPS серверы
        for server in pool.servers:
            server_id = server['id']
            server_name = f"{server['name']}"
            
            stats = pool.stats.get(server_id, {})
            blocked_until = stats.get('blocked_until')
            current_time = _time.time()
            
            if blocked_until and current_time < blocked_until:
                until_dt = datetime.fromtimestamp(blocked_until)
                status = {
                    'status': 'blocked',
                    'response_time': 0,
                    'error': f"Заблокирован до {until_dt.strftime('%H:%M:%S')}",
                    'is_current': False,  # Заблокированный не может быть активным
                }
                self.server_checked.emit(server_name, status)
                _time.sleep(0.1)
                continue
            
            start_time = _time.time()
            try:
                https_url = f"https://{server['host']}:{server['https_port']}/api/all_versions.json"
                
                from updater.server_config import should_verify_ssl
                verify_ssl = should_verify_ssl()
                
                if not verify_ssl:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                response = requests.get(https_url, timeout=10, verify=verify_ssl,
                    headers={"Accept": "application/json", "User-Agent": "Zapret-Updater/3.1"})
                
                response_time = _time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Первый работающий сервер становится активным
                    is_first_online = self._first_online_server_id is None
                    if is_first_online:
                        self._first_online_server_id = server_id
                    
                    status = {
                        'status': 'online',
                        'response_time': response_time,
                        'stable_version': data.get('stable', {}).get('version', '—'),
                        'test_version': data.get('test', {}).get('version', '—'),
                        'is_current': is_first_online,  # Звёздочка первому работающему
                    }
                    
                    from updater.update_cache import set_cached_all_versions
                    set_cached_all_versions(data, f"{server_name} (HTTPS)")
                    
                    if self._update_pool_stats:
                        pool.record_success(server_id, response_time)
                else:
                    status = {
                        'status': 'error',
                        'response_time': response_time,
                        'error': f'HTTP {response.status_code}',
                        'is_current': False,  # Ошибка - не активный
                    }
                    if self._update_pool_stats:
                        pool.record_failure(server_id, f"HTTP {response.status_code}")
                    
            except Exception as e:
                status = {
                    'status': 'error',
                    'response_time': _time.time() - start_time,
                    'error': str(e)[:40],
                    'is_current': False,  # Ошибка - не активный
                }
                if self._update_pool_stats:
                    pool.record_failure(server_id, str(e)[:40])
            
            self.server_checked.emit(server_name, status)
            _time.sleep(0.15)
        
        # 3. GitHub API
        try:
            rate_info = check_rate_limit()
            github_status = {
                'status': 'online',
                'response_time': 0.5,
                'rate_limit': rate_info['remaining'],
                'rate_limit_max': rate_info['limit'],
            }
        except Exception as e:
            github_status = {
                'status': 'error',
                'error': str(e)[:50],
            }
        
        self.server_checked.emit('GitHub API', github_status)
        self.all_complete.emit()


class VersionCheckWorker(QThread):
    """Воркер для получения версий"""
    
    version_found = pyqtSignal(str, dict)
    complete = pyqtSignal()
    
    def run(self):
        from updater.update_cache import get_cached_all_versions, get_all_versions_source, set_cached_all_versions
        from updater.github_release import normalize_version
        
        all_versions = get_cached_all_versions()
        source_name = get_all_versions_source() if all_versions else None
        
        if not all_versions:
            import requests
            from updater.server_pool import get_server_pool
            from updater.server_config import should_verify_ssl, CONNECT_TIMEOUT, READ_TIMEOUT
            
            pool = get_server_pool()
            current_server = pool.get_current_server()
            server_urls = pool.get_server_urls(current_server)
            
            for protocol, base_url in [('HTTPS', server_urls['https']), ('HTTP', server_urls['http'])]:
                try:
                    verify_ssl = should_verify_ssl() if protocol == 'HTTPS' else False
                    if not verify_ssl:
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    response = requests.get(f"{base_url}/api/all_versions.json",
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), verify=verify_ssl,
                        headers={"Accept": "application/json", "User-Agent": "Zapret-Updater/3.1"})
                    
                    if response.status_code == 200:
                        all_versions = response.json()
                        source_name = f"{current_server['name']} ({protocol})"
                        set_cached_all_versions(all_versions, source_name)
                        break
                except:
                    continue
        
        if not all_versions:
            from updater.release_manager import get_latest_release
            for channel in ['stable', 'dev']:
                try:
                    # use_cache=False чтобы получить актуальные данные
                    release = get_latest_release(channel, use_cache=False)
                    if release:
                        self.version_found.emit(channel, release)
                    else:
                        self.version_found.emit(channel, {'error': 'Не удалось получить'})
                except Exception as e:
                    self.version_found.emit(channel, {'error': str(e)})
            self.complete.emit()
            return
        
        channel_mapping = {'stable': 'stable', 'dev': 'test'}
        
        for ui_channel, api_channel in channel_mapping.items():
            data = all_versions.get(api_channel, {})
            if data and data.get('version'):
                result = {
                    'version': normalize_version(data.get('version', '0.0.0')),
                    'release_notes': data.get('release_notes', ''),
                    'source': source_name,
                }
                self.version_found.emit(ui_channel, result)
            else:
                self.version_found.emit(ui_channel, {'error': 'Нет данных'})
        
        self.complete.emit()


# ═══════════════════════════════════════════════════════════════════════════════
# КАРТОЧКА CHANGELOG (для отображения информации об обновлении)
# ═══════════════════════════════════════════════════════════════════════════════

class ChangelogCard(QFrame):
    """Карточка с changelog обновления и встроенным прогрессом скачивания"""
    
    install_clicked = pyqtSignal()
    dismiss_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("changelogCard")
        self._is_downloading = False
        self._download_start_time = 0
        self._last_bytes = 0
        self._speed_update_timer = QTimer(self)
        self._speed_update_timer.timeout.connect(self._update_speed)
        self._build_ui()
        self.hide()
        
    def _build_ui(self):
        self.setStyleSheet("""
            QFrame#changelogCard {
                background: rgba(96, 205, 255, 0.08);
                border: 1px solid rgba(96, 205, 255, 0.2);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Заголовок
        header = QHBoxLayout()
        
        self.icon_label = QLabel()
        icon = qta.icon('fa5s.arrow-circle-up', color='#60cdff')
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        header.addWidget(self.icon_label)
        
        self.title_label = QLabel("Доступно обновление")
        self.title_label.setStyleSheet("color: #60cdff; font-size: 14px; font-weight: 600;")
        header.addWidget(self.title_label)
        header.addStretch()
        
        # Кнопка закрытия (скрывается при скачивании)
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._on_dismiss)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
        """)
        close_icon = qta.icon('fa5s.times', color='rgba(255,255,255,0.5)')
        self.close_btn.setIcon(close_icon)
        header.addWidget(self.close_btn)
        
        layout.addLayout(header)
        
        # Версия / Статус
        self.version_label = QLabel()
        self.version_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px;")
        layout.addWidget(self.version_label)
        
        # Changelog текст (с кликабельными ссылками)
        self.changelog_text = QLabel()
        self.changelog_text.setWordWrap(True)
        self.changelog_text.setTextFormat(Qt.TextFormat.RichText)
        self.changelog_text.setOpenExternalLinks(True)  # Автооткрытие ссылок в браузере
        self.changelog_text.setStyleSheet("""
            color: rgba(255,255,255,0.6); 
            font-size: 12px; 
            padding: 4px 0;
        """)
        self.changelog_text.linkActivated.connect(lambda url: __import__('webbrowser').open(url))
        layout.addWidget(self.changelog_text)
        
        # ═══════════════════════════════════════════════════════════
        # Секция прогресса (скрыта по умолчанию)
        # ═══════════════════════════════════════════════════════════
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 4)
        progress_layout.setSpacing(6)
        
        # Progress bar
        self.progress_bar = Win11ProgressBar()
        self.progress_bar.setFixedHeight(4)
        progress_layout.addWidget(self.progress_bar)
        
        # Статус строка: скорость | прогресс | осталось
        status_row = QHBoxLayout()
        status_row.setSpacing(16)
        
        self.speed_label = QLabel("Скорость: —")
        self.speed_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        status_row.addWidget(self.speed_label)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")
        status_row.addWidget(self.progress_label)
        
        self.eta_label = QLabel("Осталось: —")
        self.eta_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        status_row.addWidget(self.eta_label)
        
        status_row.addStretch()
        progress_layout.addLayout(status_row)
        
        self.progress_widget.hide()
        layout.addWidget(self.progress_widget)
        
        # ═══════════════════════════════════════════════════════════
        # Кнопки
        # ═══════════════════════════════════════════════════════════
        self.buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()
        
        self.later_btn = QPushButton("Позже")
        self.later_btn.setFixedHeight(32)
        self.later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later_btn.clicked.connect(self._on_dismiss)
        self.later_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: rgba(255, 255, 255, 0.8);
                padding: 0 20px;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
        """)
        buttons_layout.addWidget(self.later_btn)
        
        self.install_btn = QPushButton("  Установить")
        self.install_btn.setFixedHeight(32)
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.clicked.connect(self._on_install)
        # Иконка download (белая)
        download_icon = qta.icon('fa5s.download', color='#ffffff')
        self.install_btn.setIcon(download_icon)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                padding: 0 16px 0 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #45a049; }
        """)
        buttons_layout.addWidget(self.install_btn)
        
        layout.addWidget(self.buttons_widget)
        
    def _make_links_clickable(self, text: str) -> str:
        """Преобразует URL в кликабельные HTML ссылки"""
        import re
        # Regex для поиска URL
        url_pattern = r'(https?://[^\s<>"\']+)'
        
        def replace_url(match):
            url = match.group(1)
            # Убираем trailing punctuation
            while url and url[-1] in '.,;:!?)':
                url = url[:-1]
            return f'<a href="{url}" style="color: #60cdff;">{url}</a>'
        
        return re.sub(url_pattern, replace_url, text)
    
    def show_update(self, version: str, changelog: str):
        """Показывает информацию об обновлении"""
        self._is_downloading = False
        self.version_label.setText(f"v{APP_VERSION}  →  v{version}")
        self.title_label.setText("Доступно обновление")
        
        icon = qta.icon('fa5s.arrow-circle-up', color='#60cdff')
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        
        if changelog:
            if len(changelog) > 200:
                changelog = changelog[:200] + "..."
            # Делаем ссылки кликабельными
            changelog_html = self._make_links_clickable(changelog)
            self.changelog_text.setText(changelog_html)
            self.changelog_text.show()
        else:
            self.changelog_text.hide()
        
        self.progress_widget.hide()
        self.buttons_widget.show()
        self.close_btn.show()
        self.show()
        
    def start_download(self, version: str):
        """Переключает в режим скачивания"""
        self._is_downloading = True
        self._download_start_time = time.time()
        self._last_bytes = 0
        
        self.title_label.setText(f"Загрузка v{version}")
        icon = qta.icon('fa5s.download', color='#60cdff')
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        
        self.version_label.setText("Подготовка к загрузке...")
        self.changelog_text.hide()
        self.buttons_widget.hide()
        self.close_btn.hide()
        
        self.progress_bar.set_progress(0)
        self.progress_label.setText("0%")
        self.speed_label.setText("Скорость: —")
        self.eta_label.setText("Осталось: —")
        self.progress_widget.show()
        
        self._speed_update_timer.start(500)
        
    def update_progress(self, percent: int, done_bytes: int, total_bytes: int):
        """Обновляет прогресс скачивания"""
        self.progress_bar.set_progress(percent / 100.0)
        self.progress_label.setText(f"{percent}%")
        
        # Размер
        done_mb = done_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        self.version_label.setText(f"Загружено {done_mb:.1f} / {total_mb:.1f} МБ")
        
        # Скорость и ETA
        elapsed = time.time() - self._download_start_time
        if elapsed > 0.5 and done_bytes > 0:
            speed = done_bytes / elapsed
            speed_kb = speed / 1024
            
            if speed_kb > 1024:
                self.speed_label.setText(f"Скорость: {speed_kb/1024:.1f} МБ/с")
            else:
                self.speed_label.setText(f"Скорость: {speed_kb:.0f} КБ/с")
            
            if speed > 0:
                remaining = (total_bytes - done_bytes) / speed
                if remaining < 60:
                    self.eta_label.setText(f"Осталось: {int(remaining)} сек")
                else:
                    self.eta_label.setText(f"Осталось: {int(remaining/60)} мин")
        
        self._last_bytes = done_bytes
        
    def download_complete(self):
        """Скачивание завершено"""
        self._speed_update_timer.stop()
        self.title_label.setText("Установка...")
        self.version_label.setText("Запуск установщика, приложение закроется")
        self.progress_bar.set_progress(1.0)
        self.progress_label.setText("100%")
        self.speed_label.setText("")
        self.eta_label.setText("")
        
    def download_failed(self, error: str):
        """Ошибка скачивания"""
        self._speed_update_timer.stop()
        self._is_downloading = False
        
        self.title_label.setText("Ошибка загрузки")
        self.title_label.setStyleSheet("color: #ff6b6b; font-size: 14px; font-weight: 600;")
        icon = qta.icon('fa5s.exclamation-triangle', color='#ff6b6b')
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        
        self.version_label.setText(error[:80] if len(error) > 80 else error)
        self.progress_widget.hide()
        self.buttons_widget.show()
        self.close_btn.show()
        self.install_btn.setText("Повторить")
        
    def _update_speed(self):
        """Периодическое обновление (для анимации)"""
        pass
        
    def _on_install(self):
        self.install_clicked.emit()
        
    def _on_dismiss(self):
        self.hide()
        self.dismiss_clicked.emit()


# ═══════════════════════════════════════════════════════════════════════════════
# ОСНОВНАЯ СТРАНИЦА
# ═══════════════════════════════════════════════════════════════════════════════

class ServersPage(BasePage):
    """Страница мониторинга серверов обновлений"""
    
    update_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Серверы", "Мониторинг серверов обновлений", parent)
        
        self.server_worker = None
        self.version_worker = None
        self._checking = False
        self._found_update = False
        self._remote_version = ""
        self._release_notes = ""

        # Cooldown только для автопроверки при открытии вкладки (не спамить)
        self._last_check_time = 0.0
        self._check_cooldown = 60  # секунд между автопроверками (было 10)

        # Автопроверка при открытии вкладки
        self._auto_check_enabled = True

        # Кэш результатов проверки (не очищать таблицу при повторном открытии)
        self._has_cached_data = False

        self._build_ui()
        
    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # Карточка обновлений (стиль Windows Update)
        # ═══════════════════════════════════════════════════════════
        self.update_card = UpdateStatusCard()
        self.update_card.check_clicked.connect(self._check_updates)
        self.add_widget(self.update_card)
        
        # ═══════════════════════════════════════════════════════════
        # Карточка Changelog (скрыта по умолчанию)
        # ═══════════════════════════════════════════════════════════
        self.changelog_card = ChangelogCard()
        self.changelog_card.install_clicked.connect(self._install_update)
        self.changelog_card.dismiss_clicked.connect(self._dismiss_update)
        self.add_widget(self.changelog_card)
        
        # ═══════════════════════════════════════════════════════════
        # Заголовок таблицы
        # ═══════════════════════════════════════════════════════════
        servers_header = QHBoxLayout()
        servers_title = QLabel("Серверы обновлений")
        servers_title.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px; font-weight: 600;")
        servers_header.addWidget(servers_title)
        servers_header.addStretch()
        
        legend_active = QLabel("⭐ активный")
        legend_active.setStyleSheet("color: rgba(96, 205, 255, 0.5); font-size: 10px;")
        servers_header.addWidget(legend_active)
        
        header_widget = QWidget()
        header_widget.setLayout(servers_header)
        self.add_widget(header_widget)
        
        # ═══════════════════════════════════════════════════════════
        # Таблица серверов (растягивается на всё пространство)
        # ═══════════════════════════════════════════════════════════
        self.servers_table = QTableWidget(0, 4)
        self.servers_table.setHorizontalHeaderLabels(["Сервер", "Статус", "Время", "Версии"])
        header = self.servers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.servers_table.verticalHeader().setVisible(False)
        self.servers_table.verticalHeader().setDefaultSectionSize(36)
        self.servers_table.setAlternatingRowColors(True)
        self.servers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.servers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.servers_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 6px;
                gridline-color: rgba(255,255,255,0.03);
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background-color: rgba(96, 205, 255, 0.12); }
            QHeaderView::section {
                background-color: rgba(255,255,255,0.03);
                color: rgba(255,255,255,0.6);
                padding: 8px;
                border: none;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        self.add_widget(self.servers_table, stretch=1)  # stretch=1 для заполнения пространства
        
        # ═══════════════════════════════════════════════════════════
        # Настройки (toggle автопроверки при открытии вкладки)
        # ═══════════════════════════════════════════════════════════
        settings_card = SettingsCard("Настройки")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(12)
        
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(12)
        
        # Toggle switch
        self.auto_check_toggle = Win11ToggleSwitch()
        self.auto_check_toggle.setChecked(True)  # По умолчанию включено
        self.auto_check_toggle.toggled.connect(self._on_auto_check_toggled)
        toggle_row.addWidget(self.auto_check_toggle)
        
        toggle_label = QLabel("Проверять обновления при открытии вкладки")
        toggle_label.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 13px;")
        toggle_row.addWidget(toggle_label)
        
        toggle_row.addStretch()
        
        version_info = QLabel(f"v{APP_VERSION} · {CHANNEL}")
        version_info.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 11px;")
        toggle_row.addWidget(version_info)
        
        settings_layout.addLayout(toggle_row)
        settings_card.add_layout(settings_layout)
        self.add_widget(settings_card)

        # ═══════════════════════════════════════════════════════════
        # Карточка с информацией о Telegram канале
        # ═══════════════════════════════════════════════════════════
        tg_card = SettingsCard("Проблемы с обновлением?")
        tg_layout = QVBoxLayout()
        tg_layout.setSpacing(12)

        # Текст с информацией
        info_label = QLabel(
            "Если возникают трудности с автоматическим обновлением, "
            "все версии программы выкладываются в Telegram канале."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px;")
        tg_layout.addWidget(info_label)

        # Кнопка открытия Telegram канала
        tg_btn_row = QHBoxLayout()

        tg_btn = QPushButton("  Открыть Telegram канал")
        tg_btn.setFixedHeight(36)
        tg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tg_btn.setIcon(qta.icon('fa5b.telegram-plane', color='#ffffff'))
        tg_btn.clicked.connect(self._open_telegram_channel)
        tg_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0088cc, stop:1 #00aaee);
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0099dd, stop:1 #00bbff);
            }
            QPushButton:pressed {
                background: #0077bb;
            }
        """)
        tg_btn_row.addWidget(tg_btn)
        tg_btn_row.addStretch()

        tg_layout.addLayout(tg_btn_row)
        tg_card.add_layout(tg_layout)
        self.add_widget(tg_card)
        
    def showEvent(self, event):
        super().showEvent(event)

        # Не запускаем проверку если идёт скачивание
        if self.changelog_card._is_downloading:
            return

        # Если есть кэшированные данные и cooldown не прошёл - не перезапускаем
        elapsed = time.time() - self._last_check_time
        if self._has_cached_data and elapsed < self._check_cooldown:
            # Показываем когда была последняя проверка
            mins_ago = int(elapsed // 60)
            secs_ago = int(elapsed % 60)
            if mins_ago > 0:
                self.update_card.subtitle_label.setText(f"Проверено {mins_ago}м {secs_ago}с назад")
            else:
                self.update_card.subtitle_label.setText(f"Проверено {secs_ago}с назад")
            return

        # Автопроверка при открытии страницы (если включена)
        if self._auto_check_enabled:
            if elapsed >= self._check_cooldown:
                QTimer.singleShot(200, self.start_checks)
        else:
            # Показываем что нужно нажать кнопку вручную
            self.update_card.subtitle_label.setText("Нажмите кнопку для проверки")
        
    def start_checks(self, telegram_only: bool = False):
        """Запускает проверку серверов
        
        Args:
            telegram_only: True = только Telegram (быстрая проверка), False = все серверы
        """
        if self._checking:
            return
        
        # Не запускаем проверку если идёт скачивание
        if self.changelog_card._is_downloading:
            log("⏭️ Пропуск проверки - идёт скачивание обновления", "🔄 UPDATE")
            return
        
        # Обновляем время последней проверки только при полной проверке
        if not telegram_only:
            self._last_check_time = time.time()
        
        self._checking = True
        self._found_update = False
        self.update_card.start_checking()
        self.servers_table.setRowCount(0)
        
        if self.server_worker and self.server_worker.isRunning():
            self.server_worker.terminate()
            self.server_worker.wait(500)  # Короткий таймаут после terminate

        if self.version_worker and self.version_worker.isRunning():
            self.version_worker.terminate()
            self.version_worker.wait(500)  # Короткий таймаут после terminate
        
        self.server_worker = ServerCheckWorker(update_pool_stats=False, telegram_only=telegram_only)
        self.server_worker.server_checked.connect(self._on_server_checked)
        self.server_worker.all_complete.connect(self._on_servers_complete)
        self.server_worker.start()
        
    def _on_server_checked(self, server_name: str, status: dict):
        row = self.servers_table.rowCount()
        self.servers_table.insertRow(row)
        
        name_item = QTableWidgetItem(server_name)
        if status.get('is_current'):
            name_item.setText(f"⭐ {server_name}")
            name_item.setForeground(QColor(96, 205, 255))
        self.servers_table.setItem(row, 0, name_item)
        
        status_item = QTableWidgetItem()
        if status.get('status') == 'online':
            status_item.setText("● Онлайн")
            status_item.setForeground(QColor(134, 194, 132))  # Пастельный зелёный
        elif status.get('status') == 'blocked':
            status_item.setText("● Блок")
            status_item.setForeground(QColor(230, 180, 100))  # Пастельный жёлтый
        else:
            status_item.setText("● Офлайн")
            status_item.setForeground(QColor(220, 130, 130))  # Пастельный красный
        self.servers_table.setItem(row, 1, status_item)
        
        time_text = f"{status.get('response_time', 0)*1000:.0f}мс" if status.get('response_time') else "—"
        self.servers_table.setItem(row, 2, QTableWidgetItem(time_text))
        
        if server_name == 'Telegram Bot':
            if status.get('status') == 'online':
                # Показываем версию текущего канала (T для dev/test, S для stable)
                if CHANNEL in ('dev', 'test'):
                    extra = f"T: {status.get('test_version', '—')}"
                else:
                    extra = f"S: {status.get('stable_version', '—')}"
            else:
                extra = status.get('error', '')[:40]
        elif server_name == 'GitHub API':
            if status.get('rate_limit') is not None:
                extra = f"Лимит: {status['rate_limit']}/{status.get('rate_limit_max', 60)}"
            else:
                extra = status.get('error', '')[:40]
        elif status.get('status') == 'online':
            extra = f"S: {status.get('stable_version', '—')}, T: {status.get('test_version', '—')}"
        else:
            extra = status.get('error', '')[:40]
        
        self.servers_table.setItem(row, 3, QTableWidgetItem(extra))
        
    def _on_servers_complete(self):
        """После проверки серверов запускаем проверку версий (кэш уже заполнен)"""
        if self.version_worker and self.version_worker.isRunning():
            self.version_worker.terminate()
            self.version_worker.wait(500)  # Короткий таймаут после terminate
        
        self.version_worker = VersionCheckWorker()
        self.version_worker.version_found.connect(self._on_version_found)
        self.version_worker.complete.connect(self._on_versions_complete)
        self.version_worker.start()
        
    def _on_version_found(self, channel: str, version_info: dict):
        if channel == 'stable' or (channel == 'dev' and CHANNEL in ('dev', 'test')):
            target_channel = 'dev' if CHANNEL in ('dev', 'test') else 'stable'
            if channel == target_channel and not version_info.get('error'):
                version = version_info.get('version', '')
                from updater.update import compare_versions
                try:
                    if compare_versions(APP_VERSION, version) < 0:
                        self._found_update = True
                        self._remote_version = version
                        self._release_notes = version_info.get('release_notes', '')
                except:
                    pass
                
    def _on_versions_complete(self):
        self._checking = False
        self._has_cached_data = True  # Данные закэшированы
        self.update_card.stop_checking(self._found_update, self._remote_version)

        # Автоматически показываем changelog если есть обновление
        if self._found_update:
            self.changelog_card.show_update(self._remote_version, self._release_notes)
        
    def _check_updates(self):
        """Запускает новую проверку обновлений (кнопка всегда доступна)"""
        # Не запускаем проверку если идёт скачивание
        if self.changelog_card._is_downloading:
            return
        
        # Скрываем старую карточку changelog если показана
        self.changelog_card.hide()
        
        # Сбрасываем состояние найденного обновления
        self._found_update = False
        self._remote_version = ""
        self._release_notes = ""
        
        # Определяем режим проверки:
        # - В течение 60 сек после последней проверки - только Telegram (быстро)
        # - После 60 сек - полная проверка всех серверов
        current_time = time.time()
        elapsed = current_time - self._last_check_time
        telegram_only = elapsed < self._check_cooldown

        if telegram_only:
            log(f"🔄 Быстрая проверка через Telegram ({int(elapsed)}с с последней)", "🔄 UPDATE")
        else:
            # Инвалидируем кэш только при полной проверке
            from updater import invalidate_cache
            invalidate_cache(CHANNEL)
            log("🔄 Полная проверка всех серверов", "🔄 UPDATE")
        
        # Запускаем проверку
        self.start_checks(telegram_only=telegram_only)
    
    
    def _install_update(self):
        """Запускает установку обновления со встроенным прогрессом"""
        log(f"Запуск установки обновления v{self._remote_version}", "🔄 UPDATE")
        
        # Инвалидируем кэш чтобы получить свежую информацию
        from updater import invalidate_cache
        invalidate_cache(CHANNEL)
        
        # Показываем прогресс в карточке
        self.changelog_card.start_download(self._remote_version)
        
        try:
            from updater.update import UpdateWorker
            from PyQt6.QtCore import QThread
            
            parent_window = self.window()
            
            # Создаём worker напрямую
            # silent=True - пропустить диалог подтверждения
            # skip_rate_limit=True - пропустить rate limiter (пользователь уже подтвердил)
            self._update_thread = QThread(parent_window)
            self._update_worker = UpdateWorker(parent_window, silent=True, skip_rate_limit=True)
            self._update_worker.moveToThread(self._update_thread)
            
            self._update_thread.started.connect(self._update_worker.run)
            self._update_worker.finished.connect(self._update_thread.quit)
            self._update_worker.finished.connect(self._update_worker.deleteLater)
            self._update_thread.finished.connect(self._update_thread.deleteLater)
            
            # Подключаем сигналы к нашей карточке
            self._update_worker.progress_bytes.connect(
                lambda p, d, t: self.changelog_card.update_progress(p, d, t)
            )
            self._update_worker.download_complete.connect(
                self.changelog_card.download_complete
            )
            self._update_worker.download_failed.connect(
                self.changelog_card.download_failed
            )
            self._update_worker.download_failed.connect(
                self._on_download_failed
            )
            self._update_worker.progress.connect(
                lambda m: log(f'{m}', "🔁 UPDATE")
            )
            
            # НЕ показываем DownloadDialog - игнорируем сигнал show_download_dialog
            
            self._update_thread.start()
            
        except Exception as e:
            log(f"Ошибка при запуске обновления: {e}", "❌ ERROR")
            self.changelog_card.download_failed(str(e)[:50])
    
    def _on_download_failed(self, error: str):
        """При ошибке загрузки показываем кнопку проверки"""
        self.update_card.title_label.setText("Ошибка загрузки")
        self.update_card.subtitle_label.setText("Попробуйте снова")
        self.update_card.check_btn.setText("ПРОВЕРИТЬ СНОВА")
        self.update_card.check_btn.show()
        self._apply_default_btn_style()
    
    def _dismiss_update(self):
        """Скрывает карточку обновления и показывает кнопку проверки"""
        log("Обновление отложено пользователем", "🔄 UPDATE")
        
        # Показываем кнопку проверки снова
        self.update_card.title_label.setText(f"Обновление v{self._remote_version} отложено")
        self.update_card.subtitle_label.setText("Нажмите для повторной проверки")
        self.update_card.check_btn.setText("ПРОВЕРИТЬ СНОВА")
        self.update_card.check_btn.show()
        self._apply_default_btn_style()
    
    def _apply_default_btn_style(self):
        """Применяет стандартный стиль к кнопке проверки (с поддержкой disabled)"""
        self.update_card.check_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #ffffff;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover:enabled {
                background: rgba(255, 255, 255, 0.1);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.02);
                border-color: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.25);
            }
        """)
            
    def _open_telegram_channel(self):
        """Открывает Telegram канал с релизами"""
        open_telegram_link("zapretnetdiscordyoutube")

    def _on_auto_check_toggled(self, enabled: bool):
        """Обработчик toggle автопроверки"""
        self._auto_check_enabled = enabled
        
        # Меняем текст кнопки
        if enabled:
            self.update_card.check_btn.setText("ПРОВЕРИТЬ СНОВА")
            self.update_card.subtitle_label.setText("Автопроверка включена")
        else:
            self.update_card.check_btn.setText("ПРОВЕРИТЬ ВРУЧНУЮ")
            self.update_card.subtitle_label.setText("Нажмите кнопку для проверки")
        
        log(f"Автопроверка при открытии вкладки: {'включена' if enabled else 'отключена'}", "🔄 UPDATE")
            
    def cleanup(self):
        """Очистка потоков при закрытии"""
        try:
            if self.server_worker and self.server_worker.isRunning():
                log("Останавливаем server_worker...", "DEBUG")
                self.server_worker.quit()
                if not self.server_worker.wait(2000):
                    log("⚠ server_worker не завершился, принудительно завершаем", "WARNING")
                    self.server_worker.terminate()
                    self.server_worker.wait(500)
            
            if self.version_worker and self.version_worker.isRunning():
                log("Останавливаем version_worker...", "DEBUG")
                self.version_worker.quit()
                if not self.version_worker.wait(2000):
                    log("⚠ version_worker не завершился, принудительно завершаем", "WARNING")
                    self.version_worker.terminate()
                    self.version_worker.wait(500)
        except Exception as e:
            log(f"Ошибка при очистке servers_page: {e}", "DEBUG")
