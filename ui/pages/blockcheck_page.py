from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation, pyqtProperty, QPointF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient


class AnimatedConstructionScene(QWidget):
    """Элегантная анимация с пульсирующими кольцами и частицами."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._phase = 0.0
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)
        
        # Частицы
        import random
        self._particles = []
        for _ in range(12):
            self._particles.append({
                "angle": random.uniform(0, 360),
                "radius": random.uniform(0.3, 0.8),
                "speed": random.uniform(0.3, 0.8),
                "size": random.uniform(3, 6)
            })

    def _tick(self):
        self._phase = (self._phase + 0.015) % 1.0
        for p in self._particles:
            p["angle"] = (p["angle"] + p["speed"]) % 360
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(32, 16, -32, -16)  # Расширенный фон
        cx, cy = rect.center().x(), rect.center().y()
        max_radius = min(rect.width(), rect.height()) / 2 - 20

        # Фон
        bg = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        bg.setColorAt(0, QColor(28, 28, 30, 250))
        bg.setColorAt(1, QColor(18, 18, 20, 250))
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(rect, 16, 16)

        # Пульсирующие кольца
        for i in range(3):
            ring_phase = (self._phase + i * 0.33) % 1.0
            radius = max_radius * ring_phase
            alpha = int(80 * (1 - ring_phase))
            
            painter.setPen(QPen(QColor(96, 205, 255, alpha), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        # Центральный круг
        center_pulse = 0.8 + 0.2 * math.sin(self._phase * math.pi * 2)
        center_size = int(24 * center_pulse)
        gradient = QLinearGradient(cx - center_size, cy - center_size, cx + center_size, cy + center_size)
        gradient.setColorAt(0, QColor(96, 205, 255, 180))
        gradient.setColorAt(1, QColor(60, 180, 255, 120))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - center_size), int(cy - center_size), center_size * 2, center_size * 2)

        # Частицы вокруг
        for p in self._particles:
            angle_rad = math.radians(p["angle"])
            r = max_radius * p["radius"]
            px = cx + r * math.cos(angle_rad)
            py = cy + r * math.sin(angle_rad)
            size = int(p["size"])
            
            alpha = int(120 + 60 * math.sin(self._phase * math.pi * 4 + p["angle"]))
            painter.setBrush(QColor(96, 205, 255, alpha))
            painter.drawEllipse(int(px - size/2), int(py - size/2), size, size)

        # Текст - выше центра
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Segoe UI Variable", 12, QFont.Weight.Medium)
        painter.setFont(font)
        text_rect = rect.adjusted(0, 0, 0, -30)  # Поднимаем текст
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, "Разрабатывается…")




class BlockcheckPage(QWidget):
    """Вкладка Blockcheck с тизером."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BlockcheckPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("Blockcheck")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 32px;
                font-weight: 800;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }
        """)
        layout.addWidget(title)

        subtitle = QLabel("Автоматический анализ блокировок и диагностика сети в один клик")
        subtitle.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 16px;
            }
        """)
        layout.addWidget(subtitle)

        scene = AnimatedConstructionScene(self)
        layout.addWidget(scene)

        # Блок "СКОРО" - по всей ширине
        soon_badge = QLabel("СКОРО")
        soon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soon_badge.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.85);
                font-weight: 600;
                letter-spacing: 3px;
                font-size: 11px;
                padding: 8px 0;
                border-radius: 12px;
                background: rgba(96, 205, 255, 0.10);
            }
        """)
        layout.addWidget(soon_badge)

        soon_text = QLabel(
            "Мониторинг DPI, тестирование операторов и автоматический поиск рабочих стратегий появятся в ближайших обновлениях. "
            "Мы строим Blockcheck, чтобы вы могли увидеть весь путь обхода блокировок в одном окне."
        )
        soon_text.setWordWrap(True)
        soon_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soon_text.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.65);
                font-size: 13px;
            }
        """)
        layout.addWidget(soon_text)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)

        cards = [
            ("🛰", "Живой мониторинг сети",
             "Отслеживайте изменения DPI в реальном времени и получайте подсказки, какие режимы стоит включить."),
            ("🤖", "Авто-поиск стратегий",
             "Blockcheck протестирует десятки профилей и найдёт лучший вариант для вашего провайдера."),
        ]

        for emoji, title_text, body in cards:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.04);
                    border: none;
                    border-radius: 12px;
                }
                QFrame:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 18, 18, 18)
            card_layout.setSpacing(8)

            icon_label = QLabel(emoji)
            icon_label.setStyleSheet("font-size: 22px;")
            card_layout.addWidget(icon_label)

            title_label = QLabel(title_text)
            title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
            card_layout.addWidget(title_label)

            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setStyleSheet("color: rgba(255, 255, 255, 0.68); font-size: 13px;")
            card_layout.addWidget(body_label)

            cards_row.addWidget(card)

        layout.addLayout(cards_row)
        layout.addStretch(1)