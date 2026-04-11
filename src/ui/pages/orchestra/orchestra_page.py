# ui/pages/orchestra/orchestra_page.py
"""Страница оркестратора автоматического обучения (circular)"""

from queue import Queue, Empty
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame,
    QLineEdit, QListWidget, QListWidgetItem, QComboBox
)
from PyQt6.QtGui import QFont, QTextCursor, QAction
import qtawesome as qta

from orchestra.page_controller import OrchestraPageController
from ..base_page import BasePage
from ui.popup_menu import exec_popup_menu
from ui.theme import get_theme_tokens
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


from ui.compat_widgets import set_tooltip
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
        return [
            ("all", self._tr("page.orchestra.filter.protocol.all", "Все")),
            ("tls", self._tr("page.orchestra.filter.protocol.tls", "TLS")),
            ("http", self._tr("page.orchestra.filter.protocol.http", "HTTP")),
            ("udp", self._tr("page.orchestra.filter.protocol.udp", "UDP")),
            ("success", self._tr("page.orchestra.filter.protocol.success", "SUCCESS")),
            ("fail", self._tr("page.orchestra.filter.protocol.fail", "FAIL")),
        ]

    def _set_protocol_filter_items(self) -> None:
        if not hasattr(self, "log_protocol_filter") or self.log_protocol_filter is None:
            return

        selected = None
        try:
            selected = self.log_protocol_filter.currentData()
        except Exception:
            selected = None

        self.log_protocol_filter.blockSignals(True)
        self.log_protocol_filter.clear()
        for code, label in self._protocol_filter_items():
            try:
                self.log_protocol_filter.addItem(label, userData=code)
            except TypeError:
                self.log_protocol_filter.addItem(label)
        self.log_protocol_filter.blockSignals(False)

        if selected is not None:
            for idx, (code, _) in enumerate(self._protocol_filter_items()):
                if code == selected:
                    self.log_protocol_filter.setCurrentIndex(idx)
                    break

    def _current_protocol_filter_code(self) -> str:
        try:
            code = self.log_protocol_filter.currentData()
            if isinstance(code, str) and code:
                return code
        except Exception:
            pass

        value = self.log_protocol_filter.currentText().strip().lower()
        mapping = {
            "все": "all",
            "all": "all",
            "tls": "tls",
            "http": "http",
            "udp": "udp",
            "success": "success",
            "fail": "fail",
        }
        return mapping.get(value, "all")

    def _build_ui(self):
        """Строит UI страницы"""

        # === Статус карточка ===
        status_card, status_layout, status_title = self._create_card(
            self._tr("page.orchestra.training_status", "Статус обучения")
        )
        self._status_card_title = status_title

        # Статус
        status_row = QHBoxLayout()
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(24, 24)
        self.status_label = BodyLabel(self._tr("page.orchestra.status.not_started", "Не запущен"))
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        # Информация о режимах
        info_label = CaptionLabel(
            self._tr(
                "page.orchestra.status.modes",
                "• IDLE - ожидание соединений\n"
                "• LEARNING - перебирает стратегии\n"
                "• RUNNING - работает на лучших стратегиях\n"
                "• UNLOCKED - переобучение (RST блокировка)",
            )
        )
        self._info_label = info_label
        status_layout.addWidget(info_label)

        self.layout.addWidget(status_card)

        # === Лог карточка ===
        log_card, log_layout, log_title = self._create_card(
            self._tr("page.orchestra.log", "Лог обучения")
        )
        self._log_card_title = log_title

        # Текстовое поле для логов
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(300)
        self.log_text.setPlaceholderText(
            self._tr("page.orchestra.log.placeholder", "Логи обучения будут отображаться здесь...")
        )
        # Контекстное меню для блокировки стратегий
        self.log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_text.customContextMenuRequested.connect(self._show_log_context_menu)
        log_layout.addWidget(self.log_text)

        # === Фильтры лога ===
        filter_row = QHBoxLayout()

        filter_label = BodyLabel(self._tr("page.orchestra.filter.label", "Фильтр:"))
        self._filter_label = filter_label
        filter_row.addWidget(filter_label)

        # Поле ввода для фильтра по домену
        self.log_filter_input = (LineEdit if _HAS_FLUENT else QLineEdit)()
        self.log_filter_input.setPlaceholderText(
            self._tr("page.orchestra.filter.domain.placeholder", "Домен (например: youtube.com)")
        )
        self.log_filter_input.textChanged.connect(self._apply_log_filter)
        filter_row.addWidget(self.log_filter_input, 2)

        # Комбобокс для фильтра по протоколу
        self.log_protocol_filter = (ComboBox if _HAS_FLUENT else QComboBox)()
        self._set_protocol_filter_items()
        self.log_protocol_filter.currentTextChanged.connect(self._apply_log_filter)
        filter_row.addWidget(self.log_protocol_filter)

        # Кнопка сброса фильтра
        clear_filter_btn = TransparentToolButton(self)
        self._clear_filter_btn = clear_filter_btn
        set_tooltip(
            clear_filter_btn,
            self._tr("page.orchestra.filter.clear.tooltip", "Сбросить фильтр"),
        )
        clear_filter_btn.setFixedSize(28, 28)
        clear_filter_btn.clicked.connect(self._clear_log_filter)
        filter_row.addWidget(clear_filter_btn)

        log_layout.addLayout(filter_row)

        # Кнопки - ряд 1
        btn_row1 = QHBoxLayout()

        self.clear_log_btn = FluentPushButton()
        self.clear_log_btn.setText(self._tr("page.orchestra.button.clear_log", "Очистить лог"))
        self.clear_log_btn.setIcon(qta.icon("fa5s.broom", color="white"))
        self.clear_log_btn.setIconSize(QSize(16, 16))
        self.clear_log_btn.setFixedHeight(32)
        self.clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_log_btn.clicked.connect(self._clear_log)
        btn_row1.addWidget(self.clear_log_btn)

        self.clear_learned_btn = FluentPushButton()
        self.clear_learned_btn.setText(
            self._tr("page.orchestra.button.clear_learning", "Сбросить обучение")
        )
        self.clear_learned_btn.setIconSize(QSize(16, 16))
        self.clear_learned_btn.setFixedHeight(32)
        self.clear_learned_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_learned_btn.clicked.connect(self._on_clear_learned_clicked)
        btn_row1.addWidget(self.clear_learned_btn)

        btn_row1.addStretch()
        log_layout.addLayout(btn_row1)

        # Кнопки залоченных/заблокированных стратегий перенесены в отдельные страницы:
        # - OrchestraLockedPage (Залоченные)
        # - OrchestraBlockedPage (Заблокированные)

        self.layout.addWidget(log_card)

        # === История логов ===
        log_history_card, log_history_layout, log_history_title = self._create_card(
            self._tr(
                "page.orchestra.log_history.title",
                "История логов (макс. {max_logs})",
                max_logs=MAX_ORCHESTRA_LOGS,
            )
        )
        self._log_history_card_title = log_history_title

        # Описание
        log_history_desc = CaptionLabel(
            self._tr(
                "page.orchestra.log_history.desc",
                "Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.",
            )
        )
        self._log_history_desc = log_history_desc
        log_history_desc.setWordWrap(True)
        log_history_layout.addWidget(log_history_desc)

        # Список логов
        self.log_history_list = (ListWidget if _HAS_FLUENT and ListWidget else QListWidget)()
        self.log_history_list.setMaximumHeight(150)
        self.log_history_list.itemDoubleClicked.connect(self._view_log_history)
        log_history_layout.addWidget(self.log_history_list)

        # Кнопки управления историей логов
        log_history_buttons = QHBoxLayout()

        view_log_btn = FluentPushButton()
        self._view_log_btn = view_log_btn
        view_log_btn.setText(self._tr("page.orchestra.button.view_log", "Просмотреть"))
        view_log_btn.setIconSize(QSize(16, 16))
        view_log_btn.setFixedHeight(32)
        view_log_btn.clicked.connect(self._view_log_history)
        log_history_buttons.addWidget(view_log_btn)

        delete_log_btn = FluentPushButton()
        self._delete_log_btn = delete_log_btn
        delete_log_btn.setText(self._tr("page.orchestra.button.delete_log", "Удалить"))
        delete_log_btn.setIconSize(QSize(16, 16))
        delete_log_btn.setFixedHeight(32)
        delete_log_btn.clicked.connect(self._delete_log_history)
        log_history_buttons.addWidget(delete_log_btn)

        log_history_buttons.addStretch()

        clear_all_logs_btn = FluentPushButton()
        clear_all_logs_btn.setText(self._tr("page.orchestra.button.clear_all_logs", "Очистить все"))
        self._clear_all_logs_btn = clear_all_logs_btn
        clear_all_logs_btn.setIconSize(QSize(16, 16))
        clear_all_logs_btn.setFixedHeight(32)
        clear_all_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_logs_btn.clicked.connect(self._clear_all_log_history)
        log_history_buttons.addWidget(clear_all_logs_btn)

        log_history_layout.addLayout(log_history_buttons)
        self.layout.addWidget(log_history_card)

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
            self._clear_filter_btn.setIcon(qta.icon("mdi.close", color=tokens.fg_faint))

        if self.clear_log_btn is not None:
            self.clear_log_btn.setIcon(qta.icon("fa5s.broom", color=tokens.fg))

        if self._clear_all_logs_btn is not None:
            self._clear_all_logs_btn.setIcon(qta.icon("fa5s.trash-alt", color=tokens.fg))

        if self.clear_learned_btn is not None:
            self._update_clear_learned_button_icon()

        if self._view_log_btn is not None:
            self._view_log_btn.setIcon(qta.icon("fa5s.eye", color=tokens.fg))

        if self._delete_log_btn is not None:
            self._delete_log_btn.setIcon(qta.icon("fa5s.trash-alt", color=tokens.fg))

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
        self.status_icon.setPixmap(qta.icon("mdi.brain", color=plan.icon_color).pixmap(24, 24))
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
        self.clear_learned_btn.setIcon(qta.icon(plan.icon_name, color=plan.icon_color))

    def _reset_clear_learned_button(self) -> None:
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
            self.clear_learned_btn.setIcon(qta.icon(plan.icon_name, color=plan.icon_color))

    def _on_clear_learned_clicked(self) -> None:
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
                self.clear_learned_btn.setIcon(qta.icon(plan.icon_name, color=plan.icon_color))
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
            self.clear_learned_btn.setIcon(qta.icon(plan.icon_name, color=plan.icon_color))
        self._clear_learned_reset_timer.start(3000)

    def _clear_learned(self):
        """Сбрасывает данные обучения"""
        self.clear_learned_requested.emit()
        self.append_log(
            self._tr("page.orchestra.log.learned_cleared", "[INFO] Данные обучения сброшены")
        )
        self._update_domains({})

    def _update_all(self):
        """Обновляет статус, данные обучения, историю и whitelist"""
        try:
            app = self.window()
            runner_alive = False
            if hasattr(app, 'dpi_starter') and app.dpi_starter:
                runner_alive = bool(app.dpi_starter.check_process_running_wmi(silent=True))

            plan = OrchestraPageController.build_update_cycle_plan(runner_alive=runner_alive)
            if plan.next_state == self.STATE_IDLE:
                self._update_status(self.STATE_IDLE)
            if plan.refresh_learned:
                self._update_learned_domains()
            if plan.refresh_history:
                self._update_log_history()
        except Exception:
            pass

    def _on_log_received(self, text: str):
        """Обработчик сигнала - добавляет лог и определяет состояние"""
        self.append_log(text)
        self._detect_state_from_line(text)

    def emit_log(self, text: str):
        """Публичный метод для отправки логов (вызывается из callback runner'а).
        Thread-safe: использует очередь вместо прямого emit сигнала.
        """
        # Кладём в очередь - это thread-safe операция
        self._log_queue.put(text)

    def _process_log_queue(self):
        """Обрабатывает очередь логов из main thread (вызывается таймером)"""
        # Обрабатываем до 20 сообщений за раз чтобы не блокировать UI
        for _ in range(20):
            try:
                text = self._log_queue.get_nowait()
                self.log_received.emit(text)
            except Empty:
                break

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
        plan = OrchestraPageController.detect_state_from_line(
            line=line,
            current_state=self._current_state,
            idle_state=self.STATE_IDLE,
            learning_state=self.STATE_LEARNING,
            running_state=self.STATE_RUNNING,
            unlocked_state=self.STATE_UNLOCKED,
        )
        if plan.next_state:
            self._update_status(plan.next_state)

    def _update_learned_domains(self):
        """Обновляет данные обученных доменов из реестра через runner"""
        try:
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
            plan = OrchestraPageController.build_learned_data_plan_from_runner(runner)
            self._update_domains(plan.data)
        except Exception as e:
            log(f"Ошибка чтения обученных доменов: {e}", "DEBUG")

    def _update_domains(self, _data: dict):
        """Данные обученных доменов теперь отображаются на вкладке Залоченное"""
        pass  # Виджет перемещён в orchestra/locked_page.py

    def append_log(self, text: str):
        """Добавляет строку в лог"""
        # Сохраняем в полный лог
        self._full_log_lines.append(text)
        # Ограничиваем размер
        if len(self._full_log_lines) > self._max_log_lines:
            self._full_log_lines = self._full_log_lines[-self._max_log_lines:]

        # Проверяем фильтр
        if self._matches_filter(text):
            self.log_text.append(text)
            # Прокручиваем вниз
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

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
        filtered_lines = OrchestraPageController.filter_lines(
            lines=self._full_log_lines,
            domain_filter=self.log_filter_input.text().strip().lower(),
            protocol_filter=self._current_protocol_filter_code(),
        )

        # Обновляем виджет лога
        self.log_text.clear()
        for line in filtered_lines:
            self.log_text.append(line)

        # Прокручиваем вниз
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def _clear_log_filter(self):
        """Сбрасывает фильтр"""
        self.log_filter_input.clear()
        self.log_protocol_filter.setCurrentIndex(0)
        self._apply_log_filter()

    @pyqtSlot()
    def start_monitoring(self):
        """Запускает мониторинг"""
        # Подключаем callback к runner если он уже запущен (при автозапуске callback не устанавливается)
        try:
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
            OrchestraPageController.ensure_output_callback(runner, self.emit_log)
        except Exception:
            pass

        plan = OrchestraPageController.build_start_monitoring_plan()
        if plan.reset_log_position:
            self._last_log_position = 0
        if plan.queue_timer_interval_ms is not None:
            self._log_queue_timer.start(plan.queue_timer_interval_ms)
        if plan.update_timer_interval_ms is not None:
            self.update_timer.start(plan.update_timer_interval_ms)
        if plan.run_update_now:
            self._update_all()

    def stop_monitoring(self):
        """Останавливает мониторинг"""
        plan = OrchestraPageController.build_stop_monitoring_plan()
        if plan.queue_timer_interval_ms is None:
            self._log_queue_timer.stop()
        if plan.update_timer_interval_ms is None:
            self.update_timer.stop()

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

        if self._status_card_title is not None:
            self._status_card_title.setText(
                self._tr("page.orchestra.training_status", "Статус обучения")
            )
        if self._log_card_title is not None:
            self._log_card_title.setText(self._tr("page.orchestra.log", "Лог обучения"))
        if self._log_history_card_title is not None:
            self._log_history_card_title.setText(
                self._tr(
                    "page.orchestra.log_history.title",
                    "История логов (макс. {max_logs})",
                    max_logs=MAX_ORCHESTRA_LOGS,
                )
            )

        if self._info_label is not None:
            self._info_label.setText(
                self._tr(
                    "page.orchestra.status.modes",
                    "• IDLE - ожидание соединений\n"
                    "• LEARNING - перебирает стратегии\n"
                    "• RUNNING - работает на лучших стратегиях\n"
                    "• UNLOCKED - переобучение (RST блокировка)",
                )
            )
        if self.log_text is not None:
            self.log_text.setPlaceholderText(
                self._tr("page.orchestra.log.placeholder", "Логи обучения будут отображаться здесь...")
            )
        if self._filter_label is not None:
            self._filter_label.setText(self._tr("page.orchestra.filter.label", "Фильтр:"))

        if self.log_filter_input is not None:
            self.log_filter_input.setPlaceholderText(
                self._tr("page.orchestra.filter.domain.placeholder", "Домен (например: youtube.com)")
            )

        self._set_protocol_filter_items()

        if self._clear_filter_btn is not None:
            set_tooltip(
                self._clear_filter_btn,
                self._tr("page.orchestra.filter.clear.tooltip", "Сбросить фильтр"),
            )

        if self.clear_log_btn is not None:
            self.clear_log_btn.setText(self._tr("page.orchestra.button.clear_log", "Очистить лог"))

        if self.clear_learned_btn is not None:
            done_ru = "✓ Сброшено"
            done_en = "✓ Reset"
            current = self.clear_learned_btn.text()
            if self._clear_learned_pending:
                self.clear_learned_btn.setText(
                    self._tr("page.orchestra.button.clear_learning.pending", "Это всё сотрёт!")
                )
            elif current in (done_ru, done_en):
                self.clear_learned_btn.setText(
                    self._tr("page.orchestra.button.clear_learning.done", "✓ Сброшено")
                )
            else:
                self.clear_learned_btn.setText(
                    self._tr("page.orchestra.button.clear_learning", "Сбросить обучение")
                )

        if self._log_history_desc is not None:
            self._log_history_desc.setText(
                self._tr(
                    "page.orchestra.log_history.desc",
                    "Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.",
                )
            )
        if self._view_log_btn is not None:
            self._view_log_btn.setText(self._tr("page.orchestra.button.view_log", "Просмотреть"))
        if self._delete_log_btn is not None:
            self._delete_log_btn.setText(self._tr("page.orchestra.button.delete_log", "Удалить"))
        if self._clear_all_logs_btn is not None:
            self._clear_all_logs_btn.setText(self._tr("page.orchestra.button.clear_all_logs", "Очистить все"))

        self._update_status(getattr(self, "_current_state", self.STATE_IDLE))
        self._update_log_history()
        self._apply_log_filter()

    # ==================== LOG HISTORY METHODS ====================

    def _update_log_history(self):
        """Обновляет список истории логов"""
        self.log_history_list.clear()

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                logs = app.orchestra_runner.get_log_history()
                plan = OrchestraPageController.build_log_history_plan(
                    logs=logs,
                    current_suffix_text=self._tr("page.orchestra.log_history.current_suffix", " (текущий)"),
                    none_text=self._tr("page.orchestra.log_history.none", "  Нет сохранённых логов"),
                )

                for entry in plan.entries:
                    item = QListWidgetItem(entry.text)
                    item.setData(Qt.ItemDataRole.UserRole, entry.log_id)

                    if entry.is_current:
                        item.setForeground(Qt.GlobalColor.green)
                    elif entry.is_placeholder:
                        item.setForeground(Qt.GlobalColor.gray)

                    self.log_history_list.addItem(item)

        except Exception as e:
            log(f"Ошибка обновления истории логов: {e}", "DEBUG")

    def _view_log_history(self):
        """Просматривает выбранный лог из истории"""
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                content = app.orchestra_runner.get_log_content(log_id)
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
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                deleted = bool(app.orchestra_runner.delete_log(log_id))
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
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                deleted = app.orchestra_runner.clear_all_logs()
                plan = OrchestraPageController.build_log_history_clear_all_plan(
                    deleted_count=deleted,
                )
                self._update_log_history()
                self.append_log(plan.message_text)
        except Exception as e:
            log(f"Ошибка очистки истории логов: {e}", "DEBUG")

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
                app = self.window()
                if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                    is_blocked = app.orchestra_runner.blocked_manager.is_blocked(domain, strategy)
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
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
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
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
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
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
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
            app = self.window()
            runner = app.orchestra_runner if hasattr(app, 'orchestra_runner') else None
            plan = OrchestraPageController.add_to_whitelist(runner, domain=domain)
            for message in plan.messages:
                self.append_log(message)
        except Exception as e:
            log(f"Ошибка добавления в whitelist из контекстного меню: {e}", "ERROR")
            self.append_log(self._tr("page.orchestra.log.error", "[ERROR] Ошибка: {error}", error=e))
