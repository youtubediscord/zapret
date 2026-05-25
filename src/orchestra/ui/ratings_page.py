# ui/pages/orchestra/ratings_page.py
"""Страница истории стратегий с рейтингами (оркестратор)"""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    LineEdit,
    PlainTextEdit,
    TransparentToolButton,
    CaptionLabel,
    CardWidget,
    StrongBodyLabel,
)

from ui.pages.base_page import BasePage
from ui.fluent_widgets import set_tooltip
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.theme import get_theme_tokens
from app.ui_texts import tr as tr_catalog
from log.log import log
from orchestra.ratings_workflow import (
    OrchestraRatingsState,
    build_orchestra_ratings_render_plan,
)


class OrchestraRatingsPage(BasePage):
    """Страница истории стратегий с рейтингами"""

    def __init__(self, parent=None, *, controller):
        super().__init__(
            "История стратегий (рейтинги)",
            "Рейтинг = успехи / (успехи + провалы). При UNLOCK выбирается лучшая стратегия из истории.",
            parent,
            title_key="page.orchestra.ratings.title",
            subtitle_key="page.orchestra.ratings.subtitle",
        )
        self.setObjectName("orchestraRatingsPage")
        self._controller = controller
        self._refresh_loading = False
        self._has_loaded_once = False
        self._no_runner = False
        self._filter_card = None
        self._history_card = None
        self._runtime_initialized = False
        self._ratings_state = OrchestraRatingsState(no_runner=True)
        self._ratings_state_runtime = OneShotWorkerRuntime()

        self._setup_ui()
        self._apply_page_theme(force=True)

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._refresh_data()

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()

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

        title_label = StrongBodyLabel(title, card)
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

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        _ = tokens or get_theme_tokens()
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setIcon(FluentIcon.SYNC)

    def _refresh_data(self):
        """Обновляет данные истории"""
        self._set_refresh_loading(True)
        self._has_loaded_once = True
        self._start_ratings_state_worker()

    def _start_ratings_state_worker(self) -> None:
        self._ratings_state_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._controller.create_state_load_worker(request_id, self),
            on_loaded=self._on_ratings_state_loaded,
            on_failed=self._on_ratings_state_failed,
            on_finished=self._on_ratings_state_worker_finished,
        )

    def _on_ratings_state_loaded(self, request_id: int, state) -> None:
        if not self._ratings_state_runtime.is_current(request_id):
            return
        self._ratings_state = state
        self._no_runner = self._ratings_state.no_runner
        self._render_history()
        self._set_refresh_loading(False)

    def _on_ratings_state_failed(self, request_id: int, error: str) -> None:
        if not self._ratings_state_runtime.is_current(request_id):
            return
        log(f"Ошибка загрузки рейтингов orchestra: {error}", "ERROR")
        self._set_refresh_loading(False)

    def _on_ratings_state_worker_finished(self, worker) -> None:
        if self._ratings_state_runtime.worker is worker:
            self._ratings_state_runtime.worker = None

    def _apply_filter(self):
        """Применяет фильтр"""
        self._render_history()

    def _render_history(self):
        """Рендерит историю с учётом фильтра"""
        plan = build_orchestra_ratings_render_plan(
            state=self._ratings_state,
            filter_text=self.filter_input.text(),
            tr_fn=self._tr,
        )
        self.stats_label.setText(plan.stats_text)
        self.history_text.setPlainText(plan.history_text)

    def cleanup(self) -> None:
        self._ratings_state_runtime.stop(
            blocking=True,
            log_fn=log,
            warning_prefix="Orchestra ratings worker",
        )
        self._ratings_state_runtime.cancel()

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
