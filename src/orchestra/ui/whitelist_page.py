# ui/pages/orchestra/whitelist_page.py
"""
Страница управления белым списком оркестратора (whitelist)
Домены из этого списка НЕ обрабатываются оркестратором.
"""
from PyQt6.QtCore import Qt, QSize, QEvent, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QFrame,
)
from qfluentwidgets import (
    FluentIcon,
    LineEdit,
    PushButton,
    TransparentToolButton,
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
    MessageBox,
    InfoBar,
    CaptionLabel,
)

from ui.pages.base_page import BasePage
from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding
from app.ui_texts import tr as tr_catalog
from log.log import log



class WhitelistDomainRow(QFrame):
    """Виджет-ряд для одного домена в белом списке"""

    def __init__(
        self,
        domain: str,
        is_default: bool = False,
        parent=None,
        system_tooltip: str = "",
        delete_tooltip: str = "",
    ):
        super().__init__(parent)
        self.domain = domain
        self.is_default = is_default
        self._system_tooltip = system_tooltip or "Системный домен (нельзя удалить)"
        self._delete_tooltip = delete_tooltip or "Удалить из белого списка"

        self._tokens = get_theme_tokens()
        self._current_qss = ""

        self._lock_icon_label = None
        self._domain_label = None
        self._delete_btn = None

        self._setup_ui(domain, is_default)
        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme)

    def _setup_ui(self, domain: str, is_default: bool):
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # Иконка замка для системных
        if is_default:
            lock_icon = QLabel()
            self._lock_icon_label = lock_icon
            set_tooltip(lock_icon, self._system_tooltip)
            layout.addWidget(lock_icon)

        # Домен
        domain_label = BodyLabel(domain)
        if is_default:
            domain_label.setEnabled(False)
        self._domain_label = domain_label
        layout.addWidget(domain_label, 1)

        # Кнопка удаления (только для пользовательских)
        if not is_default:
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

        if self.is_default:
            qss = f"""
                WhitelistDomainRow {{
                    background: transparent;
                    border: 1px solid {tokens.surface_border_disabled};
                    border-radius: 6px;
                }}
            """
        else:
            qss = f"""
                WhitelistDomainRow {{
                    background: transparent;
                    border: 1px solid {tokens.surface_border};
                    border-radius: 6px;
                }}
                WhitelistDomainRow:hover {{
                    background: {tokens.surface_bg};
                    border: 1px solid {tokens.surface_border_hover};
                }}
            """

        if qss != self._current_qss:
            self._current_qss = qss
            self.setStyleSheet(qss)

        if self._lock_icon_label is not None:
            self._lock_icon_label.setPixmap(
                get_cached_qta_pixmap("mdi.lock", color=tokens.fg_faint, size=14)
            )

        if self._delete_btn is not None:
            self._delete_btn.setIcon(FluentIcon.CLOSE)

    def _on_delete_clicked(self):
        """При клике на удаление - уведомляем родителя"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraWhitelistPage):
            parent = parent.parent()
        if parent:
            parent._on_row_delete_requested(self.domain)

    def _update_accessibility(self) -> None:
        if self.is_default:
            row_name = f"Системный домен белого списка: {self.domain}"
            set_control_accessibility(
                self,
                name=row_name,
                description="Системный домен нельзя удалить.",
            )
        else:
            row_name = f"Домен белого списка: {self.domain}"
            set_control_accessibility(
                self,
                name=row_name,
                description="Этот домен не обрабатывается оркестратором.",
            )
        set_state_text(self, row_name)
        if self._delete_btn is not None:
            delete_name = f"Удалить {self.domain} из белого списка"
            set_control_accessibility(
                self._delete_btn,
                name=delete_name,
                description="Удаляет пользовательский домен из белого списка.",
            )
            set_state_text(self._delete_btn, delete_name)


class OrchestraWhitelistPage(BasePage):
    """Страница управления белым списком оркестратора"""

    def __init__(self, parent=None, *, orchestra_feature):
        super().__init__(
            "Белый список",
            "Домены, которые НЕ обрабатываются оркестратором. Эти сайты работают без DPI bypass.",
            parent,
            title_key="page.orchestra.whitelist.title",
            subtitle_key="page.orchestra.whitelist.subtitle",
        )
        self.setObjectName("orchestraWhitelistPage")
        self._orchestra = orchestra_feature
        self._all_whitelist_data = []  # Кэш данных для фильтрации
        self._add_card = None
        self._domains_card = None
        self._runtime_initialized = False
        self._last_snapshot_revision = None
        self._snapshot_runtime = OneShotWorkerRuntime()
        self._snapshot_refresh_state = LatestValueWorkerState(self._snapshot_runtime, empty_value=False)
        self._action_runtime = OneShotWorkerRuntime()
        self._whitelist_action_state = QueuedWorkerState[dict[str, object]](self._action_runtime)

        self._setup_ui()
        self._apply_page_theme(force=True)

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._sync_whitelist_view(refresh=True)

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

    def _setup_ui(self):
        # === Предупреждение о рестарте ===
        self.restart_warning = CaptionLabel(
            self._tr(
                "page.orchestra.whitelist.warning.restart_required",
                "⚠️ Изменения применятся после перезапуска оркестратора",
            )
        )
        self.restart_warning.hide()
        self.layout.addWidget(self.restart_warning)

        # === Карточка добавления ===
        add_card, add_card_layout = self._create_card(
            self._tr("page.orchestra.whitelist.card.add", "Добавить домен")
        )
        self._add_card = add_card
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        # Поле ввода
        self.domain_input = LineEdit()
        self.domain_input.setPlaceholderText(self._tr("page.orchestra.whitelist.input.placeholder", "example.com"))
        self.domain_input.returnPressed.connect(self._add_domain)
        add_layout.addWidget(self.domain_input, 1)

        # Кнопка добавления
        self.add_btn = TransparentToolButton(self)
        # Icon styled in _apply_theme()
        self.add_btn.setIconSize(QSize(18, 18))
        self.add_btn.setFixedSize(36, 36)
        set_tooltip(
            self.add_btn,
            self._tr("page.orchestra.whitelist.tooltip.add", "Добавить в белый список"),
        )
        self.add_btn.clicked.connect(self._add_domain)
        add_layout.addWidget(self.add_btn)

        add_card_layout.addLayout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка доменов ===
        domains_card, domains_layout = self._create_card(
            self._tr("page.orchestra.whitelist.card.list", "Белый список доменов")
        )
        self._domains_card = domains_card
        domains_layout.setSpacing(8)

        # Строка с поиском и кнопками
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Поиск
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.whitelist.search.placeholder", "Поиск по доменам...")
        )
        self.search_input.setClearButtonEnabled(True)
        remove_line_edit_buttons_from_tab_order(self.search_input)
        self.search_input.textChanged.connect(self._filter_list)
        self.search_input.installEventFilter(self)
        top_row.addWidget(self.search_input)

        # Кнопка очистки пользовательских
        self.clear_user_btn = PushButton(
            self._tr("page.orchestra.whitelist.button.clear_user", "Очистить пользовательские")
        )
        self.clear_user_btn.setFixedHeight(32)
        set_tooltip(
            self.clear_user_btn,
            self._tr(
                "page.orchestra.whitelist.tooltip.clear_user",
                "Удалить все пользовательские домены (системные останутся)",
            ),
        )
        self.clear_user_btn.clicked.connect(self._clear_user_domains)
        top_row.addWidget(self.clear_user_btn)
        top_row.addStretch()

        domains_layout.addLayout(top_row)

        # Счётчик
        self.count_label = CaptionLabel()
        domains_layout.addWidget(self.count_label)

        # Контейнер для рядов (без скролла - страница сама прокручивается)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 8, 0, 0)
        self.rows_layout.setSpacing(4)
        domains_layout.addWidget(self.rows_container)

        # Храним ссылки на ряды для быстрого доступа
        self._domain_rows: list[WhitelistDomainRow] = []

        self.layout.addWidget(domains_card, 1)
        self._install_accessibility()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "add_btn") and self.add_btn is not None:
            self.add_btn.setIcon(FluentIcon.ADD)

        if hasattr(self, "clear_user_btn") and self.clear_user_btn is not None:
            self.clear_user_btn.setIcon(FluentIcon.DELETE)

        if hasattr(self, "restart_warning") and self.restart_warning is not None:
            self.restart_warning.setStyleSheet(
                f"""
                QLabel {{
                    background: transparent;
                    border: 1px solid {tokens.surface_border};
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: {tokens.fg_muted};
                    font-size: 12px;
                }}
                """
            )

        if hasattr(self, "count_label") and self.count_label is not None:
            self.count_label.setStyleSheet(
                f"color: {tokens.fg_faint}; font-size: 11px;"
            )

        # Section headers inside the list.
        try:
            if hasattr(self, "rows_layout") and self.rows_layout is not None:
                for i in range(self.rows_layout.count()):
                    item = self.rows_layout.itemAt(i)
                    w = item.widget() if item else None
                    if not isinstance(w, QLabel):
                        continue
                    section = w.property("whitelistSection")
                    if section == "user":
                        w.setStyleSheet(
                            f"color: {tokens.accent_hex}; font-size: 11px; font-weight: 600; padding: 4px 0;"
                        )
                    elif section == "system":
                        w.setStyleSheet(
                            f"color: {tokens.fg_faint}; font-size: 11px; font-weight: 600; padding: 4px 0;"
                        )
        except Exception:
            pass

        # Refresh row widgets.
        try:
            for row in list(getattr(self, "_domain_rows", [])):
                if hasattr(row, "refresh_theme"):
                    row.refresh_theme()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.restart_warning.setText(
            self._tr(
                "page.orchestra.whitelist.warning.restart_required",
                "⚠️ Изменения применятся после перезапуска оркестратора",
            )
        )
        if self._add_card is not None and hasattr(self._add_card, "_title_label"):
            self._add_card._title_label.setText(
                self._tr("page.orchestra.whitelist.card.add", "Добавить домен")
            )
        if self._domains_card is not None and hasattr(self._domains_card, "_title_label"):
            self._domains_card._title_label.setText(
                self._tr("page.orchestra.whitelist.card.list", "Белый список доменов")
            )

        self.domain_input.setPlaceholderText(self._tr("page.orchestra.whitelist.input.placeholder", "example.com"))
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.whitelist.search.placeholder", "Поиск по доменам...")
        )
        self.clear_user_btn.setText(
            self._tr("page.orchestra.whitelist.button.clear_user", "Очистить пользовательские")
        )
        set_tooltip(
            self.add_btn,
            self._tr("page.orchestra.whitelist.tooltip.add", "Добавить в белый список"),
        )
        set_tooltip(
            self.clear_user_btn,
            self._tr(
                "page.orchestra.whitelist.tooltip.clear_user",
                "Удалить все пользовательские домены (системные останутся)",
            ),
        )
        self._install_accessibility()

        if self._runtime_initialized:
            self._sync_whitelist_view(refresh=True)

    def _install_accessibility(self) -> None:
        def _set_named_state(widget, text: str) -> None:
            set_state_text(widget, text)

        restart_warning_name = "Предупреждение: изменения белого списка применятся после перезапуска оркестратора"
        set_control_accessibility(
            self.restart_warning,
            name=restart_warning_name,
            description="Если оркестратор запущен, изменения вступят в силу после его перезапуска.",
        )
        _set_named_state(self.restart_warning, restart_warning_name)
        set_control_accessibility(
            self.domain_input,
            name="Домен для белого списка",
            description="Введите домен, который оркестратор не должен обрабатывать.",
        )
        _set_named_state(self.domain_input, "Домен для белого списка")
        set_control_accessibility(
            self.add_btn,
            name="Добавить домен в белый список",
            description="Добавляет введённый домен в белый список.",
        )
        _set_named_state(self.add_btn, "Добавить домен в белый список")
        set_control_accessibility(
            self.search_input,
            name="Поиск по белому списку",
            description=(
                "Фильтрует домены белого списка по введённому тексту. "
                "После ввода перейдите к списку клавишей Tab или нажмите Стрелка вниз."
            ),
        )
        _set_named_state(self.search_input, "Поиск по белому списку")
        set_control_accessibility(
            self.clear_user_btn,
            name="Очистить пользовательские домены белого списка",
            description="Удаляет все пользовательские домены. Системные домены останутся.",
        )
        _set_named_state(self.clear_user_btn, "Очистить пользовательские домены белого списка")

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is getattr(self, "search_input", None) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down and self._focus_first_visible_row_control():
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _focus_first_visible_row_control(self) -> bool:
        for row in self._domain_rows:
            if row is None or not row.isVisible():
                continue
            target = getattr(row, "_delete_btn", None)
            if target is None:
                continue
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        return False

    def on_page_activated(self) -> None:
        if not self._runtime_initialized:
            self._run_runtime_init_once()
            return
        self._sync_whitelist_view(refresh=False)

    def _is_orchestra_running(self) -> bool:
        """Проверяет, запущен ли оркестратор"""
        return self._orchestra.is_whitelist_runtime_running()

    def _sync_whitelist_view(self, *, refresh: bool) -> None:
        self._start_snapshot_worker(refresh=refresh)

    def create_snapshot_worker(self, request_id: int, *, refresh: bool):
        return self._orchestra.create_whitelist_snapshot_load_worker(
            request_id,
            refresh=refresh,
            parent=self,
        )

    def _start_snapshot_worker(self, *, refresh: bool) -> None:
        state = self._snapshot_refresh_state_obj()
        if state.is_busy():
            if refresh:
                state.pending = True
            return
        self._snapshot_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_snapshot_worker(
                request_id,
                refresh=refresh,
            ),
            on_loaded=self._on_snapshot_loaded,
            on_failed=self._on_snapshot_failed,
            on_finished=self._on_snapshot_finished,
        )

    def _on_snapshot_loaded(self, request_id: int, refresh: bool, snapshot) -> None:
        if not self._snapshot_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._snapshot_refresh_state_obj().has_pending():
            return
        if not refresh and snapshot.revision == self._last_snapshot_revision:
            return
        self._apply_whitelist_snapshot(snapshot)

    def _on_snapshot_failed(self, request_id: int, _refresh: bool, error: str) -> None:
        if not self._snapshot_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._snapshot_refresh_state_obj().has_pending():
            return
        log(f"Не удалось загрузить whitelist: {error}", "WARNING")

    def _on_snapshot_finished(self, worker) -> None:
        self._snapshot_refresh_state_obj().schedule_pending_after_finish(
            worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_snapshot_refresh_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _schedule_snapshot_refresh_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        state = self._snapshot_refresh_state_obj()
        state.pending = True
        state.schedule_start(
            QTimer.singleShot,
            self._run_scheduled_snapshot_refresh_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_snapshot_refresh_start(self) -> None:
        pending = self._snapshot_refresh_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        self._start_snapshot_worker(refresh=True)

    def _refresh_data(self):
        """Явно перечитывает whitelist из канонического runtime service."""
        self._sync_whitelist_view(refresh=True)

    def _apply_whitelist_snapshot(self, snapshot) -> None:
        self._last_snapshot_revision = snapshot.revision
        self._apply_whitelist_entries(snapshot.entries)

    def _apply_whitelist_entries(self, entries: tuple[tuple[str, bool], ...]) -> None:
        """Обновляет список доменов из service-owned snapshot."""
        # Очищаем старые ряды
        self._domain_rows.clear()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._all_whitelist_data = []
        whitelist = [
            {"domain": domain, "is_default": is_default}
            for domain, is_default in entries
        ]
        if not whitelist:
            self.count_label.setText(
                self._tr("page.orchestra.whitelist.status.empty", "Нет доменов в whitelist")
            )

        system_count = 0
        user_count = 0

        # Разделяем на системные и пользовательские
        system_domains = []
        user_domains = []

        for entry in whitelist:
            domain = entry['domain']
            is_default = entry['is_default']
            self._all_whitelist_data.append((domain, is_default))

            if is_default:
                system_domains.append(domain)
                system_count += 1
            else:
                user_domains.append(domain)
                user_count += 1

        # Сортируем
        system_domains.sort()
        user_domains.sort()

        # Добавляем заголовок и ряды для пользовательских (если есть)
        if user_domains:
            user_header = QLabel(
                self._tr(
                    "page.orchestra.whitelist.section.user",
                    "Пользовательские ({count})",
                    count=user_count,
                )
            )
            user_header.setProperty("whitelistSection", "user")
            set_state_text(
                user_header,
                self._tr(
                    "page.orchestra.whitelist.section.user.accessible",
                    "Раздел белого списка Оркестратора: Пользовательские, {count}",
                    count=user_count,
                ),
            )
            self.rows_layout.addWidget(user_header)

            for domain in user_domains:
                row = WhitelistDomainRow(
                    domain,
                    is_default=False,
                    delete_tooltip=self._tr(
                        "page.orchestra.whitelist.tooltip.delete",
                        "Удалить из белого списка",
                    ),
                )
                self.rows_layout.addWidget(row)
                self._domain_rows.append(row)

        # Разделитель между группами
        if user_domains and system_domains:
            spacer = QWidget()
            spacer.setFixedHeight(12)
            self.rows_layout.addWidget(spacer)

        # Добавляем заголовок и ряды для системных (если есть)
        if system_domains:
            system_header = QLabel(
                self._tr(
                    "page.orchestra.whitelist.section.system",
                    "🔒 Системные ({count}) — нельзя удалить",
                    count=system_count,
                )
            )
            system_header.setProperty("whitelistSection", "system")
            set_state_text(
                system_header,
                self._tr(
                    "page.orchestra.whitelist.section.system.accessible",
                    "Раздел белого списка Оркестратора: Системные, {count}, нельзя удалить",
                    count=system_count,
                ),
            )
            self.rows_layout.addWidget(system_header)

            for domain in system_domains:
                row = WhitelistDomainRow(
                    domain,
                    is_default=True,
                    system_tooltip=self._tr(
                        "page.orchestra.whitelist.tooltip.system_domain",
                        "Системный домен (нельзя удалить)",
                    ),
                )
                self.rows_layout.addWidget(row)
                self._domain_rows.append(row)

        count_text = self._tr(
            "page.orchestra.whitelist.count.total",
            "Всего: {total} ({system} системных + {user} пользовательских)",
            total=len(whitelist),
            system=system_count,
            user=user_count,
        )
        self.count_label.setText(count_text)
        set_state_text(self.count_label, f"Счётчик белого списка Оркестратора: {count_text}")
        self._apply_filter()

        self._apply_page_theme()

    def _filter_list(self, text: str):
        """Фильтрует список по введённому тексту"""
        self._apply_filter()

    def _apply_filter(self):
        """Применяет текущий фильтр к рядам"""
        search = self.search_input.text().lower().strip()
        for row in self._domain_rows:
            domain = row.domain.lower()
            row.setVisible(search in domain if search else True)

    def _show_restart_warning(self):
        """Показывает предупреждение о необходимости рестарта"""
        if self._is_orchestra_running():
            self.restart_warning.show()

    def _add_domain(self):
        """Добавляет домен в пользовательский whitelist"""
        domain = self.domain_input.text().strip().lower()
        if not domain:
            return

        self._request_whitelist_action("add", domain=domain)

    def _on_row_delete_requested(self, domain: str):
        """Удаление при нажатии кнопки X в ряду"""
        self._request_whitelist_action("remove", domain=domain)

    def _clear_user_domains(self):
        """Очищает все пользовательские домены из белого списка"""
        user_domains = [
            domain for domain, is_default in tuple(self._all_whitelist_data or ())
            if not is_default
        ]

        if not user_domains:
            if InfoBar:
                InfoBar.info(
                    title=self._tr("page.orchestra.whitelist.infobar.info_title", "Информация"),
                    content=self._tr(
                        "page.orchestra.whitelist.info.no_user_domains",
                        "Нет пользовательских доменов для удаления. Системные домены не удаляются.",
                    ),
                    parent=self.window(),
                )
            return

        confirmed = True
        if MessageBox:
            body = self._tr(
                "page.orchestra.whitelist.dialog.clear_user.body",
                "Удалить все пользовательские домены ({count})?\n\nСистемные домены останутся.",
                count=len(user_domains),
            )
            box = MessageBox(
                self._tr("page.orchestra.whitelist.dialog.clear_user.title", "Подтверждение"),
                body,
                self.window(),
            )
            set_message_box_button_accessibility(
                box,
                yes_name="Очистить пользовательские домены белого списка",
                yes_description=body,
                cancel_name="Отменить очистку пользовательских доменов",
                cancel_description="Закрывает диалог без очистки пользовательских доменов.",
            )
            confirmed = bool(box.exec())
        if confirmed:
            self._request_whitelist_action("clear_user", user_domains=user_domains)

    def create_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        domain: str = "",
        user_domains: list[str] | None = None,
    ):
        return self._orchestra.create_whitelist_action_worker(
            request_id,
            action=action,
            domain=domain,
            user_domains=user_domains,
            parent=self,
        )

    def _request_whitelist_action(
        self,
        action: str,
        *,
        domain: str = "",
        user_domains: list[str] | None = None,
    ) -> None:
        queued = self._whitelist_action_payload(action=action, domain=domain, user_domains=user_domains)
        state = self._whitelist_action_state_obj()
        if state.is_busy():
            self._queue_whitelist_action_payload(queued)
            return
        self._start_whitelist_action_worker(queued)

    def _start_whitelist_action_worker(self, queued: dict[str, object]) -> None:
        action = str((queued or {}).get("action") or "")
        domain = str((queued or {}).get("domain") or "")
        user_domains = (queued or {}).get("user_domains")
        self._action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_action_worker(
                request_id,
                action=action,
                domain=domain,
                user_domains=user_domains,
            ),
            on_loaded=self._on_whitelist_action_loaded,
            on_failed=self._on_whitelist_action_failed,
            on_finished=self._on_whitelist_action_finished,
        )

    def _whitelist_action_payload(
        self,
        *,
        action: str,
        domain: str = "",
        user_domains: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "action": str(action or ""),
            "domain": str(domain or ""),
            "user_domains": list(user_domains) if user_domains is not None else None,
        }

    def _queue_whitelist_action(
        self,
        *,
        action: str,
        domain: str = "",
        user_domains: list[str] | None = None,
        prepend: bool = False,
    ) -> None:
        queued = self._whitelist_action_payload(action=action, domain=domain, user_domains=user_domains)
        self._queue_whitelist_action_payload(queued, prepend=prepend)

    def _queue_whitelist_action_payload(self, queued: dict[str, object], *, prepend: bool = False) -> None:
        pending = self._whitelist_action_state_obj().pending
        if queued in pending:
            return
        if prepend:
            pending.insert(0, queued)
        else:
            pending.append(queued)

    def _on_whitelist_action_loaded(self, request_id: int, action: str, payload, context) -> None:
        if not self._action_runtime.is_current(request_id):
            return
        payload = dict(payload or {})
        context = dict(context or {})
        result = payload.get("result")
        snapshot = payload.get("snapshot")
        changed = bool(getattr(result, "changed", False))
        if snapshot is not None:
            self._snapshot_runtime.cancel()
            self._apply_whitelist_snapshot(snapshot)
        if changed:
            if action == "add":
                self.domain_input.clear()
            self._show_restart_warning()
            return
        if action == "add" and InfoBar:
            InfoBar.info(
                title=self._tr("page.orchestra.whitelist.infobar.info_title", "Информация"),
                content=self._tr(
                    "page.orchestra.whitelist.info.already_exists",
                    "Домен {domain} уже в списке",
                    domain=str(context.get("domain") or ""),
                ),
                parent=self.window(),
            )

    def _on_whitelist_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if not self._action_runtime.is_current(request_id):
            return
        log(f"Не удалось выполнить действие whitelist ({action}): {error}", "WARNING")

    def _on_whitelist_action_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_action_runtime"), worker):
            return
        if self._action_runtime.worker is worker:
            self._action_runtime.worker = None
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = self._whitelist_action_state_obj().pop_next()
        if pending is not None:
            self._schedule_whitelist_action_start(dict(pending or {}))

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

    def _schedule_whitelist_action_start(self, pending: dict[str, object]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        state = self._whitelist_action_state_obj()
        if state.start_scheduled:
            self._queue_whitelist_action_payload(dict(pending or {}), prepend=True)
            return
        state.start_scheduled = True
        QTimer.singleShot(0, lambda value=dict(pending or {}): self._run_scheduled_whitelist_action_start(value))

    def _run_scheduled_whitelist_action_start(self, pending: dict[str, object]) -> None:
        self._whitelist_action_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_whitelist_action(
            str(pending.get("action") or ""),
            domain=str(pending.get("domain") or ""),
            user_domains=pending.get("user_domains"),
        )

    def _snapshot_refresh_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_snapshot_refresh_state")
        runtime = self.__dict__.get("_snapshot_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_snapshot_refresh_pending", False))
            start_scheduled = bool(self.__dict__.pop("_snapshot_refresh_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_snapshot_refresh_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _snapshot_refresh_pending(self) -> bool:
        return bool(self._snapshot_refresh_state_obj().pending)

    @_snapshot_refresh_pending.setter
    def _snapshot_refresh_pending(self, value: bool) -> None:
        self._snapshot_refresh_state_obj().pending = bool(value)

    @property
    def _snapshot_refresh_start_scheduled(self) -> bool:
        return bool(self._snapshot_refresh_state_obj().start_scheduled)

    @_snapshot_refresh_start_scheduled.setter
    def _snapshot_refresh_start_scheduled(self, value: bool) -> None:
        self._snapshot_refresh_state_obj().start_scheduled = bool(value)

    def _whitelist_action_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        state = self.__dict__.get("_whitelist_action_state")
        runtime = self.__dict__.get("_action_runtime")
        if state is None:
            pending = list(self.__dict__.pop("_whitelist_action_pending", []) or [])
            start_scheduled = bool(self.__dict__.pop("_whitelist_action_start_scheduled", False))
            state = QueuedWorkerState[dict[str, object]](
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_whitelist_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _whitelist_action_pending(self) -> list[dict[str, object]]:
        return self._whitelist_action_state_obj().pending

    @_whitelist_action_pending.setter
    def _whitelist_action_pending(self, value: list[dict[str, object]]) -> None:
        self._whitelist_action_state_obj().pending = list(value or [])

    @property
    def _whitelist_action_start_scheduled(self) -> bool:
        return bool(self._whitelist_action_state_obj().start_scheduled)

    @_whitelist_action_start_scheduled.setter
    def _whitelist_action_start_scheduled(self, value: bool) -> None:
        self._whitelist_action_state_obj().start_scheduled = bool(value)

    def cleanup(self) -> None:
        super().cleanup()
        self._snapshot_refresh_state_obj().reset()
        self._whitelist_action_state_obj().reset()
        self._snapshot_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra whitelist snapshot worker",
        )
        self._action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Orchestra whitelist action worker",
        )
