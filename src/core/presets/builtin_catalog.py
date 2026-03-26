from __future__ import annotations

from pathlib import Path


def list_builtin_presets(directory: Path) -> list[Path]:
    base = Path(directory)
    if not base.exists():
        return []
    return sorted([path for path in base.glob("*.txt") if path.is_file()], key=lambda item: item.name.lower())
