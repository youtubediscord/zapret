from __future__ import annotations

from collections.abc import Callable

from folders.defaults import PINNED_FOLDER_KEY
from presets.folders import load_preset_folder_state
from ui.widgets.folder_context_menu import FolderMenuActions, FolderMenuLabels, FolderNameDialog, show_folder_context_menu


def show_preset_folder_menu(
    *,
    parent,
    scope_key: str,
    folder_key: str,
    global_pos,
    refresh_fn: Callable[[], object],
    request_folder_action_fn: Callable[..., object],
    log_fn: Callable[[str, str], object] | None = None,
) -> None:
    scope = str(scope_key or "")

    def request_action(action: str, payload: dict) -> bool:
        request_folder_action_fn(action, **dict(payload or {}))
        return False

    show_folder_context_menu(
        parent=parent,
        folder_key=folder_key,
        global_pos=global_pos,
        actions=FolderMenuActions(
            load_state=lambda: load_preset_folder_state(scope),
            run_action=request_action,
        ),
        labels=FolderMenuLabels(
            reset_title="Сбросить папки preset-ов",
            reset_body="Вернём стандартные папки и разложим preset-ы заново по начальному правилу.",
            create_subtitle="Новая папка появится сразу после «Общие».",
            rename_subtitle="Изменится только название папки в интерфейсе. Preset-ы останутся на месте.",
            delete_body="Preset-ы из этой папки не удалятся. Они перейдут в «Общие».",
            action_error_suffix="preset-ов",
        ),
        refresh_fn=refresh_fn,
        log_fn=log_fn,
        service_folder_keys={PINNED_FOLDER_KEY},
    )


PresetFolderNameDialog = FolderNameDialog

__all__ = ["PresetFolderNameDialog", "show_preset_folder_menu"]
