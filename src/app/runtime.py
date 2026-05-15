from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.features import AppFeatures, build_app_features
from app.state_access import AppStateAccess, build_app_state_access


@dataclass(frozen=True, slots=True)
class AppRuntime:
    paths: Any
    state: AppStateAccess
    features: AppFeatures


def build_app_runtime(*, initial_ui_state=None, host: Any) -> AppRuntime:
    from pathlib import Path

    from config.config import MAIN_DIRECTORY
    from core.paths import AppPaths

    paths = AppPaths(
        user_root=Path(MAIN_DIRECTORY).resolve(),
        local_root=Path(MAIN_DIRECTORY).resolve(),
    )
    state = build_app_state_access(initial_ui_state)
    return AppRuntime(
        paths=paths,
        state=state,
        features=build_app_features(host=host, paths=paths, state=state),
    )
