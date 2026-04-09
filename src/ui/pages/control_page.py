# ui/pages/control_page.py
"""Страница управления - запуск/остановка DPI"""

import os

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
import qtawesome as qta

try:
    from qfluentwidgets import (
        SubtitleLabel, BodyLabel, StrongBodyLabel, CaptionLabel,
        IndeterminateProgressBar, MessageBox, InfoBar,
        SettingCardGroup, PushSettingCard,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    MessageBox = None
    InfoBar = None
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    _HAS_FLUENT_LABELS = False

from .base_page import BasePage
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    ResetActionButton,
    StatusIndicator,
    enable_setting_card_group_auto_height,
    set_tooltip,
)
from ui.compat_widgets import PulsingDot
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.window_action_controller import (
    open_connection_test,
    open_folder,
    start_dpi,
    stop_and_exit,
    stop_dpi,
)

try:
    from qfluentwidgets import themeColor, isDarkTheme
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False


from ui.control_page_controller import ControlPageController


class BigActionButton(PrimaryActionButton):
    """Большая акцентная кнопка действия (запуск)"""

    def __init__(self, text: str, icon_name: str = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)

    def _update_style(self):
        """No-op: qfluentwidgets handles styling."""
        pass


class StopButton(ActionButton):
    """Кнопка остановки (нейтральная, не акцентная)"""

    def __init__(self, text: str, icon_name: str = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, accent=False, parent=parent)


class ControlPage(BasePage):
    """Страница управления DPI"""

    def __init__(self, parent=None):
        super().__init__(
            "Управление",
            "Запуск и остановка Zapret, быстрые настройки программы.",
            parent,
            title_key="page.control.title",
            subtitle_key="page.control.subtitle",
        )
        self._controller = ControlPageController()
        self._program_settings_synced = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._last_known_dpi_running = False

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._update_stop_winws_button_text()

    def _start_dpi(self) -> None:
        start_dpi(self)

    def _stop_dpi(self) -> None:
        stop_dpi(self)

    def _stop_and_exit(self) -> None:
        stop_and_exit(self)

    def _open_connection_test(self) -> None:
        open_connection_test(self)

    def _open_folder(self) -> None:
        open_folder(self)

    def _build_ui(self):
        # Статус работы
        self.add_section_title(text_key="page.control.section.status")
        
        status_card = SettingsCard()
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)
        
        # Пульсирующая точка статуса
        self.status_dot = PulsingDot()
        status_layout.addWidget(self.status_dot)
        
        # Текст статуса
        status_text_layout = QVBoxLayout()
        status_text_layout.setSpacing(2)
        
        if _HAS_FLUENT_LABELS:
            self.status_title = SubtitleLabel(
                tr_catalog("page.control.status.checking", language=self._ui_language, default="Проверка...")
            )
        else:
            self.status_title = QLabel(
                tr_catalog("page.control.status.checking", language=self._ui_language, default="Проверка...")
            )
            self.status_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        status_text_layout.addWidget(self.status_title)
        
        if _HAS_FLUENT_LABELS:
            self.status_desc = CaptionLabel(
                tr_catalog("page.control.status.detecting", language=self._ui_language, default="Определение состояния процесса")
            )
        else:
            self.status_desc = QLabel(
                tr_catalog("page.control.status.detecting", language=self._ui_language, default="Определение состояния процесса")
            )
            self.status_desc.setStyleSheet("font-size: 12px;")
        status_text_layout.addWidget(self.status_desc)
        
        status_layout.addLayout(status_text_layout, 1)
        status_card.add_layout(status_layout)
        self.add_widget(status_card)
        
        self.add_spacing(16)
        
        # Управление
        self.add_section_title(text_key="page.control.section.management")
        
        control_card = SettingsCard()

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.start_btn = BigActionButton(
            tr_catalog("page.control.button.start", language=self._ui_language, default="Запустить Zapret"),
            "fa5s.play",
            accent=True,
        )
        self.start_btn.clicked.connect(self._start_dpi)
        buttons_layout.addWidget(self.start_btn)
        
        # Кнопка остановки только winws.exe / winws2.exe (в зависимости от режима)
        self.stop_winws_btn = StopButton(
            tr_catalog("page.control.button.stop_only_winws", language=self._ui_language, default="Остановить только winws.exe"),
            "fa5s.stop",
        )
        self.stop_winws_btn.clicked.connect(self._stop_dpi)
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)
        
        # Кнопка полного выхода (остановка + закрытие программы)
        self.stop_and_exit_btn = StopButton(
            tr_catalog("page.control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу"),
            "fa5s.power-off",
        )
        self.stop_and_exit_btn.clicked.connect(self._stop_and_exit)
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)
        
        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)

        # Индикатор загрузки держим под кнопками, чтобы при показе
        # ряд действий не прыгал вниз.
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        control_card.add_widget(self.progress_bar)

        # Метка статуса загрузки
        if _HAS_FLUENT_LABELS:
            self.loading_label = CaptionLabel("")
        else:
            self.loading_label = QLabel("")
            self.loading_label.setStyleSheet("font-size: 12px;")
        self.loading_label.setVisible(False)
        control_card.add_widget(self.loading_label)
        
        self.add_widget(control_card)
        
        self.add_spacing(16)

        # Текущая стратегия
        self.add_section_title(text_key="page.control.section.current_strategy")

        strategy_card = SettingsCard()

        strategy_layout = QHBoxLayout()
        strategy_layout.setSpacing(12)

        self.strategy_icon = QLabel()
        try:
            from ui.fluent_icons import fluent_pixmap
            self.strategy_icon.setPixmap(fluent_pixmap('fa5s.cog', 20))
        except Exception:
            accent = themeColor().name() if HAS_FLUENT else "#60cdff"
            self.strategy_icon.setPixmap(qta.icon('fa5s.cog', color=accent).pixmap(20, 20))
        self.strategy_icon.setFixedSize(24, 24)
        strategy_layout.addWidget(self.strategy_icon)

        strategy_text_layout = QVBoxLayout()
        strategy_text_layout.setSpacing(2)

        if _HAS_FLUENT_LABELS:
            self.strategy_label = StrongBodyLabel(
                tr_catalog("page.control.strategy.not_selected", language=self._ui_language, default="Не выбрана")
            )
        else:
            self.strategy_label = QLabel(
                tr_catalog("page.control.strategy.not_selected", language=self._ui_language, default="Не выбрана")
            )
            self.strategy_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        self.strategy_label.setWordWrap(True)
        self.strategy_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        strategy_text_layout.addWidget(self.strategy_label)

        if _HAS_FLUENT_LABELS:
            self.strategy_desc = CaptionLabel(
                tr_catalog("page.control.strategy.select_hint", language=self._ui_language, default="Выберите стратегию в разделе «Стратегии»")
            )
        else:
            self.strategy_desc = QLabel(
                tr_catalog("page.control.strategy.select_hint", language=self._ui_language, default="Выберите стратегию в разделе «Стратегии»")
            )
            self.strategy_desc.setStyleSheet("font-size: 11px;")
        strategy_text_layout.addWidget(self.strategy_desc)

        strategy_layout.addLayout(strategy_text_layout, 1)
        strategy_card.add_layout(strategy_layout)

        self.add_widget(strategy_card)

        self.add_spacing(16)

        # Настройки программы (бывшие пункты Alt-меню "Настройки")
        program_settings_title = tr_catalog(
            "page.control.section.program_settings",
            language=self._ui_language,
            default="Настройки программы",
        )
        if SettingCardGroup is not None and PushSettingCard is not None and _HAS_FLUENT_LABELS:
            self.program_settings_section_label = None
            program_settings_card = SettingCardGroup(program_settings_title, self.content)
        else:
            self.program_settings_section_label = self.add_section_title(
                text_key="page.control.section.program_settings"
            )
            program_settings_card = SettingsCard()
        self.program_settings_card = program_settings_card

        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None  # type: ignore[assignment]

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления")

        self.auto_dpi_toggle = Win11ToggleRow(
            "fa5s.bolt",
            tr_catalog("page.control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog("page.control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы"),
        )
        self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)

        self.defender_toggle = Win11ToggleRow(
            "fa5s.shield-alt",
            tr_catalog("page.control.setting.defender.title", language=self._ui_language, default="Отключить Windows Defender"),
            tr_catalog("page.control.setting.defender.desc", language=self._ui_language, default="Требуются права администратора"),
        )
        self.defender_toggle.toggled.connect(self._on_defender_toggled)

        self.max_block_toggle = Win11ToggleRow(
            "fa5s.ban",
            tr_catalog("page.control.setting.max_block.title", language=self._ui_language, default="Блокировать установку MAX"),
            tr_catalog("page.control.setting.max_block.desc", language=self._ui_language, default="Блокирует запуск/установку MAX и домены в hosts"),
        )
        self.max_block_toggle.toggled.connect(self._on_max_blocker_toggled)

        add_setting_card = getattr(program_settings_card, "addSettingCard", None)
        if callable(add_setting_card):
            add_setting_card(self.auto_dpi_toggle)
            add_setting_card(self.defender_toggle)
            add_setting_card(self.max_block_toggle)
        else:
            program_settings_card.add_widget(self.auto_dpi_toggle)
            program_settings_card.add_widget(self.defender_toggle)
            program_settings_card.add_widget(self.max_block_toggle)

        self.reset_program_card = None
        self.reset_program_btn = None
        self._reset_program_desc_label = None
        if callable(add_setting_card) and PushSettingCard is not None:
            self.reset_program_card = PushSettingCard(
                tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить"),
                qta.icon("fa5s.undo", color="#ff9800"),
                tr_catalog("page.control.setting.reset.title", language=self._ui_language, default="Сбросить программу"),
                tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)"),
            )
            self.reset_program_card.clicked.connect(self._confirm_reset_program_clicked)
            add_setting_card(self.reset_program_card)
        else:
            self.reset_program_btn = ResetActionButton(
                tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить"),
                confirm_text=tr_catalog("page.control.button.reset_confirm", language=self._ui_language, default="Сбросить?"),
            )
            self.reset_program_btn.setProperty("noDrag", True)
            self.reset_program_btn.reset_confirmed.connect(self._on_reset_program_clicked)
            reset_card = SettingsCard(
                tr_catalog("page.control.setting.reset.title", language=self._ui_language, default="Сбросить программу")
            )
            reset_desc_label = CaptionLabel(
                tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
            ) if _HAS_FLUENT_LABELS else QLabel(
                tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
            )
            reset_desc_label.setWordWrap(True)
            self._reset_program_desc_label = reset_desc_label
            reset_card.add_widget(reset_desc_label)
            reset_layout = QHBoxLayout()
            reset_layout.setSpacing(8)
            reset_layout.addWidget(self.reset_program_btn)
            reset_layout.addStretch()
            reset_card.add_layout(reset_layout)
            self.reset_program_card = reset_card
            self.add_widget(program_settings_card)
            self.add_widget(reset_card)
            program_settings_card = None

        if program_settings_card is not None:
            self.add_widget(program_settings_card)
        enable_setting_card_group_auto_height(self.program_settings_card)

        self.add_spacing(16)
        
        # Дополнительные действия
        self.test_btn = ActionButton(
            tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"),
            "fa5s.wifi",
        )
        self.test_btn.clicked.connect(self._open_connection_test)
        self.folder_btn = ActionButton(
            tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"),
            "fa5s.folder-open",
        )
        self.folder_btn.clicked.connect(self._open_folder)

        self.additional_section_label = None
        self.extra_actions_group = SettingCardGroup(
            tr_catalog("page.control.section.additional", language=self._ui_language, default="Дополнительные действия"),
            self.content,
        )
        self.test_action_card = PushSettingCard(
            tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"),
            qta.icon("fa5s.wifi", color="#60cdff"),
            tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"),
            tr_catalog("page.control.section.additional.test_desc", language=self._ui_language, default="Проверить сетевое подключение и доступность маршрута"),
        )
        self.test_action_card.clicked.connect(self._open_connection_test)

        self.folder_action_card = PushSettingCard(
            tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"),
            qta.icon("fa5s.folder-open", color="#ffc107"),
            tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"),
            tr_catalog("page.control.section.additional.folder_desc", language=self._ui_language, default="Быстро перейти к рабочей папке программы"),
        )
        self.folder_action_card.clicked.connect(self._open_folder)

        self.extra_actions_group.addSettingCards([self.test_action_card, self.folder_action_card])
        enable_setting_card_group_auto_height(self.extra_actions_group)
        self.add_widget(self.extra_actions_group)

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        # Обновляем состояние тогглов при каждом показе страницы
        try:
            self._sync_program_settings()
        except Exception:
            pass

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        """Устанавливает состояние toggle-карточки или переключателя без лишних сигналов."""
        try:
            toggle.setChecked(bool(checked), block_signals=True)
            return
        except TypeError:
            pass
        except Exception:
            pass

        try:
            toggle.blockSignals(True)
        except Exception:
            pass

        try:
            if hasattr(toggle, "setChecked"):
                toggle.setChecked(bool(checked))
        except Exception:
            pass

        # У кастомного fallback-переключателя есть анимируемый круг, который нужно
        # принудительно переставить при немом обновлении состояния.
        try:
            toggle._circle_position = (toggle.width() - 18) if checked else 4.0  # type: ignore[attr-defined]
            toggle.update()
        except Exception:
            pass

        try:
            toggle.blockSignals(False)
        except Exception:
            pass

    def _confirm_reset_program_clicked(self) -> None:
        title = tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить")
        confirm_text = tr_catalog(
            "page.control.button.reset_confirm",
            language=self._ui_language,
            default="Сбросить?",
        )
        if MessageBox is not None:
            try:
                box = MessageBox(title, confirm_text, self.window())
                if not box.exec():
                    return
            except Exception:
                pass
        self._on_reset_program_clicked()

    def _sync_program_settings(self) -> None:
        """Синхронизирует UI с текущими настройками (реестр/система)."""
        plan = self._controller.load_program_settings()
        self._set_toggle_checked(self.auto_dpi_toggle, plan.auto_dpi_enabled)
        self._set_toggle_checked(self.defender_toggle, plan.defender_disabled)
        self._set_toggle_checked(self.max_block_toggle, plan.max_blocked)

    def _set_status(self, msg: str) -> None:
        try:
            if hasattr(self.parent_app, "set_status"):
                self.parent_app.set_status(msg)
        except Exception:
            pass

    def _show_action_result_plan(self, plan, toggle=None) -> None:
        if plan.revert_checked is not None and toggle is not None:
            self._set_toggle_checked(toggle, plan.revert_checked)

        if plan.final_status:
            self._set_status(plan.final_status)

        if plan.level == "success":
            InfoBar.success(title=plan.title, content=plan.content, parent=self.window())
        elif plan.level == "warning":
            InfoBar.warning(title=plan.title, content=plan.content, parent=self.window())
        else:
            InfoBar.error(title=plan.title, content=plan.content, parent=self.window())

    def _run_confirmation_dialog(self, dialog_plan, toggle=None) -> bool:
        box = MessageBox(dialog_plan.title, dialog_plan.content, self.window())
        if box.exec():
            return True
        if dialog_plan.revert_checked is not None and toggle is not None:
            self._set_toggle_checked(toggle, dialog_plan.revert_checked)
        return False

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = self._controller.save_auto_dpi(enabled)
            self._set_status(plan.message)
            InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_defender_toggled(self, disable: bool) -> None:
        start_plan = self._controller.build_defender_toggle_start_plan(
            disable=disable,
            language=self._ui_language,
        )
        if start_plan.blocked:
            InfoBar.error(
                title=start_plan.blocked_title,
                content=start_plan.blocked_content,
                parent=self.window(),
            )
            if start_plan.blocked_revert_checked is not None:
                self._set_toggle_checked(self.defender_toggle, start_plan.blocked_revert_checked)
            return

        try:
            for dialog_plan in start_plan.confirmations:
                if not self._run_confirmation_dialog(dialog_plan, self.defender_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = self._controller.run_defender_toggle(
                disable=disable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.defender_toggle)
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        start_plan = self._controller.build_max_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        try:
            for dialog_plan in start_plan.confirmations:
                if not self._run_confirmation_dialog(dialog_plan, self.max_block_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = self._controller.run_max_block_toggle(
                enable=enable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.max_block_toggle)
        finally:
            self._sync_program_settings()

    def _on_reset_program_clicked(self) -> None:
        try:
            ok, message = self._controller.reset_startup_cache()
            if ok:
                self._set_status(message)
            else:
                InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _update_stop_winws_button_text(self):
        """Обновляет подпись кнопки остановки (winws.exe vs winws2.exe) по текущему режиму."""
        plan = self._controller.build_stop_button_plan(language=self._ui_language)
        self.stop_winws_btn.setText(plan.text)
        
    def set_loading(self, loading: bool, text: str = ""):
        """Показывает/скрывает индикатор загрузки и блокирует кнопки"""
        self.progress_bar.setVisible(loading)
        if _HAS_FLUENT_LABELS:
            if loading:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()
        self.loading_label.setVisible(loading and bool(text))
        self.loading_label.setText(text)
        
        # Блокируем/разблокируем кнопки
        self.start_btn.setEnabled(not loading)
        self.stop_winws_btn.setEnabled(not loading)
        self.stop_and_exit_btn.setEnabled(not loading)
        
        # Visual disabled state is handled globally in ui/theme.py.
        self.start_btn._update_style()
        self.stop_winws_btn._update_style()
        self.stop_and_exit_btn._update_style()

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
            fields={"dpi_phase", "dpi_running", "dpi_busy", "dpi_busy_text", "dpi_last_error", "current_strategy_summary"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        self.set_loading(state.dpi_busy, state.dpi_busy_text)
        self.update_status(state.dpi_phase or ("running" if state.dpi_running else "stopped"), state.dpi_last_error)
        self.update_strategy(state.current_strategy_summary or "")

    def _get_current_dpi_runtime_state(self) -> tuple[str, str]:
        """Возвращает текущую фазу DPI и последнюю известную ошибку."""
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                plan = self._controller.resolve_runtime_state(
                    snapshot_state=snapshot,
                    last_known_dpi_running=self._last_known_dpi_running,
                )
                return plan.phase, plan.last_error
            except Exception:
                pass
        plan = self._controller.resolve_runtime_state(
            snapshot_state=None,
            last_known_dpi_running=self._last_known_dpi_running,
        )
        return plan.phase, plan.last_error

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.start_btn.setText(tr_catalog("page.control.button.start", language=self._ui_language, default="Запустить Zapret"))
        self.stop_and_exit_btn.setText(
            tr_catalog("page.control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу")
        )
        self.test_btn.setText(tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"))
        self.folder_btn.setText(tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"))
        extra_group_title = getattr(getattr(self, "extra_actions_group", None), "titleLabel", None)
        if extra_group_title is not None:
            extra_group_title.setText(
                tr_catalog("page.control.section.additional", language=self._ui_language, default="Дополнительные действия")
            )
        title_label = getattr(getattr(self, "program_settings_card", None), "titleLabel", None)
        if title_label is not None:
            title_label.setText(
                tr_catalog("page.control.section.program_settings", language=self._ui_language, default="Настройки программы")
            )

        self.auto_dpi_toggle.set_texts(
            tr_catalog("page.control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog("page.control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы"),
        )
        self.defender_toggle.set_texts(
            tr_catalog("page.control.setting.defender.title", language=self._ui_language, default="Отключить Windows Defender"),
            tr_catalog("page.control.setting.defender.desc", language=self._ui_language, default="Требуются права администратора"),
        )
        self.max_block_toggle.set_texts(
            tr_catalog("page.control.setting.max_block.title", language=self._ui_language, default="Блокировать установку MAX"),
            tr_catalog("page.control.setting.max_block.desc", language=self._ui_language, default="Блокирует запуск/установку MAX и домены в hosts"),
        )

        if self.reset_program_card is not None and hasattr(self.reset_program_card, "setTitle"):
            try:
                self.reset_program_card.setTitle(
                    tr_catalog("page.control.setting.reset.title", language=self._ui_language, default="Сбросить программу")
                )
                self.reset_program_card.setContent(
                    tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
                )
                button = getattr(self.reset_program_card, "button", None)
                if button is not None:
                    button.setText(tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить"))
            except Exception:
                pass
        elif self.reset_program_btn is not None:
            self.reset_program_btn._default_text = tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить")
            self.reset_program_btn._confirm_text = tr_catalog(
                "page.control.button.reset_confirm",
                language=self._ui_language,
                default="Сбросить?",
            )
            self.reset_program_btn.setText(self.reset_program_btn._default_text)
            if self._reset_program_desc_label is not None:
                self._reset_program_desc_label.setText(
                    tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
                )
        if getattr(self, "test_action_card", None) is not None:
            try:
                self.test_action_card.setTitle(
                    tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения")
                )
                self.test_action_card.setContent(
                    tr_catalog("page.control.section.additional.test_desc", language=self._ui_language, default="Проверить сетевое подключение и доступность маршрута")
                )
                self.test_action_card.button.setText(
                    tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения")
                )
            except Exception:
                pass
        if getattr(self, "folder_action_card", None) is not None:
            try:
                self.folder_action_card.setTitle(
                    tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку")
                )
                self.folder_action_card.setContent(
                    tr_catalog("page.control.section.additional.folder_desc", language=self._ui_language, default="Быстро перейти к рабочей папке программы")
                )
                self.folder_action_card.button.setText(
                    tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку")
                )
            except Exception:
                pass
        self._update_stop_winws_button_text()
        phase, last_error = self._get_current_dpi_runtime_state()
        self.update_status(phase, last_error)
        self.update_strategy(self.strategy_label.text())
        
    def update_status(self, state: str | bool, last_error: str = ""):
        """Обновляет отображение статуса"""
        plan = self._controller.build_status_plan(
            state=state,
            last_error=last_error,
            language=self._ui_language,
        )
        self._last_known_dpi_running = plan.phase == "running"
        self.status_title.setText(plan.title)
        self.status_desc.setText(plan.description)
        self.status_dot.set_color(plan.dot_color)
        if plan.pulsing:
            self.status_dot.start_pulse()
        else:
            self.status_dot.stop_pulse()
        self.start_btn.setVisible(plan.show_start)
        self._update_stop_winws_button_text()
        self.stop_winws_btn.setVisible(plan.show_stop_only)
        self.stop_and_exit_btn.setVisible(plan.show_stop_and_exit)
            
    def update_strategy(self, name: str):
        """Обновляет отображение текущей стратегии"""
        self._update_stop_winws_button_text()
        plan = self._controller.build_strategy_display_plan(
            name=name,
            language=self._ui_language,
            window=self.window() or self,
        )
        self.strategy_label.setText(plan.title)
        self.strategy_desc.setText(plan.description)
        set_tooltip(self.strategy_label, plan.tooltip)
