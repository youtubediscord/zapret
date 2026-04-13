# hosts/ui/page.py
"""Страница управления Hosts файлом - разблокировка сервисов"""

from string import Template
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (
    QWidget, QLabel,
    QPushButton, QLayout, QCheckBox
)

from hosts.page_controller import HostsPageController
from ui.pages.base_page import BasePage
from hosts.ui.sections_build import (
    build_hosts_adobe_section,
    build_hosts_browser_warning,
    build_hosts_info_note,
    build_hosts_status_section,
)
from hosts.ui.services_build import (
    build_hosts_service_row,
    build_hosts_services_container,
    build_hosts_services_group,
    build_hosts_services_section_title,
)
from hosts.ui.selection_workflow import (
    apply_bulk_profile_selection_ui,
    apply_direct_toggle_ui,
    apply_profile_selection_ui,
)
from hosts.ui.catalog_workflow import (
    ensure_catalog_watcher,
    reconcile_catalog_after_hidden_refresh,
    refresh_catalog_if_needed,
    rebuild_services_runtime_state,
)
from hosts.ui.access_workflow import (
    check_hosts_access,
    dismiss_hosts_error_bar,
    restore_hosts_permissions_flow,
    show_hosts_access_error,
)
from hosts.ui.operation_workflow import (
    complete_hosts_operation,
    reset_all_service_profiles_ui,
    start_hosts_operation,
)
from hosts.ui.page_lifecycle_helpers import (
    activate_hosts_page,
    apply_hosts_page_language,
    apply_hosts_page_theme,
    cleanup_hosts_page,
    close_service_combo_popups,
    install_host_window_event_filter,
    run_hosts_runtime_init_once,
)
from ui.text_catalog import tr as tr_catalog

from log.log import log

from ui.theme import get_theme_tokens, get_themed_qta_icon
from ui.theme_semantic import get_semantic_palette

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        PushButton, ComboBox, InfoBar, MessageBox, SwitchButton,
    )
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False
    BodyLabel = QLabel  # type: ignore[misc,assignment]
    CaptionLabel = QLabel  # type: ignore[misc,assignment]
    StrongBodyLabel = QLabel  # type: ignore[misc,assignment]
    PushButton = QPushButton  # type: ignore[misc,assignment]
    ComboBox = None  # type: ignore[misc,assignment]
    InfoBar = None  # type: ignore[misc,assignment]
    MessageBox = None  # type: ignore[misc,assignment]
    SwitchButton = None  # type: ignore[misc,assignment]

try:
    # Simple Win11 toggle without text (QCheckBox-based).
    from ui.widgets.win11_controls import Win11ToggleSwitch as Win11ToggleSwitchNoText
except Exception:
    Win11ToggleSwitchNoText = QCheckBox  # type: ignore[misc,assignment]


_FLUENT_CHIP_STYLE_TEMPLATE = Template(
    """
QPushButton {
    background-color: transparent;
    border: none;
    color: $fg_muted;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    text-decoration: none;
}
QPushButton:hover {
    color: $accent_hex;
    text-decoration: underline;
}
QPushButton:pressed {
    color: rgba($accent_rgb, 0.85);
}
QPushButton:disabled {
    color: $fg_faint;
}
"""
)


def _get_fluent_chip_style(tokens=None) -> str:
    tokens = tokens or get_theme_tokens()
    return _FLUENT_CHIP_STYLE_TEMPLATE.substitute(
        fg_muted=tokens.fg_muted,
        fg_faint=tokens.fg_faint,
        accent_hex=tokens.accent_hex,
        accent_rgb=tokens.accent_rgb_str,
    )

def _is_fluent_combo(obj) -> bool:
    """Проверяет, является ли объект qfluentwidgets ComboBox."""
    if ComboBox is not None and isinstance(obj, ComboBox):
        return True
    return False


class HostsPage(BasePage):
    """Страница управления Hosts файлом"""

    def __init__(self, parent=None):
        super().__init__(
            "Hosts",
            "Управление разблокировкой сервисов через hosts файл",
            parent,
            title_key="page.hosts.title",
            subtitle_key="page.hosts.subtitle",
        )

        self.hosts_manager = None
        self.service_combos = {}
        self.service_icon_labels = {}
        self.service_icon_names = {}
        self.service_name_labels = {}
        self.service_icon_base_colors = {}
        self._services_section_title_labels = []
        self._service_group_title_labels = []
        self._service_group_chips_scrolls = []
        self._service_group_chip_buttons = []
        self._open_hosts_button = None
        self._info_text_label = None
        self._browser_warning_label = None
        self._adobe_desc_label = None
        self._adobe_title_label = None
        self._hosts_error_bar = None  # Текущий InfoBar ошибки доступа к hosts

        self._services_container = None
        self._services_layout = None
        self._catalog_sig = None
        self._catalog_dirty = False
        self._catalog_watch_timer = None
        self._host_window = None
        self._app_parent = parent
        self._worker = None
        self._thread = None
        self._applying = False
        self._cleanup_in_progress = False
        self._runtime_cache = HostsPageController.create_runtime_cache()
        self._last_error = None  # Последняя ошибка
        self._current_operation = None
        self._startup_initialized = False
        self._runtime_initialized = False
        self._service_dns_selection = HostsPageController.load_user_selection()
        self._ipv6_infobar_shown = False

        self._build_ui()
        self._apply_page_theme(force=True)
        self._start_catalog_watcher()
        self._run_runtime_init_once()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        """Applies theme tokens to widgets that still use raw setStyleSheet."""
        _ = force
        apply_hosts_page_theme(
            services_section_title_labels=self._services_section_title_labels,
            service_group_chips_scrolls=self._service_group_chips_scrolls,
            service_group_chip_buttons=self._service_group_chip_buttons,
            get_fluent_chip_style_fn=_get_fluent_chip_style,
            update_ui_fn=self._update_ui,
            get_theme_tokens_fn=lambda: tokens or get_theme_tokens(),
        )

    def on_page_activated(self) -> None:
        activate_hosts_page(
            install_host_window_event_filter_fn=self._install_host_window_event_filter,
            build_activation_plan_fn=HostsPageController.build_activation_plan,
            catalog_dirty=self._catalog_dirty,
            reconcile_hidden_refresh_fn=self._reconcile_catalog_after_hidden_refresh,
            invalidate_cache_fn=self._invalidate_cache,
            update_ui_fn=self._update_ui,
        )

    def _run_runtime_init_once(self) -> None:
        run_hosts_runtime_init_once(
            runtime_initialized=self._runtime_initialized,
            set_runtime_initialized_fn=lambda value: setattr(self, "_runtime_initialized", value),
            install_host_window_event_filter_fn=self._install_host_window_event_filter,
            ensure_ipv6_catalog_sections_fn=self._ensure_ipv6_catalog_sections,
            build_page_init_plan_fn=HostsPageController.build_page_init_plan,
            has_hosts_manager=self.hosts_manager is not None,
            init_hosts_manager_fn=self._init_hosts_manager,
            check_access_fn=self._check_hosts_access,
            rebuild_services_fn=self._rebuild_services_selectors,
            mark_startup_initialized_fn=lambda: setattr(self, "_startup_initialized", True),
            invalidate_cache_fn=self._invalidate_cache,
            update_ui_fn=self._update_ui,
        )

    def on_page_hidden(self) -> None:
        self._close_service_combo_popups()

    def _install_host_window_event_filter(self) -> None:
        install_host_window_event_filter(
            page=self,
            current_host_window=self._host_window,
            set_host_window_fn=lambda value: setattr(self, "_host_window", value),
        )

    def _close_service_combo_popups(self) -> None:
        """Close all service profile dropdown popups if they are open."""
        close_service_combo_popups(self.service_combos)

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        try:
            if obj is self._host_window and event is not None:
                et = event.type()
                if et in (
                    QEvent.Type.Hide,
                    QEvent.Type.Close,
                    QEvent.Type.WindowDeactivate,
                    QEvent.Type.WindowStateChange,
                ):
                    self._close_service_combo_popups()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_hosts_page_language(
            tr_fn=self._tr,
            clear_btn=getattr(self, "clear_btn", None),
            open_hosts_button=self._open_hosts_button,
            info_text_label=self._info_text_label,
            browser_warning_label=self._browser_warning_label,
            adobe_desc_label=self._adobe_desc_label,
            adobe_title_label=self._adobe_title_label,
            startup_initialized=self._startup_initialized,
            applying=self._applying,
            rebuild_services_selectors_fn=self._rebuild_services_selectors,
            check_hosts_access_fn=self._check_hosts_access,
            update_ui_fn=self._update_ui,
        )

    def _init_hosts_manager(self):
        if self.hosts_manager is not None:
            return

        self.hosts_manager = HostsPageController.resolve_hosts_manager(
            getattr(self, "parent_app", None),
            self._app_parent,
        )

    def _invalidate_cache(self):
        """Сбрасывает кеш активных доменов"""
        self._runtime_cache.invalidate()

    def _get_hosts_runtime_state(self):
        return self._runtime_cache.get_runtime_state(self.hosts_manager)

    def _get_hosts_path_str(self) -> str:
        return HostsPageController.get_hosts_path_str()

    def _sync_selections_from_hosts(self) -> None:
        """
        Делает UI «источником истины» = реальный hosts.
        Сбрасывает combo/конфиг к тому, что реально присутствует в hosts сейчас.
        """
        if not self.hosts_manager:
            return

        active_domains_map = HostsPageController.read_active_domains_map(self.hosts_manager)
        sync_plan = HostsPageController.build_selection_sync_plan(
            service_names=list(self.service_combos.keys()),
            active_domains_map=active_domains_map,
        )

        was_building = getattr(self, "_building_services_ui", False)
        self._building_services_ui = True
        try:
            for service_name, combo in list(self.service_combos.items()):
                entry = sync_plan.entries.get(service_name)
                if entry is None:
                    continue

                if entry.direct_only:
                    if isinstance(combo, QCheckBox):
                        combo.setEnabled(entry.toggle_enabled)
                        combo.setChecked(entry.toggle_checked)
                        self._update_profile_row_visual(service_name)
                        continue
                    inferred = entry.selected_profile
                else:
                    inferred = entry.selected_profile

                if inferred:
                    if _is_fluent_combo(combo):
                        idx = combo.findData(inferred)
                        if idx >= 0:
                            combo.blockSignals(True)
                            combo.setCurrentIndex(idx)
                            combo.blockSignals(False)
                        else:
                            combo.blockSignals(True)
                            combo.setCurrentIndex(0)
                            combo.blockSignals(False)
                else:
                    if _is_fluent_combo(combo):
                        combo.blockSignals(True)
                        combo.setCurrentIndex(0)
                        combo.blockSignals(False)
                    elif isinstance(combo, QCheckBox):
                        combo.setChecked(False)

                self._update_profile_row_visual(service_name)
        finally:
            self._building_services_ui = was_building

        self._service_dns_selection = dict(sync_plan.new_selection)
        HostsPageController.save_user_selection(self._service_dns_selection)

    def _get_active_domains(self) -> set:
        """Возвращает активные домены с кешированием (чтобы не читать hosts 28 раз)"""
        state = self._get_hosts_runtime_state()
        if state.error_message:
            self._show_error(
                self._tr("page.hosts.error.read_hosts", "Ошибка чтения hosts: {error}", error=state.error_message)
            )
            return set()

        if not state.accessible:
            hosts_path = self._get_hosts_path_str()
            self._show_error(
                self._tr(
                    "page.hosts.error.no_access.long",
                    "Нет доступа для изменения файла hosts.\nЕсли файл редактируется вручную, возможно защитник/антивирус блокирует запись.\nПуть: {path}",
                    path=hosts_path,
                )
            )
        else:
            self._hide_error()

        return self._runtime_cache.get_active_domains(self.hosts_manager)

    def _build_ui(self):
        # Информационная заметка
        self._build_info_note()
        self.add_spacing(4)

        # Предупреждение о браузере
        self._build_browser_warning()
        self.add_spacing(6)

        # Статус
        self._build_status_section()
        self.add_spacing(6)

        # Сервисы (выбор DNS-профиля по каждому сервису)
        self._build_services_container()
        self.add_spacing(6)

        # Adobe
        self._build_adobe_section()
        self.add_spacing(6)


    def _build_services_container(self) -> None:
        widgets = build_hosts_services_container()
        self._services_container = widgets.container
        self._services_layout = widgets.layout
        self.add_widget(self._services_container)

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if not item:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _start_catalog_watcher(self) -> None:
        self._catalog_watch_timer = ensure_catalog_watcher(
            page=self,
            timer=self._catalog_watch_timer,
            interval_ms=5000,
            refresh_callback=self._refresh_catalog_if_needed,
        )

    def _reconcile_catalog_after_hidden_refresh(self) -> None:
        handled = reconcile_catalog_after_hidden_refresh(
            catalog_dirty=self._catalog_dirty,
            services_layout_exists=self._services_layout is not None,
            rebuild_services_selectors=self._rebuild_services_selectors,
            invalidate_cache=self._invalidate_cache,
        )
        if handled:
            self._catalog_dirty = False

    def _ensure_ipv6_catalog_sections(self) -> tuple[bool, bool]:
        """Добавляет managed IPv6 секции в hosts.ini при доступном IPv6."""
        try:
            changed, ipv6_available = HostsPageController.ensure_ipv6_catalog_sections()
            if changed:
                log("Hosts: обнаружен IPv6, каталог hosts.ini дополнен IPv6 секциями", "INFO")
                if InfoBar is not None and not self._ipv6_infobar_shown:
                    self._ipv6_infobar_shown = True
                    InfoBar.success(
                        title=self._tr("page.hosts.ipv6.infobar.title", "IPv6"),
                        content=self._tr(
                            "page.hosts.ipv6.infobar.content",
                            "У провайдера обнаружен IPv6. В hosts.ini добавлены IPv6 разделы DNS-провайдеров.",
                        ),
                        parent=self.window(),
                    )
            return (bool(changed), bool(ipv6_available))
        except Exception as e:
            log(f"Hosts: ошибка проверки IPv6 для hosts.ini: {e}", "DEBUG")
            return (False, False)

    def _refresh_catalog_if_needed(self, trigger: str) -> None:
        result = refresh_catalog_if_needed(
            current_signature=self._catalog_sig,
            trigger=trigger,
            services_layout_exists=self._services_layout is not None,
            page_visible=self.isVisible(),
            invalidate_catalog_cache=HostsPageController.invalidate_catalog_cache,
            rebuild_services_selectors=self._rebuild_services_selectors,
            log_info=lambda message: log(message, "INFO"),
        )
        if not result["changed"]:
            return
        self._catalog_dirty = bool(result["catalog_dirty"])
        self._catalog_sig = result["catalog_sig"]

    def _services_add_section_title(self, text: str) -> None:
        if self._services_layout is None:
            return
        label = build_hosts_services_section_title(text=text)
        self._services_section_title_labels.append(label)
        self._services_layout.addWidget(label)

    def _services_add_widget(self, widget: QWidget) -> None:
        if self._services_layout is None:
            return
        self._services_layout.addWidget(widget)

    def _reset_services_runtime_bindings(self) -> None:
        self.service_combos = {}
        self.service_icon_labels = {}
        self.service_icon_names = {}
        self.service_name_labels = {}
        self.service_icon_base_colors = {}
        self._services_section_title_labels = []
        self._service_group_title_labels = []
        self._service_group_chips_scrolls = []
        self._service_group_chip_buttons = []

    def _rebuild_services_selectors(self) -> None:
        if self._services_layout is None:
            return
        self._catalog_sig = rebuild_services_runtime_state(
            clear_layout=lambda: (self._clear_layout(self._services_layout), self._reset_services_runtime_bindings()),
            build_services_selectors=self._build_services_selectors,
        )

    def _show_error(self, message: str):
        """Показывает InfoBar с ошибкой доступа и кнопкой восстановления прав."""
        self._hosts_error_bar, self._last_error = show_hosts_access_error(
            current_bar=self._hosts_error_bar,
            last_error=self._last_error,
            message=message,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            push_button_cls=PushButton,
            window=self.window(),
            on_restore=self._restore_hosts_permissions,
            log_warning=lambda text: log(text, "WARNING"),
            log_debug=lambda text: log(text, "DEBUG"),
        )

    def _dismiss_hosts_error_bar(self):
        """Закрывает текущий InfoBar ошибки доступа к hosts."""
        self._last_error = None
        dismiss_hosts_error_bar(self._hosts_error_bar)
        self._hosts_error_bar = None

    def _hide_error(self):
        """Скрывает ошибку доступа к hosts."""
        self._dismiss_hosts_error_bar()

    def _restore_hosts_permissions(self, bar=None, btn=None):
        """Восстанавливает стандартные права доступа к файлу hosts."""
        _ = btn
        if bar is not None:
            dismiss_hosts_error_bar(bar)
        self._hosts_error_bar = None
        self._last_error = None
        restore_hosts_permissions_flow(
            info_bar_cls=InfoBar,
            window=self.window(),
            dismiss_error_bar=self._dismiss_hosts_error_bar,
            invalidate_cache=self._invalidate_cache,
            update_ui=self._update_ui,
            sync_selections_from_hosts=self._sync_selections_from_hosts,
            show_error=self._show_error,
            log_error=lambda text: log(text, "ERROR"),
        )

    def _check_hosts_access(self):
        """Проверяет доступ к hosts файлу при загрузке страницы"""
        check_hosts_access(
            runtime_state=self._get_hosts_runtime_state(),
            hosts_path=self._get_hosts_path_str(),
            tr_fn=self._tr,
            hide_error=self._hide_error,
            show_error=self._show_error,
        )

    def _build_info_note(self):
        """Информационная заметка о том, зачем нужен hosts"""
        widgets = build_hosts_info_note(tr_fn=self._tr)
        self._info_text_label = widgets.info_text_label
        self.add_widget(widgets.card)

    def _build_browser_warning(self):
        """Предупреждение о необходимости перезапуска браузера"""
        self._browser_warning_label = build_hosts_browser_warning(tr_fn=self._tr)
        self.add_widget(self._browser_warning_label)

    def _build_status_section(self):
        active = self._get_active_domains()
        widgets = build_hosts_status_section(
            tr_fn=self._tr,
            active_count=len(active),
            on_clear_clicked=self._on_clear_clicked,
            on_open_hosts_file=self._open_hosts_file,
        )
        self.status_dot = widgets.status_dot
        self.status_label = widgets.status_label
        self.clear_btn = widgets.clear_button
        self._open_hosts_button = widgets.open_hosts_button
        self.add_widget(widgets.card)

    def _make_fluent_chip(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet(_get_fluent_chip_style())
        return btn

    def _get_building_services_ui(self) -> bool:
        return bool(getattr(self, "_building_services_ui", False))

    def _set_building_services_ui(self, value: bool) -> None:
        self._building_services_ui = bool(value)

    def _bulk_apply_dns_profile(self, service_names: list[str], profile_name: str | None) -> None:
        if self._applying:
            return

        plan = HostsPageController.build_bulk_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_names=service_names,
            profile_name=profile_name,
        )

        new_selection = apply_bulk_profile_selection_ui(
            plan=plan,
            profile_name=profile_name,
            service_names=service_names,
            service_combos=self.service_combos,
            is_fluent_combo=_is_fluent_combo,
            checkbox_cls=QCheckBox,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
            apply_current_selection=self._apply_current_selection,
            log_debug=lambda message: log(message, "DEBUG"),
        )
        if new_selection is not None:
            self._service_dns_selection = new_selection

    def _build_services_selectors(self):
        OFF_LABEL = self._tr("page.hosts.services.off", "Откл.")
        active_domains_map = HostsPageController.read_active_domains_map(self.hosts_manager)
        catalog_plan = HostsPageController.build_services_catalog_plan(
            current_selection=self._service_dns_selection,
            active_domains_map=active_domains_map,
            direct_title=self._tr("page.hosts.group.direct", "Напрямую из hosts"),
            ai_title=self._tr("page.hosts.group.ai", "ИИ"),
            other_title=self._tr("page.hosts.group.other", "Остальные"),
        )

        self._services_add_section_title(
            tr_catalog("page.hosts.section.services", language=self._ui_language, default="Сервисы")
        )

        self._building_services_ui = True
        try:
            for group_plan in catalog_plan.groups:
                group_widgets = build_hosts_services_group(
                    group_plan,
                    off_label=OFF_LABEL,
                    strong_body_label_cls=StrongBodyLabel,
                    make_chip=self._make_fluent_chip,
                    on_bulk_apply=self._bulk_apply_dns_profile,
                )
                card = group_widgets.card
                self._service_group_title_labels.append(group_widgets.title_label)
                if group_widgets.chips_scroll is not None:
                    self._service_group_chips_scrolls.append(group_widgets.chips_scroll)
                self._service_group_chip_buttons.extend(group_widgets.chip_buttons)

                for row_plan in group_plan.rows:
                    row_widgets = build_hosts_service_row(
                        row_plan,
                        body_label_cls=BodyLabel,
                        combo_cls=ComboBox,
                        has_fluent=_HAS_FLUENT,
                        toggle_cls=Win11ToggleSwitchNoText,
                        off_label=OFF_LABEL,
                        on_direct_toggle=self._on_direct_toggle_changed,
                        on_profile_changed=self._on_profile_changed,
                    )
                    self.service_name_labels[row_plan.service_name] = row_widgets.name_label
                    card.add_layout(row_widgets.row_layout)
                    self.service_combos[row_plan.service_name] = row_widgets.control
                    self.service_icon_labels[row_plan.service_name] = row_widgets.icon_label
                    self.service_icon_names[row_plan.service_name] = row_plan.icon_name
                    self.service_icon_base_colors[row_plan.service_name] = row_plan.icon_color

                    self._update_profile_row_visual(row_plan.service_name)

                self._services_add_widget(card)
        finally:
            self._building_services_ui = False

        self._service_dns_selection = dict(catalog_plan.new_selection)
        if catalog_plan.selection_migrated:
            HostsPageController.save_user_selection(self._service_dns_selection)

    def _on_direct_toggle_changed(self, service_name: str, checked: bool) -> None:
        if getattr(self, "_building_services_ui", False):
            self._update_profile_row_visual(service_name)
            return
        if self._applying:
            self._update_profile_row_visual(service_name)
            return

        plan = HostsPageController.build_direct_toggle_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            checked=checked,
        )
        self._service_dns_selection, _ = apply_direct_toggle_ui(
            plan=plan,
            service_name=service_name,
            service_combos=self.service_combos,
            checkbox_cls=QCheckBox,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
            apply_current_selection=self._apply_current_selection,
        )

    def _build_adobe_section(self):
        self.add_section_title(text_key="page.hosts.section.additional")
        is_adobe_active = self.hosts_manager.is_adobe_domains_active() if self.hosts_manager else False
        widgets = build_hosts_adobe_section(
            tr_fn=self._tr,
            adobe_active=is_adobe_active,
            on_toggle_adobe=self._toggle_adobe,
            switch_button_cls=SwitchButton,
            fallback_checkbox_cls=QCheckBox,
        )
        self._adobe_desc_label = widgets.description_label
        self._adobe_title_label = widgets.title_label
        self.adobe_switch = widgets.switch
        self.add_widget(widgets.card)

    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТЧИКИ
    # ═══════════════════════════════════════════════════════════════

    def _on_profile_changed(self, service_name: str, selected_profile: object):
        if getattr(self, "_building_services_ui", False):
            self._update_profile_row_visual(service_name)
            return
        if self._applying:
            self._update_profile_row_visual(service_name)
            return

        plan = HostsPageController.build_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            selected_profile=selected_profile,
        )
        self._service_dns_selection, _ = apply_profile_selection_ui(
            plan=plan,
            service_name=service_name,
            update_profile_visual=self._update_profile_row_visual,
            apply_current_selection=self._apply_current_selection,
        )

    def _update_profile_row_visual(self, service_name: str):
        combo = self.service_combos.get(service_name)
        icon_label = self.service_icon_labels.get(service_name)
        tokens = get_theme_tokens()
        base_color = self.service_icon_base_colors.get(service_name)
        if not base_color:
            base_color = tokens.accent_hex
        if not combo or not icon_label:
            return

        enabled = False
        if _is_fluent_combo(combo):
            enabled = combo.currentData() is not None
        elif isinstance(combo, QCheckBox):
            enabled = bool(combo.isChecked())
        color = base_color if enabled else tokens.fg_faint
        icon_name = self.service_icon_names.get(service_name)
        try:
            icon = get_themed_qta_icon(icon_name or "fa5s.globe", color=color)
        except Exception:
            icon = get_themed_qta_icon("fa5s.globe", color=color)
        icon_label.setPixmap(icon.pixmap(18, 18))

    def _apply_current_selection(self):
        if self._applying:
            return
        self._run_operation('apply_selection', dict(self._service_dns_selection))

    def _on_clear_clicked(self):
        if self._applying:
            return
        if MessageBox is not None:
            box = MessageBox(
                self._tr("page.hosts.dialog.clear.title", "Очистить hosts?"),
                self._tr(
                    "page.hosts.dialog.clear.body",
                    "Это полностью сбросит файл hosts к стандартному содержимому Windows и удалит ВСЕ записи, включая добавленные вручную.",
                ),
                self.window(),
            )
            if not box.exec():
                return
        self._clear_hosts()

    def _clear_hosts(self):
        """Очищает hosts"""
        if self._applying:
            return

        self._run_operation('clear_all')

    def _open_hosts_file(self):
        result = HostsPageController.open_hosts_file()
        if result.success:
            return
        if InfoBar:
            InfoBar.warning(
                title=self._tr("page.hosts.open.error.title", "Ошибка"),
                content=self._tr("page.hosts.open.error.content", "Не удалось открыть: {error}", error=result.message),
                parent=self.window(),
            )

    def _toggle_adobe(self, checked: bool):
        if self._applying:
            # Revert the switch without re-triggering the signal
            self.adobe_switch.blockSignals(True)
            self.adobe_switch.setChecked(not checked)
            self.adobe_switch.blockSignals(False)
            return
        self._run_operation('adobe_add' if checked else 'adobe_remove')

    def _run_operation(self, operation: str, payload=None):
        self._cleanup_in_progress = False
        runtime = start_hosts_operation(
            hosts_manager=self.hosts_manager,
            applying=self._applying,
            operation=operation,
            payload=payload,
            on_operation_complete=self._on_operation_complete,
            on_thread_finished=self._on_hosts_thread_finished,
            parent=self,
        )
        if runtime is None:
            return
        self._applying = runtime["applying"]
        self._current_operation = runtime["current_operation"]
        self._worker = runtime["worker"]
        self._thread = runtime["thread"]

    def _on_hosts_thread_finished(self) -> None:
        self._worker = None
        self._thread = None

    def _on_operation_complete(self, success: bool, message: str):
        if self._cleanup_in_progress:
            return
        self._worker = None
        self._thread = None
        state = complete_hosts_operation(
            current_operation=self._current_operation,
            success=success,
            message=message,
            hosts_path=self._get_hosts_path_str(),
            invalidate_cache=self._invalidate_cache,
            update_ui=self._update_ui,
            sync_selections_from_hosts=self._sync_selections_from_hosts,
            reset_profiles_ui=self._reset_all_service_profiles,
            hide_error=self._hide_error,
            show_error=self._show_error,
        )
        self._current_operation = state["current_operation"]
        self._applying = state["applying"]

    def _reset_all_service_profiles(self) -> None:
        """Сбрасывает выбор профилей в UI и user_hosts.ini (после очистки hosts)."""
        self._service_dns_selection = reset_all_service_profiles_ui(
            service_combos=self.service_combos,
            is_fluent_combo=_is_fluent_combo,
            checkbox_cls=QCheckBox,
            get_building_state=self._get_building_services_ui,
            set_building_state=self._set_building_services_ui,
            update_profile_visual=self._update_profile_row_visual,
        )

    def _update_ui(self):
        """Обновляет весь UI"""
        runtime_state = self._get_hosts_runtime_state()
        status_display = HostsPageController.build_status_display_plan(
            runtime_state,
            active_text=self._tr("page.hosts.status.active_domains", "Активно {count} доменов", count=len(runtime_state.active_domains)),
            none_text=self._tr("page.hosts.status.none_active", "Нет активных"),
        )
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()

        # Статус
        if status_display.dot_active:
            self.status_dot.setStyleSheet(f"color: {semantic.success}; font-size: 12px;")
        else:
            self.status_dot.setStyleSheet(f"color: {tokens.fg_faint}; font-size: 12px;")
        self.status_label.setText(status_display.label_text)

        # Обновляем иконки под текущие выборы
        for name in list(self.service_combos.keys()):
            self._update_profile_row_visual(name)

        # Adobe
        is_adobe = status_display.adobe_active
        self.adobe_switch.blockSignals(True)
        self.adobe_switch.setChecked(is_adobe)
        self.adobe_switch.blockSignals(False)

    def refresh(self):
        """Обновляет страницу (сбрасывает кеш и перечитывает hosts)"""
        self._invalidate_cache()
        self._update_ui()

    def cleanup(self):
        """Очистка потоков при закрытии"""
        try:
            cleanup_hosts_page(
                set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
                current_host_window=self._host_window,
                set_host_window_fn=lambda value: setattr(self, "_host_window", value),
                page=self,
                catalog_watch_timer=self._catalog_watch_timer,
                set_catalog_watch_timer_fn=lambda value: setattr(self, "_catalog_watch_timer", value),
                thread=self._thread,
                worker=self._worker,
                set_worker_fn=lambda value: setattr(self, "_worker", value),
                set_thread_fn=lambda value: setattr(self, "_thread", value),
                log_fn=log,
            )
        except Exception as e:
            log(f"Ошибка при очистке hosts_page: {e}", "DEBUG")
