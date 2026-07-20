from __future__ import annotations

from pathlib import Path

from config.runtime_layout import APPLICATION_ROOT


def _resource_roots() -> tuple[Path, ...]:
    roots = [APPLICATION_ROOT, Path.cwd()]
    return tuple(dict.fromkeys(roots))


def resolve_windows11_sidebar_icon_path(file_name: str) -> str:
    clean_name = str(file_name or "").strip()
    if not clean_name:
        return ""

    relative_path = Path("ico") / "windows11_fluent" / "sidebar" / clean_name
    for root in _resource_roots():
        candidate = root / relative_path
        if candidate.exists():
            return str(candidate)
    return ""


__all__ = ["resolve_windows11_sidebar_icon_path"]
