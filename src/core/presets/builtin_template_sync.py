from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .builtin_catalog import list_builtin_presets


def list_repo_builtin_template_paths(src_dir: Path) -> list[Path]:
    base = Path(src_dir)
    if not base.exists() or not base.is_dir():
        return []
    return [
        path
        for path in list_builtin_presets(base)
        if path.is_file() and not path.name.startswith("_")
    ]


def load_repo_builtin_templates(
    src_dir: Path,
    *,
    normalize_content: Callable[[str, str], str],
) -> dict[str, str]:
    contents: dict[str, str] = {}
    for path in list_repo_builtin_template_paths(src_dir):
        name = str(path.stem or "").strip()
        if not name:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        contents[name] = normalize_content(raw, name)
    return contents


def is_builtin_preset_file_name(file_name: str, builtin_names: Iterable[str]) -> bool:
    candidate = str(Path(str(file_name or "").strip()).stem or "").strip()
    if not candidate:
        return False
    candidate_key = candidate.casefold()
    return any(str(name or "").strip().casefold() == candidate_key for name in builtin_names)
