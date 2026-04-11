# ui/pages/hostlist_page.py
"""Объединённая страница «Листы»: обзор hostlist / ipset + редакторы доменов и IP."""

import os

import qtawesome as qta
from PyQt6.QtCore import QSize, QTimer, pyqtSignal

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from core.hostlist_page_controller import HostlistPageController

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, InfoBar, LineEdit, MessageBox, SegmentedWidget,
        StrongBodyLabel, SettingCardGroup, PushButton, PrimaryPushButton,
    )
except ImportError:
    raise

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log


class CurrentPanelStackedWidget(QStackedWidget):
    """QStackedWidget, который берёт высоту у текущей вкладки.

    Обычный QStackedWidget умеет держать sizeHint по самой высокой панели.
    Для страницы «Листы» это создаёт лишнюю пустую зону снизу на коротких
    вкладках, потому что одна из соседних панелей заметно выше остальных.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self._refresh_geometry)

    def sizeHint(self) -> QSize:  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            try:
                hint = current.sizeHint()
                if hint.isValid():
                    return hint
            except Exception:
                pass
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            try:
                hint = current.minimumSizeHint()
                if hint.isValid():
                    return hint
            except Exception:
                pass
        return super().minimumSizeHint()

    def _refresh_geometry(self, _index: int) -> None:
        self.updateGeometry()


class HostlistPage(BasePage):
    """Страница «Листы»: обзор hostlist/ipset + редакторы пользовательских доменов и IP."""

    domains_changed = pyqtSignal()
    ipset_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Листы",
            "Управление hostlist и ipset списками для обхода блокировок",
            parent,
            title_key="page.hostlist.title",
            subtitle_key="page.hostlist.subtitle",
        )
        self._runtime_initialized = False
        self._domains_loaded = False
        self._ips_loaded = False
        self._accent_icon_lbls: list[tuple] = []

        # Autosave timers (created early so textChanged can reference them before panel is shown)
        self._domains_save_timer = QTimer()
        self._domains_save_timer.setSingleShot(True)
        self._domains_save_timer.timeout.connect(self._domains_auto_save)

        self._ips_save_timer = QTimer()
        self._ips_save_timer.setSingleShot(True)
        self._ips_save_timer.timeout.connect(self._ips_auto_save)

        self._ips_status_timer = QTimer()
        self._ips_status_timer.setSingleShot(True)
        self._ips_status_timer.timeout.connect(self._ips_update_status)
        self._ip_base_set_cache: set[str] | None = None

        self._excl_loaded = False
        self._excl_base_set_cache: set[str] | None = None
        self._excl_save_timer = QTimer()
        self._excl_save_timer.setSingleShot(True)
        self._excl_save_timer.timeout.connect(self._excl_auto_save)

        self._ipru_base_set_cache: set[str] | None = None
        self._ipru_save_timer = QTimer()
        self._ipru_save_timer.setSingleShot(True)
        self._ipru_save_timer.timeout.connect(self._ipru_auto_save)
        self._ipru_status_timer = QTimer()
        self._ipru_status_timer.setSingleShot(True)
        self._ipru_status_timer.timeout.connect(self._ipru_update_status)


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

    def _apply_hostlist_action_result(self, result) -> None:
        log(result.log_message, result.log_level)

        if getattr(result, "invalidate_excl_base_cache", False):
            self._excl_base_set_cache = None

        if getattr(result, "reload_info", False):
            self._load_info()

        if getattr(result, "reload_domains", False):
            self._load_domains()
            if getattr(result, "append_domains_status_suffix", "") and hasattr(self, "_d_status"):
                self._d_status.setText(self._d_status.text() + result.append_domains_status_suffix)

        if getattr(result, "reload_exclusions", False):
            self._excl_update_status()
            if getattr(result, "append_exclusions_status_suffix", "") and hasattr(self, "_excl_status"):
                self._excl_status.setText(self._excl_status.text() + result.append_exclusions_status_suffix)

        level = getattr(result, "infobar_level", None)
        if not level or not InfoBar:
            return

        if level == "success":
            InfoBar.success(title=result.infobar_title, content=result.infobar_content, parent=self.window())
        elif level == "warning":
            InfoBar.warning(title=result.infobar_title, content=result.infobar_content, parent=self.window())
        elif level == "error":
            InfoBar.error(title=result.infobar_title, content=result.infobar_content, parent=self.window())
        else:
            InfoBar.info(title=result.infobar_title, content=result.infobar_content, parent=self.window())

    # ──────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        QTimer.singleShot(0, self._load_info)


    # ──────────────────────────────────────────────────────────────────────────
    # Main UI builder
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Pivot tab selector
        self.pivot = SegmentedWidget(self)

        # Stacked panels
        self.stacked = CurrentPanelStackedWidget(self)
        self.stacked.setSizePolicy(
            self.stacked.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Preferred,
        )

        panel_hostlist = self._build_hostlist_panel()       # index 0
        panel_ipset = self._build_ipset_panel()             # index 1
        panel_domains = self._build_domains_panel()         # index 2
        panel_ips = self._build_ips_panel()                 # index 3
        panel_exclusions = self._build_exclusions_panel()   # index 4

        self.stacked.addWidget(panel_hostlist)
        self.stacked.addWidget(panel_ipset)
        self.stacked.addWidget(panel_domains)
        self.stacked.addWidget(panel_ips)
        self.stacked.addWidget(panel_exclusions)

        self.pivot.addItem("hostlist", self._tr("page.hostlist.tab.hostlist", "Hostlist"), lambda: self._switch_tab(0))
        self.pivot.addItem("ipset", self._tr("page.hostlist.tab.ipset", "IPset"), lambda: self._switch_tab(1))
        self.pivot.addItem("domains", self._tr("page.hostlist.tab.domains", "Мои домены"), lambda: self._switch_tab(2))
        self.pivot.addItem("ips", self._tr("page.hostlist.tab.ips", "Мои IP"), lambda: self._switch_tab(3))
        self.pivot.addItem("exclusions", self._tr("page.hostlist.tab.exclusions", "Исключения"), lambda: self._switch_tab(4))
        self.pivot.setCurrentItem("hostlist")
        self.pivot.setItemFontSize(13)
        self.layout.addWidget(self.pivot)

        self.layout.addWidget(self.stacked)
        self._switch_tab(0)

    def _switch_tab(self, index: int):
        self.stacked.setCurrentIndex(index)
        keys = ["hostlist", "ipset", "domains", "ips", "exclusions"]
        if 0 <= index < len(keys):
            self.pivot.setCurrentItem(keys[index])
        self._refresh_stacked_geometry()
        # Lazy-load editors on first visit
        if index == 2 and not self._domains_loaded:
            self._domains_loaded = True
            QTimer.singleShot(0, self._load_domains)
        elif index == 3 and not self._ips_loaded:
            self._ips_loaded = True
            QTimer.singleShot(0, self._load_ips)
        elif index == 4 and not self._excl_loaded:
            self._excl_loaded = True
            QTimer.singleShot(0, self._load_exclusions)

    def _refresh_stacked_geometry(self) -> None:
        self.stacked.updateGeometry()
        current = self.stacked.currentWidget()
        if current is not None:
            current.updateGeometry()
            current.adjustSize()
        self.content.updateGeometry()
        self.content.adjustSize()
        self.updateGeometry()

    # ──────────────────────────────────────────────────────────────────────────
    # Panel builders
    # ──────────────────────────────────────────────────────────────────────────

    def _build_hostlist_panel(self) -> QWidget:
        tokens = get_theme_tokens()
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        desc_card = SettingsCard()
        desc = BodyLabel(
            self._tr("page.hostlist.hostlist.desc", "Используется для обхода блокировок по доменам.")
        )
        self._hostlist_desc_label = desc
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        lay.addWidget(desc_card)

        self._hostlist_manage_card = None
        manage_group = SettingCardGroup(self._tr("page.hostlist.section.manage", "Управление"), self.content)
        self._hostlist_manage_group = manage_group
        self._hostlist_actions_bar = QuickActionsBar(self.content)

        self._hostlist_open_folder_action_card = ActionButton(
            self._tr("page.hostlist.button.open", "Открыть"),
            "fa5s.folder-open",
        )
        self._hostlist_open_folder_action_card.clicked.connect(self._open_lists_folder)
        set_tooltip(
            self._hostlist_open_folder_action_card,
            self._tr(
                "page.hostlist.hostlist.action.open_folder.description",
                "Открыть общую папку hostlist и ipset списков в проводнике.",
            ),
        )

        self._hostlist_rebuild_action_card = ActionButton(
            self._tr("page.hostlist.button.rebuild", "Перестроить"),
            "fa5s.sync-alt",
        )
        self._hostlist_rebuild_action_card.clicked.connect(self._rebuild_hostlists)
        set_tooltip(
            self._hostlist_rebuild_action_card,
            self._tr(
                "page.hostlist.hostlist.action.rebuild.subtitle",
                "Обновляет списки из встроенной базы",
            ),
        )

        self._hostlist_actions_bar.add_buttons([
            self._hostlist_open_folder_action_card,
            self._hostlist_rebuild_action_card,
        ])
        insert_widget_into_setting_card_group(manage_group, 1, self._hostlist_actions_bar)
        manage_card = SettingsCard()
        self._hostlist_info_card = manage_card
        self.hostlist_info_label = CaptionLabel(
            self._tr("page.hostlist.info.loading", "Загрузка информации...")
        )
        self.hostlist_info_label.setStyleSheet(f"color: {tokens.fg_muted};")
        self.hostlist_info_label.setWordWrap(True)
        manage_card.add_widget(self.hostlist_info_label)
        manage_group.addSettingCard(manage_card)
        lay.addWidget(manage_group)

        lay.addStretch()
        return panel

    def _build_ipset_panel(self) -> QWidget:
        tokens = get_theme_tokens()
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        desc_card = SettingsCard()
        desc = BodyLabel(
            self._tr(
                "page.hostlist.ipset.desc",
                "Используется для обхода блокировок по IP-адресам и подсетям.",
            )
        )
        self._ipset_desc_label = desc
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        lay.addWidget(desc_card)

        self._ipset_manage_card = None
        manage_group = SettingCardGroup(self._tr("page.hostlist.section.manage", "Управление"), self.content)
        self._ipset_manage_group = manage_group
        self._ipset_actions_bar = QuickActionsBar(self.content)

        self._ipset_open_folder_action_card = ActionButton(
            self._tr("page.hostlist.button.open", "Открыть"),
            "fa5s.folder-open",
        )
        self._ipset_open_folder_action_card.clicked.connect(self._open_lists_folder)
        set_tooltip(
            self._ipset_open_folder_action_card,
            self._tr(
                "page.hostlist.ipset.action.open_folder.description",
                "Открыть общую папку hostlist и ipset списков в проводнике.",
            ),
        )
        self._ipset_actions_bar.add_button(self._ipset_open_folder_action_card)
        insert_widget_into_setting_card_group(manage_group, 1, self._ipset_actions_bar)
        manage_card = SettingsCard()
        self._ipset_info_card = manage_card
        self.ipset_info_label = CaptionLabel(
            self._tr("page.hostlist.info.loading", "Загрузка информации...")
        )
        self.ipset_info_label.setStyleSheet(f"color: {tokens.fg_muted};")
        self.ipset_info_label.setWordWrap(True)
        manage_card.add_widget(self.ipset_info_label)
        manage_group.addSettingCard(manage_card)
        lay.addWidget(manage_group)

        lay.addStretch()
        return panel

    def _build_domains_panel(self) -> QWidget:
        tokens = get_theme_tokens()
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        desc_card = SettingsCard()
        desc = BodyLabel(
            self._tr(
                "page.hostlist.domains.desc",
                "Редактируется файл other.user.txt (только ваши домены). "
                "Системная база хранится в other.base.txt, общий other.txt собирается автоматически. "
                "URL автоматически преобразуются в домены. Изменения сохраняются автоматически. "
                "Поддерживается Ctrl+Z.",
            )
        )
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        lay.addWidget(desc_card)

        add_card = SettingsCard(self._tr("page.hostlist.domains.section.add", "Добавить домен"))
        self._domains_add_card = add_card
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._d_input = LineEdit()
        if hasattr(self._d_input, "setPlaceholderText"):
            self._d_input.setPlaceholderText(
                self._tr(
                    "page.hostlist.domains.input.placeholder",
                    "Введите домен или URL (например: example.com)",
                )
            )
        if hasattr(self._d_input, "returnPressed"):
            self._d_input.returnPressed.connect(self._domains_add)
        add_row.addWidget(self._d_input, 1)
        self._d_add_btn = PrimaryPushButton()
        self._d_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        self._d_add_btn.setIcon(qta.icon("fa5s.plus", color=tokens.accent_hex))
        self._d_add_btn.setFixedHeight(38)
        self._d_add_btn.clicked.connect(self._domains_add)
        add_row.addWidget(self._d_add_btn)
        add_card.add_layout(add_row)
        lay.addWidget(add_card)

        self._domains_actions_card = None
        self._domains_actions_group = SettingCardGroup(self._tr("page.hostlist.section.actions", "Действия"), self.content)
        actions_group = self._domains_actions_group
        self._domains_actions_bar = QuickActionsBar(self.content)

        self._domains_open_action_card = ActionButton(
            self._tr("page.hostlist.button.open_file", "Открыть файл"),
            "fa5s.external-link-alt",
        )
        self._domains_open_action_card.clicked.connect(self._domains_open_file)
        set_tooltip(
            self._domains_open_action_card,
            self._tr(
                "page.hostlist.domains.tooltip.open_file",
                "Сохраняет изменения и открывает other.user.txt в проводнике",
            ),
        )

        self._domains_reset_action_card = ActionButton(
            self._tr("page.hostlist.button.reset_file", "Сбросить файл"),
            "fa5s.undo",
        )
        self._domains_reset_action_card.clicked.connect(self._domains_confirm_reset_file)
        set_tooltip(
            self._domains_reset_action_card,
            self._tr(
                "page.hostlist.domains.tooltip.reset_file",
                "Очищает other.user.txt и пересобирает other.txt из системной базы",
            ),
        )

        self._domains_clear_action_card = ActionButton(
            self._tr("page.hostlist.button.clear_all", "Очистить всё"),
            "fa5s.trash-alt",
        )
        self._domains_clear_action_card.clicked.connect(self._domains_confirm_clear_all)
        set_tooltip(
            self._domains_clear_action_card,
            self._tr("page.hostlist.domains.tooltip.clear_all", "Удаляет только пользовательские домены"),
        )

        self._domains_actions_bar.add_buttons([
            self._domains_open_action_card,
            self._domains_reset_action_card,
            self._domains_clear_action_card,
        ])
        insert_widget_into_setting_card_group(actions_group, 1, self._domains_actions_bar)
        lay.addWidget(actions_group)

        editor_card = SettingsCard(
            self._tr("page.hostlist.domains.section.editor", "other.user.txt (редактор)")
        )
        self._domains_editor_card = editor_card
        editor_lay = QVBoxLayout()
        editor_lay.setSpacing(8)
        self._d_editor = ScrollBlockingPlainTextEdit()
        self._d_editor.setPlaceholderText(
            self._tr(
                "page.hostlist.domains.editor.placeholder",
                "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
            )
        )
        self._d_editor.setMinimumHeight(350)
        self._d_editor.textChanged.connect(self._domains_on_text_changed)
        editor_lay.addWidget(self._d_editor)
        hint = CaptionLabel(
            self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
        )
        self._domains_hint_label = hint
        editor_lay.addWidget(hint)
        editor_card.add_layout(editor_lay)
        lay.addWidget(editor_card)

        self._d_status = CaptionLabel()
        lay.addWidget(self._d_status)
        lay.addStretch()

        self._apply_editor_styles()
        return panel

    def _build_ips_panel(self) -> QWidget:
        tokens = get_theme_tokens()
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        desc_card = SettingsCard()
        desc = BodyLabel(
            self._tr(
                "page.hostlist.ips.desc",
                "Добавляйте свои IP/подсети в ipset-all.user.txt.\n"
                "• Одиночный IP: 1.2.3.4\n"
                "• Подсеть: 10.0.0.0/8\n"
                "Диапазоны (a-b) не поддерживаются. Изменения сохраняются автоматически.\n"
                "Системная база хранится в ipset-all.base.txt и автоматически объединяется в ipset-all.txt.",
            )
        )
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        lay.addWidget(desc_card)

        add_card = SettingsCard(self._tr("page.hostlist.ips.section.add", "Добавить IP/подсеть"))
        self._ips_add_card = add_card
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._i_input = LineEdit()
        if hasattr(self._i_input, "setPlaceholderText"):
            self._i_input.setPlaceholderText(
                self._tr("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
            )
        if hasattr(self._i_input, "returnPressed"):
            self._i_input.returnPressed.connect(self._ips_add)
        add_row.addWidget(self._i_input, 1)
        self._i_add_btn = PrimaryPushButton()
        self._i_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        self._i_add_btn.setIcon(qta.icon("fa5s.plus", color=tokens.accent_hex))
        self._i_add_btn.setFixedHeight(38)
        self._i_add_btn.clicked.connect(self._ips_add)
        add_row.addWidget(self._i_add_btn)
        add_card.add_layout(add_row)
        lay.addWidget(add_card)

        self._ips_actions_card = None
        self._ips_actions_group = SettingCardGroup(self._tr("page.hostlist.section.actions", "Действия"), self.content)
        actions_group = self._ips_actions_group
        self._ips_actions_bar = QuickActionsBar(self.content)

        self._ips_open_action_card = ActionButton(
            self._tr("page.hostlist.button.open_file", "Открыть файл"),
            "fa5s.external-link-alt",
        )
        self._ips_open_action_card.clicked.connect(self._ips_open_file)
        set_tooltip(
            self._ips_open_action_card,
            self._tr("page.hostlist.ips.action.open_file.description", "Сохраняет изменения и открывает ipset-all.user.txt в проводнике."),
        )

        self._ips_clear_action_card = ActionButton(
            self._tr("page.hostlist.button.clear_all", "Очистить всё"),
            "fa5s.trash-alt",
        )
        self._ips_clear_action_card.clicked.connect(self._ips_clear_all)
        set_tooltip(
            self._ips_clear_action_card,
            self._tr("page.hostlist.ips.action.clear_all.description", "Удаляет все пользовательские IP и подсети."),
        )

        self._ips_actions_bar.add_buttons([self._ips_open_action_card, self._ips_clear_action_card])
        insert_widget_into_setting_card_group(actions_group, 1, self._ips_actions_bar)
        lay.addWidget(actions_group)

        editor_card = SettingsCard(
            self._tr("page.hostlist.ips.section.editor", "ipset-all.user.txt (редактор)")
        )
        self._ips_editor_card = editor_card
        editor_lay = QVBoxLayout()
        editor_lay.setSpacing(8)
        self._i_editor = ScrollBlockingPlainTextEdit()
        self._i_editor.setPlaceholderText(
            self._tr(
                "page.hostlist.ips.editor.placeholder",
                "IP/подсети по одному на строку:\n192.168.0.1\n10.0.0.0/8\n\nКомментарии начинаются с #",
            )
        )
        self._i_editor.setMinimumHeight(350)
        self._i_editor.textChanged.connect(self._ips_on_text_changed)
        editor_lay.addWidget(self._i_editor)
        hint = CaptionLabel(
            self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
        )
        self._ips_hint_label = hint
        editor_lay.addWidget(hint)
        self._i_error_label = CaptionLabel()
        self._i_error_label.setWordWrap(True)
        self._i_error_label.hide()
        editor_lay.addWidget(self._i_error_label)
        editor_card.add_layout(editor_lay)
        lay.addWidget(editor_card)

        self._i_status = CaptionLabel()
        lay.addWidget(self._i_status)
        lay.addStretch()

        self._apply_editor_styles()
        return panel

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = force
        self._apply_editor_styles(tokens=tokens)

    def _apply_editor_styles(self, tokens=None):
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "_accent_icon_lbls"):
            for lbl, icon_name in self._accent_icon_lbls:
                try:
                    lbl.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(18, 18))
                except Exception:
                    pass

        style = (
            f"QPlainTextEdit {{"
            f"  background: {tokens.surface_bg};"
            f"  border: 1px solid {tokens.surface_border};"
            f"  border-radius: 8px;"
            f"  padding: 12px;"
            f"  color: {tokens.fg};"
            f"  font-family: Consolas, 'Courier New', monospace;"
            f"  font-size: 13px;"
            f"}}"
            f"QPlainTextEdit:hover {{"
            f"  background: {tokens.surface_bg_hover};"
            f"  border: 1px solid {tokens.surface_border_hover};"
            f"}}"
            f"QPlainTextEdit:focus {{"
            f"  border: 1px solid {tokens.accent_hex};"
            f"}}"
        )
        if hasattr(self, "_d_editor") and self._d_editor is not None:
            self._d_editor.setStyleSheet(style)
        if hasattr(self, "_i_editor") and self._i_editor is not None:
            self._i_editor.setStyleSheet(style)
        if hasattr(self, "_excl_editor") and self._excl_editor is not None:
            self._excl_editor.setStyleSheet(style)
        if hasattr(self, "_ipru_editor") and self._ipru_editor is not None:
            self._ipru_editor.setStyleSheet(style)

    # ──────────────────────────────────────────────────────────────────────────
    # Hostlist / IPset folder info
    # ──────────────────────────────────────────────────────────────────────────

    def _open_lists_folder(self):
        result = HostlistPageController.open_lists_folder_action()
        self._apply_hostlist_action_result(result)

    def _rebuild_hostlists(self):
        result = HostlistPageController.rebuild_hostlists_action()
        self._apply_hostlist_action_result(result)

    def _load_info(self):
        try:
            state = HostlistPageController.load_folder_info()
            if not state.folder_exists:
                not_found = self._tr("page.hostlist.info.folder_not_found", "Папка листов не найдена")
                self.hostlist_info_label.setText(not_found)
                self.ipset_info_label.setText(not_found)
                return
            self.hostlist_info_label.setText(
                self._tr(
                    "page.hostlist.info.hostlist.summary",
                    "📁 Папка: {folder}\n📄 Файлов: {files_count}\n📝 Примерно строк: {lines_count}",
                    folder=state.folder,
                    files_count=state.hostlist_files_count,
                    lines_count=f"{state.hostlist_lines:,}",
                )
            )
            self.ipset_info_label.setText(
                self._tr(
                    "page.hostlist.info.ipset.summary",
                    "📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {lines_count}",
                    folder=state.folder,
                    files_count=state.ipset_files_count,
                    lines_count=f"{state.ipset_lines:,}",
                )
            )
        except Exception as e:
            error_text = self._tr(
                "page.hostlist.info.error",
                "Ошибка загрузки информации: {error}",
                error=e,
            )
            self.hostlist_info_label.setText(error_text)
            self.ipset_info_label.setText(error_text)

    # ──────────────────────────────────────────────────────────────────────────
    # Domains editor logic
    # ──────────────────────────────────────────────────────────────────────────

    def _load_domains(self):
        try:
            state = HostlistPageController.load_custom_domains_text()
            domains_text = state.text
            self._d_editor.blockSignals(True)
            self._d_editor.setPlainText(domains_text)
            self._d_editor.blockSignals(False)
            self._domains_update_status()
            log(f"Загружено {state.lines_count} строк из other.user.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки доменов: {e}", "ERROR")
            if hasattr(self, "_d_status"):
                self._d_status.setText(
                    self._tr("page.hostlist.status.error", "❌ Ошибка: {error}", error=e)
                )

    def _domains_on_text_changed(self):
        self._domains_save_timer.start(500)
        self._domains_update_status()

    def _domains_auto_save(self):
        self._domains_save()
        if hasattr(self, "_d_status"):
            self._d_status.setText(
                self._d_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _domains_save(self):
        try:
            text = self._d_editor.toPlainText()
            state = HostlistPageController.save_custom_domains_text(text)
            normalized_text = state.normalized_text
            if normalized_text != text:
                cursor = self._d_editor.textCursor()
                pos = cursor.position()
                self._d_editor.blockSignals(True)
                self._d_editor.setPlainText(normalized_text)
                cursor = self._d_editor.textCursor()
                cursor.setPosition(min(pos, len(normalized_text)))
                self._d_editor.setTextCursor(cursor)
                self._d_editor.blockSignals(False)
                self._domains_update_status()
            log(f"Сохранено {state.saved_count} строк в other.user.txt", "SUCCESS")
            self.domains_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения доменов: {e}", "ERROR")

    def _domains_update_status(self):
        if not hasattr(self, "_d_status") or not hasattr(self, "_d_editor"):
            return
        text = self._d_editor.toPlainText()
        plan = HostlistPageController.build_custom_domains_status_plan(text)
        self._d_status.setText(
            self._tr(
                "page.hostlist.status.domains_full_count",
                "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
                total=plan.total_count,
                base=plan.base_count,
                user=plan.user_count,
            )
        )

    def _domains_add(self):
        text = self._d_input.text().strip() if hasattr(self._d_input, "text") else ""
        if not text:
            return
        current = self._d_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_domain_plan(raw_text=text, current_text=current)
        if plan.level == "warning" and InfoBar:
            InfoBar.warning(title=plan.title or self._tr("common.error.title", "Ошибка"), content=plan.content, parent=self.window())
            return
        if plan.level == "info" and InfoBar:
            InfoBar.info(title=plan.title or self._tr("page.hostlist.infobar.info", "Информация"), content=plan.content, parent=self.window())
            return
        if plan.new_text is not None:
            self._d_editor.setPlainText(plan.new_text)
        if plan.clear_input and hasattr(self._d_input, "clear"):
            self._d_input.clear()

    def _domains_open_file(self):
        self._domains_save()
        result = HostlistPageController.open_domains_user_file_action()
        self._apply_hostlist_action_result(result)

    def _domains_confirm_reset_file(self):
        if MessageBox:
            box = MessageBox(
                self._tr("page.hostlist.button.reset_file", "Сбросить файл"),
                self._tr("page.hostlist.confirm.reset", "Подтвердить сброс"),
                self.window(),
            )
            if not box.exec():
                return
        self._domains_reset_file()

    def _domains_reset_file(self):
        result = HostlistPageController.reset_domains_file_action()
        self._apply_hostlist_action_result(result)

    def _domains_confirm_clear_all(self):
        if MessageBox:
            box = MessageBox(
                self._tr("page.hostlist.button.clear_all", "Очистить всё"),
                self._tr("page.hostlist.confirm.clear", "Подтвердить очистку"),
                self.window(),
            )
            if not box.exec():
                return
        self._domains_clear_all()

    def _domains_clear_all(self):
        self._d_editor.setPlainText("")
        self._domains_save()

    # ──────────────────────────────────────────────────────────────────────────
    # IPs editor logic
    # ──────────────────────────────────────────────────────────────────────────

    def _load_ips(self):
        try:
            state = HostlistPageController.load_custom_ipset_text()
            self._ip_base_set_cache = state.base_set
            self._i_editor.blockSignals(True)
            self._i_editor.setPlainText(state.text)
            self._i_editor.blockSignals(False)
            self._ips_update_status()
            log(f"Загружено {state.lines_count} строк из ipset-all.user.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки ipset-all.user.txt: {e}", "ERROR")
            if hasattr(self, "_i_status"):
                self._i_status.setText(
                    self._tr("page.hostlist.status.error", "❌ Ошибка: {error}", error=e)
                )

    def _ips_on_text_changed(self):
        self._ips_save_timer.start(500)
        self._ips_status_timer.start(120)

    def _ips_auto_save(self):
        self._ips_save()
        if hasattr(self, "_i_status"):
            self._i_status.setText(
                self._i_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _ips_save(self):
        try:
            text = self._i_editor.toPlainText()
            state = HostlistPageController.save_custom_ipset_text(text)
            normalized_text = state.normalized_text
            if normalized_text != text:
                cursor = self._i_editor.textCursor()
                pos = cursor.position()
                self._i_editor.blockSignals(True)
                self._i_editor.setPlainText(normalized_text)
                cursor = self._i_editor.textCursor()
                cursor.setPosition(min(pos, len(normalized_text)))
                self._i_editor.setTextCursor(cursor)
                self._i_editor.blockSignals(False)
            self._ips_update_status()
            log(f"Сохранено {state.saved_count} строк в ipset-all.user.txt", "SUCCESS")
            self.ipset_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения ipset-all.user.txt: {e}", "ERROR")

    def _ips_update_status(self):
        if not hasattr(self, "_i_status") or not hasattr(self, "_i_editor"):
            return
        text = self._i_editor.toPlainText()
        plan = HostlistPageController.build_custom_ipset_status_plan(text)

        self._i_status.setText(
            self._tr(
                "page.hostlist.status.entries_count",
                "📊 Записей: {total} (база: {base}, пользовательские: {user})",
                total=plan.total_count,
                base=plan.base_count,
                user=plan.user_count,
            )
        )
        if hasattr(self, "_i_error_label"):
            if plan.invalid_lines:
                self._i_error_label.setText(
                    self._tr(
                        "page.hostlist.ips.error.invalid_format",
                        "❌ Неверный формат: {items}",
                        items=", ".join(item for _, item in plan.invalid_lines[:5]),
                    )
                )
                self._i_error_label.show()
            else:
                self._i_error_label.hide()

    def _ips_add(self):
        text = self._i_input.text().strip() if hasattr(self._i_input, "text") else ""
        if not text:
            return
        current = self._i_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_ipset_plan(raw_text=text, current_text=current)
        if plan.level == "warning" and InfoBar:
            InfoBar.warning(title=plan.title or self._tr("common.error.title", "Ошибка"), content=plan.content, parent=self.window())
            return
        if plan.level == "info" and InfoBar:
            InfoBar.info(title=plan.title or self._tr("page.hostlist.infobar.info", "Информация"), content=plan.content, parent=self.window())
            return
        if plan.new_text is not None:
            self._i_editor.setPlainText(plan.new_text)
        if plan.clear_input and hasattr(self._i_input, "clear"):
            self._i_input.clear()

    def _ips_open_file(self):
        self._ips_save()
        result = HostlistPageController.open_ipset_all_user_file_action()
        self._apply_hostlist_action_result(result)

    def _ips_clear_all(self):
        text = self._i_editor.toPlainText().strip()
        if not text:
            return
        if MessageBox:
            box = MessageBox(
                self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
                self._tr("page.hostlist.ips.dialog.clear.body", "Удалить все записи?"),
                self.window(),
            )
            if box.exec():
                self._i_editor.clear()
        else:
            self._i_editor.clear()

    # ──────────────────────────────────────────────────────────────────────────
    # Exclusions (netrogat + ipset-ru) panel + logic
    # ──────────────────────────────────────────────────────────────────────────

    def _build_exclusions_panel(self) -> QWidget:
        tokens = get_theme_tokens()
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        desc_card = SettingsCard()
        desc = BodyLabel(
            self._tr(
                "page.hostlist.exclusions.desc",
                "Здесь два типа исключений:\n"
                "• Домены: netrogat.user.txt -> netrogat.txt (--hostlist-exclude)\n"
                "• IP/подсети: ipset-ru.user.txt -> ipset-ru.txt (--ipset-exclude)",
            )
        )
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        lay.addWidget(desc_card)

        add_card = SettingsCard(self._tr("page.hostlist.exclusions.section.add_domain", "Добавить домен"))
        self._excl_add_card = add_card
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._excl_input = LineEdit()
        if hasattr(self._excl_input, "setPlaceholderText"):
            self._excl_input.setPlaceholderText(
                self._tr(
                    "page.hostlist.exclusions.input.domain.placeholder",
                    "Например: example.com, site.com или через пробел",
                )
            )
        if hasattr(self._excl_input, "returnPressed"):
            self._excl_input.returnPressed.connect(self._excl_add)
        add_row.addWidget(self._excl_input, 1)
        self._excl_add_btn = PrimaryPushButton()
        self._excl_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        self._excl_add_btn.setIcon(qta.icon("fa5s.plus", color=tokens.accent_hex))
        self._excl_add_btn.setFixedHeight(38)
        self._excl_add_btn.clicked.connect(self._excl_add)
        add_row.addWidget(self._excl_add_btn)
        add_card.add_layout(add_row)
        lay.addWidget(add_card)

        self._excl_actions_card = None
        self._excl_actions_group = SettingCardGroup(self._tr("page.hostlist.section.actions", "Действия"), self.content)
        actions_group = self._excl_actions_group
        self._excl_actions_bar = QuickActionsBar(self.content)

        self._excl_defaults_action_card = PrimaryActionButton(
            self._tr("page.hostlist.exclusions.button.add_missing", "Добавить недостающие"),
            "fa5s.plus-circle",
        )
        self._excl_defaults_action_card.clicked.connect(self._excl_add_missing_defaults)
        set_tooltip(
            self._excl_defaults_action_card,
            self._tr("page.hostlist.exclusions.action.add_missing.description", "Восстановить недостающие домены по умолчанию в системной базе netrogat."),
        )

        self._excl_open_action_card = ActionButton(
            self._tr("page.hostlist.button.open_file", "Открыть файл"),
            "fa5s.external-link-alt",
        )
        self._excl_open_action_card.clicked.connect(self._excl_open_file)
        set_tooltip(
            self._excl_open_action_card,
            self._tr("page.hostlist.exclusions.action.open_file.description", "Сохраняет изменения и открывает netrogat.user.txt в проводнике."),
        )

        self._excl_open_final_action_card = ActionButton(
            self._tr("page.hostlist.exclusions.button.open_final", "Открыть итоговый"),
            "fa5s.file-alt",
        )
        self._excl_open_final_action_card.clicked.connect(self._excl_open_final_file)
        set_tooltip(
            self._excl_open_final_action_card,
            self._tr("page.hostlist.exclusions.action.open_final.description", "Сохраняет изменения и открывает собранный итоговый файл netrogat.txt."),
        )

        self._excl_clear_action_card = ActionButton(
            self._tr("page.hostlist.button.clear_all", "Очистить всё"),
            "fa5s.trash-alt",
        )
        self._excl_clear_action_card.clicked.connect(self._excl_clear_all)
        set_tooltip(
            self._excl_clear_action_card,
            self._tr("page.hostlist.exclusions.action.clear_all.description", "Удаляет все пользовательские домены из netrogat.user.txt."),
        )

        self._excl_actions_bar.add_buttons([
            self._excl_defaults_action_card,
            self._excl_open_action_card,
            self._excl_open_final_action_card,
            self._excl_clear_action_card,
        ])
        insert_widget_into_setting_card_group(actions_group, 1, self._excl_actions_bar)
        lay.addWidget(actions_group)

        editor_card = SettingsCard(
            self._tr("page.hostlist.exclusions.section.editor_domain", "netrogat.user.txt (редактор)")
        )
        self._excl_editor_card = editor_card
        editor_lay = QVBoxLayout()
        editor_lay.setSpacing(8)
        self._excl_editor = ScrollBlockingPlainTextEdit()
        self._excl_editor.setPlaceholderText(
            self._tr(
                "page.hostlist.exclusions.editor.domain.placeholder",
                "Домены по одному на строку:\ngosuslugi.ru\nvk.com\n\nКомментарии начинаются с #",
            )
        )
        self._excl_editor.setMinimumHeight(350)
        self._excl_editor.textChanged.connect(self._excl_on_text_changed)
        editor_lay.addWidget(self._excl_editor)
        hint = CaptionLabel(
            self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
        )
        self._excl_hint_label = hint
        editor_lay.addWidget(hint)
        editor_card.add_layout(editor_lay)
        lay.addWidget(editor_card)

        self._excl_status = CaptionLabel()
        lay.addWidget(self._excl_status)

        ipru_intro = SettingsCard()
        ipru_title = StrongBodyLabel(
            self._tr("page.hostlist.exclusions.ipru.title", "IP-исключения (--ipset-exclude)")
        )
        self._ipru_title_label = ipru_title
        ipru_title.setWordWrap(True)
        ipru_intro.add_widget(ipru_title)
        ipru_desc = CaptionLabel(
            self._tr(
                "page.hostlist.exclusions.ipru.desc",
                "Редактируйте только ipset-ru.user.txt. "
                "Системная база хранится в ipset-ru.base.txt и автоматически объединяется в ipset-ru.txt.",
            )
        )
        self._ipru_desc_label = ipru_desc
        ipru_desc.setWordWrap(True)
        ipru_intro.add_widget(ipru_desc)
        lay.addWidget(ipru_intro)

        ipru_add_card = SettingsCard(
            self._tr("page.hostlist.exclusions.ipru.section.add", "Добавить IP/подсеть в исключения")
        )
        self._ipru_add_card = ipru_add_card
        ipru_add_row = QHBoxLayout()
        ipru_add_row.setSpacing(8)
        self._ipru_input = LineEdit()
        if hasattr(self._ipru_input, "setPlaceholderText"):
            self._ipru_input.setPlaceholderText(
                self._tr("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
            )
        if hasattr(self._ipru_input, "returnPressed"):
            self._ipru_input.returnPressed.connect(self._ipru_add)
        ipru_add_row.addWidget(self._ipru_input, 1)
        self._ipru_add_btn = PrimaryPushButton()
        self._ipru_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        self._ipru_add_btn.setIcon(qta.icon("fa5s.plus", color=tokens.accent_hex))
        self._ipru_add_btn.setFixedHeight(38)
        self._ipru_add_btn.clicked.connect(self._ipru_add)
        ipru_add_row.addWidget(self._ipru_add_btn)
        ipru_add_card.add_layout(ipru_add_row)
        lay.addWidget(ipru_add_card)

        self._ipru_actions_card = None
        self._ipru_actions_group = SettingCardGroup(
            self._tr("page.hostlist.exclusions.ipru.section.actions", "Действия IP-исключений"),
            self.content,
        )
        ipru_actions_group = self._ipru_actions_group
        self._ipru_actions_bar = QuickActionsBar(self.content)
        self._ipru_open_action_card = ActionButton(
            self._tr("page.hostlist.button.open_file", "Открыть файл"),
            "fa5s.external-link-alt",
        )
        self._ipru_open_action_card.clicked.connect(self._ipru_open_file)
        set_tooltip(
            self._ipru_open_action_card,
            self._tr("page.hostlist.exclusions.ipru.action.open_file.description", "Сохраняет изменения и открывает ipset-ru.user.txt в проводнике."),
        )

        self._ipru_open_final_action_card = ActionButton(
            self._tr("page.hostlist.exclusions.button.open_final", "Открыть итоговый"),
            "fa5s.file-alt",
        )
        self._ipru_open_final_action_card.clicked.connect(self._ipru_open_final_file)
        set_tooltip(
            self._ipru_open_final_action_card,
            self._tr("page.hostlist.exclusions.ipru.action.open_final.description", "Сохраняет изменения и открывает итоговый ipset-ru.txt."),
        )

        self._ipru_clear_action_card = ActionButton(
            self._tr("page.hostlist.button.clear_all", "Очистить всё"),
            "fa5s.trash-alt",
        )
        self._ipru_clear_action_card.clicked.connect(self._ipru_clear_all)
        set_tooltip(
            self._ipru_clear_action_card,
            self._tr("page.hostlist.exclusions.ipru.action.clear_all.description", "Удаляет все пользовательские IP-исключения из ipset-ru.user.txt."),
        )

        self._ipru_actions_bar.add_buttons([
            self._ipru_open_action_card,
            self._ipru_open_final_action_card,
            self._ipru_clear_action_card,
        ])
        insert_widget_into_setting_card_group(ipru_actions_group, 1, self._ipru_actions_bar)
        lay.addWidget(ipru_actions_group)

        ipru_editor_card = SettingsCard(
            self._tr("page.hostlist.exclusions.ipru.section.editor", "ipset-ru.user.txt (редактор)")
        )
        self._ipru_editor_card = ipru_editor_card
        ipru_editor_lay = QVBoxLayout()
        ipru_editor_lay.setSpacing(8)
        self._ipru_editor = ScrollBlockingPlainTextEdit()
        self._ipru_editor.setPlaceholderText(
            self._tr(
                "page.hostlist.exclusions.ipru.editor.placeholder",
                "IP/подсети по одному на строку:\n"
                "31.13.64.0/18\n"
                "77.88.0.0/18\n\n"
                "Комментарии начинаются с #",
            )
        )
        self._ipru_editor.setMinimumHeight(260)
        self._ipru_editor.textChanged.connect(self._ipru_on_text_changed)
        ipru_editor_lay.addWidget(self._ipru_editor)
        ipru_hint = CaptionLabel(
            self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
        )
        self._ipru_hint_label = ipru_hint
        ipru_editor_lay.addWidget(ipru_hint)
        self._ipru_error_label = CaptionLabel()
        self._ipru_error_label.setWordWrap(True)
        self._ipru_error_label.hide()
        ipru_editor_lay.addWidget(self._ipru_error_label)
        ipru_editor_card.add_layout(ipru_editor_lay)
        lay.addWidget(ipru_editor_card)

        self._ipru_status = CaptionLabel()
        lay.addWidget(self._ipru_status)
        lay.addStretch()

        self._apply_editor_styles()
        return panel

    def _load_exclusions(self):
        try:
            state = HostlistPageController.load_custom_netrogat_text()
            self._excl_base_set_cache = state.base_set
            self._excl_editor.blockSignals(True)
            self._excl_editor.setPlainText(state.text)
            self._excl_editor.blockSignals(False)
            self._excl_update_status()
            log(f"Загружено {state.lines_count} строк из netrogat.user.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки netrogat: {e}", "ERROR")
            if hasattr(self, "_excl_status"):
                self._excl_status.setText(
                    self._tr("page.hostlist.status.error", "❌ Ошибка: {error}", error=e)
                )

        self._load_ipru_exclusions()

    def _load_ipru_exclusions(self):
        try:
            state = HostlistPageController.load_custom_ipru_text()
            self._ipru_base_set_cache = state.base_set

            self._ipru_editor.blockSignals(True)
            self._ipru_editor.setPlainText(state.text)
            self._ipru_editor.blockSignals(False)
            self._ipru_update_status()
            log(f"Загружено {state.lines_count} строк из ipset-ru.user.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки ipset-ru.user.txt: {e}", "ERROR")
            if hasattr(self, "_ipru_status"):
                self._ipru_status.setText(
                    self._tr("page.hostlist.status.error", "❌ Ошибка: {error}", error=e)
                )

    def _excl_on_text_changed(self):
        self._excl_save_timer.start(500)
        self._excl_update_status()

    def _excl_auto_save(self):
        self._excl_save()
        if hasattr(self, "_excl_status"):
            self._excl_status.setText(
                self._excl_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _excl_save(self):
        try:
            text = self._excl_editor.toPlainText()
            state = HostlistPageController.save_custom_netrogat_text(text)
            if state.success:
                new_text = state.normalized_text
                if new_text != text:
                    cursor = self._excl_editor.textCursor()
                    pos = cursor.position()
                    self._excl_editor.blockSignals(True)
                    self._excl_editor.setPlainText(new_text)
                    cursor = self._excl_editor.textCursor()
                    cursor.setPosition(min(pos, len(new_text)))
                    self._excl_editor.setTextCursor(cursor)
                    self._excl_editor.blockSignals(False)
        except Exception as e:
            log(f"Ошибка сохранения netrogat: {e}", "ERROR")

    def _excl_update_status(self):
        if not hasattr(self, "_excl_status") or not hasattr(self, "_excl_editor"):
            return

        text = self._excl_editor.toPlainText()
        plan = HostlistPageController.build_custom_netrogat_status_plan(text)
        self._excl_status.setText(
            self._tr(
                "page.hostlist.status.domains_full_count",
                "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
                total=plan.total_count,
                base=plan.base_count,
                user=plan.user_count,
            )
        )

    def _excl_add(self):
        raw = self._excl_input.text().strip() if hasattr(self._excl_input, "text") else ""
        if not raw:
            return
        current = self._excl_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_netrogat_plan(raw_text=raw, current_text=current)
        if plan.level == "warning" and InfoBar:
            InfoBar.warning(title=plan.title or self._tr("common.error.title", "Ошибка"), content=plan.content, parent=self.window())
            return
        if plan.level == "info" and InfoBar:
            InfoBar.info(title=plan.title or self._tr("page.hostlist.infobar.info", "Информация"), content=plan.content, parent=self.window())
            return
        if plan.new_text is not None:
            self._excl_editor.setPlainText(plan.new_text)
        if plan.clear_input and hasattr(self._excl_input, "clear"):
            self._excl_input.clear()
        if plan.level == "success" and InfoBar:
            InfoBar.success(title=plan.title or self._tr("page.hostlist.infobar.added", "Добавлено"), content=plan.content, parent=self.window())

    def _excl_open_file(self):
        self._excl_save()
        result = HostlistPageController.open_netrogat_user_file_action()
        self._apply_hostlist_action_result(result)

    def _excl_open_final_file(self):
        self._excl_save()
        result = HostlistPageController.open_netrogat_final_file_action()
        self._apply_hostlist_action_result(result)

    def _excl_clear_all(self):
        text = self._excl_editor.toPlainText().strip()
        if not text:
            return
        if MessageBox:
            box = MessageBox(
                self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
                self._tr("page.hostlist.exclusions.dialog.clear.body", "Удалить все домены?"),
                self.window(),
            )
            if box.exec():
                self._excl_editor.clear()
        else:
            self._excl_editor.clear()

    def _excl_add_missing_defaults(self):
        self._excl_save()
        result = HostlistPageController.add_missing_netrogat_defaults_action()
        self._apply_hostlist_action_result(result)

    def _ipru_on_text_changed(self):
        self._ipru_save_timer.start(500)
        self._ipru_status_timer.start(120)

    def _ipru_auto_save(self):
        self._ipru_save()
        if hasattr(self, "_ipru_status"):
            self._ipru_status.setText(
                self._ipru_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _ipru_save(self):
        try:
            text = self._ipru_editor.toPlainText()
            state = HostlistPageController.save_custom_ipru_text(text)
            normalized_text = state.normalized_text
            if normalized_text != text:
                cursor = self._ipru_editor.textCursor()
                pos = cursor.position()
                self._ipru_editor.blockSignals(True)
                self._ipru_editor.setPlainText(normalized_text)
                cursor = self._ipru_editor.textCursor()
                cursor.setPosition(min(pos, len(normalized_text)))
                self._ipru_editor.setTextCursor(cursor)
                self._ipru_editor.blockSignals(False)
            self._ipru_update_status()
            log(f"Сохранено {state.saved_count} строк в ipset-ru.user.txt", "SUCCESS")
        except Exception as e:
            log(f"Ошибка сохранения ipset-ru.user.txt: {e}", "ERROR")

    def _ipru_update_status(self):
        if not hasattr(self, "_ipru_status") or not hasattr(self, "_ipru_editor"):
            return

        text = self._ipru_editor.toPlainText()
        plan = HostlistPageController.build_custom_ipru_status_plan(text)
        self._ipru_status.setText(
            self._tr(
                "page.hostlist.status.ipru_count",
                "📊 IP-исключений: {total} (база: {base}, пользовательские: {user})",
                total=plan.total_count,
                base=plan.base_count,
                user=plan.user_count,
            )
        )
        if hasattr(self, "_ipru_error_label"):
            if plan.invalid_lines:
                self._ipru_error_label.setText(
                    self._tr(
                        "page.hostlist.ips.error.invalid_format",
                        "❌ Неверный формат: {items}",
                        items=", ".join(item for _, item in plan.invalid_lines[:5]),
                    )
                )
                self._ipru_error_label.show()
            else:
                self._ipru_error_label.hide()

    def _ipru_add(self):
        raw = self._ipru_input.text().strip() if hasattr(self._ipru_input, "text") else ""
        if not raw:
            return

        current = self._ipru_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_ipru_plan(raw_text=raw, current_text=current)
        if plan.level == "warning" and InfoBar:
            InfoBar.warning(title=plan.title or self._tr("common.error.title", "Ошибка"), content=plan.content, parent=self.window())
            return
        if plan.level == "info" and InfoBar:
            InfoBar.info(title=plan.title or self._tr("page.hostlist.infobar.info", "Информация"), content=plan.content, parent=self.window())
            return
        if plan.new_text is not None:
            self._ipru_editor.setPlainText(plan.new_text)
        if plan.clear_input and hasattr(self._ipru_input, "clear"):
            self._ipru_input.clear()

        if plan.level == "success" and InfoBar:
            InfoBar.success(title=plan.title or self._tr("page.hostlist.infobar.added", "Добавлено"), content=plan.content, parent=self.window())

    def _ipru_open_file(self):
        self._ipru_save()
        result = HostlistPageController.open_ipset_ru_user_file_action()
        self._apply_hostlist_action_result(result)

    def _ipru_open_final_file(self):
        self._ipru_save()
        result = HostlistPageController.open_ipset_ru_final_file_action()
        self._apply_hostlist_action_result(result)

    def _ipru_clear_all(self):
        text = self._ipru_editor.toPlainText().strip()
        if not text:
            return
        if MessageBox:
            box = MessageBox(
                self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
                self._tr("page.hostlist.exclusions.ipru.dialog.clear.body", "Удалить все IP-исключения?"),
                self.window(),
            )
            if box.exec():
                self._ipru_editor.clear()
        else:
            self._ipru_editor.clear()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self.pivot is not None:
            self.pivot.setItemText("hostlist", self._tr("page.hostlist.tab.hostlist", "Hostlist"))
            self.pivot.setItemText("ipset", self._tr("page.hostlist.tab.ipset", "IPset"))
            self.pivot.setItemText("domains", self._tr("page.hostlist.tab.domains", "Мои домены"))
            self.pivot.setItemText("ips", self._tr("page.hostlist.tab.ips", "Мои IP"))
            self.pivot.setItemText("exclusions", self._tr("page.hostlist.tab.exclusions", "Исключения"))

        if hasattr(self, "_hostlist_desc_label"):
            self._hostlist_desc_label.setText(
                self._tr("page.hostlist.hostlist.desc", "Используется для обхода блокировок по доменам.")
            )
        if hasattr(self, "_ipset_desc_label"):
            self._ipset_desc_label.setText(
                self._tr("page.hostlist.ipset.desc", "Используется для обхода блокировок по IP-адресам и подсетям.")
            )
        if hasattr(self, "_hostlist_manage_card"):
            self._hostlist_manage_card.set_title(self._tr("page.hostlist.section.manage", "Управление"))
        if hasattr(self, "_hostlist_manage_group"):
            try:
                self._hostlist_manage_group.titleLabel.setText(self._tr("page.hostlist.section.manage", "Управление"))
            except Exception:
                pass
        if hasattr(self, "_hostlist_open_folder_action_card"):
            self._hostlist_open_folder_action_card.setText(self._tr("page.hostlist.button.open", "Открыть"))
            set_tooltip(
                self._hostlist_open_folder_action_card,
                self._tr(
                    "page.hostlist.hostlist.action.open_folder.description",
                    "Открыть общую папку hostlist и ipset списков в проводнике.",
                ),
            )
        if hasattr(self, "_hostlist_rebuild_action_card"):
            self._hostlist_rebuild_action_card.setText(self._tr("page.hostlist.button.rebuild", "Перестроить"))
            set_tooltip(
                self._hostlist_rebuild_action_card,
                self._tr(
                    "page.hostlist.hostlist.action.rebuild.subtitle",
                    "Обновляет списки из встроенной базы",
                ),
            )
        if hasattr(self, "_ipset_manage_card"):
            self._ipset_manage_card.set_title(self._tr("page.hostlist.section.manage", "Управление"))
        if hasattr(self, "_ipset_manage_group"):
            try:
                self._ipset_manage_group.titleLabel.setText(self._tr("page.hostlist.section.manage", "Управление"))
            except Exception:
                pass
        if hasattr(self, "_ipset_open_folder_action_card"):
            self._ipset_open_folder_action_card.setText(self._tr("page.hostlist.button.open", "Открыть"))
            set_tooltip(
                self._ipset_open_folder_action_card,
                self._tr(
                    "page.hostlist.ipset.action.open_folder.description",
                    "Открыть общую папку hostlist и ipset списков в проводнике.",
                ),
            )

        if hasattr(self, "_domains_add_card"):
            self._domains_add_card.set_title(self._tr("page.hostlist.domains.section.add", "Добавить домен"))
        if hasattr(self, "_domains_actions_card"):
            self._domains_actions_card.set_title(self._tr("page.hostlist.section.actions", "Действия"))
        if hasattr(self, "_domains_actions_group"):
            try:
                self._domains_actions_group.titleLabel.setText(self._tr("page.hostlist.section.actions", "Действия"))
            except Exception:
                pass
        if hasattr(self, "_domains_editor_card"):
            self._domains_editor_card.set_title(self._tr("page.hostlist.domains.section.editor", "other.user.txt (редактор)"))
        if hasattr(self, "_d_input"):
            self._d_input.setPlaceholderText(
                self._tr("page.hostlist.domains.input.placeholder", "Введите домен или URL (например: example.com)")
            )
        if hasattr(self, "_d_add_btn"):
            self._d_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        if hasattr(self, "_domains_open_action_card"):
            self._domains_open_action_card.setText(self._tr("page.hostlist.button.open_file", "Открыть файл"))
            set_tooltip(
                self._domains_open_action_card,
                self._tr(
                    "page.hostlist.domains.tooltip.open_file",
                    "Сохраняет изменения и открывает other.user.txt в проводнике",
                ),
            )
        if hasattr(self, "_domains_reset_action_card"):
            self._domains_reset_action_card.setText(self._tr("page.hostlist.button.reset_file", "Сбросить файл"))
            set_tooltip(
                self._domains_reset_action_card,
                self._tr(
                    "page.hostlist.domains.tooltip.reset_file",
                    "Очищает other.user.txt и пересобирает other.txt из системной базы",
                ),
            )
        if hasattr(self, "_domains_clear_action_card"):
            self._domains_clear_action_card.setText(self._tr("page.hostlist.button.clear_all", "Очистить всё"))
            set_tooltip(
                self._domains_clear_action_card,
                self._tr("page.hostlist.domains.tooltip.clear_all", "Удаляет только пользовательские домены"),
            )
        if hasattr(self, "_d_editor"):
            self._d_editor.setPlaceholderText(
                self._tr(
                    "page.hostlist.domains.editor.placeholder",
                    "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
                )
            )
        if hasattr(self, "_domains_hint_label"):
            self._domains_hint_label.setText(
                self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
            )

        if hasattr(self, "_ips_add_card"):
            self._ips_add_card.set_title(self._tr("page.hostlist.ips.section.add", "Добавить IP/подсеть"))
        if hasattr(self, "_ips_actions_card"):
            self._ips_actions_card.set_title(self._tr("page.hostlist.section.actions", "Действия"))
        if hasattr(self, "_ips_actions_group"):
            try:
                self._ips_actions_group.titleLabel.setText(self._tr("page.hostlist.section.actions", "Действия"))
            except Exception:
                pass
        if hasattr(self, "_ips_editor_card"):
            self._ips_editor_card.set_title(self._tr("page.hostlist.ips.section.editor", "ipset-all.user.txt (редактор)"))
        if hasattr(self, "_i_input"):
            self._i_input.setPlaceholderText(
                self._tr("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
            )
        if hasattr(self, "_i_add_btn"):
            self._i_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        if hasattr(self, "_ips_open_action_card"):
            self._ips_open_action_card.setText(self._tr("page.hostlist.button.open_file", "Открыть файл"))
            set_tooltip(
                self._ips_open_action_card,
                self._tr("page.hostlist.ips.action.open_file.description", "Сохраняет изменения и открывает ipset-all.user.txt в проводнике."),
            )
        if hasattr(self, "_ips_clear_action_card"):
            self._ips_clear_action_card.setText(self._tr("page.hostlist.button.clear_all", "Очистить всё"))
            set_tooltip(
                self._ips_clear_action_card,
                self._tr("page.hostlist.ips.action.clear_all.description", "Удаляет все пользовательские IP и подсети."),
            )
        if hasattr(self, "_i_editor"):
            self._i_editor.setPlaceholderText(
                self._tr(
                    "page.hostlist.ips.editor.placeholder",
                    "IP/подсети по одному на строку:\n192.168.0.1\n10.0.0.0/8\n\nКомментарии начинаются с #",
                )
            )
        if hasattr(self, "_ips_hint_label"):
            self._ips_hint_label.setText(
                self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
            )

        if hasattr(self, "_excl_add_card"):
            self._excl_add_card.set_title(self._tr("page.hostlist.exclusions.section.add_domain", "Добавить домен"))
        if hasattr(self, "_excl_actions_card"):
            self._excl_actions_card.set_title(self._tr("page.hostlist.section.actions", "Действия"))
        if hasattr(self, "_excl_actions_group"):
            try:
                self._excl_actions_group.titleLabel.setText(self._tr("page.hostlist.section.actions", "Действия"))
            except Exception:
                pass
        if hasattr(self, "_excl_editor_card"):
            self._excl_editor_card.set_title(self._tr("page.hostlist.exclusions.section.editor_domain", "netrogat.user.txt (редактор)"))
        if hasattr(self, "_excl_input"):
            self._excl_input.setPlaceholderText(
                self._tr(
                    "page.hostlist.exclusions.input.domain.placeholder",
                    "Например: example.com, site.com или через пробел",
                )
            )
        if hasattr(self, "_excl_add_btn"):
            self._excl_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        if hasattr(self, "_excl_defaults_action_card"):
            self._excl_defaults_action_card.setText(self._tr("page.hostlist.exclusions.button.add_missing", "Добавить недостающие"))
            set_tooltip(
                self._excl_defaults_action_card,
                self._tr("page.hostlist.exclusions.action.add_missing.description", "Восстановить недостающие домены по умолчанию в системной базе netrogat."),
            )
        if hasattr(self, "_excl_open_action_card"):
            self._excl_open_action_card.setText(self._tr("page.hostlist.button.open_file", "Открыть файл"))
            set_tooltip(
                self._excl_open_action_card,
                self._tr("page.hostlist.exclusions.action.open_file.description", "Сохраняет изменения и открывает netrogat.user.txt в проводнике."),
            )
        if hasattr(self, "_excl_open_final_action_card"):
            self._excl_open_final_action_card.setText(self._tr("page.hostlist.exclusions.button.open_final", "Открыть итоговый"))
            set_tooltip(
                self._excl_open_final_action_card,
                self._tr("page.hostlist.exclusions.action.open_final.description", "Сохраняет изменения и открывает собранный итоговый файл netrogat.txt."),
            )
        if hasattr(self, "_excl_clear_action_card"):
            self._excl_clear_action_card.setText(self._tr("page.hostlist.button.clear_all", "Очистить всё"))
            set_tooltip(
                self._excl_clear_action_card,
                self._tr("page.hostlist.exclusions.action.clear_all.description", "Удаляет все пользовательские домены из netrogat.user.txt."),
            )
        if hasattr(self, "_excl_editor"):
            self._excl_editor.setPlaceholderText(
                self._tr(
                    "page.hostlist.exclusions.editor.domain.placeholder",
                    "Домены по одному на строку:\ngosuslugi.ru\nvk.com\n\nКомментарии начинаются с #",
                )
            )
        if hasattr(self, "_excl_hint_label"):
            self._excl_hint_label.setText(
                self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
            )

        if hasattr(self, "_ipru_title_label"):
            self._ipru_title_label.setText(
                self._tr("page.hostlist.exclusions.ipru.title", "IP-исключения (--ipset-exclude)")
            )
        if hasattr(self, "_ipru_desc_label"):
            self._ipru_desc_label.setText(
                self._tr(
                    "page.hostlist.exclusions.ipru.desc",
                    "Редактируйте только ipset-ru.user.txt. Системная база хранится в ipset-ru.base.txt и автоматически объединяется в ipset-ru.txt.",
                )
            )
        if hasattr(self, "_ipru_add_card"):
            self._ipru_add_card.set_title(self._tr("page.hostlist.exclusions.ipru.section.add", "Добавить IP/подсеть в исключения"))
        if hasattr(self, "_ipru_actions_card"):
            self._ipru_actions_card.set_title(self._tr("page.hostlist.exclusions.ipru.section.actions", "Действия IP-исключений"))
        if hasattr(self, "_ipru_actions_group"):
            try:
                self._ipru_actions_group.titleLabel.setText(
                    self._tr("page.hostlist.exclusions.ipru.section.actions", "Действия IP-исключений")
                )
            except Exception:
                pass
        if hasattr(self, "_ipru_editor_card"):
            self._ipru_editor_card.set_title(self._tr("page.hostlist.exclusions.ipru.section.editor", "ipset-ru.user.txt (редактор)"))
        if hasattr(self, "_ipru_input"):
            self._ipru_input.setPlaceholderText(
                self._tr("page.hostlist.ips.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
            )
        if hasattr(self, "_ipru_add_btn"):
            self._ipru_add_btn.setText(self._tr("page.hostlist.button.add", "Добавить"))
        if hasattr(self, "_ipru_open_action_card"):
            self._ipru_open_action_card.setText(self._tr("page.hostlist.button.open_file", "Открыть файл"))
            set_tooltip(
                self._ipru_open_action_card,
                self._tr("page.hostlist.exclusions.ipru.action.open_file.description", "Сохраняет изменения и открывает ipset-ru.user.txt в проводнике."),
            )
        if hasattr(self, "_ipru_open_final_action_card"):
            self._ipru_open_final_action_card.setText(self._tr("page.hostlist.exclusions.button.open_final", "Открыть итоговый"))
            set_tooltip(
                self._ipru_open_final_action_card,
                self._tr("page.hostlist.exclusions.ipru.action.open_final.description", "Сохраняет изменения и открывает итоговый ipset-ru.txt."),
            )
        if hasattr(self, "_ipru_clear_action_card"):
            self._ipru_clear_action_card.setText(self._tr("page.hostlist.button.clear_all", "Очистить всё"))
            set_tooltip(
                self._ipru_clear_action_card,
                self._tr("page.hostlist.exclusions.ipru.action.clear_all.description", "Удаляет все пользовательские IP-исключения из ipset-ru.user.txt."),
            )
        if hasattr(self, "_ipru_editor"):
            self._ipru_editor.setPlaceholderText(
                self._tr(
                    "page.hostlist.exclusions.ipru.editor.placeholder",
                    "IP/подсети по одному на строку:\n31.13.64.0/18\n77.88.0.0/18\n\nКомментарии начинаются с #",
                )
            )
        if hasattr(self, "_ipru_hint_label"):
            self._ipru_hint_label.setText(
                self._tr("page.hostlist.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
            )

        self._load_info()
        self._domains_update_status()
        self._ips_update_status()
        self._excl_update_status()
        self._ipru_update_status()
