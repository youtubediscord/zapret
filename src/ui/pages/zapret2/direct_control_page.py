# ui/pages/zapret2/direct_control_page.py
"""Direct Zapret2 management page (Strategies landing for direct_zapret2)."""

import os
import re
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
from ui.pages.strategies_page_base import ResetActionButton
from ui.compat_widgets import ActionButton, PrimaryActionButton, PulsingDot, SettingsCard, SettingsRow, set_tooltip
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        CaptionLabel, StrongBodyLabel, SubtitleLabel, BodyLabel,
        IndeterminateProgressBar, MessageBox, InfoBar,
        SegmentedWidget, MessageBoxBase, CardWidget,
        PushButton, TransparentPushButton, FluentIcon,
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

    def __init__(self, parent=None):
        super().__init__(
            "Управление",
            "Настройка и запуск Zapret 2. Выберите готовые пресеты-конфиги (как раньше .bat), "
            "а при необходимости выполните тонкую настройку для каждой категории в разделе «Прямой запуск».",
            parent,
            title_key="page.z2_control.title",
            subtitle_key="page.z2_control.subtitle",
        )

        self._build_ui()
        self._update_stop_winws_button_text()

    def showEvent(self, a0):
        super().showEvent(a0)
        try:
            self._sync_program_settings()
        except Exception:
            pass
        try:
            self._load_advanced_settings()
        except Exception:
            pass
        try:
            self._refresh_direct_mode_label()
        except Exception:
            pass

    def _build_ui(self):
        # Статус работы
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

        self.add_spacing(16)

        # Управление
        self.control_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.management",
        )

        control_card = SettingsCard()
        self.control_card_card = control_card

        # Индикатор загрузки (бегающая полоска) - показываем рядом с кнопками управления
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

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.start_btn = BigActionButton(tr_catalog("page.z2_control.button.start", language=self._ui_language, default="Запустить Zapret"), "fa5s.play", accent=True)
        buttons_layout.addWidget(self.start_btn)

        self.stop_winws_btn = StopButton(tr_catalog("page.z2_control.button.stop_only_winws", language=self._ui_language, default="Остановить только winws.exe"), "fa5s.stop")
        self.stop_winws_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_winws_btn)

        self.stop_and_exit_btn = StopButton(tr_catalog("page.z2_control.button.stop_and_exit", language=self._ui_language, default="Остановить и закрыть программу"), "fa5s.power-off")
        self.stop_and_exit_btn.setVisible(False)
        buttons_layout.addWidget(self.stop_and_exit_btn)

        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)
        self.add_widget(control_card)

        self.add_spacing(16)

        # ── Запуск: две вертикальные WinUI-карточки ──────────────────────
        self.preset_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.preset_switch",
        )

        # Card A — Активный пресет (single-row: icon | text | button)
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
        self.active_preset_label = self.preset_name_label  # backward-compat alias
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

        self.add_spacing(8)

        # ── Запуск: две вертикальные WinUI-карточки ──────────────────────
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
        open_btn.clicked.connect(self.navigate_to_direct_launch.emit)
        mode_btn = TransparentPushButton()
        mode_btn.setText(tr_catalog("page.z2_control.button.change_mode", language=self._ui_language, default="Изменить режим"))
        mode_btn.clicked.connect(self._open_direct_mode_dialog)
        direct_btns.addWidget(open_btn)
        direct_btns.addWidget(mode_btn)
        self.direct_open_btn = open_btn
        self.direct_mode_btn = mode_btn
        direct_row.addLayout(direct_btns)
        self.add_widget(direct_card)

        self.add_spacing(8)

        # Backward-compat hidden attributes
        self.active_preset_desc = CaptionLabel("")
        self.active_preset_desc.setVisible(False)
        self.strategy_desc = CaptionLabel("")
        self.strategy_desc.setVisible(False)

        self.add_spacing(16)

        # Настройки программы
        self.program_settings_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.program_settings",
        )
        program_settings_card = SettingsCard()
        self.program_settings_card = program_settings_card

        try:
            from ui.pages.dpi_settings_page import Win11ToggleSwitch
        except Exception:
            Win11ToggleSwitch = None  # type: ignore[assignment]

        auto_row = SettingsRow(
            "fa5s.bolt",
            tr_catalog("page.z2_control.setting.autostart.title", language=self._ui_language, default="Автозагрузка DPI"),
            tr_catalog(
                "page.z2_control.setting.autostart.desc",
                language=self._ui_language,
                default="Запускать Zapret автоматически при старте программы",
            ),
        )
        self.auto_dpi_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.auto_dpi_toggle.setProperty("noDrag", True)
        if hasattr(self.auto_dpi_toggle, "toggled"):
            self.auto_dpi_toggle.toggled.connect(self._on_auto_dpi_toggled)
        auto_row.set_control(self.auto_dpi_toggle)
        program_settings_card.add_widget(auto_row)

        defender_row = SettingsRow(
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
        self.defender_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.defender_toggle.setProperty("noDrag", True)
        if hasattr(self.defender_toggle, "toggled"):
            self.defender_toggle.toggled.connect(self._on_defender_toggled)
        defender_row.set_control(self.defender_toggle)
        program_settings_card.add_widget(defender_row)

        max_row = SettingsRow(
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
        self.max_block_toggle = Win11ToggleSwitch() if Win11ToggleSwitch else ActionButton(
            tr_catalog("common.toggle.on_off", language=self._ui_language, default="Вкл/Выкл")
        )
        self.max_block_toggle.setProperty("noDrag", True)
        if hasattr(self.max_block_toggle, "toggled"):
            self.max_block_toggle.toggled.connect(self._on_max_blocker_toggled)
        max_row.set_control(self.max_block_toggle)
        program_settings_card.add_widget(max_row)

        reset_row = SettingsRow(
            "fa5s.undo",
            tr_catalog("page.z2_control.setting.reset.title", language=self._ui_language, default="Сбросить программу"),
            tr_catalog(
                "page.z2_control.setting.reset.desc",
                language=self._ui_language,
                default="Очистить кэш проверок запуска (без удаления пресетов/настроек)",
            ),
        )
        self.reset_program_btn = ResetActionButton(
            tr_catalog("page.z2_control.button.reset", language=self._ui_language, default="Сбросить"),
            confirm_text=tr_catalog("page.z2_control.button.reset_confirm", language=self._ui_language, default="Сбросить?"),
        )
        self.reset_program_btn.setProperty("noDrag", True)
        self.reset_program_btn.reset_confirmed.connect(self._on_reset_program_clicked)
        reset_row.set_control(self.reset_program_btn)
        program_settings_card.add_widget(reset_row)

        self.add_widget(program_settings_card)

        self.add_spacing(16)

        # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ (direct_zapret2)
        self.advanced_settings_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.advanced_settings",
        )

        self.advanced_card = SettingsCard(tr_catalog("page.z2_control.card.advanced", language=self._ui_language, default="ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ"))
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(6)

        self.advanced_desc = CaptionLabel(tr_catalog("page.z2_control.advanced.warning", language=self._ui_language, default="⚠ Изменяйте только если знаете что делаете")) if _HAS_FLUENT_LABELS else QLabel(tr_catalog("page.z2_control.advanced.warning", language=self._ui_language, default="⚠ Изменяйте только если знаете что делаете"))
        self.advanced_desc.setStyleSheet("color: #ff9800; padding-bottom: 8px;")
        advanced_layout.addWidget(self.advanced_desc)

        try:
            from ui.pages.dpi_settings_page import Win11ToggleRow
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
            advanced_layout.addWidget(self.discord_restart_toggle)

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
            advanced_layout.addWidget(self.wssize_toggle)

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
            advanced_layout.addWidget(self.debug_log_toggle)

        self.advanced_card.add_layout(advanced_layout)
        self.add_widget(self.advanced_card)

        # Card C — Блобы (ссылка на страницу)
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
        
        # Дополнительные действия
        self.extra_section_label = self.add_section_title(
            return_widget=True,
            text_key="page.z2_control.section.additional",
        )
        extra_card = SettingsCard()
        self.extra_card = extra_card
        extra_layout = QHBoxLayout()
        extra_layout.setSpacing(8)
        self.test_btn = ActionButton(tr_catalog("page.z2_control.button.connection_test", language=self._ui_language, default="Тест соединения"), "fa5s.wifi")
        extra_layout.addWidget(self.test_btn)
        self.folder_btn = ActionButton(tr_catalog("page.z2_control.button.open_folder", language=self._ui_language, default="Открыть папку"), "fa5s.folder-open")
        extra_layout.addWidget(self.folder_btn)
        self.docs_btn = ActionButton(tr_catalog("page.z2_control.button.documentation", language=self._ui_language, default="Документация"), "fa5s.book")
        self.docs_btn.clicked.connect(self._open_docs)
        extra_layout.addWidget(self.docs_btn)
        extra_layout.addStretch()
        extra_card.add_layout(extra_layout)
        self.add_widget(extra_card)

        self._sync_program_settings()

        # Advanced settings initial state
        self._load_advanced_settings()

    def _load_advanced_settings(self) -> None:
        """Sync advanced toggles from registry."""
        try:
            from strategy_menu import get_wssize_enabled, get_debug_log_enabled

            try:
                from discord.discord_restart import get_discord_restart_setting

                toggle = getattr(self, "discord_restart_toggle", None)
                set_checked = getattr(toggle, "setChecked", None)
                if callable(set_checked):
                    set_checked(get_discord_restart_setting(default=True), block_signals=True)
            except Exception:
                pass

            wssize_toggle = getattr(self, "wssize_toggle", None)
            set_checked = getattr(wssize_toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(get_wssize_enabled()), block_signals=True)

            debug_toggle = getattr(self, "debug_log_toggle", None)
            set_checked = getattr(debug_toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(get_debug_log_enabled()), block_signals=True)
        except Exception:
            pass

    def _on_discord_restart_changed(self, enabled: bool) -> None:
        try:
            from discord.discord_restart import set_discord_restart_setting

            set_discord_restart_setting(bool(enabled))
        except Exception:
            pass

    def _on_wssize_toggled(self, enabled: bool) -> None:
        try:
            from strategy_menu import set_wssize_enabled

            set_wssize_enabled(bool(enabled))
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        try:
            from strategy_menu import set_debug_log_enabled

            set_debug_log_enabled(bool(enabled))
        except Exception:
            pass

        # direct_zapret2: keep generated launch config in sync with runtime --debug setting
        try:
            from core.services import get_direct_flow_coordinator

            get_direct_flow_coordinator().refresh_selected_runtime("direct_zapret2")
        except Exception:
            pass

    # ==================== Direct mode UI: Basic/Advanced ====================

    def _get_direct_launch_mode_setting(self) -> str:
        try:
            from strategy_menu import get_direct_zapret2_ui_mode

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
            from strategy_menu import get_direct_zapret2_ui_mode
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
            from strategy_menu import get_direct_zapret2_ui_mode
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
            from strategy_menu import set_direct_zapret2_ui_mode

            set_direct_zapret2_ui_mode(wanted)
        except Exception:
            pass

        # Reload strategy catalogs for the selected set.
        try:
            from strategy_menu.strategies_registry import registry

            registry.reload_strategies()
        except Exception:
            pass

        # Rebuild the generated launch config from the currently selected strategy IDs
        # using the newly selected strategies catalog (basic vs default).
        try:
            from dpi.zapret2_core_restart import trigger_dpi_reload
            from preset_zapret2 import PresetManager

            pm = PresetManager(
                on_dpi_reload_needed=lambda: trigger_dpi_reload(
                    self.parent_app,
                    reason="direct_launch_mode_changed",
                )
            )
            preset = pm.get_active_preset()
            if preset:
                try:
                    selections = pm.get_strategy_selections() or {}
                    pm.set_strategy_selections(selections, save_and_sync=False)
                except Exception:
                    pass

                try:
                    pm.save_preset(preset)
                except Exception:
                    pass

                try:
                    from core.services import get_direct_flow_coordinator

                    get_direct_flow_coordinator().refresh_selected_runtime("direct_zapret2")
                except Exception:
                    pm.sync_preset_to_active_file(preset)
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
            from strategy_menu import get_strategy_launch_method
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

    def update_status(self, is_running: bool):
        if is_running:
            self.status_title.setText(tr_catalog("page.z2_control.status.running", language=self._ui_language, default="Zapret работает"))
            self.status_desc.setText(tr_catalog("page.z2_control.status.bypass_active", language=self._ui_language, default="Обход блокировок активен"))
            self.status_dot.set_color("#6ccb5f")
            self.status_dot.start_pulse()
            self.start_btn.setVisible(False)
            self._update_stop_winws_button_text()
            self.stop_winws_btn.setVisible(True)
            self.stop_and_exit_btn.setVisible(True)
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

        show_filter_lists = False
        active_preset_name = ""

        try:
            from core.services import get_direct_flow_coordinator

            active_preset_name = (
                get_direct_flow_coordinator().get_selected_preset_name("direct_zapret2") or ""
            ).strip()
        except Exception:
            active_preset_name = ""

        try:
            from strategy_menu import get_strategy_launch_method

            method = get_strategy_launch_method()
            if method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                show_filter_lists = True
                from strategy_menu import get_direct_strategy_selections
                from strategy_menu.strategies_registry import registry

                selections = get_direct_strategy_selections() or {}
                active_lists: list[str] = []
                seen_lists: set[str] = set()

                for cat_key in registry.get_all_category_keys_by_command_order():
                    sid = selections.get(cat_key, "none") or "none"
                    if sid == "none":
                        continue

                    args = registry.get_strategy_args_safe(cat_key, sid) or ""
                    for value in _HOSTLIST_DISPLAY_RE.findall(args):
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

                if not active_lists:
                    name = tr_catalog("page.z2_control.preset.not_selected", language=self._ui_language, default="Не выбрана")
                    set_tooltip(self.strategy_label, "")
                else:
                    name = " • ".join(active_lists)
                    set_tooltip(self.strategy_label, "\n".join(active_lists))
        except Exception:
            pass

        if active_preset_name:
            self.preset_name_label.setText(active_preset_name)
            set_tooltip(self.preset_name_label, active_preset_name)
        else:
            self.preset_name_label.setText(tr_catalog("page.z2_control.preset.not_selected", language=self._ui_language, default="Не выбран"))
            set_tooltip(self.preset_name_label, "")

        autostart_disabled_ru = tr_catalog(
            "page.z2_control.strategy.autostart_disabled",
            language="ru",
            default="Автостарт DPI отключен",
        )
        autostart_disabled_en = tr_catalog(
            "page.z2_control.strategy.autostart_disabled",
            language="en",
            default="Autostart DPI is disabled",
        )

        if name and name not in {autostart_disabled_ru, autostart_disabled_en, "Автостарт DPI отключен"}:
            self.strategy_label.setText(name)
        else:
            self.strategy_label.setText(tr_catalog("page.z2_control.preset.no_active_lists", language=self._ui_language, default="Нет активных листов"))

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
        self.blobs_title_label.setText(tr_catalog("page.z2_control.blobs.title", language=self._ui_language, default="Блобы"))
        self.blobs_desc_label.setText(tr_catalog("page.z2_control.blobs.desc", language=self._ui_language, default="Бинарные данные (.bin / hex) для стратегий"))

        self._update_stop_winws_button_text()
        self._refresh_direct_mode_label()

    def _open_docs(self) -> None:
        try:
            from config.urls import DOCS_URL

            webbrowser.open(DOCS_URL)
        except Exception as e:
            InfoBar.warning(title="Документация", content=f"Не удалось открыть документацию: {e}", parent=self.window())
