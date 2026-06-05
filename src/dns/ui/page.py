# dns/ui/page.py
"""Страница сетевых настроек - DNS, hosts, proxy"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame,
)
import qtawesome as qta

from qfluentwidgets import (
    BodyLabel, CaptionLabel, CheckBox, IndeterminateProgressBar, InfoBar,
    LineEdit, MessageBox, PushButton, SettingCardGroup, StrongBodyLabel,
)

from ui.pages.base_page import BasePage
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.widgets.win11_controls import Win11ToggleRow
from ui.fluent_widgets import (
    SettingsCard,
    QuickActionsBar,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from app.ui_texts import tr as tr_catalog
from log.log import log

from dns.dns_providers import DNS_PROVIDERS
from dns import page_plans as dns_page_plans
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
from dns.page_force_dns_workflow import (
    apply_force_dns_status_state,
)
from dns.ui.isp_warning import (
    build_isp_warning_ui,
    hide_isp_warning_widget,
    insert_isp_warning_widget,
    render_isp_warning_styles,
)
from dns.page_diagnostics_warning_workflow import (
    accept_isp_dns_recommendation,
    apply_connectivity_test_result,
    cleanup_network_page,
    dismiss_isp_dns_warning,
    prepare_connectivity_test,
    render_isp_warning_theme,
    show_isp_dns_warning,
)
from dns.page_load_workflow import (
    apply_loaded_page_state,
    handle_loaded_adapters,
    handle_loaded_dns_info,
    run_network_runtime_init,
)
from dns.ui.page_runtime_helpers import (
    build_adapter_cards_ui,
    build_dns_choices_ui,
    clear_dns_selection_ui,
)
from dns.ui.page_selection_workflow import (
    build_dns_selection_sync_request_fn,
)
from dns.ui.selection import (
    apply_dns_selection_plan_ui,
    clear_dns_selection,
    select_auto_dns_ui,
    select_custom_dns_ui,
    select_provider_dns_ui,
    set_dns_card_selected,
)

class NetworkPage(BasePage):
    """Страница сетевых настроек с интегрированным DNS"""

    adapters_loaded = pyqtSignal(list)
    dns_info_loaded = pyqtSignal(dict)
    test_completed = pyqtSignal(list)  # Результаты теста соединения
    
    def __init__(self, parent=None, *, deps):
        super().__init__(
            "Сеть",
            "Настройки DNS и доступа к сервисам",
            parent,
            title_key="page.network.title",
            subtitle_key="page.network.subtitle",
        )
        self._dns = deps.dns_feature
        
        self._adapters = []
        self._dns_info = {}
        self._is_loading = True
        self._ui_built = False
        self._dns_choices_built = False
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
        self._dns_selection_sync_queued = False
        self._page_load_runtime = OneShotWorkerRuntime()
        self._page_load_pending = False
        self._page_load_start_scheduled = False
        self._connectivity_test_runtime = OneShotWorkerRuntime()
        self._connectivity_test_pending = False
        self._connectivity_test_start_scheduled = False
        self._force_dns_action_runtime = OneShotWorkerRuntime()
        self._force_dns_action_pending: list[dict[str, object]] = []
        self._scheduled_force_dns_action_request = None
        self._force_dns_action_start_scheduled = False
        self._dns_flush_cache_runtime = OneShotWorkerRuntime()
        self._dns_flush_cache_pending = False
        self._dns_flush_cache_start_scheduled = False
        self._dns_apply_runtime = OneShotWorkerRuntime()
        self._dns_apply_pending: list[dict[str, object]] = []
        self._scheduled_dns_apply_request = None
        self._dns_apply_start_scheduled = False
        self._dns_mutation_pending_order: list[str] = []
        self._isp_warning_runtime = OneShotWorkerRuntime()
        self._isp_warning_pending = False
        self._isp_warning_start_scheduled = False
        
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
        self._request_dns_selection_sync = build_dns_selection_sync_request_fn(
            get_cleanup_in_progress_fn=lambda: self._cleanup_in_progress,
            get_sync_queued_fn=lambda: self._dns_selection_sync_queued,
            set_sync_queued_fn=lambda value: setattr(self, "_dns_selection_sync_queued", value),
            schedule_fn=QTimer.singleShot,
            get_adapter_cards_fn=lambda: self.adapter_cards,
            get_dns_info_fn=lambda: self._dns_info,
            providers=DNS_PROVIDERS,
            build_dns_selection_plan_fn=lambda **kwargs: dns_page_plans.build_dns_selection_plan(
                **kwargs,
                normalize_alias_fn=self._dns.normalize_adapter_alias,
            ),
            get_selected_adapters_fn=self._get_selected_adapters,
            apply_dns_selection_plan_ui_fn=apply_dns_selection_plan_ui,
            get_dns_cards_fn=lambda: self.dns_cards,
            get_auto_indicator_fn=lambda: getattr(self, "auto_indicator", None),
            get_auto_card_fn=lambda: getattr(self, "auto_card", None),
            get_custom_indicator_fn=lambda: getattr(self, "custom_indicator", None),
            get_custom_card_fn=lambda: getattr(self, "custom_card", None),
            get_custom_primary_fn=lambda: getattr(self, "custom_primary", None),
            get_custom_secondary_fn=lambda: getattr(self, "custom_secondary", None),
            get_indicator_on_qss_fn=DNSProviderCard.indicator_on,
            get_indicator_off_qss_fn=DNSProviderCard.indicator_off,
            set_card_selected_fn=self._set_dns_card_selected,
            set_selected_provider_fn=lambda value: setattr(self, "_selected_provider", value),
        )
        self._apply_page_theme(force=True)

    def _dns_feature(self):
        return self._dns

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
            build_page_init_plan_fn=dns_page_plans.build_page_init_plan,
            mark_initialized_fn=lambda: setattr(self, "_runtime_initialized", True),
            schedule_fn=QTimer.singleShot,
            start_loading_fn=self._start_loading,
        )

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()
        if self._is_loading and not self._dns_choices_built:
            try:
                self.loading_bar.start()
            except Exception:
                pass

    def on_page_hidden(self) -> None:
        try:
            self.loading_bar.stop()
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if hasattr(self, "loading_label"):
            self.loading_label.setText(self._tr("page.network.loading", "⏳ Загрузка..."))

        if hasattr(self, "custom_label"):
            self.custom_label.setText(self._tr("page.network.custom.label", "Свой:"))
        if hasattr(self, "custom_apply_btn"):
            self.custom_apply_btn.setText(self._tr("page.network.custom.apply", "OK"))

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
            set_tooltip(
                self.force_dns_reset_dhcp_btn,
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
            body_label_cls=BodyLabel,
            settings_card_cls=SettingsCard,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            line_edit_cls=LineEdit,
            action_button_cls=PushButton,
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
        self._build_dns_choices_ui()

        self.add_spacing(12)

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

    def _build_dns_choices_ui(self):
        """Строит выбор DNS сразу, без ожидания текущих DNS Windows."""
        result = build_dns_choices_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            dns_choices_built=self._dns_choices_built,
            tr_fn=self._tr,
            settings_card_cls=SettingsCard,
            qhbox_layout_cls=QHBoxLayout,
            qframe_cls=QFrame,
            strong_body_label_cls=StrongBodyLabel,
            caption_label_cls=CaptionLabel,
            qlabel_cls=QLabel,
            qta_module=qta,
            get_theme_tokens_fn=get_theme_tokens,
            build_auto_dns_ui_fn=build_auto_dns_ui,
            build_provider_cards_fn=build_provider_cards,
            providers=DNS_PROVIDERS,
            dns_cards_layout=self.dns_cards_layout,
            on_auto_selected=self._select_auto_dns,
            on_provider_selected=self._on_dns_selected,
            ipv6_available=True,
            dns_cards_container=self.dns_cards_container,
            custom_card=self.custom_card,
            dns_provider_card_cls=DNSProviderCard,
            apply_inline_theme_styles_fn=self._apply_inline_theme_styles,
        )
        if result is None:
            return

        self._dns_choices_built = True
        auto_widgets = result["auto_widgets"]
        self.auto_card = auto_widgets.card
        self.auto_indicator = auto_widgets.indicator
        self._auto_icon_label = auto_widgets.icon_label
        self.auto_label = auto_widgets.title_label
        provider_cards = result["provider_cards"]
        self.dns_cards.update(provider_cards.dns_cards)
        self._dns_category_labels.extend(provider_cards.category_labels)
        self._update_dns_selection_state()
        try:
            self.loading_bar.stop()
        except Exception:
            pass
        self.loading_card.hide()
    
    def _start_loading(self):
        """Запускает асинхронную загрузку данных"""
        if self._cleanup_in_progress:
            return
        if (
            self._page_load_runtime.is_running()
            or self.__dict__.get("_page_load_start_scheduled", False)
        ):
            self._page_load_pending = True
            return
        self._page_load_pending = False
        try:
            cached_state = self._dns_feature().consume_warmed_page_data()
        except Exception:
            cached_state = None
        if cached_state is not None:
            self._on_page_state_loaded(cached_state)
            return
        self._page_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._dns_feature().create_page_load_worker(
                request_id,
                parent=self,
            ),
            on_loaded=self._on_page_state_loaded_from_worker,
            on_finished=self._on_page_load_worker_finished,
        )

    def _on_page_state_loaded_from_worker(self, request_id: int, state) -> None:
        if not self._page_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._on_page_state_loaded(state)

    def _on_page_load_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_page_load_runtime"), _worker):
            return
        if self.__dict__.get("_page_load_pending", False):
            self._schedule_page_load_worker_start()

    def _schedule_page_load_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_page_load_start_scheduled", False):
            self._page_load_pending = True
            return
        self._page_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_page_load_worker_start)

    def _run_scheduled_page_load_worker_start(self) -> None:
        self._page_load_start_scheduled = False
        pending = bool(self.__dict__.get("_page_load_pending", False))
        self._page_load_pending = False
        if self.__dict__.get("_cleanup_in_progress", False) or not pending:
            return
        self._start_loading()
    
    def _on_page_state_loaded(self, state):
        """Применяет готовое состояние DNS страницы в UI-потоке."""
        if self._cleanup_in_progress:
            return
        try:
            apply_loaded_page_state(
                state=state,
                set_ipv6_available_fn=lambda value: setattr(self, "_ipv6_available", value),
                set_force_dns_active_fn=lambda value: setattr(self, "_force_dns_active", value),
                set_adapters_fn=lambda adapters: setattr(self, "_adapters", adapters),
                set_dns_info_fn=lambda dns_info: setattr(self, "_dns_info", dns_info),
                emit_adapters_loaded_fn=lambda adapters: (not self._cleanup_in_progress) and self.adapters_loaded.emit(adapters),
                emit_dns_info_loaded_fn=lambda dns_info: (not self._cleanup_in_progress) and self.dns_info_loaded.emit(dns_info),
            )
            self._apply_loaded_force_dns_state()
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
        if not self._dns_choices_built:
            self._build_dns_choices_ui()

        adapter_cards = build_adapter_cards_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            adapter_cards_built=self._ui_built,
            adapters=self._adapters,
            dns_info=self._dns_info,
            build_adapter_cards_fn=build_adapter_cards,
            adapter_card_cls=AdapterCard,
            adapters_layout=self.adapters_layout,
            on_state_changed=self._request_dns_selection_sync,
            normalize_alias_fn=self._dns.normalize_adapter_alias,
            adapters_container=self.adapters_container,
        )
        if adapter_cards is None:
            return
        self._ui_built = True
        self._is_loading = False
        self.adapter_cards = adapter_cards
        self._check_and_show_isp_dns_warning()
        self._apply_inline_theme_styles()
        self._request_dns_selection_sync()
    
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
        self._request_dns_apply("auto", adapters=self._get_selected_adapters())
    
    def _apply_provider_dns_quick(self, name: str, data: dict):
        """Быстрое применение DNS провайдера"""
        self._request_dns_apply(
            "provider",
            adapters=self._get_selected_adapters(),
            name=name,
            data=data,
            ipv6_available=self._ipv6_available,
        )
    
    def _apply_custom_dns_quick(self):
        """Быстрое применение пользовательского DNS"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return
        
        primary = self.custom_primary.text().strip()
        if not primary:
            return
        
        secondary = self.custom_secondary.text().strip() or None
        
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
        
        self._request_dns_apply(
            "custom",
            adapters=self._get_selected_adapters(),
            primary=primary,
            secondary=secondary,
        )

    def create_dns_apply_worker(
        self,
        request_id: int,
        *,
        action: str,
        adapters,
        name: str = "",
        data=None,
        primary: str = "",
        secondary: str | None = None,
        ipv6_available: bool = False,
    ):
        return self._dns_feature().create_dns_apply_worker(
            request_id,
            action=action,
            adapters=adapters,
            name=name,
            data=data,
            primary=primary,
            secondary=secondary,
            ipv6_available=ipv6_available,
            parent=self,
        )

    def _request_dns_apply(self, action: str, **payload) -> None:
        request = {
            "action": str(action or "").strip(),
            **payload,
        }
        if self.__dict__.get("_dns_apply_start_scheduled", False):
            self._scheduled_dns_apply_request = dict(request)
            return
        if self._dns_mutation_action_running():
            self._queue_dns_apply_request(request)
            return
        self._start_dns_apply_worker(request)

    def _queue_dns_apply_request(self, payload: dict[str, object]) -> None:
        pending = self.__dict__.setdefault("_dns_apply_pending", [])
        pending[:] = [dict(payload or {})]
        self._mark_dns_mutation_pending("dns_apply")

    def _start_dns_apply_worker(self, payload: dict[str, object]) -> None:
        self._dns_apply_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_dns_apply_worker(
                request_id,
                action=str(payload.get("action") or ""),
                adapters=payload.get("adapters") or [],
                name=str(payload.get("name") or ""),
                data=payload.get("data") or {},
                primary=str(payload.get("primary") or ""),
                secondary=payload.get("secondary"),
                ipv6_available=bool(payload.get("ipv6_available", False)),
            ),
            on_failed=self._on_dns_apply_failed,
            on_finished=self._on_dns_apply_worker_finished,
            bind_worker=self._bind_dns_apply_worker,
        )

    def _bind_dns_apply_worker(self, worker) -> None:
        worker.completed.connect(self._on_dns_apply_finished)

    def _on_dns_apply_finished(self, request_id: int, result) -> None:
        if not self._dns_apply_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._has_pending_dns_mutation_action():
            return
        data = result if isinstance(result, dict) else {}
        plan = data.get("plan")
        if plan is not None and getattr(plan, "log_message", ""):
            log(plan.log_message, getattr(plan, "log_level", None) or "INFO")
        dns_info = data.get("dns_info")
        if isinstance(dns_info, dict):
            self._apply_refreshed_adapter_dns_info(dns_info)

    def _on_dns_apply_failed(self, request_id: int, error: str) -> None:
        if not self._dns_apply_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._has_pending_dns_mutation_action():
            return
        log(f"Ошибка применения DNS: {error}", "ERROR")

    def _on_dns_apply_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_dns_apply_runtime"), _worker):
            return
        self._start_next_dns_mutation_action()

    def _has_pending_dns_mutation_action(self) -> bool:
        return any(
            self.__dict__.get(attr)
            for attr in (
                "_dns_apply_pending",
                "_force_dns_action_pending",
                "_dns_mutation_pending_order",
            )
        )

    def _dns_mutation_action_running(self) -> bool:
        if self.__dict__.get("_dns_apply_start_scheduled", False):
            return True
        if self.__dict__.get("_force_dns_action_start_scheduled", False):
            return True
        dns_apply_runtime = self.__dict__.get("_dns_apply_runtime")
        force_dns_runtime = self.__dict__.get("_force_dns_action_runtime")
        return bool(
            (dns_apply_runtime is not None and dns_apply_runtime.is_running())
            or (force_dns_runtime is not None and force_dns_runtime.is_running())
        )

    def _start_next_dns_mutation_action(self) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        if self._dns_mutation_action_running():
            return True
        dns_apply_pending = self.__dict__.setdefault("_dns_apply_pending", [])
        force_dns_pending = self.__dict__.setdefault("_force_dns_action_pending", [])
        pending_order = self.__dict__.setdefault("_dns_mutation_pending_order", [])
        while pending_order:
            kind = str(pending_order.pop(0) or "")
            if kind == "dns_apply" and dns_apply_pending:
                pending = dns_apply_pending.pop(0)
                self._schedule_dns_apply_worker_start(dict(pending or {}))
                return True
            if kind == "force_dns" and force_dns_pending:
                pending = force_dns_pending.pop(0)
                self._schedule_force_dns_action_worker_start(dict(pending or {}))
                return True
        if dns_apply_pending:
            pending = dns_apply_pending.pop(0)
            self._schedule_dns_apply_worker_start(dict(pending or {}))
            return True
        if force_dns_pending:
            pending = force_dns_pending.pop(0)
            self._schedule_force_dns_action_worker_start(dict(pending or {}))
            return True
        return False

    def _mark_dns_mutation_pending(self, kind: str) -> None:
        normalized = str(kind or "").strip()
        if not normalized:
            return
        pending_order = self.__dict__.setdefault("_dns_mutation_pending_order", [])
        pending_order[:] = [item for item in pending_order if str(item or "") != normalized]
        pending_order.append(normalized)

    def _schedule_dns_apply_worker_start(self, payload: dict[str, object]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._scheduled_dns_apply_request = dict(payload or {})
        if self.__dict__.get("_dns_apply_start_scheduled", False):
            return
        self._dns_apply_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_dns_apply_worker_start)

    def _run_scheduled_dns_apply_worker_start(self, payload: dict[str, object] | None = None) -> None:
        self._dns_apply_start_scheduled = False
        if payload is None:
            payload = self.__dict__.get("_scheduled_dns_apply_request")
        self._scheduled_dns_apply_request = None
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_dns_apply_worker(dict(payload or {}))

    def _apply_refreshed_adapter_dns_info(self, dns_info: dict) -> None:
        if self._cleanup_in_progress:
            return
        try:
            self._dns_info = dns_info
            refresh_plan = refresh_adapter_cards(
                adapter_cards=self.adapter_cards,
                dns_info=dns_info,
                build_refresh_plan_fn=lambda names, info: dns_page_plans.build_adapter_dns_refresh_plan(
                    names,
                    info,
                    normalize_alias_fn=self._dns.normalize_adapter_alias,
                ),
            )

            self._request_dns_selection_sync()
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
            get_force_dns_status_fn=lambda: self._force_dns_active,
            setting_card_group_cls=SettingCardGroup,
            caption_label_cls=CaptionLabel,
            action_button_cls=PushButton,
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

    def _apply_loaded_force_dns_state(self) -> None:
        if self._cleanup_in_progress:
            return
        if not hasattr(self, "force_dns_toggle"):
            return
        self._set_force_dns_toggle(bool(self._force_dns_active))
        self._update_force_dns_status(bool(self._force_dns_active))
        self._update_dns_selection_state()

    def _apply_inline_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
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
                    DNSProviderCard.indicator_on() if auto_selected else DNSProviderCard.indicator_off()
                )
        except Exception:
            pass

        try:
            if hasattr(self, "custom_indicator") and self.custom_indicator is not None:
                custom_card = getattr(self, "custom_card", None)
                custom_selected = bool(custom_card.property("selected")) if custom_card is not None else False
                self.custom_indicator.setStyleSheet(
                    DNSProviderCard.indicator_on() if custom_selected else DNSProviderCard.indicator_off()
                )
        except Exception:
            pass

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._apply_inline_theme_styles(tokens)

    def _on_force_dns_toggled(self, enabled: bool):
        """Обработчик переключения принудительного DNS"""
        self._request_force_dns_action("toggle", enabled=bool(enabled))

    def create_force_dns_action_worker(self, request_id: int, *, action: str, enabled=None, adapters=None):
        return self._dns_feature().create_force_dns_action_worker(
            request_id,
            action=action,
            enabled=enabled,
            adapters=adapters,
            language=self._ui_language,
            parent=self,
        )

    def _request_force_dns_action(self, action: str, *, enabled=None) -> None:
        payload = {
            "action": str(action or "").strip(),
            "enabled": enabled,
        }
        scheduled = self.__dict__.get("_scheduled_force_dns_action_request")
        if self.__dict__.get("_force_dns_action_start_scheduled", False):
            if isinstance(scheduled, dict) and scheduled.get("action") == payload.get("action"):
                self._scheduled_force_dns_action_request = dict(payload)
            else:
                self._queue_force_dns_action(payload)
            return
        if self._dns_mutation_action_running():
            self._queue_force_dns_action(payload)
            return
        self._start_force_dns_action_worker(payload)

    def _queue_force_dns_action(self, payload: dict[str, object]) -> None:
        queued = dict(payload or {})
        action = str(queued.get("action") or "")
        pending = self.__dict__.setdefault("_force_dns_action_pending", [])
        if action == "toggle":
            pending[:] = [item for item in pending if str(item.get("action") or "") != "toggle"]
        elif queued in pending:
            return
        pending.append(queued)
        self._mark_dns_mutation_pending("force_dns")

    def _start_force_dns_action_worker(self, payload: dict[str, object]) -> None:
        self._force_dns_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_force_dns_action_worker(
                request_id,
                action=str(payload.get("action") or ""),
                enabled=payload.get("enabled"),
                adapters=[card.adapter_name for card in self.adapter_cards],
            ),
            on_failed=self._on_force_dns_action_failed,
            on_finished=self._on_force_dns_action_worker_finished,
            bind_worker=self._bind_force_dns_action_worker,
        )

    def _bind_force_dns_action_worker(self, worker) -> None:
        worker.completed.connect(self._on_force_dns_action_finished)

    def _on_force_dns_action_finished(self, request_id: int, action: str, result, context) -> None:
        if not self._force_dns_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._has_pending_dns_mutation_action():
            return
        data = result if isinstance(result, dict) else {}
        message = str(data.get("message") or "")
        if message:
            log(message, "DNS")
        if action == "toggle":
            self._apply_force_dns_toggle_worker_result(data)
            return
        if action == "reset_dhcp":
            self._apply_force_dns_reset_worker_result(data)

    def _apply_force_dns_toggle_worker_result(self, data: dict[str, object]) -> None:
        plan = data.get("plan")
        if plan is None:
            plan = dns_page_plans.build_force_dns_toggle_error_plan(
                requested_enabled=bool(data.get("enabled", False))
            )
        self._force_dns_active = bool(plan.force_dns_active)
        self._set_force_dns_toggle(bool(plan.final_checked))
        self._update_force_dns_status(
            bool(plan.force_dns_active),
            plan.details_key,
            details_kwargs=dict(plan.details_kwargs or {}),
            details_fallback=str(plan.details_fallback or ""),
        )
        self._update_dns_selection_state()
        dns_info = data.get("dns_info")
        if bool(data.get("changed", True)) and isinstance(dns_info, dict):
            self._apply_refreshed_adapter_dns_info(dns_info)

    def _apply_force_dns_reset_worker_result(self, data: dict[str, object]) -> None:
        result_plan = data.get("plan")
        if result_plan is None:
            self._on_force_dns_action_failed(
                self._force_dns_action_runtime.request_id,
                "reset_dhcp",
                "Пустой результат сброса DNS",
                {},
            )
            return
        self._force_dns_active = bool(result_plan.force_dns_active)
        self._set_force_dns_toggle(bool(result_plan.force_dns_active))

        if bool(result_plan.should_select_auto):
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

        self._update_force_dns_status(
            bool(result_plan.force_dns_active),
            result_plan.status_details_key,
        )
        self._update_dns_selection_state()
        dns_info = data.get("dns_info")
        if isinstance(dns_info, dict):
            self._apply_refreshed_adapter_dns_info(dns_info)

        if result_plan.infobar_level == "success":
            InfoBar.success(
                title=result_plan.infobar_title,
                content=result_plan.infobar_content,
                parent=self.window(),
            )
        else:
            InfoBar.warning(
                title=result_plan.infobar_title,
                content=result_plan.infobar_content,
                parent=self.window(),
            )

    def _on_force_dns_action_failed(self, request_id: int, action: str, error: str, context) -> None:
        if not self._force_dns_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self._has_pending_dns_mutation_action():
            return
        log(f"Ошибка Force DNS ({action}): {error}", "ERROR")
        if action == "toggle":
            requested_enabled = bool((context or {}).get("enabled"))
            plan = dns_page_plans.build_force_dns_toggle_error_plan(requested_enabled=requested_enabled)
            self._apply_force_dns_toggle_worker_result({"plan": plan, "changed": False})
            return
        InfoBar.warning(
            title=self._tr("page.network.error.title", "Ошибка"),
            content=self._tr(
                "page.network.error.reset_dhcp_failed",
                "Не удалось сбросить DNS: {error}",
            ).format(error=error),
            parent=self.window(),
        )

    def _on_force_dns_action_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_force_dns_action_runtime"), _worker):
            return
        self._start_next_dns_mutation_action()

    def _schedule_force_dns_action_worker_start(self, payload: dict[str, object]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._scheduled_force_dns_action_request = dict(payload or {})
        if self.__dict__.get("_force_dns_action_start_scheduled", False):
            return
        self._force_dns_action_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_force_dns_action_worker_start)

    def _run_scheduled_force_dns_action_worker_start(self, payload: dict[str, object] | None = None) -> None:
        self._force_dns_action_start_scheduled = False
        if payload is None:
            payload = self.__dict__.get("_scheduled_force_dns_action_request")
        self._scheduled_force_dns_action_request = None
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_force_dns_action_worker(dict(payload or {}))

    def create_dns_flush_cache_worker(self, request_id: int):
        return self._dns_feature().create_dns_flush_cache_worker(
            request_id,
            language=self._ui_language,
            parent=self,
        )

    def _request_dns_flush_cache(self) -> None:
        if self._dns_flush_cache_runtime.is_running() or self.__dict__.get("_dns_flush_cache_start_scheduled", False):
            self._dns_flush_cache_pending = True
            return
        self._start_dns_flush_cache_worker()

    def _start_dns_flush_cache_worker(self) -> None:
        self._dns_flush_cache_runtime.start_qthread_worker(
            worker_factory=self.create_dns_flush_cache_worker,
            on_failed=self._on_dns_flush_cache_failed,
            on_finished=self._on_dns_flush_cache_worker_finished,
            bind_worker=self._bind_dns_flush_cache_worker,
        )

    def _bind_dns_flush_cache_worker(self, worker) -> None:
        worker.completed.connect(self._on_dns_flush_cache_finished)

    def _on_dns_flush_cache_finished(self, request_id: int, plan) -> None:
        if not self._dns_flush_cache_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if getattr(plan, "infobar_level", None) == "warning":
            InfoBar.warning(
                title=plan.title,
                content=plan.content,
                parent=self.window(),
            )

    def _on_dns_flush_cache_failed(self, request_id: int, error: str) -> None:
        if not self._dns_flush_cache_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        plan = dns_page_plans.build_flush_dns_cache_result_plan(
            success=False,
            message=str(error or ""),
            language=self._ui_language,
        )
        InfoBar.warning(
            title=plan.title,
            content=plan.content,
            parent=self.window(),
        )

    def _on_dns_flush_cache_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_dns_flush_cache_runtime"), _worker):
            return
        if self._dns_flush_cache_pending and not self._cleanup_in_progress:
            self._dns_flush_cache_pending = False
            self._schedule_dns_flush_cache_worker_start()

    def _schedule_dns_flush_cache_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_dns_flush_cache_start_scheduled", False):
            self._dns_flush_cache_pending = True
            return
        self._dns_flush_cache_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_dns_flush_cache_worker_start)

    def _run_scheduled_dns_flush_cache_worker_start(self) -> None:
        self._dns_flush_cache_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_dns_flush_cache_worker()
    
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
                build_status_plan_fn=dns_page_plans.build_force_dns_status_plan,
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
        self._request_dns_flush_cache()

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
        self._request_force_dns_action("reset_dhcp")

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
        if (
            self._connectivity_test_runtime.is_running()
            or self.__dict__.get("_connectivity_test_start_scheduled", False)
        ):
            self._connectivity_test_pending = True
            return
        self._connectivity_test_pending = False
        test_plan = prepare_connectivity_test(
            cleanup_in_progress=self._cleanup_in_progress,
            set_test_in_progress_fn=lambda value: setattr(self, "_test_in_progress", value),
            update_test_action_text_fn=self._update_test_action_text,
            build_connectivity_test_plan_fn=dns_page_plans.build_connectivity_test_plan,
            language=self._ui_language,
        )
        if test_plan is None:
            return
        self._connectivity_test_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._dns_feature().create_connectivity_test_worker(
                request_id,
                test_hosts=test_plan.test_hosts,
                parent=self,
            ),
            on_finished=self._on_connectivity_test_worker_finished,
            bind_worker=self._bind_connectivity_test_worker,
        )

    def _bind_connectivity_test_worker(self, worker) -> None:
        worker.completed.connect(self._on_connectivity_test_complete)

    def _on_connectivity_test_complete(self, request_id: int, results: list) -> None:
        if not self._connectivity_test_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        self._on_test_complete(results)

    def _on_connectivity_test_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_connectivity_test_runtime"), _worker):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_connectivity_test_pending", False):
            self._schedule_connectivity_test_start()

    def _schedule_connectivity_test_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_connectivity_test_start_scheduled", False):
            return
        self._connectivity_test_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_connectivity_test_start)

    def _run_scheduled_connectivity_test_start(self) -> None:
        self._connectivity_test_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_connectivity_test_pending", False):
            return
        self._connectivity_test_pending = False
        self._test_connection()

    def _on_test_complete(self, results: list):
        """Вызывается из главного потока после завершения теста"""
        apply_connectivity_test_result(
            cleanup_in_progress=self._cleanup_in_progress,
            results=results,
            set_test_in_progress_fn=lambda value: setattr(self, "_test_in_progress", value),
            update_test_action_text_fn=self._update_test_action_text,
            build_result_plan_fn=dns_page_plans.build_connectivity_test_result_plan,
            language=self._ui_language,
            info_bar_cls=InfoBar,
            parent_window=self.window(),
        )

    # ═══════════════════════════════════════════════════════════════
    # ISP DNS предупреждение
    # ═══════════════════════════════════════════════════════════════

    def _check_and_show_isp_dns_warning(self):
        """Показывает предупреждение если у пользователя DNS от провайдера (DHCP).

        Показывается ОДИН раз за всё время установки. Решение и запись
        ISPDNSInfoShown=1 выполняются в worker-е, GUI только рисует готовый план.
        """
        self._request_isp_dns_warning_plan()

    def _request_isp_dns_warning_plan(self) -> None:
        if (
            self._isp_warning_runtime.is_running()
            or self.__dict__.get("_isp_warning_start_scheduled", False)
        ):
            self._isp_warning_pending = True
            return
        self._isp_warning_pending = False
        self._isp_warning_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._dns.create_isp_dns_warning_worker(
                request_id,
                adapters=self._adapters,
                dns_info=self._dns_info,
                force_dns_active=self._force_dns_active,
                language=self._ui_language,
                parent=self,
            ),
            on_failed=self._on_isp_dns_warning_plan_failed,
            on_finished=self._on_isp_dns_warning_worker_finished,
            bind_worker=self._bind_isp_dns_warning_worker,
        )

    def _bind_isp_dns_warning_worker(self, worker) -> None:
        worker.completed.connect(self._on_isp_dns_warning_plan_loaded)

    def _on_isp_dns_warning_plan_loaded(self, request_id: int, plan) -> None:
        if not self._isp_warning_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_isp_warning_pending", False):
            return
        show_isp_dns_warning(
            cleanup_in_progress=self._cleanup_in_progress,
            plan=plan,
            get_theme_tokens_fn=get_theme_tokens,
            build_warning_ui_fn=build_isp_warning_ui,
            insert_warning_widget_fn=insert_isp_warning_widget,
            render_warning_styles_fn=self._render_isp_warning_styles,
            parent=self,
            qframe_cls=QFrame,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qlabel_cls=QLabel,
            qpush_button_cls=PushButton,
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

    def _on_isp_dns_warning_plan_failed(self, request_id: int, error: str) -> None:
        if not self._isp_warning_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_isp_warning_pending", False):
            return
        log(f"Ошибка подготовки ISP DNS предупреждения: {error}", "DEBUG")

    def _on_isp_dns_warning_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_isp_warning_runtime"), _worker):
            return
        if self.__dict__.get("_isp_warning_pending", False):
            self._schedule_isp_warning_worker_start()

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _schedule_isp_warning_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_isp_warning_start_scheduled", False):
            self._isp_warning_pending = True
            return
        self._isp_warning_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_isp_warning_worker_start)

    def _run_scheduled_isp_warning_worker_start(self) -> None:
        self._isp_warning_start_scheduled = False
        pending = bool(self.__dict__.get("_isp_warning_pending", False))
        self._isp_warning_pending = False
        if self.__dict__.get("_cleanup_in_progress", False) or not pending:
            return
        self._request_isp_dns_warning_plan()

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
            build_accept_plan_fn=dns_page_plans.build_accept_isp_dns_warning_plan,
            warning=getattr(self, "_isp_warning", None),
            hide_warning_widget_fn=hide_isp_warning_widget,
            set_force_dns_toggle_fn=self._set_force_dns_toggle,
            on_force_dns_toggled_fn=self._on_force_dns_toggled,
            log_fn=log,
        )

    def _dismiss_isp_dns_warning(self):
        """Скрывает баннер (settings.json уже записан при показе)."""
        dismiss_isp_dns_warning(
            cleanup_in_progress=self._cleanup_in_progress,
            build_dismiss_plan_fn=dns_page_plans.build_dismiss_isp_dns_warning_plan,
            warning=getattr(self, "_isp_warning", None),
            hide_warning_widget_fn=hide_isp_warning_widget,
        )

    def cleanup(self) -> None:
        try:
            self.loading_bar.stop()
        except Exception:
            pass
        self._page_load_pending = False
        self._page_load_start_scheduled = False
        self._connectivity_test_pending = False
        self._connectivity_test_start_scheduled = False
        self._force_dns_action_pending.clear()
        self._scheduled_force_dns_action_request = None
        self._force_dns_action_start_scheduled = False
        self._dns_flush_cache_pending = False
        self._dns_flush_cache_start_scheduled = False
        self._dns_apply_pending.clear()
        self._scheduled_dns_apply_request = None
        self._dns_apply_start_scheduled = False
        self._dns_mutation_pending_order.clear()
        self._page_load_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="dns_page_load_worker",
        )
        self._page_load_runtime.cancel()
        self._connectivity_test_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="dns_connectivity_test_worker",
        )
        self._connectivity_test_runtime.cancel()
        self._force_dns_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="force_dns_action_worker",
        )
        self._force_dns_action_runtime.cancel()
        self._dns_flush_cache_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="dns_flush_cache_worker",
        )
        self._dns_flush_cache_runtime.cancel()
        self._dns_apply_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="dns_apply_worker",
        )
        self._dns_apply_runtime.cancel()
        self._isp_warning_pending = False
        self._isp_warning_start_scheduled = False
        self._isp_warning_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="isp_dns_warning_worker",
        )
        self._isp_warning_runtime.cancel()
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
