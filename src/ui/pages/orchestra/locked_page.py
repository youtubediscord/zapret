# ui/pages/orchestra/locked_page.py
"""
Страница управления залоченными стратегиями оркестратора.
Каждый домен отображается в виде редактируемого ряда с QSpinBox для номера стратегии.
Изменения автоматически сохраняются в реестр.
"""
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QWidget,
    QSpinBox, QFrame, QLineEdit, QPushButton
)
import qtawesome as qta

from ..base_page import BasePage
from ui.compat_widgets import set_tooltip

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
    CaptionLabel = QLabel
    BodyLabel = QLabel
    _HAS_FLUENT = False

from ui.widgets import NotificationBanner
from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from log import log
from orchestra.ignored_targets import is_orchestra_ignored_target
from orchestra.locked_strategies_manager import ASKEY_ALL


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
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

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
            self._delete_btn.setIcon(
                qta.icon("mdi.lock-open-variant-outline", color=tokens.fg)
            )

    def _on_strategy_changed(self, value: int):
        """При изменении стратегии - уведомляем родителя для автосохранения"""
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


class OrchestraLockedPage(BasePage):
    """Страница управления залоченными стратегиями"""

    def __init__(self, parent=None):
        super().__init__(
            "Залоченные стратегии",
            "Домены с фиксированной стратегией. Оркестратор не будет менять стратегию для этих доменов. Это значит что оркестратор нашёл для этих сайтов наилучшую стратегию. Вы можете зафиксировать свою стратегию для домена здесь.\nЕсли Вас не устраивает текущая стратегия - заблокируйте её здесь и оркестратор начнёт обучение заново при следующем посещении сайта.\nЕсли Вы просто хотите начать обучение заново - разлочьте стратегию.",
            parent,
            title_key="page.orchestra.locked.title",
            subtitle_key="page.orchestra.locked.subtitle",
        )
        self.setObjectName("orchestraLockedPage")
        self._hint_label = None
        self._add_card = None
        self._list_card = None
        self._all_locked_data = []  # Кэш данных для фильтрации
        # Инициализируем пустые данные (будут загружены при первом showEvent)
        self._direct_locked_by_askey = {askey: {} for askey in ASKEY_ALL}
        self._initial_load_done = False
        self._refresh_loading = False

        self.enable_deferred_ui_build(build=self._setup_ui, after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
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
        card._title_label = title_label

        return card, card_layout

    def _set_refresh_loading(self, loading: bool) -> None:
        self._refresh_loading = loading
        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            self.refresh_btn.setEnabled(not loading)
            set_tooltip(
                self.refresh_btn,
                self._tr("page.orchestra.locked.button.refresh.tooltip", "Обновить"),
            )
        self._apply_theme()

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

        # Кнопка обновления списка из реестра
        self.refresh_btn = TransparentToolButton(self)
        self.refresh_btn.setFixedSize(32, 32)
        set_tooltip(
            self.refresh_btn,
            self._tr("page.orchestra.locked.button.refresh.tooltip", "Обновить"),
        )
        self.refresh_btn.clicked.connect(self._reload_from_registry)
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

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "lock_btn") and self.lock_btn is not None:
            self.lock_btn.setIcon(qta.icon("mdi.plus", color=tokens.fg))

        if hasattr(self, "refresh_btn") and self.refresh_btn is not None:
            refresh_icon = "mdi.loading" if self._refresh_loading else "mdi.refresh"
            refresh_color = tokens.fg_faint if self._refresh_loading else tokens.fg
            self.refresh_btn.setIcon(qta.icon(refresh_icon, color=refresh_color))

        if hasattr(self, "unlock_all_btn") and self.unlock_all_btn is not None:
            self.unlock_all_btn.setIcon(qta.icon("mdi.lock-open-variant-outline", color=tokens.fg))

        # Refresh row widgets.
        try:
            for row in list(getattr(self, "_domain_rows", {}).values()):
                if hasattr(row, "refresh_theme"):
                    row.refresh_theme()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        if self.is_deferred_ui_build_pending():
            return

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

        self._refresh_data()

    def showEvent(self, event):
        """При показе страницы загружаем данные один раз (без авто-обновления)"""
        super().showEvent(event)
        # Загружаем данные только при первом показе
        if not self._initial_load_done:
            self._initial_load_done = True
            self._reload_from_registry()

    def _get_runner(self):
        """Получает orchestra_runner из главного окна"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner
        return None

    def _get_blocked_manager(self):
        """Получает blocked_strategies_manager из runner или создает временный"""
        runner = self._get_runner()
        if runner and hasattr(runner, 'blocked_manager'):
            return runner.blocked_manager
        # Создаем временный менеджер для проверки
        from orchestra.blocked_strategies_manager import BlockedStrategiesManager
        temp_manager = BlockedStrategiesManager()
        temp_manager.load()
        return temp_manager

    def _show_blocked_warning(self, domain: str, strategy: int):
        """
        Показывает предупреждение о заблокированной стратегии.

        Args:
            domain: Домен для которого заблокирована стратегия
            strategy: Номер заблокированной стратегии
        """
        message = self._tr(
            "page.orchestra.locked.warning.blocked_strategy",
            "Стратегия #{strategy} заблокирована для {domain}. Разблокируйте её на странице 'Заблокированные'.",
            strategy=strategy,
            domain=domain,
        )
        self.notification_banner.show_warning(message, auto_hide_ms=7000)

    def _show_ignored_target_warning(self, domain: str) -> None:
        message = self._tr(
            "page.orchestra.locked.warning.ignored_proxy_target",
            "Домен {domain} относится к отдельному Telegram Proxy модулю. Оркестратор не управляет такими целями.",
            domain=domain,
        )
        self.notification_banner.show_warning(message, auto_hide_ms=7000)

    def _refresh_data(self):
        """Обновляет все данные на странице (из памяти)"""
        self._refresh_locked_list()

    def _reload_from_registry(self):
        """Перезагружает данные из реестра и обновляет список"""
        self._set_refresh_loading(True)

        def _do_reload():
            try:
                runner = self._get_runner()
                if runner and hasattr(runner, 'locked_manager'):
                    runner.locked_manager.load()
                    log("Список залоченных перезагружен из реестра (runner)", "INFO")
                else:
                    self._load_directly_from_registry()
                    log("Список залоченных перезагружен из реестра (direct)", "INFO")
                self._refresh_data()
            finally:
                self._set_refresh_loading(False)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, _do_reload)

    def _load_directly_from_registry(self):
        """Загружает данные напрямую из реестра (без активного runner)"""
        from orchestra.locked_strategies_manager import LockedStrategiesManager
        # Создаём временный менеджер для загрузки данных
        temp_manager = LockedStrategiesManager()
        temp_manager.load()
        # Сохраняем данные для отображения
        self._direct_locked_by_askey = {askey: dict(temp_manager.locked_by_askey[askey]) for askey in ASKEY_ALL}
        total = sum(len(strategies) for strategies in self._direct_locked_by_askey.values())
        log(f"Загружено напрямую из реестра: {total} залоченных стратегий", "INFO")

    def _refresh_locked_list(self):
        """Обновляет список залоченных стратегий"""
        # Очищаем старые ряды
        self._domain_rows.clear()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._all_locked_data = []

        runner = self._get_runner()

        # Источник данных: runner или напрямую загруженные из реестра
        if runner:
            locked_data = runner.locked_manager.locked_by_askey
        elif hasattr(self, '_direct_locked_by_askey'):
            locked_data = self._direct_locked_by_askey
        else:
            # Нет данных - попробуем загрузить
            self._load_directly_from_registry()
            locked_data = getattr(self, '_direct_locked_by_askey', {askey: {} for askey in ASKEY_ALL})

        # Собираем все данные по всем askey
        for askey in ASKEY_ALL:
            for hostname, strategy in locked_data.get(askey, {}).items():
                self._all_locked_data.append((hostname, strategy, askey))

        self._all_locked_data.sort(key=lambda x: x[0].lower())

        # Создаём ряды для каждого домена
        for domain, strategy, proto in self._all_locked_data:
            row = LockedDomainRow(
                domain,
                strategy,
                proto,
                delete_tooltip=self._tr("page.orchestra.locked.row.unlock.tooltip", "Разлочить"),
            )
            key = f"{domain}:{proto}"
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

        # Проверяем, не заблокирована ли эта стратегия для домена
        blocked_manager = self._get_blocked_manager()
        if blocked_manager.is_blocked(domain, new_strategy):
            self._show_blocked_warning(domain, new_strategy)
            log(f"[USER] Попытка изменить на заблокированную стратегию #{new_strategy} для {domain}", "WARNING")
            # Восстанавливаем предыдущее значение в SpinBox
            key = f"{domain}:{askey}"
            if key in self._domain_rows:
                row = self._domain_rows[key]
                # Получаем текущее значение из менеджера
                runner = self._get_runner()
                if runner and hasattr(runner, 'locked_manager'):
                    current = runner.locked_manager.locked_by_askey.get(askey, {}).get(domain, 1)
                elif askey in self._direct_locked_by_askey:
                    current = self._direct_locked_by_askey[askey].get(domain, 1)
                else:
                    current = 1
                row.strat_spin.blockSignals(True)
                row.strat_spin.setValue(current)
                row.strat_spin.blockSignals(False)
            return  # Не сохраняем заблокированную стратегию

        runner = self._get_runner()
        if runner and hasattr(runner, 'locked_manager'):
            # Используем lock для изменения (он автоматически сохраняет)
            # user_lock=True - ручное изменение через UI не перезаписывается auto-lock
            runner.locked_manager.lock(domain, new_strategy, askey, user_lock=True)
            log(f"[USER] Изменена стратегия: {domain} [{askey.upper()}] -> #{new_strategy}", "INFO")
            # Регенерируем learned-strategies.lua и перезапускаем для применения user lock
            if runner.is_running():
                runner._generate_learned_lua()
                log("[USER] Перезапуск оркестратора для применения user lock...", "INFO")
                runner.restart()
        else:
            # Без runner - сохраняем напрямую в реестр
            from orchestra.locked_strategies_manager import LockedStrategiesManager
            temp_manager = LockedStrategiesManager()
            temp_manager.load()
            temp_manager.lock(domain, new_strategy, askey, user_lock=True)
            # Обновляем локальный кэш
            if askey in self._direct_locked_by_askey:
                self._direct_locked_by_askey[askey][domain] = new_strategy
            log(f"[USER] Изменена стратегия (direct): {domain} [{askey.upper()}] -> #{new_strategy}", "INFO")

    def _on_row_delete_requested(self, domain: str, askey: str):
        """Разлочивание при нажатии кнопки удаления"""
        runner = self._get_runner()
        if runner and hasattr(runner, 'locked_manager'):
            runner.locked_manager.unlock(domain, askey)
            log(f"Разлочена стратегия для {domain} [{askey.upper()}]", "INFO")
            self._refresh_data()
            # Перезапускаем оркестратор
            if runner.is_running():
                runner.restart()
                if InfoBar is not None:
                    InfoBar.success(
                        title=self._tr("page.orchestra.locked.infobar.applied.title", "Применено"),
                        content=self._tr(
                            "page.orchestra.locked.infobar.unlocked",
                            "Стратегия разлочена для {domain}. Оркестратор перезапускается.",
                            domain=domain,
                        ),
                        isClosable=True,
                        duration=3000,
                        parent=self.window()
                    )
        else:
            # Без runner - удаляем напрямую из реестра
            from orchestra.locked_strategies_manager import LockedStrategiesManager
            temp_manager = LockedStrategiesManager()
            temp_manager.load()
            temp_manager.unlock(domain, askey)
            # Обновляем локальный кэш
            if askey in self._direct_locked_by_askey and domain in self._direct_locked_by_askey[askey]:
                del self._direct_locked_by_askey[askey][domain]
            log(f"Разлочена стратегия (direct) для {domain} [{askey.upper()}]", "INFO")
            self._refresh_data()

    def _update_count(self):
        """Обновляет счётчик"""
        runner = self._get_runner()
        if runner:
            locked_data = runner.locked_manager.locked_by_askey
        elif hasattr(self, '_direct_locked_by_askey'):
            locked_data = self._direct_locked_by_askey
        else:
            self.count_label.setText(
                self._tr("page.orchestra.locked.count.reload_hint", "Нажмите 'Обновить' для загрузки данных")
            )
            return

        # Подсчёт по всем askey
        counts = {askey: len(locked_data.get(askey, {})) for askey in ASKEY_ALL}
        total = sum(counts.values())

        # Формируем вывод с разбиением по TCP/UDP
        tcp_count = counts.get('tls', 0) + counts.get('http', 0) + counts.get('mtproto', 0)
        udp_count = sum(counts.get(k, 0) for k in ['quic', 'discord', 'wireguard', 'dns', 'stun', 'unknown'])

        self.count_label.setText(
            self._tr(
                "page.orchestra.locked.count.total",
                "Всего залочено: {total} (TCP: {tcp_count}, UDP: {udp_count})",
                total=total,
                tcp_count=tcp_count,
                udp_count=udp_count,
            )
        )

    def _lock_strategy(self):
        """Залочивает стратегию"""
        domain = self.domain_input.text().strip().lower()
        if not domain:
            return

        if is_orchestra_ignored_target(domain):
            self._show_ignored_target_warning(domain)
            return

        strategy = self.strat_spin.value()
        askey = self.proto_combo.currentText().lower()

        # Проверяем, не заблокирована ли эта стратегия для домена
        blocked_manager = self._get_blocked_manager()
        if blocked_manager.is_blocked(domain, strategy):
            self._show_blocked_warning(domain, strategy)
            log(f"[USER] Попытка залочить заблокированную стратегию #{strategy} для {domain}", "WARNING")
            return  # Не лочим заблокированную стратегию

        runner = self._get_runner()
        if runner and hasattr(runner, 'locked_manager'):
            # user_lock=True - ручное добавление через UI не перезаписывается auto-lock
            runner.locked_manager.lock(domain, strategy, askey, user_lock=True)
            log(f"[USER] Залочена стратегия #{strategy} для {domain} [{askey.upper()}]", "INFO")
            # Регенерируем learned-strategies.lua и перезапускаем для применения user lock
            if runner.is_running():
                runner._generate_learned_lua()
                log("[USER] Перезапуск оркестратора для применения user lock...", "INFO")
                runner.restart()
        else:
            # Без runner - сохраняем напрямую
            from orchestra.locked_strategies_manager import LockedStrategiesManager
            temp_manager = LockedStrategiesManager()
            temp_manager.load()
            temp_manager.lock(domain, strategy, askey, user_lock=True)
            # Обновляем локальный кэш
            if askey in self._direct_locked_by_askey:
                self._direct_locked_by_askey[askey][domain] = strategy
            log(f"[USER] Залочена стратегия (direct) #{strategy} для {domain} [{askey.upper()}]", "INFO")

        # Очищаем поле и обновляем список
        self.domain_input.clear()
        self._refresh_data()

    def _unlock_all(self):
        """Разлочивает все стратегии"""
        runner = self._get_runner()
        if not runner:
            return

        total = sum(len(strategies) for strategies in runner.locked_manager.locked_by_askey.values())
        if total == 0:
            return

        if MessageBox is not None:
            box = MessageBox(
                self._tr("page.orchestra.locked.dialog.unlock_all.title", "Подтверждение"),
                self._tr(
                    "page.orchestra.locked.dialog.unlock_all.body",
                    "Разлочить все {total} стратегий?\nОркестратор начнёт обучение заново.",
                    total=total,
                ),
                self.window()
            )
            confirmed = box.exec()
        else:
            confirmed = False  # qfluentwidgets недоступен — действие отменено

        if confirmed:
            # Разлочиваем все домены по всем askey
            for askey in ASKEY_ALL:
                for domain in list(runner.locked_manager.locked_by_askey.get(askey, {}).keys()):
                    runner.locked_manager.unlock(domain, askey)
            log(f"Разлочены все {total} стратегий", "INFO")
            self._refresh_data()
            # Перезапускаем оркестратор чтобы сбросить все hrec.nstrategy
            if runner.is_running():
                runner.restart()
                if InfoBar is not None:
                    InfoBar.success(
                        title=self._tr("page.orchestra.locked.infobar.applied.title", "Применено"),
                        content=self._tr(
                            "page.orchestra.locked.infobar.unlocked_all",
                            "Разлочены все {total} стратегий. Оркестратор перезапускается.",
                            total=total,
                        ),
                        isClosable=True,
                        duration=3000,
                        parent=self.window()
                    )
