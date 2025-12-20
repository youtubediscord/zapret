# ui/pages/orchestra_ratings_page.py
"""Страница истории стратегий с рейтингами (оркестратор)"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QLineEdit, QPushButton
)
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard
from log import log


class OrchestraRatingsPage(BasePage):
    """Страница истории стратегий с рейтингами"""

    def __init__(self, parent=None):
        super().__init__(
            "История стратегий (рейтинги)",
            "Рейтинг = успехи / (успехи + провалы). При UNLOCK выбирается лучшая стратегия из истории.",
            parent
        )
        self.setObjectName("orchestraRatingsPage")
        self._setup_ui()

        # Таймер автообновления
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._refresh_data)

    def _setup_ui(self):
        # === Фильтр ===
        filter_card = SettingsCard("Фильтр")
        filter_layout = QHBoxLayout()

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Поиск по домену...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.filter_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        filter_layout.addWidget(self.filter_input, 1)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.setIcon(qta.icon("mdi.refresh", color="#60cdff"))
        refresh_btn.clicked.connect(self._refresh_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(96, 205, 255, 0.15);
                border: 1px solid rgba(96, 205, 255, 0.3);
                border-radius: 6px;
                color: #60cdff;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(96, 205, 255, 0.25);
            }
        """)
        filter_layout.addWidget(refresh_btn)

        filter_card.add_layout(filter_layout)
        self.layout.addWidget(filter_card)

        # === Статистика ===
        self.stats_label = QLabel("Загрузка...")
        self.stats_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px; margin: 4px 0;")
        self.layout.addWidget(self.stats_label)

        # === История стратегий ===
        history_card = SettingsCard("Рейтинги по доменам")
        history_layout = QVBoxLayout()

        self.history_label = QLabel()
        self.history_label.setWordWrap(False)
        self.history_label.setTextFormat(Qt.TextFormat.PlainText)
        self.history_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: rgba(255,255,255,0.8);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        self.history_label.setText("История стратегий появится после обучения...")
        history_layout.addWidget(self.history_label)

        history_card.add_layout(history_layout)
        self.layout.addWidget(history_card)

        # Хранилище данных для фильтрации
        self._full_history_data = {}
        self._tls_data = {}
        self._http_data = {}
        self._udp_data = {}

    def showEvent(self, event):
        """При показе страницы запускаем автообновление"""
        super().showEvent(event)
        self._refresh_data()
        self._update_timer.start(5000)  # Обновлять каждые 5 секунд

    def hideEvent(self, event):
        """При скрытии останавливаем таймер"""
        super().hideEvent(event)
        self._update_timer.stop()

    def _get_runner(self):
        """Получает orchestra_runner из главного окна"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner
        return None

    def _refresh_data(self):
        """Обновляет данные истории"""
        runner = self._get_runner()
        if not runner:
            self.stats_label.setText("Оркестратор не инициализирован")
            self.history_text.setPlainText("")
            return

        learned = runner.get_learned_data()
        self._full_history_data = learned.get('history', {})
        self._tls_data = learned.get('tls', {})
        self._http_data = learned.get('http', {})
        self._udp_data = learned.get('udp', {})

        self._render_history()

    def _apply_filter(self):
        """Применяет фильтр"""
        self._render_history()

    def _render_history(self):
        """Рендерит историю с учётом фильтра"""
        filter_text = self.filter_input.text().strip().lower()
        history_data = self._full_history_data

        if not history_data:
            self.stats_label.setText("Нет данных истории")
            self.history_label.setText("")
            return

        lines = []
        total_strategies = 0
        shown_domains = 0

        # Сортируем домены по количеству стратегий
        sorted_domains = sorted(history_data.keys(), key=lambda d: len(history_data[d]), reverse=True)

        for domain in sorted_domains:
            # Фильтр по домену
            if filter_text and filter_text not in domain.lower():
                continue

            strategies = history_data[domain]
            if not strategies:
                continue

            shown_domains += 1

            # Определяем статус домена
            status = ""
            if domain in self._tls_data:
                status = " [TLS LOCK]"
            elif domain in self._http_data:
                status = " [HTTP LOCK]"
            elif domain in self._udp_data:
                status = " [UDP LOCK]"

            # Сортируем стратегии по рейтингу
            sorted_strats = sorted(strategies.items(), key=lambda x: x[1]['rate'], reverse=True)

            lines.append(f"═══ {domain}{status} ═══")

            for strat_num, h in sorted_strats:
                s = h['successes']
                f = h['failures']
                rate = h['rate']

                # Визуальный индикатор
                if rate >= 80:
                    bar = "████████░░"
                    indicator = "🟢"
                elif rate >= 60:
                    bar = "██████░░░░"
                    indicator = "🟡"
                elif rate >= 40:
                    bar = "████░░░░░░"
                    indicator = "🟠"
                else:
                    bar = "██░░░░░░░░"
                    indicator = "🔴"

                lines.append(f"  {indicator} #{strat_num:3d}: {bar} {rate:3d}% ({s}✓/{f}✗)")
                total_strategies += 1

            lines.append("")

        # Статистика
        total_domains = len(history_data)
        if filter_text:
            self.stats_label.setText(f"Показано: {shown_domains} из {total_domains} доменов, {total_strategies} записей")
        else:
            self.stats_label.setText(f"Всего: {total_domains} доменов, {total_strategies} записей")

        self.history_label.setText("\n".join(lines))
