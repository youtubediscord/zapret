"""Preview-helper'ы для страницы деталей стратегии Z2."""

from __future__ import annotations

from ui.pages.strategy_detail_components import ensure_preview_dialog, show_strategy_preview_dialog


def close_preview_dialog(preview_dialog, *, preview_pinned: bool, force: bool = False) -> tuple[object | None, bool]:
    if preview_dialog is None:
        return None, bool(preview_pinned)
    if (not force) and preview_pinned:
        return preview_dialog, bool(preview_pinned)
    try:
        preview_dialog.close_dialog()
    except Exception:
        try:
            preview_dialog.close()
        except Exception:
            pass
    return None, False


def ensure_preview_dialog_instance(preview_dialog, *, parent_win, on_closed, dialog_cls):
    return ensure_preview_dialog(
        preview_dialog,
        parent_win=parent_win,
        on_closed=on_closed,
        dialog_cls=dialog_cls,
    )


def show_preview_dialog_for_strategy(
    preview_dialog,
    *,
    target_key: str,
    strategy_id: str,
    global_pos,
    strategy_data,
    rating_getter,
    rating_toggler,
) -> None:
    show_strategy_preview_dialog(
        preview_dialog,
        strategy_data=strategy_data,
        strategy_id=strategy_id,
        target_key=target_key,
        global_pos=global_pos,
        rating_getter=rating_getter,
        rating_toggler=rating_toggler,
    )
