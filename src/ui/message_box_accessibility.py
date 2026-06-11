from __future__ import annotations

from ui.accessibility import set_control_accessibility


def set_message_box_button_accessibility(
    box,
    *,
    yes_name: str,
    yes_description: str,
    cancel_name: str,
    cancel_description: str,
) -> None:
    yes_button = getattr(box, "yesButton", None)
    if yes_button is not None:
        set_control_accessibility(yes_button, name=yes_name, description=yes_description)
    cancel_button = getattr(box, "cancelButton", None)
    if cancel_button is not None:
        set_control_accessibility(cancel_button, name=cancel_name, description=cancel_description)


__all__ = ["set_message_box_button_accessibility"]
