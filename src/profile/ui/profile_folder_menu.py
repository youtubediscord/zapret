from __future__ import annotations

from collections.abc import Callable

from profile.folders import load_profile_folder_state
from ui.widgets.folder_context_menu import FolderMenuActions, FolderMenuLabels, show_folder_context_menu


def show_profile_folder_menu(
    *,
    parent,
    folder_key: str,
    global_pos,
    refresh_fn: Callable[[], object],
    request_folder_action_fn: Callable[..., object],
    log_fn: Callable[[str, str], object] | None = None,
) -> None:
    def request_action(action: str, payload: dict) -> bool:
        request_folder_action_fn(action, **dict(payload or {}))
        return False

    show_folder_context_menu(
        parent=parent,
        folder_key=folder_key,
        global_pos=global_pos,
        actions=FolderMenuActions(
            load_state=load_profile_folder_state,
            run_action=request_action,
        ),
        labels=FolderMenuLabels(
            reset_title="Сбросить папки profile-ов",
            reset_body="Вернём стандартные папки profile-ов и разложим их заново по начальному правилу.",
            create_subtitle="Новая папка появится сразу после «Общие».",
            rename_subtitle="Изменится только название папки в интерфейсе. Profile останутся на месте.",
            delete_body="Profile из этой папки не удалятся. Они перейдут в «Общие».",
            action_error_suffix="profile-ов",
        ),
        refresh_fn=refresh_fn,
        log_fn=log_fn,
    )


__all__ = ["show_profile_folder_menu"]
