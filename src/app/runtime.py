from __future__ import annotations

from dataclasses import dataclass
import time as _time
from typing import Any, Callable

from app.feature_assembly import build_app_features
from app.features import AppFeatures
from app.state_access import AppStateAccess, build_app_state_access
from main.runtime_state import log_startup_metric as emit_startup_metric


@dataclass(frozen=True, slots=True)
class AppRuntime:
    paths: Any
    state: AppStateAccess
    features: AppFeatures


def build_app_runtime(*, initial_ui_state=None, feature_deps_factory: Callable[[AppStateAccess], Any]) -> AppRuntime:
    from config.runtime_layout import APPLICATION_PATHS
    from core.paths import AppPaths

    t_paths = _time.perf_counter()
    paths = AppPaths(
        user_root=APPLICATION_PATHS.root,
        local_root=APPLICATION_PATHS.root,
    )
    emit_startup_metric(
        "StartupAppRuntimePaths",
        f"{(_time.perf_counter() - t_paths) * 1000:.0f}ms",
    )
    t_state = _time.perf_counter()
    state = build_app_state_access(initial_ui_state)
    emit_startup_metric(
        "StartupAppRuntimeStateAccess",
        f"{(_time.perf_counter() - t_state) * 1000:.0f}ms",
    )
    t_deps = _time.perf_counter()
    feature_deps = feature_deps_factory(state)
    emit_startup_metric(
        "StartupAppRuntimeFeatureDeps",
        f"{(_time.perf_counter() - t_deps) * 1000:.0f}ms",
    )
    t_features = _time.perf_counter()
    features = build_app_features(deps=feature_deps, paths=paths, state=state)
    emit_startup_metric(
        "StartupAppRuntimeFeatures",
        f"{(_time.perf_counter() - t_features) * 1000:.0f}ms",
    )
    return AppRuntime(
        paths=paths,
        state=state,
        features=features,
    )
