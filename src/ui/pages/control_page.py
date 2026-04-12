# ui/pages/control_page.py
"""Страница управления - запуск/остановка DPI"""

from PyQt6.QtWidgets import QHBoxLayout, QLabel
import qtawesome as qta

try:
    from qfluentwidgets import (
        SubtitleLabel, StrongBodyLabel, CaptionLabel,
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
from ui.pages.control_page_program_settings_build import (
    build_control_program_settings_section,
)
from ui.pages.control_page_runtime_helpers import (
    apply_program_settings_snapshot,
    apply_status_plan,
    apply_strategy_display,
    set_toggle_checked,
    show_action_result_plan,
)
from ui.pages.control_page_sections_build import (
    build_control_extra_actions_section,
    build_control_management_section,
    build_control_status_section,
    build_control_strategy_section,
)
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    ResetActionButton,
    enable_setting_card_group_auto_height,
)
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
    from qfluentwidgets import themeColor
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False


from ui.control_page_controller import ControlPageController


class BigActionButton(PrimaryActionButton):
    """Большая акцентная кнопка действия (запуск)"""

    def __init__(self, text: str, icon_name: str = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    """Кнопка остановки (нейтральная, не акцентная)"""

    def __init__(self, text: str, icon_name: str = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, parent=parent)


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
        self._program_settings_runtime_attached = False
        self._runtime_initialized = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._program_settings_runtime_unsubscribe = None
        self._cleanup_in_progress = False
        self._last_known_dpi_running = False

        self._build_ui()
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._attach_program_settings_runtime()
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
        
        status_widgets = build_control_status_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent_labels=_HAS_FLUENT_LABELS,
            subtitle_label_cls=SubtitleLabel,
            caption_label_cls=CaptionLabel,
        )
        self.status_dot = status_widgets.status_dot
        self.status_title = status_widgets.status_title
        self.status_desc = status_widgets.status_desc
        self.add_widget(status_widgets.card)
        
        self.add_spacing(16)
        
        # Управление
        self.add_section_title(text_key="page.control.section.management")
        
        management_widgets = build_control_management_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent_labels=_HAS_FLUENT_LABELS,
            caption_label_cls=CaptionLabel,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            big_action_button_cls=BigActionButton,
            stop_button_cls=StopButton,
            on_start=self._start_dpi,
            on_stop_winws=self._stop_dpi,
            on_stop_and_exit=self._stop_and_exit,
            parent=self,
        )
        self.start_btn = management_widgets.start_btn
        self.stop_winws_btn = management_widgets.stop_winws_btn
        self.stop_and_exit_btn = management_widgets.stop_and_exit_btn
        self.progress_bar = management_widgets.progress_bar
        self.loading_label = management_widgets.loading_label
        self.add_widget(management_widgets.card)
        
        self.add_spacing(16)

        # Текущая стратегия
        self.add_section_title(text_key="page.control.section.current_strategy")

        strategy_widgets = build_control_strategy_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            has_fluent_labels=_HAS_FLUENT_LABELS,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            accent_hex=themeColor().name() if HAS_FLUENT else "#60cdff",
        )
        self.strategy_icon = strategy_widgets.strategy_icon
        self.strategy_label = strategy_widgets.strategy_label
        self.strategy_desc = strategy_widgets.strategy_desc
        self.add_widget(strategy_widgets.card)

        self.add_spacing(16)

        # Настройки программы (бывшие пункты Alt-меню "Настройки")
        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None  # type: ignore[assignment]

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления")

        use_fluent_program_settings_group = (
            SettingCardGroup is not None
            and PushSettingCard is not None
            and _HAS_FLUENT_LABELS
        )
        self.program_settings_section_label = None
        if not use_fluent_program_settings_group:
            self.program_settings_section_label = self.add_section_title(
                text_key="page.control.section.program_settings"
            )

        program_settings_widgets = build_control_program_settings_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            setting_card_group_cls=SettingCardGroup,
            push_setting_card_cls=PushSettingCard,
            settings_card_cls=SettingsCard,
            reset_action_button_cls=ResetActionButton,
            win11_toggle_row_cls=Win11ToggleRow,
            caption_label_cls=CaptionLabel,
            fallback_label_cls=QLabel,
            qhbox_layout_cls=QHBoxLayout,
            qta_module=qta,
            on_auto_dpi_toggled=self._on_auto_dpi_toggled,
            on_defender_toggled=self._on_defender_toggled,
            on_max_blocker_toggled=self._on_max_blocker_toggled,
            on_confirm_reset_program_clicked=self._confirm_reset_program_clicked,
            on_reset_program_clicked=self._on_reset_program_clicked,
        )
        self.program_settings_card = program_settings_widgets.program_settings_card
        self.auto_dpi_toggle = program_settings_widgets.auto_dpi_toggle
        self.defender_toggle = program_settings_widgets.defender_toggle
        self.max_block_toggle = program_settings_widgets.max_block_toggle
        self.reset_program_card = program_settings_widgets.reset_program_card
        self.reset_program_btn = program_settings_widgets.reset_program_btn
        self._reset_program_desc_label = program_settings_widgets.reset_program_desc_label

        self.add_widget(self.program_settings_card)
        if program_settings_widgets.extra_reset_card is not None:
            self.add_widget(program_settings_widgets.extra_reset_card)
        enable_setting_card_group_auto_height(self.program_settings_card)

        self.add_spacing(16)
        
        # Дополнительные действия
        extra_widgets = build_control_extra_actions_section(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            strong_body_label_cls=StrongBodyLabel,
            action_button_cls=ActionButton,
            quick_actions_bar_cls=QuickActionsBar,
            parent=self.content,
            on_test=self._open_connection_test,
            on_open_folder=self._open_folder,
        )
        self.test_btn = extra_widgets.test_btn
        self.folder_btn = extra_widgets.folder_btn
        self.additional_section_label = extra_widgets.section_label
        self.extra_actions_group = extra_widgets.actions_group
        self.add_widget(self.additional_section_label)
        self.add_widget(self.extra_actions_group)

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        """Устанавливает состояние toggle-карточки или переключателя без лишних сигналов."""
        set_toggle_checked(toggle, checked)

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

    def _require_app_context(self):
        app_context = getattr(self.window(), "app_context", None)
        if app_context is None:
            raise RuntimeError("AppContext is required for ControlPage")
        return app_context

    def _attach_program_settings_runtime(self) -> None:
        if self._program_settings_runtime_attached:
            return
        self._program_settings_runtime_attached = True
        self._program_settings_runtime_unsubscribe = self._require_app_context().program_settings_runtime_service.subscribe(
            self._apply_program_settings_snapshot,
            emit_initial=True,
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        """Применяет shared snapshot программных настроек к toggle-элементам."""
        if self._cleanup_in_progress:
            return
        apply_program_settings_snapshot(
            snapshot,
            auto_dpi_toggle=self.auto_dpi_toggle,
            defender_toggle=self.defender_toggle,
            max_block_toggle=self.max_block_toggle,
        )

    def _sync_program_settings(self) -> None:
        """Явно перечитывает shared snapshot программных настроек."""
        snapshot = self._require_app_context().program_settings_runtime_service.refresh()
        self._apply_program_settings_snapshot(snapshot)

    def _get_program_settings_runtime_service(self):
        return self._require_app_context().program_settings_runtime_service

    def _set_status(self, msg: str) -> None:
        try:
            if hasattr(self.parent_app, "set_status"):
                self.parent_app.set_status(msg)
        except Exception:
            pass

    def _show_action_result_plan(self, plan, toggle=None) -> None:
        show_action_result_plan(
            plan,
            window=self.window(),
            set_status=self._set_status,
            info_bar_cls=InfoBar,
            toggle=toggle,
        )

    def _run_confirmation_dialog(self, dialog_plan, toggle=None) -> bool:
        box = MessageBox(dialog_plan.title, dialog_plan.content, self.window())
        if box.exec():
            return True
        if dialog_plan.revert_checked is not None and toggle is not None:
            self._set_toggle_checked(toggle, dialog_plan.revert_checked)
        return False

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = ControlPageController.save_auto_dpi(enabled)
            self._set_status(plan.message)
            InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_defender_toggled(self, disable: bool) -> None:
        start_plan = ControlPageController.build_defender_toggle_start_plan(
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

            result_plan = ControlPageController.run_defender_toggle(
                disable=disable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.defender_toggle)
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        start_plan = ControlPageController.build_max_block_toggle_start_plan(
            enable=enable,
            language=self._ui_language,
        )
        try:
            for dialog_plan in start_plan.confirmations:
                if not self._run_confirmation_dialog(dialog_plan, self.max_block_toggle):
                    return

            if start_plan.start_status:
                self._set_status(start_plan.start_status)

            result_plan = ControlPageController.run_max_block_toggle(
                enable=enable,
                status_callback=self._set_status,
            )
            self._show_action_result_plan(result_plan, self.max_block_toggle)
        finally:
            self._sync_program_settings()

    def _on_reset_program_clicked(self) -> None:
        try:
            ok, message = ControlPageController.reset_startup_cache()
            if ok:
                self._set_status(message)
            else:
                InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {message}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _update_stop_winws_button_text(self):
        """Обновляет подпись кнопки остановки (winws.exe vs winws2.exe) по текущему режиму."""
        plan = ControlPageController.build_stop_button_plan(language=self._ui_language)
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
        if self._cleanup_in_progress:
            return
        self.set_loading(state.dpi_busy, state.dpi_busy_text)
        self.update_status(state.dpi_phase or ("running" if state.dpi_running else "stopped"), state.dpi_last_error)
        self.update_strategy(state.current_strategy_summary or "")

    def _get_current_dpi_runtime_state(self) -> tuple[str, str]:
        """Возвращает текущую фазу DPI и последнюю известную ошибку."""
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                plan = ControlPageController.resolve_runtime_state(
                    snapshot_state=snapshot,
                    last_known_dpi_running=self._last_known_dpi_running,
                )
                return plan.phase, plan.last_error
            except Exception:
                pass
        plan = ControlPageController.resolve_runtime_state(
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
        if self.additional_section_label is not None:
            self.additional_section_label.setText(
                tr_catalog("page.control.section.additional", language=self._ui_language, default="Дополнительные действия")
            )
        self.test_btn.setToolTip(
            tr_catalog("page.control.section.additional.test_desc", language=self._ui_language, default="Проверить сетевое подключение и доступность маршрута")
        )
        self.folder_btn.setToolTip(
            tr_catalog("page.control.section.additional.folder_desc", language=self._ui_language, default="Быстро перейти к рабочей папке программы")
        )
        title_label = getattr(getattr(self, "program_settings_card", None), "titleLabel", None)
        if title_label is not None:
            title_label.setText(
                tr_catalog("page.control.section.program_settings", language=self._ui_language, default="Настройки программы")
            )

        self.auto_dpi_toggle.set_texts(
            tr_catalog("page.control.setting.autostart.title", language=self._ui_language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.control.setting.autostart.desc", language=self._ui_language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
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
        self._update_stop_winws_button_text()
        phase, last_error = self._get_current_dpi_runtime_state()
        self.update_status(phase, last_error)
        self.update_strategy(self.strategy_label.text())
        
    def update_status(self, state: str | bool, last_error: str = ""):
        """Обновляет отображение статуса"""
        plan = ControlPageController.build_status_plan(
            state=state,
            last_error=last_error,
            language=self._ui_language,
        )
        self._last_known_dpi_running = apply_status_plan(
            plan,
            status_title=self.status_title,
            status_desc=self.status_desc,
            status_dot=self.status_dot,
            start_btn=self.start_btn,
            stop_winws_btn=self.stop_winws_btn,
            stop_and_exit_btn=self.stop_and_exit_btn,
            update_stop_button_text=self._update_stop_winws_button_text,
        )
            
    def update_strategy(self, name: str):
        """Обновляет отображение текущей стратегии"""
        self._update_stop_winws_button_text()
        apply_strategy_display(
            name=name,
            language=self._ui_language,
            window=self.window() or self,
            strategy_label=self.strategy_label,
            strategy_desc=self.strategy_desc,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None

        unsubscribe_runtime = getattr(self, "_program_settings_runtime_unsubscribe", None)
        if callable(unsubscribe_runtime):
            try:
                unsubscribe_runtime()
            except Exception:
                pass
        self._program_settings_runtime_unsubscribe = None
