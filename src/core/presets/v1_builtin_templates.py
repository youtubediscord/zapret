from __future__ import annotations

from pathlib import Path
from log.log import log

from .builtin_template_sync import (
    is_builtin_preset_file_name as _is_builtin_preset_file_name,
    load_repo_builtin_templates,
)
from .v1_template_runtime import (
    _normalize_template_header_v1,
)


def list_repo_builtin_templates_v1() -> dict[str, str]:
    try:
        repo_dir = _repo_builtin_templates_dir_v1()
    except Exception as exc:
        log(f"V1 built-in repo templates unavailable, using installed runtime templates only: {exc}", "DEBUG")
        return {}

    return load_repo_builtin_templates(
        repo_dir,
        normalize_content=_normalize_template_header_v1,
    )


def list_builtin_catalog_names_v1() -> list[str]:
    repo_templates = list_repo_builtin_templates_v1()
    return sorted(repo_templates.keys(), key=lambda value: value.lower())


def is_builtin_preset_file_name_v1(file_name: str) -> bool:
    return _is_builtin_preset_file_name(file_name, list_builtin_catalog_names_v1())


def _repo_builtin_templates_dir_v1() -> Path:
    return Path(__file__).resolve().parent / "builtin" / "winws1"
