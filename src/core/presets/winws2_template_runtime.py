from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .builtin_template_sync import load_repo_builtin_templates
from log.log import log



_TEMPLATES_CACHE: Optional[dict[str, str]] = None
_TEMPLATE_BY_KEY: Optional[dict[str, str]] = None
_CANONICAL_NAME_BY_KEY: Optional[dict[str, str]] = None
_BUILTIN_VERSION_RE = re.compile(r"^\s*#\s*BuiltinVersion:\s*(.+?)\s*$", re.IGNORECASE)


def invalidate_winws2_templates_cache() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY
    _TEMPLATES_CACHE = None
    _TEMPLATE_BY_KEY = None
    _CANONICAL_NAME_BY_KEY = None


def get_template_content_winws2(name: str) -> Optional[str]:
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_TEMPLATE_BY_KEY or {}).get(key)


def get_template_canonical_name_winws2(name: str) -> Optional[str]:
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_CANONICAL_NAME_BY_KEY or {}).get(key)


def get_default_template_content_winws2() -> Optional[str]:
    canonical = get_template_canonical_name_winws2("Default")
    if canonical:
        return get_template_content_winws2(canonical)
    names = sorted((_TEMPLATES_CACHE or {}).keys(), key=lambda value: value.lower())
    if names:
        return (_TEMPLATES_CACHE or {}).get(names[0])
    return None


def get_builtin_base_from_copy_name_winws2(name: str) -> Optional[str]:
    raw = (name or "").strip()
    if not raw:
        return None
    copy_suffix_re = re.compile(r"\s+\(копия(?:\s+\d+)?\)\s*$", re.IGNORECASE)
    base = raw
    changed = False
    while True:
        stripped = copy_suffix_re.sub("", base).strip()
        if stripped == base:
            break
        base = stripped
        changed = True
    if not changed or not base:
        return None
    return get_template_canonical_name_winws2(base)

def ensure_winws2_templates_copied_to_presets() -> bool:
    return True


def reset_user_overrides_to_builtin_winws2() -> tuple[int, int, list[str]]:
    templates = _load_template_contents()
    if not templates:
        return (0, 0, [])

    presets_dir = _user_presets_dir_winws2()
    removed = 0
    failed: list[str] = []
    for name in sorted(templates.keys(), key=lambda value: value.lower()):
        dest = presets_dir / f"{name}.txt"
        if not dest.exists():
            continue
        try:
            dest.unlink()
            removed += 1
        except Exception as exc:
            failed.append(name)
            log(f"Failed to reset winws2 user override '{name}' to built-in: {exc}", "DEBUG")
    return (removed, len(templates), failed)


def overwrite_winws2_templates_to_presets() -> tuple[int, int, list[str]]:
    return reset_user_overrides_to_builtin_winws2()


def _ensure_templates_loaded() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY
    if _TEMPLATES_CACHE is not None:
        return
    templates = _load_template_contents()
    _TEMPLATES_CACHE = {key: templates[key] for key in sorted(templates.keys(), key=lambda value: value.lower())}
    _TEMPLATE_BY_KEY = {canonical.lower(): content for canonical, content in _TEMPLATES_CACHE.items()}
    _CANONICAL_NAME_BY_KEY = {canonical.lower(): canonical for canonical in _TEMPLATES_CACHE.keys()}


def _load_template_contents() -> dict[str, str]:
    return load_repo_builtin_templates(
        _builtin_presets_dir_winws2(),
        normalize_content=_normalize_template_header_winws2,
    )


def _user_presets_dir_winws2() -> Path:
    from config.config import get_presets_v2_dir

    path = Path(get_presets_v2_dir())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _builtin_presets_dir_winws2() -> Path:
    from config.config import get_builtin_presets_v2_dir

    path = Path(get_builtin_presets_v2_dir())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_template_header_winws2(content: str, preset_name: str) -> str:
    name = str(preset_name or "").strip()
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    header_end = 0
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            header_end = index
            break
    else:
        header_end = len(lines)

    header = lines[:header_end]
    body = lines[header_end:]
    out_header: list[str] = []
    saw_preset = False
    saw_template_origin = False

    for raw in header:
        stripped = raw.strip().lower()
        if stripped.startswith("# preset:"):
            out_header.append(f"# Preset: {name}")
            saw_preset = True
            continue
        if stripped.startswith("# templateorigin:"):
            out_header.append(f"# TemplateOrigin: {name}")
            saw_template_origin = True
            continue
        if stripped.startswith("# modified:") or stripped.startswith("# activepreset:") or stripped.startswith("# created:"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {name}")
    if not saw_template_origin:
        insert_at = 1 if out_header and out_header[0].startswith("# Preset:") else 0
        out_header.insert(insert_at, f"# TemplateOrigin: {name}")

    return "\n".join(out_header + body).rstrip("\n") + "\n"

def _extract_builtin_version(content: str) -> Optional[str]:
    for raw in (content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("#"):
            break
        match = _BUILTIN_VERSION_RE.match(raw)
        if match:
            value = (match.group(1) or "").strip()
            return value or None
    return None


def _version_to_tuple(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return tuple()
    chunks = re.findall(r"\d+", version)
    if not chunks:
        return tuple()
    try:
        return tuple(int(chunk) for chunk in chunks)
    except Exception:
        return tuple()


def _is_newer_builtin_version(candidate: Optional[str], current: Optional[str]) -> bool:
    left = _version_to_tuple(candidate)
    right = _version_to_tuple(current)
    if not left:
        return False
    if not right:
        return True
    max_len = max(len(left), len(right))
    left = left + (0,) * (max_len - len(left))
    right = right + (0,) * (max_len - len(right))
    return left > right


def _sanitize_version_for_filename(version: Optional[str]) -> str:
    raw = (version or "none").strip() or "none"
    sanitized = re.sub(r"[^0-9A-Za-z._-]+", "_", raw)
    return sanitized[:48] or "none"
