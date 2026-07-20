# log/ui/page.py
"""Страница просмотра логов в реальном времени"""

from collections import deque

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QApplication,
    QStackedWidget, QHeaderView, QTableWidgetItem
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    StrongBodyLabel,
    PushButton,
    PushButton as FluentPushButton,
    SegmentedWidget,
    ToolButton,
    InfoBar,
    TableWidget,
)
from PyQt6.QtGui import QFont, QPixmap, QPainter, QTransform, QIcon
import qtawesome as qta
import re
import time

from ui.accessibility import set_control_accessibility, set_state_text
from ui.segmented_accessibility import set_segmented_items_accessibility
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.performance_metrics import log_ui_timing_since
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.fluent_widgets import QuickActionsBar, SettingsCard, set_tooltip
from ui.log_limits import MAIN_LOG_VIEW_MAX_LINES
from log.ui.logs_build import build_logs_management_tab_ui, build_logs_primary_tab_ui, build_logs_secondary_panels_ui
from log.ui.runtime_helpers import (
    append_error,
    clear_errors,
    compute_errors_text_height,
    render_send_status_label,
)
from log.ui.send_build import (
    apply_logs_send_icon_accessibility,
    apply_logs_send_text_accessibility,
    build_logs_send_tab,
)
from log.ui.support_workflow import (
    apply_support_feedback,
    update_orchestra_indicator,
)
from app.ui_texts import tr as tr_catalog
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from log.log import log

# Паттерны для определения РЕАЛЬНЫХ ошибок (строгие)
ERROR_PATTERNS = [
    r'\[❌ ERROR\]',           # Наш формат ошибок
    r'\[❌ CRITICAL\]',        # Критические ошибки
    r'\[ERROR\]',             # Обычный log(..., "ERROR") и logging
    r'\[CRITICAL\]',          # Обычный CRITICAL без значка
    r'AttributeError:',        # Python ошибки атрибутов
    r'TypeError:',             # Python ошибки типов
    r'ValueError:',            # Python ошибки значений
    r'KeyError:',              # Python ошибки ключей
    r'ImportError:',           # Python ошибки импорта
    r'ModuleNotFoundError:',   # Python модуль не найден
    r'FileNotFoundError:',     # Файл не найден
    r'PermissionError:',       # Ошибка доступа
    r'OSError:',               # Ошибка ОС
    r'RuntimeError:',          # Ошибка выполнения
    r'UnboundLocalError:',     # Переменная не определена
    r'NameError:',             # Имя не определено
    r'IndexError:',            # Индекс за пределами
    r'ZeroDivisionError:',     # Деление на ноль
    r'RecursionError:',        # Переполнение рекурсии
    r'🔴 CRASH',               # Краш репорты
]


def _logs_accessible_state(prefix: str, text: str) -> str:
    prefix_text = " ".join(str(prefix or "").strip().split())
    value = " ".join(str(text or "").strip().split())
    if not prefix_text:
        return value
    if not value:
        return prefix_text
    if value == prefix_text or value.startswith(f"{prefix_text}:"):
        return value
    return f"{prefix_text}: {value}"

# Паттерны для ИСКЛЮЧЕНИЯ (не ошибки, хотя содержат ключевые слова)
EXCLUDE_PATTERNS = [
    r'Faulthandler enabled',   # Информация о включении faulthandler
    r'Crash handler установлен', # Информация об установке обработчика
    r'connection error:.*HTTPSConnectionPool',  # Сетевые ошибки VPS (не критично)
    r'connection error:.*HTTPConnectionPool',   # Сетевые ошибки VPS (не критично)
    r'\[POOL\].*ошибка',       # Ошибки пула серверов (fallback работает)
    r'Theme error:.*NoneType', # Ошибки темы при инициализации (временные)
]


def update_logs_tabs_accessibility(pivot, *, current: object | None = None, language: str = "ru") -> None:
    if pivot is None:
        return
    labels = {
        "logs": tr_catalog("page.logs.tab.logs", language=language, default="ЛОГИ").strip().title(),
        "send": tr_catalog("page.logs.tab.send", language=language, default="ОТПРАВКА").strip().title(),
        "manage": tr_catalog("page.logs.tab.manage", language=language, default="УПРАВЛЕНИЕ").strip().title(),
    }
    key = str(current or "").strip() if isinstance(current, str) else ""
    if not key:
        try:
            key = str(pivot.currentRouteKey() or "").strip()
        except Exception:
            key = ""
    selected = labels.get(key, key or "Логи")
    state = f"Вкладки страницы логов, выбрано: {selected}"
    set_state_text(pivot, state)
    set_control_accessibility(
        pivot,
        name=state,
        description="Выберите раздел страницы логов: Логи, Поддержка или Управление.",
    )
    set_segmented_items_accessibility(
        pivot,
        name="Вкладки страницы логов",
        labels=labels,
    )


class LogsPage(BasePage):
    """Страница просмотра логов"""
    
    def __init__(self, parent=None, *, logs_feature, orchestra_feature):
        super().__init__(
            "Логи",
            "Просмотр логов приложения в реальном времени",
            parent,
            title_key="page.logs.title",
            subtitle_key="page.logs.subtitle",
        )
        
        # Отключаем горизонтальную прокрутку страницы
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._cleanup_in_progress = False
        self._logs = logs_feature
        self._orchestra = orchestra_feature
        self.current_log_file = self._logs.get_current_log_file()
        self._log_file_signature = None
        self._displayed_log_file = None
        self._live_log_cursor = None
        self._live_log_bridge = None
        self._latest_logs_state = None
        self._error_pattern = re.compile('|'.join(ERROR_PATTERNS))
        self._exclude_pattern = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

        self._tokens = get_theme_tokens()

        # References for theme refresh (icons/labels created as locals).
        self._warning_icon_label = None
        self._info_icon_label = None
        self._orchestra_icon_label = None
        self._orchestra_text_label = None
        self._send_status_text = ""
        self._send_status_tone = "neutral"
        self._info_text_cache = ""
        self._controls_actions_title = None
        self._controls_actions_bar = None
        self._manage_tab_initialized = False
        self._send_actions_title = None
        self._send_actions_bar = None

        self._logs_overview_runtime = OneShotWorkerRuntime()
        self._logs_overview_pending_cleanup = False
        self._logs_overview_restart_scheduled = False
        self._log_reader_runtime = OneShotWorkerRuntime()
        self._log_text_cache_lines = deque(maxlen=MAIN_LOG_VIEW_MAX_LINES)
        self._pending_log_text_append = ""
        self._log_text_append_scheduled = False
        self._first_log_content_started_at = None
        self._first_log_content_timing_done = False
        self._support_prepare_runtime = OneShotWorkerRuntime()
        self._support_prepare_state = LatestValueWorkerState(self._support_prepare_runtime, empty_value=False)
        self._open_folder_runtime = OneShotWorkerRuntime()
        self._open_folder_state = LatestValueWorkerState(self._open_folder_runtime, empty_value=False)

        # Error panel height tuning (avoid large empty block when no errors).
        self._errors_text_min_height = 52
        self._errors_text_max_height = 140

        self._runtime_initialized = False
        self._send_tab_initialized = False
        self._runtime_started = False
        self._logs_secondary_initialized = False
        self._logs_secondary_build_scheduled = False
        self._runtime_init_scheduled = False

        # qtawesome animations (e.g. qta.Spin) are not QAbstractAnimation; track state ourselves.
        self._refresh_spin_active = False
        self._build_ui()
        try:
            self._apply_page_theme(force=True)
        except Exception:
            pass

    def _apply_warmed_overview_if_available(self) -> bool:
        try:
            warmed = self._logs.consume_warmed_page_data()
            if warmed is None:
                return False
            self._apply_logs_list_state(warmed.logs_state, run_cleanup=False)
            self._apply_logs_stats_state(warmed.stats_state)
            return True
        except Exception as exc:
            # Повреждённый или устаревший прогретый снимок не должен мешать
            # обычной фоновой загрузке страницы.
            log(f"Не удалось применить прогретые данные логов: {exc}", "DEBUG")
            return False

    def _run_runtime_init_once(self) -> None:
        if self._cleanup_in_progress or not self.isVisible():
            return
        started_at = time.perf_counter()
        self._apply_warmed_overview_if_available()
        self._runtime_initialized, self._runtime_started = self._logs.run_runtime_init(
            runtime_initialized=self._runtime_initialized,
            runtime_started=self._runtime_started,
            schedule_fn=QTimer.singleShot,
            update_stats_fn=self._update_stats,
            start_log_source_fn=self._start_log_source,
        )
        self._log_ui_timing("logs_ui.runtime_init.total", started_at)

    def _schedule_runtime_init(self) -> None:
        if self._runtime_init_scheduled:
            return
        self._runtime_init_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_runtime_init)

    def _run_scheduled_runtime_init(self) -> None:
        self._runtime_init_scheduled = False
        if self._cleanup_in_progress or not self.isVisible():
            return
        self._run_runtime_init_once()

    def _stop_runtime(self) -> None:
        self._stop_logs_overview_worker(blocking=False)
        self._stop_log_source(blocking=False)
        self._runtime_started = False

    def on_page_activated(self) -> None:
        if not self.__dict__.get("_first_log_content_timing_done", False):
            self._first_log_content_started_at = time.perf_counter()
        self._schedule_runtime_init()
        self._schedule_logs_secondary_panels()
        # Прогретые данные уже находятся в памяти: показываем их до следующего
        # прохода цикла Qt, чтобы пользователь не видел лишнее «Загрузка...».
        self._apply_warmed_overview_if_available()

    def on_page_hidden(self) -> None:
        self._runtime_init_scheduled = False
        self._logs_secondary_build_scheduled = False
        self._stop_runtime()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        self._tokens = tokens

        # Controls — TableWidget handles its own base theme
        # Tabs — Pivot handles its own theme

        if hasattr(self, "refresh_btn"):
            self._refresh_icon_normal = FluentIcon.SYNC
            if not bool(getattr(self, "_refresh_spin_active", False)):
                self.refresh_btn.setIcon(self._refresh_icon_normal)

        # info_label is now a CaptionLabel (Fluent) — no manual style needed

        # Log area
        editor_bg = tokens.surface_bg
        editor_fg = tokens.fg
        if hasattr(self, "log_text"):
            self.log_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {editor_bg};"
                f" color: {editor_fg};"
                f" border: 1px solid {tokens.surface_border};"
                " border-radius: 6px;"
                " padding: 12px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " line-height: 1.4;"
                " }"
            )

        # stats_label is now a CaptionLabel (Fluent) — no manual style needed

        # Errors panel
        err_fg = "rgba(220, 38, 38, 0.92)" if tokens.is_light else "rgba(248, 113, 113, 0.95)"
        err_bg = "rgba(220, 38, 38, 0.08)" if tokens.is_light else "rgba(248, 113, 113, 0.10)"
        err_border = "rgba(220, 38, 38, 0.25)" if tokens.is_light else "rgba(248, 113, 113, 0.25)"

        if self._warning_icon_label is not None:
            try:
                self._warning_icon_label.setPixmap(
                    get_cached_qta_pixmap('fa5s.exclamation-triangle', color=err_fg, size=16)
                )
            except Exception:
                pass

        # errors_count_label is now a CaptionLabel (Fluent) — no manual style needed

        if getattr(self, "errors_text", None) is not None:
            self.errors_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {err_bg};"
                f" color: {err_fg};"
                f" border: 1px solid {err_border};"
                " border-radius: 6px;"
                " padding: 8px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " }"
            )

        # Send tab (exists only after lazy init)
        if self._info_icon_label is not None:
            try:
                self._info_icon_label.setPixmap(
                    get_cached_qta_pixmap('fa5s.info-circle', color=tokens.accent_hex, size=14)
                )
            except Exception:
                pass

        # Orchestra mode indicator (Send tab, lazy-init)
        if self._orchestra_icon_label is not None:
            try:
                self._render_orchestra_banner_style(tokens)
            except Exception:
                pass

        # send_status_label shows the result of opening support links/folders
        try:
            self._render_send_status_label(tokens)
        except Exception:
            pass

    def _render_orchestra_banner_style(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        if getattr(self, "orchestra_mode_container", None) is None:
            return

        accent = "#7c3aed" if theme_tokens.is_light else "#a855f7"
        bg = "rgba(124, 58, 237, 0.12)" if theme_tokens.is_light else "rgba(168, 85, 247, 0.15)"

        if self._orchestra_icon_label is not None:
            self._orchestra_icon_label.setPixmap(
                get_cached_qta_pixmap('fa5s.brain', color=accent, size=16)
            )
        if self._orchestra_text_label is not None:
            self._orchestra_text_label.setStyleSheet(
                f"color: {accent}; font-size: 12px; font-weight: 600; background: transparent;"
            )
        self.orchestra_mode_container.setStyleSheet(
            "QWidget {"
            f" background-color: {bg};"
            " border-radius: 8px;"
            " }"
        )

    def _render_send_status_label(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        render_send_status_label(
            label=getattr(self, "send_status_label", None),
            text=str(getattr(self, "_send_status_text", "") or ""),
            tone=str(getattr(self, "_send_status_tone", "neutral") or "neutral"),
            theme_tokens=theme_tokens,
        )

    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # Переключатель табов (ЛОГИ / ОТПРАВКА) — Fluent Pivot
        # ═══════════════════════════════════════════════════════════
        self.tabs_pivot = SegmentedWidget()
        self.tabs_pivot.addItem(
            routeKey="logs",
            text=" " + tr_catalog("page.logs.tab.logs", default="ЛОГИ"),
            onClick=lambda: self._switch_tab(0),
        )
        self.tabs_pivot.addItem(
            routeKey="send",
            text=" " + tr_catalog("page.logs.tab.send", default="ОТПРАВКА"),
            onClick=lambda: self._switch_tab(1),
        )
        self.tabs_pivot.addItem(
            routeKey="manage",
            text=" " + tr_catalog("page.logs.tab.manage", default="УПРАВЛЕНИЕ"),
            onClick=lambda: self._switch_tab(2),
        )
        self.tabs_pivot.setCurrentItem("logs")
        self.tabs_pivot.setItemFontSize(13)
        self._update_tabs_accessibility("logs")
        self.tabs_pivot.currentItemChanged.connect(self._update_tabs_accessibility)
        self.add_widget(self.tabs_pivot)

        # ═══════════════════════════════════════════════════════════
        # Стек страниц (ЛОГИ / ОТПРАВКА)
        # ═══════════════════════════════════════════════════════════
        self.stacked_widget = QStackedWidget()

        # Страница 1: Логи
        self._logs_page = QWidget()
        logs_layout = QVBoxLayout(self._logs_page)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(16)
        self._logs_layout = logs_layout

        self._build_logs_tab(logs_layout)

        # Страница 2: Отправка (лениво создаётся при первом переходе)
        self._send_page = QWidget()
        send_layout = QVBoxLayout(self._send_page)
        send_layout.setContentsMargins(0, 0, 0, 0)
        send_layout.setSpacing(16)
        self._send_layout = send_layout

        # Страница 3: Управление логами
        self._manage_page = QWidget()
        manage_layout = QVBoxLayout(self._manage_page)
        manage_layout.setContentsMargins(0, 0, 0, 0)
        manage_layout.setSpacing(16)
        self._manage_layout = manage_layout
        self.stacked_widget.addWidget(self._logs_page)
        self.stacked_widget.addWidget(self._send_page)
        self.stacked_widget.addWidget(self._manage_page)

        self.add_widget(self.stacked_widget)

        # Apply token-driven styles once widgets exist.
        self._apply_page_theme()

    def _switch_tab(self, index: int):
        """Переключает между табами"""
        if index == 1 and not self._send_tab_initialized:
            self._send_tab_initialized = True
            try:
                self._build_send_tab(self._send_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки отправки: {e}", "ERROR")

        if index == 2 and not self._manage_tab_initialized:
            try:
                self._build_manage_tab(self._manage_layout)
                if self._latest_logs_state is not None:
                    self._apply_logs_list_state(self._latest_logs_state, run_cleanup=False)
                self._retranslate_logs_tab()
                self._apply_page_theme(force=True)
            except Exception as e:
                log(f"Ошибка построения вкладки управления логами: {e}", "ERROR")

        self.stacked_widget.setCurrentIndex(index)

        # Sync Pivot indicator
        key = "send" if index == 1 else ("manage" if index == 2 else "logs")
        try:
            self.tabs_pivot.setCurrentItem(key)
        except Exception:
            pass
        self._update_tabs_accessibility(key)

        if index == 1:
            # Обновляем видимость индикатора оркестратора
            self._update_orchestra_indicator()

    def _update_tabs_accessibility(self, current: object | None = None) -> None:
        update_logs_tabs_accessibility(
            self.tabs_pivot,
            current=current,
            language=self.__dict__.get("_ui_language", "ru"),
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        logs_text = " " + tr_catalog("page.logs.tab.logs", language=language, default="ЛОГИ")
        send_text = " " + tr_catalog("page.logs.tab.send", language=language, default="ОТПРАВКА")
        manage_text = " " + tr_catalog("page.logs.tab.manage", language=language, default="УПРАВЛЕНИЕ")

        try:
            self.tabs_pivot.setItemText("logs", logs_text)
            self.tabs_pivot.setItemText("send", send_text)
            self.tabs_pivot.setItemText("manage", manage_text)
            self._update_tabs_accessibility()
        except Exception:
            pass

        self._retranslate_logs_tab()
        if self._send_tab_initialized:
            self._retranslate_send_tab()
            self._render_send_status_label()

    def _set_card_title(self, card: SettingsCard, text: str) -> None:
        try:
            card.set_title(text)
        except Exception:
            pass

    def _retranslate_logs_tab(self) -> None:
        if self._controls_actions_title is not None:
            self._controls_actions_title.setText(
                tr_catalog("page.logs.actions.title", language=self._ui_language, default="Действия")
            )

        try:
            refresh_name = tr_catalog(
                "page.logs.accessibility.refresh.name",
                language=self._ui_language,
                default="Обновить список логов",
            )
            refresh_description = tr_catalog(
                "page.logs.accessibility.refresh.description",
                language=self._ui_language,
                default="Обновить список файлов логов и статистику.",
            )
            set_control_accessibility(
                self.refresh_btn,
                name=refresh_name,
                description=refresh_description,
            )
            set_state_text(self.refresh_btn, refresh_name)
            set_tooltip(
                self.refresh_btn,
                refresh_description,
            )
        except Exception:
            pass

        try:
            self.copy_btn.setText(tr_catalog("page.logs.button.copy", language=self._ui_language, default="Копировать"))
            self.clear_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.folder_btn.setText(tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка"))
            copy_name = tr_catalog(
                "page.logs.accessibility.copy.name",
                language=self._ui_language,
                default="Копировать текущий лог",
            )
            copy_description = tr_catalog(
                "page.logs.action.copy.description",
                language=self._ui_language,
                default="Скопировать содержимое текущего лога в буфер обмена.",
            )
            set_control_accessibility(self.copy_btn, name=copy_name, description=copy_description)
            set_state_text(self.copy_btn, copy_name)
            set_tooltip(
                self.copy_btn,
                copy_description,
            )
            clear_name = tr_catalog(
                "page.logs.accessibility.clear_view.name",
                language=self._ui_language,
                default="Очистить окно просмотра лога",
            )
            clear_description = tr_catalog(
                "page.logs.action.clear.description",
                language=self._ui_language,
                default="Очистить только текущее окно просмотра, не удаляя файл лога.",
            )
            set_control_accessibility(self.clear_btn, name=clear_name, description=clear_description)
            set_state_text(self.clear_btn, clear_name)
            set_tooltip(
                self.clear_btn,
                clear_description,
            )
            folder_name = tr_catalog(
                "page.logs.accessibility.folder.name",
                language=self._ui_language,
                default="Открыть папку логов",
            )
            folder_description = tr_catalog(
                "page.logs.action.folder.description",
                language=self._ui_language,
                default="Открыть папку logs с файлами приложения.",
            )
            set_control_accessibility(self.folder_btn, name=folder_name, description=folder_description)
            set_state_text(self.folder_btn, folder_name)
            set_tooltip(
                self.folder_btn,
                folder_description,
            )
        except Exception:
            pass

        if self._logs_secondary_initialized:
            try:
                self.errors_title_label.setText(tr_catalog("page.logs.errors.title", language=self._ui_language, default="Ошибки и предупреждения"))
                self.clear_errors_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
                errors_count_text = tr_catalog(
                    "page.logs.errors.count",
                    language=self._ui_language,
                    default="Ошибок: {count}",
                ).format(
                    count=max(0, int(self._errors_count))
                )
                self.errors_count_label.setText(errors_count_text)
                set_state_text(self.errors_count_label, errors_count_text)
            except Exception:
                pass

    def _retranslate_send_tab(self) -> None:
        try:
            self._set_card_title(
                self.send_card,
                tr_catalog("page.logs.send.card.title", language=self._ui_language, default="Поддержка через GitHub Discussions"),
            )
            if self._send_actions_title is not None:
                self._send_actions_title.setText(
                    tr_catalog("page.logs.send.actions.title", language=self._ui_language, default="Действия")
                )
            self._orchestra_text_label.setText(
                tr_catalog(
                    "page.logs.send.orchestra.active",
                    language=self._ui_language,
                    default="В режиме оркестратора проверьте основной лог и файл orchestra_*.log",
                )
            )
            self.send_desc_label.setText(
                tr_catalog(
                    "page.logs.send.desc",
                    language=self._ui_language,
                    default="Нажмите кнопку, чтобы собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
                )
            )
            self.send_info_label.setText(
                tr_catalog(
                    "page.logs.send.info",
                    language=self._ui_language,
                    default="Будет создан архив в папке logs/support_bundles. Шаблон обращения автоматически попадёт в буфер обмена.",
                )
            )
            apply_logs_send_text_accessibility(
                desc_label=self.send_desc_label,
                info_label=self.send_info_label,
                tr_catalog_fn=tr_catalog,
                ui_language=self._ui_language,
            )
            apply_logs_send_icon_accessibility(
                orchestra_icon_label=self.__dict__.get("_orchestra_icon_label"),
                info_icon_label=self.__dict__.get("_info_icon_label"),
                tr_catalog_fn=tr_catalog,
                ui_language=self._ui_language,
            )
            self.send_log_btn.setText(
                tr_catalog("page.logs.send.button.send", language=self._ui_language, default="Подготовить обращение")
            )
            self.open_logs_folder_btn.setText(
                tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка")
            )
            send_name = tr_catalog(
                "page.logs.send.accessibility.prepare.name",
                language=self._ui_language,
                default="Подготовить обращение в поддержку",
            )
            send_description = tr_catalog(
                "page.logs.send.action.send.description",
                language=self._ui_language,
                default="Собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
            )
            set_control_accessibility(self.send_log_btn, name=send_name, description=send_description)
            set_state_text(self.send_log_btn, send_name)
            set_tooltip(
                self.send_log_btn,
                send_description,
            )
            folder_name = tr_catalog(
                "page.logs.send.accessibility.folder.name",
                language=self._ui_language,
                default="Открыть папку логов и обращений",
            )
            folder_description = tr_catalog(
                "page.logs.send.action.folder.description",
                language=self._ui_language,
                default="Открыть папку logs, где лежат логи и подготовленные support bundles.",
            )
            set_control_accessibility(self.open_logs_folder_btn, name=folder_name, description=folder_description)
            set_state_text(self.open_logs_folder_btn, folder_name)
            set_tooltip(
                self.open_logs_folder_btn,
                folder_description,
            )
        except Exception:
            pass

    def _build_logs_tab(self, parent_layout):
        """Строит вкладку с логами"""
        logs_widgets = build_logs_primary_tab_ui(
            parent_layout=parent_layout,
            content_parent=self.content,
            ui_language=self._ui_language,
            tr_catalog_fn=tr_catalog,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            text_edit_cls=ScrollBlockingTextEdit,
            qfont_cls=QFont,
            get_theme_tokens_fn=get_theme_tokens,
        )
        self.log_card = logs_widgets.log_card
        self.log_text = logs_widgets.log_text
        self.stats_label = logs_widgets.stats_label

        # Счётчик ошибок
        self._errors_count = 0
        try:
            self.stats_label.setText(
                tr_catalog("page.logs.stats.loading", language=self._ui_language, default="📊 Загрузка...")
            )
            set_state_text(
                self.stats_label,
                _logs_accessible_state(
                    tr_catalog(
                        "page.logs.accessibility.stats.name",
                        language=self._ui_language,
                        default="Статистика логов",
                    ),
                    self.stats_label.text(),
                ),
            )
        except Exception:
            pass

    def _build_manage_tab(self, parent_layout):
        """Строит вкладку управления файлами логов."""
        manage_widgets = build_logs_management_tab_ui(
            parent_layout=parent_layout,
            content_parent=self.content,
            ui_language=self._ui_language,
            tr_catalog_fn=tr_catalog,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            caption_label_cls=CaptionLabel,
            tool_button_cls=ToolButton,
            push_button_cls=PushButton,
            table_widget_cls=TableWidget,
            table_item_cls=QTableWidgetItem,
            header_view_cls=QHeaderView,
            quick_actions_bar_cls=QuickActionsBar,
            get_theme_tokens_fn=get_theme_tokens,
            on_log_selected=self._on_log_table_cell_clicked,
            on_refresh=self._refresh_logs_list,
            on_spin_tick=self._on_spin_tick,
            on_copy=self._copy_log,
            on_clear_view=self._clear_view,
            on_open_folder=self._open_folder,
            refresh_timer_parent=self,
        )
        self.controls_card = manage_widgets.controls_card
        self.logs_table = manage_widgets.logs_table
        self.refresh_btn = manage_widgets.refresh_btn
        self.info_label = manage_widgets.info_label
        self._controls_actions_title = manage_widgets.controls_actions_title
        self._controls_actions_bar = manage_widgets.controls_actions_bar
        self.copy_btn = manage_widgets.copy_btn
        self.clear_btn = manage_widgets.clear_btn
        self.folder_btn = manage_widgets.folder_btn
        self._manage_tab_initialized = True
        if self._info_text_cache:
            self._set_info_text(self._info_text_cache)

    def _schedule_logs_secondary_panels(self) -> None:
        if self._logs_secondary_initialized or self._logs_secondary_build_scheduled:
            return
        self._logs_secondary_build_scheduled = True
        # Нижняя панель не видна на первом экране. Небольшая задержка отдаёт
        # приоритет первому куску текста текущего лога.
        QTimer.singleShot(250, self._ensure_logs_secondary_panels)

    def _ensure_logs_secondary_panels(self) -> bool:
        if self._logs_secondary_initialized:
            return True
        self._logs_secondary_build_scheduled = False
        if self._cleanup_in_progress or not self.isVisible():
            return False
        logs_layout = getattr(self, "_logs_layout", None)
        if logs_layout is None:
            return False

        logs_widgets = build_logs_secondary_panels_ui(
            parent_layout=logs_layout,
            ui_language=self._ui_language,
            tr_catalog_fn=tr_catalog,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            fluent_push_button_cls=FluentPushButton,
            text_edit_cls=ScrollBlockingTextEdit,
            qfont_cls=QFont,
            errors_text_min_height=self._errors_text_min_height,
            errors_text_max_height=self._errors_text_max_height,
            on_clear_errors=self._clear_errors,
            on_update_errors_height=self._update_errors_text_height,
        )
        self.errors_card = logs_widgets.errors_card
        self._warning_icon_label = logs_widgets.warning_icon_label
        self.errors_title_label = logs_widgets.errors_title_label
        self.errors_count_label = logs_widgets.errors_count_label
        self.clear_errors_btn = logs_widgets.clear_errors_btn
        self.errors_text = logs_widgets.errors_text

        self._logs_secondary_initialized = True
        self._update_errors_text_height()
        self._apply_page_theme(force=True)
        return True

    def _build_send_tab(self, parent_layout):
        """Строит вкладку поддержки по логам."""
        send_widgets = build_logs_send_tab(
            parent_layout=parent_layout,
            ui_language=self._ui_language,
            tr_catalog_fn=tr_catalog,
            settings_card_cls=SettingsCard,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            push_button_cls=PushButton,
            quick_actions_bar_cls=QuickActionsBar,
            qta_module=qta,
            get_theme_tokens_fn=get_theme_tokens,
            on_prepare_support=self._prepare_support_from_logs,
            on_open_folder=self._open_folder,
        )
        self.send_card = send_widgets.send_card
        self.orchestra_mode_container = send_widgets.orchestra_mode_container
        self._orchestra_icon_label = send_widgets.orchestra_icon_label
        self._orchestra_text_label = send_widgets.orchestra_text_label
        self._info_icon_label = send_widgets.info_icon_label
        self.send_desc_label = send_widgets.send_desc_label
        self.send_info_label = send_widgets.send_info_label
        self.send_status_label = send_widgets.send_status_label
        self._send_actions_title = send_widgets.send_actions_title
        self._send_actions_bar = send_widgets.send_actions_bar
        self.send_log_btn = send_widgets.send_log_btn
        self.open_logs_folder_btn = send_widgets.open_logs_folder_btn

        # Send tab is lazily built; apply current theme now.
        self._retranslate_send_tab()
        self._apply_page_theme(force=True)

    def _is_orchestra_mode(self) -> bool:
        """Проверяет, активен ли режим оркестратора"""
        from settings.mode import is_orchestra_launch_method

        return is_orchestra_launch_method(self.get_launch_method())

    def get_launch_method(self) -> str:
        """Возвращает текущий метод запуска"""
        try:
            from ui.workflows.common import get_current_launch_method

            return get_current_launch_method(default="")
        except Exception:
            return ""

    def _get_orchestra_runner(self):
        return self._orchestra.runner

    def _get_orchestra_log_path(self) -> str:
        """
        Возвращает путь к логу оркестратора.

        Приоритет:
        1. Текущий активный лог (если оркестратор запущен)
        2. Последний сохранённый лог из истории
        """
        return self._logs.get_orchestra_log_path(self._get_orchestra_runner())

    def _update_orchestra_indicator(self):
        """Обновляет видимость индикатора режима оркестратора"""
        update_orchestra_indicator(
            container=getattr(self, "orchestra_mode_container", None),
            is_orchestra_mode=self._is_orchestra_mode(),
        )

    def _prepare_support_from_logs(self):
        self._request_support_prepare()

    def _request_support_prepare(self) -> None:
        state = self._support_prepare_state_obj()
        if state.is_busy():
            state.pending = True
            return
        state.pending = False
        self._support_prepare_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._logs.create_support_prepare_worker(
                request_id,
                current_log_file=self.current_log_file,
                orchestra_runner=self._get_orchestra_runner(),
                parent=self,
            ),
            on_loaded=self._on_support_prepare_finished,
            on_failed=self._on_support_prepare_failed,
            on_finished=self._on_support_prepare_worker_finished,
        )

    def _on_support_prepare_finished(self, request_id: int, result) -> None:
        if not self._support_prepare_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self._support_prepare_state_obj().has_pending():
            return
        apply_support_feedback(
            result=result,
            build_feedback_fn=self._logs.build_support_feedback,
            build_error_feedback_fn=self._logs.build_support_error_feedback,
            info_bar=InfoBar,
            parent=self.window(),
            log_fn=log,
            render_status_fn=self._render_send_status_label,
            status_state_setter=lambda text, tone: (
                setattr(self, "_send_status_text", text),
                setattr(self, "_send_status_tone", tone),
            ),
        )

    def _on_support_prepare_failed(self, request_id: int, error: str) -> None:
        if not self._support_prepare_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self._support_prepare_state_obj().has_pending():
            return
        feedback = self._logs.build_support_error_feedback(str(error or ""))
        self._send_status_text = feedback.status_text
        self._send_status_tone = feedback.status_tone
        self._render_send_status_label()
        log(f"Ошибка подготовки обращения из логов: {error}", "ERROR")
        if InfoBar:
            InfoBar.warning(
                title=feedback.infobar_title,
                content=feedback.infobar_content,
                parent=self.window(),
            )

    def _on_support_prepare_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_support_prepare_runtime"), _worker):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._support_prepare_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_support_prepare_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )

    def _schedule_support_prepare_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        state = self._support_prepare_state_obj()
        state.pending = True
        state.schedule_start(
            QTimer.singleShot,
            self._run_scheduled_support_prepare_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_support_prepare_start(self) -> None:
        pending = self._support_prepare_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False)
        )
        if not pending:
            return
        self._request_support_prepare()

    def _support_prepare_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_support_prepare_state")
        runtime = self.__dict__.get("_support_prepare_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_support_prepare_pending", False))
            start_scheduled = bool(self.__dict__.pop("_support_prepare_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_support_prepare_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _support_prepare_pending(self) -> bool:
        return bool(self._support_prepare_state_obj().pending)

    @_support_prepare_pending.setter
    def _support_prepare_pending(self, value: bool) -> None:
        self._support_prepare_state_obj().pending = bool(value)

    @property
    def _support_prepare_start_scheduled(self) -> bool:
        return bool(self._support_prepare_state_obj().start_scheduled)

    @_support_prepare_start_scheduled.setter
    def _support_prepare_start_scheduled(self, value: bool) -> None:
        self._support_prepare_state_obj().start_scheduled = bool(value)

    def _refresh_logs_list(self, *, run_cleanup: bool = True):
        """Обновляет список доступных лог-файлов"""
        started_at = time.perf_counter()
        self._refresh_spin_active = True
        self._spin_angle = 0
        spin_timer = getattr(self, "_spin_timer", None)
        if spin_timer is not None:
            spin_timer.start()
        self._start_logs_overview_worker(
            run_cleanup=run_cleanup,
            source_label="logs_ui.refresh_logs_list.total",
            started_at=started_at,
        )

    def _start_logs_overview_worker(self, *, run_cleanup: bool, source_label: str, started_at: float) -> None:
        if self._logs_overview_runtime.is_running() or self.__dict__.get("_logs_overview_restart_scheduled", False):
            self._logs_overview_pending_cleanup = self._logs_overview_pending_cleanup or bool(run_cleanup)
            self._log_ui_timing(source_label, started_at)
            return

        try:
            cleanup_requested = bool(run_cleanup)
            self._logs_overview_runtime.start_qobject_worker(
                parent=self,
                worker_factory=lambda _request_id: self._logs.create_logs_overview_worker(
                    run_cleanup=cleanup_requested,
                ),
                on_loaded=lambda req, logs_state, stats_state: self._on_logs_overview_loaded(
                    req,
                    logs_state,
                    stats_state,
                    cleanup_requested,
                ),
                on_failed=self._on_logs_overview_failed,
                on_finished=self._on_logs_overview_finished,
            )
        except Exception as exc:
            log(f"Ошибка запуска worker обзора логов: {exc}", "ERROR")
            QTimer.singleShot(500, self._stop_refresh_animation)
        finally:
            self._log_ui_timing(source_label, started_at)

    def _on_logs_overview_loaded(self, request_id: int, logs_state, stats_state, run_cleanup: bool) -> None:
        if not self._logs_overview_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        self._apply_logs_list_state(logs_state, run_cleanup=run_cleanup)
        self._apply_logs_stats_state(stats_state)

    def _on_logs_overview_failed(self, request_id: int, error: str) -> None:
        if not self._logs_overview_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        log(f"Ошибка обновления обзора логов: {error}", "ERROR")
        self._set_stats_text(f"Ошибка статистики: {error}")

    def _on_logs_overview_finished(self, request_id: int, thread) -> None:
        _ = thread
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        QTimer.singleShot(500, self._stop_refresh_animation)
        if (
            self._logs_overview_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress)
            and self._logs_overview_pending_cleanup
        ):
            self._logs_overview_pending_cleanup = False
            self._schedule_logs_overview_restart()

    def _schedule_logs_overview_restart(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_logs_overview_restart_scheduled", False):
            return
        self._logs_overview_restart_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_logs_overview_restart)

    def _run_scheduled_logs_overview_restart(self) -> None:
        self._logs_overview_restart_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._refresh_logs_list(run_cleanup=True)

    def _apply_logs_list_state(self, state, *, run_cleanup: bool) -> None:
        self._latest_logs_state = state
        table = getattr(self, "logs_table", None)
        if table is None:
            return
        if table.columnCount() < 4:
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Файл", "Статус", "Размер", "Путь"])
        table.blockSignals(True)
        table.setRowCount(0)
        try:
            if run_cleanup and state.cleanup_deleted > 0:
                log(f"🗑️ Удалено старых логов: {state.cleanup_deleted} из {state.cleanup_total}", "INFO")
            if run_cleanup and state.cleanup_errors:
                log(f"⚠️ Ошибки при удалении логов: {state.cleanup_errors[:3]}", "DEBUG")

            current_index = 0
            current_display = ""
            for entry in state.entries:
                row = table.rowCount()
                table.insertRow(row)
                if entry["is_current"]:
                    current_index = row
                    current_display = str(entry.get("display") or "")
                self._set_log_table_row(table, row, entry)
            if state.entries:
                table.setCurrentCell(current_index, 0)
            self._update_logs_table_accessibility(current_display, count=len(state.entries))
        finally:
            table.blockSignals(False)

    def _set_log_table_row(self, table, row: int, entry: dict) -> None:
        path = str(entry.get("path") or "")
        display = str(entry.get("display") or "")
        status = "Текущий" if bool(entry.get("is_current")) else "Старый"
        size = ""
        try:
            size = f"{float(entry.get('size_kb') or 0):.1f} KB"
        except (TypeError, ValueError):
            size = ""
        values = [display, status, size, path]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 0:
                item.setData(Qt.ItemDataRole.AccessibleTextRole, f"Файл лога: {display}, {status}")
            table.setItem(row, col, item)

    def _update_logs_table_accessibility(self, selected_display: str, *, count: int) -> None:
        table = getattr(self, "logs_table", None)
        if table is None:
            return
        table_name = "Таблица файлов логов"
        selected_display = str(selected_display or "").strip()
        if selected_display:
            table_name = f"{table_name}, выбрано: {selected_display}"
        set_state_text(table, table_name)
        set_control_accessibility(
            table,
            name=table_name,
            description=(
                f"Доступных файлов логов: {max(0, int(count))}. "
                "Выберите строку, чтобы открыть файл лога для просмотра."
            ),
        )

    def _apply_logs_stats_state(self, stats) -> None:
        plan = self._logs.build_stats_text_plan(stats, language=self._ui_language)
        self._set_stats_text(plan.text)

    def _set_info_text(self, text: str) -> None:
        normalized_text = str(text or "")
        self._info_text_cache = normalized_text
        info_label = self.__dict__.get("info_label")
        if info_label is None:
            return
        info_label.setText(normalized_text)
        set_state_text(
            info_label,
            _logs_accessible_state(
                tr_catalog(
                    "page.logs.accessibility.info.name",
                    language=self._ui_language,
                    default="Сообщение страницы логов",
                ),
                normalized_text,
            ),
        )

    def _set_stats_text(self, text: str) -> None:
        self.stats_label.setText(text)
        set_state_text(
            self.stats_label,
            _logs_accessible_state(
                tr_catalog(
                    "page.logs.accessibility.stats.name",
                    language=self._ui_language,
                    default="Статистика логов",
                ),
                text,
            ),
        )

    def _stop_logs_overview_worker(self, blocking: bool = False) -> None:
        try:
            self._logs_overview_runtime.stop(
                blocking=blocking,
                log_fn=log,
                warning_prefix="Logs overview worker",
            )
            self._logs_overview_runtime.cancel()
        except Exception as exc:
            log(f"Ошибка остановки worker обзора логов: {exc}", "DEBUG")

    def _stop_support_prepare_worker(self, blocking: bool = False) -> None:
        try:
            self._support_prepare_state_obj().reset()
            self._support_prepare_runtime.stop(
                blocking=blocking,
                log_fn=log,
                warning_prefix="Logs support worker",
            )
            self._support_prepare_runtime.cancel()
        except Exception as exc:
            log(f"Ошибка остановки worker подготовки обращения: {exc}", "DEBUG")
    
    def _stop_refresh_animation(self):
        """Останавливает анимацию кнопки обновления"""
        self._refresh_spin_active = False
        spin_timer = getattr(self, "_spin_timer", None)
        if spin_timer is not None:
            spin_timer.stop()
        refresh_btn = getattr(self, "refresh_btn", None)
        if refresh_btn is not None:
            refresh_btn.setIcon(self._refresh_icon_normal)

    def _on_spin_tick(self):
        """Вращает иконку обновления через QTransform (работает с ToolButton)."""
        self._spin_angle = (self._spin_angle + 12) % 360
        try:
            tokens = get_theme_tokens()
            src = get_cached_qta_pixmap('fa5s.sync-alt', color=tokens.accent_hex, size=22)
            dst = QPixmap(22, 22)
            dst.fill(Qt.GlobalColor.transparent)
            painter = QPainter(dst)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            t = QTransform().translate(11, 11).rotate(self._spin_angle).translate(-11, -11)
            painter.setTransform(t)
            painter.drawPixmap(0, 0, src)
            painter.end()
            self.refresh_btn.setIcon(QIcon(dst))
        except Exception:
            pass
            
    def _on_log_table_cell_clicked(self, row: int, column: int = 0) -> None:
        """Открывает лог по выбранной строке таблицы."""
        _ = column
        table = getattr(self, "logs_table", None)
        if table is None or row < 0:
            return
        item = table.item(row, 0)
        if item is None:
            return
        log_path = item.data(Qt.ItemDataRole.UserRole)
        display = item.text()
        if log_path and log_path != self.current_log_file:
            self.current_log_file = str(log_path)
            self._update_logs_table_accessibility(display, count=table.rowCount())
            self._start_log_source()

    def _start_log_source(self):
        """Подключает живой журнал или разово читает выбранный старый файл."""
        self._stop_log_source(blocking=False)
        active_log_file = self._logs.get_current_log_file()
        if self._logs.is_same_log_file(self.current_log_file, active_log_file):
            should_reset_view = not self._logs.is_same_log_file(
                self._displayed_log_file,
                active_log_file,
            )
            self._logs.start_live_log_source(
                active_log_file=active_log_file,
                after_sequence=self._live_log_cursor,
                should_reset_view=should_reset_view,
                create_bridge_fn=lambda **kwargs: self._logs.create_live_log_bridge(parent=self, **kwargs),
                on_new_text=self._on_live_log_text,
                set_bridge_fn=lambda value: setattr(self, "_live_log_bridge", value),
                set_cursor_fn=lambda value: setattr(self, "_live_log_cursor", value),
                set_displayed_file_fn=lambda value: setattr(self, "_displayed_log_file", value),
                set_info_text_fn=self._set_info_text,
                clear_log_view_fn=self._clear_log_view_silent,
                append_text_fn=self._append_text,
                log_fn=log,
            )
            return

        self._logs.start_log_file_reader(
            selected_log_file=self.current_log_file,
            previous_signature=self._log_file_signature,
            set_file_signature_fn=lambda value: setattr(self, "_log_file_signature", value),
            build_file_read_plan_fn=self._logs.build_file_read_plan,
            set_info_text_fn=self._set_info_text,
            clear_log_view_fn=self._clear_log_view_silent,
            reader_runtime=self._log_reader_runtime,
            parent=self,
            create_reader_fn=self._logs.create_log_file_reader_worker,
            on_new_lines=self._append_text,
            set_displayed_file_fn=lambda value: setattr(self, "_displayed_log_file", value),
            log_fn=log,
        )

    def _on_live_log_text(self, sequence: int, text: str) -> None:
        if self._cleanup_in_progress or self._live_log_bridge is None:
            return
        cursor = self._live_log_cursor
        if cursor is not None and int(sequence) <= int(cursor):
            return
        self._live_log_cursor = int(sequence)
        self._append_text(text)

    def _stop_log_source(self, blocking: bool = False):
        """Отключает источник без ожидания и без постоянного опроса файла."""
        bridge = self.__dict__.get("_live_log_bridge")
        self._live_log_bridge = None
        self._logs.stop_log_source(
            live_bridge=bridge,
            reader_runtime=self._log_reader_runtime,
            blocking=blocking,
            log_fn=log,
            warning_prefix="Log file reader",
        )

    def _append_text(self, text: str):
        """Добавляет текст в лог"""
        if self._cleanup_in_progress:
            return
        if not text:
            return
        self._append_log_text_cache(text)
        self._pending_log_text_append = (
            str(self.__dict__.get("_pending_log_text_append", "") or "") + text
        )
        if self.__dict__.get("_log_text_append_scheduled", False):
            return
        self._log_text_append_scheduled = True
        QTimer.singleShot(0, self._flush_pending_log_text_append)

    def _flush_pending_log_text_append(self):
        """Вставляет накопленные строки лога в поле одним обновлением GUI."""
        text = str(self.__dict__.get("_pending_log_text_append", "") or "")
        self._pending_log_text_append = ""
        self._log_text_append_scheduled = False
        if self._cleanup_in_progress:
            return
        if not text:
            return
        self._append_text_now(text)

    def _append_text_now(self, text: str):
        """Добавляет уже собранный текст в виджет лога."""
        # Быстро вставляем текст одним куском (append по строкам сильно тормозит на больших логах).
        try:
            scrollbar = self.log_text.verticalScrollBar()
            was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 2)
        except Exception:
            was_at_bottom = True

        try:
            self.log_text.setUpdatesEnabled(False)
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(text)
            self.log_text.setTextCursor(cursor)
        finally:
            try:
                self.log_text.setUpdatesEnabled(True)
            except Exception:
                pass

        if not self.__dict__.get("_first_log_content_timing_done", False):
            started_at = self.__dict__.get("_first_log_content_started_at")
            if started_at is not None:
                self._first_log_content_timing_done = True
                self._log_ui_timing("logs_ui.first_log_content", started_at)

        # Проверяем на ошибки только по новым строкам
        try:
            for line in text.splitlines():
                clean_line = (line or "").rstrip()
                if not clean_line:
                    continue
                if self._error_pattern.search(clean_line) and not self._exclude_pattern.search(clean_line):
                    self._add_error(clean_line)
        except Exception:
            pass

        if was_at_bottom:
            try:
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except Exception:
                pass
        
    def _copy_log(self):
        """Копирует содержимое лога в буфер"""
        text = self._log_text_cache
        if text:
            QApplication.clipboard().setText(text)
            self._set_info_text(
                tr_catalog(
                    "page.logs.info.copied",
                    language=self._ui_language,
                    default="✅ Скопировано в буфер обмена",
                )
            )
        else:
            self._set_info_text(
                tr_catalog(
                    "page.logs.info.empty",
                    language=self._ui_language,
                    default="⚠️ Лог пуст",
                )
            )
            
    def _clear_view(self):
        """Очищает вид (не файл)"""
        self._clear_log_view_silent()
        self._set_info_text(
            tr_catalog(
                "page.logs.info.view_cleared",
                language=self._ui_language,
                default="🧹 Вид очищен",
            )
        )

    def _clear_log_view_silent(self) -> None:
        self.log_text.clear()
        self._log_text_cache = ""

    @property
    def _log_text_cache(self) -> str:
        lines = self.__dict__.get("_log_text_cache_lines")
        if not lines:
            return ""
        return "\n".join(lines)

    @_log_text_cache.setter
    def _log_text_cache(self, value: str) -> None:
        self.__dict__["_log_text_cache_lines"] = deque(
            str(value or "").splitlines(),
            maxlen=MAIN_LOG_VIEW_MAX_LINES,
        )

    def _append_log_text_cache(self, text: str) -> None:
        lines = self.__dict__.get("_log_text_cache_lines")
        if not isinstance(lines, deque):
            lines = deque(maxlen=MAIN_LOG_VIEW_MAX_LINES)
            self.__dict__["_log_text_cache_lines"] = lines
        lines.extend(str(text or "").splitlines())
        
    def _open_folder(self):
        """Открывает папку с логами"""
        self._request_open_logs_folder()

    def create_open_folder_worker(self, request_id: int):
        return self._logs.create_open_folder_worker(request_id, parent=self)

    def _request_open_logs_folder(self) -> None:
        state = self._open_folder_state_obj()
        if state.is_busy():
            state.pending = True
            return
        state.pending = False
        self._open_folder_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_open_folder_worker(request_id),
            on_failed=self._on_open_logs_folder_failed,
            on_finished=self._on_open_logs_folder_worker_finished,
        )

    def _on_open_logs_folder_failed(self, request_id: int, error: str) -> None:
        if not self._open_folder_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self._open_folder_state_obj().has_pending():
            return
        log(f"Ошибка открытия папки: {error}", "ERROR")

    def _on_open_logs_folder_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_open_folder_runtime"), _worker):
            return
        self._open_folder_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_open_logs_folder_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
            clear_pending_before_schedule=True,
        )

    def _schedule_open_logs_folder_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._open_folder_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_open_logs_folder_start,
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )

    def _run_scheduled_open_logs_folder_start(self) -> None:
        self._open_folder_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_open_logs_folder()

    def _open_folder_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_open_folder_state")
        runtime = self.__dict__.get("_open_folder_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_open_folder_pending", False))
            start_scheduled = bool(self.__dict__.pop("_open_folder_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_open_folder_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _open_folder_pending(self) -> bool:
        return bool(self._open_folder_state_obj().pending)

    @_open_folder_pending.setter
    def _open_folder_pending(self, value: bool) -> None:
        self._open_folder_state_obj().pending = bool(value)

    @property
    def _open_folder_start_scheduled(self) -> bool:
        return bool(self._open_folder_state_obj().start_scheduled)

    @_open_folder_start_scheduled.setter
    def _open_folder_start_scheduled(self, value: bool) -> None:
        self._open_folder_state_obj().start_scheduled = bool(value)
            
    def _update_stats(self):
        """Обновляет статистику"""
        started_at = time.perf_counter()
        self._start_logs_overview_worker(
            run_cleanup=False,
            source_label="logs_ui.update_stats.total",
            started_at=started_at,
        )

    @staticmethod
    def _log_ui_timing(label: str, started_at: float) -> None:
        log_ui_timing_since("ui", "logs", label, started_at)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _update_errors_text_height(self):
        """Подстраивает высоту панели ошибок под содержимое."""
        if not hasattr(self, "errors_text") or self.errors_text is None:
            return
        target_height = compute_errors_text_height(
            text_edit=self.errors_text,
            min_height=self._errors_text_min_height,
            max_height=self._errors_text_max_height,
        )

        if self.errors_text.height() != target_height:
            self.errors_text.setFixedHeight(target_height)
            
    def _add_error(self, text: str):
        """Добавляет ошибку в панель ошибок"""
        if not self._ensure_logs_secondary_panels():
            return
        self._errors_count = append_error(
            errors_text=self.errors_text,
            errors_count_label=self.errors_count_label,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            current_count=self._errors_count,
            text=text,
        )
        self._update_errors_text_height()
        
        # Автопрокрутка
        scrollbar = self.errors_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _clear_errors(self):
        """Очищает панель ошибок"""
        if not self._ensure_logs_secondary_panels():
            return
        self._errors_count = clear_errors(
            errors_text=self.errors_text,
            errors_count_label=self.errors_count_label,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
        )
        self._update_errors_text_height()
        self._set_info_text(
            tr_catalog(
                "page.logs.info.errors_cleared",
                language=self._ui_language,
                default="🧹 Ошибки очищены",
            )
        )
            
    def cleanup(self):
        """Очистка фоновых задач при закрытии страницы логов."""
        self._cleanup_in_progress = True
        self._logs_overview_restart_scheduled = False
        self._pending_log_text_append = ""
        self._log_text_append_scheduled = False
        spin_timer = getattr(self, "_spin_timer", None)
        if spin_timer is not None:
            spin_timer.stop()
        self._stop_logs_overview_worker(blocking=False)
        self._stop_support_prepare_worker(blocking=False)
        self._open_folder_state_obj().reset()
        self._open_folder_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Logs open folder worker",
        )
        self._open_folder_runtime.cancel()
        self._stop_log_source(blocking=False)
