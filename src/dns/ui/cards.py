"""Карточки DNS-провайдера и сетевого адаптера для страницы Network."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

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

from ui.fluent_widgets import SettingsCard, set_tooltip
from ui.accessibility import set_control_accessibility, set_state_text
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshBinding
from app.ui_texts import tr as tr_catalog


class DNSProviderCard(QWidget):
    """Лёгкая карточка DNS-провайдера."""

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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(40)
        self._setup_ui()
        self._refresh_accessibility()
        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme_refresh)

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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(10)

        icon_color = self.data.get('color') or tokens.accent_hex
        icon_label = QLabel()
        self._icon_label = icon_label
        icon_label.setPixmap(
            get_cached_qta_pixmap(
                self.data.get('icon', 'fa5s.server'),
                color=icon_color,
                size=18,
            )
        )
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)

        name_label = StrongBodyLabel(self.name)
        self._name_label = name_label
        layout.addWidget(name_label)

        desc_label = CaptionLabel(f"· {self.data.get('desc', '')}")
        self._desc_label = desc_label
        layout.addWidget(desc_label)

        if self.data.get("doh"):
            doh_label = QLabel(tr_catalog(
                "page.network.dns.doh_supported", default="DoH",
            ))
            self._doh_label = doh_label
            set_tooltip(doh_label, "DNS over HTTPS — зашифрованный DNS")
            layout.addWidget(doh_label)

        layout.addStretch()

        ip_text = self._provider_ip_text()
        ip_label = CaptionLabel(ip_text)
        self._ip_label = ip_label
        layout.addWidget(ip_label)

        self._apply_theme_styles(tokens)

    def _apply_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        self._apply_card_style(theme_tokens)
        try:
            if self._icon_label is not None:
                icon_color = self.data.get('color') or theme_tokens.accent_hex
                self._icon_label.setPixmap(
                    get_cached_qta_pixmap(
                        self.data.get('icon', 'fa5s.server'),
                        color=icon_color,
                        size=18,
                    )
                )
        except Exception:
            pass
        try:
            pass
        except Exception:
            pass
        try:
            pass
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
            pass
        except Exception:
            pass

    def _apply_card_style(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        r, g, b = theme_tokens.accent_rgb
        if self._is_selected:
            bg = f"rgba({r}, {g}, {b}, 0.28)"
            bg_hover = f"rgba({r}, {g}, {b}, 0.34)"
            border = f"rgba({r}, {g}, {b}, 0.40)"
        else:
            bg = theme_tokens.surface_bg
            bg_hover = theme_tokens.surface_bg_hover
            border = theme_tokens.surface_border
        self.setStyleSheet(
            f"""
            QWidget#dnsCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QWidget#dnsCard:hover {{
                background-color: {bg_hover};
                border: 1px solid {theme_tokens.surface_border_hover if not self._is_selected else border};
            }}
            """
        )

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.setProperty("selected", bool(selected))
        self._refresh_accessibility()
        self._apply_card_style()
        style = self.style()
        if style is not None:
            try:
                style.unpolish(self)
                style.polish(self)
            except Exception:
                pass
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.name, self.data)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self.name, self.data)
            event.accept()
            return
        super().keyPressEvent(event)

    def _refresh_accessibility(self) -> None:
        selected_text = "выбран" if self._is_selected else "не выбран"
        description = str(self.data.get("desc", "") or "").strip()
        ip_text = self._provider_ip_text()
        parts = [f"DNS {self.name}", selected_text]
        if description:
            parts.append(description)
        if ip_text and ip_text != "-":
            parts.append(ip_text)
        state_text = ", ".join(parts)
        set_state_text(self, state_text)
        set_control_accessibility(
            self,
            name=state_text,
            description="Нажмите Enter или пробел, чтобы выбрать этого DNS-провайдера.",
        )

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._apply_theme_styles(tokens)


class AdapterCard(SettingsCard):
    """Компактная карточка сетевого адаптера."""

    def __init__(self, name: str, dns_info: dict, parent=None):
        super().__init__(parent)
        self.adapter_name = name
        self.dns_info = dns_info
        self.dns_label = None
        self._name_label = None
        self._network_icon_label = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._setup_ui()
        self._refresh_accessibility()
        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme_styles)

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
        icon_label.setPixmap(get_cached_qta_pixmap('fa5s.network-wired', color=tokens.accent_hex, size=16))
        layout.addWidget(icon_label)

        name_label = StrongBodyLabel(self.adapter_name)
        self._name_label = name_label
        layout.addWidget(name_label)

        layout.addStretch()

        current_dns_v4 = self._normalize_dns_list(self.dns_info.get("ipv4", []))
        current_dns_v6 = self._normalize_dns_list(self.dns_info.get("ipv6", []))
        dns_text = self._format_dns_text(current_dns_v4, current_dns_v6)

        self.dns_label = CaptionLabel(dns_text)
        layout.addWidget(self.dns_label)

        self.add_layout(layout)
        self._apply_theme_styles(tokens)

    def _apply_theme_styles(self, tokens=None) -> None:
        theme_tokens = tokens or get_theme_tokens()
        try:
            if getattr(self, '_network_icon_label', None) is not None:
                self._network_icon_label.setPixmap(
                    get_cached_qta_pixmap('fa5s.network-wired', color=theme_tokens.accent_hex, size=16)
                )
        except Exception:
            pass
        try:
            pass
        except Exception:
            pass
        try:
            pass
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
            self._refresh_accessibility()

    def _toggle_checkbox(self):
        self.checkbox.setChecked(not self.checkbox.isChecked())
        self._refresh_accessibility()

    def _update_check_icon(self, state=None):
        _ = state
        tokens = get_theme_tokens()
        if self.checkbox.isChecked():
            self.check_icon.setPixmap(get_cached_qta_pixmap('mdi.checkbox-marked', color=tokens.accent_hex, size=18))
        else:
            self.check_icon.setPixmap(get_cached_qta_pixmap('mdi.checkbox-blank-outline', color=tokens.fg_faint, size=18))
        self._refresh_accessibility()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._toggle_checkbox()
            event.accept()
            return
        super().keyPressEvent(event)

    def _refresh_accessibility(self) -> None:
        checked_text = "выбран" if self.checkbox.isChecked() else "не выбран"
        dns_text = ""
        try:
            dns_text = str(self.dns_label.text() or "").strip() if self.dns_label is not None else ""
        except Exception:
            dns_text = ""
        parts = [f"Сетевой адаптер {self.adapter_name}", checked_text]
        if dns_text:
            parts.append(f"DNS {dns_text}")
        state_text = ", ".join(parts)
        set_state_text(self, state_text)
        set_control_accessibility(
            self,
            name=state_text,
            description="Нажмите Enter или пробел, чтобы включить или исключить этот адаптер.",
        )
