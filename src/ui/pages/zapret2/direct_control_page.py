# ui/pages/zapret2/direct_control_page.py
"""Direct Zapret2 management page (Strategies landing for direct_zapret2)."""

import os
import re
import time as _time
import webbrowser

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    PulsingDot,
    ResetActionButton,
    SettingsCard,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.theme import get_theme_tokens
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
        SegmentedWidget, MessageBoxBase, CardWidget,
        PushButton, TransparentPushButton, FluentIcon, SettingCardGroup, PushSettingCard,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    MessageBox = None
    InfoBar = None
    MessageBoxBase = object  # type: ignore[assignment]
    SegmentedWidget = None  # type: ignore[assignment]
    CardWidget = None  # type: ignore[assignment]
    PushButton = None  # type: ignore[assignment]
    TransparentPushButton = None  # type: ignore[assignment]
    FluentIcon = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    _HAS_FLUENT_LABELS = False


class DirectLaunchModeDialog(MessageBoxBase):
    """Диалог выбора Basic / Advanced режима прямого запуска."""

    def __init__(self, current_mode: str, parent=None, language: str | None = None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.title",
                language=language,
                default="Режим прямого запуска",
            ),
            self.widget,
        )
        self.mode_seg = SegmentedWidget(self.widget)
        self.mode_seg.addItem(
            "basic",
            tr_catalog("page.z2_control.mode.basic", language=language, default="Basic"),
        )
        self.mode_seg.addItem(
            "advanced",
            tr_catalog("page.z2_control.mode.advanced", language=language, default="Advanced"),
        )
        self.mode_seg.setCurrentItem(
            current_mode if current_mode in ("basic", "advanced") else "basic"
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.description",
                language=language,
                default=(
                    "Прямой запуск поддерживает несколько режимов: упрощенный и расширенный для профи. "
                    "Настройки не сохраняются между режимами Вы можете выбрать любой. Рекомендуем начать с базового. "
                    "Бывает что базовый из-за готовых стратегий плохо пробивает сайты, тогда рекомендуем попробовать "
                    "продвинутый в котором можно более тонко настроить техники дурения."
                ),
            ),
            self.widget,
        )
        self.basic_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.basic_description",
                language=language,
                default=(
                    "Basic (базовый) — готовая таблица стратегий без понятия фаз. "
                    "Собирать свои стратегии нельзя."
                ),
            ),
            self.widget,
        )
        self.adv_desc = BodyLabel(
            tr_catalog(
                "page.z2_control.mode.dialog.advanced_description",
                language=language,
                default=(
                    "Advanced (продвинутый) — каждая функция настраивается индивидуально, "
                    "можно выбирать несколько фаз и смешивать их друг с другом."
                ),
            ),
            self.widget,
        )
        self.basic_desc.setWordWrap(True)
        self.adv_desc.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.mode_seg)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.basic_desc)
        self.viewLayout.addWidget(self.adv_desc)
        self.yesButton.setText(tr_catalog("page.z2_control.mode.dialog.button.apply", language=language, default="Применить"))
        self.cancelButton.setText(tr_catalog("page.z2_control.mode.dialog.button.cancel", language=language, default="Отмена"))
        self.widget.setMinimumWidth(440)

    def get_mode(self) -> str:
        return self.mode_seg.currentRouteKey()


def _accent_fg_for_tokens(tokens) -> str:
    try:
        r, g, b = tokens.accent_rgb
        yiq = (r * 299 + g * 587 + b * 114) / 1000
        return "rgba(0, 0, 0, 0.90)" if yiq >= 160 else "rgba(245, 245, 245, 0.92)"
    except Exception:
        return "rgba(0, 0, 0, 0.90)"


_LIST_FILE_ARG_RE = re.compile(r"--(?:hostlist|ipset|hostlist-exclude|ipset-exclude)=([^\s]+)")
# Display only hostlist files (not ipset) in the preset card widget
_HOSTLIST_DISPLAY_RE = re.compile(r"--(?:hostlist|hostlist-exclude)=([^\s]+)")


def _log_startup_z2_control_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    from log import log as _log

    _log(f"⏱ Startup UI Section: ZAPRET2_DIRECT_CONTROL {section} {rounded}ms", "⏱ STARTUP")


class _AdvancedSettingsLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        state: dict = {}
        try:
            from core.presets.direct_facade import DirectPresetFacade

            state = DirectPresetFacade.from_launch_method("direct_zapret2").get_advanced_settings_state() or {}
        except Exception:
            state = {}
        self.loaded.emit(self._request_id, state)


class _DirectPresetSummaryLoadWorker(QThread):
    loaded = pyqtSignal(int, dict)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        self.loaded.emit(self._request_id, _load_direct_zapret2_preset_summary_payload())


def _load_direct_zapret2_preset_summary_payload() -> dict:
    payload: dict = {
        "active_preset_name": "",
        "active_lists": [],
    }
    try:
        from core.services import get_direct_flow_coordinator
        from core.presets.direct_facade import DirectPresetFacade

        preset = get_direct_flow_coordinator().get_selected_source_manifest("direct_zapret2")
        payload["active_preset_name"] = str(getattr(preset, "name", "") or "").strip()

        facade = DirectPresetFacade.from_launch_method("direct_zapret2")
        source_text = facade.read_selected_source_text()
        active_lists: list[str] = []
        seen_lists: set[str] = set()
        for raw in str(source_text or "").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for value in _HOSTLIST_DISPLAY_RE.findall(stripped):
                list_path = value.strip().strip('"').strip("'")
                if not list_path:
                    continue

                normalized = list_path.replace("\\", "/")
                list_name = normalized.rsplit("/", 1)[-1]
                if not list_name:
                    continue

                dedupe_key = list_name.lower()
                if dedupe_key in seen_lists:
                    continue
                seen_lists.add(dedupe_key)
                active_lists.append(list_name)
        payload["active_lists"] = active_lists
    except Exception:
        pass

    return payload


class BigActionButton(PrimaryActionButton):
    """Большая кнопка запуска (акцентная, PrimaryPushButton)."""

    def __init__(self, text: str, icon_name: str | None = None, accent: bool = True, parent=None):
        super().__init__(text, icon_name, parent)


class StopButton(ActionButton):
    """Кнопка остановки (нейтральная, PushButton)."""

    def __init__(self, text: str, icon_name: str | None = None, accent: bool = False, parent=None):
        super().__init__(text, icon_name, accent=False, parent=parent)


class Zapret2DirectControlPage(BasePage):
    """Страница управления для direct_zapret2 (главная вкладка раздела "Стратегии")."""

    navigate_to_presets = pyqtSignal()        # → PageName.ZAPRET2_USER_PRESETS
    navigate_to_direct_launch = pyqtSignal()  # → PageName.ZAPRET2_DIRECT
    navigate_to_blobs = pyqtSignal()          # → PageName.BLOBS
    direct_mode_changed = pyqtSignal(str)     # "basic" | "advanced"
    deferred_show_requested = pyqtSignal()

    def __init__(self, parent=None):
        _t_init = _time.perf_counter()
        _t_base = _time.perf_counter()
        super().__init__(
            "Управление",
            "Настройка и запуск Zapret 2. Выберите готовые пресеты-конфиги (как раньше .bat), "
            "а при необходимости выполните тонкую настройку для каждого target'а в разделе «Прямой запуск».",
            parent,
            title_key="page.z2_control.title",
            subtitle_key="page.z2_control.subtitle",
        )
        _log_startup_z2_control_metric("__init__.base_page", (_time.perf_counter() - _t_base) * 1000)

        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._startup_showevent_profile_logged = False
        self._advanced_settings_worker = None
        self._advanced_settings_request_id = 0
        self._advanced_settings_dirty = True
        self._preset_summary_worker = None
        self._preset_summary_request_id = 0
        self._preset_summary_dirty = True
        self.deferred_show_requested.connect(
            self._run_deferred_show_work,
            Qt.ConnectionType.QueuedConnection,
        )
        self.enable_deferred_ui_build(after_build=self._after_ui_built)
        _log_startup_z2_control_metric("__init__.total", (_time.perf_counter() - _t_init) * 1000)

    def _after_ui_built(self) -> None:
        try:
            self._apply_optimistic_startup_view()
        except Exception:
            pass
        self._update_stop_winws_button_text()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        theme_tokens = tokens or get_theme_tokens()

        try:
            if hasattr(self, "advanced_desc") and self.advanced_desc is not None:
                self.advanced_desc.setStyleSheet(
                    f"color: #ff9800; padding-bottom: 8px; font-family: {theme_tokens.font_family_qss};"
                )
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

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        _t_show = _time.perf_counter()
        _t_sync = _time.perf_counter()
        try:
            self._sync_program_settings()
        except Exception:
            pass
        _log_startup_z2_control_metric("showEvent.sync_program_settings", (_time.perf_counter() - _t_sync) * 1000)
        self.deferred_show_requested.emit()
        if not self._startup_showevent_profile_logged:
            self._startup_showevent_profile_logged = True
            _log_startup_z2_control_metric("activation.total", (_time.perf_counter() - _t_show) * 1000)

    def _run_deferred_show_work(self) -> None:
        if not self.isVisible():
            return

        _t_adv = _time.perf_counter()
        self._schedule_advanced_settings_reload()
        self._schedule_preset_summary_reload()
        _log_startup_z2_control_metric("showEvent.load_advanced_settings", (_time.perf_counter() - _t_adv) * 1000)

        _t_mode = _time.perf_counter()
        try:
            self._refresh_direct_mode_label()
        except Exception:
            pass
        _log_startup_z2_control_metric("showEvent.refresh_mode_label", (_time.perf_counter() - _t_mode) * 1000)

    def _prewarm_direct_payload(self) -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").get_basic_ui_payload()
        except Exception:
            pass

    def _open_direct_launch_page(self) -> None:
        self._prewarm_direct_payload()
        self.navigate_to_direct_launch.emit()

    def _build_ui(self):
        _t_total = _time.perf_counter()
        # Статус работы
        _t_status = _time.perf_counter()
        self.status_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.status",
        )

        status_card = SettingsCard()
        self.status_card = status_card
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)

        self.status_dot = PulsingDot()
        status_layout.addWidget(self.status_dot)

        status_text = QVBoxLayout()
        status_text.setContentsMargins(0, 0, 0, 0)
        status_text.setSpacing(2)

        if _HAS_FLUENT_LABELS:
            self.status_title = StrongBodyLabel(tr_catalog("page.z2_control.status.checking", language=self._ui_language, default="Проверка..."))
            self.status_desc = CaptionLabel(tr_catalog("page.z2_control.status.detecting", language=self._ui_language, default="Определение состояния процесса"))
        else:
            self.status_title = QLabel(tr_catalog("page.z2_control.status.checking", language=self._ui_language, default="Проверка..."))
            self.status_title.setStyleSheet("QLabel { font-size: 15px; font-weight: 600; }")
            self.status_desc = QLabel(tr_catalog("page.z2_control.status.detecting", language=self._ui_language, default="Определение состояния процесса"))
            self.status_desc.setStyleSheet("QLabel { font-size: 12px; }")
        status_text.addWidget(self.status_title)
        status_text.addWidget(self.status_desc)

        status_layout.addLayout(status_text, 1)
        status_card.add_layout(status_layout)
        self.add_widget(status_card)
        _log_startup_z2_control_metric("_build_ui.status_card", (_time.perf_counter() - _t_status) * 1000)

        self.add_spacing(16)

        # Управление
        _t_control = _time.perf_counter()
        self.control_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.management",
        )

        control_card = SettingsCard()
        self.control_card_card = control_card

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.start_btn = BigActionButton(tr_catalog("page.z2_control.button.start", language=self._ui_language, default="Запустить Zapret"), "fa5s.play", accent=True)
        self.start_btn.clicked.connect(self._start_dpi)
        buttons_layout.addWidget(self.start_btn)

        self.stop_winws_btn = StopButton(tr_catalog("page.z2_control.button.stop_only_winws", language=self._ui_language, default="Остановить только winws.exe"), "fa5s.stop")
        self.stop_winws_btn.clicked.connect(self._stop_dpi)
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)

        self.stop_and_exit_btn = StopButton(tr_catalog("page.z2_control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу"), "fa5s.power-off")
        self.stop_and_exit_btn.clicked.connect(self._stop_and_exit)
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)

        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)

        # Индикатор загрузки держим под кнопками, чтобы при показе
        # не сдвигать основной ряд действий вниз.
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        control_card.add_widget(self.progress_bar)

        if _HAS_FLUENT_LABELS:
            self.loading_label = CaptionLabel("")
        else:
            self.loading_label = QLabel("")
            self.loading_label.setStyleSheet("QLabel { font-size: 12px; padding-top: 4px; }")
        self.loading_label.setVisible(False)
        control_card.add_widget(self.loading_label)
        self.add_widget(control_card)
        _log_startup_z2_control_metric("_build_ui.control_card", (_time.perf_counter() - _t_control) * 1000)

        self.add_spacing(16)

        # ── Запуск: две вертикальные WinUI-карточки ──────────────────────
        _t_preset = _time.perf_counter()
        self.preset_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.preset_switch",
        )

        # Card A — Выбранный source-пресет (single-row: icon | text | button)
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
        self.preset_name_label = StrongBodyLabel(tr_catalog("page.z2_control.preset.not_selected", language=self._ui_language, default="Не выбран"))
        if _HAS_FLUENT_LABELS:
            self.strategy_label = CaptionLabel(tr_catalog("page.z2_control.preset.no_active_lists", language=self._ui_language, default="Нет активных листов"))
        else:
            self.strategy_label = QLabel(tr_catalog("page.z2_control.preset.no_active_lists", language=self._ui_language, default="Нет активных листов"))
            self.strategy_label.setStyleSheet("QLabel { font-size: 11px; }")
        self.strategy_label.setWordWrap(True)
        self.strategy_label.setVisible(False)
        preset_col.addWidget(self.preset_name_label)
        self.current_preset_caption = CaptionLabel(tr_catalog("page.z2_control.preset.current", language=self._ui_language, default="Текущий активный пресет"))
        preset_col.addWidget(self.current_preset_caption)
        preset_row.addLayout(preset_col, 1)

        presets_btn = PushButton()
        presets_btn.setText(tr_catalog("page.z2_control.button.my_presets", language=self._ui_language, default="Мои пресеты"))
        presets_btn.setIcon(FluentIcon.FOLDER)
        presets_btn.clicked.connect(self.navigate_to_presets.emit)
        preset_row.addWidget(presets_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.presets_btn = presets_btn
        self.add_widget(preset_card)
        _log_startup_z2_control_metric("_build_ui.preset_card", (_time.perf_counter() - _t_preset) * 1000)

        self.add_spacing(8)

        # ── Запуск: две вертикальные WinUI-карточки ──────────────────────
        _t_direct = _time.perf_counter()
        self.direct_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.direct_tuning",
        )

        # Card B — Прямой запуск (single-row: icon | text | buttons)
        direct_card = CardWidget()
        self.direct_card = direct_card
        direct_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        direct_row = QHBoxLayout(direct_card)
        direct_row.setContentsMargins(16, 14, 16, 14)
        direct_row.setSpacing(12)

        direct_icon_lbl = QLabel()
        direct_icon_lbl.setPixmap(qta.icon("fa5s.play", color="#60cdff").pixmap(20, 20))
        direct_icon_lbl.setFixedSize(24, 24)
        direct_row.addWidget(direct_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        direct_col = QVBoxLayout()
        direct_col.setSpacing(2)
        self.direct_mode_label = StrongBodyLabel(tr_catalog("page.z2_control.mode.basic", language=self._ui_language, default="Basic"))
        direct_col.addWidget(self.direct_mode_label)
        self.direct_mode_caption = CaptionLabel(tr_catalog("page.z2_control.direct_mode.caption", language=self._ui_language, default="Режим прямого запуска"))
        direct_col.addWidget(self.direct_mode_caption)
        direct_row.addLayout(direct_col, 1)

        direct_btns = QHBoxLayout()
        direct_btns.setSpacing(4)
        open_btn = PushButton()
        open_btn.setText(tr_catalog("page.z2_control.button.open", language=self._ui_language, default="Открыть"))
        open_btn.setIcon(FluentIcon.PLAY)
        open_btn.clicked.connect(self._open_direct_launch_page)
        mode_btn = TransparentPushButton()
        mode_btn.setText(tr_catalog("page.z2_control.button.change_mode", language=self._ui_language, default="Изменить режим"))
        mode_btn.clicked.connect(self._open_direct_mode_dialog)
        direct_btns.addWidget(open_btn)
        direct_btns.addWidget(mode_btn)
        self.direct_open_btn = open_btn
        self.direct_mode_btn = mode_btn
        direct_row.addLayout(direct_btns)
        self.add_widget(direct_card)
        _log_startup_z2_control_metric("_build_ui.direct_card", (_time.perf_counter() - _t_direct) * 1000)

        self.add_spacing(8)

        self.add_spacing(16)

        # Настройки программы
        _t_program = _time.perf_counter()
        program_settings_title = tr_catalog(
            "page.z2_control.section.program_settings",
            language=self._ui_language,
            default="Настройки программы",
        )
        if SettingCardGroup is not None and PushSettingCard is not None and _HAS_FLUENT_LABELS:
            self.program_settings_section_label = None
            program_settings_card = SettingCardGroup(program_settings_title, self.content)
        else:
            self.program_settings_section_label = self.add_section_title(
                return_widget=True,
                text_key="page.z2_control.section.program_settings",
            )
            program_settings_card = SettingsCard()
        self.program_settings_card = program_settings_card

        _t_program_toggles = _time.perf_counter()
        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None  # type: ignore[assignment]

        if Win11ToggleRow is None:
            raise RuntimeError("Win11ToggleRow недоступен для страницы управления Zapret 2")

        self.auto_dpi_toggle = Win11ToggleRow(
            "fa5s.bolt",
            tr_catalog("page.z2_control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog(
                "page.z2_control.setting.autostart.desc",
                language=self._ui_language,
                default="Запускать Zapret автоматически при старте программы",
            ),
        )
        self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)

        self.defender_toggle = Win11ToggleRow(
            "fa5s.shield-alt",
            tr_catalog(
                "page.z2_control.setting.defender.title",
                language=self._ui_language,
                default="Отключить Windows Defender",
            ),
            tr_catalog(
                "page.z2_control.setting.defender.desc",
                language=self._ui_language,
                default="Требуются права администратора",
            ),
        )
        self.defender_toggle.toggled.connect(self._on_defender_toggled)

        self.max_block_toggle = Win11ToggleRow(
            "fa5s.ban",
            tr_catalog(
                "page.z2_control.setting.max_block.title",
                language=self._ui_language,
                default="Блокировать установку MAX",
            ),
            tr_catalog(
                "page.z2_control.setting.max_block.desc",
                language=self._ui_language,
                default="Блокирует запуск/установку MAX и домены в hosts",
            ),
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
        _log_startup_z2_control_metric("_build_ui.toggle_setup", (_time.perf_counter() - _t_program_toggles) * 1000)

        self.reset_program_card = None
        self.reset_program_btn = None
        self._reset_program_desc_label = None
        if callable(add_setting_card) and PushSettingCard is not None:
            self.reset_program_card = PushSettingCard(
                tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить"),
                qta.icon("fa5s.undo", color="#ff9800"),
                tr_catalog("page.z2_control.setting.reset.title", language=self._ui_language, default="Сбросить программу"),
                tr_catalog(
                    "page.z2_control.setting.reset.desc",
                    language=self._ui_language,
                    default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
                ),
            )
            self.reset_program_card.clicked.connect(self._confirm_reset_program_clicked)
            add_setting_card(self.reset_program_card)
            self.add_widget(program_settings_card)
        else:
            self.reset_program_btn = ResetActionButton(
                tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить"),
                confirm_text=tr_catalog("page.z2_control.button.reset_confirm", language=self._ui_language, default="Сбросить?"),
            )
            self.reset_program_btn.setProperty("noDrag", True)
            self.reset_program_btn.reset_confirmed.connect(self._on_reset_program_clicked)
            reset_card = SettingsCard(
                tr_catalog("page.z2_control.setting.reset.title", language=self._ui_language, default="Сбросить программу")
            )
            reset_desc_label = CaptionLabel(
                tr_catalog(
                    "page.z2_control.setting.reset.desc",
                    language=self._ui_language,
                    default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
                )
            ) if _HAS_FLUENT_LABELS else QLabel(
                tr_catalog(
                    "page.z2_control.setting.reset.desc",
                    language=self._ui_language,
                    default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
                )
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
        enable_setting_card_group_auto_height(self.program_settings_card)
        _log_startup_z2_control_metric("_build_ui.program_settings_rows", (_time.perf_counter() - _t_program) * 1000)

        self.add_spacing(16)

        # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ (direct_zapret2)
        _t_advanced = _time.perf_counter()
        self.advanced_settings_section_label = None

        self.advanced_desc = CaptionLabel(tr_catalog("page.z2_control.advanced.warning", language=self._ui_language, default="⚠ Изменяйте только если знаете что делаете")) if _HAS_FLUENT_LABELS else QLabel(tr_catalog("page.z2_control.advanced.warning", language=self._ui_language, default="⚠ Изменяйте только если знаете что делаете"))

        try:
            from ui.widgets.win11_controls import Win11ToggleRow
        except Exception:
            Win11ToggleRow = None  # type: ignore[assignment]

        self.discord_restart_toggle = (
            Win11ToggleRow(
                "mdi.discord",
                "Перезапуск Discord",
                "Автоперезапуск при смене стратегии",
                "#7289da",
            )
            if Win11ToggleRow
            else None
        )
        if self.discord_restart_toggle:
            self.discord_restart_toggle.toggled.connect(self._on_discord_restart_changed)

        self.wssize_toggle = (
            Win11ToggleRow(
                "fa5s.ruler-horizontal",
                "Включить --wssize",
                "Добавляет параметр размера окна TCP",
                "#9c27b0",
            )
            if Win11ToggleRow
            else None
        )
        if self.wssize_toggle:
            self.wssize_toggle.toggled.connect(self._on_wssize_toggled)

        self.debug_log_toggle = (
            Win11ToggleRow(
                "mdi.file-document-outline",
                "Включить лог-файл (--debug)",
                "Записывает логи winws в папку logs",
                "#00bcd4",
            )
            if Win11ToggleRow
            else None
        )
        if self.debug_log_toggle:
            self.debug_log_toggle.toggled.connect(self._on_debug_log_toggled)

        if SettingCardGroup is not None and _HAS_FLUENT_LABELS:
            self.advanced_card = SettingCardGroup(
                tr_catalog("page.z2_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"),
                self.content,
            )
            try:
                insert_widget_into_setting_card_group(self.advanced_card, 2, self.advanced_desc)
            except Exception:
                pass
            for card in (
                self.discord_restart_toggle,
                self.wssize_toggle,
                self.debug_log_toggle,
            ):
                if card is None:
                    continue
                self.advanced_card.addSettingCard(card)
            enable_setting_card_group_auto_height(self.advanced_card)
        else:
            self.advanced_settings_section_label = self.add_section_title(
                return_widget=True,
                text_key="page.z2_control.section.advanced_settings",
            )
            self.advanced_card = SettingsCard(tr_catalog("page.z2_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"))
            advanced_layout = QVBoxLayout()
            advanced_layout.setContentsMargins(0, 0, 0, 0)
            advanced_layout.setSpacing(4)
            advanced_layout.addWidget(self.advanced_desc)
            for row in (
                self.discord_restart_toggle,
                self.wssize_toggle,
                self.debug_log_toggle,
            ):
                if row is not None:
                    advanced_layout.addWidget(row)
            self.advanced_card.add_layout(advanced_layout)

        self.add_widget(self.advanced_card)
        _log_startup_z2_control_metric("_build_ui.advanced_settings_block", (_time.perf_counter() - _t_advanced) * 1000)

        # Card C — Блобы (ссылка на страницу)
        _t_blobs = _time.perf_counter()
        blobs_card = CardWidget()
        self.blobs_card = blobs_card
        blobs_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        blobs_row = QHBoxLayout(blobs_card)
        blobs_row.setContentsMargins(16, 14, 16, 14)
        blobs_row.setSpacing(12)

        blobs_icon_lbl = QLabel()
        blobs_icon_lbl.setPixmap(qta.icon("fa5s.file-archive", color="#9c27b0").pixmap(20, 20))
        blobs_icon_lbl.setFixedSize(24, 24)
        blobs_row.addWidget(blobs_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        blobs_col = QVBoxLayout()
        blobs_col.setSpacing(2)
        self.blobs_title_label = StrongBodyLabel(tr_catalog("page.z2_control.blobs.title", language=self._ui_language, default="Блобы"))
        self.blobs_desc_label = CaptionLabel(tr_catalog("page.z2_control.blobs.desc", language=self._ui_language, default="Бинарные данные (.bin / hex) для стратегий"))
        blobs_col.addWidget(self.blobs_title_label)
        blobs_col.addWidget(self.blobs_desc_label)
        blobs_row.addLayout(blobs_col, 1)

        blobs_open_btn = PushButton()
        blobs_open_btn.setText(tr_catalog("page.z2_control.button.open", language=self._ui_language, default="Открыть"))
        blobs_open_btn.setIcon(FluentIcon.FOLDER)
        blobs_open_btn.clicked.connect(self.navigate_to_blobs.emit)
        self.blobs_open_btn = blobs_open_btn
        blobs_row.addWidget(blobs_open_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.add_widget(blobs_card)
        _log_startup_z2_control_metric("_build_ui.blobs_card", (_time.perf_counter() - _t_blobs) * 1000)
        
        # Дополнительные действия
        _t_extra = _time.perf_counter()
        self.extra_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.additional",
        )
        extra_card = SettingsCard()
        self.extra_card = extra_card
        extra_layout = QHBoxLayout()
        extra_layout.setSpacing(8)
        self.test_btn = ActionButton(tr_catalog("page.z2_control.button.connection_test", language=self._ui_language, default="Тест соединения"), "fa5s.wifi")
        self.test_btn.clicked.connect(self._open_connection_test)
        extra_layout.addWidget(self.test_btn)
        self.folder_btn = ActionButton(tr_catalog("page.z2_control.button.open_folder", language=self._ui_language, default="Открыть папку"), "fa5s.folder-open")
        self.folder_btn.clicked.connect(self._open_folder)
        extra_layout.addWidget(self.folder_btn)
        self.docs_btn = ActionButton(tr_catalog("page.z2_control.button.documentation", language=self._ui_language, default="Документация"), "fa5s.book")
        self.docs_btn.clicked.connect(self._open_docs)
        extra_layout.addWidget(self.docs_btn)
        extra_layout.addStretch()
        extra_card.add_layout(extra_layout)
        self.add_widget(extra_card)
        _log_startup_z2_control_metric("_build_ui.extra_actions", (_time.perf_counter() - _t_extra) * 1000)
        _log_startup_z2_control_metric("_build_ui.total", (_time.perf_counter() - _t_total) * 1000)

    def _apply_advanced_settings_state(self, state: dict) -> None:
        try:
            toggle = getattr(self, "discord_restart_toggle", None)
            set_checked = getattr(toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(state.get("discord_restart", True)), block_signals=True)
        except Exception:
            pass

        try:
            wssize_toggle = getattr(self, "wssize_toggle", None)
            set_checked = getattr(wssize_toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(state.get("wssize_enabled", False)), block_signals=True)
        except Exception:
            pass

        try:
            debug_toggle = getattr(self, "debug_log_toggle", None)
            set_checked = getattr(debug_toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(state.get("debug_log_enabled", False)), block_signals=True)
        except Exception:
            pass

    def _refresh_selected_preset_name_fast(self) -> None:
        try:
            from core.services import get_direct_flow_coordinator

            preset = get_direct_flow_coordinator().get_selected_source_manifest("direct_zapret2")
            active_name = str(getattr(preset, "name", "") or "").strip()
        except Exception:
            active_name = ""

        if active_name:
            self.preset_name_label.setText(active_name)
            set_tooltip(self.preset_name_label, active_name)
            return

        self.preset_name_label.setText(
            tr_catalog("page.z2_control.preset.not_selected", language=self._ui_language, default="Не выбран")
        )
        set_tooltip(self.preset_name_label, "")

    def _apply_optimistic_startup_view(self) -> None:
        """Быстрое стартовое состояние без тяжёлого чтения пресета и monitor-проверок."""
        try:
            from strategy_menu import get_strategy_launch_method

            method = str(get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = ""

        if method == "direct_zapret2":
            self.update_status("running")

        try:
            from core.services import get_selection_service

            file_name = str(get_selection_service().get_selected_file_name("winws2") or "").strip()
        except Exception:
            file_name = ""

        if not file_name:
            return

        display_name = Path(file_name).stem.strip() or file_name
        self.preset_name_label.setText(display_name)
        set_tooltip(self.preset_name_label, display_name)

    def _schedule_advanced_settings_reload(self, *, force: bool = False) -> None:
        if not force and not self._advanced_settings_dirty:
            return
        worker = getattr(self, "_advanced_settings_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                pass

        self._advanced_settings_request_id += 1
        request_id = self._advanced_settings_request_id
        worker = _AdvancedSettingsLoadWorker(request_id, self)
        self._advanced_settings_worker = worker
        worker.loaded.connect(self._on_advanced_settings_loaded)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_advanced_settings_loaded(self, request_id: int, state: dict) -> None:
        if int(request_id) != int(self._advanced_settings_request_id):
            return
        self._advanced_settings_dirty = False
        self._apply_advanced_settings_state(state if isinstance(state, dict) else {})

    def _schedule_preset_summary_reload(self, *, force: bool = False) -> None:
        if not force and not self._preset_summary_dirty:
            return
        worker = getattr(self, "_preset_summary_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                pass

        self._preset_summary_request_id += 1
        request_id = self._preset_summary_request_id
        worker = _DirectPresetSummaryLoadWorker(request_id, self)
        self._preset_summary_worker = worker
        worker.loaded.connect(self._on_preset_summary_loaded)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_preset_summary_loaded(self, request_id: int, payload: dict) -> None:
        if int(request_id) != int(self._preset_summary_request_id):
            return
        self._preset_summary_dirty = False
        active_preset_name = str((payload or {}).get("active_preset_name") or "").strip()
        active_lists = list((payload or {}).get("active_lists") or [])

        if active_preset_name:
            self.preset_name_label.setText(active_preset_name)
            set_tooltip(self.preset_name_label, active_preset_name)
        else:
            self.preset_name_label.setText(
                tr_catalog("page.z2_control.preset.not_selected", language=self._ui_language, default="Не выбран")
            )
            set_tooltip(self.preset_name_label, "")

        if active_lists:
            self.strategy_label.setText(" • ".join(active_lists))
            set_tooltip(self.strategy_label, "\n".join(active_lists))
        else:
            self.strategy_label.setText(
                tr_catalog("page.z2_control.preset.no_active_lists", language=self._ui_language, default="Нет активных листов")
            )
            set_tooltip(self.strategy_label, "")

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        self._advanced_settings_request_id += 1
        self._advanced_settings_dirty = False
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
        except Exception:
            pass

    def _on_wssize_toggled(self, enabled: bool) -> None:
        self._advanced_settings_request_id += 1
        self._advanced_settings_dirty = False
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_wssize_enabled(bool(enabled))
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        self._advanced_settings_request_id += 1
        self._advanced_settings_dirty = False
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_debug_log_enabled(bool(enabled))
        except Exception:
            pass

    # ==================== Direct mode UI: Basic/Advanced ====================

    def _get_direct_launch_mode_setting(self) -> str:
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode

            mode = (get_direct_zapret2_ui_mode() or "").strip().lower()
            if mode in ("basic", "advanced"):
                return mode
        except Exception:
            pass
        return "advanced"

    def _sync_direct_launch_mode_from_settings(self) -> None:
        self._refresh_direct_mode_label()

    def _open_direct_mode_dialog(self) -> None:
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode
        except ImportError:
            return
        current = get_direct_zapret2_ui_mode()
        dlg = DirectLaunchModeDialog(current, self.window(), language=self._ui_language)
        if dlg.exec():
            new_mode = dlg.get_mode()
            if new_mode != current:
                self._on_direct_launch_mode_selected(new_mode)
                self.direct_mode_changed.emit(new_mode)

    def _refresh_direct_mode_label(self) -> None:
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode
            mode = get_direct_zapret2_ui_mode()
            key = "page.z2_control.mode.basic" if mode == "basic" else "page.z2_control.mode.advanced"
            default = "Basic" if mode == "basic" else "Advanced"
            self.direct_mode_label.setText(tr_catalog(key, language=self._ui_language, default=default))
        except Exception:
            pass

    def _on_direct_launch_mode_selected(self, mode: str) -> None:
        wanted = str(mode or "").strip().lower()
        if wanted not in ("basic", "advanced"):
            return

        current = self._get_direct_launch_mode_setting()
        if wanted == current:
            self._sync_direct_launch_mode_from_settings()
            return

        try:
            from strategy_menu.ui_prefs_store import set_direct_zapret2_ui_mode

            set_direct_zapret2_ui_mode(wanted)
        except Exception:
            pass

        # Re-save the selected source preset through the new direct core,
        # so strategy ids are reinterpreted against the currently selected
        # basic/advanced catalogs without going through legacy registry reloads.
        try:
            from dpi.direct_runtime_apply_policy import request_direct_runtime_content_apply
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method(
                "direct_zapret2",
                on_dpi_reload_needed=lambda: request_direct_runtime_content_apply(
                    self.parent_app,
                    launch_method="direct_zapret2",
                    reason="direct_launch_mode_changed",
                ),
            )
            selections = facade.get_strategy_selections() or {}
            facade.set_strategy_selections(selections, save_and_sync=True)
        except Exception:
            pass

        # Refresh labels that depend on active strategy args.
        try:
            self.update_strategy("")
        except Exception:
            pass

        self._sync_direct_launch_mode_from_settings()

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
            toggle._circle_position = (toggle.width() - 18) if checked else 4.0  # type: ignore[attr-defined]
            toggle.update()
        except Exception:
            pass

        try:
            toggle.blockSignals(False)
        except Exception:
            pass

    def _confirm_reset_program_clicked(self) -> None:
        title = tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить")
        confirm_text = tr_catalog(
            "page.z2_control.button.reset_confirm",
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
        try:
            from config import get_dpi_autostart

            self._set_toggle_checked(self.auto_dpi_toggle, bool(get_dpi_autostart()))
        except Exception:
            pass

        try:
            from altmenu.defender_manager import WindowsDefenderManager

            self._set_toggle_checked(self.defender_toggle, bool(WindowsDefenderManager().is_defender_disabled()))
        except Exception:
            pass

        try:
            from altmenu.max_blocker import is_max_blocked

            self._set_toggle_checked(self.max_block_toggle, bool(is_max_blocked()))
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        try:
            if self.parent_app and hasattr(self.parent_app, "set_status"):
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

        if not ctypes.windll.shell32.IsUserAnAdmin():
            InfoBar.error(title="Требуются права администратора", content="Для управления Windows Defender требуются права администратора. Перезапустите программу от имени администратора.", parent=self.window())
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
                        "page.z2_control.dialog.defender_disable.title",
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
                    InfoBar.success(title="Windows Defender отключен", content=f"Windows Defender успешно отключен. Применено {count} настроек. Может потребоваться перезагрузка.", parent=self.window())
                else:
                    InfoBar.error(title="Ошибка", content="Не удалось отключить Windows Defender. Возможно, некоторые настройки заблокированы системой.", parent=self.window())
                    self._set_toggle_checked(self.defender_toggle, False)
            else:
                box = MessageBox(
                    tr_catalog(
                        "page.z2_control.dialog.defender_enable.title",
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
                    InfoBar.success(title="Windows Defender включен", content="Windows Defender успешно включен. Защита вашего компьютера восстановлена.", parent=self.window())
                else:
                    InfoBar.warning(title="Частичный успех", content="Windows Defender включен частично. Некоторые настройки могут потребовать ручного исправления.", parent=self.window())

            self._set_status("Готово")

        except Exception as e:
            InfoBar.error(title="Ошибка", content=f"Произошла ошибка при изменении настроек Windows Defender: {e}", parent=self.window())
        finally:
            self._sync_program_settings()

    def _on_max_blocker_toggled(self, enable: bool) -> None:
        try:
            from altmenu.max_blocker import MaxBlockerManager

            manager = MaxBlockerManager(status_callback=self._set_status)

            if enable:
                box = MessageBox(
                    tr_catalog(
                        "page.z2_control.dialog.max_block_enable.title",
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
                        "page.z2_control.dialog.max_block_disable.title",
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
        try:
            from strategy_menu.launch_method_store import get_strategy_launch_method
            from config import get_winws_exe_for_method

            method = get_strategy_launch_method()
            exe_name = os.path.basename(get_winws_exe_for_method(method)) or "winws.exe"
            template = tr_catalog(
                "page.z2_control.button.stop_only_template",
                language=self._ui_language,
                default="Остановить только {exe_name}",
            )
            self.stop_winws_btn.setText(template.format(exe_name=exe_name))
        except Exception:
            self.stop_winws_btn.setText(
                tr_catalog(
                    "page.z2_control.button.stop_only_winws",
                    language=self._ui_language,
                    default="Остановить только winws.exe",
                )
            )

    def set_loading(self, loading: bool, text: str = ""):
        if _HAS_FLUENT_LABELS:
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
            fields={
                "dpi_phase",
                "dpi_running",
                "dpi_busy",
                "dpi_busy_text",
                "dpi_last_error",
                "current_strategy_summary",
                "active_preset_revision",
                "mode_revision",
            },
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if "mode_revision" in changed_fields:
            self._sync_direct_launch_mode_from_settings()
        if "active_preset_revision" in changed_fields or not changed_fields:
            self._advanced_settings_dirty = True
            self._preset_summary_dirty = True
            if self.isVisible():
                self._schedule_advanced_settings_reload(force=True)
                self._schedule_preset_summary_reload(force=True)
        self.set_loading(state.dpi_busy, state.dpi_busy_text)
        self.update_status(state.dpi_phase or ("running" if state.dpi_running else "stopped"), state.dpi_last_error)
        self.update_strategy(state.current_strategy_summary or "")

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

        if phase == "running":
            self.status_title.setText(tr_catalog("page.z2_control.status.running", language=self._ui_language, default="Zapret работает"))
            self.status_desc.setText(tr_catalog("page.z2_control.status.bypass_active", language=self._ui_language, default="Обход блокировок активен"))
            self.status_dot.set_color("#6ccb5f")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self._update_stop_winws_button_text()
            self.stop_winws_btn.setVisible(True)
            self.stop_and_exit_btn.setVisible(True)
        elif phase == "autostart_pending":
            self.status_title.setText("Автозапуск Zapret запланирован")
            self.status_desc.setText("Подготавливаем стартовый запуск выбранного пресета")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "starting":
            self.status_title.setText("Zapret запускается")
            self.status_desc.setText("Ждём подтверждение процесса winws")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "stopping":
            self.status_title.setText("Zapret останавливается")
            self.status_desc.setText("Завершаем процесс и освобождаем WinDivert")
            self.status_dot.set_color("#f5a623")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        elif phase == "failed":
            self.status_title.setText("Ошибка запуска Zapret")
            self.status_desc.setText(self._short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу")
            self.status_dot.set_color("#ff6b6b")
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)
        else:
            self.status_title.setText(tr_catalog("page.z2_control.status.stopped", language=self._ui_language, default="Zapret остановлен"))
            self.status_desc.setText(tr_catalog("page.z2_control.status.press_start", language=self._ui_language, default="Нажмите «Запустить» для активации"))
            self.status_dot.set_color("#ff6b6b")
            self.status_dot.stop_pulse()
            self.start_btn.setVisible(True)
            self.stop_winws_btn.setVisible(False)
            self.stop_and_exit_btn.setVisible(False)

    def update_strategy(self, name: str):
        self._update_stop_winws_button_text()
        self._schedule_preset_summary_reload()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.start_btn.setText(tr_catalog("page.z2_control.button.start", language=self._ui_language, default="Запустить Zapret"))
        self.stop_and_exit_btn.setText(tr_catalog("page.z2_control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу"))
        self.presets_btn.setText(tr_catalog("page.z2_control.button.my_presets", language=self._ui_language, default="Мои пресеты"))
        self.direct_open_btn.setText(tr_catalog("page.z2_control.button.open", language=self._ui_language, default="Открыть"))
        self.direct_mode_btn.setText(tr_catalog("page.z2_control.button.change_mode", language=self._ui_language, default="Изменить режим"))
        self.blobs_open_btn.setText(tr_catalog("page.z2_control.button.open", language=self._ui_language, default="Открыть"))
        self.test_btn.setText(tr_catalog("page.z2_control.button.connection_test", language=self._ui_language, default="Тест соединения"))
        self.folder_btn.setText(tr_catalog("page.z2_control.button.open_folder", language=self._ui_language, default="Открыть папку"))
        self.docs_btn.setText(tr_catalog("page.z2_control.button.documentation", language=self._ui_language, default="Документация"))

        self.current_preset_caption.setText(tr_catalog("page.z2_control.preset.current", language=self._ui_language, default="Текущий активный пресет"))
        self.direct_mode_caption.setText(tr_catalog("page.z2_control.direct_mode.caption", language=self._ui_language, default="Режим прямого запуска"))
        self.advanced_desc.setText(tr_catalog("page.z2_control.advanced.warning", language=self._ui_language, default="⚠ Изменяйте только если знаете что делаете"))
        try:
            title_label = getattr(self.program_settings_card, "titleLabel", None)
            if title_label is not None:
                title_label.setText(
                    tr_catalog("page.z2_control.section.program_settings", language=self._ui_language, default="Настройки программы")
                )
        except Exception:
            pass
        try:
            self.auto_dpi_toggle.set_texts(
                tr_catalog("page.z2_control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
                tr_catalog(
                    "page.z2_control.setting.autostart.desc",
                    language=self._ui_language,
                    default="Запускать Zapret автоматически при старте программы",
                ),
            )
        except Exception:
            pass
        try:
            self.defender_toggle.set_texts(
                tr_catalog(
                    "page.z2_control.setting.defender.title",
                    language=self._ui_language,
                    default="Отключить Windows Defender",
                ),
                tr_catalog(
                    "page.z2_control.setting.defender.desc",
                    language=self._ui_language,
                    default="Требуются права администратора",
                ),
            )
        except Exception:
            pass
        try:
            self.max_block_toggle.set_texts(
                tr_catalog(
                    "page.z2_control.setting.max_block.title",
                    language=self._ui_language,
                    default="Блокировать установку MAX",
                ),
                tr_catalog(
                    "page.z2_control.setting.max_block.desc",
                    language=self._ui_language,
                    default="Блокирует запуск/установку MAX и домены в hosts",
                ),
            )
        except Exception:
            pass
        try:
            if self.reset_program_card is not None and hasattr(self.reset_program_card, "setTitle"):
                self.reset_program_card.setTitle(
                    tr_catalog("page.z2_control.setting.reset.title", language=self._ui_language, default="Сбросить программу")
                )
                self.reset_program_card.setContent(
                    tr_catalog(
                        "page.z2_control.setting.reset.desc",
                        language=self._ui_language,
                        default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
                    )
                )
                button = getattr(self.reset_program_card, "button", None)
                if button is not None:
                    button.setText(
                        tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить")
                    )
            elif self.reset_program_btn is not None:
                self.reset_program_btn._default_text = tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить")
                self.reset_program_btn._confirm_text = tr_catalog("page.z2_control.button.reset_confirm", language=self._ui_language, default="Сбросить?")
                self.reset_program_btn.setText(self.reset_program_btn._default_text)
                if self._reset_program_desc_label is not None:
                    self._reset_program_desc_label.setText(
                        tr_catalog(
                            "page.z2_control.setting.reset.desc",
                            language=self._ui_language,
                            default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
                        )
                    )
        except Exception:
            pass
        try:
            if hasattr(self.advanced_card, "set_title"):
                self.advanced_card.set_title(
                    tr_catalog("page.z2_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
                )
            title_label = getattr(self.advanced_card, "titleLabel", None)
            if title_label is not None:
                title_label.setText(tr_catalog("page.z2_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"))
        except Exception:
            pass
        self.blobs_title_label.setText(tr_catalog("page.z2_control.blobs.title", language=self._ui_language, default="Блобы"))
        self.blobs_desc_label.setText(tr_catalog("page.z2_control.blobs.desc", language=self._ui_language, default="Бинарные данные (.bin / hex) для стратегий"))

        self._update_stop_winws_button_text()
        self._refresh_direct_mode_label()
        try:
            self.discord_restart_toggle.set_texts(
                tr_catalog("page.dpi_settings.discord_restart.title", language=self._ui_language, default="Перезапуск Discord"),
                tr_catalog("page.dpi_settings.discord_restart.desc", language=self._ui_language, default="Автоперезапуск при смене стратегии"),
            )
        except Exception:
            pass
        try:
            self.wssize_toggle.set_texts(
                tr_catalog("page.dpi_settings.advanced.wssize.title", language=self._ui_language, default="Включить --wssize"),
                tr_catalog("page.dpi_settings.advanced.wssize.desc", language=self._ui_language, default="Добавляет параметр размера окна TCP"),
            )
        except Exception:
            pass
        try:
            self.debug_log_toggle.set_texts(
                tr_catalog("page.dpi_settings.advanced.debug_log.title", language=self._ui_language, default="Включить лог-файл (--debug)"),
                tr_catalog("page.dpi_settings.advanced.debug_log.desc", language=self._ui_language, default="Записывает логи winws в папку logs"),
            )
        except Exception:
            pass

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            webbrowser.open(DOCS_URL)
        except Exception as e:
            InfoBar.warning(title="Документация", content=f"Не удалось открыть документацию: {e}", parent=self.window())
