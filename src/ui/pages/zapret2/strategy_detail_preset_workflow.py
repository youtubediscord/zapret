"""Preset workflow helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations


def prompt_preset_name(*, dialog_cls, mode: str, parent, language: str, old_name: str = "") -> str | None:
    dialog = dialog_cls(mode, old_name=old_name, parent=parent, language=language)
    if not dialog.exec():
        return None
    name = dialog.get_name()
    if not name:
        return None
    return name


def present_preset_action_result(
    result,
    *,
    info_bar,
    parent,
    log_fn,
    on_structure_changed,
) -> None:
    if getattr(result, "structure_changed", False):
        on_structure_changed()

    log_fn(result.log_message, result.log_level)

    if info_bar is None:
        return

    level = str(getattr(result, "infobar_level", "") or "").strip().lower()
    title = getattr(result, "infobar_title", "") or ""
    content = getattr(result, "infobar_content", "") or ""

    if level == "success":
        info_bar.success(title=title, content=content, parent=parent)
    elif level == "warning":
        info_bar.warning(title=title, content=content, parent=parent)
    elif level == "error":
        info_bar.error(title=title, content=content, parent=parent)


def present_preset_exception(
    *,
    action_error_message: str,
    exception: Exception,
    info_bar,
    parent,
    error_title: str,
    log_fn,
) -> None:
    log_fn(f"{action_error_message}: {exception}", "ERROR")
    if info_bar is not None:
        info_bar.error(
            title=error_title,
            content=str(exception),
            parent=parent,
        )
