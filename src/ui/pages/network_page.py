"""Страница сетевых настроек - DNS, hosts, proxy"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QRadioButton, QButtonGroup,
    QLineEdit, QCheckBox, QProgressBar, QPushButton,
)
import qtawesome as qta

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

from .base_page import BasePage
from ui.widgets.win11_controls import Win11ToggleRow
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    QuickActionsBar,
    ResetActionButton,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from log import log
from dns import DNS_PROVIDERS
from dns.network_page_controller import NetworkPageController

if TYPE_CHECKING:
    from main import LupiDPIApp


class DNSProviderCard(SettingsCard):
    """Компактная карточка DNS провайдера"""

    selected = pyqtSignal(str, dict)  # name, data

    @staticmethod
    def _indicator_off() -> str:
        tokens = get_theme_tokens()
        return f"""
            background-color: {tokens.toggle_off_bg};
            border: 2px solid {tokens.toggle_off_border};
            border-radius: 8px;
        """

    @staticmethod
    def _indicator_on() -> str:
        tokens = get_theme_tokens()
        return f"""
            background-color: {tokens.accent_hex};
            border: 2px solid {tokens.accent_hex};
            border-radius: 8px;
        """

    def __init__(
        self,
        name: str,
        data: dict,
        is_current: bool = False,
        show_ipv6: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.name = name
        self.data = data
        self.is_current = is_current
        self.show_ipv6 = bool(show_ipv6)
        self._is_selected = False
        self._icon_label = None
        self._name_label = None
        self._desc_label = None
        self._doh_label = None
        self._ip_label = None
        self.setObjectName("dnsCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_refresh)

    @staticmethod
    def _normalize_ip_list(value) -> list[str]:
        if isinstance(value, str):
            return [x.strip() for x in value.replace(',', ' ').split() if x.strip()]
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                item_s = str(item).strip()
                if item_s:
                    out.append(item_s)
            return out
        return []

    def _provider_ip_text(self) -> str:
        ipv4 = self._normalize_ip_list(self.data.get('ipv4', []))
        primary_v4 = ipv4[0] if ipv4 else ""

        if not self.show_ipv6:
            return primary_v4 or "-"

        ipv6 = self._normalize_ip_list(self.data.get('ipv6', []))
        primary_v6 = ipv6[0] if ipv6 else ""

        if primary_v4 and primary_v6:
            return f"v4 {primary_v4} | v6 {primary_v6}"
        if primary_v4:
            return primary_v4
        if primary_v6:
            return primary_v6
        return "-"

    def _setup_ui(self):
        tokens = get_theme_tokens()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        # Индикатор выбора
        self.indicator = QFrame()
        self.indicator.setFixedSize(16, 16)
        self.indicator.setStyleSheet(self._indicator_off())
        layout.addWidget(self.indicator)

        # Иконка провайдера
        icon_color = self.data.get('color') or tokens.accent_hex
        icon_label = QLabel()
        self._icon_label = icon_label
        icon_label.setPixmap(qta.icon(
            self.data.get('icon', 'fa5s.server'),
            color=icon_color
        ).pixmap(18, 18))
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)

        # Название
        if _HAS_FLUENT_LABELS:
            name_label = StrongBodyLabel(self.name)
        else:
            name_label = QLabel(self.name)
        self._name_label = name_label
        layout.addWidget(name_label)

        # Описание
        if _HAS_FLUENT_LABELS:
            desc_label = CaptionLabel(f"· {self.data.get('desc', '')}")
        else:
            desc_label = QLabel(f"· {self.data.get('desc', '')}")
        self._desc_label = desc_label
        layout.addWidget(desc_label)

        # DoH бейдж
        if self.data.get("doh"):
            doh_label = QLabel(tr_catalog(
                "page.network.dns.doh_supported", default="DoH",
            ))
            self._doh_label = doh_label
            doh_label.setToolTip("DNS over HTTPS — зашифрованный DNS")
            layout.addWidget(doh_label)

        layout.addStretch()

        # IP адрес
        ip_text = self._provider_ip_text()
        if _HAS_FLUENT_LABELS:
            ip_label = CaptionLabel(ip_text)
        else:
            ip_label = QLabel(ip_text)
        self._ip_label = ip_label
        layout.addWidget(ip_label)

        self.add_layout(layout)
        self._apply_theme_styles(tokens)

    def _apply_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            if self._icon_label is not None:
                icon_color = self.data.get('color') or theme_tokens.accent_hex
                self._icon_label.setPixmap(
                    qta.icon(self.data.get('icon', 'fa5s.server'), color=icon_color).pixmap(18, 18)
                )
        except Exception:
            pass
        try:
            if self._name_label is not None and not _HAS_FLUENT_LABELS:
                self._name_label.setStyleSheet(
                    f"color: {theme_tokens.fg}; font-size: 12px; font-weight: 500;"
                )
        except Exception:
            pass
        try:
            if self._desc_label is not None and not _HAS_FLUENT_LABELS:
                self._desc_label.setStyleSheet(
                    f"color: {theme_tokens.fg_faint}; font-size: 11px;"
                )
        except Exception:
            pass
        try:
            if self._doh_label is not None:
                self._doh_label.setStyleSheet(
                    f"""
                    color: {theme_tokens.accent_hex};
                    background-color: {theme_tokens.accent_soft_bg};
                    border-radius: 6px;
                    padding: 1px 6px;
                    font-size: 9px;
                    font-weight: 600;
                    """
                )
        except Exception:
            pass
        try:
            if self._ip_label is not None and not _HAS_FLUENT_LABELS:
                self._ip_label.setStyleSheet(
                    f"color: {theme_tokens.fg_muted}; font-size: 11px; font-family: monospace;"
                )
        except Exception:
            pass

    def set_selected(self, selected: bool):
        """Устанавливает визуальное состояние выбора"""
        self._is_selected = selected
        self.setProperty("selected", bool(selected))
        style = self.style()
        if style is not None:
            try:
                style.unpolish(self)
                style.polish(self)
            except Exception:
                pass
        self.update()

        if selected:
            self.indicator.setStyleSheet(self._indicator_on())
        else:
            self.indicator.setStyleSheet(self._indicator_off())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.name, self.data)
        super().mousePressEvent(event)

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._apply_theme_styles(tokens)
        if self._is_selected:
            self.indicator.setStyleSheet(self._indicator_on())
        else:
            self.indicator.setStyleSheet(self._indicator_off())


class AdapterCard(SettingsCard):
    """Компактная карточка сетевого адаптера"""

    def __init__(self, name: str, dns_info: dict, parent=None):
        super().__init__(parent)
        self.adapter_name = name
        self.dns_info = dns_info
        self.dns_label = None  # Сохраняем ссылку для обновления
        self._name_label = None
        self._setup_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_styles)
    
    def _setup_ui(self):
        tokens = get_theme_tokens()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        # Кастомный чекбокс через иконку
        self.checkbox = CheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.hide()  # Скрываем стандартный чекбокс

        # Иконка-чекбокс
        self.check_icon = QLabel()
        self.check_icon.setFixedSize(20, 20)
        self.check_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_check_icon()
        self.check_icon.mousePressEvent = lambda e: self._toggle_checkbox()
        layout.addWidget(self.check_icon)

        # Связываем изменение чекбокса с обновлением иконки
        self.checkbox.stateChanged.connect(self._update_check_icon)

        # Иконка
        icon_label = QLabel()
        self._network_icon_label = icon_label
        icon_label.setPixmap(qta.icon('fa5s.network-wired', color=tokens.accent_hex).pixmap(16, 16))
        layout.addWidget(icon_label)

        # Название
        if _HAS_FLUENT_LABELS:
            name_label = StrongBodyLabel(self.adapter_name)
        else:
            name_label = QLabel(self.adapter_name)
        self._name_label = name_label
        layout.addWidget(name_label)

        layout.addStretch()

        # Текущий DNS
        current_dns_v4 = self._normalize_dns_list(self.dns_info.get("ipv4", []))
        current_dns_v6 = self._normalize_dns_list(self.dns_info.get("ipv6", []))
        dns_text = self._format_dns_text(current_dns_v4, current_dns_v6)

        if _HAS_FLUENT_LABELS:
            self.dns_label = CaptionLabel(dns_text)
        else:
            self.dns_label = QLabel(dns_text)
        layout.addWidget(self.dns_label)

        self.add_layout(layout)
        self._apply_theme_styles(tokens)

    def _apply_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            if getattr(self, '_network_icon_label', None) is not None:
                self._network_icon_label.setPixmap(
                    qta.icon('fa5s.network-wired', color=theme_tokens.accent_hex).pixmap(16, 16)
                )
        except Exception:
            pass
        try:
            if self._name_label is not None and not _HAS_FLUENT_LABELS:
                self._name_label.setStyleSheet(
                    f"color: {theme_tokens.fg}; font-size: 12px; font-weight: 500;"
                )
        except Exception:
            pass
        try:
            if self.dns_label is not None and not _HAS_FLUENT_LABELS:
                self.dns_label.setStyleSheet(
                    f"color: {theme_tokens.fg_faint}; font-size: 11px; font-family: monospace;"
                )
        except Exception:
            pass
        self._update_check_icon()

    @staticmethod
    def _normalize_dns_list(value) -> list:
        """Нормализует DNS в список адресов"""
        if isinstance(value, str):
            return [x.strip() for x in value.replace(',', ' ').split() if x.strip()]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    result.extend([x.strip() for x in item.replace(',', ' ').split() if x.strip()])
                else:
                    result.append(str(item))
            return result
        return []

    @staticmethod
    def _format_dns_pair(dns_list: list[str]) -> str:
        if not dns_list:
            return ""
        primary = dns_list[0]
        secondary = dns_list[1] if len(dns_list) > 1 else None
        if secondary:
            return f"{primary}, {secondary}"
        return primary

    @classmethod
    def _format_dns_text(cls, ipv4_list: list[str], ipv6_list: list[str]) -> str:
        v4 = cls._format_dns_pair(ipv4_list)
        v6 = cls._format_dns_pair(ipv6_list)

        if v4 and v6:
            return f"v4 {v4} | v6 {v6}"
        if v4:
            return f"v4 {v4}"
        if v6:
            return f"v6 {v6}"
        return "DHCP"

    def update_dns_display(self, dns_v4, dns_v6=None):
        """Обновляет отображение текущего DNS"""
        if self.dns_label:
            ipv4 = self._normalize_dns_list(dns_v4)
            ipv6 = self._normalize_dns_list(dns_v6 or [])
            dns_text = self._format_dns_text(ipv4, ipv6)
            self.dns_label.setText(dns_text)

    def _toggle_checkbox(self):
        """Переключает состояние чекбокса"""
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def _update_check_icon(self, state=None):
        """Обновляет иконку чекбокса"""
        tokens = get_theme_tokens()
        if self.checkbox.isChecked():
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-marked', color=tokens.accent_hex).pixmap(18, 18))
        else:
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-blank-outline', color=tokens.fg_faint).pixmap(18, 18))


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
        
        self._controller = NetworkPageController()
        
        self._adapters = []
        self._dns_info = {}
        self._is_loading = True
        self._selected_provider = None
        self._force_dns_active = False
        self._ipv6_available = False
        self._test_in_progress = False
        self._force_dns_status_enabled = False
        self._force_dns_status_details_key: str | None = None
        self._force_dns_status_details_kwargs: dict = {}
        self._force_dns_status_details_fallback = ""
        self._runtime_initialized = False
        
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

    def _set_reset_button_texts(
        self,
        button,
        text_key: str,
        text_default: str,
        confirm_key: str,
        confirm_default: str,
    ) -> None:
        try:
            button._default_text = self._tr(text_key, text_default)
            button._confirm_text = self._tr(confirm_key, confirm_default)
            button.setText(button._default_text)
        except Exception:
            pass

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
        plan = NetworkPageController.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.should_start_initial_load:
            return
        self._runtime_initialized = True
        QTimer.singleShot(plan.load_delay_ms, self._start_loading)

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
            self._set_reset_button_texts(
                self.force_dns_reset_dhcp_btn,
                "page.network.force_dns.reset.button",
                "Сбросить DNS на DHCP",
                "page.network.force_dns.reset.confirm",
                "Отключить Force DNS и сбросить DNS на DHCP для всех адаптеров?",
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
        tokens = get_theme_tokens()

        # ═══════════════════════════════════════════════════════════════
        # ПРИНУДИТЕЛЬНЫЙ DNS
        # ═══════════════════════════════════════════════════════════════
        self._build_force_dns_card()

        self.add_spacing(12)

        # ═══════════════════════════════════════════════════════════════
        # DNS СЕРВЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.network.section.dns_servers")

        # Индикатор загрузки
        self.loading_card = SettingsCard()
        loading_layout = QVBoxLayout()
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if _HAS_FLUENT_LABELS:
            self.loading_label = BodyLabel(self._tr("page.network.loading", "⏳ Загрузка..."))
        else:
            self.loading_label = QLabel(self._tr("page.network.loading", "⏳ Загрузка..."))
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)

        self.loading_bar = IndeterminateProgressBar(self)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setMaximumWidth(150)
        if _HAS_FLUENT_LABELS:
            self.loading_bar.start()
        else:
            self.loading_bar.setRange(0, 0)
            self.loading_bar.setTextVisible(False)
        loading_layout.addWidget(self.loading_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        self.loading_card.add_layout(loading_layout)
        self.add_widget(self.loading_card)

        # Контейнер для DNS карточек
        self.dns_cards_container = QWidget()
        self.dns_cards_layout = QVBoxLayout(self.dns_cards_container)
        self.dns_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.dns_cards_layout.setSpacing(4)
        self.dns_cards_container.hide()
        self.add_widget(self.dns_cards_container)

        self.add_spacing(6)

        # Пользовательский DNS
        self.custom_card = SettingsCard()
        self.custom_card.setObjectName("dnsCard")
        self.custom_card.setProperty("selected", False)
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(10, 6, 12, 6)
        custom_layout.setSpacing(8)

        # Индикатор
        self.custom_indicator = QFrame()
        self.custom_indicator.setFixedSize(16, 16)
        self.custom_indicator.setStyleSheet(DNSProviderCard._indicator_off())
        custom_layout.addWidget(self.custom_indicator)

        if _HAS_FLUENT_LABELS:
            self.custom_label = BodyLabel(self._tr("page.network.custom.label", "Свой:"))
        else:
            self.custom_label = QLabel(self._tr("page.network.custom.label", "Свой:"))
        custom_layout.addWidget(self.custom_label)

        self.custom_primary = LineEdit()
        self.custom_primary.setPlaceholderText("8.8.8.8")
        self.custom_primary.setFixedWidth(110)
        self.custom_primary.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_primary)

        self.custom_secondary = LineEdit()
        self.custom_secondary.setPlaceholderText("208.67.222.222")
        self.custom_secondary.setFixedWidth(110)
        self.custom_secondary.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_secondary)

        # Разделитель между IPv4 и IPv6
        ipv6_label_text = "IPv6:"
        if _HAS_FLUENT_LABELS:
            self.ipv6_label = BodyLabel(ipv6_label_text)
        else:
            self.ipv6_label = QLabel(ipv6_label_text)
            self.ipv6_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 12px; margin-left: 8px;")
        custom_layout.addWidget(self.ipv6_label)

        self.custom_primary_v6 = LineEdit()
        self.custom_primary_v6.setPlaceholderText("2001:4860:4860::8888")
        self.custom_primary_v6.setFixedWidth(180)
        self.custom_primary_v6.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_primary_v6)

        self.custom_secondary_v6 = LineEdit()
        self.custom_secondary_v6.setPlaceholderText("2620:119:35::35")
        self.custom_secondary_v6.setFixedWidth(180)
        self.custom_secondary_v6.returnPressed.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_secondary_v6)

        self.custom_apply_btn = ActionButton(self._tr("page.network.custom.apply", "OK"), "fa5s.check")
        self.custom_apply_btn.setFixedSize(70, 26)
        self.custom_apply_btn.clicked.connect(self._apply_custom_dns_quick)
        custom_layout.addWidget(self.custom_apply_btn)

        # IPv6 connectivity status indicator
        self.ipv6_status_icon = QLabel()
        self.ipv6_status_icon.setFixedSize(16, 16)
        self.ipv6_status_icon.setToolTip(self._tr(
            "page.network.ipv6.status.tooltip",
            "Индикатор доступности IPv6"
        ))
        custom_layout.addSpacing(8)
        custom_layout.addWidget(self.ipv6_status_icon)

        self.ipv6_status_label = CaptionLabel("") if _HAS_FLUENT_LABELS else QLabel("")
        self.ipv6_status_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 10px;")
        self.ipv6_status_label.setToolTip(self._tr(
            "page.network.ipv6.status.tooltip",
            "Показывает, доступен ли IPv6 от вашего провайдера"
        ))
        custom_layout.addWidget(self.ipv6_status_label)

        custom_layout.addStretch()

        self.custom_card.add_layout(custom_layout)
        self.custom_card.hide()
        self.add_widget(self.custom_card)

        self.add_spacing(12)

        # ═══════════════════════════════════════════════════════════════
        # СЕТЕВЫЕ АДАПТЕРЫ
        # ═══════════════════════════════════════════════════════════════
        self.add_section_title(text_key="page.network.section.adapters")

        # Контейнер для адаптеров
        self.adapters_container = QWidget()
        self.adapters_layout = QVBoxLayout(self.adapters_container)
        self.adapters_layout.setContentsMargins(0, 0, 0, 0)
        self.adapters_layout.setSpacing(4)
        self.adapters_container.hide()
        self.add_widget(self.adapters_container)

        self.add_spacing(12)

        # ═══════════════════════════════════════════════════════════════
        # ДИАГНОСТИКА
        # ═══════════════════════════════════════════════════════════════
        if SettingCardGroup is not None and _HAS_FLUENT_LABELS:
            self._tools_section_label = None
            tools_card = SettingCardGroup(
                self._tr("page.network.section.tools", "Диагностика"),
                self.content,
            )
            self._tools_card = tools_card
            self._tools_actions_bar = QuickActionsBar(self.content)

            self.test_btn = ActionButton(self._tr("page.network.button.test", "Тест соединения"), "fa5s.wifi")
            self.test_btn.clicked.connect(self._test_connection)
            set_tooltip(
                self.test_btn,
                self._tr(
                    "page.network.tools.test.description",
                    "Проверить доступность DNS и популярных сайтов из этой системы.",
                ),
            )

            self.dns_flush_btn = ActionButton(
                self._tr("page.network.button.flush_dns_cache", "Сбросить DNS кэш"),
                "fa5s.eraser",
            )
            self.dns_flush_btn.clicked.connect(self._confirm_flush_dns_cache)
            set_tooltip(
                self.dns_flush_btn,
                self._tr(
                    "page.network.tools.flush_dns.description",
                    "Очистить локальный кэш DNS Windows, если ответы или домены застряли в старом состоянии.",
                ),
            )

            self._tools_actions_bar.add_buttons([self.test_btn, self.dns_flush_btn])
            insert_widget_into_setting_card_group(tools_card, 1, self._tools_actions_bar)
        else:
            self._tools_section_label = self.add_section_title(text_key="page.network.section.tools")
            tools_card = SettingsCard()
            self._tools_card = tools_card
            tools_layout = QHBoxLayout()
            tools_layout.setContentsMargins(10, 8, 12, 8)
            tools_layout.setSpacing(8)
            
            self.test_btn = ActionButton(self._tr("page.network.button.test", "Тест соединения"), "fa5s.wifi")
            self.test_btn.setFixedHeight(28)
            self.test_btn.clicked.connect(self._test_connection)
            set_tooltip(
                self.test_btn,
                self._tr(
                    "page.network.tools.test.description",
                    "Проверить доступность DNS и популярных сайтов из этой системы.",
                ),
            )
            tools_layout.addWidget(self.test_btn)
            
            self.dns_flush_btn = ActionButton(
                self._tr("page.network.button.flush_dns_cache", "Сбросить DNS кэш"),
                "fa5s.eraser",
            )
            self.dns_flush_btn.setFixedHeight(28)
            self.dns_flush_btn.clicked.connect(self._confirm_flush_dns_cache)
            set_tooltip(
                self.dns_flush_btn,
                self._tr(
                    "page.network.tools.flush_dns.description",
                    "Очистить локальный кэш DNS Windows, если ответы или домены застряли в старом состоянии.",
                ),
            )
            tools_layout.addWidget(self.dns_flush_btn)
            
            tools_layout.addStretch()
            
            tools_card.add_layout(tools_layout)
        self.add_widget(tools_card)

        # Подключаем сигналы
        self.adapters_loaded.connect(self._on_adapters_loaded)
        self.dns_info_loaded.connect(self._on_dns_info_loaded)

    def _start_loading(self):
        """Запускает асинхронную загрузку данных"""
        import threading

        thread = threading.Thread(target=self._load_data, daemon=True)
        thread.start()

    @staticmethod
    def _detect_ipv6_availability() -> bool:
        try:
            from dns.dns_force import DNSForceManager
            return bool(DNSForceManager.check_ipv6_connectivity())
        except Exception as e:
            log(f"Ошибка проверки IPv6 у провайдера: {e}", "DEBUG")
            return False

    def _update_ipv6_status_indicator(self):
        """Обновляет индикатор статуса IPv6"""
        if not hasattr(self, 'ipv6_status_icon') or not hasattr(self, 'ipv6_status_label'):
            return

        tokens = get_theme_tokens()

        if self._ipv6_available:
            # IPv6 доступен - зелёная иконка
            self.ipv6_status_icon.setPixmap(
                qta.icon('fa5s.check-circle', color='#4caf50').pixmap(16, 16)
            )
            self.ipv6_status_icon.setToolTip(self._tr(
                "page.network.ipv6.status.available",
                "IPv6 доступен"
            ))
            self.ipv6_status_label.setText(self._tr(
                "page.network.ipv6.status.available.label",
                "IPv6"
            ))
        else:
            # IPv6 недоступен - серая иконка
            self.ipv6_status_icon.setPixmap(
                qta.icon('fa5s.times-circle', color=tokens.fg_faint).pixmap(16, 16)
            )
            self.ipv6_status_icon.setToolTip(self._tr(
                "page.network.ipv6.status.unavailable",
                "IPv6 недоступен от провайдера"
            ))
            self.ipv6_status_label.setText("")

    def _load_data(self):
        """Загружает данные в фоне"""
        try:
            state = NetworkPageController.load_page_data()
            self._ipv6_available = state.ipv6_available
            self._update_ipv6_status_indicator()
            self._force_dns_active = state.force_dns_active
            self._adapters = state.adapters
            self._dns_info = state.dns_info
            self.adapters_loaded.emit(state.adapters)
            self.dns_info_loaded.emit(state.dns_info)
        except Exception as exc:
            log(f"Ошибка загрузки DNS данных: {exc}", "ERROR")

    def _on_adapters_loaded(self, adapters):
        self._adapters = adapters
        if self._dns_info and not self._ui_built:
            self._build_dynamic_ui()

    def _on_dns_info_loaded(self, dns_info):
        self._dns_info = dns_info
        if self._adapters and not self._ui_built:
            self._build_dynamic_ui()

    def _build_dynamic_ui(self):
        """Строит UI после загрузки данных"""
        if self._ui_built:
            return
        self._ui_built = True
        tokens = get_theme_tokens()

        from dns.dns_core import _normalize_alias

        self._is_loading = False
        self.loading_card.hide()
        self.dns_cards_container.show()
        self.custom_card.show()
        self.adapters_container.show()
        
        # Добавляем "Автоматически (DHCP)"
        auto_card = SettingsCard()
        auto_card.setObjectName("dnsCard")
        auto_card.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_card.setProperty("selected", False)
        auto_layout = QHBoxLayout()
        auto_layout.setContentsMargins(10, 6, 12, 6)
        auto_layout.setSpacing(10)

        self.auto_indicator = QFrame()
        self.auto_indicator.setFixedSize(16, 16)
        self.auto_indicator.setStyleSheet(DNSProviderCard._indicator_off())
        auto_layout.addWidget(self.auto_indicator)

        auto_icon = QLabel()
        self._auto_icon_label = auto_icon
        auto_icon.setPixmap(qta.icon('fa5s.sync', color=tokens.fg_faint).pixmap(16, 16))
        auto_layout.addWidget(auto_icon)

        if _HAS_FLUENT_LABELS:
            self.auto_label = StrongBodyLabel(self._tr("page.network.dns.auto", "Автоматически (DHCP)"))
        else:
            self.auto_label = QLabel(self._tr("page.network.dns.auto", "Автоматически (DHCP)"))
        auto_layout.addWidget(self.auto_label)

        auto_layout.addStretch()

        auto_card.add_layout(auto_layout)
        auto_card.mousePressEvent = lambda e: self._select_auto_dns()
        self.dns_cards_layout.addWidget(auto_card)
        self.auto_card = auto_card

        # Добавляем провайдеров
        for category, providers in DNS_PROVIDERS.items():
            if _HAS_FLUENT_LABELS:
                cat_label = CaptionLabel(category)
            else:
                cat_label = QLabel(category)
                self._dns_category_labels.append(cat_label)
            self.dns_cards_layout.addWidget(cat_label)

            for name, data in providers.items():
                card = DNSProviderCard(name, data, False, show_ipv6=self._ipv6_available)
                card.selected.connect(self._on_dns_selected)
                self.dns_cards[name] = card
                self.dns_cards_layout.addWidget(card)
        
        # Адаптеры
        for name, desc in self._adapters:
            clean = _normalize_alias(name)
            dns_data = self._dns_info.get(clean, {"ipv4": [], "ipv6": []})

            card = AdapterCard(name, dns_data)
            card.checkbox.stateChanged.connect(self._sync_selected_dns_card)
            self.adapter_cards.append(card)
            self.adapters_layout.addWidget(card)

        self._sync_selected_dns_card()

        # Проверяем ISP DNS и показываем предупреждение
        self._check_and_show_isp_dns_warning()
        self._apply_inline_theme_styles(tokens)

    def _is_current_dns(self, provider_ips: list, current_ips: list) -> bool:
        return (len(provider_ips) > 0 and
                len(current_ips) > 0 and
                provider_ips[0] == current_ips[0])

    def _get_selected_adapter_dns(self) -> tuple[list[str], list[str]] | None:
        from dns.dns_core import _normalize_alias

        selected = self._get_selected_adapters()
        if not selected:
            return None

        clean = _normalize_alias(selected[0])
        dns_data = self._dns_info.get(clean, {"ipv4": [], "ipv6": []})
        current_dns_v4 = AdapterCard._normalize_dns_list(dns_data.get("ipv4", []))
        current_dns_v6 = AdapterCard._normalize_dns_list(dns_data.get("ipv6", []))
        return current_dns_v4, current_dns_v6

    def _sync_selected_dns_card(self, *_):
        if not self.adapter_cards:
            return

        selection_plan = NetworkPageController.build_dns_selection_plan(
            selected_adapters=self._get_selected_adapters(),
            dns_info=self._dns_info,
            providers=DNS_PROVIDERS,
        )
        if selection_plan.kind == "none":
            return

        if selection_plan.kind == "auto":
            self._clear_selection()
            if hasattr(self, 'auto_indicator'):
                self.auto_indicator.setStyleSheet(DNSProviderCard._indicator_on())
            if hasattr(self, 'auto_card'):
                self._set_dns_card_selected(self.auto_card, True)
            self._selected_provider = None
            return

        self._clear_selection()
        if selection_plan.kind == "provider" and selection_plan.selected_provider in self.dns_cards:
            self.dns_cards[selection_plan.selected_provider].set_selected(True)
            self._selected_provider = selection_plan.selected_provider
            return

        if hasattr(self, 'custom_indicator'):
            self.custom_indicator.setStyleSheet(DNSProviderCard._indicator_on())
        if hasattr(self, 'custom_card'):
            self._set_dns_card_selected(self.custom_card, True)

        if hasattr(self, 'custom_primary'):
            self.custom_primary.setText(selection_plan.custom_primary)
        if hasattr(self, 'custom_secondary'):
            self.custom_secondary.setText(selection_plan.custom_secondary)

        selected_dns = self._get_selected_adapter_dns()
        if selected_dns:
            _, current_dns_v6 = selected_dns
        else:
            current_dns_v6 = []

        if hasattr(self, 'custom_primary_v6'):
            self.custom_primary_v6.setText(current_dns_v6[0] if current_dns_v6 else "")
        if hasattr(self, 'custom_secondary_v6'):
            self.custom_secondary_v6.setText(current_dns_v6[1] if len(current_dns_v6) > 1 else "")

        self._selected_provider = None

    def _clear_selection(self):
        """Сбрасывает все выделения"""
        for card in self.dns_cards.values():
            card.set_selected(False)

        if hasattr(self, 'auto_indicator'):
            self.auto_indicator.setStyleSheet(DNSProviderCard._indicator_off())
            if hasattr(self, 'auto_card'):
                self._set_dns_card_selected(self.auto_card, False)

        self.custom_indicator.setStyleSheet(DNSProviderCard._indicator_off())
        self._set_dns_card_selected(self.custom_card, False)

    def _set_dns_card_selected(self, card: QWidget | None, selected: bool) -> None:
        if card is None:
            return
        try:
            card.setProperty("selected", bool(selected))
            style = card.style()
            if style is not None:
                style.unpolish(card)
                style.polish(card)
            card.update()
        except Exception:
            pass

    def _on_dns_selected(self, name: str, data: dict):
        """Обработчик выбора DNS - сразу применяем"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return

        self._clear_selection()
        self.dns_cards[name].set_selected(True)
        self._selected_provider = name

        # Применяем
        self._apply_provider_dns_quick(name, data)

    def _select_auto_dns(self):
        """Выбор автоматического DNS"""
        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return

        self._clear_selection()
        self.auto_indicator.setStyleSheet(DNSProviderCard._indicator_on())
        self._set_dns_card_selected(self.auto_card, True)
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
        from utils import IPValidator

        # Если Force DNS активен - подсвечиваем карточку Force DNS
        if self._force_dns_active:
            self._highlight_force_dns()
            return

        primary_v4 = self.custom_primary.text().strip()
        if not primary_v4:
            return

        # Валидация IPv4
        if not IPValidator.is_valid_ipv4(primary_v4):
            log(f"DNS: Неверный формат IPv4: {primary_v4}", "WARNING")
            return

        secondary_v4 = self.custom_secondary.text().strip() or None
        if secondary_v4 and not IPValidator.is_valid_ipv4(secondary_v4):
            log(f"DNS: Неверный формат IPv4 (вторичный): {secondary_v4}", "WARNING")
            return

        self._clear_selection()
        self.custom_indicator.setStyleSheet(DNSProviderCard._indicator_on())
        self._set_dns_card_selected(self.custom_card, True)

        adapters = self._get_selected_adapters()
        if not adapters:
            return

        success = 0
        for adapter in adapters:
            # Применяем IPv4
            ok_v4, _ = self._controller.set_custom_dns(adapter, primary_v4, secondary_v4, "IPv4")

            # Применяем IPv6 (если введены адреса)
            ok_v6 = True
            primary_v6 = self.custom_primary_v6.text().strip()
            if primary_v6:
                # Валидация IPv6
                if not IPValidator.is_valid_ipv6(primary_v6):
                    log(f"DNS: Неверный формат IPv6: {primary_v6}", "WARNING")
                    ok_v6 = False
                else:
                    secondary_v6 = self.custom_secondary_v6.text().strip() or None
                    if secondary_v6 and not IPValidator.is_valid_ipv6(secondary_v6):
                        log(f"DNS: Неверный формат IPv6 (вторичный): {secondary_v6}", "WARNING")
                        ok_v6 = False
                    else:
                        ok_v6, _ = self._controller.set_custom_dns(
                            adapter, primary_v6, secondary_v6, "IPv6"
                        )

            if ok_v4 and ok_v6:
                success += 1

        self._controller.flush_dns_cache()

        plan = NetworkPageController.build_custom_dns_apply_result_plan(
            primary=primary_v4,
            adapter_count=len(adapters),
            success_count=success,
        )
        if plan.log_message:
            log(plan.log_message, plan.log_level or "INFO")
        if plan.should_refresh:
            self._refresh_adapters_dns()
    
    def _refresh_adapters_dns(self):
        """Обновляет отображение DNS у всех адаптеров"""
        try:
            if not self.adapter_cards:
                log("Нет карточек адаптеров для обновления", "DEBUG")
                return

            adapter_names = [card.adapter_name for card in self.adapter_cards]
            dns_info = NetworkPageController.refresh_dns_info(adapter_names)
            self._dns_info = dns_info
            refresh_plan = NetworkPageController.build_adapter_dns_refresh_plan(adapter_names, dns_info)
            entries_by_name = {entry.adapter_name: entry for entry in refresh_plan.entries}

            for card in self.adapter_cards:
                entry = entries_by_name.get(card.adapter_name)
                if entry is None:
                    continue
                card.dns_info = entry.adapter_data
                card.update_dns_display(entry.ipv4, entry.ipv6)

            self._sync_selected_dns_card()
            
            if hasattr(refresh_plan, 'log_message') and refresh_plan.log_message:
                log(refresh_plan.log_message, refresh_plan.log_level)
            else:
                log("DNS информация адаптеров обновлена", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка обновления DNS адаптеров: {e}", "WARNING")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def _build_force_dns_card(self):
        """Строит виджет принудительного DNS в стиле DPI страницы"""
        tokens = get_theme_tokens()
        self._force_dns_active = NetworkPageController.get_force_dns_status()
        
        # Секция DNS
        self.add_section_title(text_key="page.network.section.force_dns")
        
        # Карточка / fluent-group
        if SettingCardGroup is not None and _HAS_FLUENT_LABELS:
            self.force_dns_card = SettingCardGroup(
                self._tr(
                    "page.network.force_dns.card.title",
                    "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
                ),
                self.content,
            )
            dns_layout = None
        else:
            self.force_dns_card = SettingsCard(
                self._tr(
                    "page.network.force_dns.card.title",
                    "Принудительно прописывает Google DNS + OpenDNS для обхода блокировок",
                )
            )
            dns_layout = QVBoxLayout()
            dns_layout.setSpacing(8)

        # Toggle row в стиле Win11
        self.force_dns_toggle = Win11ToggleRow(
            "fa5s.shield-alt",
            self._tr("page.network.force_dns.toggle.title", "Принудительный DNS"),
            self._tr(
                "page.network.force_dns.toggle.description",
                "Устанавливает Google DNS + OpenDNS на активные адаптеры",
            ),
            tokens.accent_hex
        )
        self.force_dns_toggle.setChecked(self._force_dns_active)
        self.force_dns_toggle.toggled.connect(self._on_force_dns_toggled)
        if hasattr(self.force_dns_card, "addSettingCard"):
            self.force_dns_card.addSettingCard(self.force_dns_toggle)
        else:
            dns_layout.addWidget(self.force_dns_toggle)
        
        # Статус
        if _HAS_FLUENT_LABELS:
            self.force_dns_status_label = CaptionLabel("")
        else:
            self.force_dns_status_label = QLabel("")
        if dns_layout is not None:
            dns_layout.addWidget(self.force_dns_status_label)
        else:
            try:
                insert_widget_into_setting_card_group(self.force_dns_card, 1, self.force_dns_status_label)
            except Exception:
                pass

        self.force_dns_reset_dhcp_btn = ResetActionButton(
            self._tr("page.network.force_dns.reset.button", "Сбросить DNS на DHCP"),
            confirm_text=self._tr(
                "page.network.force_dns.reset.confirm",
                "Отключить Force DNS и сбросить DNS на DHCP для всех адаптеров?",
            ),
        )
        self.force_dns_reset_dhcp_btn.setFixedHeight(30)
        self.force_dns_reset_dhcp_btn.reset_confirmed.connect(self._reset_dns_to_dhcp)
        self.force_dns_reset_dhcp_btn.setToolTip(
            self._tr(
                "page.network.force_dns.reset.description",
                "Отключить Force DNS и вернуть получение DNS через DHCP для всех адаптеров.",
            )
        )

        if dns_layout is None:
            self._force_dns_reset_row = QWidget(self.force_dns_card)
            reset_row_layout = QHBoxLayout(self._force_dns_reset_row)
            reset_row_layout.setContentsMargins(0, 4, 0, 0)
            reset_row_layout.setSpacing(8)
            reset_row_layout.addWidget(self.force_dns_reset_dhcp_btn, 0, Qt.AlignmentFlag.AlignLeft)
            reset_row_layout.addStretch()
            insert_widget_into_setting_card_group(self.force_dns_card, 2, self._force_dns_reset_row)
            enable_setting_card_group_auto_height(self.force_dns_card)
        else:
            dns_layout.addWidget(self.force_dns_reset_dhcp_btn, alignment=Qt.AlignmentFlag.AlignLeft)
            self.force_dns_card.add_layout(dns_layout)
        self.add_widget(self.force_dns_card)

        # Обновляем статус
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
                    qta.icon('fa5s.sync', color=theme_tokens.fg_faint).pixmap(16, 16)
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
        try:
            current_state = NetworkPageController.get_force_dns_status()
            if enabled == current_state:
                self._update_force_dns_status(enabled)
                self._update_dns_selection_state()
                return

            if enabled:
                success, ok_count, total, message = NetworkPageController.enable_force_dns(include_disconnected=False)
                log(message, "DNS")
                plan = NetworkPageController.build_force_dns_toggle_plan(
                    requested_enabled=True,
                    success=success,
                    ok_count=ok_count,
                    total=total,
                )
            else:
                success, message = NetworkPageController.disable_force_dns(reset_to_auto=False)
                log(message, "DNS")
                plan = NetworkPageController.build_force_dns_toggle_plan(
                    requested_enabled=False,
                    success=success,
                )
            
            self._force_dns_active = plan.force_dns_active
            self._set_force_dns_toggle(plan.final_checked)
            self._update_force_dns_status(
                plan.force_dns_active,
                plan.details_key,
                details_kwargs=plan.details_kwargs,
                details_fallback=plan.details_fallback,
            )
            self._update_dns_selection_state()
            self._refresh_adapters_dns()

        except Exception as e:
            log(f"Ошибка переключения Force DNS: {e}", "ERROR")
            plan = NetworkPageController.build_force_dns_toggle_error_plan(requested_enabled=enabled)
            self._force_dns_active = plan.force_dns_active
            self._set_force_dns_toggle(plan.final_checked)
            self._update_force_dns_status(
                plan.force_dns_active,
                plan.details_key,
            )

    def _set_force_dns_toggle(self, checked: bool):
        """Устанавливает состояние переключателя без триггера сигналов"""
        try:
            self.force_dns_toggle.setChecked(checked, block_signals=True)
            return
        except TypeError:
            pass
        self.force_dns_toggle.toggle.blockSignals(True)
        self.force_dns_toggle.setChecked(checked)
        self.force_dns_toggle.toggle.blockSignals(False)

    def _update_force_dns_status(
        self,
        enabled: bool,
        details_key: str | None = None,
        *,
        details_kwargs: dict | None = None,
        details_fallback: str = "",
    ):
        """Обновляет текст статуса для принудительного DNS"""
        if not hasattr(self, "force_dns_status_label"):
            return

        self._force_dns_status_enabled = bool(enabled)
        self._force_dns_status_details_key = details_key
        self._force_dns_status_details_kwargs = dict(details_kwargs or {})
        self._force_dns_status_details_fallback = details_fallback or ""

        plan = NetworkPageController.build_force_dns_status_plan(
            enabled=enabled,
            details_key=details_key,
            details_kwargs=details_kwargs,
            details_fallback=details_fallback,
            language=self._ui_language,
        )
        self.force_dns_status_label.setText(plan.text)
    
    def _update_dns_selection_state(self):
        """Обновляет состояние выбора DNS в зависимости от Force DNS"""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        is_blocked = self._force_dns_active

        # Применяем эффект прозрачности к DNS карточкам (делает серыми и иконки тоже)
        if hasattr(self, 'dns_cards_container'):
            if is_blocked:
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(0.35)
                self.dns_cards_container.setGraphicsEffect(effect)
            else:
                self.dns_cards_container.setGraphicsEffect(None)

        if hasattr(self, 'custom_card'):
            if is_blocked:
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(0.35)
                self.custom_card.setGraphicsEffect(effect)
            else:
                self.custom_card.setGraphicsEffect(None)

    def _highlight_force_dns(self):
        """Подсвечивает карточку принудительного DNS при попытке изменить DNS"""
        if not hasattr(self, 'force_dns_card'):
            return

        from PyQt6.QtCore import QTimer
        tokens = get_theme_tokens()

        # Применяем яркий стиль
        highlight_style = f"""
            SettingsCard {{
                background-color: {tokens.accent_soft_bg_hover};
                border: 2px solid {tokens.accent_hex};
                border-radius: 10px;
            }}
        """
        original_style = self.force_dns_card.styleSheet()
        self.force_dns_card.setStyleSheet(highlight_style)

        # Возвращаем оригинальный стиль через 700мс
        QTimer.singleShot(700, lambda: self.force_dns_card.setStyleSheet(original_style))

    def _flush_dns_cache(self):
        """Сбрасывает DNS кэш"""
        success, message = NetworkPageController.flush_dns_cache()
        plan = NetworkPageController.build_flush_dns_cache_result_plan(
            success=success,
            message=message,
            language=self._ui_language,
        )
        if plan.infobar_level == "warning" and InfoBar:
            InfoBar.warning(
                title=plan.title,
                content=plan.content,
                parent=self.window(),
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
        try:
            success, message = NetworkPageController.disable_force_dns(reset_to_auto=True)
            log(message, "DNS")

            result_plan = NetworkPageController.build_reset_dhcp_result_plan(
                success=success,
                message=message,
                force_dns_active=NetworkPageController.get_force_dns_status(),
                language=self._ui_language,
            )

            self._force_dns_active = result_plan.force_dns_active
            self._set_force_dns_toggle(self._force_dns_active)

            if result_plan.should_select_auto:
                self._clear_selection()
                if hasattr(self, 'auto_indicator'):
                    self.auto_indicator.setStyleSheet(DNSProviderCard._indicator_on())
                if hasattr(self, 'auto_card'):
                    self._set_dns_card_selected(self.auto_card, True)
                self._selected_provider = None

            self._update_force_dns_status(
                result_plan.force_dns_active,
                result_plan.status_details_key,
            )

            self._update_dns_selection_state()
            self._refresh_adapters_dns()

            if InfoBar:
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

        except Exception as e:
            log(f"Ошибка сброса DNS на DHCP: {e}", "ERROR")
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("page.network.error.title", "Ошибка"),
                    content=self._tr(
                        "page.network.error.reset_dhcp_failed",
                        "Не удалось сбросить DNS: {error}",
                    ).format(error=e),
                    parent=self.window(),
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
        self._test_in_progress = True
        self._update_test_action_text()

        # Подключаем сигнал (однократно)
        try:
            self.test_completed.disconnect()
        except TypeError:
            pass
        self.test_completed.connect(self._on_test_complete)
        test_plan = NetworkPageController.build_connectivity_test_plan(language=self._ui_language)

        def thread_func():
            results = NetworkPageController.run_connectivity_test(test_plan.test_hosts)
            self.test_completed.emit(results)

        import threading

        thread = threading.Thread(target=thread_func, daemon=True)
        thread.start()

    def _on_test_complete(self, results: list):
        """Вызывается из главного потока после завершения теста"""
        self._test_in_progress = False
        self._update_test_action_text()
        plan = NetworkPageController.build_connectivity_test_result_plan(results, language=self._ui_language)
        if InfoBar:
            if plan.infobar_level == "success":
                InfoBar.success(
                    title=plan.title,
                    content=plan.content,
                    parent=self.window(),
                )
            else:
                InfoBar.warning(
                    title=plan.title,
                    content=plan.content,
                    parent=self.window(),
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
        try:
            plan = NetworkPageController.build_isp_dns_warning_plan(
                self._adapters,
                self._dns_info,
                force_dns_active=self._force_dns_active,
                language=self._ui_language,
            )
            if not plan.should_show:
                return

            # Строим inline-баннер предупреждения
            tokens = get_theme_tokens()

            self._isp_warning = QFrame()

            warning_layout = QVBoxLayout(self._isp_warning)
            warning_layout.setContentsMargins(14, 10, 14, 10)
            warning_layout.setSpacing(6)

            # Заголовок с иконкой
            title_row = QHBoxLayout()
            title_row.setSpacing(8)

            icon_label = QLabel()
            self._isp_warning_icon = icon_label
            icon_label.setFixedSize(18, 18)
            title_row.addWidget(icon_label)

            title_text = QLabel(plan.title)
            self._isp_warning_title = title_text
            title_row.addWidget(title_text)
            title_row.addStretch()
            warning_layout.addLayout(title_row)

            # Текст описания
            content_label = QLabel(plan.content)
            content_label.setWordWrap(True)
            self._isp_warning_content = content_label
            warning_layout.addWidget(content_label)

            # Кнопки действий
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            accept_btn = QPushButton(plan.action_text)
            self._isp_warning_accept_btn = accept_btn
            accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            accept_btn.clicked.connect(self._accept_isp_dns_recommendation)
            btn_row.addWidget(accept_btn)

            dismiss_btn = QPushButton(plan.dismiss_text)
            self._isp_warning_dismiss_btn = dismiss_btn
            dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dismiss_btn.clicked.connect(self._dismiss_isp_dns_warning)
            btn_row.addWidget(dismiss_btn)

            btn_row.addStretch()
            warning_layout.addLayout(btn_row)

            NetworkPageController.mark_isp_dns_warning_shown()

            # Вставляем баннер перед секцией DNS-серверов (после Force DNS)
            idx = self.vBoxLayout.indexOf(self.dns_cards_container)
            if idx >= 0:
                self.vBoxLayout.insertWidget(idx, self._isp_warning)
            else:
                self.add_widget(self._isp_warning)

            self._render_isp_warning_styles(tokens)

        except Exception as e:
            log(f"Ошибка показа ISP DNS предупреждения: {e}", "DEBUG")

    def _render_isp_warning_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        warning = getattr(self, "_isp_warning", None)
        if warning is None:
            return

        warning.setStyleSheet(
            """
            QFrame {
                background-color: rgba(255, 152, 0, 0.12);
                border: 1px solid rgba(255, 152, 0, 0.35);
                border-radius: 8px;
            }
            """
        )
        if self._isp_warning_icon is not None:
            self._isp_warning_icon.setPixmap(qta.icon("fa5s.exclamation-triangle", color="#ff9800").pixmap(16, 16))
            self._isp_warning_icon.setStyleSheet("background: transparent; border: none;")
        if self._isp_warning_title is not None:
            self._isp_warning_title.setStyleSheet(
                f"""
                color: {theme_tokens.fg};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
                """
            )
        if self._isp_warning_content is not None:
            self._isp_warning_content.setStyleSheet(
                f"""
                color: {theme_tokens.fg_muted};
                font-size: 12px;
                background: transparent;
                border: none;
                """
            )
        if self._isp_warning_accept_btn is not None:
            self._isp_warning_accept_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {theme_tokens.accent_hex};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 14px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {theme_tokens.accent_hover_hex};
                }}
                """
            )
        if self._isp_warning_dismiss_btn is not None:
            self._isp_warning_dismiss_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {theme_tokens.fg_muted};
                    border: 1px solid {theme_tokens.toggle_off_border};
                    border-radius: 6px;
                    padding: 5px 14px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme_tokens.surface_bg_hover};
                }}
                """
            )

    def _accept_isp_dns_recommendation(self):
        """Включает Force DNS по рекомендации из баннера"""
        try:
            plan = NetworkPageController.build_accept_isp_dns_warning_plan()
            if plan.hide_warning and hasattr(self, "_isp_warning"):
                self._isp_warning.hide()
                self._isp_warning.deleteLater()

            if plan.enable_force_dns:
                self._set_force_dns_toggle(True)
                self._on_force_dns_toggled(True)
        except Exception as e:
            log(f"Ошибка применения рекомендуемого DNS: {e}", "ERROR")

    def _dismiss_isp_dns_warning(self):
        """Скрывает баннер (реестр уже записан при показе)"""
        plan = NetworkPageController.build_dismiss_isp_dns_warning_plan()
        if plan.hide_warning and hasattr(self, "_isp_warning"):
            self._isp_warning.hide()
            self._isp_warning.deleteLater()