"""Список выбора DNS в стиле строк пресетов."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QObject, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
)

from app.ui_texts import tr as tr_catalog
from ui.accessibility import set_control_accessibility, set_state_text
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect


KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 1
KEY_ROLE = int(Qt.ItemDataRole.UserRole) + 2
TITLE_ROLE = int(Qt.ItemDataRole.UserRole) + 3
DESCRIPTION_ROLE = int(Qt.ItemDataRole.UserRole) + 4
IP_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 5
ICON_ROLE = int(Qt.ItemDataRole.UserRole) + 6
ICON_COLOR_ROLE = int(Qt.ItemDataRole.UserRole) + 7
DOH_ROLE = int(Qt.ItemDataRole.UserRole) + 8
SELECTED_ROLE = int(Qt.ItemDataRole.UserRole) + 9
PROVIDER_DATA_ROLE = int(Qt.ItemDataRole.UserRole) + 10


class DnsChoiceHandle(QObject):
    """Лёгкая ручка выбора вместо отдельной карточки-виджета."""

    def __init__(self, view: "DnsChoiceListWidget", item: QListWidgetItem, base_name: str):
        super().__init__(view)
        self.view = view
        self.item = item
        self._accessible_base_name = str(base_name or "")
        self._accessible_name = base_name
        self._accessible_description = ""
        self.setProperty("selected", False)
        self._sync_accessibility()

    def set_selected(self, selected: bool) -> None:
        selected_bool = bool(selected)
        self.setProperty("selected", selected_bool)
        self.view.set_item_selected(self.item, selected_bool)
        self._sync_accessibility()

    def setAccessibleName(self, value: str) -> None:  # noqa: N802
        self._accessible_base_name = str(value or "")
        self._sync_accessibility()

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleDescription(self, value: str) -> None:  # noqa: N802
        self._accessible_description = str(value or "")

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def _sync_accessibility(self) -> None:
        base_name = self._accessible_base_name
        state = "выбран" if bool(self.property("selected")) else "не выбран"
        text = f"{base_name}, {state}"
        self._accessible_name = text
        self.setProperty("screenReaderStateText", text)
        self.item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
        self.view.refresh_item(self.item)


class DnsChoiceListWidget(QListWidget):
    """Один список DNS-выборов вместо набора отдельных карточек."""

    auto_selected = pyqtSignal()
    provider_selected = pyqtSignal(str, dict)
    custom_selected = pyqtSignal()
    custom_provider_context_requested = pyqtSignal(str, dict, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_item: QListWidgetItem | None = None
        self.setObjectName("dnsChoiceList")
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setItemDelegate(DnsChoiceListDelegate(self))
        set_control_accessibility(
            self,
            name="Список DNS-серверов",
            description="Выберите DNS стрелками вверх и вниз, затем нажмите Enter или Пробел.",
        )
        set_state_text(self, "Список DNS-серверов")
        self.currentItemChanged.connect(lambda current, _previous: self._update_current_dns_accessibility(current))
        self.itemClicked.connect(self.activate_item)
        self.itemActivated.connect(self.activate_item)
        self.setStyleSheet(
            """
            QListWidget#dnsChoiceList {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget#dnsChoiceList::item {
                background: transparent;
                border: none;
            }
            """
        )

    def add_section(self, title: str) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(KIND_ROLE, "section")
        item.setData(TITLE_ROLE, str(title or ""))
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.addItem(item)
        self._sync_height()
        return item

    def add_auto_choice(self, title: str, *, on_select=None) -> DnsChoiceHandle:
        item = QListWidgetItem()
        item.setData(KIND_ROLE, "auto")
        item.setData(KEY_ROLE, "auto")
        item.setData(TITLE_ROLE, str(title or "Автоматически (DHCP)"))
        item.setData(ICON_ROLE, "fa5s.sync")
        item.setData(SELECTED_ROLE, False)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, "DNS автоматически (DHCP)")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.addItem(item)
        handle = DnsChoiceHandle(self, item, "DNS автоматически (DHCP)")
        if callable(on_select):
            self.auto_selected.connect(on_select)
        self._sync_height()
        return handle

    def set_custom_choice(self, item_widget) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(KIND_ROLE, "custom")
        item.setData(KEY_ROLE, "custom")
        item.setData(TITLE_ROLE, "Свой DNS")
        item.setData(SELECTED_ROLE, False)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setSizeHint(QSize(0, 40))
        self.addItem(item)
        self.setItemWidget(item, item_widget)
        self._custom_item = item
        self._sync_height()
        return item

    def custom_item(self) -> QListWidgetItem | None:
        return self._custom_item

    def add_provider(self, name: str, data: dict, *, show_ipv6: bool = False) -> DnsChoiceHandle:
        item = QListWidgetItem()
        item.setData(KIND_ROLE, "provider")
        item.setData(KEY_ROLE, str(name or ""))
        item.setData(TITLE_ROLE, str(name or ""))
        item.setData(DESCRIPTION_ROLE, str(data.get("desc", "") or ""))
        item.setData(IP_TEXT_ROLE, _provider_ip_text(data, show_ipv6=show_ipv6))
        item.setData(ICON_ROLE, str(data.get("icon") or "fa5s.server"))
        item.setData(ICON_COLOR_ROLE, str(data.get("color") or ""))
        item.setData(DOH_ROLE, bool(data.get("doh")))
        item.setData(PROVIDER_DATA_ROLE, dict(data or {}))
        item.setData(SELECTED_ROLE, False)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, f"DNS {name}")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.addItem(item)
        handle = DnsChoiceHandle(self, item, f"DNS {name}")
        self._sync_height()
        return handle

    def set_item_selected(self, item: QListWidgetItem, selected: bool) -> None:
        item.setData(SELECTED_ROLE, bool(selected))
        row = self.row(item)
        if row >= 0:
            index = self.model().index(row, 0)
            self.viewport().update(self.visualRect(index))
        self._refresh_custom_widget_selection(item, bool(selected))

    def activate_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        kind = str(item.data(KIND_ROLE) or "")
        if kind == "auto":
            self.auto_selected.emit()
            return
        if kind == "custom":
            self.custom_selected.emit()
            return
        if kind == "provider":
            name = str(item.data(KEY_ROLE) or "")
            data = item.data(PROVIDER_DATA_ROLE)
            self.provider_selected.emit(name, dict(data or {}))

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate_item(self.currentItem())
            event.accept()
            return
        if event.key() == Qt.Key.Key_Menu or (
            event.key() == Qt.Key.Key_F10
            and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            item = self.currentItem()
            if item is not None and self._emit_custom_provider_context(item, self.visualItemRect(item).center()):
                event.accept()
                return
        super().keyPressEvent(event)

    def focusInEvent(self, event):  # noqa: N802
        super().focusInEvent(event)
        if self.currentItem() is None:
            self._focus_first_choice()
        self._update_current_dns_accessibility(self.currentItem())

    def refresh_theme(self) -> None:
        self.viewport().update()

    def refresh_item(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        if row >= 0:
            index = self.model().index(row, 0)
            self.viewport().update(self.visualRect(index))
        if self.currentItem() is item:
            self._update_current_dns_accessibility(item)

    def _emit_custom_provider_context(self, item: QListWidgetItem, pos: QPoint) -> bool:
        if str(item.data(KIND_ROLE) or "") != "provider":
            return False
        name = str(item.data(KEY_ROLE) or "")
        data = item.data(PROVIDER_DATA_ROLE)
        provider_data = dict(data or {})
        if not str(provider_data.get("custom_id") or "").strip():
            return False
        self.custom_provider_context_requested.emit(name, provider_data, self.viewport().mapToGlobal(pos))
        return True

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None:
                self.setCurrentItem(item)
                if self._emit_custom_provider_context(item, event.position().toPoint()):
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def _refresh_custom_widget_selection(self, item: QListWidgetItem, selected: bool) -> None:
        if self._custom_item is None or item is not self._custom_item:
            return
        widget = self.itemWidget(item)
        set_selected = getattr(widget, "set_selected", None)
        if callable(set_selected):
            set_selected(selected)

    def _focus_first_choice(self) -> None:
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                self.setCurrentItem(item)
                return

    def _update_current_dns_accessibility(self, item: QListWidgetItem | None) -> None:
        text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip() if item is not None else ""
        if text:
            set_state_text(
                self,
                f"Список DNS-серверов: {text}. Нажмите Enter или Пробел, чтобы выбрать DNS.",
            )
            return
        set_state_text(self, "Список DNS-серверов")

    def _sync_height(self) -> None:
        total = 2 * self.frameWidth()
        for row in range(self.count()):
            item_height = self.sizeHintForRow(row)
            if item_height <= 0:
                hint = self.item(row).sizeHint()
                item_height = hint.height() if hint.isValid() else 40
            total += max(1, item_height)
        self.setMinimumHeight(total)
        self.setMaximumHeight(total)
        self.updateGeometry()


class DnsChoiceListDelegate(QStyledItemDelegate):
    """Рисует DNS-строки тем же мягким фоном, что и список пресетов."""

    _ROW_HEIGHT = 38
    _SECTION_HEIGHT = 24
    _CUSTOM_HEIGHT = 40
    _ICON_SIZE = 18

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        kind = str(index.data(KIND_ROLE) or "")
        if kind == "section":
            return QSize(0, self._SECTION_HEIGHT)
        if kind == "custom":
            return QSize(0, self._CUSTOM_HEIGHT)
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        kind = str(index.data(KIND_ROLE) or "")
        if kind == "section":
            self._paint_section(painter, option, index)
            return
        if kind == "custom":
            return
        self._paint_choice_row(painter, option, index)

    def _paint_section(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        tokens = get_theme_tokens()
        rect = option.rect.adjusted(20, 6, -12, 0)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        painter.setPen(to_qcolor(tokens.fg_faint, "#8a929d"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), str(index.data(TITLE_ROLE) or ""))
        painter.restore()

    def _paint_choice_row(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        rect = profile_hover_row_rect(option.rect)
        active = bool(index.data(SELECTED_ROLE))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        paint_profile_hover_row(
            painter,
            rect,
            active=active,
            hovered=hovered,
            selected=selected,
        )

        left = rect.left() + (24 if active else 18)
        right = rect.right() - 16
        icon_name = str(index.data(ICON_ROLE) or "fa5s.server")
        icon_color = str(index.data(ICON_COLOR_ROLE) or tokens.fg_faint)
        icon_rect = QRect(left, rect.center().y() - self._ICON_SIZE // 2, self._ICON_SIZE, self._ICON_SIZE)
        pixmap = get_cached_qta_pixmap(icon_name, color=icon_color, size=self._ICON_SIZE)
        if not pixmap.isNull():
            painter.drawPixmap(icon_rect, pixmap)
        left = icon_rect.right() + 12

        metrics = QFontMetrics(painter.font())
        meta_font = QFont(painter.font())
        meta_font.setBold(False)
        meta_metrics = QFontMetrics(meta_font)

        ip_text = str(index.data(IP_TEXT_ROLE) or "")
        ip_rect = QRect()
        if ip_text:
            ip_width = min(meta_metrics.horizontalAdvance(ip_text) + 4, max(80, rect.width() // 3))
            ip_rect = QRect(right - ip_width, rect.top(), ip_width, rect.height())
            right = ip_rect.left() - 12

        doh_rect = QRect()
        if bool(index.data(DOH_ROLE)):
            doh_text = tr_catalog("page.network.dns.doh_supported", default="DoH")
            doh_width = meta_metrics.horizontalAdvance(doh_text) + 16
            doh_rect = QRect(right - doh_width, rect.center().y() - 10, doh_width, 20)
            right = doh_rect.left() - 10

        title = str(index.data(TITLE_ROLE) or "")
        description = str(index.data(DESCRIPTION_ROLE) or "")
        title_width = metrics.horizontalAdvance(title)
        title_rect = QRect(left, rect.top(), max(0, right - left), rect.height())
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        painter.drawText(
            title_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width()),
        )

        if description and title_width + 12 < title_rect.width():
            desc_left = left + title_width + 8
            desc_rect = QRect(desc_left, rect.top(), max(0, right - desc_left), rect.height())
            painter.setFont(meta_font)
            painter.setPen(to_qcolor(tokens.fg_muted, "#b7bec8"))
            painter.drawText(
                desc_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(f"· {description}", Qt.TextElideMode.ElideRight, desc_rect.width()),
            )

        if doh_rect.isValid():
            painter.setFont(meta_font)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(to_qcolor(tokens.accent_soft_bg, tokens.accent_hex))
            painter.drawRoundedRect(doh_rect, 6, 6)
            painter.setPen(to_qcolor(tokens.accent_hex, "#5caee8"))
            painter.drawText(doh_rect, int(Qt.AlignmentFlag.AlignCenter), tr_catalog("page.network.dns.doh_supported", default="DoH"))

        if ip_rect.isValid():
            painter.setFont(meta_font)
            painter.setPen(to_qcolor(tokens.fg_muted, "#b7bec8"))
            painter.drawText(
                ip_rect,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(ip_text, Qt.TextElideMode.ElideRight, ip_rect.width()),
            )

        painter.restore()


def _normalize_ip_list(value) -> list[str]:
    if isinstance(value, str):
        return [x.strip() for x in value.replace(",", " ").split() if x.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _provider_ip_text(data: dict, *, show_ipv6: bool) -> str:
    ipv4 = _normalize_ip_list(data.get("ipv4", []))
    primary_v4 = ipv4[0] if ipv4 else ""
    if not show_ipv6:
        return primary_v4 or "-"
    ipv6 = _normalize_ip_list(data.get("ipv6", []))
    primary_v6 = ipv6[0] if ipv6 else ""
    if primary_v4 and primary_v6:
        return f"v4 {primary_v4} | v6 {primary_v6}"
    if primary_v4:
        return primary_v4
    if primary_v6:
        return primary_v6
    return "-"


__all__ = [
    "DnsChoiceHandle",
    "DnsChoiceListDelegate",
    "DnsChoiceListWidget",
]
