from __future__ import annotations

from pathlib import Path

from config.runtime_layout import APPLICATION_ROOT, PACKAGED_RUNTIME


def _resource_roots() -> tuple[Path, ...]:
    # В установке ico лежит в корне над `_internal`.
    # Импорты для тестов/сборки читают те же ресурсы из `src`;
    # это не разрешает запуск самого приложения из исходников.
    resource_root = APPLICATION_ROOT if PACKAGED_RUNTIME else APPLICATION_ROOT / "src"
    roots = [resource_root, Path.cwd()]
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
