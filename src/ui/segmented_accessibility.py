from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt

from ui.accessibility import set_control_accessibility, set_state_text


_FILTER_ATTR = "_zapretgui_segmented_keyboard_filter"
_TITLE_ATTR = "_zapretgui_segmented_accessible_title"
_LABELS_ATTR = "_zapretgui_segmented_accessible_labels"
_SELECTED_WORD_ATTR = "_zapretgui_segmented_selected_word"
_UNSELECTED_WORD_ATTR = "_zapretgui_segmented_unselected_word"


def _clean_text(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _segmented_description(widget) -> str:
    keyboard_hint = "Выберите пункт стрелками влево и вправо, затем нажмите Enter или Пробел."
    try:
        current = _clean_text(widget.accessibleDescription())
    except Exception:
        current = ""
    if not current:
        return keyboard_hint
    if "Enter или Пробел" in current:
        return current
    return f"{current} {keyboard_hint}"


def _segmented_current_key(widget) -> str:
    current_route_key = getattr(widget, "currentRouteKey", None)
    if callable(current_route_key):
        try:
            key = _clean_text(current_route_key())
        except Exception:
            key = ""
        if key:
            return key
    key = _clean_text(getattr(widget, "_currentRouteKey", ""))
    if key:
        return key
    try:
        return str(widget.currentItem() or "").strip()
    except Exception:
        return ""


def _segmented_items(widget) -> dict[str, object]:
    try:
        return {str(key): item for key, item in dict(getattr(widget, "items", {}) or {}).items()}
    except Exception:
        return {}


def _set_strong_focus(widget) -> None:
    try:
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    except Exception:
        pass


def _click_segmented_item(widget, key: str, items: dict[str, object]) -> bool:
    item = items.get(str(key))
    if item is not None:
        click = getattr(item, "click", None)
        if callable(click):
            click()
            return True
    set_current = getattr(widget, "setCurrentItem", None)
    if callable(set_current):
        try:
            set_current(str(key))
            return True
        except Exception:
            return False
    return False


def _set_segmented_focus(item: object) -> None:
    set_focus = getattr(item, "setFocus", None)
    if callable(set_focus):
        try:
            set_focus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            try:
                set_focus()
            except Exception:
                pass


def _refresh_segmented_items_accessibility(
    widget,
    *,
    title: str,
    labels: dict[str, object],
    selected_word: str,
    unselected_word: str,
) -> None:
    current_key = _segmented_current_key(widget)
    items = _segmented_items(widget)
    accessible_labels = {str(key): value for key, value in dict(labels or {}).items()}
    current_label = ""
    for key, item in items.items():
        try:
            label = _clean_text(accessible_labels.get(str(key), item.text()))
        except Exception:
            label = ""
        if not label:
            continue
        state = selected_word if str(key) == current_key else unselected_word
        if str(key) == current_key:
            current_label = label
        text = f"{title}: {label}, {state}"
        set_control_accessibility(item, name=text)
        set_state_text(item, text)
    widget_text = f"{title}, выбрано: {current_label}" if current_label else title
    set_control_accessibility(
        widget,
        name=widget_text,
        description=_segmented_description(widget),
    )
    set_state_text(widget, widget_text)


def _refresh_segmented_items_accessibility_from_widget(widget) -> None:
    title = _clean_text(getattr(widget, _TITLE_ATTR, ""))
    if not title:
        return
    labels = getattr(widget, _LABELS_ATTR, {}) or {}
    selected_word = _clean_text(getattr(widget, _SELECTED_WORD_ATTR, "")) or "выбрано"
    unselected_word = _clean_text(getattr(widget, _UNSELECTED_WORD_ATTR, "")) or "не выбрано"
    _refresh_segmented_items_accessibility(
        widget,
        title=title,
        labels=dict(labels or {}),
        selected_word=selected_word,
        unselected_word=unselected_word,
    )


class _SegmentedKeyboardFilter(QObject):
    def __init__(self, widget) -> None:
        super().__init__(widget)
        self._widget = widget

    def eventFilter(self, watched, event):  # noqa: N802
        if event is None or event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        handled_keys = {
            int(Qt.Key.Key_Left),
            int(Qt.Key.Key_Up),
            int(Qt.Key.Key_Right),
            int(Qt.Key.Key_Down),
            int(Qt.Key.Key_Home),
            int(Qt.Key.Key_End),
            int(Qt.Key.Key_Return),
            int(Qt.Key.Key_Enter),
            int(Qt.Key.Key_Space),
        }
        if int(key) not in handled_keys:
            return False

        widget = self._widget
        items = _segmented_items(widget)
        keys = list(items)
        if not keys:
            return False

        watched_key = next((item_key for item_key, item in items.items() if item is watched), "")
        current_key = watched_key or _segmented_current_key(widget)
        current_index = keys.index(current_key) if current_key in keys else 0

        if int(key) in {int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter), int(Qt.Key.Key_Space)}:
            target_key = current_key if current_key in items else keys[current_index]
        elif int(key) in {int(Qt.Key.Key_Left), int(Qt.Key.Key_Up)}:
            target_key = keys[(current_index - 1) % len(keys)]
        elif int(key) in {int(Qt.Key.Key_Right), int(Qt.Key.Key_Down)}:
            target_key = keys[(current_index + 1) % len(keys)]
        elif int(key) == int(Qt.Key.Key_Home):
            target_key = keys[0]
        else:
            target_key = keys[-1]

        if not _click_segmented_item(widget, target_key, items):
            return False
        _set_segmented_focus(items[target_key])
        _refresh_segmented_items_accessibility_from_widget(widget)
        event.accept()
        return True


def _ensure_segmented_keyboard_access(widget, items: dict[str, object]) -> None:
    _set_strong_focus(widget)
    keyboard_filter = getattr(widget, _FILTER_ATTR, None)
    if keyboard_filter is None:
        keyboard_filter = _SegmentedKeyboardFilter(widget)
        setattr(widget, _FILTER_ATTR, keyboard_filter)
        try:
            widget.installEventFilter(keyboard_filter)
        except Exception:
            pass
    for item in items.values():
        _set_strong_focus(item)
        try:
            item.installEventFilter(keyboard_filter)
        except Exception:
            pass


def set_segmented_items_accessibility(
    widget,
    *,
    name: str,
    labels: dict[str, object] | None = None,
    selected_word: str = "выбрано",
    unselected_word: str = "не выбрано",
) -> None:
    if widget is None:
        return
    title = _clean_text(name)
    if not title:
        return
    items = _segmented_items(widget)
    labels = dict(labels or {})
    setattr(widget, _TITLE_ATTR, title)
    setattr(widget, _LABELS_ATTR, labels)
    setattr(widget, _SELECTED_WORD_ATTR, _clean_text(selected_word) or "выбрано")
    setattr(widget, _UNSELECTED_WORD_ATTR, _clean_text(unselected_word) or "не выбрано")
    _ensure_segmented_keyboard_access(widget, items)
    _refresh_segmented_items_accessibility_from_widget(widget)


__all__ = ["set_segmented_items_accessibility"]
