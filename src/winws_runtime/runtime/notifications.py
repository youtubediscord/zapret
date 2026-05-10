from __future__ import annotations

from app_notifications import advisory_notification, notification_action


def notify_conflicting_processes(app, conflicting: list[dict], request_id: int) -> None:
    names = ", ".join(str(item.get("name") or item.get("exe") or "неизвестно") for item in conflicting)
    app.window_notification_controller.notify(
        advisory_notification(
            level="warning",
            title="Обнаружены конфликтующие программы",
            content=(
                "Обнаружены программы, которые блокируют WinDivert:\n\n"
                f"{names}\n\n"
                "Эти программы перехватывают системные вызовы и не дают "
                "WinDivert драйверу запуститься."
            ),
            source="launch.conflicting_processes",
            presentation="infobar",
            queue="immediate",
            duration=-1,
            dedupe_key=f"launch.conflicting_processes:{request_id}",
            dedupe_window_ms=0,
            buttons=[
                notification_action("launch_conflict_kill_start", "Закрыть и продолжить", value=request_id),
                notification_action("launch_conflict_ignore_start", "Продолжить без закрытия", value=request_id),
                notification_action("launch_conflict_cancel", "Отмена", value=request_id),
            ],
        )
    )


def notify_conflict_kill_failed(app, request_id: int) -> None:
    app.window_notification_controller.notify(
        advisory_notification(
            level="warning",
            title="Не удалось закрыть процессы",
            content=(
                "Некоторые конфликтующие процессы не удалось закрыть.\n"
                "Запуск DPI может завершиться ошибкой."
            ),
            source="launch.conflicting_processes.kill_failed",
            presentation="infobar",
            queue="immediate",
            duration=-1,
            dedupe_key=f"launch.conflicting_processes.kill_failed:{request_id}",
            dedupe_window_ms=0,
            buttons=[
                notification_action("launch_conflict_ignore_start", "Продолжить запуск", value=request_id),
                notification_action("launch_conflict_cancel", "Отмена", value=request_id),
            ],
        )
    )


def notify_runner_launch_error_threadsafe(app, message: str) -> None:
    text = str(message or "").strip()
    if not text:
        return
    controller = getattr(app, "window_notification_controller", None)
    if controller is None:
        return
    controller.notify_threadsafe(
        advisory_notification(
            level="error",
            title="Ошибка",
            content=text,
            source="launch.runner_error",
            presentation="infobar",
            queue="immediate",
            duration=10000,
            dedupe_key=f"launch.runner_error:{' '.join(text.split()).lower()}",
        )
    )
