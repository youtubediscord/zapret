# ui/pages/home_page.py
"""Главная страница - обзор состояния системы"""

import time as _time

from PyQt6.QtCore import (
    Qt,
    QSize,
    QTimer,
    pyqtSignal,
    QUrl,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QPushButton
)
from PyQt6.QtGui import QColor, QDesktopServices
import qtawesome as qta

from .base_page import BasePage
from ui.home_page_controller import HomePageController
from ui.compat_widgets import SettingsCard, StatusIndicator, set_tooltip
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
        PushButton,
        SubtitleLabel, BodyLabel, StrongBodyLabel, CaptionLabel,
        IndeterminateProgressBar, SettingCardGroup, PushSettingCard, PrimaryPushSettingCard,
    )
    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    HAS_FLUENT = False
    CardWidget = QFrame
    PushButton = QPushButton  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    PrimaryPushSettingCard = None  # type: ignore[assignment]


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

        self._controller = HomePageController()
        self._autostart_worker = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._startup_showevent_profile_logged = False
        self._actions_group = None
        self._actions_section_label = None
        self._start_action_card = None
        self._stop_action_card = None
        self._test_action_card = None
        self._folder_action_card = None
        self._guide_action_card = None
        self.enable_deferred_ui_build(after_build=self._after_ui_built)
        _log_startup_home_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def _after_ui_built(self) -> None:
        _t_build = _time.perf_counter()
        self._connect_card_signals()
        _log_startup_home_metric("__init__.connect_card_signals", (_time.perf_counter() - _t_build) * 1000)

    def on_page_activated(self, first_show: bool) -> None:
        """При активации страницы обновляем лёгкое runtime-состояние."""
        _ = first_show
        _t_show = _time.perf_counter()
        self._check_autostart_status()
        self._refresh_strategy_card()
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_home_metric("activation.schedule_deferred", (_time.perf_counter() - _t_show) * 1000)

    def update_launch_method_card(self) -> None:
        """Обновляет карточку метода запуска на главной странице."""
        plan = self._controller.build_launch_method_plan(language=self._ui_language)
        self.strategy_card.set_value(
            plan.value,
            plan.info,
        )

    def _refresh_strategy_card(self) -> None:
        """Обновляет карточку метода запуска после инициализации UI."""
        self.update_launch_method_card()
    
    def _check_autostart_status(self):
        """Запускает фоновую проверку статуса автозапуска"""
        if self._autostart_worker is not None and self._autostart_worker.isRunning():
            return
        
        self._autostart_worker = self._controller.create_autostart_worker()
        self._autostart_worker.finished.connect(self._on_autostart_checked)
        self._autostart_worker.start()
    
    def _on_autostart_checked(self, enabled: bool):
        """Обработчик результата проверки автозапуска"""
        dispatch_plan = self._controller.build_autostart_dispatch_plan(
            has_runtime_state=getattr(self.window(), "app_runtime_state", None) is not None,
            has_store=self._ui_state_store is not None,
            enabled=enabled,
        )
        app_runtime_state = getattr(self.window(), "app_runtime_state", None)
        if dispatch_plan.target == "runtime" and app_runtime_state is not None:
            app_runtime_state.set_autostart(dispatch_plan.enabled)
        elif dispatch_plan.target == "store" and self._ui_state_store is not None:
            self._ui_state_store.set_autostart(dispatch_plan.enabled)
        else:
            self.update_autostart_status(dispatch_plan.enabled)

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
        launch_plan = self._controller.build_launch_method_plan(language=self._ui_language)
        self.strategy_card = StatusCard("fa5s.cog", tr_catalog("page.home.card.method.title", language=self._ui_language, default="Метод запуска"))
        self.strategy_card.set_value(
            launch_plan.value,
            launch_plan.info,
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
        quick_actions_title = tr_catalog("page.home.section.quick_actions", language=self._ui_language, default="Быстрые действия")
        self._actions_section_label = None
        self._actions_group = SettingCardGroup(quick_actions_title, self.content)
        self.actions_card = self._actions_group

        self._start_action_card = PrimaryPushSettingCard(
            tr_catalog("page.home.action.start", language=self._ui_language, default="Запустить"),
            qta.icon("fa5s.play", color="#4CAF50"),
            tr_catalog("page.home.action.start.title", language=self._ui_language, default="Запустить Zapret"),
            tr_catalog(
                "page.home.action.start.description",
                language=self._ui_language,
                default="Запустить обход блокировок прямо с главного экрана.",
            ),
        )
        self.start_btn = self._start_action_card.button
        self.start_btn.clicked.connect(self._start_dpi)
        self._actions_group.addSettingCard(self._start_action_card)

        self._stop_action_card = PushSettingCard(
            tr_catalog("page.home.action.stop", language=self._ui_language, default="Остановить"),
            qta.icon("fa5s.stop", color="#ff9800"),
            tr_catalog("page.home.action.stop.title", language=self._ui_language, default="Остановить Zapret"),
            tr_catalog(
                "page.home.action.stop.description",
                language=self._ui_language,
                default="Остановить уже запущенный процесс обхода блокировок.",
            ),
        )
        self.stop_btn = self._stop_action_card.button
        self.stop_btn.clicked.connect(self._stop_dpi)
        self._stop_action_card.setVisible(False)
        self._actions_group.addSettingCard(self._stop_action_card)

        self._test_action_card = PushSettingCard(
            tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"),
            qta.icon("fa5s.wifi", color=_accent_hex()),
            tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"),
            tr_catalog(
                "page.home.action.connection_test.description",
                language=self._ui_language,
                default="Открыть страницу диагностики сетевых соединений.",
            ),
        )
        self.test_btn = self._test_action_card.button
        self.test_btn.clicked.connect(self._open_connection_test)
        self._actions_group.addSettingCard(self._test_action_card)

        self._folder_action_card = PushSettingCard(
            tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"),
            qta.icon("fa5s.folder-open", color=_accent_hex()),
            tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"),
            tr_catalog(
                "page.home.action.open_folder.description",
                language=self._ui_language,
                default="Открыть рабочую папку приложения и связанные файлы.",
            ),
        )
        self.folder_btn = self._folder_action_card.button
        self.folder_btn.clicked.connect(self._open_folder)
        self._actions_group.addSettingCard(self._folder_action_card)

        self._guide_action_card = PushSettingCard(
            tr_catalog("page.home.action.how_to_use", language=self._ui_language, default="Как использовать"),
            qta.icon("fa5s.question-circle", color=_accent_hex()),
            tr_catalog("page.home.action.how_to_use", language=self._ui_language, default="Как использовать"),
            tr_catalog(
                "page.home.action.how_to_use.description",
                language=self._ui_language,
                default="Открыть руководство по использованию в браузере.",
            ),
        )
        self.guide_btn = self._guide_action_card.button
        self.guide_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://publish.obsidian.md/zapret/Zapret/guide"))
        )
        self._actions_group.addSettingCard(self._guide_action_card)
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
        
    def update_dpi_status(self, state: str | bool, strategy_name: str | None = None, last_error: str = ""):
        """Обновляет отображение статуса DPI"""
        _ = strategy_name
        plan = self._controller.build_dpi_status_plan(
            state=state,
            last_error=last_error,
            language=self._ui_language,
        )
        self.dpi_status_card.set_value(plan.value, plan.info)
        self.dpi_status_card.set_status_color(plan.status_color)
        self._start_action_card.setVisible(plan.show_start)
        self._stop_action_card.setVisible(plan.show_stop)
            
        # На главной всегда отображаем текущий метод запуска (без иконок категорий).
        self.update_launch_method_card()

    def _update_strategy_card_with_icons(self, strategy_name: str):
        """Совместимость: карточка на главной теперь показывает метод запуска."""
        _ = strategy_name
        self.update_launch_method_card()
    
    def update_autostart_status(self, enabled: bool):
        """Обновляет отображение статуса автозапуска"""
        plan = self._controller.build_autostart_status_plan(enabled=enabled, language=self._ui_language)
        self.autostart_card.set_value(plan.value, plan.info)
        self.autostart_card.set_status_color(plan.status_color)
            
    def update_subscription_status(self, is_premium: bool, days: int | None = None):
        """Обновляет отображение статуса подписки"""
        plan = self._controller.build_subscription_status_plan(
            is_premium=is_premium,
            days=days,
            language=self._ui_language,
        )
        self.subscription_card.set_value(plan.value, plan.info)
        self.subscription_card.set_status_color(plan.status_color)
            
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
        self._start_action_card.setEnabled(not loading)
        self._stop_action_card.setEnabled(not loading)
        
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
        self.premium_link_btn = PushButton()
        self.premium_link_btn.setText(tr_catalog("page.home.premium.more", language=self._ui_language, default="Подробнее"))
        self.premium_link_btn.setIcon(qta.icon("fa5s.arrow-right", color=_accent_hex()))
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
        try:
            title_label = getattr(getattr(self, "_actions_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(tr_catalog("page.home.section.quick_actions", language=self._ui_language, default="Быстрые действия"))
        except Exception:
            pass

        self._start_action_card.setTitle(tr_catalog("page.home.action.start.title", language=self._ui_language, default="Запустить Zapret"))
        self._start_action_card.setContent(
            tr_catalog(
                "page.home.action.start.description",
                language=self._ui_language,
                default="Запустить обход блокировок прямо с главного экрана.",
            )
        )
        self.start_btn.setText(tr_catalog("page.home.action.start", language=self._ui_language, default="Запустить"))

        self._stop_action_card.setTitle(tr_catalog("page.home.action.stop.title", language=self._ui_language, default="Остановить Zapret"))
        self._stop_action_card.setContent(
            tr_catalog(
                "page.home.action.stop.description",
                language=self._ui_language,
                default="Остановить уже запущенный процесс обхода блокировок.",
            )
        )
        self.stop_btn.setText(tr_catalog("page.home.action.stop", language=self._ui_language, default="Остановить"))

        self._test_action_card.setTitle(tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"))
        self._test_action_card.setContent(
            tr_catalog(
                "page.home.action.connection_test.description",
                language=self._ui_language,
                default="Открыть страницу диагностики сетевых соединений.",
            )
        )
        self.test_btn.setText(tr_catalog("page.home.action.connection_test", language=self._ui_language, default="Тест соединения"))

        self._folder_action_card.setTitle(tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"))
        self._folder_action_card.setContent(
            tr_catalog(
                "page.home.action.open_folder.description",
                language=self._ui_language,
                default="Открыть рабочую папку приложения и связанные файлы.",
            )
        )
        self.folder_btn.setText(tr_catalog("page.home.action.open_folder", language=self._ui_language, default="Открыть папку"))

        self._guide_action_card.setTitle(tr_catalog("page.home.action.how_to_use", language=self._ui_language, default="Как использовать"))
        self._guide_action_card.setContent(
            tr_catalog(
                "page.home.action.how_to_use.description",
                language=self._ui_language,
                default="Открыть руководство по использованию в браузере.",
            )
        )
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
