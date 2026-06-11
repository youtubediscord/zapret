# ui/pages/orchestra/locked_page.py
"""
Страница управления залоченными стратегиями оркестратора.
Каждый домен отображается в виде редактируемого ряда с QSpinBox для номера стратегии.
Изменения автоматически сохраняются в settings.json.
"""
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QWidget,
    QFrame,
)

from ui.pages.base_page import BasePage
from ui.accessibility import set_control_accessibility, set_state_text
from ui.combo_accessibility import set_combo_items_accessibility
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState
from qfluentwidgets import (
    ComboBox,
    FluentIcon,
    SpinBox,
    LineEdit,
    PushButton,
    TransparentToolButton,
    CardWidget,
    StrongBodyLabel,
    MessageBox,
    InfoBar,
    CaptionLabel,
    BodyLabel,
)

from ui.widgets.notification_banner import NotificationBanner
from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding
from app.ui_texts import tr as tr_catalog
from log.log import log

from orchestra.ignored_targets import is_orchestra_ignored_target


class LockedDomainRow(QFrame):
    """Виджет-ряд для одного залоченного домена с редактируемой стратегией"""

    def __init__(
        self,
        domain: str,
        strategy: int,
        proto: str,
        parent=None,
        *,
        delete_tooltip: str = "",
    ):
        super().__init__(parent)
        self.domain = domain
        self.proto = proto
        self._delete_tooltip = delete_tooltip or "Разлочить"
        self._tokens = get_theme_tokens()
        self._current_qss = ""

        self._domain_label = None
        self._proto_label = None
        self._delete_btn = None
        self._setup_ui(domain, strategy, proto)
        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme)

    def _setup_ui(self, domain: str, strategy: int, proto: str):
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # Домен
        domain_label = BodyLabel(domain)
        self._domain_label = domain_label
        layout.addWidget(domain_label, 1)

        # Протокол
        proto_label = CaptionLabel(f"[{proto.upper()}]")
        self._proto_label = proto_label
        proto_label.setFixedWidth(45)
        layout.addWidget(proto_label)

        # Стратегия SpinBox
        self.strat_spin = SpinBox()
        self.strat_spin.setRange(1, 999)
        self.strat_spin.setValue(strategy)
        self.strat_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strat_spin.valueChanged.connect(self._on_strategy_changed)
        layout.addWidget(self.strat_spin)

        # Кнопка удаления (разлочить)
        delete_btn = TransparentToolButton(self)
        self._delete_btn = delete_btn
        delete_btn.setIconSize(QSize(16, 16))
        delete_btn.setFixedSize(28, 28)
        set_tooltip(delete_btn, self._delete_tooltip)
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)

        self._update_accessibility()
        self._apply_theme()

    def refresh_theme(self) -> None:
        self._tokens = get_theme_tokens()
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._tokens or get_theme_tokens("Темная синяя")

        qss = f"""
            LockedDomainRow {{
                background: transparent;
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
            }}
            LockedDomainRow:hover {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border_hover};
            }}
        """
        if qss != self._current_qss:
            self._current_qss = qss
            self.setStyleSheet(qss)

        if self._delete_btn is not None:
            self._delete_btn.setIcon(FluentIcon.REMOVE)

    def _on_strategy_changed(self, value: int):
        """При изменении стратегии - уведомляем родителя для автосохранения"""
        self._update_accessibility(value)
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraLockedPage):
            parent = parent.parent()
        if parent:
            parent._on_row_strategy_changed(self.domain, value, self.proto)

    def _on_delete_clicked(self):
        """При клике на удаление - уведомляем родителя"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraLockedPage):
            parent = parent.parent()
        if parent:
            parent._on_row_delete_requested(self.domain, self.proto)

    def _update_accessibility(self, strategy: int | None = None) -> None:
        selected_strategy = int(strategy if strategy is not None else self.strat_spin.value())
        proto_text = str(self.proto or "").upper()
        strategy_state = f"Стратегия для {self.domain} {proto_text}, выбрано: {selected_strategy}"
        set_control_accessibility(
            self,
            name=f"Залоченная стратегия: {self.domain}, {proto_text}, стратегия {selected_strategy}",
            description="Стратегия зафиксирована для этого домена.",
        )
        set_state_text(self.strat_spin, strategy_state)
        set_control_accessibility(
            self.strat_spin,
            name=strategy_state,
            description="Стрелками вверх и вниз можно изменить номер стратегии. Изменение сохранится автоматически.",
        )
        if self._delete_btn is not None:
            set_control_accessibility(
                self._delete_btn,
                name=f"Разлочить {self.domain} {proto_text}",
                description="Убирает фиксацию стратегии для этого домена.",
            )


class OrchestraLockedPage(BasePage):
    """Страница управления залоченными стратегиями"""

    def __init__(self, parent=None, *, orchestra_feature):
        super().__init__(
            "Залоченные стратегии",
            "Домены с фиксированной стратегией. Оркестратор не будет менять стратегию для этих доменов. Это значит что оркестратор нашёл для этих сайтов наилучшую стратегию. Вы можете зафиксировать свою стратегию для домена здесь.\nЕсли Вас не устраивает текущая стратегия - заблокируйте её здесь и оркестратор начнёт обучение заново при следующем посещении сайта.\nЕсли Вы просто хотите начать обучение заново - разлочьте стратегию.",
            parent,
            title_key="page.orchestra.locked.title",
            subtitle_key="page.orchestra.locked.subtitle",
        )
        self.setObjectName("orchestraLockedPage")
        self._orchestra = orchestra_feature
        self._askey_all = tuple(self._orchestra.ASKEY_ALL)
        self._hint_label = None
        self._add_card = None
        self._list_card = None
        self._all_locked_data = []  # Кэш данных для фильтрации
        self._runtime_initialized = False
        self._refresh_loading = False
        self._cleanup_in_progress = False
        self._snapshot_load_runtime = OneShotWorkerRuntime()
        self._snapshot_load_state = LatestValueWorkerState(
            self._snapshot_load_runtime,
            empty_value=False,
        )
        self._managed_action_runtime = OneShotWorkerRuntime()
        self._managed_action_state = QueuedWorkerState[tuple[str, dict]](
            self._managed_action_runtime,
        )

        self._setup_ui()
        self._apply_page_theme(force=True)

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._reload_from_settings()

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
        if self._cleanup_in_progress:
            return
        self._refresh_loading = loading
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setEnabled(not loading)
            set_tooltip(
                self.refresh_btn,
                self._tr("page.orchestra.locked.button.refresh.tooltip", "Обновить"),
            )
        self._apply_page_theme()

    def _setup_ui(self):
        # === Уведомление (баннер) ===
        self.notification_banner = NotificationBanner(self)
        self.layout.addWidget(self.notification_banner)

        # === Карточка добавления ===
        add_card, add_card_layout = self._create_card(
            self._tr("page.orchestra.locked.card.add", "Залочить стратегию вручную")
        )
        self._add_card = add_card
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        # Домен
        self.domain_input = LineEdit()
        self.domain_input.setPlaceholderText(
            self._tr("page.orchestra.locked.input.domain.placeholder", "example.com")
        )
        add_layout.addWidget(self.domain_input, 1)

        # Протокол (askey)
        self.proto_combo = ComboBox()
        self.proto_combo.addItems([askey.upper() for askey in self._askey_all])
        self.proto_combo.setFixedWidth(90)
        add_layout.addWidget(self.proto_combo)

        # Стратегия
        self.strat_spin = SpinBox()
        self.strat_spin.setRange(1, 999)
        self.strat_spin.setValue(1)
        self.strat_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_layout.addWidget(self.strat_spin)

        # Кнопка добавления
        self.lock_btn = TransparentToolButton(self)
        # Icon styled in _apply_theme()
        self.lock_btn.setIconSize(QSize(18, 18))
        self.lock_btn.setFixedSize(36, 36)
        set_tooltip(
            self.lock_btn,
            self._tr("page.orchestra.locked.button.lock.tooltip", "Залочить стратегию"),
        )
        self.lock_btn.clicked.connect(self._lock_strategy)
        add_layout.addWidget(self.lock_btn)

        add_card_layout.addLayout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка ===
        list_card, list_layout = self._create_card(
            self._tr("page.orchestra.locked.card.list", "Список залоченных")
        )
        self._list_card = list_card
        list_layout.setSpacing(8)

        # Кнопка и счётчик сверху
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Поиск
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.locked.search.placeholder", "Поиск по доменам...")
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_list)
        top_row.addWidget(self.search_input)

        # Кнопка обновления списка из settings.json
        self.refresh_btn = TransparentToolButton(self)
        self.refresh_btn.setFixedSize(32, 32)
        set_tooltip(
            self.refresh_btn,
            self._tr("page.orchestra.locked.button.refresh.tooltip", "Обновить"),
        )
        self.refresh_btn.clicked.connect(self._reload_from_settings)
        top_row.addWidget(self.refresh_btn)

        self.unlock_all_btn = PushButton(
            self._tr("page.orchestra.locked.button.unlock_all", "Разлочить все")
        )
        self.unlock_all_btn.setFixedHeight(32)
        self.unlock_all_btn.clicked.connect(self._unlock_all)
        top_row.addWidget(self.unlock_all_btn)
        top_row.addStretch()

        list_layout.addLayout(top_row)

        # Счётчик на отдельной строке (чтобы влезал в таб)
        self.count_label = CaptionLabel()
        list_layout.addWidget(self.count_label)

        # Подсказка
        hint_label = CaptionLabel(
            self._tr(
                "page.orchestra.locked.hint",
                "Измените номер стратегии и она автоматически сохранится",
            )
        )
        self._hint_label = hint_label
        list_layout.addWidget(hint_label)

        # Контейнер для рядов (без скролла - страница сама прокручивается)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 8, 0, 0)
        self.rows_layout.setSpacing(4)
        list_layout.addWidget(self.rows_container)

        # Храним ссылки на ряды для быстрого доступа
        self._domain_rows = {}

        self.layout.addWidget(list_card)
        self._install_accessibility()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "lock_btn") and self.lock_btn is not None:
            self.lock_btn.setIcon(FluentIcon.ADD)

        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setIcon(FluentIcon.SYNC)

        if hasattr(self, "unlock_all_btn") and self.unlock_all_btn is not None:
            self.unlock_all_btn.setIcon(FluentIcon.REMOVE)

        # Refresh row widgets.
        try:
            for row in list(getattr(self, "_domain_rows", {}).values()):
                if hasattr(row, "refresh_theme"):
                    row.refresh_theme()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._add_card is not None and hasattr(self._add_card, "_title_label"):
            self._add_card._title_label.setText(
                self._tr("page.orchestra.locked.card.add", "Залочить стратегию вручную")
            )
        if self._list_card is not None and hasattr(self._list_card, "_title_label"):
            self._list_card._title_label.setText(
                self._tr("page.orchestra.locked.card.list", "Список залоченных")
            )

        self.domain_input.setPlaceholderText(
            self._tr("page.orchestra.locked.input.domain.placeholder", "example.com")
        )
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.locked.search.placeholder", "Поиск по доменам...")
        )
        self.unlock_all_btn.setText(
            self._tr("page.orchestra.locked.button.unlock_all", "Разлочить все")
        )

        if self._hint_label is not None:
            self._hint_label.setText(
                self._tr(
                    "page.orchestra.locked.hint",
                    "Измените номер стратегии и она автоматически сохранится",
                )
            )

        set_tooltip(
            self.lock_btn,
            self._tr("page.orchestra.locked.button.lock.tooltip", "Залочить стратегию"),
        )
        set_tooltip(
            self.refresh_btn,
            self._tr("page.orchestra.locked.button.refresh.tooltip", "Обновить"),
        )
        self._install_accessibility()

        if self._runtime_initialized:
            self._refresh_data()

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.domain_input,
            name="Домен для залочки стратегии",
            description="Введите домен, например example.com.",
        )
        set_control_accessibility(
            self.proto_combo,
            description="Выберите протокол: TCP или UDP.",
        )
        set_control_accessibility(
            self.strat_spin,
            description="Выберите номер стратегии. Стрелки вверх и вниз меняют значение.",
        )
        set_control_accessibility(
            self.lock_btn,
            name="Залочить стратегию для домена",
            description="Фиксирует выбранную стратегию для указанного домена.",
        )
        set_control_accessibility(
            self.search_input,
            name="Поиск по залоченным доменам",
            description="Фильтрует список залоченных доменов по введённому тексту.",
        )
        set_control_accessibility(
            self.refresh_btn,
            name="Обновить список залоченных стратегий",
            description="Перечитывает список залоченных стратегий из настроек.",
        )
        set_control_accessibility(
            self.unlock_all_btn,
            name="Разлочить все стратегии",
            description="Удаляет все ручные фиксации стратегий.",
        )
        self._update_accessibility_state()
        try:
            self.proto_combo.currentIndexChanged.disconnect(self._update_accessibility_state)
        except Exception:
            pass
        try:
            self.strat_spin.valueChanged.disconnect(self._update_accessibility_state)
        except Exception:
            pass
        self.proto_combo.currentIndexChanged.connect(self._update_accessibility_state)
        self.strat_spin.valueChanged.connect(self._update_accessibility_state)

    def _update_accessibility_state(self, *_args) -> None:
        selected_proto = str(self.proto_combo.currentText() or "").strip() or "не выбрано"
        proto_state = f"Протокол залочки стратегии, выбрано: {selected_proto}"
        strategy_state = f"Номер стратегии для залочки, выбрано: {self.strat_spin.value()}"
        set_state_text(self.proto_combo, proto_state)
        set_state_text(self.strat_spin, strategy_state)
        set_control_accessibility(
            self.proto_combo,
            name=proto_state,
        )
        set_combo_items_accessibility(self.proto_combo, name="Протокол залочки стратегии")
        set_control_accessibility(
            self.strat_spin,
            name=strategy_state,
        )

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()

    def _show_blocked_warning(self, domain: str, strategy: int):
        """
        Показывает предупреждение о заблокированной стратегии.

        Args:
            domain: Домен для которого заблокирована стратегия
            strategy: Номер заблокированной стратегии
        """
        if self._cleanup_in_progress:
            return
        message = self._tr(
            "page.orchestra.locked.warning.blocked_strategy",
            "Стратегия #{strategy} заблокирована для {domain}. Разблокируйте её на странице 'Заблокированные'.",
            strategy=strategy,
            domain=domain,
        )
        self.notification_banner.show_warning(message, auto_hide_ms=7000)

    def _show_ignored_target_warning(self, domain: str) -> None:
        if self._cleanup_in_progress:
            return
        message = self._tr(
            "page.orchestra.locked.warning.ignored_proxy_target",
            "Домен {domain} относится к отдельному Telegram Proxy модулю. Оркестратор не управляет такими целями.",
            domain=domain,
        )
        self.notification_banner.show_warning(message, auto_hide_ms=7000)

    def _refresh_data(self):
        """Обновляет все данные на странице (из памяти)"""
        if self._cleanup_in_progress:
            return
        self._refresh_locked_list()

    def _reload_from_settings(self):
        """Перезагружает данные из settings.json и обновляет список."""
        if self._cleanup_in_progress:
            return
        self._set_refresh_loading(True)
        self._start_snapshot_worker()

    def _start_snapshot_worker(self) -> None:
        if self._cleanup_in_progress:
            return
        state = self._snapshot_load_state_obj()
        if state.is_busy():
            state.pending = True
            return
        state.pending = False
        self._snapshot_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._orchestra.create_locked_snapshot_load_worker(request_id, self),
            on_loaded=self._on_snapshot_loaded,
            on_failed=self._on_snapshot_failed,
            on_finished=self._on_snapshot_worker_finished,
        )

    def _on_snapshot_loaded(self, request_id: int, _snapshot) -> None:
        if not self._snapshot_load_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._refresh_data()
        self._set_refresh_loading(False)

    def _on_snapshot_failed(self, request_id: int, error: str) -> None:
        if not self._snapshot_load_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Ошибка загрузки залоченных стратегий: {error}", "ERROR")
        self._set_refresh_loading(False)

    def _on_snapshot_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_snapshot_load_runtime"), worker):
            return
        if self._snapshot_load_runtime.worker is worker:
            self._snapshot_load_runtime.worker = None
        if self._snapshot_load_state_obj().has_pending() and not self._cleanup_in_progress:
            self._schedule_snapshot_load_start()

    def _schedule_snapshot_load_start(self) -> None:
        self._snapshot_load_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_snapshot_load_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_snapshot_load_start(self) -> None:
        pending = self._snapshot_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is False:
            return
        self._start_snapshot_worker()

    def _snapshot_load_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_snapshot_load_state")
        runtime = self.__dict__.get("_snapshot_load_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_snapshot_load_pending", False))
            start_scheduled = bool(self.__dict__.pop("_snapshot_load_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_snapshot_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _snapshot_load_pending(self) -> bool:
        return bool(self._snapshot_load_state_obj().pending)

    @_snapshot_load_pending.setter
    def _snapshot_load_pending(self, value: bool) -> None:
        self._snapshot_load_state_obj().pending = bool(value)

    @property
    def _snapshot_load_start_scheduled(self) -> bool:
        return bool(self._snapshot_load_state_obj().start_scheduled)

    @_snapshot_load_start_scheduled.setter
    def _snapshot_load_start_scheduled(self, value: bool) -> None:
        self._snapshot_load_state_obj().start_scheduled = bool(value)

    def create_action_worker(self, request_id: int, *, action: str, **kwargs):
        return self._orchestra.create_locked_action_worker(
            request_id,
            action=action,
            parent=self,
            **kwargs,
        )

    def _request_managed_action(self, action: str, **kwargs) -> None:
        if self._cleanup_in_progress:
            return
        payload = (str(action or "").strip(), dict(kwargs))
        if self._managed_action_state_obj().is_busy():
            self._queue_managed_action(payload)
            return
        self._start_managed_action(payload)

    def _queue_managed_action(self, payload: tuple[str, dict]) -> None:
        action, kwargs = payload
        queued = (str(action or "").strip(), dict(kwargs or {}))
        self._managed_action_state_obj().append_unique(queued, key=lambda item: item)

    def _start_managed_action(self, payload: tuple[str, dict]) -> None:
        action, kwargs = payload
        self._managed_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_action_worker(
                request_id,
                action=action,
                **kwargs,
            ),
            on_loaded=self._on_managed_action_loaded,
            on_failed=self._on_managed_action_failed,
            on_finished=self._on_managed_action_worker_finished,
        )

    def _on_managed_action_loaded(self, request_id: int, action: str, payload, context) -> None:
        if not self._managed_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        payload = dict(payload or {})
        context = dict(context or {})
        result = payload.get("result")
        if bool(payload.get("blocked_by_policy")):
            strategy = int(context.get("new_strategy") or context.get("strategy") or 0)
            domain = str(context.get("domain") or "")
            askey = str(context.get("askey") or "")
            self._show_blocked_warning(domain, strategy)
            log(f"[USER] Попытка использовать заблокированную стратегию #{strategy} для {domain}", "WARNING")
            if action == "locked_change":
                self._restore_locked_strategy_spin(
                    domain,
                    askey,
                    int(payload.get("current_strategy") or 1),
                )
            return

        if payload.get("snapshot") is not None:
            self._snapshot_load_runtime.cancel()
            self._refresh_data()

        if action == "locked_add" and bool(getattr(result, "changed", False)):
            self.domain_input.clear()

        if not bool(getattr(result, "restarted", False)) or InfoBar is None:
            return

        if action == "locked_remove":
            content = self._tr(
                "page.orchestra.locked.infobar.unlocked",
                "Стратегия разлочена для {domain}. Оркестратор перезапускается.",
                domain=str(context.get("domain") or ""),
            )
        elif action == "locked_clear":
            content = self._tr(
                "page.orchestra.locked.infobar.unlocked_all",
                "Разлочены все {total} стратегий. Оркестратор перезапускается.",
                total=int(context.get("total") or 0),
            )
        else:
            return

        InfoBar.success(
            title=self._tr("page.orchestra.locked.infobar.applied.title", "Применено"),
            content=content,
            isClosable=True,
            duration=3000,
            parent=self.window(),
        )

    def _on_managed_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if not self._managed_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Не удалось выполнить действие залоченных стратегий ({action}): {error}", "WARNING")

    def _on_managed_action_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_managed_action_runtime"), worker):
            return
        if self._managed_action_runtime.worker is worker:
            self._managed_action_runtime.worker = None
        pending = self._managed_action_state_obj().pop_next_after_finish(
            worker,
            is_current_worker_finish=self._is_current_worker_finish,
            cleanup_in_progress=self._cleanup_in_progress,
        )
        if pending is not None:
            self._schedule_managed_action_start(pending)

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

    def _schedule_managed_action_start(self, payload: tuple[str, dict]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        action, kwargs = payload
        queued = (str(action or "").strip(), dict(kwargs or {}))
        state = self._managed_action_state_obj()
        if state.start_scheduled:
            self._queue_managed_action(queued)
            return
        state.start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_managed_action_start(value))

    def _run_scheduled_managed_action_start(self, payload: tuple[str, dict]) -> None:
        self._managed_action_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_managed_action(payload)

    def _managed_action_state_obj(self) -> QueuedWorkerState[tuple[str, dict]]:
        state = self.__dict__.get("_managed_action_state")
        runtime = self.__dict__.get("_managed_action_runtime")
        if state is None:
            pending = [
                (str(action or "").strip(), dict(kwargs or {}))
                for action, kwargs in list(self.__dict__.pop("_managed_action_pending", []) or [])
            ]
            start_scheduled = bool(self.__dict__.pop("_managed_action_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_managed_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _managed_action_pending(self) -> list[tuple[str, dict]]:
        return self._managed_action_state_obj().pending

    @_managed_action_pending.setter
    def _managed_action_pending(self, value) -> None:
        self._managed_action_state_obj().pending = [
            (str(action or "").strip(), dict(kwargs or {}))
            for action, kwargs in list(value or [])
        ]

    @property
    def _managed_action_start_scheduled(self) -> bool:
        return bool(self._managed_action_state_obj().start_scheduled)

    @_managed_action_start_scheduled.setter
    def _managed_action_start_scheduled(self, value: bool) -> None:
        self._managed_action_state_obj().start_scheduled = bool(value)

    def _restore_locked_strategy_spin(self, domain: str, askey: str, strategy: int) -> None:
        key = f"{domain}:{askey}"
        if key not in self._domain_rows:
            return
        row = self._domain_rows[key]
        row.strat_spin.blockSignals(True)
        row.strat_spin.setValue(int(strategy))
        row.strat_spin.blockSignals(False)

    def _refresh_locked_list(self):
        """Обновляет список залоченных стратегий"""
        if self._cleanup_in_progress:
            return
        # Очищаем старые ряды
        self._domain_rows.clear()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        snapshot = self._orchestra.current_locked_snapshot()
        self._all_locked_data = [(item.domain, item.strategy, item.askey) for item in snapshot.items]

        # Создаём ряды для каждого домена
        for item in snapshot.items:
            row = LockedDomainRow(
                item.domain,
                item.strategy,
                item.askey,
                delete_tooltip=self._tr("page.orchestra.locked.row.unlock.tooltip", "Разлочить"),
            )
            key = f"{item.domain}:{item.askey}"
            self._domain_rows[key] = row
            self.rows_layout.addWidget(row)

        self._update_count()
        self._apply_filter()

    def _filter_list(self, text: str):
        """Фильтрует список по введённому тексту"""
        self._apply_filter()

    def _apply_filter(self):
        """Применяет текущий фильтр к рядам"""
        search = self.search_input.text().lower().strip()
        for key, row in self._domain_rows.items():
            domain = row.domain.lower()
            row.setVisible(search in domain if search else True)

    def _on_row_strategy_changed(self, domain: str, new_strategy: int, askey: str):
        """Автосохранение при изменении стратегии в SpinBox"""
        if is_orchestra_ignored_target(domain):
            self._show_ignored_target_warning(domain)
            self._refresh_data()
            return

        self._request_managed_action(
            "locked_change",
            domain=domain,
            new_strategy=new_strategy,
            askey=askey,
        )

    def _on_row_delete_requested(self, domain: str, askey: str):
        """Разлочивание при нажатии кнопки удаления"""
        self._request_managed_action(
            "locked_remove",
            domain=domain,
            askey=askey,
        )

    def _update_count(self):
        """Обновляет счётчик"""
        snapshot = self._orchestra.current_locked_snapshot()

        count_text = self._tr(
            "page.orchestra.locked.count.total",
            "Всего залочено: {total} (TCP: {tcp_count}, UDP: {udp_count})",
            total=snapshot.total_count,
            tcp_count=snapshot.tcp_count,
            udp_count=snapshot.udp_count,
        )
        self.count_label.setText(count_text)
        set_state_text(self.count_label, f"Счётчик залоченных стратегий Оркестратора: {count_text}")

    def _lock_strategy(self):
        """Залочивает стратегию"""
        if self._cleanup_in_progress:
            return
        domain = self.domain_input.text().strip().lower()
        if not domain:
            return

        if is_orchestra_ignored_target(domain):
            self._show_ignored_target_warning(domain)
            return

        strategy = self.strat_spin.value()
        askey = self.proto_combo.currentText().lower()

        self._request_managed_action(
            "locked_add",
            domain=domain,
            strategy=strategy,
            askey=askey,
        )

    def _unlock_all(self):
        """Разлочивает все стратегии"""
        if self._cleanup_in_progress:
            return
        if not self._orchestra.runner:
            return

        total = self._orchestra.count_locked_strategies()
        if total == 0:
            return

        if MessageBox is not None:
            body = self._tr(
                "page.orchestra.locked.dialog.unlock_all.body",
                "Разлочить все {total} стратегий?\nОркестратор начнёт обучение заново.",
                total=total,
            )
            box = MessageBox(
                self._tr("page.orchestra.locked.dialog.unlock_all.title", "Подтверждение"),
                body,
                self.window()
            )
            set_message_box_button_accessibility(
                box,
                yes_name="Разлочить все стратегии",
                yes_description=body,
                cancel_name="Отменить разлочку всех стратегий",
                cancel_description="Закрывает диалог без разлочки стратегий.",
            )
            confirmed = box.exec()
        else:
            confirmed = False  # qfluentwidgets недоступен — действие отменено

        if confirmed:
            self._request_managed_action("locked_clear", total=total)

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._refresh_loading = False
        self._snapshot_load_state_obj().reset()
        self._snapshot_load_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra locked snapshot worker",
        )
        self._managed_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra locked action worker",
        )
        self._snapshot_load_runtime.cancel()
        self._managed_action_runtime.cancel()
        self._managed_action_state_obj().reset()
        try:
            self.notification_banner.auto_hide_timer.stop()
            self.notification_banner.hide()
        except Exception:
            pass
