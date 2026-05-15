"""Общие UI-actions для страниц пользовательских пресетов."""

from __future__ import annotations


def open_presets_folder_action(
    *,
    open_presets_folder_fn,
    info_bar_cls,
    tr_fn,
    parent_window,
    error_key: str,
    error_default: str,
    log_prefix: str,
    log_fn,
) -> None:
    try:
        open_presets_folder_fn()
    except Exception as exc:
        log_fn(f"{log_prefix}: open presets folder failed: {exc}", "WARNING")
        if info_bar_cls:
            info_bar_cls.error(
                title=tr_fn("common.error.title", "Ошибка"),
                content=tr_fn(error_key, error_default, error=exc),
                parent=parent_window,
            )
