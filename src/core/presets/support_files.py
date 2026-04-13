from __future__ import annotations

from core.paths import AppPaths
from .z2_template_runtime import ensure_templates_copied_to_presets
from .v1_template_runtime import ensure_v1_templates_copied_to_presets, update_changed_v1_templates_in_presets


def prepare_direct_support_files(launch_method: str, app_paths: AppPaths) -> None:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        _prepare_direct_zapret2_support_files(app_paths)
        return
    if method == "direct_zapret1":
        _prepare_direct_zapret1_support_files()
        return
    raise ValueError(f"Unsupported direct launch method: {launch_method}")


def _prepare_direct_zapret2_support_files(app_paths: AppPaths) -> None:
    presets_dir = app_paths.engine_paths("winws2").ensure_directories().presets_dir
    presets_dir.mkdir(parents=True, exist_ok=True)

    ensure_templates_copied_to_presets()


def _prepare_direct_zapret1_support_files() -> None:
    update_changed_v1_templates_in_presets()
    ensure_v1_templates_copied_to_presets()
