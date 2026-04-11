# ui/pages/autostart_page.py
"""Страница настроек автозапуска"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
)
import qtawesome as qta

from autostart.page_controller import AutostartPageController
from .base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import (
    get_theme_tokens,
    get_card_gradient_qss,
    get_card_disabled_gradient_qss,
    get_success_surface_gradient_qss,
    get_neutral_card_border_qss,
)
from ui.theme_semantic import get_semantic_palette
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from log import log

try:
    from qfluentwidgets import (
        SimpleCardWidget,
        StrongBodyLabel,
        BodyLabel,
        CaptionLabel,
    )
    _HAS_FLUENT = True
except ImportError:
    SimpleCardWidget = QWidget  # type: ignore[misc,assignment]
    StrongBodyLabel = QLabel    # type: ignore[misc,assignment]
    BodyLabel = QLabel          # type: ignore[misc,assignment]
    CaptionLabel = QLabel       # type: ignore[misc,assignment]
    _HAS_FLUENT = False

class AutostartOptionCard(SimpleCardWidget):
    """Карточка опции автозапуска"""

    clicked = pyqtSignal()

    def __init__(self, icon_name: str, title: str, description: str,
                 accent: bool = False, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = accent
        self._disabled = False
        self._is_active = False
        self._icon_name = icon_name
        self._tokens = get_theme_tokens()
        self._current_qss = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # Иконка
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(36, 36)
        layout.addWidget(self._icon_label)

        # Текст
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        self._title_label = StrongBodyLabel(title)
        title_layout.addWidget(self._title_label)

        title_layout.addStretch()
        text_layout.addLayout(title_layout)

        self._desc_label = CaptionLabel(description)
        self._desc_label.setWordWrap(True)
        text_layout.addWidget(self._desc_label)

        layout.addLayout(text_layout, 1)

        # Стрелка
        self._arrow = QLabel()
        layout.addWidget(self._arrow)

        self._apply_visuals()

    def set_texts(self, title: str, description: str) -> None:
        self._title_label.setText(title)
        self._desc_label.setText(description)

    def refresh_theme(self) -> None:
        self._tokens = get_theme_tokens()
        self._apply_visuals()

    def _apply_visuals(self) -> None:
        tokens = self._tokens or get_theme_tokens("Темная синяя")
        semantic = get_semantic_palette()

        if self._is_active:
            icon_color = semantic.success
            arrow_icon = qta.icon("fa5s.check-circle", color=semantic.success)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            card_bg = get_success_surface_gradient_qss(tokens.theme_name)
            card_border = semantic.success
            card_hover_bg = card_bg
            card_hover_border = card_border
            title_color = tokens.fg
            desc_color = tokens.fg_muted
            self.setEnabled(True)
        elif self._disabled:
            icon_color = tokens.fg_faint
            arrow_icon = qta.icon("fa5s.chevron-right", color=tokens.fg_faint)
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            card_bg = get_card_disabled_gradient_qss(tokens.theme_name)
            card_border = get_neutral_card_border_qss(tokens.theme_name, disabled=True)
            card_hover_bg = card_bg
            card_hover_border = card_border
            title_color = tokens.fg_faint
            desc_color = tokens.fg_faint
            # Disabled cards must not react to hover/click at all.
            self.setEnabled(False)
        else:
            icon_color = tokens.accent_hex if self._accent else tokens.fg
            arrow_icon = qta.icon("fa5s.chevron-right", color=tokens.fg_faint)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            card_bg = get_card_gradient_qss(tokens.theme_name)
            card_border = get_neutral_card_border_qss(tokens.theme_name)
            card_hover_bg = get_card_gradient_qss(tokens.theme_name, hover=True)
            card_hover_border = get_neutral_card_border_qss(tokens.theme_name, hover=True)
            title_color = tokens.fg
            desc_color = tokens.fg_muted
            self.setEnabled(True)

        self._title_label.setStyleSheet(f"color: {title_color};")
        self._desc_label.setStyleSheet(f"color: {desc_color};")

        card_qss = f"""
            AutostartOptionCard {{
                background: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
            AutostartOptionCard:hover {{
                background: {card_hover_bg};
                border: 1px solid {card_hover_border};
            }}
        """
        if card_qss != self._current_qss:
            self._current_qss = card_qss
            self.setStyleSheet(card_qss)

        self._icon_label.setPixmap(qta.icon(self._icon_name, color=icon_color).pixmap(28, 28))

        self._arrow.setPixmap(arrow_icon.pixmap(18 if self._is_active else 16, 18 if self._is_active else 16))

    def set_disabled(self, disabled: bool, is_active: bool = False):
        """
        Устанавливает состояние карточки.

        Args:
            disabled: True - карточка заблокирована (не кликабельна)
            is_active: True - карточка активна (выделена зелёным, но не кликабельна)
        """
        self._disabled = disabled
        self._is_active = is_active

        self._apply_visuals()
        self.update()  # Принудительное обновление виджета

    def enterEvent(self, event):
        if not self._disabled and not self._is_active:
            pass  # SimpleCardWidget handles its own hover background
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        # Блокируем любые клики по неактивным/выбранным карточкам.
        if self._disabled or self._is_active or not self.isEnabled():
            event.accept()
            return

        self.clicked.emit()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ClickableModeCard(SimpleCardWidget):
    """Кликабельная карточка режима"""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def refresh_theme(self) -> None:
        # SimpleCardWidget handles its own theming; nothing extra needed.
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            log("ClickableModeCard: clicked!", "DEBUG")
            self.clicked.emit()
        super().mousePressEvent(event)


class AutostartPage(BasePage):
    """Страница настроек автозапуска."""

    autostart_enabled = pyqtSignal()
    autostart_disabled = pyqtSignal()
    navigate_to_dpi_settings = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Автозапуск",
            "Настройка автоматического запуска Zapret",
            parent,
            title_key="page.autostart.title",
            subtitle_key="page.autostart.subtitle",
        )

        self._app_instance = None
        self.strategy_name = None
        self._detector_worker = None
        self._detection_pending = False
        self._current_mode_method = ""
        self._runtime_initialized = False

        self._ui_state_store = None
        self._ui_state_unsubscribe = None

        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _run_runtime_init_once(self) -> None:
        if not AutostartPageController.should_schedule_initial_detection(
            runtime_initialized=self._runtime_initialized,
        ):
            return
        self._runtime_initialized = True
        self._schedule_autostart_detection_when_ready(50)

    def _schedule_autostart_detection_when_ready(self, delay_ms: int) -> None:
        self.run_when_page_ready(
            lambda delay=delay_ms: QTimer.singleShot(delay, self._start_autostart_detection)
        )

    def _start_autostart_detection(self):
        if not self.isVisible():
            self.run_when_page_ready(self._start_autostart_detection)
            return

        if not AutostartPageController.should_start_detection(
            detection_pending=self._detection_pending,
            worker_running=bool(self._detector_worker is not None and self._detector_worker.isRunning()),
        ):
            return

        self._detection_pending = True
        self._detector_worker = AutostartPageController.create_detector_worker()
        self._detector_worker.finished.connect(self._on_autostart_detected)
        self._detector_worker.start()

    def _on_autostart_detected(self, enabled: bool):
        self._detection_pending = False
        enabled = bool(enabled)
        log(f"Detected canonical autostart: enabled={enabled}", "DEBUG")
        self._push_autostart_state(enabled, self.strategy_name)

    @property
    def app_instance(self):
        if self._app_instance is None:
            self._auto_init()
        return self._app_instance

    @app_instance.setter
    def app_instance(self, value):
        self._app_instance = value

    def _auto_init(self):
        try:
            app_instance, strategy_name, strategy_text = AutostartPageController.resolve_app_init(
                self.parent(),
                strategy_name=self.strategy_name,
                strategy_not_selected_text=self._tr("page.autostart.strategy.not_selected", "Не выбрана"),
            )
            self._app_instance = app_instance
            self.strategy_name = strategy_name
            self.current_strategy_label.setText(strategy_text)
        except Exception as exc:
            log(f"AutostartPage._auto_init ошибка: {exc}", "WARNING")

    def set_app_instance(self, app):
        self._app_instance = app

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
            fields={"autostart_enabled", "current_strategy_summary"},
            emit_initial=True,
        )

    def _push_autostart_state(
        self,
        enabled: bool,
        strategy_name: str | None = None,
    ) -> None:
        app_runtime_state = getattr(self.window(), "app_runtime_state", None)
        if self._ui_state_store is not None:
            if strategy_name:
                self._ui_state_store.set_current_strategy_summary(strategy_name)
            if app_runtime_state is not None:
                app_runtime_state.set_autostart(enabled)
            else:
                self._ui_state_store.set_autostart(enabled)
            return
        self.update_status(enabled, strategy_name)

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        strategy_name = state.current_strategy_summary or self.strategy_name
        self.update_status(state.autostart_enabled, strategy_name)

    def set_strategy_name(self, name: str):
        self.strategy_name = name
        if hasattr(self, "current_strategy_label"):
            self.current_strategy_label.setText(
                name or self._tr("page.autostart.strategy.not_selected", "Не выбрана")
            )

    def _build_ui(self):
        tokens = get_theme_tokens()

        self.add_section_title(text_key="page.autostart.section.status")

        status_card = SettingsCard()
        status_layout = QHBoxLayout()
        status_layout.setSpacing(14)

        self.status_icon = QLabel()
        self.status_icon.setPixmap(qta.icon("fa5s.circle", color=tokens.fg_faint).pixmap(20, 20))
        self.status_icon.setFixedSize(24, 24)
        status_layout.addWidget(self.status_icon)

        status_text_layout = QVBoxLayout()
        status_text_layout.setSpacing(4)

        self.status_label = StrongBodyLabel(
            self._tr("page.autostart.status.disabled.title", "Автозапуск отключён")
        )
        status_text_layout.addWidget(self.status_label)

        self.status_desc = CaptionLabel(
            self._tr("page.autostart.status.disabled.desc", "Zapret не запускается автоматически")
        )
        status_text_layout.addWidget(self.status_desc)

        status_layout.addLayout(status_text_layout, 1)

        self.disable_btn = ActionButton(
            self._tr("page.autostart.button.disable", "Отключить"),
            "fa5s.times",
        )
        self.disable_btn.setFixedHeight(36)
        self.disable_btn.setVisible(False)
        self.disable_btn.clicked.connect(self._on_disable_clicked)
        status_layout.addWidget(self.disable_btn)

        status_card.add_layout(status_layout)
        self.add_widget(status_card)

        self.add_spacing(20)
        self.add_section_title(text_key="page.autostart.section.mode")

        self.mode_card = ClickableModeCard()
        self.mode_card.clicked.connect(self._on_mode_card_clicked)

        mode_card_layout = QVBoxLayout(self.mode_card)
        mode_card_layout.setContentsMargins(16, 14, 16, 14)
        mode_card_layout.setSpacing(0)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)

        self._mode_icon_label = QLabel()
        self._mode_icon_label.setFixedSize(22, 22)
        self._mode_icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self._mode_icon_label)

        self._mode_text_label = CaptionLabel(
            self._tr("page.autostart.mode.current_label", "Текущий режим:")
        )
        self._mode_text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self._mode_text_label)

        self.mode_label = BodyLabel(self._tr("page.autostart.mode.loading", "Загрузка..."))
        self.mode_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self.mode_label)

        mode_layout.addSpacing(20)

        self._strategy_text_label = CaptionLabel(
            self._tr("page.autostart.mode.strategy_label", "Стратегия:")
        )
        self._strategy_text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self._strategy_text_label)

        self.current_strategy_label = BodyLabel(
            self._tr("page.autostart.strategy.not_selected", "Не выбрана")
        )
        self.current_strategy_label.setWordWrap(True)
        self.current_strategy_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self.current_strategy_label, 1)

        self.mode_arrow = QLabel()
        self.mode_arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mode_layout.addWidget(self.mode_arrow)

        mode_card_layout.addLayout(mode_layout)
        self.add_widget(self.mode_card)

        self.add_spacing(20)
        self.add_section_title(text_key="page.autostart.section.select_type")

        self.gui_option = AutostartOptionCard(
            "fa5s.desktop",
            self._tr("page.autostart.option.gui.title", "Автозапуск программы Zapret"),
            self._tr(
                "page.autostart.option.gui.desc",
                "Запускает главное окно программы при входе в Windows. "
                "Приложение стартует в трее и уже оттуда применяет текущие настройки.",
            ),
            accent=True,
        )
        self.gui_option.clicked.connect(self._on_gui_autostart)
        self.add_widget(self.gui_option)

        self.add_spacing(20)
        self.add_section_title(text_key="page.autostart.section.info")

        info_card = SettingsCard()
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)

        tip_layout = QHBoxLayout()
        tip_layout.setSpacing(10)

        tip_icon = QLabel()
        tip_icon.setPixmap(qta.icon("fa5s.lightbulb", color=get_semantic_palette().warning).pixmap(18, 18))
        tip_icon.setFixedSize(22, 22)
        tip_layout.addWidget(tip_icon)

        self._tip_text_label = CaptionLabel(
            self._tr(
                "page.autostart.tip.recommendation",
                "Используется один тип автозапуска: запуск самого ZapretGUI в трей через Планировщик заданий Windows.",
            )
        )
        self._tip_text_label.setWordWrap(True)
        tip_layout.addWidget(self._tip_text_label, 1)

        info_layout.addLayout(tip_layout)
        info_card.add_layout(info_layout)
        self.add_widget(info_card)

        self._update_mode()
        self._apply_page_theme()

    def _update_mode(self):
        try:
            from strategy_menu import get_strategy_launch_method

            method = get_strategy_launch_method()
            self._current_mode_method = str(method or "").strip()
            if self._current_mode_method == "direct_zapret2":
                mode_text = "Прямой запуск (Zapret 2)"
            elif self._current_mode_method == "orchestra":
                mode_text = "Оркестр (автообучение)"
            elif self._current_mode_method:
                mode_text = "Классический (BAT файлы)"
            else:
                mode_text = "Неизвестно"
            self.mode_label.setText(mode_text)
        except Exception as exc:
            log(f"Ошибка обновления режима: {exc}", "WARNING")
            self._current_mode_method = ""
            self.mode_label.setText(self._tr("page.autostart.mode.unknown", "Неизвестно"))

    def _on_mode_card_clicked(self):
        log("AutostartPage: mode_card clicked, emitting navigate_to_dpi_settings", "DEBUG")
        self.navigate_to_dpi_settings.emit()

    def _update_arrow_color(self):
        if not hasattr(self, "mode_arrow"):
            return

        tokens = get_theme_tokens()
        self.mode_arrow.setPixmap(qta.icon("fa5s.chevron-right", color=tokens.fg_faint).pixmap(14, 14))

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "_mode_icon_label"):
            self._mode_icon_label.setPixmap(qta.icon("fa5s.cog", color=tokens.accent_hex).pixmap(18, 18))

        if hasattr(self, "mode_label"):
            self.mode_label.setStyleSheet(
                f"color: {tokens.accent_hex}; font-size: 13px; font-weight: 600;"
            )

        if hasattr(self, "current_strategy_label"):
            self.current_strategy_label.setStyleSheet(
                f"color: {tokens.fg}; font-size: 13px; font-weight: 500;"
            )

        self._update_arrow_color()

        if hasattr(self, "status_icon"):
            if self._current_autostart_state():
                self.status_icon.setPixmap(
                    qta.icon("fa5s.check-circle", color=get_semantic_palette().success).pixmap(20, 20)
                )
            else:
                self.status_icon.setPixmap(qta.icon("fa5s.circle", color=tokens.fg_faint).pixmap(20, 20))

        if hasattr(self, "gui_option") and hasattr(self.gui_option, "refresh_theme"):
            try:
                self.gui_option.refresh_theme()
            except Exception:
                pass

        if hasattr(self, "mode_card") and hasattr(self.mode_card, "refresh_theme"):
            try:
                self.mode_card.refresh_theme()
            except Exception:
                pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.disable_btn.setText(self._tr("page.autostart.button.disable", "Отключить"))
        self._mode_text_label.setText(self._tr("page.autostart.mode.current_label", "Текущий режим:"))
        self._strategy_text_label.setText(self._tr("page.autostart.mode.strategy_label", "Стратегия:"))

        self.gui_option.set_texts(
            self._tr("page.autostart.option.gui.title", "Автозапуск программы Zapret"),
            self._tr(
                "page.autostart.option.gui.desc",
                "Запускает главное окно программы при входе в Windows. "
                "Приложение стартует в трее и уже оттуда применяет текущие настройки.",
            ),
        )
        self._tip_text_label.setText(
            self._tr(
                "page.autostart.tip.recommendation",
                "Используется один тип автозапуска: запуск самого ZapretGUI в трей через Планировщик заданий Windows.",
            )
        )

        self.update_status(self._current_autostart_state(), self.strategy_name)

    def update_status(self, enabled: bool, strategy_name: str = None):
        enabled = bool(enabled)
        if strategy_name:
            self.strategy_name = strategy_name
        strategy_text = (
            strategy_name
            or self.current_strategy_label.text()
            or self._tr("page.autostart.strategy.not_selected", "Не выбрана")
        )

        if enabled:
            self.status_label.setText(self._tr("page.autostart.status.enabled.title", "Автозапуск включён"))
            self.status_desc.setText(
                self._tr(
                    "page.autostart.status.enabled.desc.base",
                    "Zapret запускается автоматически при входе в Windows и открывается в трее",
                )
            )
            self.status_icon.setPixmap(
                qta.icon("fa5s.check-circle", color=get_semantic_palette().success).pixmap(20, 20)
            )
            self.disable_btn.setVisible(True)
        else:
            self.status_label.setText(self._tr("page.autostart.status.disabled.title", "Автозапуск отключён"))
            self.status_desc.setText(
                self._tr("page.autostart.status.disabled.desc", "Zapret не запускается автоматически")
            )
            tokens = get_theme_tokens()
            self.status_icon.setPixmap(qta.icon("fa5s.circle", color=tokens.fg_faint).pixmap(20, 20))
            self.disable_btn.setVisible(False)

        self.current_strategy_label.setText(strategy_text)

        self._update_options_state(enabled)
        self._update_mode()

    def _current_autostart_state(self) -> bool:
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                return bool(snapshot.autostart_enabled)
            except Exception:
                pass

        return bool(self.disable_btn.isVisible()) if hasattr(self, "disable_btn") else False

    def _update_options_state(self, autostart_enabled: bool):
        log(f"_update_options_state: enabled={autostart_enabled}", "DEBUG")
        self.gui_option.set_disabled(bool(autostart_enabled), is_active=bool(autostart_enabled))

    def _on_disable_clicked(self):
        try:
            removed_count = AutostartPageController.disable_autostart()
            self._push_autostart_state(False)
            self.autostart_disabled.emit()
            if removed_count > 0:
                log(f"Автозапуск отключён, удалено механизмов: {removed_count}", "INFO")
            else:
                log("Автозапуск отключён", "INFO")
        except Exception as exc:
            log(f"Ошибка отключения автозапуска: {exc}", "ERROR")

    def _on_gui_autostart(self):
        try:
            ok = AutostartPageController.setup_gui_autostart(status_cb=lambda msg: log(msg, "INFO"))
            if not ok:
                log("Не удалось настроить автозапуск GUI", "ERROR")
                return
            self._push_autostart_state(True, self.strategy_name)
            self.autostart_enabled.emit()
        except Exception as exc:
            log(f"Ошибка автозапуска GUI: {exc}", "ERROR")
