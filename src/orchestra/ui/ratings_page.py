# ui/pages/orchestra/ratings_page.py
"""Страница истории стратегий с рейтингами (оркестратор)"""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QPushButton,
)

try:
    from qfluentwidgets import (
        LineEdit,
        PlainTextEdit,
        TransparentToolButton,
        CaptionLabel,
        CardWidget,
        StrongBodyLabel,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QLineEdit as LineEdit, QTextEdit as PlainTextEdit, QLabel as CaptionLabel
    TransparentToolButton = QPushButton
    CardWidget = QFrame
    StrongBodyLabel = QLabel
    _HAS_FLUENT = False

from ..base_page import BasePage
from ui.compat_widgets import set_tooltip
from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.theme import get_theme_tokens, get_themed_qta_icon
from ui.text_catalog import tr as tr_catalog
from log import log


class OrchestraRatingsPage(BasePage):
    """Страница истории стратегий с рейтингами"""

    def __init__(self, parent=None):
        super().__init__(
            "История стратегий (рейтинги)",
            "Рейтинг = успехи / (успехи + провалы). При UNLOCK выбирается лучшая стратегия из истории.",
            parent,
            title_key="page.orchestra.ratings.title",
            subtitle_key="page.orchestra.ratings.subtitle",
        )
        self.setObjectName("orchestraRatingsPage")
        self._refresh_loading = False
        self._has_loaded_once = False
        self._no_runner = False
        self._filter_card = None
        self._history_card = None
        self._runtime_initialized = False

        self._setup_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._refresh_data()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _create_card(self, title: str):
        card = CardWidget(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        title_label = StrongBodyLabel(title, card) if _HAS_FLUENT else QLabel(title)
        if not _HAS_FLUENT:
            title_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        card_layout.addWidget(title_label)
        card._title_label = title_label

        return card, card_layout

    def _set_refresh_loading(self, loading: bool) -> None:
        self._refresh_loading = loading
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setEnabled(not loading)
            set_tooltip(
                self.refresh_btn,
                self._tr("page.orchestra.ratings.button.refresh", "Обновить"),
            )
        self._apply_page_theme()

    def _setup_ui(self):
        # === Фильтр ===
        filter_card, filter_card_layout = self._create_card(
            self._tr("page.orchestra.ratings.card.filter", "Фильтр")
        )
        self._filter_card = filter_card

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.filter_input = LineEdit()
        self.filter_input.setPlaceholderText(
            self._tr("page.orchestra.ratings.filter.placeholder", "Поиск по домену...")
        )
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        # Styled in _apply_theme()
        filter_row.addWidget(self.filter_input, 1)

        self.refresh_btn = TransparentToolButton(self)
        self.refresh_btn.setFixedSize(32, 32)
        set_tooltip(self.refresh_btn, self._tr("page.orchestra.ratings.button.refresh", "Обновить"))
        self.refresh_btn.clicked.connect(self._refresh_data)
        filter_row.addWidget(self.refresh_btn)

        filter_card_layout.addLayout(filter_row)

        self.layout.addWidget(filter_card)

        # === Статистика ===
        self.stats_label = CaptionLabel(self._tr("page.orchestra.ratings.stats.loading", "Загрузка..."))
        self.layout.addWidget(self.stats_label)

        # === История стратегий ===
        history_card, history_layout = self._create_card(
            self._tr("page.orchestra.ratings.card.history", "Рейтинги по доменам")
        )
        self._history_card = history_card

        self.history_text = PlainTextEdit()
        apply_editor_smooth_scroll_preference(self.history_text)
        self.history_text.setReadOnly(True)
        self.history_text.setMinimumHeight(300)
        # Styled in _apply_theme()
        self.history_text.setPlainText(
            self._tr("page.orchestra.ratings.history.placeholder", "История стратегий появится после обучения...")
        )
        history_layout.addWidget(self.history_text)

        self.layout.addWidget(history_card)

        # Хранилище данных для фильтрации
        self._full_history_data = {}
        self._tls_data = {}
        self._http_data = {}
        self._udp_data = {}

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            icon_name = "mdi.loading" if self._refresh_loading else "mdi.refresh"
            icon_color = tokens.fg_faint if self._refresh_loading else tokens.fg
            self.refresh_btn.setIcon(get_themed_qta_icon(icon_name, color=icon_color))

    def _get_runner(self):
        """Получает orchestra_runner из главного окна"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner
        return None

    def _refresh_data(self):
        """Обновляет данные истории"""
        self._set_refresh_loading(True)
        self._has_loaded_once = True
        try:
            runner = self._get_runner()
            if not runner:
                self._no_runner = True
                self._full_history_data = {}
                self._tls_data = {}
                self._http_data = {}
                self._udp_data = {}
                self.stats_label.setText(
                    self._tr("page.orchestra.ratings.status.not_initialized", "Оркестратор не инициализирован")
                )
                self.history_text.setPlainText("")
                return
            self._no_runner = False
            learned = runner.get_learned_data()
            self._full_history_data = learned.get('history', {})
            self._tls_data = learned.get('tls', {})
            self._http_data = learned.get('http', {})
            self._udp_data = learned.get('udp', {})
            self._render_history()
        finally:
            self._set_refresh_loading(False)

    def _apply_filter(self):
        """Применяет фильтр"""
        self._render_history()

    def _render_history(self):
        """Рендерит историю с учётом фильтра"""
        if self._no_runner:
            self.stats_label.setText(
                self._tr("page.orchestra.ratings.status.not_initialized", "Оркестратор не инициализирован")
            )
            self.history_text.setPlainText("")
            return

        filter_text = self.filter_input.text().strip().lower()
        history_data = self._full_history_data

        if not history_data:
            self.stats_label.setText(self._tr("page.orchestra.ratings.status.no_history", "Нет данных истории"))
            self.history_text.setPlainText("")
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
                status = self._tr("page.orchestra.ratings.status.lock.tls", " [TLS LOCK]")
            elif domain in self._http_data:
                status = self._tr("page.orchestra.ratings.status.lock.http", " [HTTP LOCK]")
            elif domain in self._udp_data:
                status = self._tr("page.orchestra.ratings.status.lock.udp", " [UDP LOCK]")

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
            self.stats_label.setText(
                self._tr(
                    "page.orchestra.ratings.stats.filtered",
                    "Показано: {shown} из {total} доменов, {records} записей",
                    shown=shown_domains,
                    total=total_domains,
                    records=total_strategies,
                )
            )
        else:
            self.stats_label.setText(
                self._tr(
                    "page.orchestra.ratings.stats.total",
                    "Всего: {total} доменов, {records} записей",
                    total=total_domains,
                    records=total_strategies,
                )
            )

        self.history_text.setPlainText("\n".join(lines))

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._filter_card is not None and hasattr(self._filter_card, "_title_label"):
            self._filter_card._title_label.setText(
                self._tr("page.orchestra.ratings.card.filter", "Фильтр")
            )
        if self._history_card is not None and hasattr(self._history_card, "_title_label"):
            self._history_card._title_label.setText(
                self._tr("page.orchestra.ratings.card.history", "Рейтинги по доменам")
            )

        self.filter_input.setPlaceholderText(
            self._tr("page.orchestra.ratings.filter.placeholder", "Поиск по домену...")
        )
        set_tooltip(self.refresh_btn, self._tr("page.orchestra.ratings.button.refresh", "Обновить"))

        if self._no_runner:
            self.stats_label.setText(
                self._tr("page.orchestra.ratings.status.not_initialized", "Оркестратор не инициализирован")
            )
            self.history_text.setPlainText("")
            return

        if not self._has_loaded_once:
            self.stats_label.setText(self._tr("page.orchestra.ratings.stats.loading", "Загрузка..."))
            self.history_text.setPlainText(
                self._tr("page.orchestra.ratings.history.placeholder", "История стратегий появится после обучения...")
            )
            return

        self._render_history()
