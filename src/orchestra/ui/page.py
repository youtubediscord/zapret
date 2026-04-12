# orchestra/ui/page.py
"""Страница оркестратора автоматического обучения (circular)"""

from queue import Queue
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel,
    QPushButton, QFrame,
    QLineEdit, QListWidget, QComboBox
)
from PyQt6.QtGui import QAction

from orchestra.page_controller import OrchestraPageController
from ui.page_dependencies import resolve_page_orchestra_runner
from ui.pages.base_page import BasePage
from orchestra.ui.page_build import (
    build_orchestra_log_card,
    build_orchestra_log_history_card,
    build_orchestra_status_card,
)
from orchestra.ui.page_runtime_helpers import (
    append_log_line,
    apply_log_filter_to_view,
    apply_orchestra_language,
    current_protocol_filter_code,
    protocol_filter_items,
    set_protocol_filter_items,
    update_log_history_view,
)
from orchestra.ui.page_monitoring_workflow import (
    detect_state_transition_from_line,
    process_log_queue,
    run_update_cycle,
    start_monitoring as start_orchestra_monitoring,
    stop_monitoring as stop_orchestra_monitoring,
)
from ui.popup_menu import exec_popup_menu
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel, PushButton as FluentPushButton,
        LineEdit, ComboBox, ListWidget, RoundMenu, CardWidget, TransparentToolButton,
    )
    _HAS_FLUENT = True
except ImportError:
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    FluentPushButton = QPushButton
    LineEdit = QLineEdit
    ComboBox = QComboBox
    ListWidget = QListWidget
    RoundMenu = None
    CardWidget = QFrame
    TransparentToolButton = QPushButton
    _HAS_FLUENT = False


from log import log
from orchestra import MAX_ORCHESTRA_LOGS
from orchestra.ignored_targets import is_orchestra_ignored_target


class OrchestraPage(BasePage):
    """Страница оркестратора с логами обучения"""

    clear_learned_requested = pyqtSignal()  # Сигнал очистки данных обучения
    log_received = pyqtSignal(str)  # Сигнал для получения логов из потока runner'а

    # Состояния оркестратора
    STATE_IDLE = "idle"          # Нет активности (серый)
    STATE_RUNNING = "running"    # Работает на залоченной стратегии (зелёный)
    STATE_LEARNING = "learning"  # Перебирает стратегии (оранжевый)
    STATE_UNLOCKED = "unlocked"  # RST блокировка, переобучение (красный)

    def __init__(self, parent=None):
        super().__init__(
            "Оркестратор v0.9.6 (Beta)",
            "Автоматическое обучение стратегий DPI bypass. Система находит лучшую стратегию для каждого домена (TCP: TLS/HTTP, UDP: QUIC/Discord Voice/STUN).\nЧтобы начать обучение зайдите на сайт и через несколько секунд обновите вкладку. Продолжайте это пока стратегия не будет помечена как LOCKED",
            parent,
            title_key="page.orchestra.title",
            subtitle_key="page.orchestra.subtitle",
        )

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

        title_label = StrongBodyLabel(title, card) if _HAS_FLUENT else QLabel(title)
        if not _HAS_FLUENT:
            title_label.setStyleSheet("font-size: 14px; font-weight: 600;")
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
            has_fluent=_HAS_FLUENT,
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
            has_fluent=_HAS_FLUENT,
            list_widget_cls=ListWidget,
            qlist_widget_cls=QListWidget,
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
            self._clear_filter_btn.setIcon(get_themed_qta_icon("mdi.close", color=tokens.fg_faint))

        if self.clear_log_btn is not None:
            self.clear_log_btn.setIcon(get_themed_qta_icon("fa5s.broom", color=tokens.fg))

        if self._clear_all_logs_btn is not None:
            self._clear_all_logs_btn.setIcon(get_themed_qta_icon("fa5s.trash-alt", color=tokens.fg))

        if self.clear_learned_btn is not None:
            self._update_clear_learned_button_icon()

        if self._view_log_btn is not None:
            self._view_log_btn.setIcon(get_themed_qta_icon("fa5s.eye", color=tokens.fg))

        if self._delete_log_btn is not None:
            self._delete_log_btn.setIcon(get_themed_qta_icon("fa5s.trash-alt", color=tokens.fg))

        self._update_status(getattr(self, "_current_state", self.STATE_IDLE))

    def _update_status(self, state: str):
        """Обновляет статус на основе состояния"""
        self._current_state = state
        tokens = get_theme_tokens()
        plan = OrchestraPageController.build_status_display_plan(
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
        plan = OrchestraPageController.build_clear_learned_button_plan(
            pending=self._clear_learned_pending,
            default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
            pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
            done_text="",
            fg_color=tokens.fg,
        )
        self.clear_learned_btn.setIcon(get_themed_qta_icon(plan.icon_name, color=plan.icon_color))

    def _reset_clear_learned_button(self) -> None:
        if self._cleanup_in_progress:
            return
        self._clear_learned_pending = False
        if self.clear_learned_btn is not None:
            plan = OrchestraPageController.build_clear_learned_button_plan(
                pending=False,
                default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                done_text="",
                fg_color=get_theme_tokens().fg,
            )
            self.clear_learned_btn.setText(plan.text)
            self.clear_learned_btn.setIcon(get_themed_qta_icon(plan.icon_name, color=plan.icon_color))

    def _on_clear_learned_clicked(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._clear_learned_pending:
            self._clear_learned_reset_timer.stop()
            self._clear_learned_pending = False
            if self.clear_learned_btn is not None:
                plan = OrchestraPageController.build_clear_learned_button_plan(
                    pending=False,
                    default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                    pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                    done_text=self._tr("page.orchestra.button.clear_learning.done", "✓ Сброшено"),
                    fg_color=get_theme_tokens().fg,
                )
                self.clear_learned_btn.setText(plan.text)
                self.clear_learned_btn.setIcon(get_themed_qta_icon(plan.icon_name, color=plan.icon_color))
            self._clear_learned()
            QTimer.singleShot(1500, self._reset_clear_learned_button)
            return

        self._clear_learned_pending = True
        if self.clear_learned_btn is not None:
            plan = OrchestraPageController.build_clear_learned_button_plan(
                pending=True,
                default_text=self._tr("page.orchestra.button.clear_learning", "Сбросить обучение"),
                pending_text=self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!"),
                done_text="",
                fg_color=get_theme_tokens().fg,
            )
            self.clear_learned_btn.setText(plan.text)
            self.clear_learned_btn.setIcon(get_themed_qta_icon(plan.icon_name, color=plan.icon_color))
        self._clear_learned_reset_timer.start(3000)

    def _clear_learned(self):
        """Сбрасывает данные обучения"""
        if self._cleanup_in_progress:
            return
        self.clear_learned_requested.emit()
        self.append_log(
            self._tr("page.orchestra.log.learned_cleared", "[INFO] Данные обучения сброшены")
        )
        self._update_domains({})

    def _update_all(self):
        """Обновляет статус, данные обучения, историю и whitelist"""
        if self._cleanup_in_progress:
            return
        run_update_cycle(
            is_runner_alive=lambda: bool(
                getattr(getattr(self, "launch_runtime_api", None), "is_any_running", lambda silent=True: False)(silent=True)
            ),
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
        # Кладём в очередь - это thread-safe операция
        self._log_queue.put(text)

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
        """Обновляет данные обученных доменов из реестра через runner"""
        if self._cleanup_in_progress:
            return
        try:
            runner = getattr(self, "orchestra_runner", None)
            plan = OrchestraPageController.build_learned_data_plan_from_runner(runner)
            self._update_domains(plan.data)
        except Exception as e:
            log(f"Ошибка чтения обученных доменов: {e}", "DEBUG")

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
        return OrchestraPageController.matches_filter(
            text=text,
            domain_filter=domain_filter,
            protocol_filter=protocol_filter,
        )

    def _apply_log_filter(self):
        """Применяет фильтр к логу"""
        if self._cleanup_in_progress:
            return
        apply_log_filter_to_view(
            lines=self._full_log_lines,
            domain_filter=self.log_filter_input.text().strip().lower(),
            protocol_filter=self._current_protocol_filter_code(),
            log_text=self.log_text,
        )

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
        runner = getattr(self, "orchestra_runner", None)
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
        """Скрытие страницы не должно выключать runtime оркестратора."""
        pass

    def set_learned_data(self, data: dict):
        """Устанавливает данные обучения"""
        self._update_domains(data)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_orchestra_language(
            tr_fn=self._tr,
            current_state=getattr(self, "_current_state", self.STATE_IDLE),
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
        try:
            runner = self._get_runner()
            if runner is not None:
                update_log_history_view(
                    runner=runner,
                    tr_fn=self._tr,
                    log_history_list=self.log_history_list,
                )

        except Exception as e:
            log(f"Ошибка обновления истории логов: {e}", "DEBUG")

    def _view_log_history(self):
        """Просматривает выбранный лог из истории"""
        if self._cleanup_in_progress:
            return
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            runner = self._get_runner()
            if runner is not None:
                content = runner.get_log_content(log_id)
                plan = OrchestraPageController.build_log_history_view_plan(
                    log_id=log_id,
                    has_content=bool(content),
                )
                if content:
                    # Очищаем текущий лог и показываем содержимое выбранного
                    self.log_text.clear()
                    self.log_text.setPlainText(content)
                    self.append_log(plan.message_text)
                else:
                    self.append_log(plan.message_text)
        except Exception as e:
            log(f"Ошибка просмотра лога: {e}", "DEBUG")

    def _delete_log_history(self):
        """Удаляет выбранный лог из истории"""
        if self._cleanup_in_progress:
            return
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            runner = self._get_runner()
            if runner is not None:
                deleted = bool(runner.delete_log(log_id))
                plan = OrchestraPageController.build_log_history_delete_plan(
                    log_id=log_id,
                    deleted=deleted,
                )
                if deleted:
                    self._update_log_history()
                    self.append_log(plan.message_text)
                else:
                    self.append_log(plan.message_text)
        except Exception as e:
            log(f"Ошибка удаления лога: {e}", "DEBUG")

    def _clear_all_log_history(self):
        """Удаляет все логи из истории"""
        if self._cleanup_in_progress:
            return
        try:
            runner = self._get_runner()
            if runner is not None:
                deleted = runner.clear_all_logs()
                plan = OrchestraPageController.build_log_history_clear_all_plan(
                    deleted_count=deleted,
                )
                self._update_log_history()
                self.append_log(plan.message_text)
        except Exception as e:
            log(f"Ошибка очистки истории логов: {e}", "DEBUG")

    def _get_runner(self):
        return resolve_page_orchestra_runner(self, parent=self.parent())

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._clear_learned_pending = False
        self.stop_monitoring()
        self._clear_learned_reset_timer.stop()

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
        # Получаем текущую строку под курсором
        cursor = self.log_text.cursorForPosition(pos)
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText().strip()

        if not line_text:
            return

        # Парсим строку для извлечения домена и стратегии
        parsed = self._parse_log_line_for_strategy(line_text)

        # Создаём контекстное меню
        if _HAS_FLUENT and RoundMenu:
            menu = RoundMenu(parent=self)
        else:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)

        context_plan = None
        if parsed:
            domain, strategy, protocol = parsed
            is_blocked = False
            try:
                runner = self._get_runner()
                if runner is not None:
                    is_blocked = runner.blocked_manager.is_blocked(domain, strategy)
            except Exception:
                pass

            context_plan = OrchestraPageController.build_context_menu_plan(
                domain=domain,
                strategy=strategy,
                is_blocked=is_blocked,
                copy_label=self._tr("page.orchestra.context.copy_line", "📋 Копировать строку"),
                lock_label=self._tr(
                    "page.orchestra.context.lock_strategy",
                    "🔒 Залочить стратегию #{strategy} для {domain}",
                    strategy=strategy,
                    domain=domain,
                ) if strategy > 0 else None,
                block_label=self._tr(
                    "page.orchestra.context.block_strategy",
                    "🚫 Заблокировать стратегию #{strategy} для {domain}",
                    strategy=strategy,
                    domain=domain,
                ) if strategy > 0 else None,
                unblock_label=self._tr(
                    "page.orchestra.context.unblock_strategy",
                    "✅ Разблокировать стратегию #{strategy} для {domain}",
                    strategy=strategy,
                    domain=domain,
                ) if strategy > 0 else None,
                whitelist_label=self._tr(
                    "page.orchestra.context.add_whitelist",
                    "⬚ Добавить {domain} в белый список",
                    domain=domain,
                ),
            )
        else:
            context_plan = OrchestraPageController.build_context_menu_plan(
                domain=None,
                strategy=None,
                is_blocked=False,
                copy_label=self._tr("page.orchestra.context.copy_line", "📋 Копировать строку"),
                lock_label=None,
                block_label=None,
                unblock_label=None,
                whitelist_label=None,
            )

        actions_by_id: dict[str, QAction] = {}
        for action_plan in context_plan.actions:
            action = QAction(action_plan.label, self)
            actions_by_id[action_plan.action_id] = action
            menu.addAction(action)

        copy_action = actions_by_id.get("copy")
        if copy_action is not None:
            copy_action.triggered.connect(lambda: self._copy_line_to_clipboard(line_text))

        if parsed and context_plan.has_strategy_actions:
            domain, strategy, protocol = parsed
            menu.insertSeparator(actions_by_id.get("copy"))
            if "lock" in actions_by_id:
                actions_by_id["lock"].triggered.connect(lambda: self._lock_strategy_from_log(domain, strategy, protocol))
            if "block" in actions_by_id:
                actions_by_id["block"].triggered.connect(lambda: self._block_strategy_from_log(domain, strategy, protocol))
            if "unblock" in actions_by_id:
                actions_by_id["unblock"].triggered.connect(lambda: self._unblock_strategy_from_log(domain, strategy, protocol))
            if "whitelist" in actions_by_id:
                actions_by_id["whitelist"].triggered.connect(lambda: self._add_to_whitelist_from_log(domain))

        exec_popup_menu(menu, self.log_text.mapToGlobal(pos), owner=self)

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
        parsed = OrchestraPageController.parse_log_line_for_strategy(line)
        if parsed is None:
            return None
        return (parsed.domain, parsed.strategy, parsed.protocol)

    def _copy_line_to_clipboard(self, text: str):
        """Копирует текст в буфер обмена"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.append_log(
                self._tr("page.orchestra.log.clipboard_copied", "[INFO] Строка скопирована в буфер обмена")
            )

    def _lock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Залочивает стратегию из контекстного меню лога"""
        try:
            runner = self._get_runner()
            plan = OrchestraPageController.lock_strategy(
                runner,
                domain=domain,
                strategy=strategy,
                protocol=protocol,
                ignored_target=is_orchestra_ignored_target(domain),
            )
            for message in plan.messages:
                self.append_log(message)
            if plan.refresh_learned:
                self._update_learned_domains()
        except Exception as e:
            log(f"Ошибка залочивания из контекстного меню: {e}", "ERROR")
            self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=e))

    def _block_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Блокирует стратегию из контекстного меню лога"""
        try:
            runner = self._get_runner()
            plan = OrchestraPageController.block_strategy(
                runner,
                domain=domain,
                strategy=strategy,
                protocol=protocol,
                ignored_target=is_orchestra_ignored_target(domain),
            )
            for message in plan.messages:
                self.append_log(message)
            if plan.refresh_learned:
                self._update_learned_domains()
        except Exception as e:
            log(f"Ошибка блокировки из контекстного меню: {e}", "ERROR")
            self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=e))

    def _unblock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Разблокирует стратегию из контекстного меню лога"""
        try:
            runner = self._get_runner()
            plan = OrchestraPageController.unblock_strategy(
                runner,
                domain=domain,
                strategy=strategy,
                protocol=protocol,
            )
            for message in plan.messages:
                self.append_log(message)
            if plan.refresh_learned:
                self._update_learned_domains()
        except Exception as e:
            log(f"Ошибка разблокировки из контекстного меню: {e}", "ERROR")
            self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=e))

    def _add_to_whitelist_from_log(self, domain: str):
        """Добавляет домен в whitelist из контекстного меню лога"""
        try:
            runner = self._get_runner()
            plan = OrchestraPageController.add_to_whitelist(runner, domain=domain)
            for message in plan.messages:
                self.append_log(message)
        except Exception as e:
            log(f"Ошибка добавления в whitelist из контекстного меню: {e}", "ERROR")
            self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=e))
