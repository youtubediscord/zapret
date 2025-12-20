# ui/pages/orchestra_locked_page.py
"""
Страница управления залоченными стратегиями оркестратора
Оптимизирована для работы с большими списками (QListWidget с виртуализацией)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QMenu, QListWidget, QListWidgetItem,
    QLineEdit, QSpinBox, QFrame, QMessageBox, QApplication
)
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard
from log import log


class OrchestraLockedPage(BasePage):
    """Страница управления залоченными стратегиями"""

    def __init__(self, parent=None):
        super().__init__(
            "Залоченные стратегии",
            "Домены с фиксированной стратегией. Оркестратор не будет менять стратегию для этих доменов. Это значит что оркестратор нашёл для этих сайтов наилучшую стратегию. Вы можете зафиксировать свою стратегию для домена здесь.\nЕсли Вас не устраивает текущая стратегия - заблокируйте её здесь и оркестратор начнёт обучение заново при следующем посещении сайта.\nЕсли Вы просто хотите начать обучение заново - разлочьте стратегию.",
            parent
        )
        self.setObjectName("orchestraLockedPage")
        self._all_locked_data = []  # Кэш данных для фильтрации
        # Инициализируем пустые данные (будут загружены при первом showEvent)
        self._direct_locked = {}
        self._direct_http_locked = {}
        self._direct_udp_locked = {}
        self._initial_load_done = False
        self._setup_ui()

    def _setup_ui(self):
        # === Карточка добавления ===
        add_card = SettingsCard("Залочить стратегию")
        add_layout = QVBoxLayout()
        add_layout.setSpacing(12)

        # Секция: Из обученных доменов
        learned_label = QLabel("Выбрать из обученных")
        learned_label.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 600;")
        add_layout.addWidget(learned_label)

        # Комбобокс для обученных доменов
        self.domain_combo = QComboBox()
        self.domain_combo.setMaxVisibleItems(15)
        self.domain_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #0078d4;
            }
        """)
        add_layout.addWidget(self.domain_combo)

        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); margin: 8px 0;")
        separator.setFixedHeight(1)
        add_layout.addWidget(separator)

        # Секция: Ручной ввод
        custom_label = QLabel("Или ввести вручную")
        custom_label.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 600;")
        add_layout.addWidget(custom_label)

        # Ручной ввод
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.custom_domain_input = QLineEdit()
        self.custom_domain_input.setPlaceholderText("example.com")
        self.custom_domain_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 8px 12px;
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        custom_row.addWidget(self.custom_domain_input, 2)

        self.custom_proto_combo = QComboBox()
        self.custom_proto_combo.addItems(["TLS (443)", "HTTP (80)", "UDP"])
        self.custom_proto_combo.setStyleSheet(self.domain_combo.styleSheet())
        custom_row.addWidget(self.custom_proto_combo)
        add_layout.addLayout(custom_row)

        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); margin: 8px 0;")
        separator2.setFixedHeight(1)
        add_layout.addWidget(separator2)

        # Номер стратегии и кнопка
        strat_row = QHBoxLayout()
        strat_row.setSpacing(12)

        strat_label = QLabel("Стратегия #")
        strat_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
        strat_row.addWidget(strat_label)

        self.strat_spin = QSpinBox()
        self.strat_spin.setRange(1, 999)
        self.strat_spin.setValue(1)
        self.strat_spin.setStyleSheet("""
            QSpinBox {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 70px;
            }
            QSpinBox:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QSpinBox:focus {
                border: 1px solid #60cdff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        strat_row.addWidget(self.strat_spin)
        strat_row.addStretch()

        self.lock_btn = QPushButton("Залочить")
        self.lock_btn.setIcon(qta.icon("mdi.lock", color="#4CAF50"))
        self.lock_btn.clicked.connect(self._lock_strategy)
        self.lock_btn.setStyleSheet("""
            QPushButton {
                background: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 6px;
                color: #4CAF50;
                padding: 8px 24px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(76, 175, 80, 0.3);
            }
        """)
        strat_row.addWidget(self.lock_btn)
        add_layout.addLayout(strat_row)

        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка ===
        list_card = SettingsCard("Список залоченных")
        list_layout = QVBoxLayout()
        list_layout.setSpacing(8)

        # Кнопка и счётчик сверху
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Поиск
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по доменам...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_list)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 200px;
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        top_row.addWidget(self.search_input)

        # Кнопка обновления списка из реестра
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.setIcon(qta.icon("mdi.refresh", color="#60cdff"))
        self.refresh_btn.clicked.connect(self._reload_from_registry)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(96, 205, 255, 0.15);
                border: 1px solid rgba(96, 205, 255, 0.3);
                border-radius: 6px;
                color: #60cdff;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(96, 205, 255, 0.25);
            }
        """)
        top_row.addWidget(self.refresh_btn)

        self.unlock_all_btn = QPushButton("Разлочить все")
        self.unlock_all_btn.setIcon(qta.icon("mdi.lock-open-variant-outline", color="#ff9800"))
        self.unlock_all_btn.clicked.connect(self._unlock_all)
        self.unlock_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 152, 0, 0.15);
                border: 1px solid rgba(255, 152, 0, 0.3);
                border-radius: 6px;
                color: #ff9800;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 152, 0, 0.25);
            }
        """)
        top_row.addWidget(self.unlock_all_btn)
        top_row.addStretch()

        list_layout.addLayout(top_row)

        # Счётчик на отдельной строке (чтобы влезал в таб)
        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        list_layout.addWidget(self.count_label)

        # Подсказка
        hint_label = QLabel("ПКМ по строке для действий")
        hint_label.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 10px; font-style: italic;")
        list_layout.addWidget(hint_label)

        # QListWidget - быстрый даже с тысячами элементов
        self.locked_list = QListWidget()
        self.locked_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.locked_list.customContextMenuRequested.connect(self._show_context_menu)
        self.locked_list.setMinimumHeight(300)
        self.locked_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                color: white;
                font-size: 13px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: rgba(96, 205, 255, 0.2);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        list_layout.addWidget(self.locked_list)

        list_card.add_layout(list_layout)
        self.layout.addWidget(list_card)

        # Подключаем сигналы
        self.domain_combo.currentIndexChanged.connect(self._on_domain_changed)

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

    def _refresh_data(self):
        """Обновляет все данные на странице (из памяти)"""
        self._refresh_domain_combo()
        self._refresh_locked_list()

    def _reload_from_registry(self):
        """Перезагружает данные из реестра и обновляет список"""
        # Визуальный фидбек
        old_text = self.refresh_btn.text()
        self.refresh_btn.setText("Загрузка...")
        self.refresh_btn.setEnabled(False)
        QApplication.processEvents()  # Обновить UI сразу

        try:
            runner = self._get_runner()
            if runner and hasattr(runner, 'locked_manager'):
                # Перезагружаем данные из реестра
                runner.locked_manager.load()
                # Синхронизируем ссылки в runner
                runner.locked_strategies = runner.locked_manager.locked_strategies
                runner.http_locked_strategies = runner.locked_manager.http_locked_strategies
                runner.udp_locked_strategies = runner.locked_manager.udp_locked_strategies
                log("Список залоченных перезагружен из реестра (runner)", "INFO")
            else:
                # Нет активного runner - загружаем напрямую из реестра
                self._load_directly_from_registry()
                log("Список залоченных перезагружен из реестра (direct)", "INFO")
            # Обновляем UI
            self._refresh_data()
        finally:
            # Восстанавливаем кнопку
            self.refresh_btn.setText(old_text)
            self.refresh_btn.setEnabled(True)

    def _load_directly_from_registry(self):
        """Загружает данные напрямую из реестра (без активного runner)"""
        from orchestra.locked_strategies_manager import LockedStrategiesManager
        # Создаём временный менеджер для загрузки данных
        temp_manager = LockedStrategiesManager()
        temp_manager.load()
        # Сохраняем данные для отображения
        self._direct_locked = temp_manager.locked_strategies.copy()
        self._direct_http_locked = temp_manager.http_locked_strategies.copy()
        self._direct_udp_locked = temp_manager.udp_locked_strategies.copy()
        total = len(self._direct_locked) + len(self._direct_http_locked) + len(self._direct_udp_locked)
        log(f"Загружено напрямую из реестра: {total} залоченных стратегий", "INFO")

    def _refresh_domain_combo(self):
        """Обновляет комбобокс с обученными доменами"""
        self.domain_combo.clear()
        runner = self._get_runner()
        if not runner:
            self.domain_combo.addItem("Оркестратор не запущен", None)
            self.domain_combo.setEnabled(False)
            return

        self.domain_combo.setEnabled(True)
        learned = runner.get_learned_data()

        all_domains = []
        for domain, strats in learned.get('tls', {}).items():
            if strats:
                all_domains.append((domain, strats[0], 'tls'))
        for domain, strats in learned.get('http', {}).items():
            if strats:
                all_domains.append((domain, strats[0], 'http'))
        for ip, strats in learned.get('udp', {}).items():
            if strats:
                all_domains.append((ip, strats[0], 'udp'))

        all_domains.sort(key=lambda x: x[0].lower())

        if all_domains:
            for domain, strat, proto in all_domains:
                self.domain_combo.addItem(f"{domain} (#{strat}, {proto.upper()})", (domain, strat, proto))
        else:
            self.domain_combo.addItem("Нет обученных доменов", None)

    def _refresh_locked_list(self):
        """Обновляет список залоченных стратегий"""
        self.locked_list.clear()
        self._all_locked_data = []

        runner = self._get_runner()

        # Источник данных: runner или напрямую загруженные из реестра
        if runner:
            tls_data = runner.locked_strategies
            http_data = runner.http_locked_strategies
            udp_data = runner.udp_locked_strategies
        elif hasattr(self, '_direct_locked'):
            tls_data = self._direct_locked
            http_data = self._direct_http_locked
            udp_data = self._direct_udp_locked
        else:
            # Нет данных - попробуем загрузить
            self._load_directly_from_registry()
            tls_data = getattr(self, '_direct_locked', {})
            http_data = getattr(self, '_direct_http_locked', {})
            udp_data = getattr(self, '_direct_udp_locked', {})

        # Собираем все данные
        for domain, strategy in tls_data.items():
            self._all_locked_data.append((domain, strategy, "tls"))
        for domain, strategy in http_data.items():
            self._all_locked_data.append((domain, strategy, "http"))
        for ip, strategy in udp_data.items():
            self._all_locked_data.append((ip, strategy, "udp"))

        self._all_locked_data.sort(key=lambda x: x[0].lower())

        # Добавляем в список
        for domain, strategy, proto in self._all_locked_data:
            text = f"{domain}  →  стратегия #{strategy}  [{proto.upper()}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (domain, strategy, proto))
            self.locked_list.addItem(item)

        self._update_count()

    def _filter_list(self, text: str):
        """Фильтрует список по введённому тексту"""
        search = text.lower().strip()
        for i in range(self.locked_list.count()):
            item = self.locked_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                domain = data[0].lower()
                item.setHidden(search not in domain if search else False)

    def _show_context_menu(self, pos):
        """Показывает контекстное меню для выбранного элемента"""
        item = self.locked_list.itemAt(pos)
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: white;
            }
            QMenu::item:selected {
                background-color: rgba(76, 175, 80, 0.3);
            }
        """)
        unlock_action = menu.addAction(qta.icon("mdi.lock-open", color="#4CAF50"), "Разлочить")
        block_action = menu.addAction(qta.icon("mdi.block-helper", color="#e91e63"), "Заблокировать (не работает)")

        action = menu.exec(self.locked_list.mapToGlobal(pos))
        if action == unlock_action:
            self._unlock_by_data(data)
        elif action == block_action:
            self._block_by_data(data)

    def _unlock_by_data(self, data):
        """Разлочивает стратегию по данным"""
        runner = self._get_runner()
        if not runner:
            return

        domain, strategy, proto = data
        runner.locked_manager.unlock(domain, proto)
        log(f"Разлочена стратегия #{strategy} для {domain} [{proto.upper()}]", "INFO")
        self._refresh_data()

    def _block_by_data(self, data):
        """Блокирует стратегию (добавляет в чёрный список)"""
        runner = self._get_runner()
        if not runner:
            return

        domain, strategy, proto = data
        # Сначала разлочиваем, потом блокируем
        runner.locked_manager.unlock(domain, proto)
        runner.blocked_manager.block(domain, strategy, proto)
        log(f"Заблокирована стратегия #{strategy} для {domain} [{proto.upper()}] — оркестратор найдёт другую", "INFO")
        self._refresh_data()

    def _update_count(self):
        """Обновляет счётчик"""
        runner = self._get_runner()
        if runner:
            tls_count = len(runner.locked_strategies)
            http_count = len(runner.http_locked_strategies)
            udp_count = len(runner.udp_locked_strategies)
        elif hasattr(self, '_direct_locked'):
            tls_count = len(self._direct_locked)
            http_count = len(self._direct_http_locked)
            udp_count = len(self._direct_udp_locked)
        else:
            self.count_label.setText("Нажмите 'Обновить' для загрузки данных")
            return

        total = tls_count + http_count + udp_count
        self.count_label.setText(
            f"Всего залочено: {total} (TLS: {tls_count}, HTTP: {http_count}, UDP: {udp_count})"
        )

    def _on_domain_changed(self, index):
        """При смене домена обновляем номер стратегии"""
        data = self.domain_combo.itemData(index)
        if data:
            self.strat_spin.setValue(data[1])

    def _lock_strategy(self):
        """Залочивает стратегию"""
        runner = self._get_runner()
        if not runner:
            return

        strategy = self.strat_spin.value()

        # Приоритет: если в поле ввода есть текст - используем его
        custom_domain = self.custom_domain_input.text().strip().lower()
        if custom_domain:
            domain = custom_domain
            proto_text = self.custom_proto_combo.currentText()
            if "TLS" in proto_text:
                proto = "tls"
            elif "HTTP" in proto_text:
                proto = "http"
            else:
                proto = "udp"
            # Очищаем поле после добавления
            self.custom_domain_input.clear()
        else:
            # Используем выбор из комбобокса
            data = self.domain_combo.currentData()
            if not data:
                return
            domain, _, proto = data

        runner.locked_manager.lock(domain, strategy, proto)
        log(f"Залочена стратегия #{strategy} для {domain} [{proto.upper()}]", "INFO")
        self._refresh_data()

    def _unlock_all(self):
        """Разлочивает все стратегии"""
        runner = self._get_runner()
        if not runner:
            return

        total = len(runner.locked_strategies) + len(runner.http_locked_strategies) + len(runner.udp_locked_strategies)
        if total == 0:
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Разлочить все {total} стратегий?\nОркестратор начнёт обучение заново.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for domain in list(runner.locked_strategies.keys()):
                runner.locked_manager.unlock(domain, "tls")
            for domain in list(runner.http_locked_strategies.keys()):
                runner.locked_manager.unlock(domain, "http")
            for ip in list(runner.udp_locked_strategies.keys()):
                runner.locked_manager.unlock(ip, "udp")
            log(f"Разлочены все {total} стратегий", "INFO")
            self._refresh_data()
