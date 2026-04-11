# ui/pages/zapret1/direct_control_page.py
"""Direct Zapret1 management page (entry point for direct_zapret1 mode)."""

import os
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
)
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.control_page_controller import ControlPageController
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    PulsingDot,
    SettingsCard,
    build_advanced_settings_section,
    enable_setting_card_group_auto_height,
    set_tooltip,
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
    from qfluentwidgets import (
        CaptionLabel, StrongBodyLabel, SubtitleLabel, BodyLabel,
        IndeterminateProgressBar, MessageBox, InfoBar,
        PushButton, PushSettingCard, FluentIcon, CardWidget, SettingCardGroup,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QLabel as StrongBodyLabel, QLabel as CaptionLabel, QLabel as BodyLabel  # type: ignore
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore
    MessageBox = None
    InfoBar = None
    PushButton = None
    PushSettingCard = None
    FluentIcon = None
    CardWidget = QWidget  # type: ignore
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT = False


class BigActionButton(PrimaryActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, parent=parent)


class Zapret1DirectControlPage(BasePage):
    """Страница управления для direct_zapret1 (главная вкладка раздела «Стратегии»)."""

    navigate_to_strategies = pyqtSignal()   # → PageName.ZAPRET1_DIRECT
    navigate_to_presets = pyqtSignal()       # → PageName.ZAPRET1_USER_PRESETS
    navigate_to_blobs = pyqtSignal()         # → PageName.BLOBS

    def __init__(self, parent=None):
        super().__init__(
            "Управление Zapret 1",
            "Настройка и запуск Zapret 1 (winws.exe). Выберите стратегии для категорий "
            "или переключитесь на другой пресет.",
            parent,
            title_key="page.z1_control.title",
            subtitle_key="page.z1_control.subtitle",
        )
        self.parent_app = parent
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._last_known_dpi_running = False
        self._program_settings_runtime_attached = False
        self._preset_name_runtime = ControlPageController.create_preset_name_runtime()
        self._advanced_settings_dirty = True
        self._build_ui()
        self._attach_program_settings_runtime()
        self.run_when_page_ready(self._apply_pending_advanced_settings_refresh)
        try:
            preset_name_text, preset_name_tooltip = self._load_preset_name()
            if preset_name_text:
                self.preset_name_label.setText(preset_name_text)
                set_tooltip(self.preset_name_label, preset_name_tooltip)
            self._refresh_advanced_settings()
            if self._is_direct_zapret1_launch_active():
                self.update_status("running")
            else:
                self.update_status("stopped")
            self._preset_name_runtime.mark_applied()
        except Exception:
            pass

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

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            webbrowser.open(DOCS_URL)
        except Exception:
            pass

    def _apply_pending_preset_name_refresh(self) -> None:
        if not self._preset_name_runtime.should_refresh():
            return
        if not self.is_page_ready():
            return
        try:
            self._refresh_preset_name()
        except Exception:
            pass

    def _build_ui(self):
        # ── Статус работы ──────────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.status")

        status_card = SettingsCard()
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)

        self.status_dot = PulsingDot()
        status_layout.addWidget(self.status_dot)

        status_text = QVBoxLayout()
        status_text.setContentsMargins(0, 0, 0, 0)
        status_text.setSpacing(2)

        if _HAS_FLUENT:
            self.status_title = StrongBodyLabel(
                tr_catalog("page.z1_control.status.checking", language=self._ui_language, default="Проверка...")
            )
            self.status_desc = CaptionLabel(
                tr_catalog("page.z1_control.status.detecting", language=self._ui_language, default="Определение состояния процесса")
            )
        else:
            from PyQt6.QtWidgets import QLabel
            self.status_title = QLabel(
                tr_catalog("page.z1_control.status.checking", language=self._ui_language, default="Проверка...")
            )
            self.status_desc = QLabel(
                tr_catalog("page.z1_control.status.detecting", language=self._ui_language, default="Определение состояния процесса")
            )

        status_text.addWidget(self.status_title)
        status_text.addWidget(self.status_desc)
        status_layout.addLayout(status_text, 1)
        status_card.add_layout(status_layout)
        self.add_widget(status_card)

        self.add_spacing(16)

        # ── Управление ─────────────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.management")

        control_card = SettingsCard()

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.start_btn = BigActionButton(
            tr_catalog("page.z1_control.button.start", language=self._ui_language, default="Запустить Zapret"),
            "fa5s.play",
            accent=True,
        )
        self.start_btn.clicked.connect(self._start_dpi)
        buttons_layout.addWidget(self.start_btn)

        self.stop_winws_btn = StopButton(
            tr_catalog("page.z1_control.button.stop_winws", language=self._ui_language, default="Остановить winws.exe"),
            "fa5s.stop",
        )
        self.stop_winws_btn.clicked.connect(self._stop_dpi)
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)

        self.stop_and_exit_btn = StopButton(
            tr_catalog("page.z1_control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть"),
            "fa5s.power-off",
        )
        self.stop_and_exit_btn.clicked.connect(self._stop_and_exit)
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)

        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)

        # Полоса загрузки должна быть ниже кнопок, чтобы кнопки не смещались,
        # когда состояние страницы переходит в busy/loading.
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        control_card.add_widget(self.progress_bar)

        if _HAS_FLUENT:
            self.loading_label = CaptionLabel("")
        else:
            from PyQt6.QtWidgets import QLabel
            self.loading_label = QLabel("")
        self.loading_label.setVisible(False)
        control_card.add_widget(self.loading_label)
        self.add_widget(control_card)

        self.add_spacing(16)

        # ── Пресет / Стратегии ──────────────────────────────────────────────
        self.add_section_title(text_key="page.z1_control.section.presets")

        # Card A — Выбранный активный пресет
        if PushSettingCard is not None:
            preset_card = PushSettingCard(
                tr_catalog("page.z1_control.button.my_presets", language=self._ui_language, default="Мои пресеты"),
                qta.icon("fa5s.star", color="#ffc107"),
                tr_catalog("page.z1_control.preset.not_selected", language=self._ui_language, default="Не выбран"),
                tr_catalog("page.z1_control.preset.current", language=self._ui_language, default="Текущий активный пресет"),
                self.content,
            )
            preset_card.clicked.connect(self.navigate_to_presets.emit)
            self.preset_name_label = preset_card.titleLabel
            self.preset_caption_label = preset_card.contentLabel
            self.presets_btn = preset_card.button
        else:
            preset_card = CardWidget()
            self.preset_card = preset_card
            preset_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            preset_row = QHBoxLayout(preset_card)
            preset_row.setContentsMargins(16, 14, 16, 14)
            preset_row.setSpacing(12)

            preset_icon_lbl = QLabel()
            preset_icon_lbl.setPixmap(qta.icon("fa5s.star", color="#ffc107").pixmap(20, 20))
            preset_icon_lbl.setFixedSize(24, 24)
            preset_row.addWidget(preset_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            preset_col = QVBoxLayout()
            preset_col.setSpacing(2)
            self.preset_name_label = StrongBodyLabel(
                tr_catalog("page.z1_control.preset.not_selected", language=self._ui_language, default="Не выбран")
            )
            self.preset_caption_label = CaptionLabel(
                tr_catalog("page.z1_control.preset.current", language=self._ui_language, default="Текущий активный пресет")
            )
            preset_col.addWidget(self.preset_name_label)
            preset_col.addWidget(self.preset_caption_label)
            preset_row.addLayout(preset_col, 1)

            presets_btn = ActionButton(
                tr_catalog("page.z1_control.button.my_presets", language=self._ui_language, default="Мои пресеты"),
                "fa5s.folder-open",
            )
            presets_btn.clicked.connect(self.navigate_to_presets.emit)
            self.presets_btn = presets_btn
            preset_row.addWidget(presets_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.add_widget(preset_card)

        self.add_spacing(8)

        # Card B — Стратегии
        if PushSettingCard is not None:
            strat_card = PushSettingCard(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                qta.icon("fa5s.play", color="#60cdff"),
                tr_catalog("page.z1_control.strategies.title", language=self._ui_language, default="Стратегии по категориям"),
                tr_catalog("page.z1_control.strategies.desc", language=self._ui_language, default="Выбор стратегии для YouTube, Discord и др."),
                self.content,
            )
            strat_card.clicked.connect(self._open_strategies_page)
            self.strategies_title_label = strat_card.titleLabel
            self.strategies_desc_label = strat_card.contentLabel
            self.open_strat_btn = strat_card.button
        else:
            strat_card = CardWidget()
            self.strategies_card = strat_card
            strat_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            strat_row = QHBoxLayout(strat_card)
            strat_row.setContentsMargins(16, 14, 16, 14)
            strat_row.setSpacing(12)

            strat_icon_lbl = QLabel()
            strat_icon_lbl.setPixmap(qta.icon("fa5s.play", color="#60cdff").pixmap(20, 20))
            strat_icon_lbl.setFixedSize(24, 24)
            strat_row.addWidget(strat_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            strat_col = QVBoxLayout()
            strat_col.setSpacing(2)
            self.strategies_title_label = StrongBodyLabel(
                tr_catalog("page.z1_control.strategies.title", language=self._ui_language, default="Стратегии по категориям")
            )
            self.strategies_desc_label = CaptionLabel(
                tr_catalog("page.z1_control.strategies.desc", language=self._ui_language, default="Выбор стратегии для YouTube, Discord и др.")
            )
            strat_col.addWidget(self.strategies_title_label)
            strat_col.addWidget(self.strategies_desc_label)
            strat_row.addLayout(strat_col, 1)

            open_strat_btn = ActionButton(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                "fa5s.play",
            )
            open_strat_btn.clicked.connect(self._open_strategies_page)
            self.open_strat_btn = open_strat_btn
            strat_row.addWidget(open_strat_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.add_widget(strat_card)

        self.add_spacing(16)

        # ── Настройки программы ─────────────────────────────────────────────
        program_settings_title = tr_catalog(
            "page.z1_control.section.program_settings",
            language=self._ui_language,
            default="Настройки программы",
        )
        if SettingCardGroup is not None and _HAS_FLUENT:
            self.program_settings_section_label = None
            program_settings_card = SettingCardGroup(program_settings_title, self.content)
        else:
            self.program_settings_section_label = self.add_section_title(
                text_key="page.z1_control.section.program_settings"
            )
            program_settings_card = SettingsCard()
        self.program_settings_card = program_settings_card

        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления Zapret 1")

        self.auto_dpi_toggle = Win11ToggleRow(
            "fa5s.bolt",
            tr_catalog("page.z1_control.setting.autostart.title", language=self._ui_language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=self._ui_language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим"),
        )
        self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)

        add_setting_card = getattr(program_settings_card, "addSettingCard", None)
        if callable(add_setting_card):
            add_setting_card(self.auto_dpi_toggle)
        else:
            program_settings_card.add_widget(self.auto_dpi_toggle)

        self.add_widget(program_settings_card)
        self.add_spacing(16)

        # ── Дополнительные настройки direct_zapret1 ───────────────────────
        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None

        self.discord_restart_toggle = (
            Win11ToggleRow(
                "mdi.discord",
                tr_catalog("page.z1_control.advanced.discord_restart.title", language=self._ui_language, default="Перезапуск Discord"),
                tr_catalog("page.z1_control.advanced.discord_restart.desc", language=self._ui_language, default="Автоперезапуск при смене стратегии"),
                "#7289da",
            )
            if Win11ToggleRow
            else None
        )
        if self.discord_restart_toggle is not None:
            self.discord_restart_toggle.toggled.connect(self._on_discord_restart_changed)

        self.wssize_toggle = (
            Win11ToggleRow(
                "fa5s.ruler-horizontal",
                tr_catalog("page.z1_control.advanced.wssize.title", language=self._ui_language, default="Включить --wssize"),
                tr_catalog("page.z1_control.advanced.wssize.desc", language=self._ui_language, default="Добавляет параметр размера окна TCP"),
            )
            if Win11ToggleRow
            else None
        )
        if self.wssize_toggle is not None:
            self.wssize_toggle.toggled.connect(self._on_wssize_toggled)

        self.debug_log_toggle = (
            Win11ToggleRow(
                "mdi.file-document-outline",
                tr_catalog("page.z1_control.advanced.debug_log.title", language=self._ui_language, default="Включить лог-файл (--debug)"),
                tr_catalog("page.z1_control.advanced.debug_log.desc", language=self._ui_language, default="Записывает логи winws в папку logs"),
            )
            if Win11ToggleRow
            else None
        )
        if self.debug_log_toggle is not None:
            self.debug_log_toggle.toggled.connect(self._on_debug_log_toggled)

        if PushSettingCard is not None:
            self.blobs_action_card = PushSettingCard(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                qta.icon("fa5s.file-archive", color="#ff9800"),
                tr_catalog("page.z1_control.blobs.title", language=self._ui_language, default="Блобы"),
                tr_catalog("page.z1_control.blobs.desc", language=self._ui_language, default="Бинарные данные (.bin / hex) для стратегий"),
            )
            self.blobs_action_card.clicked.connect(self.navigate_to_blobs.emit)
            self.blobs_open_btn = self.blobs_action_card.button
        else:
            self.blobs_action_card = None
            self.blobs_open_btn = None

        self.advanced_card, self.advanced_notice = build_advanced_settings_section(
            title=tr_catalog("page.z1_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"),
            warning_text=tr_catalog("page.z1_control.advanced.warning", language=self._ui_language, default="Изменяйте только если знаете что делаете"),
            parent=self.content,
            toggle_rows=[
                self.discord_restart_toggle,
                self.wssize_toggle,
                self.debug_log_toggle,
            ],
            action_rows=[self.blobs_action_card],
        )
        self.add_widget(self.advanced_card)

        self.add_spacing(16)

        # ── Дополнительные действия ────────────────────────────────────────
        if SettingCardGroup is not None and PushSettingCard is not None and _HAS_FLUENT:
            self.extra_section_label = None
            extra_group = SettingCardGroup(
                tr_catalog("page.z1_control.section.additional", language=self._ui_language, default="Дополнительные действия"),
                self.content,
            )
            self.extra_card = extra_group

            self.test_btn = None
            self.folder_btn = None
            self.docs_btn = None

            self.test_action_card = PushSettingCard(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                qta.icon("fa5s.wifi", color="#60cdff"),
                tr_catalog("page.z1_control.button.connection_test", language=self._ui_language, default="Тест соединения"),
                tr_catalog("page.z1_control.button.connection_test.desc", language=self._ui_language, default="Проверить доступность сети и состояние обхода"),
            )
            self.test_action_card.clicked.connect(self._open_connection_test)

            self.folder_action_card = PushSettingCard(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                qta.icon("fa5s.folder-open", color="#f5c04d"),
                tr_catalog("page.z1_control.button.open_folder", language=self._ui_language, default="Открыть папку"),
                tr_catalog("page.z1_control.button.open_folder.desc", language=self._ui_language, default="Перейти в папку программы и служебных файлов"),
            )
            self.folder_action_card.clicked.connect(self._open_folder)

            self.docs_action_card = PushSettingCard(
                tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"),
                qta.icon("fa5s.book", color="#8ab4f8"),
                tr_catalog("page.z1_control.button.documentation", language=self._ui_language, default="Документация"),
                tr_catalog("page.z1_control.button.documentation.desc", language=self._ui_language, default="Открыть справку и описание возможностей"),
            )
            self.docs_action_card.clicked.connect(self._open_docs)

            extra_group.addSettingCard(self.test_action_card)
            extra_group.addSettingCard(self.folder_action_card)
            extra_group.addSettingCard(self.docs_action_card)
            enable_setting_card_group_auto_height(extra_group)
            self.add_widget(extra_group)
        else:
            self.add_section_title(text_key="page.z1_control.section.additional")

            extra_card = SettingsCard()
            self.extra_card = extra_card
            extra_layout = QHBoxLayout()
            extra_layout.setSpacing(8)

            self.test_btn = ActionButton(
                tr_catalog("page.z1_control.button.connection_test", language=self._ui_language, default="Тест соединения"),
                "fa5s.wifi",
            )
            self.test_btn.clicked.connect(self._open_connection_test)
            extra_layout.addWidget(self.test_btn)

            self.folder_btn = ActionButton(
                tr_catalog("page.z1_control.button.open_folder", language=self._ui_language, default="Открыть папку"),
                "fa5s.folder-open",
            )
            self.folder_btn.clicked.connect(self._open_folder)
            extra_layout.addWidget(self.folder_btn)

            self.docs_btn = ActionButton(
                tr_catalog("page.z1_control.button.documentation", language=self._ui_language, default="Документация"),
                "fa5s.book",
            )
            self.docs_btn.clicked.connect(self._open_docs)
            extra_layout.addWidget(self.docs_btn)

            extra_layout.addStretch()
            extra_card.add_layout(extra_layout)
            self.test_action_card = None
            self.folder_action_card = None
            self.docs_action_card = None
            self.add_widget(extra_card)

    def _set_toggle_checked(self, toggle, checked: bool) -> None:
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
        try:
            toggle.blockSignals(False)
        except Exception:
            pass

    def _attach_program_settings_runtime(self) -> None:
        if self._program_settings_runtime_attached:
            return
        self._program_settings_runtime_attached = True
        self._get_program_settings_runtime_service().subscribe(
            self._apply_program_settings_snapshot,
            emit_initial=True,
        )

    def _apply_program_settings_snapshot(self, snapshot) -> None:
        self._set_toggle_checked(self.auto_dpi_toggle, getattr(snapshot, "auto_dpi_enabled", False))

    def _sync_program_settings(self) -> None:
        snapshot = self._get_program_settings_runtime_service().refresh()
        self._apply_program_settings_snapshot(snapshot)

    def _get_program_settings_runtime_service(self):
        app_context = getattr(self.window(), "app_context", None)
        service = getattr(app_context, "program_settings_runtime_service", None)
        if service is None:
            from core.services import get_program_settings_runtime_service

            service = get_program_settings_runtime_service()
        return service

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            plan = ControlPageController.save_auto_dpi(enabled)
            if InfoBar:
                InfoBar.success(title=plan.title, content=plan.message, parent=self.window())
        finally:
            self._sync_program_settings()

    def _set_status(self, msg: str) -> None:
        try:
            if self.parent_app and hasattr(self.parent_app, "set_status"):
                self.parent_app.set_status(msg)
        except Exception:
            pass

    def _load_preset_name(self) -> tuple[str, str]:
        try:
            payload = self._get_direct_ui_snapshot_service().load_basic_ui_payload("direct_zapret1", refresh=False)
            active_name = str(getattr(payload, "selected_preset_name", "") or "").strip()
            if active_name:
                return active_name, active_name
        except Exception:
            pass

        return (
            tr_catalog("page.z1_control.preset.not_selected", language=self._ui_language, default="Не выбран"),
            "",
        )

    def _load_advanced_settings_state(self, *, refresh: bool = False) -> dict:
        try:
            return self._get_direct_ui_snapshot_service().load_advanced_settings_state(
                "direct_zapret1",
                refresh=refresh,
            )
        except Exception:
            return {}

    def _apply_advanced_settings_state(self, state: dict | None) -> None:
        payload = state if isinstance(state, dict) else {}
        self._set_toggle_checked(
            self.discord_restart_toggle,
            bool(payload.get("discord_restart", True)),
        )
        self._set_toggle_checked(
            self.wssize_toggle,
            bool(payload.get("wssize_enabled", False)),
        )
        self._set_toggle_checked(
            self.debug_log_toggle,
            bool(payload.get("debug_log_enabled", False)),
        )
        self._advanced_settings_dirty = False

    def _refresh_advanced_settings(self, *, refresh: bool = False) -> None:
        self._apply_advanced_settings_state(
            self._load_advanced_settings_state(refresh=refresh)
        )

    def _apply_pending_advanced_settings_refresh(self) -> None:
        if not self._advanced_settings_dirty:
            return
        if not self.is_page_ready():
            return
        try:
            self._refresh_advanced_settings()
        except Exception:
            pass

    def _get_direct_ui_snapshot_service(self):
        app_context = getattr(self.window(), "app_context", None)
        service = getattr(app_context, "direct_ui_snapshot_service", None)
        if service is None:
            from core.services import get_direct_ui_snapshot_service

            service = get_direct_ui_snapshot_service()
        return service

    @staticmethod
    def _is_direct_zapret1_launch_active() -> bool:
        try:
            from strategy_menu import get_strategy_launch_method

            return str(get_strategy_launch_method() or "").strip().lower() == "direct_zapret1"
        except Exception:
            return False

    def _refresh_preset_name(self) -> None:
        text, tooltip = self._load_preset_name()
        self.preset_name_label.setText(text)
        set_tooltip(self.preset_name_label, tooltip)
        self._preset_name_runtime.mark_applied()

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_wssize_toggled(self, enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").set_wssize_enabled(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").set_debug_log_enabled(bool(enabled))
            self._advanced_settings_dirty = False
        except Exception:
            pass

    def _open_strategies_page(self) -> None:
        self.navigate_to_strategies.emit()

    def set_loading(self, loading: bool, text: str = ""):
        if _HAS_FLUENT:
            if loading:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()
        self.progress_bar.setVisible(loading)
        self.loading_label.setVisible(loading and bool(text))
        self.loading_label.setText(text)
        self.start_btn.setEnabled(not loading)
        self.stop_winws_btn.setEnabled(not loading)
        self.stop_and_exit_btn.setEnabled(not loading)

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
            fields={"dpi_phase", "dpi_running", "dpi_busy", "dpi_busy_text", "dpi_last_error", "current_strategy_summary", "active_preset_revision"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        changed = set(changed_fields or ())
        if "active_preset_revision" in changed:
            self._preset_name_runtime.mark_dirty()
            self._advanced_settings_dirty = True
            if self.isVisible():
                self._refresh_preset_name()
                self._refresh_advanced_settings()
            else:
                self.run_when_page_ready(self._apply_pending_preset_name_refresh)
                self.run_when_page_ready(self._apply_pending_advanced_settings_refresh)
        self.set_loading(bool(state.dpi_busy), str(state.dpi_busy_text or ""))
        self.update_status(
            state.dpi_phase or ("running" if state.dpi_running else "stopped"),
            str(state.dpi_last_error or ""),
        )
        self.update_strategy(str(state.current_strategy_summary or ""))

    def _get_current_dpi_runtime_state(self) -> tuple[str, str]:
        """Берёт текущую фазу DPI из общего store, а не из видимости кнопок."""
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
            last_known_dpi_running=bool(getattr(self, "_last_known_dpi_running", False)),
        )
        return plan.phase, plan.last_error

    def update_status(self, state: str | bool, last_error: str = ""):
        phase = str(state or "").strip().lower()
        if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        if phase == "running":
            title = tr_catalog("page.z1_control.status.running", language=self._ui_language, default="Zapret 1 работает")
            description = tr_catalog(
                "page.z1_control.status.bypass_active",
                language=self._ui_language,
                default="Обход блокировок активен",
            )
            dot_color = "#6ccb5f"
            pulsing = True
            show_start = False
            show_stop_only = True
            show_stop_and_exit = True
        elif phase == "autostart_pending":
            title = "Автозапуск Zapret 1 запланирован"
            description = "Подготавливаем стартовый запуск выбранного пресета"
            dot_color = "#f5a623"
            pulsing = True
            show_start = False
            show_stop_only = False
            show_stop_and_exit = False
        elif phase == "starting":
            title = "Zapret 1 запускается"
            description = "Ждём подтверждение процесса winws.exe"
            dot_color = "#f5a623"
            pulsing = True
            show_start = False
            show_stop_only = False
            show_stop_and_exit = False
        elif phase == "stopping":
            title = "Zapret 1 останавливается"
            description = "Завершаем winws.exe и освобождаем WinDivert"
            dot_color = "#f5a623"
            pulsing = True
            show_start = False
            show_stop_only = False
            show_stop_and_exit = False
        elif phase == "failed":
            title = "Ошибка запуска Zapret 1"
            description = ControlPageController.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу"
            dot_color = "#ff6b6b"
            pulsing = False
            show_start = True
            show_stop_only = False
            show_stop_and_exit = False
        else:
            phase = "stopped"
            title = tr_catalog("page.z1_control.status.stopped", language=self._ui_language, default="Zapret 1 остановлен")
            description = tr_catalog(
                "page.z1_control.status.press_start",
                language=self._ui_language,
                default="Нажмите «Запустить» для активации",
            )
            dot_color = "#ff6b6b"
            pulsing = False
            show_start = True
            show_stop_only = False
            show_stop_and_exit = False

        self._last_known_dpi_running = phase == "running"
        self.status_title.setText(title)
        self.status_desc.setText(description)
        self.status_dot.set_color(dot_color)
        if pulsing:
            self.status_dot.start_pulse()
        else:
            self.status_dot.stop_pulse()
        self.start_btn.setVisible(show_start)
        self.stop_winws_btn.setVisible(show_stop_only)
        self.stop_and_exit_btn.setVisible(show_stop_and_exit)

    def update_strategy(self, name: str):
        _ = name
        if not self.isVisible():
            self._preset_name_runtime.mark_dirty()
            self.run_when_page_ready(self._apply_pending_preset_name_refresh)
            return
        self._refresh_preset_name()

    def update_current_strategy(self, name: str):
        _ = name
        if not self.isVisible():
            self._preset_name_runtime.mark_dirty()
            self.run_when_page_ready(self._apply_pending_preset_name_refresh)
            return
        self._refresh_preset_name()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.start_btn.setText(tr_catalog("page.z1_control.button.start", language=self._ui_language, default="Запустить Zapret"))
        self.stop_winws_btn.setText(
            tr_catalog("page.z1_control.button.stop_winws", language=self._ui_language, default="Остановить winws.exe")
        )
        self.stop_and_exit_btn.setText(
            tr_catalog("page.z1_control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть")
        )
        self.presets_btn.setText(tr_catalog("page.z1_control.button.my_presets", language=self._ui_language, default="Мои пресеты"))
        self.open_strat_btn.setText(tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть"))

        if self.preset_caption_label is not None:
            self.preset_caption_label.setText(
                tr_catalog("page.z1_control.preset.current", language=self._ui_language, default="Текущий активный пресет")
            )
        self.strategies_title_label.setText(
            tr_catalog("page.z1_control.strategies.title", language=self._ui_language, default="Стратегии по категориям")
        )
        if self.strategies_desc_label is not None:
            self.strategies_desc_label.setText(
                tr_catalog("page.z1_control.strategies.desc", language=self._ui_language, default="Выбор стратегии для YouTube, Discord и др.")
            )

        title_label = getattr(getattr(self, "program_settings_card", None), "titleLabel", None)
        if title_label is not None:
            title_label.setText(
                tr_catalog("page.z1_control.section.program_settings", language=self._ui_language, default="Настройки программы")
            )
        extra_title_label = getattr(getattr(self, "extra_card", None), "titleLabel", None)
        if extra_title_label is not None:
            extra_title_label.setText(
                tr_catalog("page.z1_control.section.additional", language=self._ui_language, default="Дополнительные действия")
            )
        self.auto_dpi_toggle.set_texts(
            tr_catalog("page.z1_control.setting.autostart.title", language=self._ui_language, default="Автозапуск DPI после старта программы"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=self._ui_language, default="После запуска ZapretGUI автоматически запускать текущий DPI-режим")
        )
        try:
            if getattr(self, "test_action_card", None) is not None:
                self.test_action_card.setTitle(
                    tr_catalog("page.z1_control.button.connection_test", language=self._ui_language, default="Тест соединения")
                )
                self.test_action_card.setContent(
                    tr_catalog("page.z1_control.button.connection_test.desc", language=self._ui_language, default="Проверить доступность сети и состояние обхода")
                )
                self.test_action_card.button.setText(
                    tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть")
                )
            elif self.test_btn is not None:
                self.test_btn.setText(
                    tr_catalog("page.z1_control.button.connection_test", language=self._ui_language, default="Тест соединения")
                )

            if getattr(self, "folder_action_card", None) is not None:
                self.folder_action_card.setTitle(
                    tr_catalog("page.z1_control.button.open_folder", language=self._ui_language, default="Открыть папку")
                )
                self.folder_action_card.setContent(
                    tr_catalog("page.z1_control.button.open_folder.desc", language=self._ui_language, default="Перейти в папку программы и служебных файлов")
                )
                self.folder_action_card.button.setText(
                    tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть")
                )
            elif self.folder_btn is not None:
                self.folder_btn.setText(
                    tr_catalog("page.z1_control.button.open_folder", language=self._ui_language, default="Открыть папку")
                )

            if getattr(self, "docs_action_card", None) is not None:
                self.docs_action_card.setTitle(
                    tr_catalog("page.z1_control.button.documentation", language=self._ui_language, default="Документация")
                )
                self.docs_action_card.setContent(
                    tr_catalog("page.z1_control.button.documentation.desc", language=self._ui_language, default="Открыть справку и описание возможностей")
                )
                self.docs_action_card.button.setText(
                    tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть")
                )
            elif self.docs_btn is not None:
                self.docs_btn.setText(
                    tr_catalog("page.z1_control.button.documentation", language=self._ui_language, default="Документация")
                )
        except Exception:
            pass
        try:
            if hasattr(self.advanced_card, "set_title"):
                self.advanced_card.set_title(
                    tr_catalog("page.z1_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
                )
            title_label = getattr(self.advanced_card, "titleLabel", None)
            if title_label is not None:
                title_label.setText(
                    tr_catalog("page.z1_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
                )
        except Exception:
            pass
        try:
            self.advanced_notice.setText(
                tr_catalog("page.z1_control.advanced.warning", language=self._ui_language, default="Изменяйте только если знаете что делаете")
            )
        except Exception:
            pass
        try:
            self.discord_restart_toggle.set_texts(
                tr_catalog("page.z1_control.advanced.discord_restart.title", language=self._ui_language, default="Перезапуск Discord"),
                tr_catalog("page.z1_control.advanced.discord_restart.desc", language=self._ui_language, default="Автоперезапуск при смене стратегии"),
            )
        except Exception:
            pass
        try:
            self.wssize_toggle.set_texts(
                tr_catalog("page.z1_control.advanced.wssize.title", language=self._ui_language, default="Включить --wssize"),
                tr_catalog("page.z1_control.advanced.wssize.desc", language=self._ui_language, default="Добавляет параметр размера окна TCP"),
            )
        except Exception:
            pass
        try:
            self.debug_log_toggle.set_texts(
                tr_catalog("page.z1_control.advanced.debug_log.title", language=self._ui_language, default="Включить лог-файл (--debug)"),
                tr_catalog("page.z1_control.advanced.debug_log.desc", language=self._ui_language, default="Записывает логи winws в папку logs"),
            )
        except Exception:
            pass
        if getattr(self, "blobs_action_card", None) is not None:
            self.blobs_action_card.setTitle(
                tr_catalog("page.z1_control.blobs.title", language=self._ui_language, default="Блобы")
            )
            self.blobs_action_card.setContent(
                tr_catalog("page.z1_control.blobs.desc", language=self._ui_language, default="Бинарные данные (.bin / hex) для стратегий")
            )
            if getattr(self, "blobs_open_btn", None) is not None:
                self.blobs_open_btn.setText(
                    tr_catalog("page.z1_control.button.open", language=self._ui_language, default="Открыть")
                )

        self._refresh_preset_name()
        phase, last_error = self._get_current_dpi_runtime_state()
        self.update_status(phase, last_error)
