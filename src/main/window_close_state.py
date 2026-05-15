from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WindowCloseState:
    """Состояние сценария закрытия главного окна."""

    is_exiting: bool = False
    stop_dpi_on_exit: bool = False
    closing_completely: bool = False
