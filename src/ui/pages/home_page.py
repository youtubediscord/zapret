# ui/pages/home_page.py
"""Главная страница - обзор состояния системы"""

import time as _time

from PyQt6.QtCore import (
    Qt,
    QSize,
    QTimer,
    QThread,
    pyqtSignal,
    QUrl,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout
)
from PyQt6.QtGui import QColor, QDesktopServices
import qtawesome as qta

from .base_page import BasePage
from ui.compat_widgets import SettingsCard, StatusIndicator, ActionButton, set_tooltip
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.window_action_controller import (
    open_connection_test as _open_connection_test_action,
    open_folder as _open_folder_action,
    start_dpi as _start_dpi_action,
    stop_dpi as _stop_dpi_action,
)
from log import log

try:
    from qfluentwidgets import (
        CardWidget, isDarkTheme, themeColor,
        SubtitleLabel, BodyLabel, StrongBodyLabel, CaptionLabel,
        IndeterminateProgressBar,
    )
    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    HAS_FLUENT = False
    CardWidget = QFrame


class AutostartCheckWorker(QThread):
    """Быстрая фоновая проверка статуса автозапуска"""
    finished = pyqtSignal(bool)  # True если автозапуск включён
    
    def run(self):
        try:
            result = self._check_autostart()
            self.finished.emit(result)
        except Exception as e:
            log(f"AutostartCheckWorker error: {e}", "WARNING")
            self.finished.emit(False)
    
    def _check_autostart(self) -> bool:
        """Быстрая проверка наличия автозапуска через реестр"""
        try:
            from autostart.registry_check import AutostartRegistryChecker
            return AutostartRegistryChecker.is_autostart_enabled()
        except Exception:
            return False


def _accent_hex() -> str:
    """Get current accent color hex."""
    if HAS_FLUENT:
        try:
            return themeColor().name()
        except Exception:
            pass
    return "#60cdff"


def _log_startup_home_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    log(f"⏱ Startup UI Section: HOME {section} {rounded}ms", "⏱ STARTUP")


class StatusCard(CardWidget if HAS_FLUENT else QFrame):
    """Большая карточка статуса на главной странице"""

    clicked = pyqtSignal()

    def __init__(self, icon_name: str, title: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._use_fluent_icon = False
        self.setObjectName("statusCard")
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Top row: icon + title
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        self.icon_label = QLabel()
        try:
            from ui.fluent_icons import fluent_pixmap
            self.icon_label.setPixmap(fluent_pixmap(icon_name, 28))
            self._use_fluent_icon = True
        except Exception:
            self.icon_label.setPixmap(qta.icon(icon_name, color=_accent_hex()).pixmap(28, 28))
        self.icon_label.setFixedSize(32, 32)
        top_layout.addWidget(self.icon_label)

        if HAS_FLUENT:
            self.title_label = CaptionLabel(title)
        else:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()

        layout.addLayout(top_layout)

        # Value (large text)
        if HAS_FLUENT:
            self.value_label = SubtitleLabel("\u2014")
        else:
            self.value_label = QLabel("\u2014")
            self.value_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self.value_label)

        # Additional info
        if HAS_FLUENT:
            self.info_label = CaptionLabel("")
        else:
            self.info_label = QLabel("")
            self.info_label.setStyleSheet("font-size: 11px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        layout.addStretch()

    def set_title(self, title: str) -> None:
        try:
            self.title_label.setText(title)
        except Exception:
            pass
        
    def set_value(self, value: str, info: str = ""):
        """Устанавливает текстовое значение"""
        # Скрываем иконки, показываем текст
        if hasattr(self, 'icons_container'):
            self.icons_container.hide()
        self.value_label.show()
        self.value_label.setText(value)
        self.info_label.setText(info)
    
    def set_value_with_icons(self, categories_data: list, info: str = ""):
        """
        Устанавливает значение с иконками категорий.
        
        Args:
            categories_data: список кортежей (icon_name, icon_color, is_active)
            info: текст подписи
        """
        # Создаём контейнер для иконок если его нет
        if not hasattr(self, 'icons_container'):
            self.icons_container = QWidget()
            self.icons_layout = QHBoxLayout(self.icons_container)
            self.icons_layout.setContentsMargins(0, 0, 0, 0)
            self.icons_layout.setSpacing(4)
            # Вставляем после value_label
            lay = self.layout()
            if isinstance(lay, QVBoxLayout):
                lay.insertWidget(2, self.icons_container)
            else:
                # Fallback: keep layout stable even if stubs/types differ.
                try:
                    lay.insertWidget(2, self.icons_container)  # type: ignore[attr-defined]
                except Exception:
                    try:
                        lay.addWidget(self.icons_container)  # type: ignore[attr-defined]
                    except Exception:
                        pass
        
        # Очищаем старые иконки
        while self.icons_layout.count():
            item = self.icons_layout.takeAt(0)
            if not item:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()
        
        # Скрываем текстовый label, показываем иконки
        self.value_label.hide()
        self.icons_container.show()
        
        # Добавляем иконки категорий
        active_count = 0
        for icon_name, icon_color, is_active in categories_data:
            if is_active:
                active_count += 1
                icon_label = QLabel()
                try:
                    pixmap = qta.icon(icon_name, color=icon_color).pixmap(20, 20)
                    icon_label.setPixmap(pixmap)
                except:
                    pixmap = qta.icon('fa5s.globe', color=_accent_hex()).pixmap(20, 20)
                    icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(22, 22)
                set_tooltip(icon_label, icon_name.split('.')[-1].replace('-', ' ').title())
                self.icons_layout.addWidget(icon_label)
        
        # Если слишком много - показываем +N
        if active_count > 10:
            # Оставляем первые 9 + счётчик
            while self.icons_layout.count() > 9:
                item = self.icons_layout.takeAt(9)
                if not item:
                    continue
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            
            extra_label = QLabel(f"+{active_count - 9}")
            try:
                from qfluentwidgets import isDarkTheme as _idt
                _dark = _idt()
            except Exception:
                _dark = True
            _extra_bg = "rgba(255,255,255,0.06)" if _dark else "rgba(0,0,0,0.06)"
            _extra_border = "rgba(255,255,255,0.08)" if _dark else "rgba(0,0,0,0.10)"
            extra_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 6px;
                    background: {_extra_bg};
                    border: 1px solid {_extra_border};
                    border-radius: 8px;
                }}
            """)
            self.icons_layout.addWidget(extra_label)
        
        self.icons_layout.addStretch()
        self.info_label.setText(info)
        
    def set_status_color(self, status: str):
        """Меняет цвет иконки по статусу"""
        colors = {
            'running': '#4caf50',
            'stopped': '#f44336',
            'warning': '#ff9800',
            'neutral': _accent_hex(),
        }
        color = colors.get(status, colors['neutral'])
        # Применяем цвет к value_label: через Fluent API когда доступен,
        # иначе через raw setStyleSheet для QLabel-fallback.
        if HAS_FLUENT:
            self.value_label.setTextColor(QColor(color), QColor(color))
        else:
            self.value_label.setStyleSheet(f"color: {color};")

    def mousePressEvent(self, event):  # type: ignore[override]
        """Обработка клика по карточке"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HomePage(BasePage):
    """Главная страница - обзор состояния"""

    # Сигналы для навигации на другие страницы
    navigate_to_control = pyqtSignal()
    navigate_to_strategies = pyqtSignal()
    navigate_to_autostart = pyqtSignal()
    navigate_to_premium = pyqtSignal()
    navigate_to_dpi_settings = pyqtSignal()

    _LAUNCH_METHOD_LABELS = {
        "direct_zapret2": "page.home.launch_method.direct_z2",
        "direct_zapret1": "page.home.launch_method.direct_z1",
        "orchestra": "page.home.launch_method.orchestra",
        "direct_zapret2_orchestra": "page.home.launch_method.orchestra_z2",
    }

    def __init__(self, parent=None):
        _t_init = _time.perf_counter()
        _t_base = _time.perf_counter()
        super().__init__(
            "Главная",
            "Обзор состояния Zapret",
            parent,
            title_key="page.home.title",
            subtitle_key="page.home.subtitle",
        )
        _log_startup_home_metric("__init__.base_page", (_time.perf_counter() - _t_base) * 1000)

        self._autostart_worker = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._startup_showevent_profile_logged = False
        _t_build = _time.perf_counter()
        self._build_ui()
        _log_startup_home_metric("__init__.build_ui", (_time.perf_counter() - _t_build) * 1000)
        _t_connect = _time.perf_counter()
        self._connect_card_signals()
        _log_startup_home_metric("__init__.connect_card_signals", (_time.perf_counter() - _t_connect) * 1000)
        _log_startup_home_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def showEvent(self, event):  # type: ignore[override]
        """При показе страницы обновляем статус автозапуска"""
        _t_show = _time.perf_counter()
        super().showEvent(event)
        # Не нагружаем самый первый кадр второстепенными действиями.
        QTimer.singleShot(280, self._check_autostart_status)
        QTimer.singleShot(360, self._refresh_strategy_card)
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_home_metric("showEvent.schedule_deferred", (_time.perf_counter() - _t_show) * 1000)

    def _get_launch_method_display_name(self) -> str:
        """Возвращает человекочитаемое название текущего метода запуска."""
        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
            if method:
                label_key = self._LAUNCH_METHOD_LABELS.get(method, self._LAUNCH_METHOD_LABELS["direct_zapret2"])
                return tr_catalog(label_key, language=self._ui_language, default="Zapret 2")
        except Exception:
            pass
        return tr_catalog(self._LAUNCH_METHOD_LABELS["direct_zapret2"], language=self._ui_language, default="Zapret 2")

    def update_launch_method_card(self) -> None:
        """Обновляет карточку метода запуска на главной странице."""
        self.strategy_card.set_value(
            self._get_launch_method_display_name(),
            tr_catalog("page.home.strategy.current_method", language=self._ui_language, default="Текущий метод запуска"),
        )

    def _refresh_strategy_card(self) -> None:
        """Обновляет карточку метода запуска после инициализации UI."""
        self.update_launch_method_card()
    
    def _check_autostart_status(self):
        """Запускает фоновую проверку статуса автозапуска"""
        if self._autostart_worker is not None and self._autostart_worker.isRunning():
            return
        
        self._autostart_worker = AutostartCheckWorker()
        self._autostart_worker.finished.connect(self._on_autostart_checked)
        self._autostart_worker.start()
    
    def _on_autostart_checked(self, enabled: bool):
        """Обработчик результата проверки автозапуска"""
        app_runtime_state = getattr(self.window(), "app_runtime_state", None)
        if app_runtime_state is not None:
            app_runtime_state.set_autostart(bool(enabled))
        elif self._ui_state_store is not None:
            self._ui_state_store.set_autostart(enabled)
        else:
            self.update_autostart_status(enabled)

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={
                "dpi_phase",
                "dpi_running",
                "dpi_busy",
                "dpi_busy_text",
                "dpi_last_error",
                "mode_revision",
                "autostart_enabled",
                "subscription_is_premium",
                "subscription_days_remaining",
                "status_text",
                "status_kind",
                "current_strategy_summary",
            },
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        self.update_dpi_status(
            state.dpi_phase or ("running" if state.dpi_running else "stopped"),
            state.current_strategy_summary or None,
            state.dpi_last_error,
        )
        self.update_autostart_status(state.autostart_enabled)
        self.update_subscription_status(
            state.subscription_is_premium,
            state.subscription_days_remaining,
        )
        if state.status_text:
            self.set_status(state.status_text, state.status_kind or "neutral")
        self.set_loading(state.dpi_busy, state.dpi_busy_text)
        self.update_launch_method_card()
        
    def _build_ui(self):
        _t_total = _time.perf_counter()

        # Сетка карточек статуса
        _t_cards = _time.perf_counter()
        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        
        # Карточка статуса DPI
        self.dpi_status_card = StatusCard("fa5s.shield-alt", tr_catalog("page.home.card.dpi.title", language=self._ui_language, default="Статус Zapret"))
        self.dpi_status_card.set_value(
            tr_catalog("page.home.status.checking", language=self._ui_language, default="Проверка..."),
            tr_catalog("page.home.status.detecting", language=self._ui_language, default="Определение состояния"),
        )
        cards_layout.addWidget(self.dpi_status_card, 0, 0)
        
        # Карточка стратегии
        self.strategy_card = StatusCard("fa5s.cog", tr_catalog("page.home.card.method.title", language=self._ui_language, default="Метод запуска"))
        self.strategy_card.set_value(
            self._get_launch_method_display_name(),
            tr_catalog("page.home.strategy.current_method", language=self._ui_language, default="Текущий метод запуска"),
        )
        cards_layout.addWidget(self.strategy_card, 0, 1)
        
        # Карточка автозапуска
        self.autostart_card = StatusCard("fa5s.rocket", tr_catalog("page.home.card.autostart.title", language=self._ui_language, default="Автозапуск"))
        self.autostart_card.set_value(
            tr_catalog("page.home.autostart.disabled", language=self._ui_language, default="Отключён"),
            tr_catalog("page.home.autostart.manual", language=self._ui_language, default="Запускайте вручную"),
        )
        cards_layout.addWidget(self.autostart_card, 1, 0)
        
        # Карточка подписки
        self.subscription_card = StatusCard("fa5s.star", tr_catalog("page.home.card.subscription.title", language=self._ui_language, default="Подписка"))
        self.subscription_card.set_value(
            tr_catalog("page.home.subscription.free", language=self._ui_language, default="Free"),
            tr_catalog("page.home.subscription.basic", language=self._ui_language, default="Базовые функции"),
        )
        cards_layout.addWidget(self.subscription_card, 1, 1)
        
        self.cards_widget = QWidget(self.content)  # ✅ Явный родитель
        self.cards_widget.setLayout(cards_layout)
        self.add_widget(self.cards_widget)
        _log_startup_home_metric("_build_ui.status_cards", (_time.perf_counter() - _t_cards) * 1000)
        
        self.add_spacing(8)
        
        # Быстрые действия
        _t_actions = _time.perf_counter()
        self.add_section_title(text_key="page.home.section.quick_actions")
        
        self.actions_card = SettingsCard()
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        # Кнопка запуска
        self.start_btn = ActionButton(tr_catalog("page.home.action.start", language=self._ui_language, default="Запустить"), "fa5s.play", accent=True)
        self.start_btn.clicked.connect(self._start_dpi)
        actions_layout.addWidget(self.start_btn)
        
        # Кнопка остановки
        self.stop_btn = ActionButton(tr_catalog("page.home.action.stop", language=self._ui_language, default="Остановить"), "fa5s.stop")
        self.stop_btn.clicked.connect(self._stop_dpi)
        self.stop_btn.setVisible(False)
        actions_layout.addWidget(self.stop_btn)
        
        # Кнопка теста
        self.test_btn = ActionButton(tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"), "fa5s.wifi")
        self.test_btn.clicked.connect(self._open_connection_test)
        actions_layout.addWidget(self.test_btn)
        
        # Кнопка папки
        self.folder_btn = ActionButton(tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"), "fa5s.folder-open")
        self.folder_btn.clicked.connect(self._open_folder)
        actions_layout.addWidget(self.folder_btn)

        # Кнопка "Как использовать"
        self.guide_btn = ActionButton(tr_catalog("page.home.action.how_to_use", language=self._ui_language, default="Как использовать"), "fa5s.question-circle")
        self.guide_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://publish.obsidian.md/zapret/Zapret/guide"))
        )
        actions_layout.addWidget(self.guide_btn)
        
        actions_layout.addStretch()
        self.actions_card.add_layout(actions_layout)
        self.add_widget(self.actions_card)
        _log_startup_home_metric("_build_ui.quick_actions", (_time.perf_counter() - _t_actions) * 1000)
        
        self.add_spacing(8)
        
        # Статусная строка
        _t_status = _time.perf_counter()
        self.add_section_title(text_key="page.home.section.status")
        
        self.status_card = SettingsCard()
        self.status_indicator = StatusIndicator()
        self.status_indicator.set_status(tr_catalog("page.home.status.ready", language=self._ui_language, default="Готов к работе"), "neutral")
        self.status_card.add_widget(self.status_indicator)
        self.add_widget(self.status_card)
        
        # Индикатор загрузки (бегающая полоска)
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        self.add_widget(self.progress_bar)
        _log_startup_home_metric("_build_ui.status_block", (_time.perf_counter() - _t_status) * 1000)

        self.add_spacing(12)

        # Блок Premium
        _t_premium = _time.perf_counter()
        self._build_premium_block()
        _log_startup_home_metric("_build_ui.premium_block", (_time.perf_counter() - _t_premium) * 1000)
        _log_startup_home_metric("_build_ui.total", (_time.perf_counter() - _t_total) * 1000)

    def _connect_card_signals(self):
        """Подключает клики по карточкам к сигналам навигации"""
        self.dpi_status_card.clicked.connect(self.navigate_to_control.emit)
        self.strategy_card.clicked.connect(self.navigate_to_dpi_settings.emit)
        self.autostart_card.clicked.connect(self.navigate_to_autostart.emit)
        self.subscription_card.clicked.connect(self.navigate_to_premium.emit)

    def _start_dpi(self) -> None:
        """Локальный обработчик запуска DPI для кнопки на главной."""
        _start_dpi_action(self)

    def _stop_dpi(self) -> None:
        """Локальный обработчик остановки DPI для кнопки на главной."""
        _stop_dpi_action(self)

    def _open_connection_test(self) -> None:
        """Локальный обработчик открытия страницы теста соединения."""
        _open_connection_test_action(self)

    def _open_folder(self) -> None:
        """Локальный обработчик открытия рабочей папки приложения."""
        _open_folder_action(self)
        
    @staticmethod
    def _short_dpi_error(last_error: str) -> str:
        text = str(last_error or "").strip()
        if not text:
            return ""
        first_line = text.splitlines()[0].strip()
        if len(first_line) <= 160:
            return first_line
        return first_line[:157] + "..."

    def update_dpi_status(self, state: str | bool, strategy_name: str | None = None, last_error: str = ""):
        """Обновляет отображение статуса DPI"""
        phase = str(state or "").strip().lower()
        if phase not in {"starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        if phase == "running":
            self.dpi_status_card.set_value(
                tr_catalog("page.home.status.running", language=self._ui_language, default="Запущен"),
                tr_catalog("page.home.status.bypass_active", language=self._ui_language, default="Обход блокировок активен"),
            )
            self.dpi_status_card.set_status_color('running')
            self.start_btn.setVisible(False)
            self.stop_btn.setVisible(True)
        elif phase == "starting":
            self.dpi_status_card.set_value("Запускается", "Ждём подтверждение процесса winws")
            self.dpi_status_card.set_status_color('warning')
            self.start_btn.setVisible(False)
            self.stop_btn.setVisible(False)
        elif phase == "stopping":
            self.dpi_status_card.set_value("Останавливается", "Завершаем процесс и освобождаем WinDivert")
            self.dpi_status_card.set_status_color('warning')
            self.start_btn.setVisible(False)
            self.stop_btn.setVisible(False)
        elif phase == "failed":
            self.dpi_status_card.set_value("Ошибка запуска", self._short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу")
            self.dpi_status_card.set_status_color('stopped')
            self.start_btn.setVisible(True)
            self.stop_btn.setVisible(False)
        else:
            self.dpi_status_card.set_value(
                tr_catalog("page.home.status.stopped", language=self._ui_language, default="Остановлен"),
                tr_catalog("page.home.status.press_start", language=self._ui_language, default="Нажмите Запустить"),
            )
            self.dpi_status_card.set_status_color('stopped')
            self.start_btn.setVisible(True)
            self.stop_btn.setVisible(False)
            
        # На главной всегда отображаем текущий метод запуска (без иконок категорий).
        self.update_launch_method_card()

    def _update_strategy_card_with_icons(self, strategy_name: str):
        """Совместимость: карточка на главной теперь показывает метод запуска."""
        _ = strategy_name
        self.update_launch_method_card()
    
    def _truncate_strategy_name(self, name: str, max_items: int = 2) -> str:
        """Обрезает длинное название стратегии для карточки"""
        if not name or name in ("Не выбрана", "Прямой запуск"):
            return name
        
        # Определяем разделитель - поддерживаем и " • " (Direct режим) и ", " (старый формат)
        separator = " • " if " • " in name else ", "
        
        # Если это список категорий
        if separator in name:
            parts = name.split(separator)
            # Проверяем есть ли "+N ещё" в конце
            extra = ""
            if parts and (parts[-1].startswith("+") or "ещё" in parts[-1]):
                # Извлекаем число из "+N ещё"
                last_part = parts[-1]
                if last_part.startswith("+"):
                    # Формат "+2 ещё"
                    extra_num = int(''.join(filter(str.isdigit, last_part))) or 0
                    parts = parts[:-1]
                    extra_num += len(parts) - max_items
                    if extra_num > 0:
                        extra = f"+{extra_num}"
            elif len(parts) > max_items:
                extra = f"+{len(parts) - max_items}"
                
            if len(parts) > max_items:
                return separator.join(parts[:max_items]) + (f" {extra}" if extra else "")
            elif extra:
                return separator.join(parts) + f" {extra}"
                
        return name
            
    def update_autostart_status(self, enabled: bool):
        """Обновляет отображение статуса автозапуска"""
        if enabled:
            self.autostart_card.set_value(
                tr_catalog("page.home.autostart.enabled", language=self._ui_language, default="Включён"),
                tr_catalog("page.home.autostart.with_windows", language=self._ui_language, default="Запускается с Windows"),
            )
            self.autostart_card.set_status_color('running')
        else:
            self.autostart_card.set_value(
                tr_catalog("page.home.autostart.disabled", language=self._ui_language, default="Отключён"),
                tr_catalog("page.home.autostart.manual", language=self._ui_language, default="Запускайте вручную"),
            )
            self.autostart_card.set_status_color('neutral')
            
    def update_subscription_status(self, is_premium: bool, days: int | None = None):
        """Обновляет отображение статуса подписки"""
        if is_premium:
            if days:
                self.subscription_card.set_value(
                    tr_catalog("page.home.subscription.premium", language=self._ui_language, default="Premium"),
                    tr_catalog("page.home.subscription.days_left", language=self._ui_language, default="Осталось {days} дней").format(days=days),
                )
            else:
                self.subscription_card.set_value(
                    tr_catalog("page.home.subscription.premium", language=self._ui_language, default="Premium"),
                    tr_catalog("page.home.subscription.all_features", language=self._ui_language, default="Все функции доступны"),
                )
            self.subscription_card.set_status_color('running')
        else:
            self.subscription_card.set_value(
                tr_catalog("page.home.subscription.free", language=self._ui_language, default="Free"),
                tr_catalog("page.home.subscription.basic", language=self._ui_language, default="Базовые функции"),
            )
            self.subscription_card.set_status_color('neutral')
            
    def set_status(self, text: str, status: str = "neutral"):
        """Устанавливает текст статусной строки"""
        self.status_indicator.set_status(text, status)
    
    def set_loading(self, loading: bool, text: str = ""):
        """Показывает/скрывает индикатор загрузки и блокирует кнопки"""
        self.progress_bar.setVisible(loading)
        if HAS_FLUENT:
            if loading:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()

        # Блокируем/разблокируем кнопки
        self.start_btn.setEnabled(not loading)
        self.stop_btn.setEnabled(not loading)
        
        # Обновляем статус если есть текст
        if loading and text:
            self.status_indicator.set_status(text, "neutral")
        
    def _build_premium_block(self):
        """Создает блок Premium на главной странице"""
        self.premium_card = SettingsCard()
        
        premium_layout = QHBoxLayout()
        premium_layout.setSpacing(16)
        
        # Иконка звезды
        star_label = QLabel()
        star_label.setPixmap(qta.icon('fa5s.star', color='#ffc107').pixmap(32, 32))
        star_label.setFixedSize(40, 40)
        premium_layout.addWidget(star_label)
        
        # Текст
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        if HAS_FLUENT:
            title = StrongBodyLabel(tr_catalog("page.home.premium.title", language=self._ui_language, default="Zapret Premium"))
        else:
            title = QLabel(tr_catalog("page.home.premium.title", language=self._ui_language, default="Zapret Premium"))
            title.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.premium_title_label = title
        text_layout.addWidget(title)

        if HAS_FLUENT:
            desc = CaptionLabel(tr_catalog("page.home.premium.desc", language=self._ui_language, default="Дополнительные темы, приоритетная поддержка и VPN-сервис"))
        else:
            desc = QLabel(tr_catalog("page.home.premium.desc", language=self._ui_language, default="Дополнительные темы, приоритетная поддержка и VPN-сервис"))
            desc.setStyleSheet("font-size: 12px;")
        self.premium_desc_label = desc
        desc.setWordWrap(True)
        text_layout.addWidget(desc)
        
        premium_layout.addLayout(text_layout, 1)
        
        # Кнопка Premium
        self.premium_link_btn = ActionButton(tr_catalog("page.home.premium.more", language=self._ui_language, default="Подробнее"), "fa5s.arrow-right")
        self.premium_link_btn.setFixedHeight(36)
        premium_layout.addWidget(self.premium_link_btn)
        
        self.premium_card.add_layout(premium_layout)
        self.add_widget(self.premium_card)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.dpi_status_card.set_title(tr_catalog("page.home.card.dpi.title", language=self._ui_language, default="Статус Zapret"))
        self.strategy_card.set_title(tr_catalog("page.home.card.method.title", language=self._ui_language, default="Метод запуска"))
        self.autostart_card.set_title(tr_catalog("page.home.card.autostart.title", language=self._ui_language, default="Автозапуск"))
        self.subscription_card.set_title(tr_catalog("page.home.card.subscription.title", language=self._ui_language, default="Подписка"))

        self.start_btn.setText(tr_catalog("page.home.action.start", language=self._ui_language, default="Запустить"))
        self.stop_btn.setText(tr_catalog("page.home.action.stop", language=self._ui_language, default="Остановить"))
        self.test_btn.setText(tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"))
        self.folder_btn.setText(tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"))
        self.guide_btn.setText(tr_catalog("page.home.action.how_to_use", language=self._ui_language, default="Как использовать"))

        try:
            self.premium_title_label.setText(tr_catalog("page.home.premium.title", language=self._ui_language, default="Zapret Premium"))
            self.premium_desc_label.setText(tr_catalog("page.home.premium.desc", language=self._ui_language, default="Дополнительные темы, приоритетная поддержка и VPN-сервис"))
        except Exception:
            pass
        self.premium_link_btn.setText(tr_catalog("page.home.premium.more", language=self._ui_language, default="Подробнее"))

        # Refresh runtime-dependent card texts using current state.
        try:
            self.update_launch_method_card()
        except Exception:
            pass
