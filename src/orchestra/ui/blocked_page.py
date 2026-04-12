# ui/pages/orchestra/blocked_page.py
"""
Страница управления заблокированными стратегиями оркестратора (чёрный список).
Каждая блокировка отображается в виде ряда с редактируемым номером стратегии.
Изменения автоматически сохраняются в реестр.
"""
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QFrame,
    QLineEdit, QSpinBox, QComboBox, QPushButton
)

try:
    from qfluentwidgets import (
        ComboBox,
        SpinBox,
        LineEdit,
        PushButton,
        TransparentToolButton,
        CardWidget,
        StrongBodyLabel,
        MessageBox,
        InfoBar,
        InfoBarPosition,
        CaptionLabel,
        BodyLabel,
    )
    _HAS_FLUENT = True
except ImportError:
    ComboBox = QComboBox
    SpinBox = QSpinBox
    LineEdit = QLineEdit
    PushButton = QPushButton
    TransparentToolButton = QPushButton
    CardWidget = QFrame
    StrongBodyLabel = QLabel
    MessageBox = None
    InfoBar = None
    InfoBarPosition = None
    CaptionLabel = QLabel
    BodyLabel = QLabel
    _HAS_FLUENT = False

from ..base_page import BasePage
from ui.compat_widgets import set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from log import log
from orchestra.ignored_targets import is_orchestra_ignored_target
from orchestra.blocked_strategies_manager import ASKEY_ALL


class BlockedDomainRow(QFrame):
    """Виджет-ряд для одной заблокированной стратегии с редактируемым номером"""

    def __init__(
        self,
        hostname: str,
        strategy: int,
        askey: str,
        is_default: bool = False,
        parent=None,
        *,
        system_tooltip: str = "",
        add_tooltip: str = "",
        delete_tooltip: str = "",
    ):
        super().__init__(parent)
        self.hostname = hostname
        self.original_strategy = strategy  # Сохраняем оригинальную стратегию для изменений
        self.askey = askey
        self.is_default = is_default
        self._system_tooltip = system_tooltip or "Системная блокировка (нельзя изменить)"
        self._add_tooltip = add_tooltip or "Добавить ещё одну заблокированную стратегию для этого домена"
        self._delete_tooltip = delete_tooltip or "Разблокировать"

        self._tokens = get_theme_tokens()
        self._current_qss = ""

        self._lock_icon_label = None
        self._domain_label = None
        self._proto_label = None
        self._default_strat_label = None
        self._add_btn = None
        self._delete_btn = None

        self._setup_ui(hostname, strategy, askey, is_default)
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

    def _setup_ui(self, hostname: str, strategy: int, askey: str, is_default: bool):
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # Иконка замка для дефолтных
        if is_default:
            lock_icon = QLabel()
            self._lock_icon_label = lock_icon
            set_tooltip(lock_icon, self._system_tooltip)
            layout.addWidget(lock_icon)

        # Домен
        domain_label = BodyLabel(hostname)
        if is_default:
            domain_label.setEnabled(False)
        self._domain_label = domain_label
        layout.addWidget(domain_label, 1)

        # Протокол
        proto_label = CaptionLabel(f"[{askey.upper()}]")
        if is_default:
            proto_label.setEnabled(False)
        self._proto_label = proto_label
        proto_label.setFixedWidth(60)
        layout.addWidget(proto_label)

        if is_default:
            # Для системных - только текст стратегии
            strat_label = CaptionLabel(f"#{strategy}")
            strat_label.setEnabled(False)
            self._default_strat_label = strat_label
            strat_label.setFixedWidth(50)
            layout.addWidget(strat_label)
        else:
            # Для пользовательских - редактируемый SpinBox
            self.strat_spin = SpinBox()
            self.strat_spin.setRange(1, 999)
            self.strat_spin.setValue(strategy)
            self.strat_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.strat_spin.valueChanged.connect(self._on_strategy_changed)
            layout.addWidget(self.strat_spin)

            # Кнопка добавления ещё одной блокировки для этого домена
            add_btn = TransparentToolButton(self)
            self._add_btn = add_btn
            add_btn.setIconSize(QSize(14, 14))
            add_btn.setFixedSize(24, 24)
            set_tooltip(add_btn, self._add_tooltip)
            add_btn.clicked.connect(self._on_add_clicked)
            layout.addWidget(add_btn)

            # Кнопка удаления (разблокировать)
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
                BlockedDomainRow {{
                    background: transparent;
                    border: 1px solid {tokens.surface_border_disabled};
                    border-radius: 6px;
                }}
            """
        else:
            qss = f"""
                BlockedDomainRow {{
                    background: transparent;
                    border: 1px solid {tokens.surface_border};
                    border-radius: 6px;
                }}
                BlockedDomainRow:hover {{
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

        if self._add_btn is not None:
            self._add_btn.setIcon(get_themed_qta_icon("mdi.plus", color=tokens.fg))
        if self._delete_btn is not None:
            self._delete_btn.setIcon(get_themed_qta_icon("mdi.close-circle-outline", color=tokens.fg))

    def _on_strategy_changed(self, new_value: int):
        """При изменении номера стратегии - уведомляем родителя для автосохранения"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraBlockedPage):
            parent = parent.parent()
        if parent:
            parent._on_row_strategy_changed(self.hostname, self.original_strategy, new_value, self.askey)
            self.original_strategy = new_value  # Обновляем для следующих изменений

    def _on_add_clicked(self):
        """При клике на + - заполняем форму для добавления новой блокировки этого домена"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraBlockedPage):
            parent = parent.parent()
        if parent:
            parent._prefill_domain(self.hostname)

    def _on_delete_clicked(self):
        """При клике на удаление - уведомляем родителя"""
        parent = self.parent()
        while parent and not isinstance(parent, OrchestraBlockedPage):
            parent = parent.parent()
        if parent:
            parent._on_row_delete_requested(self.hostname, self.original_strategy, self.askey)


class OrchestraBlockedPage(BasePage):
    """Страница управления заблокированными стратегиями (чёрный список)"""

    def __init__(self, parent=None):
        super().__init__(
            "Заблокированные стратегии",
            "Системные блокировки (strategy=1 для заблокированных РКН сайтов) + пользовательский чёрный список. Оркестратор не будет их использовать.",
            parent,
            title_key="page.orchestra.blocked.title",
            subtitle_key="page.orchestra.blocked.subtitle",
        )
        self.setObjectName("orchestraBlockedPage")
        self._hint_label = None
        self._add_card = None
        self._list_card = None
        # Инициализируем пустые данные. Первый reload выполняется после build/init страницы.
        self._direct_blocked_by_askey = {askey: {} for askey in ASKEY_ALL}
        self._runtime_initialized = False
        self._refresh_loading = False
        self._cleanup_in_progress = False

        self._setup_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._reload_from_registry()

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
        if self._cleanup_in_progress:
            return
        self._refresh_loading = loading
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setEnabled(not loading)
            set_tooltip(
                self.refresh_btn,
                self._tr("page.orchestra.blocked.button.refresh.tooltip", "Обновить"),
            )
        self._apply_theme()

    def _setup_ui(self):
        # === Карточка добавления ===
        add_card, add_card_layout = self._create_card(
            self._tr("page.orchestra.blocked.card.add", "Заблокировать стратегию вручную")
        )
        self._add_card = add_card
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        # Домен
        self.domain_input = LineEdit()
        self.domain_input.setPlaceholderText(
            self._tr("page.orchestra.blocked.input.domain.placeholder", "example.com")
        )
        # Styled in _apply_theme()
        add_layout.addWidget(self.domain_input, 1)

        # Протокол (askey)
        self.proto_combo = ComboBox()
        self.proto_combo.addItems([askey.upper() for askey in ASKEY_ALL])
        self.proto_combo.setFixedWidth(90)
        add_layout.addWidget(self.proto_combo)

        # Стратегия
        self.strat_spin = SpinBox()
        self.strat_spin.setRange(1, 999)
        self.strat_spin.setValue(1)
        self.strat_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_layout.addWidget(self.strat_spin)

        # Кнопка добавления
        self.block_btn = TransparentToolButton(self)
        # Icon styled in _apply_theme()
        self.block_btn.setIconSize(QSize(18, 18))
        self.block_btn.setFixedSize(36, 36)
        set_tooltip(
            self.block_btn,
            self._tr("page.orchestra.blocked.button.block.tooltip", "Заблокировать стратегию"),
        )
        self.block_btn.clicked.connect(self._block_strategy)
        add_layout.addWidget(self.block_btn)

        add_card_layout.addLayout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка ===
        list_card, list_layout = self._create_card(
            self._tr("page.orchestra.blocked.card.list", "Чёрный список")
        )
        self._list_card = list_card
        list_layout.setSpacing(8)

        # Кнопка и счётчик сверху
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Поиск
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.blocked.search.placeholder", "Поиск по доменам...")
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_list)
        # Styled in _apply_theme()
        top_row.addWidget(self.search_input)

        # Кнопка обновления списка из реестра
        self.refresh_btn = TransparentToolButton(self)
        self.refresh_btn.setFixedSize(32, 32)
        set_tooltip(
            self.refresh_btn,
            self._tr("page.orchestra.blocked.button.refresh.tooltip", "Обновить"),
        )
        self.refresh_btn.clicked.connect(self._reload_from_registry)
        top_row.addWidget(self.refresh_btn)

        self.unblock_all_btn = PushButton(
            self._tr("page.orchestra.blocked.button.clear_user", "Очистить пользовательские")
        )
        self.unblock_all_btn.setFixedHeight(32)
        set_tooltip(
            self.unblock_all_btn,
            self._tr(
                "page.orchestra.blocked.button.clear_user.tooltip",
                "Удалить все пользовательские блокировки (системные останутся)",
            ),
        )
        self.unblock_all_btn.clicked.connect(self._unblock_all)
        top_row.addWidget(self.unblock_all_btn)
        top_row.addStretch()

        list_layout.addLayout(top_row)

        # Счётчик на отдельной строке (чтобы влезал в таб)
        self.count_label = CaptionLabel()
        list_layout.addWidget(self.count_label)

        # Подсказка
        hint_label = CaptionLabel(
            self._tr(
                "page.orchestra.blocked.hint",
                "Измените номер стратегии и она автоматически сохранится • Системные блокировки неизменяемы",
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
        self._blocked_rows: list[BlockedDomainRow] = []

        self.layout.addWidget(list_card)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "block_btn") and self.block_btn is not None:
            self.block_btn.setIcon(get_themed_qta_icon("mdi.plus", color=tokens.fg))

        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            refresh_icon = "mdi.loading" if self._refresh_loading else "mdi.refresh"
            refresh_color = tokens.fg_faint if self._refresh_loading else tokens.fg
            self.refresh_btn.setIcon(get_themed_qta_icon(refresh_icon, color=refresh_color))

        if hasattr(self, "unblock_all_btn") and self.unblock_all_btn is not None:
            self.unblock_all_btn.setIcon(get_themed_qta_icon("mdi.delete-sweep", color=tokens.fg))

        try:
            if hasattr(self, "rows_layout") and self.rows_layout is not None:
                for i in range(self.rows_layout.count()):
                    item = self.rows_layout.itemAt(i)
                    w = item.widget() if item else None
                    if not isinstance(w, QLabel):
                        continue
                    section = w.property("blockedSection")
                    if section == "user":
                        w.setStyleSheet(
                            f"color: {tokens.accent_hex}; font-size: 11px; font-weight: 600; padding: 4px 0;"
                        )
                    elif section == "default":
                        w.setStyleSheet(
                            f"color: {tokens.fg_faint}; font-size: 11px; font-weight: 600; padding: 4px 0;"
                        )
        except Exception:
            pass

        try:
            for row in list(getattr(self, "_blocked_rows", [])):
                if hasattr(row, "refresh_theme"):
                    row.refresh_theme()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._add_card is not None and hasattr(self._add_card, "_title_label"):
            self._add_card._title_label.setText(
                self._tr("page.orchestra.blocked.card.add", "Заблокировать стратегию вручную")
            )
        if self._list_card is not None and hasattr(self._list_card, "_title_label"):
            self._list_card._title_label.setText(
                self._tr("page.orchestra.blocked.card.list", "Чёрный список")
            )

        self.domain_input.setPlaceholderText(
            self._tr("page.orchestra.blocked.input.domain.placeholder", "example.com")
        )
        self.search_input.setPlaceholderText(
            self._tr("page.orchestra.blocked.search.placeholder", "Поиск по доменам...")
        )
        self.unblock_all_btn.setText(
            self._tr("page.orchestra.blocked.button.clear_user", "Очистить пользовательские")
        )
        if self._hint_label is not None:
            self._hint_label.setText(
                self._tr(
                    "page.orchestra.blocked.hint",
                    "Измените номер стратегии и она автоматически сохранится • Системные блокировки неизменяемы",
                )
            )

        set_tooltip(
            self.block_btn,
            self._tr("page.orchestra.blocked.button.block.tooltip", "Заблокировать стратегию"),
        )
        set_tooltip(
            self.refresh_btn,
            self._tr("page.orchestra.blocked.button.refresh.tooltip", "Обновить"),
        )
        set_tooltip(
            self.unblock_all_btn,
            self._tr(
                "page.orchestra.blocked.button.clear_user.tooltip",
                "Удалить все пользовательские блокировки (системные останутся)",
            ),
        )

        self._refresh_data()

    def _get_runner(self):
        """Получает orchestra_runner из главного окна"""
        return getattr(self, "orchestra_runner", None)

    def _refresh_data(self):
        """Обновляет все данные на странице"""
        if self._cleanup_in_progress:
            return
        self._refresh_blocked_list()

    def _show_ignored_target_warning(self, domain: str) -> None:
        if self._cleanup_in_progress:
            return
        if InfoBar is not None:
            InfoBar.warning(
                title=self._tr("page.orchestra.blocked.infobar.ignored_proxy.title", "Игнорируется"),
                content=self._tr(
                    "page.orchestra.blocked.infobar.ignored_proxy.body",
                    "Домен {domain} относится к отдельному Telegram Proxy модулю. Оркестратор не управляет такими целями.",
                    domain=domain,
                ),
                isClosable=True,
                duration=5000,
                parent=self.window(),
                position=InfoBarPosition.TOP,
            )

    def _reload_from_registry(self):
        """Перезагружает данные из реестра и обновляет список"""
        if self._cleanup_in_progress:
            return
        self._set_refresh_loading(True)

        def _do_reload():
            if self._cleanup_in_progress:
                return
            try:
                runner = self._get_runner()
                if runner and hasattr(runner, 'blocked_manager'):
                    runner.blocked_manager.load()
                    log("Список заблокированных перезагружен из реестра (runner)", "INFO")
                else:
                    self._load_directly_from_registry()
                    log("Список заблокированных перезагружен из реестра (direct)", "INFO")
                self._refresh_data()
            finally:
                if not self._cleanup_in_progress:
                    self._set_refresh_loading(False)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and _do_reload())

    def _load_directly_from_registry(self):
        """Загружает данные напрямую из реестра (без активного runner)"""
        from orchestra.blocked_strategies_manager import BlockedStrategiesManager
        # Создаём временный менеджер для загрузки данных
        temp_manager = BlockedStrategiesManager()
        temp_manager.load()
        # Сохраняем данные для отображения
        self._direct_blocked_by_askey = {askey: dict(temp_manager.blocked_by_askey[askey]) for askey in ASKEY_ALL}
        # Логируем количество загруженных записей
        total = sum(len(strategies) for askey_data in temp_manager.blocked_by_askey.values() for strategies in askey_data.values())
        log(f"Загружено напрямую из реестра: {total} заблокированных стратегий", "INFO")

    def _refresh_blocked_list(self):
        """Обновляет список заблокированных стратегий"""
        if self._cleanup_in_progress:
            return
        # Очищаем старые ряды
        self._blocked_rows.clear()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        runner = self._get_runner()

        # Источник данных: runner или напрямую загруженные из реестра
        if runner:
            blocked_data = runner.blocked_manager.blocked_by_askey
            blocked_manager = runner.blocked_manager
        elif hasattr(self, '_direct_blocked_by_askey'):
            blocked_data = self._direct_blocked_by_askey
            blocked_manager = None
        else:
            # Нет данных - попробуем загрузить
            self._load_directly_from_registry()
            blocked_data = getattr(self, '_direct_blocked_by_askey', {askey: {} for askey in ASKEY_ALL})
            blocked_manager = None

        # Собираем все блокировки с флагом is_default по всем askey
        all_blocked = []
        for askey in ASKEY_ALL:
            for hostname, strategies in blocked_data.get(askey, {}).items():
                for strategy in strategies:
                    if blocked_manager:
                        is_default = blocked_manager.is_default_blocked(hostname, strategy)
                    else:
                        # Без менеджера - проверяем только strategy=1 для TLS
                        from orchestra.blocked_strategies_manager import is_default_blocked_pass_domain
                        is_default = (strategy == 1 and askey == "tls" and is_default_blocked_pass_domain(hostname))
                    all_blocked.append((hostname, strategy, askey, is_default))

        # Сортируем: сначала пользовательские, потом дефолтные, внутри групп по алфавиту
        all_blocked.sort(key=lambda x: (x[3], x[0].lower(), x[2], x[1]))

        # Добавляем разделитель если есть оба типа
        user_items = [x for x in all_blocked if not x[3]]
        default_items = [x for x in all_blocked if x[3]]

        if user_items:
            user_header = QLabel(
                self._tr(
                    "page.orchestra.blocked.section.user",
                    "Пользовательские ({count})",
                    count=len(user_items),
                )
            )
            user_header.setProperty("blockedSection", "user")
            self.rows_layout.addWidget(user_header)

            for hostname, strategy, askey, is_default in user_items:
                row = BlockedDomainRow(
                    hostname,
                    strategy,
                    askey,
                    is_default=False,
                    add_tooltip=self._tr(
                        "page.orchestra.blocked.row.add.tooltip",
                        "Добавить ещё одну заблокированную стратегию для этого домена",
                    ),
                    delete_tooltip=self._tr(
                        "page.orchestra.blocked.row.unblock.tooltip",
                        "Разблокировать",
                    ),
                )
                self.rows_layout.addWidget(row)
                self._blocked_rows.append(row)

        if default_items:
            if user_items:
                # Разделитель
                spacer = QWidget()
                spacer.setFixedHeight(12)
                self.rows_layout.addWidget(spacer)

            default_header = QLabel(
                self._tr(
                    "page.orchestra.blocked.section.system",
                    "Системные ({count}) - заблокированные РКН сайты",
                    count=len(default_items),
                )
            )
            default_header.setProperty("blockedSection", "default")
            self.rows_layout.addWidget(default_header)

            for hostname, strategy, askey, is_default in default_items:
                row = BlockedDomainRow(
                    hostname,
                    strategy,
                    askey,
                    is_default=True,
                    system_tooltip=self._tr(
                        "page.orchestra.blocked.row.system.tooltip",
                        "Системная блокировка (нельзя изменить)",
                    ),
                )
                self.rows_layout.addWidget(row)
                self._blocked_rows.append(row)

        self._update_count()
        self._apply_filter()

        self._apply_theme()

    def _filter_list(self, text: str):
        """Фильтрует список по введённому тексту"""
        self._apply_filter()

    def _apply_filter(self):
        """Применяет текущий фильтр к рядам"""
        search = self.search_input.text().lower().strip()
        for row in self._blocked_rows:
            hostname = row.hostname.lower()
            row.setVisible(search in hostname if search else True)

    def _on_row_strategy_changed(self, hostname: str, old_strategy: int, new_strategy: int, askey: str):
        """Автосохранение при изменении стратегии в SpinBox"""
        if is_orchestra_ignored_target(hostname):
            self._show_ignored_target_warning(hostname)
            self._refresh_data()
            return

        runner = self._get_runner()
        if runner and hasattr(runner, 'blocked_manager'):
            # Удаляем старую блокировку и добавляем новую
            runner.blocked_manager.unblock(hostname, old_strategy, askey)
            runner.blocked_manager.block(hostname, new_strategy, askey)
            log(f"Изменена блокировка: {hostname} [{askey.upper()}] #{old_strategy} -> #{new_strategy}", "INFO")
        else:
            log(f"Не удалось изменить блокировку: оркестратор не запущен", "WARNING")

    def _on_row_delete_requested(self, hostname: str, strategy: int, askey: str):
        """Разблокирование при нажатии кнопки удаления"""
        runner = self._get_runner()
        if not runner:
            return

        success = runner.blocked_manager.unblock(hostname, strategy, askey)
        if success:
            log(f"Разблокирована стратегия #{strategy} для {hostname} [{askey.upper()}]", "INFO")
            # Перезапускаем оркестратор чтобы применить изменения
            if runner.is_running():
                runner.restart()
                if InfoBar is not None:
                    InfoBar.success(
                        title=self._tr("page.orchestra.blocked.infobar.applied.title", "Применено"),
                        content=self._tr(
                            "page.orchestra.blocked.infobar.unblocked",
                            "Стратегия #{strategy} разблокирована для {domain}. Оркестратор перезапускается.",
                            strategy=strategy,
                            domain=hostname,
                        ),
                        isClosable=True,
                        duration=3000,
                        parent=self.window(),
                    )
        self._refresh_data()

    def _prefill_domain(self, hostname: str):
        """Заполняет форму добавления указанным доменом и фокусируется на SpinBox"""
        self.domain_input.setText(hostname)
        self.strat_spin.setFocus()
        self.strat_spin.selectAll()

    def _update_count(self):
        """Обновляет счётчик"""
        runner = self._get_runner()

        # Источник данных
        if runner:
            blocked_data = runner.blocked_manager.blocked_by_askey
            blocked_manager = runner.blocked_manager
        elif hasattr(self, '_direct_blocked_by_askey'):
            blocked_data = self._direct_blocked_by_askey
            blocked_manager = None
        else:
            self.count_label.setText(
                self._tr("page.orchestra.blocked.count.reload_hint", "Нажмите 'Обновить' для загрузки данных")
            )
            return

        user_count = 0
        default_count = 0
        for askey in ASKEY_ALL:
            for hostname, strategies in blocked_data.get(askey, {}).items():
                for strategy in strategies:
                    if blocked_manager:
                        is_default = blocked_manager.is_default_blocked(hostname, strategy)
                    else:
                        from orchestra.blocked_strategies_manager import is_default_blocked_pass_domain
                        is_default = (strategy == 1 and askey == "tls" and is_default_blocked_pass_domain(hostname))
                    if is_default:
                        default_count += 1
                    else:
                        user_count += 1
        total = user_count + default_count
        self.count_label.setText(
            self._tr(
                "page.orchestra.blocked.count.total",
                "Всего: {total} ({user_count} пользовательских + {default_count} системных)",
                total=total,
                user_count=user_count,
                default_count=default_count,
            )
        )

    def _block_strategy(self):
        """Блокирует стратегию"""
        if self._cleanup_in_progress:
            return
        runner = self._get_runner()
        if not runner:
            return

        domain = self.domain_input.text().strip().lower()
        if not domain:
            return

        if is_orchestra_ignored_target(domain):
            self._show_ignored_target_warning(domain)
            return

        strategy = self.strat_spin.value()
        askey = self.proto_combo.currentText().lower()

        # Очищаем поле после добавления
        self.domain_input.clear()

        runner.blocked_manager.block(domain, strategy, askey, user_block=True)
        log(f"Заблокирована стратегия #{strategy} для {domain} [{askey.upper()}]", "INFO")
        self._refresh_data()

        # Перезапускаем оркестратор чтобы применить изменения
        if runner.is_running():
            runner.restart()
            if InfoBar is not None:
                InfoBar.success(
                    title=self._tr("page.orchestra.blocked.infobar.applied.title", "Применено"),
                    content=self._tr(
                        "page.orchestra.blocked.infobar.blocked",
                        "Стратегия #{strategy} заблокирована для {domain}. Оркестратор перезапускается.",
                        strategy=strategy,
                        domain=domain,
                    ),
                    isClosable=True,
                    duration=3000,
                    parent=self.window(),
                )

    def _unblock_all(self):
        """Очищает пользовательский чёрный список (системные блокировки остаются)"""
        if self._cleanup_in_progress:
            return
        runner = self._get_runner()
        if not runner:
            return

        # Считаем только пользовательские блокировки по всем askey
        user_count = 0
        for askey in ASKEY_ALL:
            for hostname, strategies in runner.blocked_manager.blocked_by_askey.get(askey, {}).items():
                for strategy in strategies:
                    if not runner.blocked_manager.is_default_blocked(hostname, strategy):
                        user_count += 1

        if user_count == 0:
            if InfoBar is not None:
                InfoBar.info(
                    title=self._tr("page.orchestra.blocked.infobar.info.title", "Информация"),
                    content=self._tr(
                        "page.orchestra.blocked.infobar.no_user_blocks",
                        "Нет пользовательских блокировок для удаления. Системные блокировки не удаляются.",
                    ),
                    isClosable=True,
                    duration=4000,
                    parent=self.window(),
                )
            return

        confirmed = True
        if MessageBox is not None:
            box = MessageBox(
                self._tr("page.orchestra.blocked.dialog.clear_user.title", "Подтверждение"),
                self._tr(
                    "page.orchestra.blocked.dialog.clear_user.body",
                    "Очистить пользовательский чёрный список ({count} записей)?\n\nСистемные блокировки останутся.",
                    count=user_count,
                ),
                self.window(),
            )
            confirmed = bool(box.exec())
        if confirmed:
            runner.blocked_manager.clear()
            log(f"Очищен пользовательский чёрный список ({user_count} записей)", "INFO")
            self._refresh_data()
            # Перезапускаем оркестратор чтобы применить изменения
            if runner.is_running():
                runner.restart()
                if InfoBar is not None:
                    InfoBar.success(
                        title=self._tr("page.orchestra.blocked.infobar.applied.title", "Применено"),
                        content=self._tr(
                            "page.orchestra.blocked.infobar.cleared",
                            "Чёрный список очищен. Оркестратор перезапускается.",
                        ),
                        isClosable=True,
                        duration=3000,
                        parent=self.window(),
                    )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._refresh_loading = False
