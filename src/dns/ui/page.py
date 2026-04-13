# dns/ui/page.py
"""Страница сетевых настроек - DNS, hosts, proxy"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame,
    QLineEdit, QCheckBox, QProgressBar, QPushButton,
)

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        CheckBox, IndeterminateProgressBar, LineEdit, InfoBar, MessageBox,
        SettingCardGroup,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    CheckBox = QCheckBox
    IndeterminateProgressBar = QProgressBar
    LineEdit = QLineEdit
    InfoBar = None
    MessageBox = None  # type: ignore[assignment]
    SettingCardGroup = None
    _HAS_FLUENT_LABELS = False

from ui.pages.base_page import BasePage
from ui.widgets.win11_controls import Win11ToggleRow
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    QuickActionsBar,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log.log import log

from dns.dns_providers import DNS_PROVIDERS
from dns.network_page_controller import NetworkPageController
from dns.ui.adapters import build_adapter_cards, refresh_adapter_cards
from dns.ui.cards import DNSProviderCard, AdapterCard
from dns.ui.dns_build import build_auto_dns_ui, build_custom_dns_ui
from dns.ui.page_build import build_network_page_shell
from dns.ui.providers_build import build_provider_cards
from dns.ui.tools_build import build_tools_card_ui
from dns.ui.force_dns_ui import (
    highlight_force_dns_card,
    set_force_dns_toggle,
    update_dns_selection_block_state,
    update_force_dns_status_label,
)
from dns.ui.force_dns_build import build_force_dns_card_ui
from dns.ui.page_force_dns_workflow import (
    apply_force_dns_status_state,
    flush_dns_cache_action,
    handle_force_dns_toggled_action,
    reset_dns_to_dhcp_action,
)
from dns.ui.isp_warning import (
    build_isp_warning_ui,
    hide_isp_warning_widget,
    insert_isp_warning_widget,
    render_isp_warning_styles,
)
from dns.ui.page_diagnostics_warning_workflow import (
    accept_isp_dns_recommendation,
    apply_connectivity_test_result,
    cleanup_network_page,
    dismiss_isp_dns_warning,
    render_isp_warning_theme,
    show_isp_dns_warning,
    start_connectivity_test,
)
from dns.ui.load_workflow import (
    apply_loaded_page_state,
    handle_loaded_adapters,
    handle_loaded_dns_info,
    run_network_runtime_init,
    start_background_loading,
)
from dns.ui.page_runtime_helpers import (
    build_dynamic_network_ui,
    clear_dns_selection_ui,
    sync_selected_dns_card_ui,
)
from dns.ui.selection import (
    apply_dns_selection_plan_ui,
    clear_dns_selection,
    select_auto_dns_ui,
    select_custom_dns_ui,
    select_provider_dns_ui,
    set_dns_card_selected,
)

try:
    import qtawesome as qta
except ImportError:
    qta = None  # type: ignore[assignment]

class NetworkPage(BasePage):
    """Страница сетевых настроек с интегрированным DNS"""

    adapters_loaded = pyqtSignal(list)
    dns_info_loaded = pyqtSignal(dict)
    test_completed = pyqtSignal(list)  # Результаты теста соединения
    
    def __init__(self, parent=None):
        super().__init__(
            "Сеть",
            "Настройки DNS и доступа к сервисам",
            parent,
            title_key="page.network.title",
            subtitle_key="page.network.subtitle",
        )
        
        self._adapters = []
        self._dns_info = {}
        self._is_loading = True
        self._ui_built = False
        self._selected_provider = None
        self._force_dns_active = False
        self._ipv6_available = False
        self._test_in_progress = False
        self._force_dns_status_enabled = False
        self._force_dns_status_details_key: str | None = None
        self._force_dns_status_details_kwargs: dict = {}
        self._force_dns_status_details_fallback = ""
        self._runtime_initialized = False
        self._cleanup_in_progress = False
        
        self.dns_cards = {}
        self.adapter_cards = []
        self._dns_category_labels: list[QLabel] = []
        self._isp_warning = None
        self._isp_warning_title = None
        self._isp_warning_content = None
        self._isp_warning_icon = None
        self._isp_warning_accept_btn = None
        self._isp_warning_dismiss_btn = None
        self._auto_icon_label = None
        self._force_dns_reset_row = None
        self._tools_card = None
        self._tools_actions_bar = None
        self._tools_section_label = None
        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _confirm_action(
        self,
        title_key: str,
        title_default: str,
        confirm_key: str,
        confirm_default: str,
    ) -> bool:
        if MessageBox is None:
            return True
        try:
            box = MessageBox(
                self._tr(title_key, title_default),
                self._tr(confirm_key, confirm_default),
                self.window(),
            )
            return bool(box.exec())
        except Exception:
            return True

    def _update_test_action_text(self) -> None:
        text = (
            self._tr("page.network.button.test.in_progress", "Проверка...")
            if self._test_in_progress
            else self._tr("page.network.button.test", "Тест соединения")
        )
        try:
            if getattr(self, "test_btn", None) is not None:
                self.test_btn.setText(text)
                self.test_btn.setEnabled(not self._test_in_progress)
        except Exception:
            pass

    def _run_runtime_init_once(self) -> None:
        run_network_runtime_init(
            runtime_initialized=self._runtime_initialized,
            build_page_init_plan_fn=NetworkPageController.build_page_init_plan,
            mark_initialized_fn=lambda: setattr(self, "_runtime_initialized", True),
            schedule_fn=QTimer.singleShot,
            start_loading_fn=self._start_loading,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if hasattr(self, "loading_label"):
            self.loading_label.setText(self._tr("page.network.loading", "⏳ Загрузка..."))

        if hasattr(self, "custom_label"):
            self.custom_label.setText(self._tr("page.network.custom.label", "Свой:"))
        if hasattr(self, "custom_apply_btn"):
            self.custom_apply_btn.setText(self._tr("page.network.custom.apply", "OK"))
        if hasattr(self, "ipv6_label"):
            self.ipv6_label.setText(self._tr("page.network.custom.ipv6.label", "IPv6:"))

        self._update_test_action_text()

        if hasattr(self, "dns_flush_btn"):
            self.dns_flush_btn.setText(
                self._tr("page.network.button.flush_dns_cache", "Сбросить DNS кэш")
            )
            set_tooltip(
                self.dns_flush_btn,
                self._tr(
                    "page.network.tools.flush_dns.description",
                    "Очистить локальный кэш DNS Windows, если ответы или домены застряли в старом состоянии.",
                ),
            )

        if hasattr(self, "auto_label"):
            self.auto_label.setText(self._tr("page.network.dns.auto", "Автоматически (DHCP)"))

        try:
            title_label = getattr(getattr(self, "_tools_card", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(self._tr("page.network.section.tools", "Диагностика"))
        except Exception:
            pass

        if hasattr(self, "force_dns_card"):
            try:
                self.force_dns_card.set_title(
                    self._tr(
                        "page.network.force_dns.card.title",
                        "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
                    )
                )
            except Exception:
                pass
            try:
                title_label = getattr(self.force_dns_card, "titleLabel", None)
                if title_label is not None:
                    title_label.setText(
                        self._tr(
                            "page.network.force_dns.card.title",
                            "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
                        )
                    )
            except Exception:
                pass
        if hasattr(self, "force_dns_toggle"):
            self.force_dns_toggle.set_texts(
                self._tr("page.network.force_dns.toggle.title", "Принудительный DNS"),
                self._tr(
                    "page.network.force_dns.toggle.description",
                    "Устанавливает Google DNS + OpenDNS на активные адаптеры",
                ),
            )
        if hasattr(self, "force_dns_reset_dhcp_btn"):
            self.force_dns_reset_dhcp_btn.setText(
                self._tr("page.network.force_dns.reset.button", "Сбросить DNS на DHCP")
            )
            self.force_dns_reset_dhcp_btn.setToolTip(
                self._tr(
                    "page.network.force_dns.reset.description",
                    "Отключить Force DNS и вернуть получение DNS через DHCP для всех адаптеров.",
                )
            )

        if hasattr(self, "force_dns_status_label"):
            self._update_force_dns_status(
                self._force_dns_status_enabled,
                self._force_dns_status_details_key,
                details_kwargs=self._force_dns_status_details_kwargs,
                details_fallback=self._force_dns_status_details_fallback,
            )
        self._apply_inline_theme_styles()
        
    def _build_ui(self):
        """Строит интерфейс страницы"""
        # ═══════════════════════════════════════════════════════════════
        # ПРИНУДИТЕЛЬНЫЙ DNS
        # ═══════════════════════════════════════════════════════════════
        self._build_force_dns_card()
        
        self.add_spacing(12)
        
        # ═══════════════════════════════════════════════════════════════
        # DNS СЕРВЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.network.section.dns_servers")

        shell = build_network_page_shell(
            parent=self,
            content_parent=self.content,
            tr_fn=self._tr,
            add_section_title_fn=self.add_section_title,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            body_label_cls=BodyLabel if _HAS_FLUENT_LABELS else QLabel,
            qlabel_cls=QLabel,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            line_edit_cls=LineEdit,
            action_button_cls=ActionButton,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            setting_card_group_cls=SettingCardGroup,
            quick_actions_bar_cls=QuickActionsBar,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            build_custom_dns_ui_fn=build_custom_dns_ui,
            build_tools_card_ui_fn=build_tools_card_ui,
            on_apply_custom_dns=self._apply_custom_dns_quick,
            on_test_connection=self._test_connection,
            on_flush_dns_cache=self._confirm_flush_dns_cache,
            set_tooltip_fn=set_tooltip,
            dns_provider_card_cls=DNSProviderCard,
            show_ipv6=self._ipv6_available,
        )
        self.loading_card = shell.loading_card
        self.loading_label = shell.loading_label
        self.loading_bar = shell.loading_bar
        self.dns_cards_container = shell.dns_cards_container
        self.dns_cards_layout = shell.dns_cards_layout
        self.custom_card = shell.custom_card
        self.custom_indicator = shell.custom_indicator
        self.custom_label = shell.custom_label
        self.custom_primary = shell.custom_primary
        self.custom_secondary = shell.custom_secondary
        self.custom_apply_btn = shell.custom_apply_btn
        
        # IPv6 поля (если доступны)
        if shell.ipv6_label is not None:
            self.ipv6_label = shell.ipv6_label
        if shell.custom_primary_v6 is not None:
            self.custom_primary_v6 = shell.custom_primary_v6
        if shell.custom_secondary_v6 is not None:
            self.custom_secondary_v6 = shell.custom_secondary_v6
            
        self.adapters_container = shell.adapters_container
        self.adapters_layout = shell.adapters_layout
        self._tools_section_label = shell.tools_section_label
        self._tools_card = shell.tools_card
        self._tools_actions_bar = shell.tools_actions_bar
        self.test_btn = shell.test_btn
        self.dns_flush_btn = shell.dns_flush_btn

        self.add_widget(self.loading_card)
        self.add_widget(self.dns_cards_container)
        self.add_spacing(6)
        self.add_widget(self.custom_card)

        # ═══════════════════════════════════════════════════════════════
        # СЕТЕВЫЕ АДАПТЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.network.section.adapters")
        self.add_widget(self.adapters_container)

        self.add_spacing(12)

        # ═══════════════════════════════════════════════════════════════
        # ДИАГНОСТИКА
        # ═══════════════════════════════════════════════════════════════
        self.add_widget(self._tools_card)
        
        # Подключаем сигналы
        self.adapters_loaded.connect(self._on_adapters_loaded)
        self.dns_info_loaded.connect(self._on_dns_info_loaded)
    
    def _start_loading(self):
        """Запускает асинхронную загрузку данных"""
        if self._cleanup_in_progress:
            return
        start_background_loading(load_data_fn=self._load_data)
    
    def _load_data(self):
        """Загружает данные в фоне"""
        if self._cleanup_in_progress:
            return
        try:
            state = NetworkPageController.load_page_data()
            if self._cleanup_in_progress:
                return
            apply_loaded_page_state(
                state=state,
                set_ipv6_available_fn=lambda value: setattr(self, "_ipv6_available", value),
                set_force_dns_active_fn=lambda value: setattr(self, "_force_dns_active", value),
                set_adapters_fn=lambda adapters: setattr(self, "_adapters", adapters),
                set_dns_info_fn=lambda dns_info: setattr(self, "_dns_info", dns_info),
                emit_adapters_loaded_fn=lambda adapters: (not self._cleanup_in_progress) and self.adapters_loaded.emit(adapters),
                emit_dns_info_loaded_fn=lambda dns_info: (not self._cleanup_in_progress) and self.dns_info_loaded.emit(dns_info),
            )
        except Exception as exc:
            log(f"Ошибка загрузки DNS данных: {exc}", "ERROR")
    
    def _on_adapters_loaded(self, adapters):
        if self._cleanup_in_progress:
            return
        handle_loaded_adapters(
            adapters=adapters,
            current_dns_info=self._dns_info,
            ui_built=self._ui_built,
            set_adapters_fn=lambda value: setattr(self, "_adapters", value),
            build_dynamic_ui_fn=self._build_dynamic_ui,
        )
    
    def _on_dns_info_loaded(self, dns_info):
        if self._cleanup_in_progress:
            return
        handle_loaded_dns_info(
            dns_info=dns_info,
            current_adapters=self._adapters,
            ui_built=self._ui_built,
            set_dns_info_fn=lambda value: setattr(self, "_dns_info", value),
            build_dynamic_ui_fn=self._build_dynamic_ui,
        )
    
    def _build_dynamic_ui(self):
        """Строит UI после загрузки данных"""
        from dns.dns_core import _normalize_alias
        result = build_dynamic_network_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            ui_built=self._ui_built,
            tr_fn=self._tr,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            settings_card_cls=SettingsCard,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            strong_body_label_cls=StrongBodyLabel if _HAS_FLUENT_LABELS else QLabel,
            caption_label_cls=CaptionLabel if _HAS_FLUENT_LABELS else QLabel,
            qlabel_cls=QLabel,
            dns_provider_card_cls=DNSProviderCard,
            adapter_card_cls=AdapterCard,
            qta_module=qta,
            get_theme_tokens_fn=get_theme_tokens,
            build_auto_dns_ui_fn=build_auto_dns_ui,
            build_provider_cards_fn=build_provider_cards,
            build_adapter_cards_fn=build_adapter_cards,
            providers=DNS_PROVIDERS,
            adapters=self._adapters,
            dns_info=self._dns_info,
            dns_cards_layout=self.dns_cards_layout,
            adapters_layout=self.adapters_layout,
            on_auto_selected=self._select_auto_dns,
            on_provider_selected=self._on_dns_selected,
            on_adapter_state_changed=self._sync_selected_dns_card,
            normalize_alias_fn=_normalize_alias,
            ipv6_available=self._ipv6_available,
            dns_cards_container=self.dns_cards_container,
            custom_card=self.custom_card,
            adapters_container=self.adapters_container,
            sync_selected_dns_card_fn=self._sync_selected_dns_card,
            check_and_show_isp_dns_warning_fn=self._check_and_show_isp_dns_warning,
            apply_inline_theme_styles_fn=self._apply_inline_theme_styles,
        )
        if result is None:
            return
        self._ui_built = True
        self._is_loading = False
        self.loading_card.hide()
        auto_widgets = result["auto_widgets"]
        self.auto_card = auto_widgets.card
        self.auto_indicator = auto_widgets.indicator
        self._auto_icon_label = auto_widgets.icon_label
        self.auto_label = auto_widgets.title_label
        provider_cards = result["provider_cards"]
        self.dns_cards.update(provider_cards.dns_cards)
        self._dns_category_labels.extend(provider_cards.category_labels)
        self.adapter_cards = result["adapter_cards"]

    def _sync_selected_dns_card(self, *_):
        self._selected_provider = sync_selected_dns_card_ui(
            adapter_cards=self.adapter_cards,
            dns_info=self._dns_info,
            providers=DNS_PROVIDERS,
            build_dns_selection_plan_fn=NetworkPageController.build_dns_selection_plan,
            get_selected_adapters_fn=self._get_selected_adapters,
            apply_dns_selection_plan_ui_fn=apply_dns_selection_plan_ui,
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            custom_primary=getattr(self, 'custom_primary', None),
            custom_secondary=getattr(self, 'custom_secondary', None),
            indicator_on_qss=DNSProviderCard.indicator_on(),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            set_card_selected_fn=self._set_dns_card_selected,
        )
    
    def _clear_selection(self):
        """Сбрасывает все выделения"""
        clear_dns_selection_ui(
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            clear_dns_selection_fn=clear_dns_selection,
            set_card_selected_fn=self._set_dns_card_selected,
        )

    def _set_dns_card_selected(self, card: QWidget | None, selected: bool) -> None:
        set_dns_card_selected(card, selected)
    
    def _on_dns_selected(self, name: str, data: dict):
        """Обработчик выбора DNS - сразу применяем"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        self._selected_provider = select_provider_dns_ui(
            name=name,
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            set_card_selected_fn=self._set_dns_card_selected,
        )
        
        # Применяем
        self._apply_provider_dns_quick(name, data)
    
    def _select_auto_dns(self):
        """Выбор автоматического DNS"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        select_auto_dns_ui(
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            indicator_on_qss=DNSProviderCard.indicator_on(),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            set_card_selected_fn=self._set_dns_card_selected,
        )
        self._selected_provider = None
        
        # Применяем
        self._apply_auto_dns_quick()
    
    def _get_selected_adapters(self) -> list:
        """Возвращает выбранные адаптеры"""
        return [card.adapter_name for card in self.adapter_cards if card.checkbox.isChecked()]
    
    def _apply_auto_dns_quick(self):
        """Быстрое применение автоматического DNS (IPv4 + IPv6)"""
        adapters = self._get_selected_adapters()
        if not adapters:
            return

        success = NetworkPageController.apply_auto_dns(adapters)
        plan = NetworkPageController.build_auto_dns_apply_result_plan(
            adapter_count=len(adapters),
            success_count=success,
        )
        if plan.log_message:
            log(plan.log_message, plan.log_level or "INFO")
        if plan.should_refresh:
            self._refresh_adapters_dns()
    
    def _apply_provider_dns_quick(self, name: str, data: dict):
        """Быстрое применение DNS провайдера"""
        adapters = self._get_selected_adapters()
        if not adapters:
            return

        provider_plan = NetworkPageController.build_provider_dns_plan(
            name=name,
            data=data,
            ipv6_available=self._ipv6_available,
        )
        if not provider_plan.valid:
            if provider_plan.log_message:
                log(provider_plan.log_message, provider_plan.log_level or "WARNING")
            return

        success = NetworkPageController.apply_provider_dns(
            adapters,
            provider_plan.ipv4,
            provider_plan.ipv6,
            ipv6_available=self._ipv6_available,
        )
        result_plan = NetworkPageController.build_provider_dns_apply_result_plan(
            name=name,
            adapter_count=len(adapters),
            success_count=success,
            ipv6_available=self._ipv6_available,
            ipv6=provider_plan.ipv6,
        )
        if result_plan.log_message:
            log(result_plan.log_message, result_plan.log_level or "INFO")
        if result_plan.should_refresh:
            self._refresh_adapters_dns()
    
    def _apply_custom_dns_quick(self):
        """Быстрое применение пользовательского DNS (IPv4 + IPv6)"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return

        from utils import IPValidator

        primary = self.custom_primary.text().strip()
        if not primary:
            return

        # Валидация IPv4
        if not IPValidator.is_valid_ipv4(primary):
            log(f"DNS: Неверный формат IPv4: {primary}", "WARNING")
            return

        secondary = self.custom_secondary.text().strip() or None
        if secondary and not IPValidator.is_valid_ipv4(secondary):
            log(f"DNS: Неверный формат IPv4 (вторичный): {secondary}", "WARNING")
            return

        # Валидация IPv6 (если поля существуют и заполнены)
        primary_v6 = None
        secondary_v6 = None
        
        if hasattr(self, 'custom_primary_v6') and self.custom_primary_v6 is not None:
            primary_v6 = self.custom_primary_v6.text().strip() or None
            if primary_v6:
                if not IPValidator.is_valid_ipv6(primary_v6):
                    log(f"DNS: Неверный формат IPv6: {primary_v6}", "WARNING")
                    return

                if hasattr(self, 'custom_secondary_v6') and self.custom_secondary_v6 is not None:
                    secondary_v6 = self.custom_secondary_v6.text().strip() or None
                    if secondary_v6 and not IPValidator.is_valid_ipv6(secondary_v6):
                        log(f"DNS: Неверный формат IPv6 (вторичный): {secondary_v6}", "WARNING")
                        return

        select_custom_dns_ui(
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            indicator_on_qss=DNSProviderCard.indicator_on(),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            set_card_selected_fn=self._set_dns_card_selected,
        )

        adapters = self._get_selected_adapters()
        if not adapters:
            return

        success = NetworkPageController.apply_custom_dns(
            adapters,
            primary,
            secondary,
            primary_v6=primary_v6,
            secondary_v6=secondary_v6,
            ipv6_available=self._ipv6_available,
        )
        plan = NetworkPageController.build_custom_dns_apply_result_plan(
            primary=primary,
            adapter_count=len(adapters),
            success_count=success,
        )
        if plan.log_message:
            log(plan.log_message, plan.log_level or "INFO")
        if plan.should_refresh:
            self._refresh_adapters_dns()
    
    def _refresh_adapters_dns(self):
        """Обновляет отображение DNS у всех адаптеров"""
        if self._cleanup_in_progress:
            return
        try:
            if not self.adapter_cards:
                log("Нет карточек адаптеров для обновления", "DEBUG")
                return

            adapter_names = [card.adapter_name for card in self.adapter_cards]
            dns_info = NetworkPageController.refresh_dns_info(adapter_names)
            self._dns_info = dns_info
            refresh_plan = refresh_adapter_cards(
                adapter_cards=self.adapter_cards,
                dns_info=dns_info,
                build_refresh_plan_fn=NetworkPageController.build_adapter_dns_refresh_plan,
            )

            self._sync_selected_dns_card()
            if refresh_plan is not None:
                log(refresh_plan.log_message, refresh_plan.log_level)
            
        except Exception as e:
            log(f"Ошибка обновления DNS адаптеров: {e}", "WARNING")
            import traceback
            log(traceback.format_exc(), "DEBUG")
    
    def _build_force_dns_card(self):
        """Строит виджет принудительного DNS в стиле DPI страницы"""
        self._force_dns_active, force_dns_widgets = build_force_dns_card_ui(
            parent=self,
            content_parent=self.content,
            add_section_title_fn=self.add_section_title,
            tr_fn=self._tr,
            add_widget_fn=self.add_widget,
            get_theme_tokens_fn=get_theme_tokens,
            get_force_dns_status_fn=NetworkPageController.get_force_dns_status,
            has_fluent_labels=_HAS_FLUENT_LABELS,
            setting_card_group_cls=SettingCardGroup,
            settings_card_cls=SettingsCard,
            caption_label_cls=CaptionLabel if _HAS_FLUENT_LABELS else QLabel,
            action_button_cls=ActionButton,
            win11_toggle_row_cls=Win11ToggleRow,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qt_namespace=Qt,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            enable_setting_card_group_auto_height_fn=enable_setting_card_group_auto_height,
            on_toggle=self._on_force_dns_toggled,
            on_confirm_reset=self._confirm_reset_dns_to_dhcp,
        )
        self.force_dns_card = force_dns_widgets.card
        self.force_dns_toggle = force_dns_widgets.toggle
        self.force_dns_status_label = force_dns_widgets.status_label
        self.force_dns_reset_dhcp_btn = force_dns_widgets.reset_button
        self._force_dns_reset_row = force_dns_widgets.reset_row

        self._update_force_dns_status(self._force_dns_active)
        self._update_dns_selection_state()

    def _apply_inline_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            if hasattr(self, "loading_label") and self.loading_label is not None and not _HAS_FLUENT_LABELS:
                self.loading_label.setStyleSheet(f"color: {theme_tokens.fg_muted}; font-size: 12px;")
        except Exception:
            pass
        try:
            if hasattr(self, "custom_label") and self.custom_label is not None and not _HAS_FLUENT_LABELS:
                self.custom_label.setStyleSheet(f"color: {theme_tokens.fg_muted}; font-size: 12px;")
        except Exception:
            pass
        try:
            if hasattr(self, "auto_label") and self.auto_label is not None and not _HAS_FLUENT_LABELS:
                self.auto_label.setStyleSheet(f"color: {theme_tokens.fg}; font-size: 12px; font-weight: 500;")
        except Exception:
            pass
        try:
            if hasattr(self, "force_dns_status_label") and self.force_dns_status_label is not None and not _HAS_FLUENT_LABELS:
                self.force_dns_status_label.setStyleSheet(f"color: {theme_tokens.fg_muted}; font-size: 11px;")
        except Exception:
            pass
        try:
            for label in list(getattr(self, "_dns_category_labels", [])):
                if label is None:
                    continue
                label.setStyleSheet(
                    f"""
                    color: {theme_tokens.fg_faint};
                    font-size: 10px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    padding: 8px 0 4px 4px;
                    """
                )
        except Exception:
            pass
        try:
            self._render_isp_warning_styles(theme_tokens)
        except Exception:
            pass
        try:
            self._refresh_static_dns_card_styles(theme_tokens)
        except Exception:
            pass

    def _refresh_static_dns_card_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()

        try:
            if self._auto_icon_label is not None:
                self._auto_icon_label.setPixmap(
                    get_cached_qta_pixmap('fa5s.sync', color=theme_tokens.fg_faint, size=16)
                )
        except Exception:
            pass

        try:
            if hasattr(self, "auto_indicator") and self.auto_indicator is not None:
                auto_card = getattr(self, "auto_card", None)
                auto_selected = bool(auto_card.property("selected")) if auto_card is not None else False
                self.auto_indicator.setStyleSheet(
                    DNSProviderCard._indicator_on() if auto_selected else DNSProviderCard._indicator_off()
                )
        except Exception:
            pass

        try:
            if hasattr(self, "custom_indicator") and self.custom_indicator is not None:
                custom_card = getattr(self, "custom_card", None)
                custom_selected = bool(custom_card.property("selected")) if custom_card is not None else False
                self.custom_indicator.setStyleSheet(
                    DNSProviderCard._indicator_on() if custom_selected else DNSProviderCard._indicator_off()
                )
        except Exception:
            pass

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._apply_inline_theme_styles(tokens)

    def _on_force_dns_toggled(self, enabled: bool):
        """Обработчик переключения принудительного DNS"""
        handle_force_dns_toggled_action(
            enabled=enabled,
            get_force_dns_status_fn=NetworkPageController.get_force_dns_status,
            enable_force_dns_fn=NetworkPageController.enable_force_dns,
            disable_force_dns_fn=NetworkPageController.disable_force_dns,
            build_toggle_plan_fn=NetworkPageController.build_force_dns_toggle_plan,
            build_toggle_error_plan_fn=NetworkPageController.build_force_dns_toggle_error_plan,
            set_force_dns_active_fn=lambda value: setattr(self, "_force_dns_active", value),
            set_force_dns_toggle_fn=self._set_force_dns_toggle,
            update_force_dns_status_fn=self._update_force_dns_status,
            update_dns_selection_state_fn=self._update_dns_selection_state,
            refresh_adapters_dns_fn=self._refresh_adapters_dns,
            log_fn=log,
        )
    
    def _set_force_dns_toggle(self, checked: bool):
        """Устанавливает состояние переключателя без триггера сигналов"""
        set_force_dns_toggle(self.force_dns_toggle, checked)
    
    def _update_force_dns_status(
        self,
        enabled: bool,
        details_key: str | None = None,
        *,
        details_kwargs: dict | None = None,
        details_fallback: str = "",
    ):
        """Обновляет текст статуса для принудительного DNS"""
        apply_force_dns_status_state(
            has_status_label=hasattr(self, "force_dns_status_label"),
            enabled=enabled,
            details_key=details_key,
            details_kwargs=details_kwargs,
            details_fallback=details_fallback,
            set_enabled_state_fn=lambda value: setattr(self, "_force_dns_status_enabled", value),
            set_details_key_fn=lambda value: setattr(self, "_force_dns_status_details_key", value),
            set_details_kwargs_fn=lambda value: setattr(self, "_force_dns_status_details_kwargs", value),
            set_details_fallback_fn=lambda value: setattr(self, "_force_dns_status_details_fallback", value),
            update_force_dns_status_label_fn=lambda **kwargs: update_force_dns_status_label(
                label=self.force_dns_status_label,
                language=self._ui_language,
                build_status_plan_fn=NetworkPageController.build_force_dns_status_plan,
                **kwargs,
            ),
        )
    
    def _update_dns_selection_state(self):
        """Обновляет состояние выбора DNS в зависимости от Force DNS"""
        update_dns_selection_block_state(
            blocked=bool(self._force_dns_active),
            dns_cards_container=getattr(self, 'dns_cards_container', None),
            custom_card=getattr(self, 'custom_card', None),
        )
    
    def _highlight_force_dns(self):
        """Подсвечивает карточку принудительного DNS при попытке изменить DNS"""
        highlight_force_dns_card(
            card=getattr(self, 'force_dns_card', None),
            get_theme_tokens_fn=get_theme_tokens,
            schedule_fn=QTimer.singleShot,
        )
    
    def _flush_dns_cache(self):
        """Сбрасывает DNS кэш"""
        flush_dns_cache_action(
            flush_dns_cache_fn=NetworkPageController.flush_dns_cache,
            build_result_plan_fn=NetworkPageController.build_flush_dns_cache_result_plan,
            language=self._ui_language,
            info_bar_cls=InfoBar,
            parent_window=self.window(),
        )

    def _confirm_flush_dns_cache(self):
        if not self._confirm_action(
            "page.network.button.flush_dns_cache",
            "Сбросить DNS кэш",
            "page.network.button.flush_dns_cache.confirm",
            "Сбросить?",
        ):
            return
        self._flush_dns_cache()

    def _reset_dns_to_dhcp(self):
        """Явно сбрасывает DNS на DHCP и отключает Force DNS"""
        reset_dns_to_dhcp_action(
            disable_force_dns_fn=NetworkPageController.disable_force_dns,
            get_force_dns_status_fn=NetworkPageController.get_force_dns_status,
            build_result_plan_fn=NetworkPageController.build_reset_dhcp_result_plan,
            language=self._ui_language,
            set_force_dns_active_fn=lambda value: setattr(self, "_force_dns_active", value),
            set_force_dns_toggle_fn=self._set_force_dns_toggle,
            select_auto_dns_ui_fn=select_auto_dns_ui,
            dns_cards=self.dns_cards,
            auto_indicator=getattr(self, 'auto_indicator', None),
            auto_card=getattr(self, 'auto_card', None),
            custom_indicator=getattr(self, 'custom_indicator', None),
            custom_card=getattr(self, 'custom_card', None),
            indicator_on_qss=DNSProviderCard.indicator_on(),
            indicator_off_qss=DNSProviderCard.indicator_off(),
            set_card_selected_fn=self._set_dns_card_selected,
            set_selected_provider_fn=lambda value: setattr(self, "_selected_provider", value),
            update_force_dns_status_fn=self._update_force_dns_status,
            update_dns_selection_state_fn=self._update_dns_selection_state,
            refresh_adapters_dns_fn=self._refresh_adapters_dns,
            info_bar_cls=InfoBar,
            parent_window=self.window(),
            tr_fn=self._tr,
            log_fn=log,
        )

    def _confirm_reset_dns_to_dhcp(self):
        if not self._confirm_action(
            "page.network.force_dns.reset.button",
            "Сбросить DNS на DHCP",
            "page.network.force_dns.reset.confirm",
            "Отключить Force DNS и сбросить DNS на DHCP для всех адаптеров?",
        ):
            return
        self._reset_dns_to_dhcp()

    def _test_connection(self):
        """Тестирует соединение с интернетом"""
        start_connectivity_test(
            cleanup_in_progress=self._cleanup_in_progress,
            set_test_in_progress_fn=lambda value: setattr(self, "_test_in_progress", value),
            update_test_action_text_fn=self._update_test_action_text,
            test_completed_signal=self.test_completed,
            on_test_complete_fn=self._on_test_complete,
            build_connectivity_test_plan_fn=NetworkPageController.build_connectivity_test_plan,
            run_connectivity_test_fn=NetworkPageController.run_connectivity_test,
            language=self._ui_language,
        )

    def _on_test_complete(self, results: list):
        """Вызывается из главного потока после завершения теста"""
        apply_connectivity_test_result(
            cleanup_in_progress=self._cleanup_in_progress,
            results=results,
            set_test_in_progress_fn=lambda value: setattr(self, "_test_in_progress", value),
            update_test_action_text_fn=self._update_test_action_text,
            build_result_plan_fn=NetworkPageController.build_connectivity_test_result_plan,
            language=self._ui_language,
            info_bar_cls=InfoBar,
            parent_window=self.window(),
        )

    # ═══════════════════════════════════════════════════════════════
    # ISP DNS предупреждение
    # ═══════════════════════════════════════════════════════════════

    def _check_and_show_isp_dns_warning(self):
        """Показывает предупреждение если у пользователя DNS от провайдера (DHCP).

        Показывается ОДИН раз за всё время установки. Как только баннер
        отрисован — в реестр пишется ISPDNSInfoShown=1 и повторно он
        больше никогда не появится.
        """
        show_isp_dns_warning(
            cleanup_in_progress=self._cleanup_in_progress,
            adapters=self._adapters,
            dns_info=self._dns_info,
            force_dns_active=self._force_dns_active,
            language=self._ui_language,
            build_warning_plan_fn=NetworkPageController.build_isp_dns_warning_plan,
            get_theme_tokens_fn=get_theme_tokens,
            build_warning_ui_fn=build_isp_warning_ui,
            insert_warning_widget_fn=insert_isp_warning_widget,
            mark_warning_shown_fn=NetworkPageController.mark_isp_dns_warning_shown,
            render_warning_styles_fn=self._render_isp_warning_styles,
            parent=self,
            qframe_cls=QFrame,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            qpush_button_cls=QPushButton,
            qt_namespace=Qt,
            add_widget_fn=self.add_widget,
            before_widget=self.dns_cards_container,
            on_accept=self._accept_isp_dns_recommendation,
            on_dismiss=self._dismiss_isp_dns_warning,
            set_warning_widgets_fn=lambda widgets: (
                setattr(self, "_isp_warning", widgets.frame),
                setattr(self, "_isp_warning_title", widgets.title),
                setattr(self, "_isp_warning_content", widgets.content),
                setattr(self, "_isp_warning_icon", widgets.icon),
                setattr(self, "_isp_warning_accept_btn", widgets.accept_button),
                setattr(self, "_isp_warning_dismiss_btn", widgets.dismiss_button),
            ),
            log_fn=log,
        )

    def _render_isp_warning_styles(self, tokens=None) -> None:
        render_isp_warning_theme(
            tokens=tokens,
            get_theme_tokens_fn=get_theme_tokens,
            render_warning_styles_fn=render_isp_warning_styles,
            warning=getattr(self, "_isp_warning", None),
            icon_label=self._isp_warning_icon,
            title_label=self._isp_warning_title,
            content_label=self._isp_warning_content,
            accept_button=self._isp_warning_accept_btn,
            dismiss_button=self._isp_warning_dismiss_btn,
            qta_module=qta,
        )

    def _accept_isp_dns_recommendation(self):
        """Включает Force DNS по рекомендации из баннера"""
        accept_isp_dns_recommendation(
            cleanup_in_progress=self._cleanup_in_progress,
            build_accept_plan_fn=NetworkPageController.build_accept_isp_dns_warning_plan,
            warning=getattr(self, "_isp_warning", None),
            hide_warning_widget_fn=hide_isp_warning_widget,
            set_force_dns_toggle_fn=self._set_force_dns_toggle,
            on_force_dns_toggled_fn=self._on_force_dns_toggled,
            log_fn=log,
        )

    def _dismiss_isp_dns_warning(self):
        """Скрывает баннер (реестр уже записан при показе)"""
        dismiss_isp_dns_warning(
            cleanup_in_progress=self._cleanup_in_progress,
            build_dismiss_plan_fn=NetworkPageController.build_dismiss_isp_dns_warning_plan,
            warning=getattr(self, "_isp_warning", None),
            hide_warning_widget_fn=hide_isp_warning_widget,
        )

    def cleanup(self) -> None:
        cleanup_network_page(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            set_test_in_progress_fn=lambda value: setattr(self, "_test_in_progress", value),
            signal_objects={
                "adapters_loaded": getattr(self, "adapters_loaded", None),
                "dns_info_loaded": getattr(self, "dns_info_loaded", None),
                "test_completed": getattr(self, "test_completed", None),
            },
            warning=getattr(self, "_isp_warning", None),
            hide_warning_widget_fn=hide_isp_warning_widget,
        )
