from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBox, MessageBoxBase, RoundMenu, SubtitleLabel

from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import style_semantic_caption_label
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.popup_menu import exec_popup_menu
from ui.presets_menu.common import fluent_icon, make_menu_action


@dataclass(frozen=True)
class FolderMenuActions:
    run_action: Callable[[str, dict], object]


@dataclass(frozen=True)
class FolderMenuLabels:
    reset_title: str
    reset_body: str
    create_subtitle: str
    rename_subtitle: str
    delete_body: str
    action_error_suffix: str


class FolderNameDialog(MessageBoxBase):
    def __init__(self, *, title: str, subtitle: str, button_text: str, current_name: str = "", parent=None):
        if parent is not None and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)

        self.titleLabel = SubtitleLabel(title, self.widget)
        self.subtitleLabel = BodyLabel(subtitle, self.widget)
        self.subtitleLabel.setWordWrap(True)

        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(str(current_name or ""))
        self.nameEdit.setPlaceholderText("Название папки")
        self.nameEdit.setClearButtonEnabled(True)
        self.nameEdit.selectAll()

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(button_text)
        self.cancelButton.setText("Отмена")
        self.widget.setMinimumWidth(420)
        self._install_accessibility(button_text=button_text)

    def validate(self) -> bool:
        if self.nameEdit.text().strip():
            self.warningLabel.hide()
            return True
        self._show_warning("Введите название папки.")
        self.warningLabel.show()
        return False

    def _install_accessibility(self, *, button_text: str) -> None:
        current_name = self.nameEdit.text().strip()
        is_rename = bool(current_name) or str(button_text or "").strip().lower().startswith("переимен")
        if is_rename:
            name = "Новое название папки"
            description = f"Текущее имя: {current_name}. Введите новое имя папки."
            yes_name = "Переименовать папку"
            yes_description = "Меняет имя папки."
            cancel_name = "Отменить переименование папки"
        else:
            name = "Название папки"
            description = "Введите имя папки для группировки элементов."
            yes_name = "Создать папку"
            yes_description = "Создаёт папку."
            cancel_name = "Отменить создание папки"
        set_control_accessibility(self.nameEdit, name=name, description=description)
        set_control_accessibility(self.yesButton, name=yes_name, description=yes_description)
        set_control_accessibility(
            self.cancelButton,
            name=cancel_name,
            description="Закрывает окно без изменений.",
        )

    def _show_warning(self, text: str) -> None:
        self.warningLabel.setText(text)
        set_state_text(self.warningLabel, f"Ошибка: {text}")


def show_folder_context_menu(
    *,
    parent,
    folder_key: str,
    global_pos,
    folder_state: dict,
    actions: FolderMenuActions,
    labels: FolderMenuLabels,
    refresh_fn: Callable[[], object],
    log_fn: Callable[[str, str], object] | None = None,
    service_folder_keys: set[str] | None = None,
) -> None:
    key = str(folder_key or "").strip()
    service_keys = {str(value or "").strip() for value in (service_folder_keys or set()) if str(value or "").strip()}
    state = folder_state if isinstance(folder_state, dict) else {}
    folders = state.get("folders", {}) if isinstance(state, dict) else {}
    folder = folders.get(key) if isinstance(folders, dict) else None
    is_service = key in service_keys
    is_existing_folder = isinstance(folder, dict) or is_service
    is_system = bool(folder.get("system", False)) if isinstance(folder, dict) else is_service
    is_collapsed = bool(folder.get("collapsed", False)) if isinstance(folder, dict) else False

    menu = RoundMenu(parent=parent)
    action_map: dict[object, tuple[str, dict]] = {}

    def _add_action(text: str, *, icon_name: str, command: str, payload: dict | None = None):
        action = make_menu_action(text, icon=fluent_icon(icon_name), parent=menu)
        menu.addAction(action)
        action_map[action] = (str(command or ""), dict(payload or {}))
        return action

    if is_existing_folder:
        _add_action(
            "Развернуть" if is_collapsed else "Свернуть",
            icon_name="DOWN" if is_collapsed else "UP",
            command="set_collapsed",
            payload={"folder_key": key, "collapsed": not is_collapsed},
        )

    if is_service:
        chosen = exec_popup_menu(menu, global_pos, owner=parent, capture_action=True)
        _dispatch_folder_menu_action(
            chosen,
            action_map,
            parent,
            actions,
            labels,
            key,
            folder,
            refresh_fn,
            log_fn,
        )
        return

    if menu.actions():
        menu.addSeparator()
    _add_action("Создать папку", icon_name="ADD", command="create")

    if is_existing_folder and not is_system:
        menu.addSeparator()
        _add_action("Переименовать папку", icon_name="EDIT", command="rename")
        _add_action("Удалить папку", icon_name="DELETE", command="delete")

    if is_existing_folder:
        menu.addSeparator()
        _add_action("Переместить выше", icon_name="UP", command="move_step", payload={"folder_key": key, "direction": -1})
        _add_action("Переместить ниже", icon_name="DOWN", command="move_step", payload={"folder_key": key, "direction": 1})

    menu.addSeparator()
    _add_action(labels.reset_title, icon_name="SYNC", command="reset")

    chosen = exec_popup_menu(menu, global_pos, owner=parent, capture_action=True)
    _dispatch_folder_menu_action(
        chosen,
        action_map,
        parent,
        actions,
        labels,
        key,
        folder,
        refresh_fn,
        log_fn,
    )


def _dispatch_folder_menu_action(
    chosen_action,
    action_map: dict[object, tuple[str, dict]],
    parent,
    actions: FolderMenuActions,
    labels: FolderMenuLabels,
    folder_key: str,
    folder,
    refresh_fn: Callable[[], object],
    log_fn,
) -> None:
    command, payload = action_map.get(chosen_action, ("", {}))
    if not command:
        return
    if command == "create":
        _create_folder(parent, actions, labels, refresh_fn, log_fn)
        return
    if command == "rename":
        current_name = str(folder.get("name") or "") if isinstance(folder, dict) else ""
        _rename_folder(parent, actions, labels, folder_key, current_name, refresh_fn, log_fn)
        return
    if command == "delete":
        _delete_folder(parent, actions, labels, folder_key, refresh_fn, log_fn)
        return
    if command == "reset":
        _reset_folders(parent, actions, labels, refresh_fn, log_fn)
        return
    if command == "set_collapsed":
        error_text = f"не удалось свернуть или развернуть папку {labels.action_error_suffix}"
    elif command == "move_step":
        error_text = f"не удалось переместить папку {labels.action_error_suffix}"
    else:
        error_text = f"не удалось выполнить действие папки {labels.action_error_suffix}"
    _run_folder_action(parent, actions, command, payload, refresh_fn, log_fn, error_text)


def _create_folder(parent, actions: FolderMenuActions, labels: FolderMenuLabels, refresh_fn: Callable[[], object], log_fn) -> None:
    dialog = FolderNameDialog(
        title="Создать папку",
        subtitle=labels.create_subtitle,
        button_text="Создать",
        parent=parent,
    )
    if not dialog.exec():
        return
    name = dialog.nameEdit.text().strip()
    _run_folder_action(parent, actions, "create", {"name": name}, refresh_fn, log_fn, f"не удалось создать папку {labels.action_error_suffix}")


def _rename_folder(parent, actions: FolderMenuActions, labels: FolderMenuLabels, folder_key: str, current_name: str, refresh_fn: Callable[[], object], log_fn) -> None:
    dialog = FolderNameDialog(
        title="Переименовать папку",
        subtitle=labels.rename_subtitle,
        button_text="Переименовать",
        current_name=current_name,
        parent=parent,
    )
    if not dialog.exec():
        return
    name = dialog.nameEdit.text().strip()
    _run_folder_action(parent, actions, "rename", {"folder_key": folder_key, "name": name}, refresh_fn, log_fn, f"не удалось переименовать папку {labels.action_error_suffix}")


def _delete_folder(parent, actions: FolderMenuActions, labels: FolderMenuLabels, folder_key: str, refresh_fn: Callable[[], object], log_fn) -> None:
    box = MessageBox(
        "Удалить папку",
        labels.delete_body,
        parent.window() if parent is not None and not parent.isWindow() else parent,
    )
    box.yesButton.setText("Удалить")
    box.cancelButton.setText("Отмена")
    set_message_box_button_accessibility(
        box,
        yes_name="Удалить папку",
        yes_description=labels.delete_body,
        cancel_name="Отменить удаление папки",
        cancel_description="Закрывает диалог без удаления папки.",
    )
    if not box.exec():
        return
    _run_folder_action(parent, actions, "delete", {"folder_key": folder_key}, refresh_fn, log_fn, f"не удалось удалить папку {labels.action_error_suffix}")


def _reset_folders(parent, actions: FolderMenuActions, labels: FolderMenuLabels, refresh_fn: Callable[[], object], log_fn) -> None:
    box = MessageBox(
        labels.reset_title,
        labels.reset_body,
        parent.window() if parent is not None and not parent.isWindow() else parent,
    )
    box.yesButton.setText("Сбросить")
    box.cancelButton.setText("Отмена")
    set_message_box_button_accessibility(
        box,
        yes_name="Сбросить папки",
        yes_description=labels.reset_body,
        cancel_name="Отменить сброс папок",
        cancel_description="Закрывает диалог без сброса папок.",
    )
    if not box.exec():
        return
    _run_folder_action(parent, actions, "reset", {}, refresh_fn, log_fn, f"не удалось сбросить папки {labels.action_error_suffix}")


def _run_folder_action(parent, actions: FolderMenuActions, action: str, payload: dict, refresh_fn: Callable[[], object], log_fn, error_text: str) -> None:
    try:
        result = actions.run_action(str(action or ""), dict(payload or {}))
        if result:
            refresh_fn()
    except Exception as exc:
        if log_fn is not None:
            log_fn(f"{parent.__class__.__name__}: {error_text}: {exc}", "ERROR")


__all__ = [
    "FolderMenuActions",
    "FolderMenuLabels",
    "FolderNameDialog",
    "show_folder_context_menu",
]
