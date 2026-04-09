# ui/pages/zapret1/direct_control_page.py
"""Direct Zapret1 management page (entry point for direct_zapret1 mode)."""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
)
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, PrimaryActionButton, PulsingDot, SettingsCard, set_tooltip
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.window_action_controller import start_dpi, stop_and_exit, stop_dpi

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
        super().__init__(text, icon_name, accent=False, parent=parent)


class Zapret1DirectControlPage(BasePage):
    """Страница управления для direct_zapret1 (главная вкладка раздела «Стратегии»)."""

    navigate_to_strategies = pyqtSignal()   # → PageName.ZAPRET1_DIRECT
    navigate_to_presets = pyqtSignal()       # → PageName.ZAPRET1_USER_PRESETS

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
        self.enable_deferred_ui_build()

    def _start_dpi(self) -> None:
        start_dpi(self)

    def _stop_dpi(self) -> None:
        stop_dpi(self)

    def _stop_and_exit(self) -> None:
        stop_and_exit(self)

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        try:
            self._sync_program_settings()
        except Exception:
            pass
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

        # Card A — Выбранный source-пресет
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
        self.add_widget(preset_card)

        self.add_spacing(8)

        # Card B — Стратегии
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
            tr_catalog("page.z1_control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы"),
        )
        self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)

        add_setting_card = getattr(program_settings_card, "addSettingCard", None)
        if callable(add_setting_card):
            add_setting_card(self.auto_dpi_toggle)
        else:
            program_settings_card.add_widget(self.auto_dpi_toggle)

        self.add_widget(program_settings_card)

        self._sync_program_settings()

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

    def _sync_program_settings(self) -> None:
        try:
            from config import get_dpi_autostart
            self._set_toggle_checked(self.auto_dpi_toggle, bool(get_dpi_autostart()))
        except Exception:
            pass

    def _on_auto_dpi_toggled(self, enabled: bool) -> None:
        try:
            from config import set_dpi_autostart
            set_dpi_autostart(bool(enabled))
            if InfoBar:
                msg = "DPI будет включаться автоматически" if enabled else "Автозагрузка DPI отключена"
                InfoBar.success(title="Автозагрузка DPI", content=msg, parent=self.window())
        finally:
            self._sync_program_settings()

    def _set_status(self, msg: str) -> None:
        try:
            if self.parent_app and hasattr(self.parent_app, "set_status"):
                self.parent_app.set_status(msg)
        except Exception:
            pass

    def _refresh_preset_name(self) -> None:
        try:
            from core.services import get_direct_flow_coordinator

            preset = get_direct_flow_coordinator().get_selected_source_manifest("direct_zapret1")
            active_name = str(getattr(preset, "name", "") or "").strip()
            if active_name:
                self.preset_name_label.setText(active_name)
                set_tooltip(self.preset_name_label, active_name)
            else:
                self.preset_name_label.setText(
                    tr_catalog("page.z1_control.preset.not_selected", language=self._ui_language, default="Не выбран")
                )
        except Exception:
            pass

    def _prewarm_direct_payload(self) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").get_basic_ui_payload()
        except Exception:
            pass

    def _open_strategies_page(self) -> None:
        self._prewarm_direct_payload()
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
        if "active_preset_revision" in changed_fields:
            if self.isVisible():
                self._refresh_preset_name()
        self.set_loading(state.dpi_busy, state.dpi_busy_text)
        self.update_status(state.dpi_phase or ("running" if state.dpi_running else "stopped"), state.dpi_last_error)
        self.update_strategy(state.current_strategy_summary or "")

    def _get_current_dpi_runtime_state(self) -> tuple[str, str]:
        """Берёт текущую фазу DPI из общего store, а не из видимости кнопок."""
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                phase = str(snapshot.dpi_phase or "").strip().lower() or ("running" if snapshot.dpi_running else "stopped")
                return phase, str(snapshot.dpi_last_error or "").strip()
            except Exception:
                pass
        return ("running" if bool(getattr(self, "_last_known_dpi_running", False)) else "stopped"), ""

    @staticmethod
    def _short_dpi_error(last_error: str) -> str:
        text = str(last_error or "").strip()
        if not text:
            return ""
        first_line = text.splitlines()[0].strip()
        if len(first_line) <= 160:
            return first_line
        return first_line[:157] + "..."

    def update_status(self, state: str | bool, last_error: str = ""):
        phase = str(state or "").strip().lower()
        if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        self._last_known_dpi_running = phase == "running"
        if phase == "running":
            self.status_title.setText(
                tr_catalog("page.z1_control.status.running", language=self._ui_language, default="Zapret 1 работает")
            )
            self.status_desc.setText(
                tr_catalog("page.z1_control.status.bypass_active", language=self._ui_language, default="Обход блокировок активен")
            )
            self.status_dot.set_color("#6ccb5f")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(True)
            self.stop_and_exit_btn.setVisible(True)
        elif phase == "autostart_pending":
            self.status_title.setText("Автозапуск Zapret 1 запланирован")
            self.status_desc.setText("Подготавливаем стартовый запуск выбранного пресета")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "starting":
            self.status_title.setText("Zapret 1 запускается")
            self.status_desc.setText("Ждём подтверждение процесса winws.exe")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "stopping":
            self.status_title.setText("Zapret 1 останавливается")
            self.status_desc.setText("Завершаем winws.exe и освобождаем WinDivert")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "failed":
            self.status_title.setText("Ошибка запуска Zapret 1")
            self.status_desc.setText(self._short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу")
            self.status_dot.set_color("#ff6b6b")
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        else:
            self.status_title.setText(
                tr_catalog("page.z1_control.status.stopped", language=self._ui_language, default="Zapret 1 остановлен")
            )
            self.status_desc.setText(
                tr_catalog("page.z1_control.status.press_start", language=self._ui_language, default="Нажмите «Запустить» для активации")
            )
            self.status_dot.set_color("#ff6b6b")
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)

    def update_strategy(self, name: str):
        self._refresh_preset_name()

    def update_current_strategy(self, name: str):
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
        self.auto_dpi_toggle.set_texts(
            tr_catalog("page.z1_control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog("page.z1_control.setting.autostart.desc", language=self._ui_language, default="Запускать Zapret автоматически при старте программы")
        )

        self._refresh_preset_name()
        phase, last_error = self._get_current_dpi_runtime_state()
        self.update_status(phase, last_error)
