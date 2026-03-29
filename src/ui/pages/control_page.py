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
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    MessageBox = None
    InfoBar = None
    _HAS_FLUENT_LABELS = False

from .base_page import BasePage
from ui.compat_widgets import SettingsRow, PulsingDot
from ui.compat_widgets import SettingsCard, ActionButton, PrimaryActionButton, StatusIndicator, set_tooltip
from ui.pages.strategies_page_base import ResetActionButton
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import themeColor, isDarkTheme
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False


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
        self._program_settings_synced = False
        
        self._build_ui()
        self._update_stop_winws_button_text()

    def showEvent(self, event):  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if event.spontaneous():
            return
        if self._program_settings_synced:
            return

        self._program_settings_synced = True
        QTimer.singleShot(0, self._sync_program_settings)

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

        # Индикатор загрузки (бегающая полоска) - показываем рядом с кнопками управления
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
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.start_btn = BigActionButton(
            tr_catalog("page.control.button.start", language=self._ui_language, default="Запустить Zapret"),
            "fa5s.play",
            accent=True,
        )
        buttons_layout.addWidget(self.start_btn)
        
        # Кнопка остановки только winws.exe / winws2.exe (в зависимости от режима)
        self.stop_winws_btn = StopButton(
            tr_catalog("page.control.button.stop_only_winws", language=self._ui_language, default="Остановить только winws.exe"),
            "fa5s.stop",
        )
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)
        
        # Кнопка полного выхода (остановка + закрытие программы)
        self.stop_and_exit_btn = StopButton(
            tr_catalog("page.control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу"),
            "fa5s.power-off",
        )
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)
        
        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)
        
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
        self.add_section_title(text_key="page.control.section.program_settings")

        program_settings_card = SettingsCard()

        try:
            from ui.pages.dpi_settings_page import Win11ToggleSwitch
        except Exception:
            Win11ToggleSwitch = None  # type: ignore[assignment]

        # Автозагрузка DPI
        auto_row = SettingsRow(
            "fa5s.bolt",
            tr_catalog("page.control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog("page.control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы"),
        )
        self.auto_row = auto_row
        self.auto_dpi_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.auto_dpi_toggle.setProperty("noDrag", True)
        if hasattr(self.auto_dpi_toggle, "toggled"):
            self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)
        auto_row.set_control(self.auto_dpi_toggle)
        program_settings_card.add_widget(auto_row)

        # Windows Defender
        defender_row = SettingsRow(
            "fa5s.shield-alt",
            tr_catalog("page.control.setting.defender.title", language=self._ui_language, default="Отключить Windows Defender"),
            tr_catalog("page.control.setting.defender.desc", language=self._ui_language, default="Требуются права администратора"),
        )
        self.defender_row = defender_row
        self.defender_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.defender_toggle.setProperty("noDrag", True)
        if hasattr(self.defender_toggle, "toggled"):
            self.defender_toggle.toggled.connect(self._on_defender_toggled)
        defender_row.set_control(self.defender_toggle)
        program_settings_card.add_widget(defender_row)

        # MAX blocker
        max_row = SettingsRow(
            "fa5s.ban",
            tr_catalog("page.control.setting.max_block.title", language=self._ui_language, default="Блокировать установку MAX"),
            tr_catalog("page.control.setting.max_block.desc", language=self._ui_language, default="Блокирует запуск/установку MAX и домены в hosts"),
        )
        self.max_row = max_row
        self.max_block_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.max_block_toggle.setProperty("noDrag", True)
        if hasattr(self.max_block_toggle, "toggled"):
            self.max_block_toggle.toggled.connect(self._on_max_blocker_toggled)
        max_row.set_control(self.max_block_toggle)
        program_settings_card.add_widget(max_row)

        # Сброс программы
        reset_row = SettingsRow(
            "fa5s.undo",
            tr_catalog("page.control.setting.reset.title", language=self._ui_language, default="Сбросить программу"),
            tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)"),
        )
        self.reset_row = reset_row
        self.reset_program_btn = ResetActionButton(
            tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить"),
            confirm_text=tr_catalog("page.control.button.reset_confirm", language=self._ui_language, default="Сбросить?"),
        )
        self.reset_program_btn.setProperty("noDrag", True)
        self.reset_program_btn.reset_confirmed.connect(self._on_reset_program_clicked)
        reset_row.set_control(self.reset_program_btn)
        program_settings_card.add_widget(reset_row)

        self.add_widget(program_settings_card)

        self.add_spacing(16)
        
        # Дополнительные действия
        self.add_section_title(text_key="page.control.section.additional")
        
        extra_card = SettingsCard()
        
        extra_layout = QHBoxLayout()
        extra_layout.setSpacing(8)
        
        self.test_btn = ActionButton(
            tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"),
            "fa5s.wifi",
        )
        extra_layout.addWidget(self.test_btn)
        
        self.folder_btn = ActionButton(
            tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"),
            "fa5s.folder-open",
        )
        extra_layout.addWidget(self.folder_btn)
        
        extra_layout.addStretch()
        extra_card.add_layout(extra_layout)
        
        self.add_widget(extra_card)

    def showEvent(self, event):
        super().showEvent(event)
        # Обновляем состояние тогглов при каждом показе страницы
        try:
            self._sync_program_settings()
        except Exception:
            pass

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
        """Устанавливает состояние Win11ToggleSwitch без побочных эффектов анимации/сигналов."""
        try:
            toggle.blockSignals(True)
        except Exception:
            pass

        try:
            if hasattr(toggle, "setChecked"):
                toggle.setChecked(bool(checked))
        except Exception:
            pass

        # Win11ToggleSwitch: обновляем позицию круга без анимации (как в Win11ToggleRow)
        try:
            toggle._circle_position = (toggle.width() - 18) if checked else 4.0  # type: ignore[attr-defined]
            toggle.update()
        except Exception:
            pass

        try:
            toggle.blockSignals(False)
        except Exception:
            pass

    def _sync_program_settings(self) -> None:
        """Синхронизирует UI с текущими настройками (реестр/система)."""
        # Автозагрузка DPI
        try:
            from config import get_dpi_autostart
            self._set_toggle_checked(self.auto_dpi_toggle, bool(get_dpi_autostart()))
        except Exception:
            pass

        # Windows Defender (реальное состояние системы)
        try:
            from altmenu.defender_manager import WindowsDefenderManager
            self._set_toggle_checked(self.defender_toggle, bool(WindowsDefenderManager().is_defender_disabled()))
        except Exception:
            pass

        # MAX blocker (состояние из реестра GUI)
        try:
            from altmenu.max_blocker import is_max_blocked
            self._set_toggle_checked(self.max_block_toggle, bool(is_max_blocked()))
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        try:
            if hasattr(self.parent_app, "set_status"):
                self.parent_app.set_status(msg)
        except Exception:
            pass

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            from config import set_dpi_autostart
            set_dpi_autostart(bool(enabled))

            msg = (
                "DPI будет включаться автоматически при старте программы"
                if enabled
                else "Автозагрузка DPI отключена"
            )
            self._set_status(msg)
            InfoBar.success(title="Автозагрузка DPI", content=msg, parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_defender_toggled(self, disable: bool) -> None:
        import ctypes

        # Требуются права администратора
        if not ctypes.windll.shell32.IsUserAnAdmin():
            InfoBar.error(
                title="Требуются права администратора",
                content="Для управления Windows Defender требуются права администратора. Перезапустите программу от имени администратора.",
                parent=self.window(),
            )
            self._set_toggle_checked(self.defender_toggle, not disable)
            return

        try:
            from altmenu.defender_manager import WindowsDefenderManager, set_defender_disabled

            manager = WindowsDefenderManager(status_callback=self._set_status)

            if disable:
                # Первое подтверждение: подробное предупреждение о последствиях
                # Пользователь должен осознанно принять решение об отключении защиты
                box = MessageBox(
                    tr_catalog(
                        "page.control.dialog.defender_disable.title",
                        language=self._ui_language,
                        default="⚠️ Отключение Windows Defender",
                    ),
                    "Вы собираетесь отключить встроенную антивирусную защиту Windows.\n\n"
                    "Что произойдёт:\n"
                    "• Защита в реальном времени будет отключена\n"
                    "• Облачная защита и SmartScreen будут отключены\n"
                    "• Автоматическая отправка образцов будет отключена\n"
                    "• Мониторинг поведения программ будет отключён\n\n"
                    "⚠️ Ваш компьютер станет уязвим для вирусов и вредоносного ПО.\n"
                    "Отключайте только если вы понимаете, что делаете.\n"
                    "Вы сможете включить Defender обратно в любой момент.",
                    self.window(),
                )
                if not box.exec():
                    self._set_toggle_checked(self.defender_toggle, False)
                    return

                # Второе подтверждение: финальное согласие пользователя
                box2 = MessageBox(
                    "Подтверждение",
                    "Вы уверены? Нажимая «ОК», вы подтверждаете, что:\n\n"
                    "• Вы самостоятельно приняли решение отключить Windows Defender\n"
                    "• Вы осознаёте риски работы без антивирусной защиты\n"
                    "• Вы знаете, что можете включить защиту обратно\n\n"
                    "Может потребоваться перезагрузка для полного применения.",
                    self.window(),
                )
                if not box2.exec():
                    self._set_toggle_checked(self.defender_toggle, False)
                    return

                self._set_status("Отключение Windows Defender...")
                success, count = manager.disable_defender()

                if success:
                    set_defender_disabled(True)
                    InfoBar.success(
                        title="Windows Defender отключен",
                        content=f"Windows Defender успешно отключен. Применено {count} настроек. Может потребоваться перезагрузка.",
                        parent=self.window(),
                    )
                else:
                    InfoBar.error(
                        title="Ошибка",
                        content="Не удалось отключить Windows Defender. Возможно, некоторые настройки заблокированы системой.",
                        parent=self.window(),
                    )
                    self._set_toggle_checked(self.defender_toggle, False)
            else:
                box = MessageBox(
                    tr_catalog(
                        "page.control.dialog.defender_enable.title",
                        language=self._ui_language,
                        default="Включение Windows Defender",
                    ),
                    "Включить Windows Defender обратно?\n\n"
                    "Это восстановит защиту вашего компьютера.",
                    self.window(),
                )
                if not box.exec():
                    self._set_toggle_checked(self.defender_toggle, True)
                    return

                self._set_status("Включение Windows Defender...")
                success, count = manager.enable_defender()

                if success:
                    set_defender_disabled(False)
                    InfoBar.success(
                        title="Windows Defender включен",
                        content="Windows Defender успешно включен. Защита вашего компьютера восстановлена.",
                        parent=self.window(),
                    )
                else:
                    InfoBar.warning(
                        title="Частичный успех",
                        content="Windows Defender включен частично. Некоторые настройки могут потребовать ручного исправления.",
                        parent=self.window(),
                    )

            self._set_status("Готово")

        except Exception as e:
            InfoBar.error(
                title="Ошибка",
                content=f"Произошла ошибка при изменении настроек Windows Defender: {e}",
                parent=self.window(),
            )
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        try:
            from altmenu.max_blocker import MaxBlockerManager

            manager = MaxBlockerManager(status_callback=self._set_status)

            if enable:
                box = MessageBox(
                    tr_catalog(
                        "page.control.dialog.max_block_enable.title",
                        language=self._ui_language,
                        default="Блокировка MAX",
                    ),
                    "Включить блокировку установки и работы программы MAX?\n\n"
                    "• Заблокирует запуск max.exe, max.msi и других файлов MAX\n"
                    "• Добавит правила блокировки в Windows Firewall\n"
                    "• Заблокирует домены MAX в файле hosts",
                    self.window(),
                )
                if not box.exec():
                    self._set_toggle_checked(self.max_block_toggle, False)
                    return

                success, message = manager.enable_blocking()

                if success:
                    InfoBar.success(title="Блокировка включена", content=message, parent=self.window())
                else:
                    InfoBar.warning(title="Ошибка", content=f"Не удалось полностью включить блокировку: {message}", parent=self.window())
                    self._set_toggle_checked(self.max_block_toggle, False)
            else:
                box = MessageBox(
                    tr_catalog(
                        "page.control.dialog.max_block_disable.title",
                        language=self._ui_language,
                        default="Отключение блокировки MAX",
                    ),
                    "Отключить блокировку программы MAX?\n\n"
                    "Это удалит все созданные блокировки и правила.",
                    self.window(),
                )
                if not box.exec():
                    self._set_toggle_checked(self.max_block_toggle, True)
                    return

                success, message = manager.disable_blocking()
                if success:
                    InfoBar.success(title="Блокировка отключена", content=message, parent=self.window())
                else:
                    InfoBar.warning(title="Ошибка", content=f"Не удалось полностью отключить блокировку: {message}", parent=self.window())

            self._set_status("Готово")

        except Exception as e:
            InfoBar.error(title="Ошибка", content=f"Ошибка при переключении блокировки MAX: {e}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_reset_program_clicked(self) -> None:
        from startup.check_cache import startup_cache
        from log import log

        try:
            startup_cache.invalidate_cache()
            log("Кэш проверок запуска очищен пользователем", "INFO")
            self._set_status("Кэш проверок запуска очищен")
        except Exception as e:
            InfoBar.warning(title="Ошибка", content=f"Не удалось очистить кэш: {e}", parent=self.window())
            log(f"Ошибка очистки кэша: {e}", "❌ ERROR")
        finally:
            self._sync_program_settings()

    def _update_stop_winws_button_text(self):
        """Обновляет подпись кнопки остановки (winws.exe vs winws2.exe) по текущему режиму."""
        try:
            from strategy_menu import get_strategy_launch_method
            from config import get_winws_exe_for_method

            method = get_strategy_launch_method()
            exe_name = os.path.basename(get_winws_exe_for_method(method)) or "winws.exe"
            template = tr_catalog(
                "page.control.button.stop_only_template",
                language=self._ui_language,
                default="Остановить только {exe_name}",
            )
            self.stop_winws_btn.setText(template.format(exe_name=exe_name))
        except Exception:
            # Fallback на старую подпись (не ломаем UI из-за циклических импортов/ошибок реестра)
            self.stop_winws_btn.setText(
                tr_catalog(
                    "page.control.button.stop_only_winws",
                    language=self._ui_language,
                    default="Остановить только winws.exe",
                )
            )
        
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

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.start_btn.setText(tr_catalog("page.control.button.start", language=self._ui_language, default="Запустить Zapret"))
        self.stop_and_exit_btn.setText(
            tr_catalog("page.control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу")
        )
        self.test_btn.setText(tr_catalog("page.control.button.connection_test", language=self._ui_language, default="Тест соединения"))
        self.folder_btn.setText(tr_catalog("page.control.button.open_folder", language=self._ui_language, default="Открыть папку"))
        self.reset_program_btn._default_text = tr_catalog("page.control.button.reset", language=self._ui_language, default="Сбросить")
        self.reset_program_btn._confirm_text = tr_catalog(
            "page.control.button.reset_confirm",
            language=self._ui_language,
            default="Сбросить?",
        )
        self.reset_program_btn.setText(self.reset_program_btn._default_text)

        self.auto_row.set_title(tr_catalog("page.control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"))
        self.auto_row.set_description(
            tr_catalog("page.control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы")
        )
        self.defender_row.set_title(tr_catalog("page.control.setting.defender.title", language=self._ui_language, default="Отключить Windows Defender"))
        self.defender_row.set_description(
            tr_catalog("page.control.setting.defender.desc", language=self._ui_language, default="Требуются права администратора")
        )
        self.max_row.set_title(tr_catalog("page.control.setting.max_block.title", language=self._ui_language, default="Блокировать установку MAX"))
        self.max_row.set_description(
            tr_catalog("page.control.setting.max_block.desc", language=self._ui_language, default="Блокирует запуск/установку MAX и домены в hosts")
        )
        self.reset_row.set_title(tr_catalog("page.control.setting.reset.title", language=self._ui_language, default="Сбросить программу"))
        self.reset_row.set_description(
            tr_catalog("page.control.setting.reset.desc", language=self._ui_language, default="Очистить кэш проверок запуска (без удаления пресетов/настроек)")
        )
        self._update_stop_winws_button_text()
        self.update_status(bool(self.stop_winws_btn.isVisible()))
        self.update_strategy(self.strategy_label.text())
        
    def update_status(self, is_running: bool):
        """Обновляет отображение статуса"""
        if is_running:
            self.status_title.setText(
                tr_catalog("page.control.status.running", language=self._ui_language, default="Zapret работает")
            )
            self.status_desc.setText(
                tr_catalog("page.control.status.bypass_active", language=self._ui_language, default="Обход блокировок активен")
            )
            self.status_dot.set_color('#6ccb5f')
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self._update_stop_winws_button_text()
            self.stop_winws_btn.setVisible(True)
            self.stop_and_exit_btn.setVisible(True)
        else:
            self.status_title.setText(
                tr_catalog("page.control.status.stopped", language=self._ui_language, default="Zapret остановлен")
            )
            self.status_desc.setText(
                tr_catalog("page.control.status.press_start", language=self._ui_language, default="Нажмите «Запустить» для активации")
            )
            self.status_dot.set_color('#ff6b6b')
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
            
    def update_strategy(self, name: str):
        """Обновляет отображение текущей стратегии"""
        self._update_stop_winws_button_text()
        # Direct modes: show summary of active target'ов from the selected source preset.
        try:
            from strategy_menu import get_strategy_launch_method

            method = get_strategy_launch_method()
            if method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                from ui.main_window_display import get_direct_strategy_summary

                summary = get_direct_strategy_summary(self.window() or self, max_items=2)
                name = summary or tr_catalog(
                    "page.control.strategy.not_selected",
                    language=self._ui_language,
                    default="Не выбрана",
                )

                if method in ("direct_zapret2", "direct_zapret1"):
                    from core.presets.direct_facade import DirectPresetFacade

                    selections = DirectPresetFacade.from_launch_method(method).get_strategy_selections() or {}
                else:
                    from strategy_menu import get_direct_strategy_selections

                    selections = get_direct_strategy_selections() or {}
                active_count = sum(1 for strategy_id in selections.values() if (strategy_id or "none") != "none")
                if active_count > 0:
                    set_tooltip(self.strategy_label, summary.replace(" • ", "\n").replace(" +", "\n+"))
                else:
                    set_tooltip(self.strategy_label, "")
        except Exception:
            pass

        not_selected = tr_catalog("page.control.strategy.not_selected", language=self._ui_language, default="Не выбрана")
        if name and name not in ("Автостарт DPI отключен", not_selected):
            self.strategy_label.setText(name)
            self.strategy_desc.setText(
                tr_catalog("page.control.strategy.active", language=self._ui_language, default="Активная стратегия обхода")
            )
        else:
            self.strategy_label.setText(
                tr_catalog("page.control.strategy.not_selected", language=self._ui_language, default="Не выбрана")
            )
            self.strategy_desc.setText(
                tr_catalog("page.control.strategy.select_hint", language=self._ui_language, default="Выберите стратегию в разделе «Стратегии»")
            )
