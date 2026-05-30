# autostart/ui/page.py
"""Страница настроек автозапуска"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
)
from ui.pages.base_page import BasePage
from ui.fluent_widgets import SettingsCard
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.theme import (
    get_cached_qta_pixmap,
    get_theme_tokens,
    get_themed_qta_icon,
    get_card_gradient_qss,
    get_card_disabled_gradient_qss,
    get_success_surface_gradient_qss,
    get_neutral_card_border_qss,
)
from ui.theme_semantic import get_semantic_palette
from app.state_store import AppUiState, MainWindowStateStore
from app.ui_texts import tr as tr_catalog
from autostart.ui.notifications import build_autostart_error_notification
from log.log import log
from qfluentwidgets import (
    FluentIcon,
    PushButton,
    SimpleCardWidget,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
)


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
            arrow_icon = get_themed_qta_icon("fa5s.check-circle", color=semantic.success)
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
            arrow_icon = get_themed_qta_icon("fa5s.chevron-right", color=tokens.fg_faint)
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
            arrow_icon = get_themed_qta_icon("fa5s.chevron-right", color=tokens.fg_faint)
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

        self._icon_label.setPixmap(get_cached_qta_pixmap(self._icon_name, color=icon_color, size=28))

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            log("ClickableModeCard: clicked!", "DEBUG")
            self.clicked.emit()
        super().mousePressEvent(event)


class AutostartPage(BasePage):
    """Страница настроек автозапуска."""

    def __init__(self, parent=None, *, autostart_feature, open_dpi_settings, notify, ui_state_store):
        super().__init__(
            "Автозапуск",
            "Настройка автоматического запуска Zapret",
            parent,
            title_key="page.autostart.title",
            subtitle_key="page.autostart.subtitle",
        )

        self._autostart = autostart_feature
        self._open_dpi_settings_callback = open_dpi_settings
        self._notify = notify
        self.strategy_name = None
        self._cleanup_in_progress = False

        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._autostart_action_runtime = OneShotWorkerRuntime()
        self._autostart_action_pending: list[tuple[str, bool | None, str | None]] = []
        self._mode_load_runtime = OneShotWorkerRuntime()
        self._mode_load_pending = False

        self._build_ui()
        self._apply_page_theme(force=True)
        self.bind_ui_state_store(ui_state_store)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

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
        self._autostart.set_autostart_runtime_state(bool(enabled))
        self._request_autostart_action(
            "save_state",
            enabled=bool(enabled),
            strategy_name=strategy_name,
        )
        self.update_status(enabled, strategy_name)

    def create_autostart_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        enabled=None,
        strategy_name=None,
    ):
        return self._autostart.create_autostart_action_worker(
            request_id,
            action=action,
            enabled=enabled,
            strategy_name=strategy_name,
            parent=self,
        )

    def _request_autostart_action(
        self,
        action: str,
        *,
        enabled=None,
        strategy_name=None,
    ) -> None:
        payload = (str(action or "").strip(), enabled, strategy_name)
        if self._autostart_action_runtime.is_running():
            self._autostart_action_pending.append(payload)
            return
        self._start_autostart_action_worker(payload)

    def _start_autostart_action_worker(self, payload: tuple[str, bool | None, str | None]) -> None:
        self._autostart_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_autostart_action_worker(
                request_id,
                action=payload[0],
                enabled=payload[1],
                strategy_name=payload[2],
            ),
            on_failed=self._on_autostart_action_failed,
            on_finished=self._on_autostart_action_worker_finished,
            bind_worker=self._bind_autostart_action_worker,
        )

    def _bind_autostart_action_worker(self, worker) -> None:
        worker.completed.connect(self._on_autostart_action_finished)
        worker.status.connect(self._on_autostart_action_status)

    def _on_autostart_action_status(self, request_id: int, _action: str, message: str) -> None:
        if not self._autostart_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if message:
            log(message, "INFO")

    def _on_autostart_action_finished(self, request_id: int, action: str, result, context) -> None:
        if not self._autostart_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        context = context if isinstance(context, dict) else {}
        if action == "save_state":
            enabled = bool(context.get("enabled"))
            strategy_name = context.get("strategy_name")
            self._autostart.set_autostart_runtime_state(enabled)
            self.update_status(enabled, strategy_name)
            return

        if action == "disable":
            self._autostart.set_autostart_runtime_state(False)
            self.update_status(False, self.strategy_name)
            removed_count = int(getattr(result, "removed_count", 0) or 0)
            if removed_count > 0:
                log(f"Автозапуск отключён, удалена задача: {removed_count}", "INFO")
            else:
                log("Автозапуск отключён", "INFO")
            return

        if action == "enable":
            if getattr(result, "restart_requested", False):
                log("Для включения автозапуска нужны права администратора", "WARNING")
                from PyQt6.QtWidgets import QApplication

                QApplication.quit()
                return
            if not getattr(result, "success", False):
                message = str(
                    getattr(result, "message", "")
                    or "Не удалось включить автозапуск. Windows не принял задачу Планировщика заданий."
                )
                log(message, "WARNING")
                self._show_autostart_error(message)
                return
            strategy_name = context.get("strategy_name") or self.strategy_name
            self._autostart.set_autostart_runtime_state(True)
            self.update_status(True, strategy_name)

    def _on_autostart_action_failed(self, request_id: int, _action: str, error: str, _context) -> None:
        if not self._autostart_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        message = f"Не удалось изменить автозапуск: {error}"
        log(message, "WARNING")
        self._show_autostart_error(message)

    def _on_autostart_action_worker_finished(self, _worker) -> None:
        if self._autostart_action_pending and not self._cleanup_in_progress:
            pending = self._autostart_action_pending.pop(0)
            self._start_autostart_action_worker(pending)

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        changed = set(changed_fields or ())
        strategy_name = state.current_strategy_summary or self.strategy_name
        if not changed or "autostart_enabled" in changed:
            self.update_status(state.autostart_enabled, strategy_name)
        elif "current_strategy_summary" in changed:
            self._set_current_strategy_label(strategy_name)

    def _build_ui(self):
        tokens = get_theme_tokens()

        self.add_section_title(text_key="page.autostart.section.status")

        status_card = SettingsCard()
        status_layout = QHBoxLayout()
        status_layout.setSpacing(14)

        self.status_icon = QLabel()
        self.status_icon.setPixmap(get_cached_qta_pixmap("fa5s.circle", color=tokens.fg_faint, size=20))
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

        self.disable_btn = PushButton(
            self._tr("page.autostart.button.disable", "Отключить"),
            icon=FluentIcon.CLOSE,
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
        tip_icon.setPixmap(get_cached_qta_pixmap("fa5s.lightbulb", color=get_semantic_palette().warning, size=18))
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
        self._request_mode_load()

    def create_autostart_mode_load_worker(self, request_id: int):
        return self._autostart.create_autostart_mode_load_worker(request_id, parent=self)

    def _request_mode_load(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._mode_load_runtime.is_running():
            self._mode_load_pending = True
            return
        self._start_mode_load_worker()

    def _start_mode_load_worker(self) -> None:
        self._mode_load_pending = False
        self._mode_load_runtime.start_qthread_worker(
            worker_factory=self.create_autostart_mode_load_worker,
            on_loaded=self._on_mode_loaded,
            on_failed=self._on_mode_load_failed,
            on_finished=self._on_mode_load_worker_finished,
        )

    def _on_mode_loaded(self, request_id: int, method: str) -> None:
        if not self._mode_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._apply_loaded_mode(method)

    def _on_mode_load_failed(self, request_id: int, error: str) -> None:
        if not self._mode_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка обновления режима: {error}", "WARNING")
        self.mode_label.setText(self._tr("page.autostart.mode.unknown", "Неизвестно"))

    def _on_mode_load_worker_finished(self, _worker) -> None:
        if self._mode_load_pending and not self._cleanup_in_progress:
            self._start_mode_load_worker()

    def _apply_loaded_mode(self, method: str) -> None:
        try:
            from settings.mode import (
                is_orchestra_launch_method,
                is_zapret1_launch_method,
                is_zapret2_launch_method,
            )

            method = str(method or "").strip()
            if is_zapret2_launch_method(method):
                mode_text = "Профили (Zapret 2)"
            elif is_zapret1_launch_method(method):
                mode_text = "Профили (Zapret 1)"
            elif is_orchestra_launch_method(method):
                mode_text = "Оркестр (автообучение)"
            else:
                mode_text = "Неизвестно"
            self.mode_label.setText(mode_text)
        except Exception as exc:
            log(f"Ошибка обновления режима: {exc}", "WARNING")
            self.mode_label.setText(self._tr("page.autostart.mode.unknown", "Неизвестно"))

    def _on_mode_card_clicked(self):
        log("AutostartPage: mode_card clicked, emitting navigate_to_dpi_settings", "DEBUG")
        self._open_dpi_settings_callback()

    def _update_arrow_color(self):
        if not hasattr(self, "mode_arrow"):
            return

        tokens = get_theme_tokens()
        self.mode_arrow.setPixmap(get_cached_qta_pixmap("fa5s.chevron-right", color=tokens.fg_faint, size=14))

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "_mode_icon_label"):
            self._mode_icon_label.setPixmap(get_cached_qta_pixmap("fa5s.cog", color=tokens.accent_hex, size=18))

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
                    get_cached_qta_pixmap("fa5s.check-circle", color=get_semantic_palette().success, size=20)
                )
            else:
                self.status_icon.setPixmap(get_cached_qta_pixmap("fa5s.circle", color=tokens.fg_faint, size=20))

        if hasattr(self, "gui_option") and hasattr(self.gui_option, "refresh_theme"):
            try:
                self.gui_option.refresh_theme()
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
                get_cached_qta_pixmap("fa5s.check-circle", color=get_semantic_palette().success, size=20)
            )
            self.disable_btn.setVisible(True)
        else:
            self.status_label.setText(self._tr("page.autostart.status.disabled.title", "Автозапуск отключён"))
            self.status_desc.setText(
                self._tr("page.autostart.status.disabled.desc", "Zapret не запускается автоматически")
            )
            tokens = get_theme_tokens()
            self.status_icon.setPixmap(get_cached_qta_pixmap("fa5s.circle", color=tokens.fg_faint, size=20))
            self.disable_btn.setVisible(False)

        self._set_current_strategy_label(strategy_text)

        self._update_options_state(enabled)
        self._update_mode()

    def _set_current_strategy_label(self, strategy_name: str | None) -> None:
        if strategy_name:
            self.strategy_name = strategy_name
        strategy_text = (
            strategy_name
            or self.current_strategy_label.text()
            or self._tr("page.autostart.strategy.not_selected", "Не выбрана")
        )
        try:
            if str(self.current_strategy_label.text() or "") == str(strategy_text or ""):
                return
        except Exception:
            pass
        self.current_strategy_label.setText(strategy_text)

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
        self._request_autostart_action("disable", enabled=False, strategy_name=self.strategy_name)

    def _on_gui_autostart(self):
        self._request_autostart_action("enable", enabled=True, strategy_name=self.strategy_name)

    def _show_autostart_error(self, message: str) -> None:
        notify = getattr(self, "_notify", None)
        if not callable(notify):
            return
        try:
            notify(build_autostart_error_notification(message))
        except Exception as exc:
            log(f"Не удалось показать уведомление автозапуска: {exc}", "DEBUG")

    def cleanup(self):
        self._cleanup_in_progress = True
        self._autostart_action_pending.clear()
        self._autostart_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="autostart_action_worker",
        )
        self._autostart_action_runtime.cancel()
        self._mode_load_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="autostart_mode_load_worker",
        )
        self._mode_load_runtime.cancel()
