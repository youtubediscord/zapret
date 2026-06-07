"""Accessibility helpers for About help cards."""

from __future__ import annotations

from ui.accessibility import set_control_accessibility


def set_help_card_accessibility(card, *, action_name: str, description: str) -> None:
    """Задаёт понятный текст кликабельной карточке справки."""

    set_control_accessibility(
        card,
        name=action_name,
        description=description,
    )


__all__ = ["set_help_card_accessibility"]
