# ui/pages/hosts_page.py
"""Страница управления Hosts файлом - разблокировка сервисов"""

import os
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox
)
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard
from log import log
from utils import get_system32_path

# Импортируем сервисы и домены
try:
    from hosts.proxy_domains import PROXY_DOMAINS, QUICK_SERVICES, PRESETS, get_service_domains, get_preset_domains
except ImportError:
    PROXY_DOMAINS = {}
    QUICK_SERVICES = []
    PRESETS = {}
    def get_service_domains(s): return {}
    def get_preset_domains(p): return {}

# Импортируем функции реестра
try:
    from config import get_active_hosts_domains, set_active_hosts_domains
except ImportError:
    def get_active_hosts_domains(): return set()
    def set_active_hosts_domains(d): return False


class QuickServiceButton(QPushButton):
    """Кнопка быстрого выбора сервиса"""
    
    def __init__(self, icon_name: str, name: str, icon_color: str = "#ffffff", is_active: bool = False, parent=None):
        super().__init__(parent)
        self.service_name = name
        self.icon_name = icon_name
        self.icon_color = icon_color
        
        self.setText(name)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(is_active)
        self._update_style()
        
    def _update_style(self):
        from PyQt6.QtCore import QSize
        # Устанавливаем иконку с правильным цветом
        if self.isChecked():
            self.setIcon(qta.icon(self.icon_name, color='white'))
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3182ce; color: white;
                    border: none; border-radius: 4px;
                    font-size: 10px; font-weight: 600; padding: 2px 8px;
                }
                QPushButton:hover { background-color: #2b6cb0; }
            """)
        else:
            self.setIcon(qta.icon(self.icon_name, color=self.icon_color))
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.06);
                    color: rgba(255,255,255,0.8);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 4px; font-size: 10px; padding: 2px 8px;
                }
                QPushButton:hover { background-color: rgba(255,255,255,0.1); }
            """)
        self.setIconSize(QSize(14, 14))
            
    def set_active(self, active: bool):
        self.blockSignals(True)
        self.setChecked(active)
        self.blockSignals(False)
        self._update_style()


class HostsWorker(QObject):
    """Воркер для асинхронных операций с hosts файлом"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, hosts_manager, operation, domains=None):
        super().__init__()
        self.hosts_manager = hosts_manager
        self.operation = operation
        self.domains = domains
        
    def run(self):
        try:
            success = False
            message = ""
            
            if self.operation == 'apply':
                if not self.domains:
                    success = self.hosts_manager.clear_hosts_file()
                    message = "Hosts очищен" if success else "Ошибка"
                else:
                    success = self.hosts_manager.apply_selected_domains(self.domains)
                    message = f"Применено {len(self.domains)} доменов" if success else "Ошибка"
                        
            elif self.operation == 'adobe_add':
                success = self.hosts_manager.add_adobe_domains()
                message = "Adobe заблокирован" if success else "Ошибка"
                
            elif self.operation == 'adobe_remove':
                success = self.hosts_manager.remove_adobe_domains()
                message = "Adobe разблокирован" if success else "Ошибка"
            
            self.finished.emit(success, message)
            
        except Exception as e:
            log(f"Ошибка в HostsWorker: {e}", "ERROR")
            self.finished.emit(False, str(e))


class HostsPage(BasePage):
    """Страница управления Hosts файлом"""
    
    def __init__(self, parent=None):
        super().__init__("Hosts", "Управление разблокировкой сервисов через hosts файл", parent)
        
        self.hosts_manager = None
        self.quick_buttons = {}
        self._worker = None
        self._thread = None
        self._applying = False
        self._active_domains_cache = None  # Кеш активных доменов
        self._last_error = None  # Последняя ошибка
        self.error_panel = None  # Панель ошибок
        
        self._init_hosts_manager()
        self._build_ui()
        
    def _init_hosts_manager(self):
        try:
            from hosts.hosts import HostsManager
            self.hosts_manager = HostsManager(status_callback=lambda m: log(f"Hosts: {m}", "INFO"))
        except Exception as e:
            log(f"Ошибка инициализации HostsManager: {e}", "ERROR")
    
    def _invalidate_cache(self):
        """Сбрасывает кеш активных доменов"""
        self._active_domains_cache = None
            
    def _get_active_domains(self) -> set:
        """Возвращает активные домены с кешированием (чтобы не читать hosts 28 раз)"""
        if self._active_domains_cache is not None:
            return self._active_domains_cache
        if self.hosts_manager:
            try:
                # Пробуем прочитать hosts файл напрямую для проверки доступа
                hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
                with open(hosts_path, 'r', encoding='utf-8') as f:
                    f.read()
                self._hide_error()
                self._active_domains_cache = self.hosts_manager.get_active_domains()
                return self._active_domains_cache
            except PermissionError:
                hosts_path = os.path.join(get_system32_path(), "drivers", "etc", "hosts")
                self._show_error(
                    "Нет доступа к файлу hosts. Запустите программу от имени администратора.\n"
                    f"Путь: {hosts_path}"
                )
                return set()
            except Exception as e:
                self._show_error(f"Ошибка чтения hosts: {e}")
                return set()
        return set()
    
    def _is_service_active(self, service_name: str) -> bool:
        """Проверяет активен ли сервис (все его домены в hosts с правильными IP)"""
        active = self._get_active_domains()
        service_domains = get_service_domains(service_name)
        if not service_domains:
            return False
        # Сервис активен если хотя бы половина его доменов активна
        active_count = sum(1 for d in service_domains if d in active)
        return active_count >= len(service_domains) / 2
        
    def _build_ui(self):
        # Панель ошибок (скрыта по умолчанию)
        self._build_error_panel()
        
        # Проверяем доступ сразу при загрузке
        self._check_hosts_access()
        
        # Информационная заметка
        self._build_info_note()
        self.add_spacing(4)
        
        # Предупреждение о браузере
        self._build_browser_warning()
        self.add_spacing(6)
        
        # Статус
        self._build_status_section()
        self.add_spacing(6)
        
        # Быстрый выбор (все сервисы)
        self._build_quick_select()
        self.add_spacing(6)
        
        # Adobe
        self._build_adobe_section()
        self.add_spacing(6)
        
        # Кнопки
        self._build_actions()
        
    def _build_error_panel(self):
        """Панель для отображения ошибок доступа к hosts"""
        self.error_panel = QWidget()
        error_layout = QVBoxLayout(self.error_panel)
        error_layout.setContentsMargins(12, 10, 12, 10)
        error_layout.setSpacing(8)

        # Верхняя строка с иконкой, текстом и кнопкой закрытия
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Иконка ошибки
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color='#ff5252').pixmap(20, 20))
        top_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Текст ошибки
        self.error_text = QLabel()
        self.error_text.setWordWrap(True)
        self.error_text.setStyleSheet("color: #ff5252; font-size: 12px; background: transparent;")
        top_row.addWidget(self.error_text, 1)

        # Кнопка закрыть
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon('fa5s.times', color='rgba(255,255,255,0.5)'))
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 10px; }
        """)
        close_btn.clicked.connect(lambda: self.error_panel.hide())
        top_row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        error_layout.addLayout(top_row)

        # Кнопка восстановления прав
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(30, 0, 0, 0)  # Отступ слева под иконку

        self.restore_btn = QPushButton(" Восстановить права доступа")
        self.restore_btn.setIcon(qta.icon('fa5s.wrench', color='white'))
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.setFixedHeight(28)
        self.restore_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 152, 0, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 152, 0, 1);
            }
            QPushButton:disabled {
                background-color: rgba(255, 152, 0, 0.4);
            }
        """)
        self.restore_btn.clicked.connect(self._restore_hosts_permissions)
        btn_row.addWidget(self.restore_btn)
        btn_row.addStretch()

        error_layout.addLayout(btn_row)

        self.error_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 82, 82, 0.15);
                border: 1px solid rgba(255, 82, 82, 0.4);
                border-radius: 8px;
            }
        """)

        self.error_panel.hide()  # Скрыта по умолчанию
        self.add_widget(self.error_panel)
        
    def _show_error(self, message: str):
        """Показывает ошибку на панели"""
        self._last_error = message
        self.error_text.setText(message)
        self.error_panel.show()

    def _hide_error(self):
        """Скрывает панель ошибок"""
        self._last_error = None
        self.error_panel.hide()

    def _restore_hosts_permissions(self):
        """Восстанавливает права доступа к файлу hosts"""
        self.restore_btn.setEnabled(False)
        self.restore_btn.setText(" Восстановление...")

        try:
            from hosts.hosts import restore_hosts_permissions
            success, message = restore_hosts_permissions()

            if success:
                self._hide_error()
                self._invalidate_cache()
                self._update_ui()
                QMessageBox.information(
                    self, "Успех",
                    "Права доступа к файлу hosts успешно восстановлены!"
                )
            else:
                self._show_error(message)
                QMessageBox.warning(
                    self, "Ошибка",
                    f"Не удалось восстановить права:\n{message}\n\n"
                    "Попробуйте временно отключить защиту файла hosts "
                    "в настройках антивируса (Kaspersky, Dr.Web и т.д.)"
                )
        except Exception as e:
            log(f"Ошибка при восстановлении прав: {e}", "ERROR")
            self._show_error(f"Ошибка: {e}")
        finally:
            self.restore_btn.setEnabled(True)
            self.restore_btn.setText(" Восстановить права доступа")
    
    def _check_hosts_access(self):
        """Проверяет доступ к hosts файлу при загрузке страницы"""
        try:
            hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
            with open(hosts_path, 'r', encoding='utf-8') as f:
                f.read()
            self._hide_error()
        except PermissionError:
            self._show_error(
                "Нет доступа к файлу hosts. Скорее всего антивирус заблокировал его для записи."
            )
        except Exception as e:
            self._show_error(f"Ошибка чтения hosts: {e}")
        
    def _build_info_note(self):
        """Информационная заметка о том, зачем нужен hosts"""
        info_card = SettingsCard()
        
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        # Иконка лампочки
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.lightbulb', color='#ffc107').pixmap(20, 20))
        icon_label.setFixedSize(24, 24)
        info_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        
        # Текст пояснения
        info_text = QLabel(
            "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — "
            "это не блокировка РКН. Решается не через Zapret, а через проксирование: "
            "домены направляются через отдельный прокси-сервер в файле hosts."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("""
            color: rgba(255, 255, 255, 0.75);
            font-size: 11px;
            line-height: 1.4;
        """)
        info_layout.addWidget(info_text, 1)
        
        info_card.add_layout(info_layout)
        self.add_widget(info_card)
        
    def _build_browser_warning(self):
        """Предупреждение о необходимости перезапуска браузера"""
        warning_layout = QHBoxLayout()
        warning_layout.setContentsMargins(12, 4, 12, 4)
        warning_layout.setSpacing(10)
        
        # Иконка предупреждения
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.sync-alt', color='#ff9800').pixmap(16, 16))
        warning_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Текст предупреждения
        warning_text = QLabel(
            "После добавления или удаления доменов необходимо перезапустить браузер, "
            "чтобы изменения вступили в силу."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: rgba(255, 152, 0, 0.85); font-size: 11px; background: transparent;")
        warning_layout.addWidget(warning_text, 1)
        
        # Простой контейнер без фона
        warning_widget = QWidget()
        warning_widget.setLayout(warning_layout)
        warning_widget.setStyleSheet("background: transparent;")
        
        self.add_widget(warning_widget)
        
    def _build_status_section(self):
        status_card = SettingsCard()
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)
        
        active = self._get_active_domains()
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {'#6ccb5f' if active else '#888'}; font-size: 12px;")
        status_layout.addWidget(self.status_dot)
        
        self.status_label = QLabel(f"Активно {len(active)} доменов" if active else "Нет активных")
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px;")
        status_layout.addWidget(self.status_label, 1)
        
        status_card.add_layout(status_layout)
        self.add_widget(status_card)
        
    def _build_quick_select(self):
        self.add_section_title("Быстрый выбор")
        
        quick_card = SettingsCard()
        
        # Пресеты сначала
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        
        for preset_name, preset_data in PRESETS.items():
            icon_name, icon_color, services = preset_data
            btn = QPushButton(f" {preset_name}")
            btn.setIcon(qta.icon(icon_name, color='#60cdff'))
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(96, 205, 255, 0.08);
                    color: #60cdff;
                    border: 1px solid rgba(96, 205, 255, 0.25);
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background-color: rgba(96, 205, 255, 0.18);
                    border-color: rgba(96, 205, 255, 0.4);
                }
            """)
            btn.clicked.connect(lambda checked, p=preset_name: self._apply_preset(p))
            presets_row.addWidget(btn)
            
        presets_row.addStretch()
        quick_card.add_layout(presets_row)
        
        # Все сервисы - автоматически распределяем по рядам (по 5 в ряду)
        SERVICES_PER_ROW = 5
        
        for row_start in range(0, len(QUICK_SERVICES), SERVICES_PER_ROW):
            row = QHBoxLayout()
            row.setSpacing(6)
            
            for icon_name, name, icon_color in QUICK_SERVICES[row_start:row_start + SERVICES_PER_ROW]:
                is_active = self._is_service_active(name)
                btn = QuickServiceButton(icon_name, name, icon_color, is_active)
                btn.clicked.connect(lambda checked, n=name: self._toggle_service(n))
                self.quick_buttons[name] = btn
                row.addWidget(btn, 1)  # stretch factor 1 для равномерного распределения
            
            quick_card.add_layout(row)
        
        self.add_widget(quick_card)
        
    def _build_adobe_section(self):
        self.add_section_title("Дополнительно")
        
        adobe_card = SettingsCard()
        
        # Описание для чего нужна блокировка
        desc_label = QLabel("⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.")
        desc_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 10px; margin-bottom: 6px;")
        desc_label.setWordWrap(True)
        adobe_card.add_widget(desc_label)
        
        adobe_layout = QHBoxLayout()
        adobe_layout.setContentsMargins(0, 0, 0, 0)
        adobe_layout.setSpacing(8)
        
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.puzzle-piece', color='#ff0000').pixmap(20, 20))
        adobe_layout.addWidget(icon_label)
        
        title = QLabel("Блокировка Adobe")
        title.setStyleSheet("color: #fff; font-size: 12px; font-weight: 600;")
        adobe_layout.addWidget(title, 1)
        
        is_adobe_active = self.hosts_manager.is_adobe_domains_active() if self.hosts_manager else False
        
        self.adobe_status = QLabel("Активно" if is_adobe_active else "Откл.")
        self.adobe_status.setStyleSheet(f"color: {'#6ccb5f' if is_adobe_active else 'rgba(255,255,255,0.5)'}; font-size: 11px;")
        adobe_layout.addWidget(self.adobe_status)
        
        self.adobe_btn = QPushButton("Откл." if is_adobe_active else "Вкл.")
        self.adobe_btn.setFixedSize(50, 24)
        self.adobe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adobe_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#dc3545' if is_adobe_active else '#28a745'};
                color: white; border: none; border-radius: 4px; font-size: 10px;
            }}
            QPushButton:hover {{ background-color: {'#c82333' if is_adobe_active else '#218838'}; }}
        """)
        self.adobe_btn.clicked.connect(self._toggle_adobe)
        adobe_layout.addWidget(self.adobe_btn)
        
        adobe_card.add_layout(adobe_layout)
        self.add_widget(adobe_card)
        
    def _build_actions(self):
        actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        
        # Выбрать все
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #fff; border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px; font-size: 11px; padding: 6px 10px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.12); }
        """)
        select_all_btn.clicked.connect(self._select_all)
        actions_layout.addWidget(select_all_btn)
        
        # Очистить
        clear_btn = QPushButton("Очистить")
        clear_btn.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.7);
                color: white; border: none;
                border-radius: 4px; font-size: 11px; padding: 4px 10px;
            }
            QPushButton:hover { background-color: rgba(220, 53, 69, 0.9); }
        """)
        clear_btn.clicked.connect(self._clear_hosts)
        actions_layout.addWidget(clear_btn)
        
        actions_layout.addStretch()
        
        # Открыть файл
        open_btn = QPushButton(" Открыть")
        open_btn.setIcon(qta.icon('fa5s.external-link-alt', color='white'))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #fff; border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px; font-size: 11px; padding: 6px 10px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.12); }
        """)
        open_btn.clicked.connect(self._open_hosts_file)
        actions_layout.addWidget(open_btn)
        
        actions_card.add_layout(actions_layout)
        self.add_widget(actions_card)
        
    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТЧИКИ
    # ═══════════════════════════════════════════════════════════════
    
    def _toggle_service(self, service_name: str):
        """Переключает сервис - добавляет или удаляет все его домены"""
        if self._applying:
            return
            
        active = self._get_active_domains()
        service_domains = get_service_domains(service_name)
        
        # Проверяем текущее состояние
        is_active = self._is_service_active(service_name)
        
        if is_active:
            # Удаляем все домены сервиса
            new_domains = active - set(service_domains.keys())
        else:
            # Добавляем все домены сервиса
            new_domains = active | set(service_domains.keys())
        
        self._run_operation('apply', new_domains)
        
    def _apply_preset(self, preset_name: str):
        """Применяет пресет - выбирает только указанные сервисы"""
        if self._applying:
            return
        
        preset_domains = get_preset_domains(preset_name)
        self._run_operation('apply', set(preset_domains.keys()))
        
    def _select_all(self):
        """Выбирает все сервисы"""
        if self._applying:
            return
        self._run_operation('apply', set(PROXY_DOMAINS.keys()))
        
    def _clear_hosts(self):
        """Очищает hosts"""
        if self._applying:
            return
            
        reply = QMessageBox.question(
            self, "Очистка hosts",
            "Удалить все записи из hosts?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_operation('apply', set())
            
    def _open_hosts_file(self):
        try:
            import ctypes
            import os
            hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
            if os.path.exists(hosts_path):
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "notepad.exe", hosts_path, None, 1)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть: {e}")
            
    def _toggle_adobe(self):
        if self._applying:
            return
        is_active = self.hosts_manager.is_adobe_domains_active() if self.hosts_manager else False
        self._run_operation('adobe_remove' if is_active else 'adobe_add')
        
    def _run_operation(self, operation: str, domains: set = None):
        if not self.hosts_manager or self._applying:
            return
            
        self._applying = True
        
        self._worker = HostsWorker(self.hosts_manager, operation, domains)
        self._thread = QThread()
        
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_operation_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        self._thread.start()
        
    def _on_operation_complete(self, success: bool, message: str):
        self._applying = False
        
        # Сбрасываем кеш и обновляем UI
        self._invalidate_cache()
        self._update_ui()
        
        if success:
            self._hide_error()
            set_active_hosts_domains(self._get_active_domains())
        else:
            # Показываем ошибку на панели
            if "Permission denied" in message or "Access" in message:
                self._show_error(
                    "Нет доступа к файлу hosts. Запустите программу от имени администратора."
                )
            else:
                self._show_error(f"Ошибка: {message}")
            
    def _update_ui(self):
        """Обновляет весь UI"""
        active = self._get_active_domains()
        
        # Статус
        if active:
            self.status_dot.setStyleSheet("color: #6ccb5f; font-size: 12px;")
            self.status_label.setText(f"Активно {len(active)} доменов")
        else:
            self.status_dot.setStyleSheet("color: #888; font-size: 12px;")
            self.status_label.setText("Нет активных")
        
        # Быстрые кнопки
        for name, btn in self.quick_buttons.items():
            btn.set_active(self._is_service_active(name))
        
        # Adobe
        is_adobe = self.hosts_manager.is_adobe_domains_active() if self.hosts_manager else False
        self.adobe_status.setText("Активно" if is_adobe else "Откл.")
        self.adobe_status.setStyleSheet(f"color: {'#6ccb5f' if is_adobe else 'rgba(255,255,255,0.5)'}; font-size: 11px;")
        self.adobe_btn.setText("Откл." if is_adobe else "Вкл.")
        self.adobe_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#dc3545' if is_adobe else '#28a745'};
                color: white; border: none; border-radius: 4px; font-size: 10px;
            }}
            QPushButton:hover {{ background-color: {'#c82333' if is_adobe else '#218838'}; }}
        """)
        
    def refresh(self):
        """Обновляет страницу (сбрасывает кеш и перечитывает hosts)"""
        self._invalidate_cache()
        self._update_ui()
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log import log
        try:
            if self._thread and self._thread.isRunning():
                log("Останавливаем hosts worker...", "DEBUG")
                self._thread.quit()
                if not self._thread.wait(2000):
                    log("⚠ Hosts worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self._thread.terminate()
                        self._thread.wait(500)
                    except:
                        pass
        except Exception as e:
            log(f"Ошибка при очистке hosts_page: {e}", "DEBUG")