from __future__ import annotations

from pathlib import Path

from .builtin_template_sync import (
    is_builtin_preset_file_name as _is_builtin_preset_file_name,
    load_repo_builtin_templates,
)
from .z2_template_runtime import (
    _normalize_template_header_v2,
)


def list_repo_builtin_templates_v2() -> dict[str, str]:
    return load_repo_builtin_templates(
        _repo_builtin_templates_dir_v2(),
        normalize_content=_normalize_template_header_v2,
    )


def list_builtin_catalog_names_v2() -> list[str]:
    repo_templates = list_repo_builtin_templates_v2()
    return sorted(repo_templates.keys(), key=lambda value: value.lower())


def is_builtin_preset_file_name_v2(file_name: str) -> bool:
    return _is_builtin_preset_file_name(file_name, list_builtin_catalog_names_v2())


def _repo_builtin_templates_dir_v2() -> Path:
    return Path(__file__).resolve().parent / "builtin" / "winws2"
