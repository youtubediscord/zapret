"""Карточки DNS-провайдера и сетевого адаптера для страницы Network."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
)
import qtawesome as qta

try:
    from qfluentwidgets import (
        CaptionLabel,
        CheckBox,
        IndeterminateProgressBar,
        InfoBar,
        LineEdit,
        MessageBox,
        SettingCardGroup,
        StrongBodyLabel,
    )
    HAS_FLUENT_LABELS = True
except ImportError:
    CheckBox = QCheckBox
    IndeterminateProgressBar = QProgressBar
    LineEdit = QLineEdit
    InfoBar = None
    MessageBox = None  # type: ignore[assignment]
    SettingCardGroup = None
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    HAS_FLUENT_LABELS = False

from ui.compat_widgets import SettingsCard
from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog


class DNSProviderCard(SettingsCard):
    """Компактная карточка DNS-провайдера."""

    selected = pyqtSignal(str, dict)

    @staticmethod
    def indicator_off() -> str:
        tokens = get_theme_tokens()
        return f"""
            background-color: {tokens.toggle_off_bg};
            border: 2px solid {tokens.toggle_off_border};
            border-radius: 8px;
        """

    @staticmethod
    def indicator_on() -> str:
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

        self.indicator = QFrame()
        self.indicator.setFixedSize(16, 16)
        self.indicator.setStyleSheet(self.indicator_off())
        layout.addWidget(self.indicator)

        icon_color = self.data.get('color') or tokens.accent_hex
        icon_label = QLabel()
        self._icon_label = icon_label
        icon_label.setPixmap(qta.icon(
            self.data.get('icon', 'fa5s.server'),
            color=icon_color
        ).pixmap(18, 18))
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)

        if HAS_FLUENT_LABELS:
            name_label = StrongBodyLabel(self.name)
        else:
            name_label = QLabel(self.name)
        self._name_label = name_label
        layout.addWidget(name_label)

        if HAS_FLUENT_LABELS:
            desc_label = CaptionLabel(f"· {self.data.get('desc', '')}")
        else:
            desc_label = QLabel(f"· {self.data.get('desc', '')}")
        self._desc_label = desc_label
        layout.addWidget(desc_label)

        if self.data.get("doh"):
            doh_label = QLabel(tr_catalog(
                "page.network.dns.doh_supported", default="DoH",
            ))
            self._doh_label = doh_label
            doh_label.setToolTip("DNS over HTTPS — зашифрованный DNS")
            layout.addWidget(doh_label)

        layout.addStretch()

        ip_text = self._provider_ip_text()
        if HAS_FLUENT_LABELS:
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
            if self._name_label is not None and not HAS_FLUENT_LABELS:
                self._name_label.setStyleSheet(
                    f"color: {theme_tokens.fg}; font-size: 12px; font-weight: 500;"
                )
        except Exception:
            pass
        try:
            if self._desc_label is not None and not HAS_FLUENT_LABELS:
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
            if self._ip_label is not None and not HAS_FLUENT_LABELS:
                self._ip_label.setStyleSheet(
                    f"color: {theme_tokens.fg_muted}; font-size: 11px; font-family: monospace;"
                )
        except Exception:
            pass

    def set_selected(self, selected: bool):
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
            self.indicator.setStyleSheet(self.indicator_on())
        else:
            self.indicator.setStyleSheet(self.indicator_off())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.name, self.data)
        super().mousePressEvent(event)

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._apply_theme_styles(tokens)
        if self._is_selected:
            self.indicator.setStyleSheet(self.indicator_on())
        else:
            self.indicator.setStyleSheet(self.indicator_off())


class AdapterCard(SettingsCard):
    """Компактная карточка сетевого адаптера."""

    def __init__(self, name: str, dns_info: dict, parent=None):
        super().__init__(parent)
        self.adapter_name = name
        self.dns_info = dns_info
        self.dns_label = None
        self._name_label = None
        self._network_icon_label = None
        self._setup_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_styles)

    def _setup_ui(self):
        tokens = get_theme_tokens()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        self.checkbox = CheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.hide()

        self.check_icon = QLabel()
        self.check_icon.setFixedSize(20, 20)
        self.check_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_check_icon()
        self.check_icon.mousePressEvent = lambda e: self._toggle_checkbox()
        layout.addWidget(self.check_icon)

        self.checkbox.stateChanged.connect(self._update_check_icon)

        icon_label = QLabel()
        self._network_icon_label = icon_label
        icon_label.setPixmap(qta.icon('fa5s.network-wired', color=tokens.accent_hex).pixmap(16, 16))
        layout.addWidget(icon_label)

        if HAS_FLUENT_LABELS:
            name_label = StrongBodyLabel(self.adapter_name)
        else:
            name_label = QLabel(self.adapter_name)
        self._name_label = name_label
        layout.addWidget(name_label)

        layout.addStretch()

        current_dns_v4 = self._normalize_dns_list(self.dns_info.get("ipv4", []))
        current_dns_v6 = self._normalize_dns_list(self.dns_info.get("ipv6", []))
        dns_text = self._format_dns_text(current_dns_v4, current_dns_v6)

        if HAS_FLUENT_LABELS:
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
            if self._name_label is not None and not HAS_FLUENT_LABELS:
                self._name_label.setStyleSheet(
                    f"color: {theme_tokens.fg}; font-size: 12px; font-weight: 500;"
                )
        except Exception:
            pass
        try:
            if self.dns_label is not None and not HAS_FLUENT_LABELS:
                self.dns_label.setStyleSheet(
                    f"color: {theme_tokens.fg_faint}; font-size: 11px; font-family: monospace;"
                )
        except Exception:
            pass
        self._update_check_icon()

    @staticmethod
    def _normalize_dns_list(value) -> list:
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
        if self.dns_label:
            ipv4 = self._normalize_dns_list(dns_v4)
            ipv6 = self._normalize_dns_list(dns_v6 or [])
            dns_text = self._format_dns_text(ipv4, ipv6)
            self.dns_label.setText(dns_text)

    def _toggle_checkbox(self):
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def _update_check_icon(self, state=None):
        _ = state
        tokens = get_theme_tokens()
        if self.checkbox.isChecked():
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-marked', color=tokens.accent_hex).pixmap(18, 18))
        else:
            self.check_icon.setPixmap(qta.icon('mdi.checkbox-blank-outline', color=tokens.fg_faint).pixmap(18, 18))
