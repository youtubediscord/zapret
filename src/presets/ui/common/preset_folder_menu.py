from __future__ import annotations

from collections.abc import Callable

from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBox, MessageBoxBase, RoundMenu, SubtitleLabel

from folders.defaults import PINNED_FOLDER_KEY
from presets.folders import (
    create_preset_folder,
    delete_preset_folder,
    load_preset_folder_state,
    move_preset_folder_by_step,
    rename_preset_folder,
    reset_preset_folders,
)
from ui.fluent_widgets import style_semantic_caption_label
from ui.presets_menu.common import fluent_icon, make_menu_action


class PresetFolderNameDialog(MessageBoxBase):
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

    def validate(self) -> bool:
        if self.nameEdit.text().strip():
            self.warningLabel.hide()
            return True
        self.warningLabel.setText("Введите название папки.")
        self.warningLabel.show()
        return False


def show_preset_folder_menu(
    *,
    parent,
    scope_key: str,
    folder_key: str,
    global_pos,
    refresh_fn: Callable[[], object],
    log_fn: Callable[[str, str], object] | None = None,
) -> None:
    key = str(folder_key or "").strip()
    state = load_preset_folder_state(scope_key)
    folders = state.get("folders", {}) if isinstance(state, dict) else {}
    folder = folders.get(key) if isinstance(folders, dict) else None
    is_service = key == PINNED_FOLDER_KEY
    is_existing_folder = isinstance(folder, dict) or is_service
    is_system = bool(folder.get("system", False)) if isinstance(folder, dict) else is_service

    menu = RoundMenu(parent=parent)

    if is_service:
        return

    create_action = make_menu_action("Создать папку", icon=fluent_icon("ADD"), parent=menu)
    create_action.triggered.connect(lambda: _create_folder(parent, scope_key, refresh_fn, log_fn))
    menu.addAction(create_action)

    if is_existing_folder and not is_system:
        menu.addSeparator()
        rename_action = make_menu_action("Переименовать папку", icon=fluent_icon("EDIT"), parent=menu)
        rename_action.triggered.connect(
            lambda: _rename_folder(
                parent,
                scope_key,
                key,
                str(folder.get("name") or ""),
                refresh_fn,
                log_fn,
            )
        )
        menu.addAction(rename_action)

        delete_action = make_menu_action("Удалить папку", icon=fluent_icon("DELETE"), parent=menu)
        delete_action.triggered.connect(lambda: _delete_folder(parent, scope_key, key, refresh_fn, log_fn))
        menu.addAction(delete_action)

    if is_existing_folder:
        menu.addSeparator()
        move_up_action = make_menu_action("Переместить выше", icon=fluent_icon("UP"), parent=menu)
        move_down_action = make_menu_action("Переместить ниже", icon=fluent_icon("DOWN"), parent=menu)
        move_up_action.triggered.connect(
            lambda: _run_folder_action(
                parent,
                lambda: move_preset_folder_by_step(scope_key, key, -1),
                refresh_fn,
                log_fn,
                "не удалось переместить папку preset-ов",
            )
        )
        move_down_action.triggered.connect(
            lambda: _run_folder_action(
                parent,
                lambda: move_preset_folder_by_step(scope_key, key, 1),
                refresh_fn,
                log_fn,
                "не удалось переместить папку preset-ов",
            )
        )
        menu.addAction(move_up_action)
        menu.addAction(move_down_action)

    menu.addSeparator()
    reset_action = make_menu_action("Сбросить папки preset-ов", icon=fluent_icon("SYNC"), parent=menu)
    reset_action.triggered.connect(lambda: _reset_folders(parent, scope_key, refresh_fn, log_fn))
    menu.addAction(reset_action)

    menu.exec(global_pos)


def _create_folder(parent, scope_key: str, refresh_fn: Callable[[], object], log_fn) -> None:
    dialog = PresetFolderNameDialog(
        title="Создать папку",
        subtitle="Новая папка появится сразу после «Общие».",
        button_text="Создать",
        parent=parent,
    )
    if not dialog.exec():
        return
    name = dialog.nameEdit.text().strip()
    _run_folder_action(parent, lambda: bool(create_preset_folder(scope_key, name)), refresh_fn, log_fn, "не удалось создать папку preset-ов")


def _rename_folder(parent, scope_key: str, folder_key: str, current_name: str, refresh_fn: Callable[[], object], log_fn) -> None:
    dialog = PresetFolderNameDialog(
        title="Переименовать папку",
        subtitle="Изменится только название папки в интерфейсе. Preset-ы останутся на месте.",
        button_text="Переименовать",
        current_name=current_name,
        parent=parent,
    )
    if not dialog.exec():
        return
    name = dialog.nameEdit.text().strip()
    _run_folder_action(parent, lambda: rename_preset_folder(scope_key, folder_key, name), refresh_fn, log_fn, "не удалось переименовать папку preset-ов")


def _delete_folder(parent, scope_key: str, folder_key: str, refresh_fn: Callable[[], object], log_fn) -> None:
    box = MessageBox(
        "Удалить папку",
        "Preset-ы из этой папки не удалятся. Они перейдут в «Общие».",
        parent.window() if parent is not None and not parent.isWindow() else parent,
    )
    box.yesButton.setText("Удалить")
    box.cancelButton.setText("Отмена")
    if not box.exec():
        return
    _run_folder_action(parent, lambda: delete_preset_folder(scope_key, folder_key), refresh_fn, log_fn, "не удалось удалить папку preset-ов")


def _reset_folders(parent, scope_key: str, refresh_fn: Callable[[], object], log_fn) -> None:
    box = MessageBox(
        "Сбросить папки preset-ов",
        "Вернём стандартные папки и разложим preset-ы заново по начальному правилу.",
        parent.window() if parent is not None and not parent.isWindow() else parent,
    )
    box.yesButton.setText("Сбросить")
    box.cancelButton.setText("Отмена")
    if not box.exec():
        return
    _run_folder_action(parent, lambda: bool(reset_preset_folders(scope_key)), refresh_fn, log_fn, "не удалось сбросить папки preset-ов")


def _run_folder_action(parent, action: Callable[[], object], refresh_fn: Callable[[], object], log_fn, error_text: str) -> None:
    try:
        if action():
            refresh_fn()
    except Exception as exc:
        if log_fn is not None:
            log_fn(f"{parent.__class__.__name__}: {error_text}: {exc}", "ERROR")


__all__ = ["PresetFolderNameDialog", "show_preset_folder_menu"]
