# ui/pages/hosts_page.py
"""Страница управления Hosts файлом - разблокировка сервисов"""

import os
from string import Template
from PyQt6.QtCore import Qt, QThread, QTimer, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QLayout, QCheckBox
)
import qtawesome as qta

from hosts.page_controller import HostsPageController
from .base_page import BasePage
from ui.compat_widgets import SettingsCard
from ui.text_catalog import tr as tr_catalog

from log import log
from ui.theme import get_theme_tokens
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

# Импортируем сервисы и домены
try:
    from hosts.proxy_domains import (
        ensure_ipv6_catalog_sections_if_available,
    )
except ImportError:
    def ensure_ipv6_catalog_sections_if_available() -> tuple[bool, bool]:
        return (False, False)

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

        self._controller = HostsPageController()
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
        self._catalog_watch_timer = None
        self._main_window = None
        self._app_parent = parent
        self._worker = None
        self._thread = None
        self._applying = False
        self._active_domains_cache = None  # Кеш активных доменов
        self._runtime_state_cache = None
        self._last_error = None  # Последняя ошибка
        self._current_operation = None
        self._startup_initialized = False
        self._service_dns_selection = self._controller.load_user_selection()
        self._ipv6_infobar_shown = False

        from qfluentwidgets import qconfig
        qconfig.themeChanged.connect(lambda _: self._apply_theme())
        qconfig.themeColorChanged.connect(lambda _: self._apply_theme())

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._apply_theme()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _apply_theme(self) -> None:
        """Applies theme tokens to widgets that still use raw setStyleSheet."""
        tokens = get_theme_tokens()

        # Section title labels (plain QLabel kept for layout/padding control).
        for label in list(self._services_section_title_labels):
            try:
                label.setStyleSheet(
                    f"color: {tokens.fg_muted}; font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;"
                )
            except Exception:
                pass

        # Chip scroll areas (plain QScrollArea, no Fluent equivalent).
        chips_qss = (
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea QWidget { background: transparent; }"
            "QScrollBar:horizontal { height: 4px; background: transparent; margin: 0px; }"
            f"QScrollBar::handle:horizontal {{ background: {tokens.scrollbar_handle}; border-radius: 2px; min-width: 24px; }}"
            f"QScrollBar::handle:horizontal:hover {{ background: {tokens.scrollbar_handle_hover}; }}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; background: transparent; border: none; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
        )
        for scroll in list(self._service_group_chips_scrolls):
            try:
                scroll.setStyleSheet(chips_qss)
            except Exception:
                pass

        # Chip buttons (plain QPushButton link-style, no direct Fluent equivalent).
        chip_qss = _get_fluent_chip_style(tokens)
        for btn in list(self._service_group_chip_buttons):
            try:
                btn.setStyleSheet(chip_qss)
            except Exception:
                pass


        try:
            self._update_ui()
        except Exception:
            pass

    def showEvent(self, event):  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self._install_main_window_event_filter()
        # Не запускаем тяжёлые операции при системном восстановлении окна (из трея/свёрнутого).
        if event.spontaneous():
            return

        ipv6_catalog_changed, _ = self._ensure_ipv6_catalog_sections()
        show_plan = self._controller.build_show_event_plan(
            startup_initialized=self._startup_initialized,
            has_hosts_manager=self.hosts_manager is not None,
            ipv6_catalog_changed=ipv6_catalog_changed,
        )

        # Лениво инициализируем тяжёлые части страницы только при первом открытии вкладки.
        if show_plan.init_hosts_manager:
            self._init_hosts_manager()
        if show_plan.check_access:
            self._check_hosts_access()
        if show_plan.rebuild_services:
            self._rebuild_services_selectors()
        if show_plan.mark_initialized:
            self._startup_initialized = True

        if show_plan.start_watcher:
            self._start_catalog_watcher()
        for trigger in show_plan.refresh_triggers:
            self._refresh_catalog_if_needed(trigger=trigger)

        # После инициализации/пересборки селекторов обновляем статус по реальному hosts.
        if show_plan.invalidate_cache:
            self._invalidate_cache()
        if show_plan.update_ui:
            self._update_ui()

    def hideEvent(self, event):  # noqa: N802 (Qt naming)
        self._close_service_combo_popups()
        self._stop_catalog_watcher()
        super().hideEvent(event)

    def _install_main_window_event_filter(self) -> None:
        try:
            w = self.window()
        except Exception:
            w = None
        if not w or w is self._main_window:
            return

        if self._main_window is not None:
            try:
                self._main_window.removeEventFilter(self)
            except Exception:
                pass

        self._main_window = w
        try:
            w.installEventFilter(self)
        except Exception:
            pass

    def _close_service_combo_popups(self) -> None:
        """Close all service profile dropdown popups if they are open."""
        for control in list(self.service_combos.values()):
            if control is None:
                continue
            try:
                if hasattr(control, "_closeComboMenu"):
                    control._closeComboMenu()
                elif hasattr(control, "hidePopup"):
                    control.hidePopup()
            except Exception:
                pass

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        try:
            if obj is self._main_window and event is not None:
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

        if hasattr(self, "clear_btn") and self.clear_btn is not None:
            self.clear_btn.setText(self._tr("page.hosts.button.clear", " Очистить"))

        if self._open_hosts_button is not None:
            self._open_hosts_button.setText(self._tr("page.hosts.button.open", " Открыть"))

        if self._info_text_label is not None:
            self._info_text_label.setText(
                self._tr(
                    "page.hosts.info.note",
                    "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — это не блокировка РКН. Решается не через Zapret, а через проксирование: домены направляются через отдельный прокси-сервер в файле hosts.",
                )
            )

        if self._browser_warning_label is not None:
            self._browser_warning_label.setText(
                self._tr(
                    "page.hosts.warning.browser_restart",
                    "После добавления или удаления доменов необходимо перезапустить браузер, чтобы изменения вступили в силу.",
                )
            )

        if self._adobe_desc_label is not None:
            self._adobe_desc_label.setText(
                self._tr(
                    "page.hosts.adobe.description",
                    "⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.",
                )
            )
        if self._adobe_title_label is not None:
            self._adobe_title_label.setText(self._tr("page.hosts.adobe.title", "Блокировка Adobe"))

        if self._startup_initialized and not self._applying:
            self._rebuild_services_selectors()
            self._check_hosts_access()

        self._update_ui()

    def _init_hosts_manager(self):
        if self.hosts_manager is not None:
            return

        self.hosts_manager = self._controller.resolve_hosts_manager(
            getattr(self, "parent_app", None),
            self._app_parent,
        )

    def _invalidate_cache(self):
        """Сбрасывает кеш активных доменов"""
        self._active_domains_cache = None
        self._runtime_state_cache = None

    def _get_hosts_runtime_state(self):
        if self._runtime_state_cache is not None:
            return self._runtime_state_cache

        state = self._controller.read_runtime_state(self.hosts_manager)
        self._runtime_state_cache = state
        return state

    def _get_hosts_path_str(self) -> str:
        return self._controller.get_hosts_path_str()

    def _sync_selections_from_hosts(self) -> None:
        """
        Делает UI «источником истины» = реальный hosts.
        Сбрасывает combo/конфиг к тому, что реально присутствует в hosts сейчас.
        """
        if not self.hosts_manager:
            return

        active_domains_map = self._controller.read_active_domains_map(self.hosts_manager)
        sync_plan = self._controller.build_selection_sync_plan(
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
        self._controller.save_user_selection(self._service_dns_selection)

    def _get_active_domains(self) -> set:
        """Возвращает активные домены с кешированием (чтобы не читать hosts 28 раз)"""
        if self._active_domains_cache is not None:
            return self._active_domains_cache
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

        self._active_domains_cache = set(state.active_domains)
        return self._active_domains_cache
        return set()

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
        self._services_container = QWidget()
        self._services_layout = QVBoxLayout(self._services_container)
        self._services_layout.setContentsMargins(0, 0, 0, 0)
        self._services_layout.setSpacing(16)
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
        if self._catalog_watch_timer is None:
            self._catalog_watch_timer = QTimer(self)
            self._catalog_watch_timer.setInterval(5000)
            self._catalog_watch_timer.timeout.connect(lambda: self._refresh_catalog_if_needed(trigger="watcher"))
        if not self._catalog_watch_timer.isActive():
            self._catalog_watch_timer.start()

    def _ensure_ipv6_catalog_sections(self) -> tuple[bool, bool]:
        """Добавляет managed IPv6 секции в hosts.ini при доступном IPv6."""
        try:
            changed, ipv6_available = self._controller.ensure_ipv6_catalog_sections()
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

    def _stop_catalog_watcher(self) -> None:
        if self._catalog_watch_timer is not None and self._catalog_watch_timer.isActive():
            self._catalog_watch_timer.stop()

    def _refresh_catalog_if_needed(self, trigger: str) -> None:
        sig = self._controller.get_catalog_signature()
        refresh_plan = self._controller.build_catalog_refresh_plan(
            current_signature=self._catalog_sig,
            new_signature=sig,
            trigger=trigger,
            services_layout_exists=self._services_layout is not None,
        )

        if not refresh_plan.changed:
            return

        if refresh_plan.invalidate_cache:
            self._controller.invalidate_catalog_cache()

        if not refresh_plan.should_rebuild:
            self._catalog_sig = refresh_plan.new_signature
            return

        if refresh_plan.should_log:
            log(refresh_plan.log_message, "INFO")

        self._rebuild_services_selectors()
        self._catalog_sig = refresh_plan.new_signature

    def _services_add_section_title(self, text: str) -> None:
        if self._services_layout is None:
            return
        label = QLabel(text)
        self._services_section_title_labels.append(label)
        tokens = get_theme_tokens()
        label.setStyleSheet(
            f"color: {tokens.fg_muted}; font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;"
        )
        self._services_layout.addWidget(label)

    def _services_add_widget(self, widget: QWidget) -> None:
        if self._services_layout is None:
            return
        self._services_layout.addWidget(widget)

    def _rebuild_services_selectors(self) -> None:
        if self._services_layout is None:
            return
        self._clear_layout(self._services_layout)
        self.service_combos = {}
        self.service_icon_labels = {}
        self.service_icon_names = {}
        self.service_name_labels = {}
        self.service_icon_base_colors = {}
        self._services_section_title_labels = []
        self._service_group_title_labels = []
        self._service_group_chips_scrolls = []
        self._service_group_chip_buttons = []
        self._build_services_selectors()
        self._catalog_sig = self._controller.get_catalog_signature()

    def _show_error(self, message: str):
        """Показывает InfoBar с ошибкой доступа и кнопкой восстановления прав."""
        if self._last_error == message:
            return  # Не дублируем одну и ту же ошибку
        self._dismiss_hosts_error_bar()
        self._last_error = message

        if not InfoBar:
            log(f"hosts access error (no InfoBar): {message}", "WARNING")
            return

        try:
            from qfluentwidgets import InfoBarPosition
            error_plan = self._controller.build_error_bar_plan(
                message=message,
                title=self._tr("page.hosts.error.title", "Нет доступа к hosts"),
                action_text=self._tr("page.hosts.button.restore_access", "Восстановить права доступа"),
                action_pending_text=self._tr("page.hosts.button.restoring_access", "Восстановление..."),
            )

            bar = InfoBar.error(
                title=error_plan.title,
                content=error_plan.content,
                orient=Qt.Orientation.Vertical,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=-1,  # Не исчезает автоматически
                parent=self.window(),
            )

            # Кнопка "Восстановить права"
            restore_btn = PushButton(error_plan.action_text)
            restore_btn.setFixedWidth(220)

            def _on_restore():
                restore_btn.setEnabled(False)
                restore_btn.setText(error_plan.action_pending_text)
                self._restore_hosts_permissions(bar, restore_btn)

            restore_btn.clicked.connect(_on_restore)
            bar.addWidget(restore_btn)
            self._hosts_error_bar = bar
        except Exception as e:
            log(f"Ошибка показа InfoBar: {e}", "DEBUG")

    def _dismiss_hosts_error_bar(self):
        """Закрывает текущий InfoBar ошибки доступа к hosts."""
        self._last_error = None
        if self._hosts_error_bar is not None:
            try:
                self._hosts_error_bar.close()
            except Exception:
                pass
            self._hosts_error_bar = None

    def _hide_error(self):
        """Скрывает ошибку доступа к hosts."""
        self._dismiss_hosts_error_bar()

    def _restore_hosts_permissions(self, bar=None, btn=None):
        """Восстанавливает стандартные права доступа к файлу hosts."""
        try:
            result = self._controller.restore_hosts_permissions()
            success = result.success
            message = result.message
            restore_plan = self._controller.build_restore_permissions_plan(
                success=success,
                message=message,
            )

            if success:
                self._dismiss_hosts_error_bar()
                self._invalidate_cache()
                self._update_ui()
                self._sync_selections_from_hosts()
                if InfoBar and restore_plan.message_plan is not None:
                    from qfluentwidgets import InfoBarPosition
                    InfoBar.success(
                        title=restore_plan.message_plan.title,
                        content=restore_plan.message_plan.content,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self.window(),
                    )
            else:
                if bar is not None:
                    try:
                        bar.close()
                    except Exception:
                        pass
                self._hosts_error_bar = None
                self._last_error = None
                self._show_error(restore_plan.error_message)
        except Exception as e:
            log(f"Ошибка при восстановлении прав: {e}", "ERROR")
            if bar is not None:
                try:
                    bar.close()
                except Exception:
                    pass
            self._hosts_error_bar = None
            self._last_error = None
            self._show_error(str(e))

    def _check_hosts_access(self):
        """Проверяет доступ к hosts файлу при загрузке страницы"""
        state = self._get_hosts_runtime_state()
        access_plan = self._controller.build_access_plan(
            state,
            hosts_path=self._get_hosts_path_str(),
            read_error_message=self._tr("page.hosts.error.read_hosts", "Ошибка чтения hosts: {error}", error=state.error_message),
            no_access_message=self._tr(
                "page.hosts.error.no_access.short",
                "Нет доступа для изменения файла hosts. Скорее всего защитник/антивирус заблокировал запись.\nПуть: {path}",
                path="{path}",
            ),
        )
        if not access_plan.show_error:
            self._hide_error()
            return
        self._show_error(access_plan.error_message)

    def _build_info_note(self):
        """Информационная заметка о том, зачем нужен hosts"""
        semantic = get_semantic_palette()
        info_card = SettingsCard()

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)

        # Иконка лампочки (QLabel с pixmap — оставляем)
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.lightbulb', color=semantic.warning).pixmap(20, 20))
        icon_label.setFixedSize(24, 24)
        info_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Текст пояснения
        self._info_text_label = CaptionLabel(
            self._tr(
                "page.hosts.info.note",
                "Некоторые сервисы (ChatGPT, Spotify и др.) сами блокируют доступ из России — это не блокировка РКН. Решается не через Zapret, а через проксирование: домены направляются через отдельный прокси-сервер в файле hosts.",
            )
        )
        self._info_text_label.setWordWrap(True)
        info_layout.addWidget(self._info_text_label, 1)

        info_card.add_layout(info_layout)
        self.add_widget(info_card)

    def _build_browser_warning(self):
        """Предупреждение о необходимости перезапуска браузера"""
        semantic = get_semantic_palette()
        warning_layout = QHBoxLayout()
        warning_layout.setContentsMargins(12, 4, 12, 4)
        warning_layout.setSpacing(10)

        # Иконка предупреждения (QLabel с pixmap — оставляем)
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.sync-alt', color=semantic.warning).pixmap(16, 16))
        warning_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Текст предупреждения
        self._browser_warning_label = CaptionLabel(
            self._tr(
                "page.hosts.warning.browser_restart",
                "После добавления или удаления доменов необходимо перезапустить браузер, чтобы изменения вступили в силу.",
            )
        )
        self._browser_warning_label.setWordWrap(True)
        self._browser_warning_label.setStyleSheet(
            f"color: {semantic.warning_soft}; font-size: 11px; background: transparent;"
        )
        warning_layout.addWidget(self._browser_warning_label, 1)

        # Простой контейнер без фона
        warning_widget = QWidget()
        warning_widget.setLayout(warning_layout)
        warning_widget.setStyleSheet("background: transparent;")

        self.add_widget(warning_widget)

    def _build_status_section(self):
        status_card = SettingsCard()
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)

        active = self._get_active_domains()
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()

        # status_dot — цветной символ «●», оставляем plain QLabel для управления цветом
        self.status_dot = QLabel("●")
        dot_color = semantic.success if active else tokens.fg_faint
        self.status_dot.setStyleSheet(f"color: {dot_color}; font-size: 12px;")
        status_layout.addWidget(self.status_dot)

        self.status_label = BodyLabel(
            self._tr("page.hosts.status.active_domains", "Активно {count} доменов", count=len(active))
            if active
            else self._tr("page.hosts.status.none_active", "Нет активных")
        )
        self.status_label.setProperty("tone", "primary")
        status_layout.addWidget(self.status_label, 1)

        self.clear_btn = PushButton()
        self.clear_btn.setIcon(qta.icon('fa5s.trash-alt', color=tokens.fg_muted))
        self.clear_btn.setText(self._tr("page.hosts.button.clear", " Очистить"))
        self.clear_btn.setFixedHeight(32)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        status_layout.addWidget(self.clear_btn)

        self._open_hosts_button = PushButton()
        self._open_hosts_button.setIcon(qta.icon('fa5s.external-link-alt', color=tokens.fg))
        self._open_hosts_button.setText(self._tr("page.hosts.button.open", " Открыть"))
        self._open_hosts_button.setFixedHeight(32)
        self._open_hosts_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_hosts_button.clicked.connect(self._open_hosts_file)
        status_layout.addWidget(self._open_hosts_button)

        status_card.add_layout(status_layout)
        self.add_widget(status_card)

    def _make_fluent_chip(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet(_get_fluent_chip_style())
        return btn

    def _bulk_apply_dns_profile(self, service_names: list[str], profile_name: str | None) -> None:
        if self._applying:
            return

        plan = self._controller.build_bulk_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_names=service_names,
            profile_name=profile_name,
        )

        if not plan.changed:
            if plan.skipped_services:
                log(
                    "Hosts: профиль недоступен для: "
                    + ", ".join(plan.skipped_services[:8])
                    + ("…" if len(plan.skipped_services) > 8 else ""),
                    "DEBUG",
                )
            return

        target_profile = (profile_name or "").strip()
        for service_name in service_names:
            control = self.service_combos.get(service_name)
            if not control:
                continue

            if _is_fluent_combo(control):
                target_idx = control.findData(target_profile) if target_profile else 0
                if target_idx >= 0 and control.currentIndex() != target_idx:
                    control.blockSignals(True)
                    control.setCurrentIndex(target_idx)
                    control.blockSignals(False)
            elif isinstance(control, QCheckBox):
                desired = bool(target_profile)
                if control.isChecked() != desired:
                    was_building = getattr(self, "_building_services_ui", False)
                    self._building_services_ui = True
                    try:
                        control.setChecked(desired)
                    finally:
                        self._building_services_ui = was_building

            self._update_profile_row_visual(service_name)

        self._service_dns_selection = dict(plan.new_selection)
        self._apply_current_selection()

    def _build_services_selectors(self):
        OFF_LABEL = self._tr("page.hosts.services.off", "Откл.")
        active_domains_map = self._controller.read_active_domains_map(self.hosts_manager)
        catalog_plan = self._controller.build_services_catalog_plan(
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
                card = SettingsCard()

                header = QHBoxLayout()
                header.setContentsMargins(0, 0, 0, 0)
                header.setSpacing(10)

                title_label = StrongBodyLabel(group_plan.title)
                self._service_group_title_labels.append(title_label)
                header.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

                if not group_plan.direct_only:
                    chips = QWidget()
                    chips_layout = QHBoxLayout(chips)
                    chips_layout.setContentsMargins(0, 0, 0, 0)
                    chips_layout.setSpacing(4)
                    chips_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
                    chips_layout.addStretch(1)

                    off_btn = self._make_fluent_chip(OFF_LABEL)
                    self._service_group_chip_buttons.append(off_btn)
                    off_btn.clicked.connect(
                        lambda _checked=False, n=tuple(group_plan.service_names): self._bulk_apply_dns_profile(list(n), None)
                    )
                    chips_layout.addWidget(off_btn)

                    for profile_name, label in group_plan.common_profiles:
                        if not label:
                            continue
                        btn = self._make_fluent_chip(label)
                        self._service_group_chip_buttons.append(btn)
                        btn.clicked.connect(
                            lambda _checked=False, n=tuple(group_plan.service_names), p=profile_name: self._bulk_apply_dns_profile(list(n), p)
                        )
                        chips_layout.addWidget(btn)

                    chips_scroll = QScrollArea()
                    chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
                    chips_scroll.setWidgetResizable(True)
                    chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                    chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    chips_scroll.setFixedHeight(30)
                    self._service_group_chips_scrolls.append(chips_scroll)
                    tokens = get_theme_tokens()
                    chips_scroll.setStyleSheet(
                        (
                            "QScrollArea { background: transparent; border: none; }"
                            "QScrollArea QWidget { background: transparent; }"
                            "QScrollBar:horizontal { height: 4px; background: transparent; margin: 0px; }"
                            f"QScrollBar::handle:horizontal {{ background: {tokens.scrollbar_handle}; border-radius: 2px; min-width: 24px; }}"
                            f"QScrollBar::handle:horizontal:hover {{ background: {tokens.scrollbar_handle_hover}; }}"
                            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; background: transparent; border: none; }"
                            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
                        )
                    )
                    chips_scroll.setWidget(chips)

                    header.addWidget(chips_scroll, 1, Qt.AlignmentFlag.AlignVCenter)
                else:
                    header.addStretch(1)

                card.add_layout(header)

                for row_plan in group_plan.rows:
                    row = QHBoxLayout()
                    row.setContentsMargins(0, 0, 0, 0)
                    row.setSpacing(10)

                    # Иконка сервиса (QLabel с pixmap — оставляем)
                    icon_label = QLabel()
                    icon_label.setFixedSize(20, 20)
                    row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

                    name_label = BodyLabel(row_plan.service_name)
                    self.service_name_labels[row_plan.service_name] = name_label
                    row.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)

                    if row_plan.direct_only:
                        toggle = Win11ToggleSwitchNoText()
                        toggle.setEnabled(row_plan.toggle_enabled)
                        toggle.setChecked(row_plan.toggle_checked)

                        toggle.toggled.connect(
                            lambda checked, s=row_plan.service_name: self._on_direct_toggle_changed(s, checked)
                        )

                        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
                        card.add_layout(row)
                        self.service_combos[row_plan.service_name] = toggle
                    else:
                        if _HAS_FLUENT and ComboBox is not None:
                            combo = ComboBox()
                        else:
                            from PyQt6.QtWidgets import QComboBox as _QComboBox
                            combo = _QComboBox()
                        combo.setFixedHeight(32)
                        combo.setCursor(Qt.CursorShape.PointingHandCursor)
                        combo.setMinimumWidth(220)
                        combo.addItem(OFF_LABEL, userData=None)
                        for profile_name, label in row_plan.profile_items:
                            combo.addItem(label, userData=profile_name)

                        if row_plan.selected_profile:
                            inferred_idx = combo.findData(row_plan.selected_profile)
                            if inferred_idx >= 0:
                                combo.setCurrentIndex(inferred_idx)
                            else:
                                combo.setCurrentIndex(0)
                        else:
                            combo.setCurrentIndex(0)

                        combo.currentIndexChanged.connect(
                            lambda _idx, s=row_plan.service_name, c=combo: self._on_profile_changed(s, c.currentData())
                        )
                        row.addWidget(combo, 0, Qt.AlignmentFlag.AlignVCenter)

                        card.add_layout(row)
                        self.service_combos[row_plan.service_name] = combo
                    self.service_icon_labels[row_plan.service_name] = icon_label
                    self.service_icon_names[row_plan.service_name] = row_plan.icon_name
                    self.service_icon_base_colors[row_plan.service_name] = row_plan.icon_color

                    self._update_profile_row_visual(row_plan.service_name)

                self._services_add_widget(card)
        finally:
            self._building_services_ui = False

        self._service_dns_selection = dict(catalog_plan.new_selection)
        if catalog_plan.selection_migrated:
            self._controller.save_user_selection(self._service_dns_selection)

    def _on_direct_toggle_changed(self, service_name: str, checked: bool) -> None:
        if getattr(self, "_building_services_ui", False):
            self._update_profile_row_visual(service_name)
            return
        if self._applying:
            self._update_profile_row_visual(service_name)
            return

        plan = self._controller.build_direct_toggle_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            checked=checked,
        )
        self._service_dns_selection = dict(plan.new_selection)

        if plan.force_checked is not None or plan.force_enabled is not None:
            control = self.service_combos.get(service_name)
            if isinstance(control, QCheckBox):
                was_building = getattr(self, "_building_services_ui", False)
                self._building_services_ui = True
                try:
                    if plan.force_checked is not None:
                        control.setChecked(plan.force_checked)
                    if plan.force_enabled is not None:
                        control.setEnabled(plan.force_enabled)
                finally:
                    self._building_services_ui = was_building
            return

        self._update_profile_row_visual(service_name)
        if plan.apply_now:
            self._apply_current_selection()

    def _build_adobe_section(self):
        self.add_section_title(text_key="page.hosts.section.additional")

        adobe_card = SettingsCard()

        self._adobe_desc_label = CaptionLabel(
            self._tr(
                "page.hosts.adobe.description",
                "⚠️ Блокирует серверы проверки активации Adobe. Включите, если у вас установлена пиратская версия.",
            )
        )
        self._adobe_desc_label.setWordWrap(True)
        adobe_card.add_widget(self._adobe_desc_label)

        adobe_layout = QHBoxLayout()
        adobe_layout.setContentsMargins(0, 0, 0, 0)
        adobe_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.puzzle-piece', color='#ff0000').pixmap(20, 20))
        adobe_layout.addWidget(icon_label)

        self._adobe_title_label = StrongBodyLabel(self._tr("page.hosts.adobe.title", "Блокировка Adobe"))
        adobe_layout.addWidget(self._adobe_title_label, 1)

        is_adobe_active = self.hosts_manager.is_adobe_domains_active() if self.hosts_manager else False

        if SwitchButton is not None:
            self.adobe_switch = SwitchButton()
            self.adobe_switch.setChecked(is_adobe_active)
            self.adobe_switch.checkedChanged.connect(self._toggle_adobe)
        else:
            from PyQt6.QtWidgets import QCheckBox
            self.adobe_switch = QCheckBox()
            self.adobe_switch.setChecked(is_adobe_active)
            self.adobe_switch.toggled.connect(self._toggle_adobe)
        adobe_layout.addWidget(self.adobe_switch)

        adobe_card.add_layout(adobe_layout)
        self.add_widget(adobe_card)

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

        plan = self._controller.build_profile_selection_plan(
            current_selection=self._service_dns_selection,
            service_name=service_name,
            selected_profile=selected_profile,
        )
        self._service_dns_selection = dict(plan.new_selection)

        self._update_profile_row_visual(service_name)
        if plan.apply_now:
            self._apply_current_selection()

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
            icon = qta.icon(icon_name or "fa5s.globe", color=color)
        except Exception:
            icon = qta.icon("fa5s.globe", color=color)
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
        result = self._controller.open_hosts_file()
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
        if not self.hosts_manager or self._applying:
            return

        self._applying = True
        self._current_operation = operation

        self._worker = self._controller.create_operation_worker(self.hosts_manager, operation, payload)
        self._thread = QThread()

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_operation_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_operation_complete(self, success: bool, message: str):
        operation = self._current_operation
        self._current_operation = None
        self._applying = False
        completion_plan = self._controller.build_operation_completion_plan(
            operation=operation,
            success=success,
            message=message,
            hosts_path=self._get_hosts_path_str(),
        )

        # Сбрасываем кеш и обновляем UI
        self._invalidate_cache()
        self._update_ui()
        self._sync_selections_from_hosts()

        if completion_plan.reset_profiles:
            self._reset_all_service_profiles()

        if completion_plan.clear_error:
            self._hide_error()
        else:
            self._show_error(completion_plan.error_message)

    def _reset_all_service_profiles(self) -> None:
        """Сбрасывает выбор профилей в UI и user_hosts.ini (после очистки hosts)."""
        reset_plan = self._controller.build_reset_selection_plan()
        self._service_dns_selection = dict(reset_plan.new_selection)
        self._controller.save_user_selection(self._service_dns_selection)

        was_building = getattr(self, "_building_services_ui", False)
        self._building_services_ui = True
        try:
            for control in self.service_combos.values():
                if _is_fluent_combo(control):
                    control.blockSignals(True)
                    control.setCurrentIndex(0)
                    control.blockSignals(False)
                elif isinstance(control, QCheckBox):
                    control.setChecked(False)
        finally:
            self._building_services_ui = was_building

        for service_name in list(self.service_combos.keys()):
            self._update_profile_row_visual(service_name)

    def _update_ui(self):
        """Обновляет весь UI"""
        runtime_state = self._get_hosts_runtime_state()
        status_display = self._controller.build_status_display_plan(
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
        from log import log
        try:
            if self._main_window is not None:
                try:
                    self._main_window.removeEventFilter(self)
                except Exception:
                    pass
                self._main_window = None

            if self._thread and self._thread.isRunning():
                log("Останавливаем hosts worker...", "DEBUG")
                self._thread.quit()
                if not self._thread.wait(2000):
                    log("⚠ Hosts worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self._thread.terminate()
                        self._thread.wait(500)
                    except:
                        pass
        except Exception as e:
            log(f"Ошибка при очистке hosts_page: {e}", "DEBUG")
