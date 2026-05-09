"""Общие UI-actions для страниц пользовательских пресетов."""

from __future__ import annotations

import os
import subprocess
import sys


def open_presets_folder_action(
    *,
    get_presets_dir_fn,
    info_bar_cls,
    tr_fn,
    parent_window,
    error_key: str,
    error_default: str,
    log_prefix: str,
    log_fn,
) -> None:
    try:
        presets_dir = get_presets_dir_fn()
        presets_dir.mkdir(parents=True, exist_ok=True)
        path = str(presets_dir)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])  # noqa: S603 - user-triggered opener
    except Exception as exc:
        log_fn(f"{log_prefix}: open presets folder failed: {exc}", "WARNING")
        if info_bar_cls:
            info_bar_cls.error(
                title=tr_fn("common.error.title", "Ошибка"),
                content=tr_fn(error_key, error_default, error=exc),
                parent=parent_window,
            )
