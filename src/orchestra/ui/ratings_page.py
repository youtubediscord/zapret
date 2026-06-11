# ui/pages/orchestra/ratings_page.py
"""Страница истории стратегий с рейтингами (оркестратор)"""

from PyQt6.QtCore import QSize, QTimer
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
from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
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

    def __init__(self, parent=None, *, orchestra_feature):
        super().__init__(
            "История стратегий (рейтинги)",
            "Рейтинг = успехи / (успехи + провалы). При UNLOCK выбирается лучшая стратегия из истории.",
            parent,
            title_key="page.orchestra.ratings.title",
            subtitle_key="page.orchestra.ratings.subtitle",
        )
        self.setObjectName("orchestraRatingsPage")
        self._orchestra = orchestra_feature
        self._refresh_loading = False
        self._has_loaded_once = False
        self._no_runner = False
        self._filter_card = None
        self._history_card = None
        self._runtime_initialized = False
        self._ratings_state = OrchestraRatingsState(no_runner=True)
        self._ratings_state_runtime = OneShotWorkerRuntime()
        self._ratings_render_runtime = OneShotWorkerRuntime()
        self._ratings_render_state = LatestValueWorkerState(
            self._ratings_render_runtime,
            empty_value=None,
        )
        self._ratings_render_timer = QTimer(self)
        self._ratings_render_timer.setSingleShot(True)
        self._ratings_render_timer.timeout.connect(self._run_debounced_ratings_render)

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
        self._install_accessibility()

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
            worker_factory=lambda request_id: self._orchestra.create_ratings_state_load_worker(request_id, self),
            on_loaded=self._on_ratings_state_loaded,
            on_failed=self._on_ratings_state_failed,
            on_finished=self._on_ratings_state_worker_finished,
        )

    def _on_ratings_state_loaded(self, request_id: int, state) -> None:
        if not self._ratings_state_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        self._ratings_state = state
        self._no_runner = self._ratings_state.no_runner
        self._request_render_history()
        self._set_refresh_loading(False)

    def _on_ratings_state_failed(self, request_id: int, error: str) -> None:
        if not self._ratings_state_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        log(f"Ошибка загрузки рейтингов orchestra: {error}", "ERROR")
        self._set_refresh_loading(False)

    def _on_ratings_state_worker_finished(self, worker) -> None:
        if self._ratings_state_runtime.worker is worker:
            self._ratings_state_runtime.worker = None

    def _apply_filter(self):
        """Применяет фильтр"""
        self._request_render_history()

    def _request_render_history(self) -> None:
        state = self._ratings_render_state_obj()
        state.pending = (
            self._ratings_state,
            self.filter_input.text(),
        )
        try:
            self._ratings_render_timer.start(120)
        except Exception:
            self._run_debounced_ratings_render()

    def _run_debounced_ratings_render(self) -> None:
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        state = self._ratings_render_state_obj()
        pending = state.pending
        if pending is None:
            return
        if state.is_busy():
            return
        state.pending = None
        ratings_state, filter_text = pending
        self._start_ratings_render_worker(ratings_state, filter_text)

    def _start_ratings_render_worker(self, ratings_state, filter_text: str) -> None:
        self._ratings_render_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_ratings_render_worker(
                request_id,
                state=ratings_state,
                filter_text=filter_text,
            ),
            on_loaded=self._on_ratings_render_loaded,
            on_failed=self._on_ratings_render_failed,
            on_finished=self._on_ratings_render_worker_finished,
        )

    def create_ratings_render_worker(self, request_id: int, *, state, filter_text: str):
        from orchestra.ratings_worker import OrchestraRatingsRenderWorker

        language = str(self._ui_language or "ru")

        def _tr_worker(key: str, default: str, **kwargs) -> str:
            text = tr_catalog(key, language=language, default=default)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        return OrchestraRatingsRenderWorker(
            request_id,
            state=state,
            filter_text=filter_text,
            tr_fn=_tr_worker,
            build_render_plan=build_orchestra_ratings_render_plan,
            parent=self,
        )

    def _on_ratings_render_loaded(self, request_id: int, plan) -> None:
        if not self._ratings_render_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._ratings_render_state_obj().has_pending():
            return
        self._apply_ratings_render_plan(plan)

    def _on_ratings_render_failed(self, request_id: int, error: str) -> None:
        if not self._ratings_render_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._ratings_render_state_obj().has_pending():
            return
        log(f"Ошибка подготовки рейтингов orchestra: {error}", "DEBUG")

    def _on_ratings_render_worker_finished(self, worker) -> None:
        self._ratings_render_state_obj().schedule_pending_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, current_worker: self._is_current_ratings_render_worker_finish(
                current_worker,
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_ratings_render_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _schedule_ratings_render_start(self) -> None:
        self._ratings_render_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_ratings_render_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
            pending_when_already_scheduled=self._ratings_render_state_obj().pending,
        )

    def _run_scheduled_ratings_render_start(self) -> None:
        pending = self._ratings_render_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )
        if pending is None:
            return
        ratings_state, filter_text = pending
        self._start_ratings_render_worker(ratings_state, filter_text)

    def _is_current_ratings_render_worker_finish(self, worker) -> bool:
        if getattr(self._ratings_render_runtime, "worker", None) is worker:
            return True
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        return int(request_id) == int(getattr(self._ratings_render_runtime, "request_id", 0) or 0)

    def _ratings_render_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_ratings_render_state")
        runtime = self.__dict__.get("_ratings_render_runtime")
        if state is None:
            pending = self.__dict__.pop("_ratings_render_pending", None)
            start_scheduled = bool(self.__dict__.pop("_ratings_render_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_ratings_render_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _apply_ratings_render_plan(self, plan) -> None:
        self.history_text.setPlainText(plan.history_text)
        self._set_stats_text(plan.stats_text)

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        render_timer = self.__dict__.get("_ratings_render_timer")
        if render_timer is not None:
            render_timer.stop()
        render_runtime = self.__dict__.get("_ratings_render_runtime")
        if render_runtime is not None:
            self._ratings_render_state_obj().reset()
            render_runtime.stop(
                blocking=False,
                log_fn=log,
                warning_prefix="Orchestra ratings render worker",
            )
            render_runtime.cancel()
        self._ratings_state_runtime.stop(
            blocking=False,
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
        self._install_accessibility()

        if self._no_runner:
            self._set_stats_text(
                self._tr("page.orchestra.ratings.status.not_initialized", "Оркестратор не инициализирован")
            )
            self.history_text.setPlainText("")
            return

        if not self._has_loaded_once:
            self._set_stats_text(self._tr("page.orchestra.ratings.stats.loading", "Загрузка..."))
            self.history_text.setPlainText(
                self._tr("page.orchestra.ratings.history.placeholder", "История стратегий появится после обучения...")
            )
            return

        self._request_render_history()

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.filter_input,
            name="Фильтр рейтингов по домену",
            description=(
                "Введите часть домена, чтобы оставить в истории только подходящие записи. "
                "После ввода перейдите к истории клавишей Tab."
            ),
        )
        set_control_accessibility(
            self.refresh_btn,
            name="Обновить рейтинги стратегий",
            description="Загружает свежую историю обучения оркестратора.",
        )
        set_control_accessibility(
            self.history_text,
            name="История рейтингов стратегий",
            description="Здесь показаны результаты обучения оркестратора по доменам и стратегиям.",
        )
        self._set_stats_text(self.stats_label.text())

    def _set_stats_text(self, text: str) -> None:
        value = str(text or "").strip()
        self.stats_label.setText(value)
        set_state_text(self.stats_label, f"Статистика рейтингов: {value}")
