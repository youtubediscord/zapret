# lists/ui/hostlist_page.py
"""Объединённая страница «Листы»: обзор hostlist / ipset + редакторы доменов и IP."""

import os
import qtawesome as qta

from PyQt6.QtCore import QTimer, pyqtSignal

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from lists.controller import HostlistPageController

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, InfoBar, LineEdit, MessageBox, SegmentedWidget,
        StrongBodyLabel, SettingCardGroup, PushButton, PrimaryPushButton,
    )
except ImportError:
    raise

from ui.pages.base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log
from lists.ui.hostlist_page_editors_build import build_domains_panel_ui, build_ips_panel_ui
from lists.ui.hostlist_page_exclusions_build import build_exclusions_panel_ui
from lists.ui.hostlist_page_exclusions_workflow import (
    update_exclusions_status,
    update_ipru_status,
)
from lists.ui.hostlist_page_folder_info import (
    accept_folder_info_failed,
    accept_folder_info_loaded,
    build_folder_info_error_text,
    build_folder_info_text,
    normalize_folder_info_category,
    request_folder_info,
    start_folder_info_thread,
)
from lists.ui.hostlist_page_overview_build import build_overview_panel
from lists.ui.hostlist_page_tabs import CurrentPanelStackedWidget, switch_hostlist_tab
from lists.ui.hostlist_page_text_workflow import (
    apply_add_plan,
    apply_normalized_text,
    clear_editor_with_confirm,
    load_text_into_editor,
    update_domains_status,
    update_ips_status,
)


class HostlistPage(BasePage):
    """Страница «Листы»: обзор hostlist/ipset + редакторы пользовательских доменов и IP."""

    domains_changed = pyqtSignal()
    ipset_changed = pyqtSignal()
    folder_info_loaded = pyqtSignal(str, int, object)
    folder_info_failed = pyqtSignal(str, int, str)

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
        self._cleanup_in_progress = False
        self._folder_info_request_seq = {"hostlist": 0, "ipset": 0}
        self._folder_info_loading = {"hostlist": False, "ipset": False}
        self._folder_info_loaded = {"hostlist": False, "ipset": False}
        self._folder_info_state = {"hostlist": None, "ipset": None}
        self.folder_info_loaded.connect(self._on_folder_info_loaded)
        self.folder_info_failed.connect(self._on_folder_info_failed)

        # Autosave timers (created early so textChanged can reference them before panel is shown)
        self._domains_save_timer = QTimer(self)
        self._domains_save_timer.setSingleShot(True)
        self._domains_save_timer.timeout.connect(self._domains_auto_save)

        self._ips_save_timer = QTimer(self)
        self._ips_save_timer.setSingleShot(True)
        self._ips_save_timer.timeout.connect(self._ips_auto_save)

        self._ips_status_timer = QTimer(self)
        self._ips_status_timer.setSingleShot(True)
        self._ips_status_timer.timeout.connect(self._ips_update_status)
        self._ip_base_set_cache: set[str] | None = None

        self._excl_loaded = False
        self._excl_base_set_cache: set[str] | None = None
        self._excl_save_timer = QTimer(self)
        self._excl_save_timer.setSingleShot(True)
        self._excl_save_timer.timeout.connect(self._excl_auto_save)

        self._ipru_base_set_cache: set[str] | None = None
        self._ipru_save_timer = QTimer(self)
        self._ipru_save_timer.setSingleShot(True)
        self._ipru_save_timer.timeout.connect(self._ipru_auto_save)
        self._ipru_status_timer = QTimer(self)
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
            self._load_info(force=True)

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
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._load_info())


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
        result = switch_hostlist_tab(
            index=index,
            stacked=self.stacked,
            pivot=self.pivot,
            refresh_geometry_fn=self._refresh_stacked_geometry,
            request_folder_info_fn=self._request_folder_info,
            domains_loaded=self._domains_loaded,
            ips_loaded=self._ips_loaded,
            excl_loaded=self._excl_loaded,
            schedule_fn=QTimer.singleShot,
            load_domains_fn=self._load_domains,
            load_ips_fn=self._load_ips,
            load_exclusions_fn=self._load_exclusions,
        )
        self._domains_loaded = result.domains_loaded
        self._ips_loaded = result.ips_loaded
        self._excl_loaded = result.excl_loaded

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
        overview = build_overview_panel(
            content_parent=self.content,
            tr_fn=self._tr,
            get_theme_tokens_fn=get_theme_tokens,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            action_button_cls=ActionButton,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            set_tooltip_fn=set_tooltip,
            desc_key="page.hostlist.hostlist.desc",
            desc_default="Используется для обхода блокировок по доменам.",
            open_tooltip_key="page.hostlist.hostlist.action.open_folder.description",
            open_tooltip_default="Открыть общую папку hostlist и ipset списков в проводнике.",
            on_open=self._open_lists_folder,
            on_rebuild=self._rebuild_hostlists,
            rebuild_tooltip_key="page.hostlist.hostlist.action.rebuild.subtitle",
            rebuild_tooltip_default="Обновляет списки из встроенной базы",
        )
        self._hostlist_desc_label = overview.desc_label
        self._hostlist_manage_group = overview.manage_group
        self._hostlist_actions_bar = overview.actions_bar
        self._hostlist_open_folder_action_card = overview.open_button
        self._hostlist_rebuild_action_card = overview.rebuild_button
        self._hostlist_info_card = overview.info_card
        self.hostlist_info_label = overview.info_label
        self._hostlist_manage_card = None
        return overview.panel

    def _build_ipset_panel(self) -> QWidget:
        overview = build_overview_panel(
            content_parent=self.content,
            tr_fn=self._tr,
            get_theme_tokens_fn=get_theme_tokens,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            action_button_cls=ActionButton,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            set_tooltip_fn=set_tooltip,
            desc_key="page.hostlist.ipset.desc",
            desc_default="Используется для обхода блокировок по IP-адресам и подсетям.",
            open_tooltip_key="page.hostlist.ipset.action.open_folder.description",
            open_tooltip_default="Открыть общую папку hostlist и ipset списков в проводнике.",
            on_open=self._open_lists_folder,
        )
        self._ipset_desc_label = overview.desc_label
        self._ipset_manage_group = overview.manage_group
        self._ipset_actions_bar = overview.actions_bar
        self._ipset_open_folder_action_card = overview.open_button
        self._ipset_info_card = overview.info_card
        self.ipset_info_label = overview.info_label
        self._ipset_manage_card = None
        return overview.panel

    def _build_domains_panel(self) -> QWidget:
        widgets = build_domains_panel_ui(
            content_parent=self.content,
            tr_fn=self._tr,
            get_theme_tokens_fn=get_theme_tokens,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            line_edit_cls=LineEdit,
            primary_push_button_cls=PrimaryPushButton,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            action_button_cls=ActionButton,
            plain_text_edit_cls=ScrollBlockingPlainTextEdit,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            set_tooltip_fn=set_tooltip,
            qta_module=qta,
            on_add=self._domains_add,
            on_open_file=self._domains_open_file,
            on_reset_file=self._domains_confirm_reset_file,
            on_clear_all=self._domains_confirm_clear_all,
            on_text_changed=self._domains_on_text_changed,
        )
        self._domains_add_card = widgets.add_card
        self._d_input = widgets.input_edit
        self._d_add_btn = widgets.add_button
        self._domains_actions_group = widgets.actions_group
        self._domains_actions_bar = widgets.actions_bar
        self._domains_open_action_card = widgets.open_action
        self._domains_reset_action_card = widgets.reset_action
        self._domains_clear_action_card = widgets.clear_action
        self._domains_editor_card = widgets.editor_card
        self._d_editor = widgets.editor
        self._domains_hint_label = widgets.hint_label
        self._d_status = widgets.status_label
        self._domains_actions_card = None

        self._apply_editor_styles()
        return widgets.panel

    def _build_ips_panel(self) -> QWidget:
        widgets = build_ips_panel_ui(
            content_parent=self.content,
            tr_fn=self._tr,
            get_theme_tokens_fn=get_theme_tokens,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            line_edit_cls=LineEdit,
            primary_push_button_cls=PrimaryPushButton,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            action_button_cls=ActionButton,
            plain_text_edit_cls=ScrollBlockingPlainTextEdit,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            set_tooltip_fn=set_tooltip,
            qta_module=qta,
            on_add=self._ips_add,
            on_open_file=self._ips_open_file,
            on_clear_all=self._ips_clear_all,
            on_text_changed=self._ips_on_text_changed,
        )
        self._ips_add_card = widgets.add_card
        self._i_input = widgets.input_edit
        self._i_add_btn = widgets.add_button
        self._ips_actions_group = widgets.actions_group
        self._ips_actions_bar = widgets.actions_bar
        self._ips_open_action_card = widgets.open_action
        self._ips_clear_action_card = widgets.clear_action
        self._ips_editor_card = widgets.editor_card
        self._i_editor = widgets.editor
        self._ips_hint_label = widgets.hint_label
        self._i_error_label = widgets.error_label
        self._i_status = widgets.status_label
        self._ips_actions_card = None

        self._apply_editor_styles()
        return widgets.panel

    def _apply_page_theme(self, tokens=None, force: bool = False):
        _ = force
        self._apply_editor_styles(tokens=tokens)

    def _apply_editor_styles(self, tokens=None):
        tokens = tokens or get_theme_tokens()

        if hasattr(self, "_accent_icon_lbls"):
            for lbl, icon_name in self._accent_icon_lbls:
                try:
                    lbl.setPixmap(get_cached_qta_pixmap(icon_name, color=tokens.accent_hex, size=18))
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

    def _load_info(self, *, force: bool = False):
        if self._cleanup_in_progress:
            return
        self._request_folder_info("hostlist", force=force)
        if force or self.stacked.currentIndex() == 1 or self._folder_info_loaded.get("ipset"):
            self._request_folder_info("ipset", force=force)

    def _set_folder_info_loading(self, category: str) -> None:
        loading_text = self._tr("page.hostlist.info.loading", "Загрузка информации...")
        if category == "ipset":
            self.ipset_info_label.setText(loading_text)
        else:
            self.hostlist_info_label.setText(loading_text)

    def _apply_folder_info_state(self, category: str, state) -> None:
        text = build_folder_info_text(
            category=category,
            state=state,
            tr_fn=self._tr,
        )

        if category == "ipset":
            self.ipset_info_label.setText(text)
        else:
            self.hostlist_info_label.setText(text)

    def _apply_folder_info_error(self, category: str, error: str) -> None:
        error_text = build_folder_info_error_text(
            error=error,
            tr_fn=self._tr,
        )
        if category == "ipset":
            self.ipset_info_label.setText(error_text)
        else:
            self.hostlist_info_label.setText(error_text)

    def _request_folder_info(self, category: str, *, force: bool = False) -> None:
        if self._cleanup_in_progress:
            return
        should_start, normalized, request_seq = request_folder_info(
            category=category,
            force=force,
            request_seq_map=self._folder_info_request_seq,
            loading_map=self._folder_info_loading,
            loaded_map=self._folder_info_loaded,
            state_map=self._folder_info_state,
        )
        if not should_start:
            return
        self._set_folder_info_loading(normalized)

        start_folder_info_thread(
            load_worker_fn=self._load_folder_info_worker,
            category=normalized,
            request_seq=request_seq,
        )

    def _load_folder_info_worker(self, category: str, request_seq: int) -> None:
        try:
            if category == "ipset":
                state = HostlistPageController.load_ipset_folder_info()
            else:
                state = HostlistPageController.load_hostlist_folder_info()
            self.folder_info_loaded.emit(category, request_seq, state)
        except Exception as e:
            self.folder_info_failed.emit(category, request_seq, str(e))

    def _on_folder_info_loaded(self, category: str, request_seq: int, state) -> None:
        if self._cleanup_in_progress:
            return
        accepted, normalized = accept_folder_info_loaded(
            category=category,
            request_seq=request_seq,
            state=state,
            request_seq_map=self._folder_info_request_seq,
            loading_map=self._folder_info_loading,
            loaded_map=self._folder_info_loaded,
            state_map=self._folder_info_state,
        )
        if not accepted:
            return
        self._apply_folder_info_state(normalized, state)

    def _on_folder_info_failed(self, category: str, request_seq: int, error: str) -> None:
        if self._cleanup_in_progress:
            return
        accepted, normalized = accept_folder_info_failed(
            category=category,
            request_seq=request_seq,
            request_seq_map=self._folder_info_request_seq,
            loading_map=self._folder_info_loading,
            loaded_map=self._folder_info_loaded,
            state_map=self._folder_info_state,
        )
        if not accepted:
            return
        self._apply_folder_info_error(normalized, error)

    def _refresh_folder_info_labels(self) -> None:
        for category in ("hostlist", "ipset"):
            state = self._folder_info_state.get(category)
            if state is not None:
                self._apply_folder_info_state(normalize_folder_info_category(category), state)
            elif self._folder_info_loading.get(category) or not self._folder_info_loaded.get(category):
                self._set_folder_info_loading(normalize_folder_info_category(category))

    # ──────────────────────────────────────────────────────────────────────────
    # Domains editor logic
    # ──────────────────────────────────────────────────────────────────────────

    def _load_domains(self):
        if self._cleanup_in_progress:
            return
        try:
            state = HostlistPageController.load_custom_domains_text()
            domains_text = state.text
            load_text_into_editor(self._d_editor, domains_text)
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
        if self._cleanup_in_progress:
            return
        self._domains_save()
        if hasattr(self, "_d_status"):
            self._d_status.setText(
                self._d_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _domains_save(self):
        try:
            text = self._d_editor.toPlainText()
            state = HostlistPageController.save_custom_domains_text(text)
            apply_normalized_text(
                self._d_editor,
                state.normalized_text,
                current_text=text,
                update_status_fn=self._domains_update_status,
            )
            log(f"Сохранено {state.saved_count} строк в other.user.txt", "SUCCESS")
            self.domains_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения доменов: {e}", "ERROR")

    def _domains_update_status(self):
        if not hasattr(self, "_d_status") or not hasattr(self, "_d_editor"):
            return
        update_domains_status(
            self._d_status,
            self._d_editor,
            build_plan_fn=HostlistPageController.build_custom_domains_status_plan,
            tr_fn=self._tr,
        )

    def _domains_add(self):
        text = self._d_input.text().strip() if hasattr(self._d_input, "text") else ""
        if not text:
            return
        current = self._d_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_domain_plan(raw_text=text, current_text=current)
        apply_add_plan(
            plan=plan,
            input_widget=self._d_input,
            editor_widget=self._d_editor,
            info_bar=InfoBar,
            window=self.window(),
            tr_fn=self._tr,
        )

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
        if clear_editor_with_confirm(
            editor=self._d_editor,
            message_box_cls=MessageBox,
            window=self.window(),
            title=self._tr("page.hostlist.button.clear_all", "Очистить всё"),
            body=self._tr("page.hostlist.confirm.clear", "Подтвердить очистку"),
        ):
            self._domains_save()

    # ──────────────────────────────────────────────────────────────────────────
    # IPs editor logic
    # ──────────────────────────────────────────────────────────────────────────

    def _load_ips(self):
        if self._cleanup_in_progress:
            return
        try:
            state = HostlistPageController.load_custom_ipset_text()
            self._ip_base_set_cache = state.base_set
            load_text_into_editor(self._i_editor, state.text)
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
        if self._cleanup_in_progress:
            return
        self._ips_save()
        if hasattr(self, "_i_status"):
            self._i_status.setText(
                self._i_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def _ips_save(self):
        try:
            text = self._i_editor.toPlainText()
            state = HostlistPageController.save_custom_ipset_text(text)
            apply_normalized_text(
                self._i_editor,
                state.normalized_text,
                current_text=text,
                update_status_fn=self._ips_update_status,
            )
            self._ips_update_status()
            log(f"Сохранено {state.saved_count} строк в ipset-all.user.txt", "SUCCESS")
            self.ipset_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения ipset-all.user.txt: {e}", "ERROR")

    def _ips_update_status(self):
        if not hasattr(self, "_i_status") or not hasattr(self, "_i_editor"):
            return
        update_ips_status(
            self._i_status,
            getattr(self, "_i_error_label", None),
            self._i_editor,
            build_plan_fn=HostlistPageController.build_custom_ipset_status_plan,
            tr_fn=self._tr,
        )

    def _ips_add(self):
        text = self._i_input.text().strip() if hasattr(self._i_input, "text") else ""
        if not text:
            return
        current = self._i_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_ipset_plan(raw_text=text, current_text=current)
        apply_add_plan(
            plan=plan,
            input_widget=self._i_input,
            editor_widget=self._i_editor,
            info_bar=InfoBar,
            window=self.window(),
            tr_fn=self._tr,
        )

    def _ips_open_file(self):
        self._ips_save()
        result = HostlistPageController.open_ipset_all_user_file_action()
        self._apply_hostlist_action_result(result)

    def _ips_clear_all(self):
        clear_editor_with_confirm(
            editor=self._i_editor,
            message_box_cls=MessageBox,
            window=self.window(),
            title=self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
            body=self._tr("page.hostlist.ips.dialog.clear.body", "Удалить все записи?"),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Exclusions (netrogat + ipset-ru) panel + logic
    # ──────────────────────────────────────────────────────────────────────────

    def _build_exclusions_panel(self) -> QWidget:
        widgets = build_exclusions_panel_ui(
            content_parent=self.content,
            tr_fn=self._tr,
            get_theme_tokens_fn=get_theme_tokens,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            strong_body_label_cls=StrongBodyLabel,
            line_edit_cls=LineEdit,
            primary_push_button_cls=PrimaryPushButton,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            action_button_cls=ActionButton,
            plain_text_edit_cls=ScrollBlockingPlainTextEdit,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            set_tooltip_fn=set_tooltip,
            qta_module=qta,
            on_excl_add=self._excl_add,
            on_excl_defaults=self._excl_add_missing_defaults,
            on_excl_open_file=self._excl_open_file,
            on_excl_open_final=self._excl_open_final_file,
            on_excl_clear_all=self._excl_clear_all,
            on_excl_text_changed=self._excl_on_text_changed,
            on_ipru_add=self._ipru_add,
            on_ipru_open_file=self._ipru_open_file,
            on_ipru_open_final=self._ipru_open_final_file,
            on_ipru_clear_all=self._ipru_clear_all,
            on_ipru_text_changed=self._ipru_on_text_changed,
        )
        self._excl_add_card = widgets.excl_add_card
        self._excl_input = widgets.excl_input
        self._excl_add_btn = widgets.excl_add_btn
        self._excl_actions_group = widgets.excl_actions_group
        self._excl_actions_bar = widgets.excl_actions_bar
        self._excl_defaults_action_card = widgets.excl_defaults_action_card
        self._excl_open_action_card = widgets.excl_open_action_card
        self._excl_open_final_action_card = widgets.excl_open_final_action_card
        self._excl_clear_action_card = widgets.excl_clear_action_card
        self._excl_editor_card = widgets.excl_editor_card
        self._excl_editor = widgets.excl_editor
        self._excl_hint_label = widgets.excl_hint_label
        self._excl_status = widgets.excl_status
        self._ipru_title_label = widgets.ipru_title_label
        self._ipru_desc_label = widgets.ipru_desc_label
        self._ipru_add_card = widgets.ipru_add_card
        self._ipru_input = widgets.ipru_input
        self._ipru_add_btn = widgets.ipru_add_btn
        self._ipru_actions_group = widgets.ipru_actions_group
        self._ipru_actions_bar = widgets.ipru_actions_bar
        self._ipru_open_action_card = widgets.ipru_open_action_card
        self._ipru_open_final_action_card = widgets.ipru_open_final_action_card
        self._ipru_clear_action_card = widgets.ipru_clear_action_card
        self._ipru_editor_card = widgets.ipru_editor_card
        self._ipru_editor = widgets.ipru_editor
        self._ipru_hint_label = widgets.ipru_hint_label
        self._ipru_error_label = widgets.ipru_error_label
        self._ipru_status = widgets.ipru_status
        self._excl_actions_card = None
        self._ipru_actions_card = None

        self._apply_editor_styles()
        return widgets.panel
    def _load_exclusions(self):
        if self._cleanup_in_progress:
            return
        try:
            state = HostlistPageController.load_custom_netrogat_text()
            self._excl_base_set_cache = state.base_set
            load_text_into_editor(self._excl_editor, state.text)
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
        if self._cleanup_in_progress:
            return
        try:
            state = HostlistPageController.load_custom_ipru_text()
            self._ipru_base_set_cache = state.base_set

            load_text_into_editor(self._ipru_editor, state.text)
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
        if self._cleanup_in_progress:
            return
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
                apply_normalized_text(
                    self._excl_editor,
                    state.normalized_text,
                    current_text=text,
                )
        except Exception as e:
            log(f"Ошибка сохранения netrogat: {e}", "ERROR")

    def _excl_update_status(self):
        if not hasattr(self, "_excl_status") or not hasattr(self, "_excl_editor"):
            return
        update_exclusions_status(
            self._excl_status,
            self._excl_editor,
            build_plan_fn=HostlistPageController.build_custom_netrogat_status_plan,
            tr_fn=self._tr,
        )

    def _excl_add(self):
        raw = self._excl_input.text().strip() if hasattr(self._excl_input, "text") else ""
        if not raw:
            return
        current = self._excl_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_netrogat_plan(raw_text=raw, current_text=current)
        apply_add_plan(
            plan=plan,
            input_widget=self._excl_input,
            editor_widget=self._excl_editor,
            info_bar=InfoBar,
            window=self.window(),
            tr_fn=self._tr,
        )

    def _excl_open_file(self):
        self._excl_save()
        result = HostlistPageController.open_netrogat_user_file_action()
        self._apply_hostlist_action_result(result)

    def _excl_open_final_file(self):
        self._excl_save()
        result = HostlistPageController.open_netrogat_final_file_action()
        self._apply_hostlist_action_result(result)

    def _excl_clear_all(self):
        clear_editor_with_confirm(
            editor=self._excl_editor,
            message_box_cls=MessageBox,
            window=self.window(),
            title=self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
            body=self._tr("page.hostlist.exclusions.dialog.clear.body", "Удалить все домены?"),
        )

    def _excl_add_missing_defaults(self):
        self._excl_save()
        result = HostlistPageController.add_missing_netrogat_defaults_action()
        self._apply_hostlist_action_result(result)

    def _ipru_on_text_changed(self):
        self._ipru_save_timer.start(500)
        self._ipru_status_timer.start(120)

    def _ipru_auto_save(self):
        if self._cleanup_in_progress:
            return
        self._ipru_save()
        if hasattr(self, "_ipru_status"):
            self._ipru_status.setText(
                self._ipru_status.text() + self._tr("page.hostlist.status.saved_suffix", " • ✅ Сохранено")
            )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True

        for category in ("hostlist", "ipset"):
            self._folder_info_request_seq[category] += 1
            self._folder_info_loading[category] = False

        for timer in (
            self._domains_save_timer,
            self._ips_save_timer,
            self._ips_status_timer,
            self._excl_save_timer,
            self._ipru_save_timer,
            self._ipru_status_timer,
        ):
            try:
                timer.stop()
            except Exception:
                pass

    def _ipru_save(self):
        try:
            text = self._ipru_editor.toPlainText()
            state = HostlistPageController.save_custom_ipru_text(text)
            apply_normalized_text(
                self._ipru_editor,
                state.normalized_text,
                current_text=text,
            )
            self._ipru_update_status()
            log(f"Сохранено {state.saved_count} строк в ipset-ru.user.txt", "SUCCESS")
        except Exception as e:
            log(f"Ошибка сохранения ipset-ru.user.txt: {e}", "ERROR")

    def _ipru_update_status(self):
        if not hasattr(self, "_ipru_status") or not hasattr(self, "_ipru_editor"):
            return
        update_ipru_status(
            self._ipru_status,
            getattr(self, "_ipru_error_label", None),
            self._ipru_editor,
            build_plan_fn=HostlistPageController.build_custom_ipru_status_plan,
            tr_fn=self._tr,
        )

    def _ipru_add(self):
        raw = self._ipru_input.text().strip() if hasattr(self._ipru_input, "text") else ""
        if not raw:
            return

        current = self._ipru_editor.toPlainText()
        plan = HostlistPageController.build_add_custom_ipru_plan(raw_text=raw, current_text=current)
        apply_add_plan(
            plan=plan,
            input_widget=self._ipru_input,
            editor_widget=self._ipru_editor,
            info_bar=InfoBar,
            window=self.window(),
            tr_fn=self._tr,
        )

    def _ipru_open_file(self):
        self._ipru_save()
        result = HostlistPageController.open_ipset_ru_user_file_action()
        self._apply_hostlist_action_result(result)

    def _ipru_open_final_file(self):
        self._ipru_save()
        result = HostlistPageController.open_ipset_ru_final_file_action()
        self._apply_hostlist_action_result(result)

    def _ipru_clear_all(self):
        clear_editor_with_confirm(
            editor=self._ipru_editor,
            message_box_cls=MessageBox,
            window=self.window(),
            title=self._tr("page.hostlist.dialog.clear.title", "Очистить всё"),
            body=self._tr("page.hostlist.exclusions.ipru.dialog.clear.body", "Удалить все IP-исключения?"),
        )

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

        self._refresh_folder_info_labels()
        self._domains_update_status()
        self._ips_update_status()
        self._excl_update_status()
        self._ipru_update_status()
