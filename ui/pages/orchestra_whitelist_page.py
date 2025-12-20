# ui/pages/orchestra_whitelist_page.py
"""
Страница управления белым списком оркестратора (whitelist)
Домены из этого списка НЕ обрабатываются оркестратором.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QFrame, QMessageBox
)
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard
from log import log


class OrchestraWhitelistPage(BasePage):
    """Страница управления белым списком оркестратора"""

    def __init__(self, parent=None):
        super().__init__(
            "Белый список",
            "Домены, которые НЕ обрабатываются оркестратором. Эти сайты работают без DPI bypass.",
            parent
        )
        self.setObjectName("orchestraWhitelistPage")
        self._runner_cache = None  # Кэш для runner когда оркестратор не запущен
        self._setup_ui()

    def _setup_ui(self):
        # === Предупреждение о рестарте ===
        self.restart_warning = QLabel(
            "⚠️ Изменения применятся после перезапуска оркестратора"
        )
        self.restart_warning.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 193, 7, 0.15);
                border: 1px solid rgba(255, 193, 7, 0.3);
                border-radius: 6px;
                padding: 10px 14px;
                color: #ffc107;
                font-size: 12px;
            }
        """)
        self.restart_warning.hide()
        self.layout.addWidget(self.restart_warning)

        # === Карточка добавления ===
        add_card = SettingsCard("Добавить домен")
        add_layout = QVBoxLayout()
        add_layout.setSpacing(12)

        # Подсказка
        hint_label = QLabel("Введите домен, который не нужно обрабатывать")
        hint_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        add_layout.addWidget(hint_label)

        # Поле ввода и кнопка
        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("example.com")
        self.domain_input.returnPressed.connect(self._add_domain)
        self.domain_input.setStyleSheet("""
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
        input_row.addWidget(self.domain_input, 1)

        self.add_btn = QPushButton("+ ДОБАВИТЬ")
        self.add_btn.clicked.connect(self._add_domain)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                color: rgba(255, 255, 255, 0.7);
                padding: 8px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.3);
            }
        """)
        input_row.addWidget(self.add_btn)

        self.remove_btn = QPushButton("УДАЛИТЬ")
        self.remove_btn.clicked.connect(self._remove_domain)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                color: rgba(255, 255, 255, 0.7);
                padding: 8px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.3);
            }
        """)
        input_row.addWidget(self.remove_btn)

        add_layout.addLayout(input_row)
        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка доменов ===
        domains_card = SettingsCard("Белый список доменов")
        domains_layout = QVBoxLayout()
        domains_layout.setSpacing(12)

        domains_hint = QLabel("🔒 Системные домены (нельзя удалить) | ✏️ Пользовательские (можно удалить)")
        domains_hint.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 11px;")
        domains_layout.addWidget(domains_hint)

        self.domains_list = QListWidget()
        self.domains_list.setMinimumHeight(300)
        self.domains_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                color: white;
                padding: 8px;
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
        domains_layout.addWidget(self.domains_list, 1)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        domains_layout.addWidget(self.count_label)

        domains_card.add_layout(domains_layout)
        self.layout.addWidget(domains_card, 1)

    def showEvent(self, event):
        """При показе страницы обновляем данные"""
        super().showEvent(event)
        self._refresh_data()

    def _get_runner(self):
        """Получает orchestra_runner из главного окна или создаёт временный"""
        # Сначала пробуем из главного окна
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner
        
        # Если нет - создаём/используем кэшированный для работы с whitelist
        if not self._runner_cache:
            try:
                from orchestra.orchestra_runner import OrchestraRunner
                self._runner_cache = OrchestraRunner()
            except Exception as e:
                log(f"Ошибка создания OrchestraRunner: {e}", "ERROR")
                return None
        return self._runner_cache

    def _is_orchestra_running(self) -> bool:
        """Проверяет, запущен ли оркестратор"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner.is_running()
        return False

    def _refresh_data(self):
        """Обновляет список доменов"""
        self.domains_list.clear()
        runner = self._get_runner()
        if not runner:
            self.count_label.setText("Ошибка инициализации")
            return

        # Получаем полный список с пометками о типе
        whitelist = runner.get_whitelist()
        
        system_count = 0
        user_count = 0
        
        for entry in whitelist:
            domain = entry['domain']
            is_default = entry['is_default']
            
            # Формируем текст с иконкой
            if is_default:
                text = f"🔒 {domain}"
                system_count += 1
            else:
                text = f"✏️ {domain}"
                user_count += 1
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, domain)  # Сохраняем чистый домен для удаления
            item.setData(Qt.ItemDataRole.UserRole + 1, is_default)  # Флаг системного
            
            # Системные - светлее, нельзя выбрать для удаления
            if is_default:
                item.setForeground(Qt.GlobalColor.gray)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            
            self.domains_list.addItem(item)

        self.count_label.setText(f"Всего: {len(whitelist)} ({system_count} системных + {user_count} пользовательских)")

    def _show_restart_warning(self):
        """Показывает предупреждение о необходимости рестарта"""
        if self._is_orchestra_running():
            self.restart_warning.show()

    def _add_domain(self):
        """Добавляет домен в пользовательский whitelist"""
        domain = self.domain_input.text().strip().lower()
        if not domain:
            return

        runner = self._get_runner()
        if not runner:
            QMessageBox.warning(self, "Ошибка", "Не удалось инициализировать оркестратор")
            return

        if runner.add_to_whitelist(domain):
            self.domain_input.clear()
            self._refresh_data()
            self._show_restart_warning()
            log(f"Добавлен в белый список: {domain}", "INFO")
        else:
            QMessageBox.information(self, "Информация", f"Домен {domain} уже в списке")

    def _remove_domain(self):
        """Удаляет выбранный домен из пользовательского whitelist"""
        item = self.domains_list.currentItem()
        if not item:
            QMessageBox.information(self, "Информация", "Выберите домен для удаления")
            return

        # Проверяем что это не системный домен
        is_default = item.data(Qt.ItemDataRole.UserRole + 1)
        if is_default:
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить системный домен")
            return

        domain = item.data(Qt.ItemDataRole.UserRole)
        runner = self._get_runner()
        if not runner:
            return

        if runner.remove_from_whitelist(domain):
            self._refresh_data()
            self._show_restart_warning()
            log(f"Удалён из белого списка: {domain}", "INFO")
