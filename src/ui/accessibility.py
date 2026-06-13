from __future__ import annotations

from types import MethodType

from PyQt6.QtCore import Qt


_TOGGLE_ACCESSIBLE_BASE_PROPERTY = "_keyboardToggleAccessibleBaseName"
_TOGGLE_ACCESSIBLE_TEXT_PROPERTY = "_keyboardToggleAccessibleText"


def _clean_text(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _widget_text(widget) -> str:
    try:
        return _clean_text(widget.text())
    except Exception:
        return ""


def set_accessible_name(widget, text: object | None = None) -> bool:
    """Задаёт короткое имя элемента для экранного диктора."""

    if widget is None:
        return False
    value = _clean_text(_widget_text(widget) if text is None else text)
    if not value:
        return False
    try:
        if _clean_text(widget.accessibleName()) == value:
            return False
    except Exception:
        pass
    try:
        widget.setAccessibleName(value)
        return True
    except Exception:
        return False


def set_accessible_description(widget, text: object) -> bool:
    """Задаёт пояснение: что произойдёт или что значит элемент."""

    if widget is None:
        return False
    value = _clean_text(text)
    if not value:
        return False
    try:
        if _clean_text(widget.accessibleDescription()) == value:
            return False
    except Exception:
        pass
    try:
        widget.setAccessibleDescription(value)
        return True
    except Exception:
        return False


def set_control_accessibility(
    widget,
    *,
    name: object | None = None,
    description: object | None = None,
) -> None:
    """Заполняет имя и описание обычной кнопки, поля или переключателя."""

    set_accessible_name(widget, name)
    if description is not None:
        set_accessible_description(widget, description)
    remove_line_edit_buttons_from_tab_order(widget)
    remove_scrollbar_arrow_buttons_from_tab_order(widget)
    remove_switch_indicators_from_tab_order(widget)
    _sync_spinbox_children_accessibility(widget, name=name, description=description)
    _remember_keyboard_toggle_accessibility(widget, name=name)
    _enable_keyboard_click_for_button(widget)


def set_state_text(widget, text: object) -> None:
    """Записывает текстовое состояние, чтобы смысл не зависел от цвета/иконки."""

    value = _clean_text(text)
    if not value:
        return
    set_accessible_name(widget, value)
    remove_line_edit_buttons_from_tab_order(widget)
    remove_scrollbar_arrow_buttons_from_tab_order(widget)
    remove_switch_indicators_from_tab_order(widget)
    _sync_spinbox_children_accessibility(widget, name=value, description=None)
    try:
        if _clean_text(widget.property("screenReaderStateText")) == value:
            return
    except Exception:
        pass
    try:
        widget.setProperty("screenReaderStateText", value)
    except Exception:
        pass


def _sync_spinbox_children_accessibility(
    widget,
    *,
    name: object | None,
    description: object | None,
) -> None:
    value = _clean_text(name)
    if widget is None or not value:
        return
    try:
        children = widget.findChildren(object)
    except Exception:
        return
    for child in children:
        try:
            object_name = str(child.objectName() or "")
        except Exception:
            object_name = ""
        child_type = type(child).__name__
        if object_name == "qt_spinbox_lineedit":
            set_accessible_name(child, value)
            if description is not None:
                set_accessible_description(child, description)
            continue
        if child_type != "SpinButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def set_item_accessible_text(item, text: object, *, description: object | None = None) -> None:
    """Задаёт текст для диктора у строки/ячейки Qt item-модели."""

    if item is None:
        return
    value = _clean_text(text)
    if value:
        try:
            item.setData(Qt.ItemDataRole.AccessibleTextRole, value)
        except Exception:
            pass
    if description is not None:
        description_value = _clean_text(description)
        if description_value:
            try:
                item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, description_value)
            except Exception:
                pass


def remove_line_edit_buttons_from_tab_order(line_edit) -> None:
    """Убирает служебные кнопки qfluentwidgets LineEdit/SearchLineEdit из Tab-порядка."""

    if line_edit is None:
        return
    try:
        children = line_edit.findChildren(object)
    except Exception:
        return
    for child in children:
        try:
            object_name = str(child.objectName() or "")
        except Exception:
            continue
        if object_name != "lineEditButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def remove_scrollbar_arrow_buttons_from_tab_order(widget) -> None:
    """Убирает служебные стрелки qfluentwidgets ScrollBar из Tab-порядка."""

    if widget is None:
        return
    try:
        children = widget.findChildren(object)
    except Exception:
        return
    for child in children:
        if type(child).__name__ != "ArrowButton":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def remove_switch_indicators_from_tab_order(widget) -> None:
    """Убирает служебный Indicator qfluentwidgets SwitchButton из Tab-порядка."""

    if widget is None:
        return
    try:
        children = widget.findChildren(object)
    except Exception:
        return
    for child in children:
        if type(child).__name__ != "Indicator":
            continue
        try:
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass


def set_breadcrumb_accessibility(widget, parts: object) -> None:
    """Записывает путь навигации как обычный текст для диктора."""

    if widget is None:
        return
    cleaned_parts = [_clean_text(part) for part in tuple(parts or ())]
    visible_parts = [part for part in cleaned_parts if part]
    if not visible_parts:
        return
    text = f"Навигация: {' > '.join(visible_parts)}"
    set_control_accessibility(
        widget,
        name=text,
        description="Показывает путь до текущей страницы. Выберите пункт, чтобы вернуться назад.",
    )
    set_state_text(widget, text)


def enable_keyboard_click(widget) -> None:
    """Делает кликабельную карточку доступной через Tab, Enter и Пробел."""

    if widget is None:
        return
    try:
        if widget.focusPolicy() != Qt.FocusPolicy.StrongFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    except Exception:
        return
    try:
        if widget.property("_keyboardClickEnabled"):
            return
        widget.setProperty("_keyboardClickEnabled", True)
    except Exception:
        pass

    original_key_press = getattr(widget, "keyPressEvent", None)

    def _keyboard_click_key_press(self, event):  # noqa: ANN001
        try:
            key = event.key()
        except Exception:
            key = None
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if _activate_keyboard_click_target(self):
                try:
                    event.accept()
                except Exception:
                    pass
                return
        if original_key_press is not None:
            return original_key_press(event)
        return None

    try:
        widget.keyPressEvent = MethodType(_keyboard_click_key_press, widget)
    except Exception:
        pass


def _activate_keyboard_click_target(widget) -> bool:
    click = getattr(widget, "click", None)
    if click is not None:
        click()
        return True
    clicked = getattr(widget, "clicked", None)
    emit = getattr(clicked, "emit", None)
    if emit is not None:
        try:
            emit()
            return True
        except TypeError:
            pass
    for child_name in ("button", "linkButton"):
        child = getattr(widget, child_name, None)
        click = getattr(child, "click", None)
        if click is None:
            continue
        click()
        return True
    return False


def _enable_keyboard_click_for_button(widget) -> None:
    if widget is None:
        return
    if _is_checkable_widget(widget):
        enable_keyboard_toggle(widget)
        return
    try:
        clicked = getattr(widget, "clicked", None)
    except Exception:
        return
    if clicked is None:
        return
    enable_keyboard_click(widget)


def _is_checkable_widget(widget) -> bool:
    if widget is None:
        return False
    try:
        is_checked = getattr(widget, "isChecked", None)
        set_checked = getattr(widget, "setChecked", None)
    except Exception:
        return False
    if not (callable(is_checked) and callable(set_checked)):
        return False
    if type(widget).__name__ in {"CheckBox", "SwitchButton"}:
        return True
    try:
        is_checkable = getattr(widget, "isCheckable", None)
    except Exception:
        return False
    if callable(is_checkable):
        try:
            return bool(is_checkable())
        except Exception:
            return False
    return False


def _remember_keyboard_toggle_accessibility(widget, *, name: object | None) -> None:
    if not _is_checkable_widget(widget):
        return
    value = _clean_text(_widget_text(widget) if name is None else name)
    for state in ("включено", "выключено"):
        suffix = f", {state}"
        if not value.endswith(suffix):
            continue
        base = value[: -len(suffix)].strip()
        if not base:
            return
        try:
            widget.setProperty(_TOGGLE_ACCESSIBLE_BASE_PROPERTY, base)
            widget.setProperty(_TOGGLE_ACCESSIBLE_TEXT_PROPERTY, value)
        except Exception:
            pass
        return


def _refresh_keyboard_toggle_accessibility(widget) -> None:
    if not _is_checkable_widget(widget):
        return
    try:
        base = _clean_text(widget.property(_TOGGLE_ACCESSIBLE_BASE_PROPERTY))
    except Exception:
        base = ""
    if not base:
        return
    try:
        state = "включено" if bool(widget.isChecked()) else "выключено"
    except Exception:
        return
    text = f"{base}, {state}"
    set_accessible_name(widget, text)
    try:
        widget.setProperty("screenReaderStateText", text)
        widget.setProperty(_TOGGLE_ACCESSIBLE_TEXT_PROPERTY, text)
    except Exception:
        pass


def enable_keyboard_toggle(widget) -> None:
    """Делает переключатель доступным через Tab, Enter и Пробел."""

    if widget is None:
        return
    try:
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    except Exception:
        return
    try:
        if widget.property("_keyboardToggleEnabled"):
            return
        widget.setProperty("_keyboardToggleEnabled", True)
    except Exception:
        pass

    original_key_press = getattr(widget, "keyPressEvent", None)

    def _keyboard_toggle_key_press(self, event):  # noqa: ANN001
        try:
            key = event.key()
        except Exception:
            key = None
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            try:
                self.setChecked(not bool(self.isChecked()))
                _refresh_keyboard_toggle_accessibility(self)
                event.accept()
                return
            except Exception:
                pass
        if original_key_press is not None:
            return original_key_press(event)
        return None

    try:
        widget.keyPressEvent = MethodType(_keyboard_toggle_key_press, widget)
    except Exception:
        pass


__all__ = [
    "enable_keyboard_click",
    "enable_keyboard_toggle",
    "remove_switch_indicators_from_tab_order",
    "remove_line_edit_buttons_from_tab_order",
    "remove_scrollbar_arrow_buttons_from_tab_order",
    "set_breadcrumb_accessibility",
    "set_accessible_description",
    "set_accessible_name",
    "set_control_accessibility",
    "set_item_accessible_text",
    "set_state_text",
]
