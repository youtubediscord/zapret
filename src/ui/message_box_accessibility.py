from __future__ import annotations

from ui.accessibility import set_control_accessibility, set_state_text


def _clean_text(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _object_text(obj) -> str:
    if obj is None:
        return ""
    text_fn = getattr(obj, "text", None)
    if callable(text_fn):
        try:
            return _clean_text(text_fn())
        except Exception:
            return ""
    return ""


def _message_box_title(box) -> str:
    title = _clean_text(getattr(box, "title", ""))
    if title:
        return title
    title = _object_text(getattr(box, "titleLabel", None))
    if title:
        return title
    window_title = getattr(box, "windowTitle", None)
    if callable(window_title):
        try:
            return _clean_text(window_title())
        except Exception:
            return ""
    return ""


def _message_box_body(box) -> str:
    body = _clean_text(getattr(box, "body", ""))
    if body:
        return body
    body = _object_text(getattr(box, "contentLabel", None))
    if body:
        return body
    text_fn = getattr(box, "text", None)
    if callable(text_fn):
        try:
            return _clean_text(text_fn())
        except Exception:
            return ""
    return ""


def _set_message_box_accessibility(box) -> None:
    if box is None:
        return
    title = _message_box_title(box)
    body = _message_box_body(box)
    parts = []
    if title:
        parts.append(f"Диалог: {title}")
    else:
        parts.append("Диалог")
    if body:
        parts.append(body)
    text = ". ".join(parts)
    set_state_text(box, text)
    set_control_accessibility(box, name=text, description=body or title or text)


def set_message_box_button_accessibility(
    box,
    *,
    yes_name: str,
    yes_description: str,
    cancel_name: str,
    cancel_description: str,
    yes_button=None,
    cancel_button=None,
) -> None:
    _set_message_box_accessibility(box)
    if yes_button is None:
        yes_button = getattr(box, "yesButton", None)
    if yes_button is not None:
        set_state_text(yes_button, yes_name)
        set_control_accessibility(yes_button, name=yes_name, description=yes_description)
    if cancel_button is None:
        cancel_button = getattr(box, "cancelButton", None)
    if cancel_button is not None:
        set_state_text(cancel_button, cancel_name)
        set_control_accessibility(cancel_button, name=cancel_name, description=cancel_description)


__all__ = ["set_message_box_button_accessibility"]
