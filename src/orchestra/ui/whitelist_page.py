# ui/pages/orchestra/whitelist_page.py
"""
Страница управления белым списком оркестратора (whitelist)
Домены из этого списка НЕ обрабатываются оркестратором.
"""
from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QLineEdit, QFrame, QPushButton
)

try:
    from qfluentwidgets import (
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
    _HAS_FLUENT = True
except ImportError:
    LineEdit = QLineEdit
    PushButton = QPushButton
    TransparentToolButton = QPushButton
    CardWidget = QFrame
    StrongBodyLabel = QLabel
    BodyLabel = QLabel
    MessageBox = None
    InfoBar = None
    CaptionLabel = QLabel
    _HAS_FLUENT = False

from ..base_page import BasePage
from ui.compat_widgets import set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from log import log


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
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

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
            self._delete_btn.setIcon(get_themed_qta_icon("mdi.close-circle-outline", color=tokens.fg))

    def _on_delete_clicked(self):
        """При клике на удаление - уведомляем родителя"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraWhitelistPage):
            parent = parent.parent()
        if parent:
            parent._on_row_delete_requested(self.domain)


class OrchestraWhitelistPage(BasePage):
    """Страница управления белым списком оркестратора"""

    def __init__(self, parent=None):
        super().__init__(
            "Белый список",
            "Домены, которые НЕ обрабатываются оркестратором. Эти сайты работают без DPI bypass.",
            parent,
            title_key="page.orchestra.whitelist.title",
            subtitle_key="page.orchestra.whitelist.subtitle",
        )
        self.setObjectName("orchestraWhitelistPage")
        self._all_whitelist_data = []  # Кэш данных для фильтрации
        self._add_card = None
        self._domains_card = None
        self._runtime_initialized = False
        self._last_snapshot_revision = None

        self._setup_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

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

        title_label = StrongBodyLabel(title, card) if _HAS_FLUENT else QLabel(title)
        if not _HAS_FLUENT:
            title_label.setStyleSheet("font-size: 14px; font-weight: 600;")
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
        self.search_input.textChanged.connect(self._filter_list)
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

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "add_btn") and self.add_btn is not None:
            self.add_btn.setIcon(get_themed_qta_icon("mdi.plus", color=tokens.fg))

        if hasattr(self, "clear_user_btn") and self.clear_user_btn is not None:
            self.clear_user_btn.setIcon(get_themed_qta_icon("mdi.delete-sweep", color=tokens.fg))

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

        self._sync_whitelist_view(refresh=True)

    def on_page_activated(self) -> None:
        self._sync_whitelist_view(refresh=False)

    def _is_orchestra_running(self) -> bool:
        """Проверяет, запущен ли оркестратор"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner.is_running()
        return False

    def _sync_whitelist_view(self, *, refresh: bool) -> None:
        snapshot = self.window().app_context.orchestra_whitelist_runtime_service.get_snapshot(
            self.window(),
            refresh=refresh,
        )
        if not refresh and snapshot.revision == self._last_snapshot_revision:
            return
        self._last_snapshot_revision = snapshot.revision
        self._apply_whitelist_entries(snapshot.entries)

    def _refresh_data(self):
        """Явно перечитывает whitelist из канонического runtime service."""
        self._sync_whitelist_view(refresh=True)

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

        self.count_label.setText(
            self._tr(
                "page.orchestra.whitelist.count.total",
                "Всего: {total} ({system} системных + {user} пользовательских)",
                total=len(whitelist),
                system=system_count,
                user=user_count,
            )
        )
        self._apply_filter()

        self._apply_theme()

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

        if self.window().app_context.orchestra_whitelist_runtime_service.add_domain(self.window(), domain):
            self.domain_input.clear()
            self._refresh_data()
            self._show_restart_warning()
            log(f"Добавлен в белый список: {domain}", "INFO")
        else:
            if InfoBar:
                InfoBar.info(
                    title=self._tr("page.orchestra.whitelist.infobar.info_title", "Информация"),
                    content=self._tr(
                        "page.orchestra.whitelist.info.already_exists",
                        "Домен {domain} уже в списке",
                        domain=domain,
                    ),
                    parent=self.window(),
                )

    def _on_row_delete_requested(self, domain: str):
        """Удаление при нажатии кнопки X в ряду"""
        if self.window().app_context.orchestra_whitelist_runtime_service.remove_domain(self.window(), domain):
            self._refresh_data()
            self._show_restart_warning()
            log(f"Удалён из белого списка: {domain}", "INFO")

    def _clear_user_domains(self):
        """Очищает все пользовательские домены из белого списка"""
        snapshot = self.window().app_context.orchestra_whitelist_runtime_service.get_snapshot(
            self.window(),
            refresh=True,
        )
        user_domains = [domain for domain, is_default in snapshot.entries if not is_default]

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
            box = MessageBox(
                self._tr("page.orchestra.whitelist.dialog.clear_user.title", "Подтверждение"),
                self._tr(
                    "page.orchestra.whitelist.dialog.clear_user.body",
                    "Удалить все пользовательские домены ({count})?\n\nСистемные домены останутся.",
                    count=len(user_domains),
                ),
                self.window(),
            )
            confirmed = bool(box.exec())
        if confirmed:
            removed = self.window().app_context.orchestra_whitelist_runtime_service.clear_user_domains(
                self.window(),
                user_domains,
            )
            if removed:
                log(f"Очищены все пользовательские домены из белого списка ({removed})", "INFO")
                self._refresh_data()
                self._show_restart_warning()
