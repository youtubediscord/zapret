"""Список сетевых адаптеров в стиле компактных строк DNS."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QObject, QRect, QSize, Qt, pyqtSignal
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

from ui.accessibility import set_control_accessibility, set_state_text
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect


NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 31
DNS_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 32
CHECKED_ROLE = int(Qt.ItemDataRole.UserRole) + 33


class AdapterChoiceCheck(QObject):
    """Минимальная замена чекбокса для старого контракта страницы."""

    stateChanged = pyqtSignal(int)

    def __init__(self, checked: bool = True, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        checked_bool = bool(checked)
        if self._checked == checked_bool:
            return
        self._checked = checked_bool
        self.stateChanged.emit(2 if checked_bool else 0)


class _TextValue:
    def __init__(self, value: str = ""):
        self._value = str(value or "")

    def text(self) -> str:
        return self._value

    def setText(self, value: str) -> None:  # noqa: N802
        self._value = str(value or "")


class AdapterChoiceHandle(QObject):
    """Лёгкая ручка строки адаптера вместо отдельной карточки-виджета."""

    def __init__(self, view: "AdapterChoiceListWidget", item: QListWidgetItem, name: str, dns_info: dict):
        super().__init__(view)
        self.view = view
        self.item = item
        self.adapter_name = str(name or "")
        self.dns_info = dict(dns_info or {})
        self.checkbox = AdapterChoiceCheck(True, self)
        self.dns_label = _TextValue(_format_dns_text_from_info(self.dns_info))
        self.checkbox.stateChanged.connect(self._on_checked_changed)
        self._sync_row()
        self._refresh_accessibility()

    def toggle(self) -> None:
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def update_dns_display(self, dns_v4, dns_v6=None) -> None:
        dns_text = _format_dns_text(_normalize_dns_list(dns_v4), _normalize_dns_list(dns_v6 or []))
        self.dns_label.setText(dns_text)
        self._refresh_accessibility()
        self._sync_row()

    def accessibleName(self) -> str:  # noqa: N802
        return str(self.property("accessibleName") or "")

    def accessibleDescription(self) -> str:  # noqa: N802
        return str(self.property("accessibleDescription") or "")

    def _on_checked_changed(self, _state: int) -> None:
        self._refresh_accessibility()
        self._sync_row()

    def _sync_row(self) -> None:
        self.item.setData(CHECKED_ROLE, self.checkbox.isChecked())
        self.item.setData(DNS_TEXT_ROLE, self.dns_label.text())
        self.view.refresh_item(self.item)

    def _refresh_accessibility(self) -> None:
        checked_text = "выбран" if self.checkbox.isChecked() else "не выбран"
        dns_text = self.dns_label.text().strip()
        parts = [f"Сетевой адаптер {self.adapter_name}", checked_text]
        if dns_text:
            parts.append(f"DNS {dns_text}")
        state_text = ", ".join(parts)
        self.setProperty("accessibleName", state_text)
        set_state_text(self, state_text)
        set_control_accessibility(
            self,
            name=state_text,
            description="Нажмите Enter или пробел, чтобы включить или исключить этот адаптер.",
        )
        self.item.setData(Qt.ItemDataRole.AccessibleTextRole, state_text)


class AdapterChoiceListWidget(QListWidget):
    """Компактный список сетевых адаптеров без отдельных карточек-виджетов."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("adapterChoiceList")
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setItemDelegate(AdapterChoiceListDelegate(self))
        set_control_accessibility(
            self,
            name="Список сетевых адаптеров",
            description="Выберите адаптер стрелками вверх и вниз, затем нажмите Enter или Пробел.",
        )
        set_state_text(self, "Список сетевых адаптеров")
        self.currentItemChanged.connect(lambda current, _previous: self._update_current_adapter_accessibility(current))
        self.itemClicked.connect(self.activate_item)
        self.itemActivated.connect(self.activate_item)
        self.setStyleSheet(
            """
            QListWidget#adapterChoiceList {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget#adapterChoiceList::item {
                background: transparent;
                border: none;
            }
            """
        )

    def add_adapter(self, name: str, dns_info: dict) -> AdapterChoiceHandle:
        item = QListWidgetItem()
        item.setData(NAME_ROLE, str(name or ""))
        item.setData(DNS_TEXT_ROLE, _format_dns_text_from_info(dns_info))
        item.setData(CHECKED_ROLE, True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.addItem(item)
        handle = AdapterChoiceHandle(self, item, name, dns_info)
        self._sync_height()
        return handle

    def activate_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        handle = self._handle_for_item(item)
        if handle is not None:
            handle.toggle()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate_item(self.currentItem())
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):  # noqa: N802
        super().focusInEvent(event)
        if self.currentItem() is None:
            self._focus_first_adapter()
        self._update_current_adapter_accessibility(self.currentItem())

    def refresh_item(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        if row >= 0:
            index = self.model().index(row, 0)
            self.viewport().update(self.visualRect(index))
        self._sync_height()
        if self.currentItem() is item:
            self._update_current_adapter_accessibility(item)

    def _handle_for_item(self, item: QListWidgetItem) -> AdapterChoiceHandle | None:
        for child in self.children():
            if isinstance(child, AdapterChoiceHandle) and child.item is item:
                return child
        return None

    def _focus_first_adapter(self) -> None:
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                self.setCurrentItem(item)
                return

    def _update_current_adapter_accessibility(self, item: QListWidgetItem | None) -> None:
        text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip() if item is not None else ""
        if text:
            set_state_text(
                self,
                f"Список сетевых адаптеров: {text}. Нажмите Enter или Пробел, чтобы включить или исключить этот адаптер.",
            )
            return
        set_state_text(self, "Список сетевых адаптеров")

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


class AdapterChoiceListDelegate(QStyledItemDelegate):
    """Рисует адаптеры теми же мягкими строками, что и DNS."""

    _ROW_HEIGHT = 38
    _ICON_SIZE = 18

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        _ = option, index
        return QSize(0, self._ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        rect = profile_hover_row_rect(option.rect)
        checked = bool(index.data(CHECKED_ROLE))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected) or bool(
            option.state & QStyle.StateFlag.State_HasFocus
        )
        paint_profile_hover_row(
            painter,
            rect,
            active=False,
            hovered=hovered,
            selected=selected,
        )

        left = rect.left() + (24 if checked else 18)
        right = rect.right() - 16
        check_icon = "mdi.checkbox-marked" if checked else "mdi.checkbox-blank-outline"
        check_color = tokens.accent_hex if checked else tokens.fg_faint
        check_rect = QRect(left, rect.center().y() - self._ICON_SIZE // 2, self._ICON_SIZE, self._ICON_SIZE)
        pixmap = get_cached_qta_pixmap(check_icon, color=check_color, size=self._ICON_SIZE)
        if not pixmap.isNull():
            painter.drawPixmap(check_rect, pixmap)
        left = check_rect.right() + 12

        metrics = QFontMetrics(painter.font())
        meta_font = QFont(painter.font())
        meta_font.setBold(False)
        meta_metrics = QFontMetrics(meta_font)

        dns_text = str(index.data(DNS_TEXT_ROLE) or "")
        dns_rect = QRect()
        if dns_text:
            dns_width = min(meta_metrics.horizontalAdvance(dns_text) + 4, max(92, rect.width() // 3))
            dns_rect = QRect(right - dns_width, rect.top(), dns_width, rect.height())
            right = dns_rect.left() - 12

        name = str(index.data(NAME_ROLE) or "")
        name_rect = QRect(left, rect.top(), max(0, right - left), rect.height())
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        painter.drawText(
            name_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width()),
        )

        if dns_rect.isValid():
            painter.setFont(meta_font)
            painter.setPen(to_qcolor(tokens.fg_muted, "#b7bec8"))
            painter.drawText(
                dns_rect,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                meta_metrics.elidedText(dns_text, Qt.TextElideMode.ElideRight, dns_rect.width()),
            )

        painter.restore()


def _normalize_dns_list(value) -> list[str]:
    if isinstance(value, str):
        return [x.strip() for x in value.replace(",", " ").split() if x.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.extend([x.strip() for x in item.replace(",", " ").split() if x.strip()])
            else:
                result.append(str(item))
        return result
    return []


def _format_dns_pair(dns_list: list[str]) -> str:
    if not dns_list:
        return ""
    primary = dns_list[0]
    secondary = dns_list[1] if len(dns_list) > 1 else None
    if secondary:
        return f"{primary}, {secondary}"
    return primary


def _format_dns_text(ipv4_list: list[str], ipv6_list: list[str]) -> str:
    v4 = _format_dns_pair(ipv4_list)
    v6 = _format_dns_pair(ipv6_list)
    if v4 and v6:
        return f"v4 {v4} | v6 {v6}"
    if v4:
        return f"v4 {v4}"
    if v6:
        return f"v6 {v6}"
    return "DHCP"


def _format_dns_text_from_info(dns_info: dict) -> str:
    return _format_dns_text(
        _normalize_dns_list((dns_info or {}).get("ipv4", [])),
        _normalize_dns_list((dns_info or {}).get("ipv6", [])),
    )


__all__ = [
    "AdapterChoiceCheck",
    "AdapterChoiceHandle",
    "AdapterChoiceListDelegate",
    "AdapterChoiceListWidget",
]
