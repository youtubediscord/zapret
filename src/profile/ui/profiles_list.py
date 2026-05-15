from __future__ import annotations

from typing import Any, Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from profile.ui.profile_item import ProfileItem
from profile.ui.widgets.profile_group import ProfileGroup
from profile.ui.widgets.profile_type_selector import ProfileTypeSelector
from profile.match_filters import is_voice_match, ports_label_from_match_lines, protocol_label_from_match_lines


class ProfilesList(QWidget):
    profile_selected = pyqtSignal(str)
    profile_move_requested = pyqtSignal(str, str)
    profile_move_to_end_requested = pyqtSignal(str)

    GROUP_NAMES = {
        "youtube": "YouTube",
        "discord": "Discord",
        "telegram": "Telegram",
        "hostlists": "Hostlist",
        "ipsets": "IPset",
        "default": "Прочее",
    }
    GROUP_ORDER = ["youtube", "discord", "telegram", "hostlists", "ipsets", "default"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items_by_key: Dict[str, ProfileItem] = {}
        self._profile_items: Dict[str, Any] = {}
        self._groups: Dict[str, ProfileGroup] = {}
        self._profile_to_group: Dict[str, str] = {}
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._profile_type_selector = ProfileTypeSelector(self)
        self._profile_type_selector.profile_types_changed.connect(self._apply_profile_type_filter)
        layout.addWidget(self._profile_type_selector)

        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch()
        layout.addWidget(self._content)

    def build_profiles(self, items: tuple[Any, ...]) -> None:
        self.clear()
        grouped: dict[str, list[Any]] = {}
        for item in items:
            grouped.setdefault(item.group or "default", []).append(item)

        for group_key in self.GROUP_ORDER:
            rows = grouped.get(group_key) or []
            if not rows:
                continue
            rows.sort(key=lambda item: item.order)
            group = ProfileGroup(group_key, self.GROUP_NAMES.get(group_key, group_key.title()), self)
            self._groups[group_key] = group

            for item in rows:
                widget = self._create_item(item)
                group.add_widget(widget)
                self._items_by_key[item.key] = widget
                self._profile_items[item.key] = item
                self._profile_to_group[item.key] = group_key

            self._content_layout.insertWidget(self._content_layout.count() - 1, group)

    def clear(self) -> None:
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._items_by_key.clear()
        self._profile_items.clear()
        self._groups.clear()
        self._profile_to_group.clear()

    def expand_all(self) -> None:
        for group in self._groups.values():
            group.set_expanded(True)

    def collapse_all(self) -> None:
        for group in self._groups.values():
            group.set_expanded(False)

    def _create_item(self, item: Any) -> ProfileItem:
        ports = ports_label_from_match_lines(item.match_lines)
        description_parts = [part for part in (protocol_label_from_match_lines(item.match_lines), f"порты: {ports}" if ports else "") if part]
        description = " | ".join(description_parts)
        tooltip = _match_summary(item)
        if not item.in_preset:
            tooltip = f"{tooltip}\nПрофиля ещё нет в пресете. Включите его или выберите готовую стратегию."
        elif not item.enabled:
            tooltip = f"{tooltip}\nПрофиль есть в пресете, но сейчас выключен. В файле это записано через --skip."

        widget = ProfileItem(
            item.key,
            item.display_name,
            description,
            None,
            "#60cdff" if item.in_preset else "#888888",
            tooltip,
            item.list_type if item.list_type in {"hostlist", "ipset"} else None,
            self,
        )
        widget.set_drag_enabled(bool(item.in_preset))
        widget.item_activated.connect(self._on_item_clicked)
        widget.item_dropped.connect(self._on_item_dropped)
        widget.set_strategy(item.strategy_id, item.strategy_name)
        widget.set_feedback_state(item.rating, item.favorite)
        return widget

    def _on_item_clicked(self, profile_key: str) -> None:
        self.profile_selected.emit(profile_key)

    def _on_item_dropped(self, source_key: str, destination_key: str) -> None:
        source = self._profile_items.get(source_key)
        destination = self._profile_items.get(destination_key)
        if source is None or destination is None:
            return
        if not source.in_preset or not destination.in_preset:
            return
        if source_key == destination_key:
            return
        self.profile_move_requested.emit(source_key, destination_key)

    def _apply_profile_type_filter(self, active_profile_types: set[str]) -> None:
        if "all" in active_profile_types:
            for widget in self._items_by_key.values():
                widget.setVisible(True)
            for group in self._groups.values():
                group.setVisible(True)
            return

        visible: set[str] = set()
        for key, item in self._profile_items.items():
            protocol = protocol_label_from_match_lines(item.match_lines).upper()
            summary = _match_summary(item)
            text = f"{item.display_name} {summary} {item.group}".lower()
            if "tcp" in active_profile_types and "TCP" in protocol:
                visible.add(key)
            if "udp" in active_profile_types and ("UDP" in protocol or "L7" in protocol):
                visible.add(key)
            if "discord" in active_profile_types and "discord" in text:
                visible.add(key)
            if "voice" in active_profile_types and is_voice_match(item.match_lines):
                visible.add(key)
            if "games" in active_profile_types and "game" in text:
                visible.add(key)

        for key, widget in self._items_by_key.items():
            widget.setVisible(key in visible)

        for group_key, group in self._groups.items():
            group.setVisible(any(
                widget.isVisible()
                for key, widget in self._items_by_key.items()
                if self._profile_to_group.get(key) == group_key
            ))

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileItem.MIME_TYPE):
            event.acceptProposedAction()
            return
        return super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(ProfileItem.MIME_TYPE):
            event.acceptProposedAction()
            return
        return super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        if not event.mimeData().hasFormat(ProfileItem.MIME_TYPE):
            return super().dropEvent(event)
        source_key = bytes(event.mimeData().data(ProfileItem.MIME_TYPE)).decode("utf-8", errors="replace").strip()
        item = self._profile_items.get(source_key)
        if source_key and item is not None and item.in_preset:
            self.profile_move_to_end_requested.emit(source_key)
            event.acceptProposedAction()
            return
        event.ignore()

def _match_summary(item: Any) -> str:
    parts = [part for part in (protocol_label_from_match_lines(item.match_lines), ports_label_from_match_lines(item.match_lines), item.list_type) if part]
    return " • ".join(parts) or "без явных условий"
