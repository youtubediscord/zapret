from __future__ import annotations

from pathlib import Path
from log.log import log

from .builtin_template_sync import (
    is_builtin_preset_file_name as _is_builtin_preset_file_name,
    load_repo_builtin_templates,
)
from .winws1_template_runtime import (
    _normalize_template_header_winws1,
)


def list_repo_builtin_templates_winws1() -> dict[str, str]:
    try:
        repo_dir = _repo_builtin_templates_dir_winws1()
    except Exception as exc:
        log(f"winws1 built-in repo templates unavailable, using installed runtime templates only: {exc}", "DEBUG")
        return {}

    return load_repo_builtin_templates(
        repo_dir,
        normalize_content=_normalize_template_header_winws1,
    )


def list_builtin_catalog_names_winws1() -> list[str]:
    repo_templates = list_repo_builtin_templates_winws1()
    return sorted(repo_templates.keys(), key=lambda value: value.lower())


def is_builtin_preset_file_name_winws1(file_name: str) -> bool:
    return _is_builtin_preset_file_name(file_name, list_builtin_catalog_names_winws1())


def _repo_builtin_templates_dir_winws1() -> Path:
    return Path(__file__).resolve().parent / "builtin" / "winws1"
