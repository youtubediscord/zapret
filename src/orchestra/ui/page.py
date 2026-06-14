# orchestra/ui/page.py
"""Страница оркестратора автоматического обучения (circular)"""

from queue import Queue
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel,
)
from qfluentwidgets import FluentIcon

import orchestra.page_runtime as orchestra_page_runtime
from ui.pages.base_page import BasePage
from ui.log_limits import ORCHESTRA_PENDING_MAX_LINES, apply_text_line_limit, put_latest_bounded
from orchestra.ui.page_build import (
    build_orchestra_log_card,
    build_orchestra_log_history_card,
    build_orchestra_status_card,
    set_orchestra_status_accessibility,
)
from orchestra.ui.page_runtime_helpers import (
    append_log_line,
    apply_orchestra_language,
    current_protocol_filter_code,
    protocol_filter_items,
    set_protocol_filter_items,
    update_log_history_view,
)
from orchestra.monitoring_workflow import (
    detect_state_transition_from_line,
    process_log_queue,
    run_update_cycle,
    start_monitoring as start_orchestra_monitoring,
    stop_monitoring as stop_orchestra_monitoring,
)
from orchestra.ui.page_log_context_workflow import (
    copy_line_to_clipboard,
    parse_log_line_for_strategy,
    show_log_context_menu,
)
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.queued_worker_state import QueuedWorkerState
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from app.ui_texts import tr as tr_catalog
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    PushButton as FluentPushButton,
    LineEdit,
    ComboBox,
    ListWidget,
    CardWidget,
    TransparentToolButton,
)


from log.log import log

from orchestra.orchestra_runner import MAX_ORCHESTRA_LOGS


class OrchestraPage(BasePage):
    """Страница оркестратора с логами обучения"""

    log_received = pyqtSignal(str)  # Сигнал для получения логов из потока runner'а

    # Состояния оркестратора
    STATE_IDLE = "idle"          # Нет активности (серый)
    STATE_RUNNING = "running"    # Работает на залоченной стратегии (зелёный)
    STATE_LEARNING = "learning"  # Перебирает стратегии (оранжевый)
    STATE_UNLOCKED = "unlocked"  # RST блокировка, переобучение (красный)

    def __init__(self, parent=None, *, orchestra_feature, is_runtime_running):
        super().__init__(
            "Оркестратор v0.9.6 (Beta)",
            "Автоматическое обучение стратегий DPI bypass. Система находит лучшую стратегию для каждого домена (TCP: TLS/HTTP, UDP: QUIC/Discord Voice/STUN).\nЧтобы начать обучение зайдите на сайт и через несколько секунд обновите вкладку. Продолжайте это пока стратегия не будет помечена как LOCKED",
            parent,
            title_key="page.orchestra.title",
            subtitle_key="page.orchestra.subtitle",
        )
        self._orchestra = orchestra_feature
        self._is_runtime_running = is_runtime_running

        self._info_label = None
        self._filter_label = None
        self._clear_filter_btn = None
        self._log_history_desc = None
        self._clear_all_logs_btn = None
        self._view_log_btn = None
        self._delete_log_btn = None
        self._status_card_title = None
        self._log_card_title = None
        self._log_history_card_title = None
        self._clear_learned_pending = False
        self._cleanup_in_progress = False
        self._clear_learned_runtime = OneShotWorkerRuntime()
        self._clear_learned_pending_worker = False
        self._clear_learned_start_scheduled = False
        self._log_history_runtime = OneShotWorkerRuntime()
        self._log_history_state = LatestValueWorkerState(
            self._log_history_runtime,
            empty_value=False,
        )
        self._log_history_action_runtime = OneShotWorkerRuntime()
        self._log_history_action_state = QueuedWorkerState[tuple[str, str]](
            self._log_history_action_runtime,
        )
        self._log_context_action_runtime = OneShotWorkerRuntime()
        self._log_context_action_state = QueuedWorkerState[tuple[str, str, int, str]](
            self._log_context_action_runtime,
        )
        self._log_filter_runtime = OneShotWorkerRuntime()
        self._log_filter_state = LatestValueWorkerState(
            self._log_filter_runtime,
            empty_value=None,
        )
        self._log_filter_timer = QTimer(self)
        self._log_filter_timer.setSingleShot(True)
        self._log_filter_timer.timeout.connect(self._run_debounced_log_filter)
        self._clear_learned_reset_timer = QTimer(self)
        self._clear_learned_reset_timer.setSingleShot(True)
        self._clear_learned_reset_timer.timeout.connect(self._reset_clear_learned_button)

        self._build_ui()

        # Путь к лог-файлу (берём из runner динамически)
        self._log_file_path = None  # Устанавливается в _update_log_file_path()
        self._last_log_position = 0  # Позиция в файле для инкрементального чтения
        self._current_state = self.STATE_IDLE  # Текущее состояние

        # Хранилище всех строк лога для фильтрации
        self._full_log_lines = []
        self._max_log_lines = 1000  # Максимум строк в памяти
        apply_text_line_limit(self.log_text, self._max_log_lines)

        # Таймер для обновления статуса и логов
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_all)

        # Thread-safe очередь для логов из runner потока
        self._log_queue = Queue()

        # Таймер для обработки очереди логов (50ms - быстро, но не блокирует UI)
        self._log_queue_timer = QTimer(self)
        self._log_queue_timer.timeout.connect(self._process_log_queue)
        # НЕ стартуем здесь — только при start_monitoring() / showEvent()
        self._runtime_started = False

        # Подключаем сигнал для обновления логов (теперь только из main thread)
        self.log_received.connect(self._on_log_received)

        # Apply token styles after UI construction.
        self._apply_page_theme(force=True)

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

        return card, card_layout, title_label

    def _protocol_filter_items(self) -> list[tuple[str, str]]:
        return protocol_filter_items(tr_fn=self._tr)

    def _set_protocol_filter_items(self) -> None:
        set_protocol_filter_items(
            combo=getattr(self, "log_protocol_filter", None),
            items=self._protocol_filter_items(),
        )

    def _current_protocol_filter_code(self) -> str:
        return current_protocol_filter_code(combo=self.log_protocol_filter)

    def _build_ui(self):
        """Строит UI страницы"""

        # === Статус карточка ===
        status_widgets = build_orchestra_status_card(
            create_card=self._create_card,
            tr_fn=self._tr,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
        )
        self._status_card_title = status_widgets.title_label
        self.status_icon = status_widgets.status_icon
        self.status_label = status_widgets.status_label
        self._info_label = status_widgets.info_label
        self.layout.addWidget(status_widgets.card)

        # === Лог карточка ===
        log_widgets = build_orchestra_log_card(
            create_card=self._create_card,
            tr_fn=self._tr,
            line_edit_cls=LineEdit,
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            transparent_tool_button_cls=TransparentToolButton,
            fluent_push_button_cls=FluentPushButton,
            on_show_log_context_menu=self._show_log_context_menu,
            on_apply_log_filter=self._apply_log_filter,
            on_clear_log_filter=self._clear_log_filter,
            on_clear_log=self._clear_log,
            on_clear_learned_clicked=self._on_clear_learned_clicked,
        )
        self._log_card_title = log_widgets.title_label
        self.log_text = log_widgets.log_text
        self._filter_label = log_widgets.filter_label
        self.log_filter_input = log_widgets.log_filter_input
        self.log_protocol_filter = log_widgets.log_protocol_filter
        self._clear_filter_btn = log_widgets.clear_filter_btn
        self.clear_log_btn = log_widgets.clear_log_btn
        self.clear_learned_btn = log_widgets.clear_learned_btn
        self._set_protocol_filter_items()
        self.layout.addWidget(log_widgets.card)

        # === История логов ===
        log_history_widgets = build_orchestra_log_history_card(
            create_card=self._create_card,
            tr_fn=self._tr,
            max_logs=MAX_ORCHESTRA_LOGS,
            list_widget_cls=ListWidget,
            caption_label_cls=CaptionLabel,
            fluent_push_button_cls=FluentPushButton,
            on_view_log_history=self._view_log_history,
            on_delete_log_history=self._delete_log_history,
            on_clear_all_log_history=self._clear_all_log_history,
        )
        self._log_history_card_title = log_history_widgets.title_label
        self._log_history_desc = log_history_widgets.desc_label
        self.log_history_list = log_history_widgets.log_history_list
        self._view_log_btn = log_history_widgets.view_log_btn
        self._delete_log_btn = log_history_widgets.delete_log_btn
        self._clear_all_logs_btn = log_history_widgets.clear_all_logs_btn
        self.layout.addWidget(log_history_widgets.card)

        # Обновляем статус
        self._update_status(self.STATE_IDLE)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        selection_fg = "rgba(0, 0, 0, 0.90)" if tokens.is_light else "rgba(245, 245, 245, 0.92)"

        if self.status_label is not None:
            # Final state color is applied by _update_status.
            self.status_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 14px;")

        if self._info_label is not None:
            self._info_label.setContentsMargins(0, 8, 0, 0)

        if self.log_text is not None:
            self.log_text.setStyleSheet(
                f"""
                QTextEdit {{
                    background-color: {tokens.surface_bg};
                    border: 1px solid {tokens.surface_border};
                    border-radius: 8px;
                    color: {tokens.fg};
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 11px;
                    padding: 8px;
                }}
                QTextEdit::selection {{
                    background-color: {tokens.accent_soft_bg_hover};
                    color: {selection_fg};
                }}
                """
            )

        # log_filter_input (LineEdit) and log_protocol_filter (ComboBox) are
        # qfluentwidgets widgets — they style themselves.

        if self._clear_filter_btn is not None:
            self._clear_filter_btn.setIcon(FluentIcon.CLOSE)

        if self.clear_log_btn is not None:
            self.clear_log_btn.setIcon(FluentIcon.BROOM)

        if self._clear_all_logs_btn is not None:
            self._clear_all_logs_btn.setIcon(FluentIcon.DELETE)

        if self.clear_learned_btn is not None:
            self._update_clear_learned_button_icon()

        if self._view_log_btn is not None:
            self._view_log_btn.setIcon(FluentIcon.VIEW)

        if self._delete_log_btn is not None:
            self._delete_log_btn.setIcon(FluentIcon.DELETE)

        self._update_status(self._current_state)

    def _update_status(self, state: str):
        """Обновляет статус на основе состояния"""
        self._current_state = state
        tokens = get_theme_tokens()
        plan = orchestra_page_runtime.build_status_display_plan(
            state=state,
            idle_state=self.STATE_IDLE,
            learning_state=self.STATE_LEARNING,
            running_state=self.STATE_RUNNING,
            unlocked_state=self.STATE_UNLOCKED,
            idle_text=self._tr("page.orchestra.status.idle", "⏸ IDLE - ожидание соединений"),
            learning_text=self._tr("page.orchestra.status.learning", "🔄 LEARNING - перебирает стратегии"),
            running_text=self._tr("page.orchestra.status.running", "✅ RUNNING - работает на лучших стратегиях"),
            unlocked_text=self._tr("page.orchestra.status.unlocked", "🔓 UNLOCKED - переобучение (RST блокировка)"),
            idle_color=tokens.fg_faint,
        )
        self.status_icon.setPixmap(get_cached_qta_pixmap("mdi.brain", color=plan.icon_color, size=24))
        self.status_label.setText(plan.label_text)
        self.status_label.setStyleSheet(f"color: {plan.label_color}; font-size: 14px;")
        set_orchestra_status_accessibility(self.status_label, plan.label_text, status_icon=self.status_icon)

    def _clear_log(self):
        """Очищает лог"""
        self.log_text.clear()
        self._full_log_lines = []  # Очищаем хранилище
        # Сбрасываем позицию чтобы перечитать файл с начала
        self._last_log_position = 0

    def _update_clear_learned_button_icon(self) -> None:
        if self.clear_learned_btn is None:
            return
        tokens = get_theme_tokens()
        plan = orchestra_page_runtime.build_clear_learned_button_plan(
            pending=self._clear_learned_pending,
            default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
            pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
            done_text="",
            fg_color=tokens.fg,
        )
        self.clear_learned_btn.setIcon(FluentIcon.DELETE if plan.action in {"confirm", "done"} else FluentIcon.SYNC)

    def _reset_clear_learned_button(self) -> None:
        if self._cleanup_in_progress:
            return
        self._clear_learned_pending = False
        if self.clear_learned_btn is not None:
            plan = orchestra_page_runtime.build_clear_learned_button_plan(
                pending=False,
                default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                done_text="",
                fg_color=get_theme_tokens().fg,
            )
            self.clear_learned_btn.setText(plan.text)
            self.clear_learned_btn.setIcon(FluentIcon.DELETE if plan.action in {"confirm", "done"} else FluentIcon.SYNC)

    def _on_clear_learned_clicked(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._clear_learned_pending:
            self._clear_learned_reset_timer.stop()
            self._clear_learned_pending = False
            if self.clear_learned_btn is not None:
                plan = orchestra_page_runtime.build_clear_learned_button_plan(
                    pending=False,
                    default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                    pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                    done_text=self._tr("page.orchestra.button.clear_learning.done", "✓ Сброшено"),
                    fg_color=get_theme_tokens().fg,
                )
                self.clear_learned_btn.setText(plan.text)
                self.clear_learned_btn.setIcon(FluentIcon.DELETE if plan.action in {"confirm", "done"} else FluentIcon.SYNC)
            self._clear_learned()
            QTimer.singleShot(1500, self._reset_clear_learned_button)
            return

        self._clear_learned_pending = True
        if self.clear_learned_btn is not None:
            plan = orchestra_page_runtime.build_clear_learned_button_plan(
                pending=True,
                default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                done_text="",
                fg_color=get_theme_tokens().fg,
            )
            self.clear_learned_btn.setText(plan.text)
            self.clear_learned_btn.setIcon(FluentIcon.DELETE if plan.action in {"confirm", "done"} else FluentIcon.SYNC)
        self._clear_learned_reset_timer.start(3000)

    def _clear_learned(self):
        """Сбрасывает данные обучения"""
        if self._cleanup_in_progress:
            return
        log("Запрошена очистка данных обучения", "INFO")
        self._request_clear_learned_worker()

    def create_clear_learned_worker(self, request_id: int):
        return self._orchestra.create_clear_learned_worker(request_id, self)

    def _request_clear_learned_worker(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        runtime = self.__dict__.get("_clear_learned_runtime")
        if (
            (runtime is not None and runtime.is_running())
            or self.__dict__.get("_clear_learned_start_scheduled", False)
        ):
            self._clear_learned_pending_worker = True
            return
        self._start_clear_learned_worker()

    def _start_clear_learned_worker(self) -> None:
        self._clear_learned_pending_worker = False
        runtime = self.__dict__.get("_clear_learned_runtime")
        if runtime is None or runtime.is_running():
            return
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_clear_learned_worker(request_id),
            on_loaded=self._on_clear_learned_worker_loaded,
            on_failed=self._on_clear_learned_worker_failed,
            on_finished=self._on_clear_learned_worker_finished,
        )

    def _on_clear_learned_worker_loaded(self, request_id: int, cleared: bool) -> None:
        if not self._clear_learned_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if bool(cleared):
            log("Данные обучения очищены", "INFO")
        self.append_log(
            self._tr("page.orchestra.log.learned_cleared", "[INFO] Данные обучения сброшены")
        )
        self._update_domains({})

    def _on_clear_learned_worker_failed(self, request_id: int, error: str) -> None:
        if not self._clear_learned_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Не удалось сбросить данные обучения: {error}", "WARNING")

    def _on_clear_learned_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_clear_learned_runtime"), worker):
            return
        if self.__dict__.get("_clear_learned_pending_worker", False) and not self.__dict__.get(
            "_cleanup_in_progress",
            False,
        ):
            self._schedule_clear_learned_worker_start()

    def _schedule_clear_learned_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_clear_learned_start_scheduled", False):
            self._clear_learned_pending_worker = True
            return
        self._clear_learned_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_clear_learned_worker_start)
        except Exception:
            self._run_scheduled_clear_learned_worker_start()

    def _run_scheduled_clear_learned_worker_start(self) -> None:
        self._clear_learned_start_scheduled = False
        pending = bool(self.__dict__.get("_clear_learned_pending_worker", False))
        self._clear_learned_pending_worker = False
        if not pending or self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_clear_learned_worker()

    def _update_all(self):
        """Обновляет статус, данные обучения, историю и whitelist"""
        if self._cleanup_in_progress:
            return
        run_update_cycle(
            is_runner_alive=self._is_runtime_running,
            state_idle=self.STATE_IDLE,
            update_status=self._update_status,
            update_learned_domains=self._update_learned_domains,
            update_log_history=self._update_log_history,
        )

    def _on_log_received(self, text: str):
        """Обработчик сигнала - добавляет лог и определяет состояние"""
        if self._cleanup_in_progress:
            return
        self.append_log(text)
        self._detect_state_from_line(text)

    def emit_log(self, text: str):
        """Публичный метод для отправки логов (вызывается из callback runner'а).
        Thread-safe: использует очередь вместо прямого emit сигнала.
        """
        if self._cleanup_in_progress:
            return
        # Кладём в очередь с лимитом, чтобы UI не копил бесконечный хвост логов.
        put_latest_bounded(
            self._log_queue,
            text,
            max_items=ORCHESTRA_PENDING_MAX_LINES,
        )

    def _process_log_queue(self):
        """Обрабатывает очередь логов из main thread (вызывается таймером)"""
        if self._cleanup_in_progress:
            return
        process_log_queue(
            log_queue=self._log_queue,
            emit_log=self.log_received.emit,
            batch_size=20,
        )

    def _detect_state_from_line(self, line: str):
        """Определяет состояние оркестратора из строки лога

        Форматы сообщений из orchestra_runner:
        - "[18:21:27] PRELOADED: domain.com = strategy 1 [tls]" - предзагружено (RUNNING)
        - "[17:45:13] ✓ SUCCESS: domain.com :443 strategy=1" - обычный успех
        - "[17:45:13] 🔒 LOCKED: domain.com :443 = strategy 1" - залочен (RUNNING)
        - "[17:45:13] 🔓 UNLOCKED: domain.com :443 - re-learning..." - разлочен (UNLOCKED)
        - "[17:45:13] ✗ FAIL: domain.com :443 strategy=1" - провал
        - "[17:45:13] 🔄 Strategy rotated to 2" - ротация (LEARNING)
        - "[18:08:36] ⚡ RST detected - DPI block" - RST блок (LEARNING)
        """
        detect_state_transition_from_line(
            line=line,
            current_state=self._current_state,
            idle_state=self.STATE_IDLE,
            learning_state=self.STATE_LEARNING,
            running_state=self.STATE_RUNNING,
            unlocked_state=self.STATE_UNLOCKED,
            update_status=self._update_status,
        )

    def _update_learned_domains(self):
        """Данные обучения больше не читаются на главной странице Orchestra."""
        return

    def _update_domains(self, _data: dict):
        """Данные обученных доменов теперь отображаются на вкладке Залоченное"""
        pass  # Виджет перемещён в orchestra/locked_page.py

    def append_log(self, text: str):
        """Добавляет строку в лог"""
        if self._cleanup_in_progress:
            return
        self._full_log_lines = append_log_line(
            text=text,
            full_log_lines=self._full_log_lines,
            max_log_lines=self._max_log_lines,
            matches_filter=self._matches_filter,
            log_text=self.log_text,
        )

    def _matches_filter(self, text: str) -> bool:
        """Проверяет, соответствует ли строка текущему фильтру"""
        domain_filter = self.log_filter_input.text().strip().lower()
        protocol_filter = self._current_protocol_filter_code()
        return orchestra_page_runtime.matches_filter(
            text=text,
            domain_filter=domain_filter,
            protocol_filter=protocol_filter,
        )

    def _apply_log_filter(self):
        """Применяет фильтр к логу"""
        if self._cleanup_in_progress:
            return
        request = (
            tuple(self._full_log_lines),
            self.log_filter_input.text().strip().lower(),
            self._current_protocol_filter_code(),
        )
        self._log_filter_state_obj().pending = request
        try:
            self._log_filter_timer.start(120)
        except Exception:
            self._run_debounced_log_filter()

    def create_log_filter_worker(self, request_id: int, *, lines, domain_filter: str, protocol_filter: str):
        from orchestra.page_workers import OrchestraLogFilterWorker

        return OrchestraLogFilterWorker(
            request_id,
            lines=lines,
            domain_filter=domain_filter,
            protocol_filter=protocol_filter,
            filter_lines=orchestra_page_runtime.filter_lines,
            parent=self,
        )

    def _run_debounced_log_filter(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = self._log_filter_state_obj().pending
        if pending is None:
            return
        if self._log_filter_state_obj().is_busy():
            return
        self._log_filter_state_obj().pending = None
        lines, domain_filter, protocol_filter = pending
        self._start_log_filter_worker(lines, domain_filter, protocol_filter)

    def _start_log_filter_worker(self, lines, domain_filter: str, protocol_filter: str) -> None:
        self._log_filter_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_log_filter_worker(
                request_id,
                lines=lines,
                domain_filter=str(domain_filter or ""),
                protocol_filter=str(protocol_filter or ""),
            ),
            on_loaded=self._on_log_filter_loaded,
            on_failed=self._on_log_filter_failed,
            on_finished=self._on_log_filter_worker_finished,
        )

    def _on_log_filter_loaded(self, request_id: int, text: str) -> None:
        if not self._log_filter_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._log_filter_state_obj().has_pending():
            return
        self.log_text.clear()
        if text:
            self.log_text.setPlainText(str(text or ""))
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def _on_log_filter_failed(self, request_id: int, error: str) -> None:
        if not self._log_filter_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._log_filter_state_obj().has_pending():
            return
        log(f"Ошибка фильтрации лога Orchestra: {error}", "DEBUG")

    def _on_log_filter_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_log_filter_runtime"), worker):
            return
        if self._log_filter_state_obj().has_pending() and not self._cleanup_in_progress:
            self._schedule_log_filter_worker_start()

    def _schedule_log_filter_worker_start(self) -> None:
        self._log_filter_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_log_filter_worker_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=self._log_filter_state_obj().pending,
        )

    def _run_scheduled_log_filter_worker_start(self) -> None:
        pending = self._log_filter_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is None:
            return
        lines, domain_filter, protocol_filter = pending
        self._start_log_filter_worker(lines, domain_filter, protocol_filter)

    def _log_filter_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_log_filter_state")
        runtime = self.__dict__.get("_log_filter_runtime")
        if state is None:
            pending = self.__dict__.pop("_log_filter_pending", None)
            start_scheduled = bool(self.__dict__.pop("_log_filter_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_log_filter_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _clear_log_filter(self):
        """Сбрасывает фильтр"""
        if self._cleanup_in_progress:
            return
        self.log_filter_input.clear()
        self.log_protocol_filter.setCurrentIndex(0)
        self._apply_log_filter()

    @pyqtSlot()
    def start_monitoring(self):
        """Запускает мониторинг"""
        if self._cleanup_in_progress:
            return
        runner = self._get_runner()
        start_orchestra_monitoring(
            runner=runner,
            emit_log_callback=self.emit_log,
            set_last_log_position=lambda value: setattr(self, "_last_log_position", value),
            log_queue_timer=self._log_queue_timer,
            update_timer=self.update_timer,
            run_update_now=self._update_all,
        )

    def stop_monitoring(self):
        """Останавливает мониторинг"""
        stop_orchestra_monitoring(
            log_queue_timer=self._log_queue_timer,
            update_timer=self.update_timer,
        )

    def on_page_activated(self) -> None:
        """Автозапуск мониторинга при активации страницы."""
        if not self._runtime_started:
            self._runtime_started = True
            self.start_monitoring()

    def on_page_hidden(self) -> None:
        """Останавливает только UI-мониторинг скрытой страницы."""
        self.stop_monitoring()
        self._runtime_started = False

    def set_learned_data(self, data: dict):
        """Устанавливает данные обучения"""
        self._update_domains(data)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_orchestra_language(
            tr_fn=self._tr,
            current_state=self._current_state,
            update_status=self._update_status,
            update_log_history=self._update_log_history,
            apply_log_filter=self._apply_log_filter,
            status_card_title=self._status_card_title,
            log_card_title=self._log_card_title,
            log_history_card_title=self._log_history_card_title,
            info_label=self._info_label,
            log_text=self.log_text,
            filter_label=self._filter_label,
            log_filter_input=self.log_filter_input,
            log_protocol_filter=self.log_protocol_filter,
            clear_filter_btn=self._clear_filter_btn,
            clear_log_btn=self.clear_log_btn,
            clear_learned_btn=self.clear_learned_btn,
            clear_learned_pending=self._clear_learned_pending,
            log_history_desc=self._log_history_desc,
            view_log_btn=self._view_log_btn,
            delete_log_btn=self._delete_log_btn,
            clear_all_logs_btn=self._clear_all_logs_btn,
        )

    # ==================== LOG HISTORY METHODS ====================

    def _update_log_history(self):
        """Обновляет список истории логов"""
        if self._cleanup_in_progress:
            return
        self._request_log_history_load()

    def create_log_history_load_worker(self, request_id: int):
        return self._orchestra.create_log_history_load_worker(request_id, self)

    def _request_log_history_load(self) -> None:
        if self._log_history_state_obj().is_busy():
            self._log_history_state_obj().pending = True
            return
        self._log_history_state_obj().pending = False
        self._start_log_history_load_worker()

    def _start_log_history_load_worker(self) -> None:
        self._log_history_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_log_history_load_worker(request_id),
            on_loaded=self._on_log_history_loaded,
            on_failed=self._on_log_history_failed,
            on_finished=self._on_log_history_worker_finished,
        )

    def _on_log_history_loaded(self, request_id: int, logs) -> None:
        if not self._log_history_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        update_log_history_view(
            logs=logs,
            tr_fn=self._tr,
            log_history_list=self.log_history_list,
        )

    def _on_log_history_failed(self, request_id: int, error: str) -> None:
        if not self._log_history_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка обновления истории логов: {error}", "DEBUG")

    def _on_log_history_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_log_history_runtime"), worker):
            return
        if self._log_history_state_obj().has_pending() and not self._cleanup_in_progress:
            self._schedule_log_history_load_worker_start()

    def _schedule_log_history_load_worker_start(self) -> None:
        self._log_history_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_log_history_load_worker_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_log_history_load_worker_start(self) -> None:
        pending = self._log_history_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is False:
            return
        self._start_log_history_load_worker()

    def _log_history_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_log_history_state")
        runtime = self.__dict__.get("_log_history_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_log_history_pending", False))
            start_scheduled = bool(self.__dict__.pop("_log_history_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_log_history_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _log_history_pending(self) -> bool:
        return bool(self._log_history_state_obj().pending)

    @_log_history_pending.setter
    def _log_history_pending(self, value: bool) -> None:
        self._log_history_state_obj().pending = bool(value)

    @property
    def _log_history_start_scheduled(self) -> bool:
        return bool(self._log_history_state_obj().start_scheduled)

    @_log_history_start_scheduled.setter
    def _log_history_start_scheduled(self, value: bool) -> None:
        self._log_history_state_obj().start_scheduled = bool(value)

    def create_log_history_action_worker(self, request_id: int, *, action: str, log_id: str):
        return self._orchestra.create_log_history_action_worker(
            request_id,
            action=action,
            log_id=log_id,
            parent=self,
        )

    def _current_log_history_id(self) -> str:
        current_item = self.log_history_list.currentItem()
        if current_item is None:
            return ""
        return str(current_item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _request_log_history_action(self, action: str, log_id: str = "") -> None:
        if self._cleanup_in_progress:
            return
        runner = self._get_runner()
        if runner is None:
            return
        normalized_action = str(action or "").strip()
        normalized_log_id = str(log_id or "").strip()
        if normalized_action in {"view", "delete"} and not normalized_log_id:
            return
        payload = (normalized_action, normalized_log_id)
        if self._log_history_action_state_obj().is_busy():
            self._queue_log_history_action(payload)
            return
        self._start_log_history_action_worker(payload)

    def _queue_log_history_action(self, payload) -> None:
        action, log_id = payload
        queued = (str(action or "").strip(), str(log_id or "").strip())
        self._log_history_action_state_obj().append_unique(queued, key=lambda item: item)

    def _start_log_history_action_worker(self, payload) -> None:
        action, log_id = payload
        self._log_history_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_log_history_action_worker(
                request_id,
                action=str(action),
                log_id=str(log_id),
            ),
            on_loaded=self._on_log_history_action_finished,
            on_failed=self._on_log_history_action_failed,
            on_finished=self._on_log_history_action_worker_finished,
        )

    def _on_log_history_action_finished(self, request_id: int, action: str, result) -> None:
        if not self._log_history_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        normalized_action = str(action or "").strip()
        if normalized_action == "view":
            content = str(getattr(result, "content", "") or "")
            if content:
                self.log_text.clear()
                self.log_text.setPlainText(content)
        elif normalized_action == "delete":
            if bool(getattr(result, "deleted", False)):
                self._update_log_history()
        elif normalized_action == "clear":
            self._update_log_history()

        message = str(getattr(result, "message_text", "") or "")
        if message:
            self.append_log(message)

    def _on_log_history_action_failed(self, request_id: int, action: str, error: str) -> None:
        if not self._log_history_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка действия истории логов {action}: {error}", "DEBUG")

    def _on_log_history_action_worker_finished(self, worker) -> None:
        pending = self._log_history_action_state_obj().pop_next_after_finish(
            worker,
            is_current_worker_finish=self._is_current_worker_finish,
            cleanup_in_progress=self._cleanup_in_progress,
        )
        if pending is None:
            return
        self._schedule_log_history_action_worker_start(pending)

    def _schedule_log_history_action_worker_start(self, payload) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        action, log_id = payload
        queued = (str(action or "").strip(), str(log_id or "").strip())
        state = self._log_history_action_state_obj()
        if state.start_scheduled:
            self._queue_log_history_action(queued)
            return
        state.start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_log_history_action_worker_start(value))

    def _run_scheduled_log_history_action_worker_start(self, payload) -> None:
        self._log_history_action_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_log_history_action_worker(payload)

    def _log_history_action_state_obj(self) -> QueuedWorkerState[tuple[str, str]]:
        state = self.__dict__.get("_log_history_action_state")
        runtime = self.__dict__.get("_log_history_action_runtime")
        if state is None:
            pending = [
                (str(action or "").strip(), str(log_id or "").strip())
                for action, log_id in list(self.__dict__.pop("_log_history_action_pending", []) or [])
            ]
            start_scheduled = bool(self.__dict__.pop("_log_history_action_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_log_history_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _log_history_action_pending(self) -> list[tuple[str, str]]:
        return self._log_history_action_state_obj().pending

    @_log_history_action_pending.setter
    def _log_history_action_pending(self, value) -> None:
        self._log_history_action_state_obj().pending = [
            (str(action or "").strip(), str(log_id or "").strip())
            for action, log_id in list(value or [])
        ]

    @property
    def _log_history_action_start_scheduled(self) -> bool:
        return bool(self._log_history_action_state_obj().start_scheduled)

    @_log_history_action_start_scheduled.setter
    def _log_history_action_start_scheduled(self, value: bool) -> None:
        self._log_history_action_state_obj().start_scheduled = bool(value)

    def _view_log_history(self):
        """Просматривает выбранный лог из истории"""
        self._request_log_history_action("view", self._current_log_history_id())

    def _delete_log_history(self):
        """Удаляет выбранный лог из истории"""
        self._request_log_history_action("delete", self._current_log_history_id())

    def _clear_all_log_history(self):
        """Удаляет все логи из истории"""
        self._request_log_history_action("clear")

    def _get_runner(self):
        return self._orchestra.runner

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._clear_learned_pending = False
        self._clear_learned_pending_worker = False
        self._clear_learned_start_scheduled = False
        self.stop_monitoring()
        self._clear_learned_reset_timer.stop()
        self._log_filter_timer.stop()
        self._log_filter_state_obj().reset()
        self._log_filter_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra log filter worker",
        )
        self._clear_learned_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra clear learned worker",
        )
        self._log_history_state_obj().reset()
        self._log_history_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra log history worker",
        )
        self._log_history_action_state_obj().reset()
        self._log_history_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra log history action worker",
        )
        self._log_context_action_state_obj().reset()
        self._log_context_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra log context action worker",
        )

        try:
            while not self._log_queue.empty():
                self._log_queue.get_nowait()
        except Exception:
            pass

        try:
            self.log_received.disconnect()
        except Exception:
            pass

        try:
            runner = self._get_runner()
            if runner is not None:
                runner.set_output_callback(lambda _text: None)
        except Exception:
            pass

    # Методы _show_block_strategy_dialog, _show_lock_strategy_dialog,
    # _show_manage_blocked_dialog, _show_manage_locked_dialog удалены -
    # функционал перенесён в отдельные страницы:
    # - OrchestraLockedPage (ui/pages/orchestra/locked_page.py)
    # - OrchestraBlockedPage (ui/pages/orchestra/blocked_page.py)

    def _show_log_context_menu(self, pos):
        """Показывает контекстное меню для строки лога"""
        show_log_context_menu(
            owner=self,
            log_text=self.log_text,
            pos=pos,
            is_strategy_blocked_fn=self._is_strategy_blocked_from_log,
            tr_fn=self._tr,
            copy_line_fn=self._copy_line_to_clipboard,
            lock_strategy_fn=self._lock_strategy_from_log,
            block_strategy_fn=self._block_strategy_from_log,
            unblock_strategy_fn=self._unblock_strategy_from_log,
            add_to_whitelist_fn=self._add_to_whitelist_from_log,
        )

    def _parse_log_line_for_strategy(self, line: str) -> tuple | None:
        """Парсит строку лога и извлекает домен, стратегию и протокол

        Форматы строк:
        - "[20:17:14] ✓ SUCCESS: qms.ru :443 strategy=1"
        - "[19:55:15] ✓ SUCCESS: youtube.com :443 strategy=5 [tls]"
        - "[19:55:15] ✗ FAIL: youtube.com :443 strategy=5"
        - "[19:55:15] 🔒 LOCKED: youtube.com :443 = strategy 5"
        - "[19:55:15] 🔓 UNLOCKED: youtube.com :443 - re-learning..."
        - "[HH:MM:SS] ✓ SUCCESS: domain UDP strategy=1"
        """
        return parse_log_line_for_strategy(line)

    def _copy_line_to_clipboard(self, text: str):
        """Копирует текст в буфер обмена"""
        copy_line_to_clipboard(text=text, append_log=self.append_log, tr_fn=self._tr)

    def _is_strategy_blocked_from_log(self, domain: str, strategy: int) -> bool:
        return self._orchestra.is_strategy_blocked(domain=domain, strategy=int(strategy or 0))

    def create_log_context_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        domain: str,
        strategy: int,
        protocol: str,
    ):
        return self._orchestra.create_log_context_action_worker(
            request_id,
            action=action,
            domain=domain,
            strategy=int(strategy or 0),
            protocol=protocol,
            parent=self,
        )

    def _request_log_context_action(self, action: str, domain: str, strategy: int = 0, protocol: str = "") -> None:
        if self._cleanup_in_progress:
            return
        if self._get_runner() is None:
            return
        payload = (
            str(action or "").strip(),
            str(domain or "").strip(),
            int(strategy or 0),
            str(protocol or "").strip(),
        )
        if not payload[0] or not payload[1]:
            return
        if self._log_context_action_state_obj().is_busy():
            self._queue_log_context_action(payload)
            return
        self._start_log_context_action_worker(payload)

    def _queue_log_context_action(self, payload) -> None:
        action, domain, strategy, protocol = payload
        queued = (
            str(action or "").strip(),
            str(domain or "").strip(),
            int(strategy or 0),
            str(protocol or "").strip(),
        )
        self._log_context_action_state_obj().append_unique(queued, key=lambda item: item)

    def _start_log_context_action_worker(self, payload) -> None:
        action, domain, strategy, protocol = payload
        self._log_context_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_log_context_action_worker(
                request_id,
                action=str(action),
                domain=str(domain),
                strategy=int(strategy or 0),
                protocol=str(protocol),
            ),
            on_loaded=self._on_log_context_action_finished,
            on_failed=self._on_log_context_action_failed,
            on_finished=self._on_log_context_action_worker_finished,
        )

    def _on_log_context_action_finished(self, request_id: int, _action: str, plan) -> None:
        if not self._log_context_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        for message in getattr(plan, "messages", ()) or ():
            self.append_log(str(message))
        if bool(getattr(plan, "refresh_learned", False)):
            self._update_learned_domains()

    def _on_log_context_action_failed(self, request_id: int, _action: str, error: str) -> None:
        if not self._log_context_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка действия контекстного меню лога: {error}", "ERROR")
        self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=error))

    def _on_log_context_action_worker_finished(self, worker) -> None:
        pending = self._log_context_action_state_obj().pop_next_after_finish(
            worker,
            is_current_worker_finish=self._is_current_worker_finish,
            cleanup_in_progress=self._cleanup_in_progress,
        )
        if pending is None:
            return
        self._schedule_log_context_action_worker_start(pending)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        if runtime is None:
            return False
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _schedule_log_context_action_worker_start(self, payload) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        action, domain, strategy, protocol = payload
        queued = (
            str(action or "").strip(),
            str(domain or "").strip(),
            int(strategy or 0),
            str(protocol or "").strip(),
        )
        state = self._log_context_action_state_obj()
        if state.start_scheduled:
            self._queue_log_context_action(queued)
            return
        state.start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_log_context_action_worker_start(value))

    def _run_scheduled_log_context_action_worker_start(self, payload) -> None:
        self._log_context_action_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_log_context_action_worker(payload)

    def _log_context_action_state_obj(self) -> QueuedWorkerState[tuple[str, str, int, str]]:
        state = self.__dict__.get("_log_context_action_state")
        runtime = self.__dict__.get("_log_context_action_runtime")
        if state is None:
            pending = [
                (
                    str(action or "").strip(),
                    str(domain or "").strip(),
                    int(strategy or 0),
                    str(protocol or "").strip(),
                )
                for action, domain, strategy, protocol in list(
                    self.__dict__.pop("_log_context_action_pending", []) or []
                )
            ]
            start_scheduled = bool(self.__dict__.pop("_log_context_action_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_log_context_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _log_context_action_pending(self) -> list[tuple[str, str, int, str]]:
        return self._log_context_action_state_obj().pending

    @_log_context_action_pending.setter
    def _log_context_action_pending(self, value) -> None:
        self._log_context_action_state_obj().pending = [
            (
                str(action or "").strip(),
                str(domain or "").strip(),
                int(strategy or 0),
                str(protocol or "").strip(),
            )
            for action, domain, strategy, protocol in list(value or [])
        ]

    @property
    def _log_context_action_start_scheduled(self) -> bool:
        return bool(self._log_context_action_state_obj().start_scheduled)

    @_log_context_action_start_scheduled.setter
    def _log_context_action_start_scheduled(self, value: bool) -> None:
        self._log_context_action_state_obj().start_scheduled = bool(value)

    def _lock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Залочивает стратегию из контекстного меню лога"""
        self._request_log_context_action("lock", domain, strategy, protocol)

    def _block_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Блокирует стратегию из контекстного меню лога"""
        self._request_log_context_action("block", domain, strategy, protocol)

    def _unblock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Разблокирует стратегию из контекстного меню лога"""
        self._request_log_context_action("unblock", domain, strategy, protocol)

    def _add_to_whitelist_from_log(self, domain: str):
        """Добавляет домен в whitelist из контекстного меню лога"""
        self._request_log_context_action("whitelist", domain)
