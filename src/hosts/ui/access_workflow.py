"""Helper-слой доступа к hosts и восстановления прав."""

from __future__ import annotations

from PyQt6.QtCore import Qt

import hosts.page_plans as hosts_page_plans


def dismiss_hosts_error_bar(current_bar) -> None:
    if current_bar is not None:
        try:
            current_bar.close()
        except Exception:
            pass


def show_hosts_access_error(
    *,
    current_bar,
    last_error: str | None,
    message: str,
    tr_fn,
    info_bar_cls,
    push_button_cls,
    window,
    on_restore,
    log_warning,
    log_debug,
):
    if last_error == message:
        return current_bar, last_error

    dismiss_hosts_error_bar(current_bar)

    if not info_bar_cls:
        log_warning(f"hosts access error (no InfoBar): {message}")
        return None, message

    try:
        from qfluentwidgets import InfoBarPosition

        error_plan = hosts_page_plans.build_error_bar_plan(
            message=message,
            title=tr_fn("page.hosts.error.title", "Нет доступа к hosts"),
            action_text=tr_fn("page.hosts.button.restore_access", "Восстановить права доступа"),
            action_pending_text=tr_fn("page.hosts.button.restoring_access", "Восстановление..."),
        )

        bar = info_bar_cls.error(
            title=error_plan.title,
            content=error_plan.content,
            orient=Qt.Orientation.Vertical,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=-1,
            parent=window,
        )

        restore_btn = push_button_cls(error_plan.action_text)
        restore_btn.setFixedWidth(220)

        def _on_restore():
            restore_btn.setEnabled(False)
            restore_btn.setText(error_plan.action_pending_text)
            on_restore(bar, restore_btn)

        restore_btn.clicked.connect(_on_restore)
        bar.addWidget(restore_btn)
        return bar, message
    except Exception as exc:
        log_debug(f"Ошибка показа InfoBar: {exc}")
        return None, message


def check_hosts_access(
    *,
    runtime_state,
    hosts_path: str,
    tr_fn,
    hide_error,
    show_error,
) -> None:
    access_plan = hosts_page_plans.build_access_plan(
        runtime_state,
        hosts_path=hosts_path,
        read_error_message=tr_fn("page.hosts.error.read_hosts", "Ошибка чтения hosts: {error}", error=runtime_state.error_message),
        no_access_message=tr_fn(
            "page.hosts.error.no_access.short",
            "Нет доступа для изменения файла hosts. Скорее всего защитник/антивирус заблокировал запись.\nПуть: {path}",
            path="{path}",
        ),
    )
    if not access_plan.show_error:
        hide_error()
        return
    show_error(access_plan.error_message)


def restore_hosts_permissions_flow(
    *,
    restore_hosts_permissions_fn,
    info_bar_cls,
    window,
    dismiss_error_bar,
    invalidate_cache,
    update_ui,
    sync_selections_from_hosts,
    show_error,
    log_error,
) -> tuple[bool, str | None]:
    try:
        result = restore_hosts_permissions_fn()
        restore_plan = hosts_page_plans.build_restore_permissions_plan(
            success=result.success,
            message=result.message,
        )

        if result.success:
            dismiss_error_bar()
            invalidate_cache()
            update_ui()
            sync_selections_from_hosts()
            if info_bar_cls and restore_plan.message_plan is not None:
                from qfluentwidgets import InfoBarPosition

                info_bar_cls.success(
                    title=restore_plan.message_plan.title,
                    content=restore_plan.message_plan.content,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=window,
                )
            return True, None

        dismiss_error_bar()
        show_error(restore_plan.error_message)
        return False, restore_plan.error_message
    except Exception as exc:
        log_error(f"Ошибка при восстановлении прав: {exc}")
        dismiss_error_bar()
        show_error(str(exc))
        return False, str(exc)
