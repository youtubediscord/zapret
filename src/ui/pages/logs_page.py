# ui/pages/logs_page.py
"""Страница просмотра логов в реальном времени"""

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QApplication,
    QTextEdit, QStackedWidget
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
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

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.compat_widgets import QuickActionsBar, SettingsCard, set_tooltip
from ui.pages.logs_page_logs_build import build_logs_tab_ui
from ui.pages.logs_page_runtime_helpers import (
    append_error,
    clear_errors,
    compute_errors_text_height,
    format_winws_output_line,
    render_send_status_label,
    resolve_winws_status_style,
    set_winws_status,
)
from ui.pages.logs_page_send_build import build_logs_send_tab
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from log import log
from log.logs_page_controller import LogsPageController

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
    
    def __init__(self, parent=None):
        super().__init__(
            "Логи",
            "Просмотр логов приложения в реальном времени",
            parent,
            title_key="page.logs.title",
            subtitle_key="page.logs.subtitle",
        )
        
        # Отключаем горизонтальную прокрутку страницы
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._thread = None
        self._worker = None
        self.current_log_file = LogsPageController.get_current_log_file()
        self._error_pattern = re.compile('|'.join(ERROR_PATTERNS))
        self._exclude_pattern = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

        self._tokens = get_theme_tokens()

        # Theme-dependent colors used in runtime status/output updates.
        self._winws_stdout_color = "#00ff88"
        self._winws_stderr_color = "#ff6b6b"
        self._winws_status_neutral = self._tokens.fg_muted
        self._winws_status_running = self._tokens.accent_hex
        self._winws_status_error = self._tokens.fg

        # References for theme refresh (icons/labels created as locals).
        self._warning_icon_label = None
        self._terminal_icon_label = None
        self._info_icon_label = None
        self._orchestra_icon_label = None
        self._orchestra_text_label = None
        self._send_status_text = ""
        self._send_status_tone = "neutral"
        self._controls_actions_title = None
        self._controls_actions_bar = None
        self._send_actions_title = None
        self._send_actions_bar = None

        # Winws output worker
        self._winws_thread = None
        self._winws_worker = None
        self._winws_lines_count = 0

        # Error panel height tuning (avoid large empty block when no errors).
        self._errors_text_min_height = 52
        self._errors_text_max_height = 140

        # Таймер для обновления статуса winws
        self._winws_status_timer = QTimer(self)
        self._winws_status_timer.timeout.connect(self._update_winws_status)

        self._runtime_initialized = False
        self._send_tab_initialized = False
        self._runtime_started = False

        # qtawesome animations (e.g. qta.Spin) are not QAbstractAnimation; track state ourselves.
        self._refresh_spin_active = False
        self._build_ui()
        try:
            self._apply_page_theme(force=True)
        except Exception:
            pass
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True

        # Делаем первый refresh после построения UI, а не из activation,
        # чтобы page activation не владел initial runtime-догрузкой.
        QTimer.singleShot(0, lambda: self._refresh_logs_list(run_cleanup=False))
        QTimer.singleShot(0, self._update_stats)

        if not self._runtime_started:
            self._runtime_started = True
            self._start_tail_worker()
            self._start_winws_output_worker()
            # Таймер статуса должен жить отдельно от простого переключения вкладок.
            self._winws_status_timer.start(3000)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        self._tokens = tokens

        # Controls — log_combo is now a Fluent ComboBox; no manual stylesheet needed
        # Tabs — Pivot handles its own theme

        if hasattr(self, "refresh_btn"):
            self._refresh_icon_normal = qta.icon('fa5s.sync-alt', color=tokens.fg)
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
                self._warning_icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color=err_fg).pixmap(16, 16))
            except Exception:
                pass

        # errors_count_label is now a CaptionLabel (Fluent) — no manual style needed

        if hasattr(self, "errors_text"):
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

        # winws panel
        if self._terminal_icon_label is not None:
            try:
                self._terminal_icon_label.setPixmap(qta.icon('fa5s.terminal', color=tokens.accent_hex).pixmap(16, 16))
            except Exception:
                pass

        self._winws_stdout_color = "rgba(21, 128, 61, 0.92)" if tokens.is_light else "#00ff88"
        self._winws_stderr_color = err_fg
        self._winws_status_neutral = tokens.fg_muted
        self._winws_status_running = tokens.accent_hex
        self._winws_status_error = err_fg

        if hasattr(self, "winws_text"):
            self.winws_text.setStyleSheet(
                "QTextEdit {"
                f" background-color: {editor_bg};"
                f" color: {editor_fg};"
                f" border: 1px solid {tokens.surface_border};"
                " border-radius: 6px;"
                " padding: 8px;"
                " font-family: 'Consolas', 'Courier New', monospace;"
                " font-size: 11px;"
                " }"
            )
            self._refresh_winws_status_style_only()

        # Send tab (exists only after lazy init)
        if self._info_icon_label is not None:
            try:
                self._info_icon_label.setPixmap(qta.icon('fa5s.info-circle', color=tokens.accent_hex).pixmap(14, 14))
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
            self._orchestra_icon_label.setPixmap(qta.icon('fa5s.brain', color=accent).pixmap(16, 16))
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

    def _update_tab_styles(self) -> None:
        """No-op — Pivot manages its own indicator."""

    def _refresh_winws_status_style_only(self) -> None:
        try:
            current_text = self.winws_status_label.text() or ""
        except Exception:
            current_text = ""
        kind, text = resolve_winws_status_style(
            current_text=current_text,
            neutral_color=self._winws_status_neutral,
            running_color=self._winws_status_running,
            error_color=self._winws_status_error,
        )
        self._set_winws_status(kind, text)

    def _set_winws_status(self, kind: str, text: str) -> None:
        set_winws_status(
            self.winws_status_label,
            kind=kind,
            text=text,
            neutral_color=self._winws_status_neutral,
            running_color=self._winws_status_running,
            error_color=self._winws_status_error,
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
            self.copy_btn.setToolTip(
                tr_catalog(
                    "page.logs.action.copy.description",
                    language=self._ui_language,
                    default="Скопировать содержимое текущего лога в буфер обмена.",
                )
            )
            self.clear_btn.setToolTip(
                tr_catalog(
                    "page.logs.action.clear.description",
                    language=self._ui_language,
                    default="Очистить только текущее окно просмотра, не удаляя файл лога.",
                )
            )
            self.folder_btn.setToolTip(
                tr_catalog(
                    "page.logs.action.folder.description",
                    language=self._ui_language,
                    default="Открыть папку logs с файлами приложения.",
                )
            )
            self.errors_title_label.setText(tr_catalog("page.logs.errors.title", language=self._ui_language, default="Ошибки и предупреждения"))
            self.clear_errors_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.clear_winws_btn.setText(tr_catalog("page.logs.button.clear", language=self._ui_language, default="Очистить"))
            self.errors_count_label.setText(
                tr_catalog("page.logs.errors.count", language=self._ui_language, default="Ошибок: {count}").format(
                    count=max(0, int(self._errors_count))
                )
            )
            self._refresh_winws_title()
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
            self.send_log_btn.setToolTip(
                tr_catalog(
                    "page.logs.send.action.send.description",
                    language=self._ui_language,
                    default="Собрать ZIP из свежих логов, скопировать шаблон обращения и открыть GitHub Discussions.",
                )
            )
            self.open_logs_folder_btn.setToolTip(
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
        logs_widgets = build_logs_tab_ui(
            parent_layout=parent_layout,
            content_parent=self.content,
            ui_language=self._ui_language,
            tr_catalog_fn=tr_catalog,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            combo_box_cls=ComboBox,
            tool_button_cls=ToolButton,
            push_button_cls=PushButton,
            fluent_push_button_cls=FluentPushButton,
            text_edit_cls=ScrollBlockingTextEdit,
            quick_actions_bar_cls=QuickActionsBar,
            qfont_cls=QFont,
            qtextedit_cls=QTextEdit,
            qta_module=qta,
            get_theme_tokens_fn=get_theme_tokens,
            errors_text_min_height=self._errors_text_min_height,
            errors_text_max_height=self._errors_text_max_height,
            on_log_selected=self._on_log_selected,
            on_refresh=self._refresh_logs_list,
            on_spin_tick=self._on_spin_tick,
            on_copy=self._copy_log,
            on_clear_view=self._clear_view,
            on_open_folder=self._open_folder,
            on_clear_errors=self._clear_errors,
            on_update_errors_height=self._update_errors_text_height,
            on_clear_winws_output=self._clear_winws_output,
            refresh_timer_parent=self,
        )
        self.controls_card = logs_widgets.controls_card
        self.log_combo = logs_widgets.log_combo
        self.refresh_btn = logs_widgets.refresh_btn
        self._controls_actions_title = logs_widgets.controls_actions_title
        self._controls_actions_bar = logs_widgets.controls_actions_bar
        self.copy_btn = logs_widgets.copy_btn
        self.clear_btn = logs_widgets.clear_btn
        self.folder_btn = logs_widgets.folder_btn
        self.log_card = logs_widgets.log_card
        self.log_text = logs_widgets.log_text
        self.stats_label = logs_widgets.stats_label
        self.errors_card = logs_widgets.errors_card
        self._warning_icon_label = logs_widgets.warning_icon_label
        self.errors_title_label = logs_widgets.errors_title_label
        self.errors_count_label = logs_widgets.errors_count_label
        self.clear_errors_btn = logs_widgets.clear_errors_btn
        self.errors_text = logs_widgets.errors_text
        self.winws_card = logs_widgets.winws_card
        self._terminal_icon_label = logs_widgets.terminal_icon_label
        self.winws_title_label = logs_widgets.winws_title_label
        self.winws_status_label = logs_widgets.winws_status_label
        self.clear_winws_btn = logs_widgets.clear_winws_btn
        self.winws_text = logs_widgets.winws_text

        self.errors_text.document().contentsChanged.connect(self._update_errors_text_height)
        self._update_errors_text_height()

        # Счётчик ошибок
        self._errors_count = 0
        try:
            self.stats_label.setText(
                tr_catalog("page.logs.stats.loading", language=self._ui_language, default="📊 Загрузка...")
            )
        except Exception:
            pass

        self._refresh_winws_title()

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
        return self._get_launch_method() == "orchestra"

    def _get_launch_method(self) -> str:
        """Возвращает текущий метод запуска"""
        try:
            from strategy_menu import get_strategy_launch_method
            return (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            return ""

    def _get_orchestra_runner(self):
        """Возвращает orchestra_runner из главного окна"""
        try:
            app = self.window()
            runner = getattr(app, 'orchestra_runner', None) if app else None
            if runner:
                return runner
        except Exception:
            pass

        try:
            qapp = QApplication.instance()
            if qapp:
                active_window_getter = getattr(qapp, 'activeWindow', None)
                main_window = active_window_getter() if callable(active_window_getter) else None
                runner = getattr(main_window, 'orchestra_runner', None) if main_window else None
                if runner:
                    return runner

                for widget in qapp.topLevelWidgets():
                    runner = getattr(widget, 'orchestra_runner', None)
                    if runner:
                        return runner
        except Exception:
            pass

        return None

    def _refresh_winws_title(self):
        """Обновляет заголовок панели вывода по текущему методу запуска"""
        if not hasattr(self, "winws_title_label"):
            return

        try:
            exe_name = LogsPageController.resolve_winws_exe_name(self._get_launch_method())
        except Exception:
            exe_name = "winws.exe"

        self.winws_title_label.setText(
            tr_catalog(
                "page.logs.winws.title_template",
                language=self._ui_language,
                default="Вывод {exe_name}",
            ).format(exe_name=exe_name)
        )

    def _get_running_runner_source(self):
        """
        Возвращает источник активного процесса.

        Returns:
            Tuple[str|None, runner|None] где source:
            - "orchestra" для OrchestraRunner
            - "direct" для StrategyRunner
            - None если процесс не запущен
        """
        return LogsPageController.get_running_runner_source(
            self._get_launch_method(),
            self._get_orchestra_runner(),
        )

    def _get_runner_pid(self, runner):
        """Возвращает PID для любого типа runner'а"""
        return LogsPageController.get_runner_pid(runner)

    def _get_orchestra_log_path(self) -> str:
        """
        Возвращает путь к логу оркестратора.

        Приоритет:
        1. Текущий активный лог (если оркестратор запущен)
        2. Последний сохранённый лог из истории
        """
        return LogsPageController.get_orchestra_log_path(self._get_orchestra_runner())

    def _update_orchestra_indicator(self):
        """Обновляет видимость индикатора режима оркестратора"""
        is_orchestra = self._is_orchestra_mode()
        self.orchestra_mode_container.setVisible(is_orchestra)

    def _prepare_support_from_logs(self):
        try:
            result = LogsPageController.prepare_support_bundle(
                current_log_file=self.current_log_file,
                orchestra_runner=self._get_orchestra_runner(),
            )

            if result.zip_path:
                log(f"Подготовлен архив поддержки: {result.zip_path}", "INFO")
            feedback = LogsPageController.build_support_feedback(result)
            self._send_status_text = feedback.status_text
            self._send_status_tone = feedback.status_tone
            self._render_send_status_label()

            if InfoBar:
                InfoBar.success(
                    title=feedback.infobar_title,
                    content=feedback.infobar_content,
                    parent=self.window(),
                    duration=5000,
                )
        except Exception as e:
            log(f"Ошибка подготовки обращения из логов: {e}", "ERROR")
            feedback = LogsPageController.build_support_error_feedback(str(e))
            self._send_status_text = feedback.status_text
            self._send_status_tone = feedback.status_tone
            self._render_send_status_label()
            if InfoBar:
                InfoBar.warning(
                    title=feedback.infobar_title,
                    content=feedback.infobar_content,
                    parent=self.window(),
                )
        
    def _refresh_logs_list(self, *, run_cleanup: bool = True):
        """Обновляет список доступных лог-файлов"""
        # Запускаем анимацию вращения
        self._refresh_spin_active = True
        self._spin_angle = 0
        self._spin_timer.start()
        
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        
        try:
            state = LogsPageController.list_logs(run_cleanup=run_cleanup)
            if run_cleanup and state.cleanup_deleted > 0:
                log(f"🗑️ Удалено старых логов: {state.cleanup_deleted} из {state.cleanup_total}", "INFO")
            if run_cleanup and state.cleanup_errors:
                log(f"⚠️ Ошибки при удалении логов: {state.cleanup_errors[:3]}", "DEBUG")

            current_index = 0

            for entry in state.entries:
                if entry["is_current"]:
                    current_index = entry["index"]
                self.log_combo.addItem(entry["display"], userData=entry["path"])
            
            self.log_combo.setCurrentIndex(current_index)
            
        except Exception as e:
            log(f"Ошибка обновления списка логов: {e}", "ERROR")
        finally:
            self.log_combo.blockSignals(False)
            # Останавливаем анимацию через небольшую задержку для визуального эффекта
            QTimer.singleShot(500, self._stop_refresh_animation)
    
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
            src = qta.icon('fa5s.sync-alt', color=tokens.accent_hex).pixmap(22, 22)
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
        self._stop_tail_worker()
        plan = LogsPageController.build_tail_start_plan(current_log_file=self.current_log_file)
        if not plan.should_start:
            return

        self.log_text.clear()
        self.info_label.setText(plan.info_text)

        try:
            self._thread = QThread(self)
            self._worker = LogsPageController.create_log_tail_worker(plan.file_path)
            self._worker.moveToThread(self._thread)

            self._thread.started.connect(self._worker.run)
            self._worker.new_lines.connect(self._append_text)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._on_tail_thread_finished)
            self._thread.finished.connect(self._thread.deleteLater)

            self._thread.start()
        except Exception as e:
            log(f"Ошибка запуска log tail worker: {e}", "ERROR")

    def _on_tail_thread_finished(self):
        """Очищает ссылки на thread/worker после завершения, чтобы не дергать удалённые Qt-объекты."""
        self._thread = None
        self._worker = None
            
    def _stop_tail_worker(self, blocking: bool = False):
        """Останавливает worker (неблокирующий по умолчанию)"""
        worker = getattr(self, "_worker", None)
        thread = getattr(self, "_thread", None)
        stop_plan = LogsPageController.build_thread_stop_plan(
            has_worker=worker is not None,
            thread_running=bool(thread and self._thread and self._thread.isRunning()) if thread is not None else False,
            blocking=blocking,
        )

        if stop_plan.should_stop_worker and worker:
            try:
                worker.stop()
            except RuntimeError:
                # Qt-объект уже удалён
                self._worker = None
                worker = None

        if not thread:
            return

        try:
            running = bool(thread.isRunning())
        except RuntimeError:
            # Qt-объект уже удалён
            self._thread = None
            return

        if not stop_plan.should_quit_thread or not running:
            return

        thread.quit()
        if not stop_plan.should_wait:
            return

        # Блокирующий режим только при закрытии приложения
        if not thread.wait(stop_plan.wait_timeout_ms):
            log("⚠ Log tail worker не завершился, принудительно завершаем", "WARNING")
            if stop_plan.should_terminate:
                try:
                    thread.terminate()
                    thread.wait(stop_plan.terminate_wait_ms)
                except Exception:
                    pass

    def _start_winws_output_worker(self):
        """Запускает worker для чтения вывода winws"""
        self._stop_winws_output_worker()
        self._refresh_winws_title()

        plan = LogsPageController.build_winws_output_plan(
            launch_method=self._get_launch_method(),
            orchestra_runner=self._get_orchestra_runner(),
            language=self._ui_language,
        )
        self._set_winws_status(plan.status_kind, plan.status_text)

        if plan.action != "start_worker" or not plan.process:
            return

        try:
            self._winws_thread = QThread(self)
            self._winws_worker = LogsPageController.create_winws_output_worker(plan.process)
            self._winws_worker.moveToThread(self._winws_thread)

            self._winws_thread.started.connect(self._winws_worker.run)
            self._winws_worker.new_output.connect(self._append_winws_output)
            self._winws_worker.process_ended.connect(self._on_winws_process_ended)
            self._winws_worker.finished.connect(self._winws_thread.quit)

            self._winws_thread.start()
        except Exception as e:
            log(f"Ошибка запуска winws output worker: {e}", "ERROR")

    def _stop_winws_output_worker(self, blocking: bool = False):
        """Останавливает worker чтения вывода winws (неблокирующий по умолчанию)"""
        try:
            stop_plan = LogsPageController.build_thread_stop_plan(
                has_worker=self._winws_worker is not None,
                thread_running=bool(self._winws_thread and self._winws_thread.isRunning()),
                blocking=blocking,
            )
            if stop_plan.should_stop_worker and self._winws_worker:
                self._winws_worker.stop()
            if stop_plan.should_quit_thread and self._winws_thread and self._winws_thread.isRunning():
                self._winws_thread.quit()
                if stop_plan.should_wait:
                    # Блокирующий режим только при закрытии приложения
                    if not self._winws_thread.wait(stop_plan.wait_timeout_ms):
                        log("⚠ Winws output worker не завершился, принудительно завершаем", "WARNING")
                        if stop_plan.should_terminate:
                            try:
                                self._winws_thread.terminate()
                                self._winws_thread.wait(stop_plan.terminate_wait_ms)
                            except:
                                pass
                # Неблокирующий режим - поток остановится сам
        except Exception as e:
            log(f"Ошибка остановки winws output worker: {e}", "DEBUG")

    def _append_winws_output(self, text: str, stream_type: str):
        """Добавляет вывод winws в текстовое поле"""
        self._winws_lines_count += 1

        formatted = format_winws_output_line(
            text=text,
            stream_type=stream_type,
            stdout_color=self._winws_stdout_color,
            stderr_color=self._winws_stderr_color,
        )

        self.winws_text.append(formatted)

        # Автопрокрутка
        scrollbar = self.winws_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_winws_process_ended(self, exit_code: int):
        """Обработчик завершения процесса winws"""
        if exit_code == 0:
            self._set_winws_status(
                "neutral",
                tr_catalog(
                    "page.logs.winws.status.ended_template",
                    language=self._ui_language,
                    default="Процесс завершён (код: {code})",
                ).format(code=exit_code),
            )
        else:
            self._set_winws_status(
                "error",
                tr_catalog(
                    "page.logs.winws.status.ended_error_template",
                    language=self._ui_language,
                    default="Процесс завершён с ошибкой (код: {code})",
                ).format(code=exit_code),
            )

    def _update_winws_status(self):
        """Периодически проверяет статус процесса winws"""
        self._refresh_winws_title()
        source, runner = self._get_running_runner_source()

        if source == "orchestra" and runner:
            # Для оркестратора всегда останавливаем worker чтения stdout,
            # чтобы не конкурировать с внутренним reader'ом orchestra_runner.
            if self._winws_thread and self._winws_thread.isRunning():
                self._stop_winws_output_worker()

            pid = self._get_runner_pid(runner)
            self._set_winws_status("running", f"PID: {pid} | Оркестратор")
            return

        if source == "direct" and runner:
            # Если worker не работает, запускаем его
            if not self._winws_thread or not self._winws_thread.isRunning():
                self._start_winws_output_worker()
            return

        # Процесс не запущен - обновляем статус если worker не работает
        if not self._winws_thread or not self._winws_thread.isRunning():
            self._set_winws_status(
                "neutral",
                tr_catalog("page.logs.winws.status.not_running", language=self._ui_language, default="Процесс не запущен"),
            )

    def _clear_winws_output(self):
        """Очищает поле вывода winws"""
        self.winws_text.clear()
        self._winws_lines_count = 0
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.winws_cleared",
                language=self._ui_language,
                default="🧹 Вывод winws очищен",
            )
        )

    def _append_text(self, text: str):
        """Добавляет текст в лог"""
        if not text:
            return

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
        text = self.log_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.info_label.setText(
                tr_catalog(
                    "page.logs.info.copied",
                    language=self._ui_language,
                    default="✅ Скопировано в буфер обмена",
                )
            )
        else:
            self.info_label.setText(
                tr_catalog(
                    "page.logs.info.empty",
                    language=self._ui_language,
                    default="⚠️ Лог пуст",
                )
            )
            
    def _clear_view(self):
        """Очищает вид (не файл)"""
        self.log_text.clear()
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.view_cleared",
                language=self._ui_language,
                default="🧹 Вид очищен",
            )
        )
        
    def _open_folder(self):
        """Открывает папку с логами"""
        try:
            LogsPageController.open_logs_folder()
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            
    def _update_stats(self):
        """Обновляет статистику"""
        try:
            stats = LogsPageController.build_stats()
            plan = LogsPageController.build_stats_text_plan(stats, language=self._ui_language)
            self.stats_label.setText(plan.text)
        except Exception as e:
            self.stats_label.setText(f"Ошибка статистики: {e}")

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
        self._errors_count = clear_errors(
            errors_text=self.errors_text,
            errors_count_label=self.errors_count_label,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
        )
        self._update_errors_text_height()
        self.info_label.setText(
            tr_catalog(
                "page.logs.info.errors_cleared",
                language=self._ui_language,
                default="🧹 Ошибки очищены",
            )
        )
            
    def cleanup(self):
        """Очистка при закрытии - блокирующий режим"""
        self._winws_status_timer.stop()
        self._stop_tail_worker(blocking=True)
        self._stop_winws_output_worker(blocking=True)
