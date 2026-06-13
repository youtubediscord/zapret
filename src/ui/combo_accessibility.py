from __future__ import annotations

from types import MethodType

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction
from qfluentwidgets import MenuAnimationType

from ui.accessibility import set_accessible_description, set_control_accessibility, set_state_text


def _clean_text(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _combo_accessible_name(combo) -> str:
    try:
        return _clean_text(combo.accessibleName())
    except Exception:
        return _clean_text(getattr(combo, "accessible_name", ""))


def _combo_accessible_description(combo) -> str:
    try:
        return _clean_text(combo.accessibleDescription())
    except Exception:
        return _clean_text(getattr(combo, "accessible_description", ""))


def _combo_description(combo) -> str:
    keyboard_hint = "Откройте список и выберите пункт стрелками, затем нажмите Enter."
    current = _combo_accessible_description(combo)
    if not current:
        return keyboard_hint
    if "Enter" in current:
        return current
    return f"{current} {keyboard_hint}"


def _combo_count(combo) -> int:
    try:
        return int(combo.count())
    except Exception:
        try:
            return len(getattr(combo, "items", []) or [])
        except Exception:
            return 0


def _combo_item_text(combo, index: int) -> str:
    try:
        return _clean_text(combo.itemText(index))
    except Exception:
        try:
            return _clean_text((getattr(combo, "items", []) or [])[index].text)
        except Exception:
            return ""


def set_combo_item_accessible_text(combo, index: int, text: object) -> None:
    if combo is None:
        return
    value = _clean_text(text)
    if not value:
        return
    try:
        items = getattr(combo, "items", []) or []
        if 0 <= int(index) < len(items):
            setattr(items[int(index)], "accessibleText", value)
    except Exception:
        pass


def _sync_combo_items_accessibility(combo) -> None:
    config = getattr(combo, "_accessible_combo_items_config", None)
    if combo is None or not isinstance(config, dict):
        return
    name = _clean_text(config.get("name"))
    if not name:
        return
    selected_word = _clean_text(config.get("selected_word")) or "выбран"
    unselected_word = _clean_text(config.get("unselected_word")) or "не выбран"
    clean_label = config.get("clean_label")
    try:
        current_index = int(combo.currentIndex())
    except Exception:
        current_index = -1
    current_label = ""
    for index in range(_combo_count(combo)):
        label = _combo_item_text(combo, index)
        if clean_label is not None:
            try:
                label = _clean_text(clean_label(label))
            except Exception:
                label = _clean_text(label)
        if not label:
            continue
        state = selected_word if index == current_index else unselected_word
        if index == current_index:
            current_label = label
        set_combo_item_accessible_text(combo, index, f"{name}: {label}, {state}")
    combo_text = f"{name}, выбрано: {current_label}" if current_label else name
    previous_combo_text = _clean_text(getattr(combo, "_accessible_combo_widget_text", ""))
    existing_name = _combo_accessible_name(combo)
    if not existing_name or existing_name == previous_combo_text:
        set_control_accessibility(combo, name=combo_text, description=_combo_description(combo))
        set_state_text(combo, combo_text)
        try:
            setattr(combo, "_accessible_combo_widget_text", combo_text)
        except Exception:
            pass
    else:
        set_accessible_description(combo, _combo_description(combo))


def _ensure_combo_items_accessibility_signal(combo) -> None:
    if combo is None or bool(getattr(combo, "_accessible_combo_items_signal_connected", False)):
        return
    try:
        combo.currentIndexChanged.connect(lambda _index=None: _sync_combo_items_accessibility(combo))
        setattr(combo, "_accessible_combo_items_signal_connected", True)
    except Exception:
        pass


def install_accessible_combo_menu(combo) -> None:
    if combo is None or bool(getattr(combo, "_accessible_combo_menu_installed", False)):
        return

    def _create_accessible_combo_menu(self):
        menu = self._createComboMenu()
        for index, item in enumerate(getattr(self, "items", []) or []):
            action = QAction(item.icon, item.text, triggered=lambda _checked=False, row=index: self._onItemClicked(row))
            action.setEnabled(item.isEnabled)
            menu.addAction(action)
            accessible_text = _clean_text(getattr(item, "accessibleText", ""))
            menu_item = action.property("item")
            if accessible_text and menu_item is not None:
                menu_item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
                menu_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
        return menu

    def _show_combo_menu(self) -> None:
        if not getattr(self, "items", None):
            return

        menu = self._create_accessible_combo_menu()
        if menu.view.width() < self.width():
            menu.view.setMinimumWidth(self.width())
            menu.adjustSize()

        menu.setMaxVisibleItems(self.maxVisibleItems())
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.closedSignal.connect(self._onDropMenuClosed)
        self.dropMenu = menu

        if self.currentIndex() >= 0 and self.items:
            menu.setDefaultAction(menu.actions()[self.currentIndex()])

        x = -menu.width() // 2 + menu.layout().contentsMargins().left() + self.width() // 2
        down_pos = self.mapToGlobal(QPoint(x, self.height()))
        down_height = menu.view.heightForAnimation(down_pos, MenuAnimationType.DROP_DOWN)

        up_pos = self.mapToGlobal(QPoint(x, 0))
        up_height = menu.view.heightForAnimation(up_pos, MenuAnimationType.PULL_UP)

        if down_height >= up_height:
            menu.view.adjustSize(down_pos, MenuAnimationType.DROP_DOWN)
            menu.exec(down_pos, aniType=MenuAnimationType.DROP_DOWN)
        else:
            menu.view.adjustSize(up_pos, MenuAnimationType.PULL_UP)
            menu.exec(up_pos, aniType=MenuAnimationType.PULL_UP)

    try:
        combo._create_accessible_combo_menu = MethodType(_create_accessible_combo_menu, combo)
        combo._showComboMenu = MethodType(_show_combo_menu, combo)
        setattr(combo, "_accessible_combo_menu_installed", True)
    except Exception:
        pass


def set_combo_items_accessibility(
    combo,
    *,
    name: str,
    selected_word: str = "выбран",
    unselected_word: str = "не выбран",
    clean_label=None,
) -> None:
    if combo is None:
        return
    install_accessible_combo_menu(combo)
    try:
        setattr(
            combo,
            "_accessible_combo_items_config",
            {
                "name": name,
                "selected_word": selected_word,
                "unselected_word": unselected_word,
                "clean_label": clean_label,
            },
        )
    except Exception:
        pass
    _ensure_combo_items_accessibility_signal(combo)
    _sync_combo_items_accessibility(combo)


__all__ = [
    "install_accessible_combo_menu",
    "set_combo_item_accessible_text",
    "set_combo_items_accessibility",
]
