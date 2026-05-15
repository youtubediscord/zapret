from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.state_store import AppRuntimeState
    from app.state_store import AppUiState
    from app.state_store import MainWindowStateStore


@dataclass(frozen=True, slots=True)
class AppStateAccess:
    """Короткий доступ к состоянию приложения без чтения полей окна."""

    ui: "MainWindowStateStore"
    runtime: "AppRuntimeState"


def build_app_state_access(initial_ui_state: "AppUiState | None" = None) -> AppStateAccess:
    from app.state_store import AppRuntimeState, AppUiState, MainWindowStateStore

    ui_store = MainWindowStateStore(initial_ui_state or AppUiState())
    return AppStateAccess(
        ui=ui_store,
        runtime=AppRuntimeState(ui_store),
    )
