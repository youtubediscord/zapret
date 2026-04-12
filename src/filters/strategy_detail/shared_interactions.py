from __future__ import annotations

from filters.strategy_detail.shared import ensure_preview_dialog, show_strategy_preview_dialog


def build_preview_strategy_data(*, strategy_id: str, strategy_data: dict | None) -> dict:
    normalized_id = str(strategy_id or "").strip()
    data = dict(strategy_data or {})
    if "name" not in data:
        data["name"] = normalized_id or "Стратегия"

    args = data.get("args", [])
    if isinstance(args, str):
        args_text = args
    elif isinstance(args, (list, tuple)):
        args_text = "\n".join([str(a) for a in args if a is not None]).strip()
    else:
        args_text = ""
    data["args"] = args_text
    return data


def resolve_mark_rating(mark_state: object) -> str | None:
    if mark_state is True:
        return "working"
    if mark_state is False:
        return "broken"
    return None


def get_preview_rating(mark_store, *, strategy_id: str, target_key: str) -> str | None:
    normalized_target = str(target_key or "").strip()
    normalized_strategy = str(strategy_id or "").strip()
    if not normalized_target or not normalized_strategy or normalized_strategy == "none":
        return None
    try:
        mark_state = mark_store.get_mark(normalized_target, normalized_strategy)
    except Exception:
        return None
    return resolve_mark_rating(mark_state)


def toggle_preview_rating(mark_store, *, strategy_id: str, rating: str, target_key: str) -> tuple[bool, object, str | None]:
    normalized_target = str(target_key or "").strip()
    normalized_strategy = str(strategy_id or "").strip()
    if not normalized_target or not normalized_strategy or normalized_strategy == "none":
        return False, None, None

    try:
        current = mark_store.get_mark(normalized_target, normalized_strategy)
    except Exception:
        current = None

    normalized_rating = str(rating or "").strip().lower()
    if normalized_rating == "working":
        new_state = None if current is True else True
    elif normalized_rating == "broken":
        new_state = None if current is False else False
    else:
        new_state = None

    try:
        mark_store.set_mark(normalized_target, normalized_strategy, new_state)
    except Exception:
        return False, current, resolve_mark_rating(current)

    return True, new_state, resolve_mark_rating(new_state)


def save_strategy_mark(mark_store, *, strategy_id: str, is_working, target_key: str) -> tuple[bool, object, str | None]:
    normalized_target = str(target_key or "").strip()
    normalized_strategy = str(strategy_id or "").strip()
    if not normalized_target or not normalized_strategy or normalized_strategy == "none":
        return False, None, None

    try:
        mark_store.set_mark(normalized_target, normalized_strategy, is_working)
    except Exception:
        return False, None, None
    return True, is_working, resolve_mark_rating(is_working)


def toggle_favorite(
    favorites_store,
    *,
    strategy_id: str,
    is_favorite: bool,
    target_key: str,
    favorite_ids: set[str],
) -> tuple[bool, set[str]]:
    normalized_target = str(target_key or "").strip()
    normalized_strategy = str(strategy_id or "").strip()
    current_ids = set(favorite_ids or set())
    if not normalized_target or not normalized_strategy:
        return False, current_ids

    try:
        favorites_store.set_favorite(normalized_target, normalized_strategy, is_favorite)
    except Exception:
        return False, current_ids

    if is_favorite:
        current_ids.add(normalized_strategy)
    else:
        current_ids.discard(normalized_strategy)

    return True, current_ids


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
