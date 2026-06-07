# log/ui/page.py
"""Страница просмотра логов в реальном времени"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QApplication,
    QStackedWidget
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    StrongBodyLabel,
    PushButton,
    PushButton as FluentPushButton,
    ComboBox,
    SegmentedWidget,
    ToolButton,
    InfoBar,
)
from PyQt6.QtGui import QFont, QPixmap, QPainter, QTransform, QIcon
import qtawesome as qta
import re
import time

from ui.accessibility import set_control_accessibility, set_state_text
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.fluent_widgets import QuickActionsBar, SettingsCard, set_tooltip
from ui.log_limits import MAIN_LOG_VIEW_MAX_LINES
from log.ui.logs_build import build_logs_primary_tab_ui, build_logs_secondary_panels_ui
from log.ui.runtime_helpers import (
    append_error,
    clear_errors,
    compute_errors_text_height,
    render_send_status_label,
)
from log.ui.send_build import build_logs_send_tab
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

# Паттерны для ИСКЛЮЧЕНИЯ (не ошибки, хотя содержат ключевые слова)
EXCLUDE_PATTERNS = [
    r'Faulthandler enabled',   # Информация о включении faulthandler
    r'Crash handler установлен', # Информация об установке обработчика
    r'connection error:.*HTTPSConnectionPool',  # Сетевые ошибки VPS (не критично)
    r'connection error:.*HTTPConnectionPool',   # Сетевые ошибки VPS (не критично)
    r'\[POOL\].*ошибка',       # Ошибки пула серверов (fallback работает)
    r'Theme error:.*NoneType', # Ошибки темы при инициализации (временные)
]


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
        self._tail_file_signature = None
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
        self._controls_actions_title = None
        self._controls_actions_bar = None
        self._send_actions_title = None
        self._send_actions_bar = None

        self._logs_overview_runtime = OneShotWorkerRuntime()
        self._logs_overview_pending_cleanup = False
        self._logs_overview_restart_scheduled = False
        self._tail_runtime = OneShotWorkerRuntime()
        self._log_text_cache = ""
        self._support_prepare_runtime = OneShotWorkerRuntime()
        self._support_prepare_pending = False
        self._support_prepare_start_scheduled = False
        self._open_folder_runtime = OneShotWorkerRuntime()
        self._open_folder_pending = False
        self._open_folder_start_scheduled = False

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

    def _run_runtime_init_once(self) -> None:
        if self._cleanup_in_progress or not self.isVisible():
            return
        started_at = time.perf_counter()
        warmed = self._logs.consume_warmed_page_data()
        if warmed is not None:
            self._apply_logs_list_state(warmed.logs_state, run_cleanup=False)
            self._apply_logs_stats_state(warmed.stats_state)
        self._runtime_initialized, self._runtime_started = self._logs.run_runtime_init(
            runtime_initialized=self._runtime_initialized,
            runtime_started=self._runtime_started,
            schedule_fn=QTimer.singleShot,
            refresh_logs_fn=self._refresh_logs_list,
            update_stats_fn=self._update_stats,
            start_tail_worker_fn=self._start_tail_worker,
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
        self._stop_tail_worker(blocking=False)
        self._runtime_started = False

    def on_page_activated(self) -> None:
        self._schedule_runtime_init()
        self._schedule_logs_secondary_panels()

    def on_page_hidden(self) -> None:
        self._runtime_init_scheduled = False
        self._logs_secondary_build_scheduled = False
        self._stop_runtime()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        self._tokens = tokens

        # Controls — log_combo is now a Fluent ComboBox; no manual stylesheet needed
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
        self.tabs_pivot.setCurrentItem("logs")
        self.tabs_pivot.setItemFontSize(13)
        set_control_accessibility(
            self.tabs_pivot,
            name=tr_catalog("page.logs.accessibility.tabs.name", default="Вкладки страницы логов"),
            description=tr_catalog(
                "page.logs.accessibility.tabs.description",
                default="Переключение между просмотром логов и подготовкой обращения в поддержку.",
            ),
        )
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

        self.stacked_widget.addWidget(self._logs_page)
        self.stacked_widget.addWidget(self._send_page)

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

        self.stacked_widget.setCurrentIndex(index)

        # Sync Pivot indicator
        key = "send" if index == 1 else "logs"
        try:
            self.tabs_pivot.setCurrentItem(key)
        except Exception:
            pass

        if index == 1:
            # Обновляем видимость индикатора оркестратора
            self._update_orchestra_indicator()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        logs_text = " " + tr_catalog("page.logs.tab.logs", language=language, default="ЛОГИ")
        send_text = " " + tr_catalog("page.logs.tab.send", language=language, default="ОТПРАВКА")

        try:
            self.tabs_pivot.setItemText("logs", logs_text)
            self.tabs_pivot.setItemText("send", send_text)
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
        try:
            self._set_card_title(
                self.controls_card,
                tr_catalog("page.logs.card.controls", language=self._ui_language, default="Управление логами"),
            )
            self._set_card_title(
                self.log_card,
                tr_catalog("page.logs.card.content", language=self._ui_language, default="Содержимое"),
            )
        except Exception:
            pass

        if self._controls_actions_title is not None:
            self._controls_actions_title.setText(
                tr_catalog("page.logs.actions.title", language=self._ui_language, default="Действия")
            )

        try:
            set_tooltip(
                self.refresh_btn,
                tr_catalog("page.logs.tooltip.refresh", language=self._ui_language, default="Обновить список файлов"),
            )
        except Exception:
            pass

        try:
            self.copy_btn.setText(tr_catalog("page.logs.button.copy", language=self._ui_language, default="Копировать"))
            self.clear_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.folder_btn.setText(tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка"))
            set_tooltip(
                self.copy_btn,
                tr_catalog(
                    "page.logs.action.copy.description",
                    language=self._ui_language,
                    default="Скопировать содержимое текущего лога в буфер обмена.",
                )
            )
            set_tooltip(
                self.clear_btn,
                tr_catalog(
                    "page.logs.action.clear.description",
                    language=self._ui_language,
                    default="Очистить только текущее окно просмотра, не удаляя файл лога.",
                )
            )
            set_tooltip(
                self.folder_btn,
                tr_catalog(
                    "page.logs.action.folder.description",
                    language=self._ui_language,
                    default="Открыть папку logs с файлами приложения.",
                )
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
            self.send_log_btn.setText(
                tr_catalog("page.logs.send.button.send", language=self._ui_language, default="Подготовить обращение")
            )
            self.open_logs_folder_btn.setText(
                tr_catalog("page.logs.button.folder", language=self._ui_language, default="Папка")
            )
            set_tooltip(
                self.send_log_btn,
                tr_catalog(
                    "page.logs.send.action.send.description",
                    language=self._ui_language,
                    default="Собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
                )
            )
            set_tooltip(
                self.open_logs_folder_btn,
                tr_catalog(
                    "page.logs.send.action.folder.description",
                    language=self._ui_language,
                    default="Открыть папку logs, где лежат логи и подготовленные support bundles.",
                )
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
            combo_box_cls=ComboBox,
            tool_button_cls=ToolButton,
            push_button_cls=PushButton,
            text_edit_cls=ScrollBlockingTextEdit,
            quick_actions_bar_cls=QuickActionsBar,
            qfont_cls=QFont,
            get_theme_tokens_fn=get_theme_tokens,
            on_log_selected=self._on_log_selected,
            on_refresh=self._refresh_logs_list,
            on_spin_tick=self._on_spin_tick,
            on_copy=self._copy_log,
            on_clear_view=self._clear_view,
            on_open_folder=self._open_folder,
            refresh_timer_parent=self,
        )
        self.controls_card = logs_widgets.controls_card
        self.log_combo = logs_widgets.log_combo
        self.refresh_btn = logs_widgets.refresh_btn
        self.info_label = logs_widgets.info_label
        self._controls_actions_title = logs_widgets.controls_actions_title
        self._controls_actions_bar = logs_widgets.controls_actions_bar
        self.copy_btn = logs_widgets.copy_btn
        self.clear_btn = logs_widgets.clear_btn
        self.folder_btn = logs_widgets.folder_btn
        self.log_card = logs_widgets.log_card
        self.log_text = logs_widgets.log_text
        self.stats_label = logs_widgets.stats_label

        # Счётчик ошибок
        self._errors_count = 0
        try:
            self.stats_label.setText(
                tr_catalog("page.logs.stats.loading", language=self._ui_language, default="📊 Загрузка...")
            )
            set_state_text(self.stats_label, self.stats_label.text())
        except Exception:
            pass

    def _schedule_logs_secondary_panels(self) -> None:
        if self._logs_secondary_initialized or self._logs_secondary_build_scheduled:
            return
        self._logs_secondary_build_scheduled = True
        QTimer.singleShot(0, self._ensure_logs_secondary_panels)

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
        if (
            self._support_prepare_runtime.is_running()
            or self.__dict__.get("_support_prepare_start_scheduled", False)
        ):
            self._support_prepare_pending = True
            return
        self._support_prepare_pending = False
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
        if self.__dict__.get("_support_prepare_pending", False):
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
        if self.__dict__.get("_support_prepare_pending", False):
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
        if self.__dict__.get("_support_prepare_pending", False):
            self._schedule_support_prepare_start()

    def _schedule_support_prepare_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_support_prepare_start_scheduled", False):
            return
        self._support_prepare_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_support_prepare_start)

    def _run_scheduled_support_prepare_start(self) -> None:
        self._support_prepare_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_support_prepare_pending", False):
            return
        self._support_prepare_pending = False
        self._request_support_prepare()

    def _refresh_logs_list(self, *, run_cleanup: bool = True):
        """Обновляет список доступных лог-файлов"""
        started_at = time.perf_counter()
        self._refresh_spin_active = True
        self._spin_angle = 0
        self._spin_timer.start()
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
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        try:
            if run_cleanup and state.cleanup_deleted > 0:
                log(f"🗑️ Удалено старых логов: {state.cleanup_deleted} из {state.cleanup_total}", "INFO")
            if run_cleanup and state.cleanup_errors:
                log(f"⚠️ Ошибки при удалении логов: {state.cleanup_errors[:3]}", "DEBUG")

            current_index = 0
            for entry in state.entries:
                if entry["is_current"]:
                    current_index = entry["index"]
                self.log_combo.addItem(entry["display"], userData=entry["path"])
            set_control_accessibility(
                self.log_combo,
                name=tr_catalog(
                    "page.logs.accessibility.log_combo.name",
                    language=self._ui_language,
                    default="Выбор файла лога",
                ),
                description=tr_catalog(
                    "page.logs.accessibility.log_combo.count_description",
                    language=self._ui_language,
                    default="Доступных файлов логов: {count}.",
                ).format(count=len(state.entries)),
            )
            self.log_combo.setCurrentIndex(current_index)
        finally:
            self.log_combo.blockSignals(False)

    def _apply_logs_stats_state(self, stats) -> None:
        plan = self._logs.build_stats_text_plan(stats, language=self._ui_language)
        self._set_stats_text(plan.text)

    def _set_info_text(self, text: str) -> None:
        self.info_label.setText(text)
        set_state_text(self.info_label, text)

    def _set_stats_text(self, text: str) -> None:
        self.stats_label.setText(text)
        set_state_text(self.stats_label, text)

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
            self._support_prepare_pending = False
            self._support_prepare_start_scheduled = False
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
        self._spin_timer.stop()
        self.refresh_btn.setIcon(self._refresh_icon_normal)

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
            
    def _on_log_selected(self, index):
        """Обработчик выбора лог-файла"""
        if index < 0:
            return
            
        log_path = self.log_combo.itemData(index)
        if log_path and log_path != self.current_log_file:
            self.current_log_file = log_path
            self._start_tail_worker()
            
    def _start_tail_worker(self):
        """Запускает worker для чтения лога"""
        self._logs.start_tail_worker(
            current_log_file=self.current_log_file,
            previous_signature=self._tail_file_signature,
            set_tail_signature_fn=lambda value: setattr(self, "_tail_file_signature", value),
            stop_worker_fn=self._stop_tail_worker,
            build_tail_start_plan_fn=self._logs.build_tail_start_plan,
            set_info_text_fn=self._set_info_text,
            clear_log_view_fn=self._clear_log_view_silent,
            tail_runtime=self._tail_runtime,
            parent=self,
            create_worker_fn=self._logs.create_log_tail_worker,
            on_new_lines=self._append_text,
            log_fn=log,
        )
            
    def _stop_tail_worker(self, blocking: bool = False):
        """Останавливает worker (неблокирующий по умолчанию)"""
        self._logs.stop_tail_worker(
            tail_runtime=self._tail_runtime,
            blocking=blocking,
            log_fn=log,
            warning_prefix="Log tail worker",
        )

    def _append_text(self, text: str):
        """Добавляет текст в лог"""
        if self._cleanup_in_progress:
            return
        if not text:
            return
        self._append_log_text_cache(text)

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
        text = str(self.__dict__.get("_log_text_cache", "") or "")
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

    def _append_log_text_cache(self, text: str) -> None:
        current = str(self.__dict__.get("_log_text_cache", "") or "")
        combined = f"{current}\n{text}" if current else str(text or "")
        lines = combined.splitlines()
        if len(lines) > MAIN_LOG_VIEW_MAX_LINES:
            lines = lines[-MAIN_LOG_VIEW_MAX_LINES:]
        self._log_text_cache = "\n".join(lines)
        
    def _open_folder(self):
        """Открывает папку с логами"""
        self._request_open_logs_folder()

    def create_open_folder_worker(self, request_id: int):
        return self._logs.create_open_folder_worker(request_id, parent=self)

    def _request_open_logs_folder(self) -> None:
        if self._open_folder_runtime.is_running() or self.__dict__.get("_open_folder_start_scheduled", False):
            self._open_folder_pending = True
            return
        self._open_folder_pending = False
        self._open_folder_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_open_folder_worker(request_id),
            on_failed=self._on_open_logs_folder_failed,
            on_finished=self._on_open_logs_folder_worker_finished,
        )

    def _on_open_logs_folder_failed(self, request_id: int, error: str) -> None:
        if not self._open_folder_runtime.is_current(request_id, cleanup_in_progress=self._cleanup_in_progress):
            return
        if self.__dict__.get("_open_folder_pending", False):
            return
        log(f"Ошибка открытия папки: {error}", "ERROR")

    def _on_open_logs_folder_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_open_folder_runtime"), _worker):
            return
        if self._open_folder_pending and not self._cleanup_in_progress:
            self._open_folder_pending = False
            self._schedule_open_logs_folder_start()

    def _schedule_open_logs_folder_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_open_folder_start_scheduled", False):
            return
        self._open_folder_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_open_logs_folder_start)

    def _run_scheduled_open_logs_folder_start(self) -> None:
        self._open_folder_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_open_logs_folder()
            
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
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass

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
        self._spin_timer.stop()
        self._stop_logs_overview_worker(blocking=False)
        self._stop_support_prepare_worker(blocking=False)
        self._open_folder_pending = False
        self._open_folder_start_scheduled = False
        self._open_folder_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="Logs open folder worker",
        )
        self._open_folder_runtime.cancel()
        self._stop_tail_worker(blocking=False)
