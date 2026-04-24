from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .builtin_template_sync import load_repo_builtin_templates
from log.log import log



_DEFAULT_TEMPLATE_CONTENT = """\
# Preset: Default
# IconColor: #60cdff
# Description: Default Zapret 1 preset

--wf-tcp=443
--wf-udp=443
"""

def get_template_content_v1(name: str) -> Optional[str]:
    key = str(name or "").strip().lower()
    if not key:
        return None
    for canonical, content in _load_template_contents().items():
        if canonical.lower() == key:
            return content
    return None


def get_template_canonical_name_v1(name: str) -> Optional[str]:
    key = str(name or "").strip().lower()
    if not key:
        return None
    for canonical in _load_template_contents().keys():
        if canonical.lower() == key:
            return canonical
    return None


def get_default_template_content_v1() -> Optional[str]:
    canonical = get_template_canonical_name_v1("Default")
    if canonical:
        return get_template_content_v1(canonical)
    contents = _load_template_contents()
    if contents:
        first_name = sorted(contents.keys(), key=lambda value: value.lower())[0]
        return contents[first_name]
    return None


def get_builtin_preset_content_v1(name: str) -> Optional[str]:
    content = get_template_content_v1(name)
    if content:
        return content
    if str(name or "").strip().lower() == "default":
        return _normalize_template_header_v1(_DEFAULT_TEMPLATE_CONTENT, "Default")
    return None


def get_builtin_base_from_copy_name_v1(name: str) -> Optional[str]:
    raw = str(name or "").strip()
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
    return get_template_canonical_name_v1(base)


def ensure_v1_templates_copied_to_presets() -> int:
    return 0


def update_changed_v1_templates_in_presets() -> int:
    return 0


def reset_user_overrides_to_builtin_v1() -> tuple[int, int, list[str]]:
    templates = _load_template_contents()
    if not templates:
        return (0, 0, [])

    presets_dir = _user_presets_dir_v1()
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
            log(f"Failed to reset V1 user override '{name}' to built-in: {exc}", "DEBUG")

    return (removed, len(templates), failed)


def overwrite_v1_templates_to_presets() -> tuple[int, int, list[str]]:
    return reset_user_overrides_to_builtin_v1()


def ensure_default_preset_exists_v1() -> bool:
    try:
        presets_dir = _builtin_presets_dir_v1()
        if (presets_dir / "Default v1 (game filter).txt").exists():
            return True
        return next((path for path in sorted(presets_dir.glob("*.txt"), key=lambda item: item.name.lower())), None) is not None
    except Exception as exc:
        log(f"Error ensuring V1 default preset: {exc}", "DEBUG")
        return False

def _user_presets_dir_v1() -> Path:
    try:
        from config.config import get_presets_v1_dir

        path = Path(get_presets_v1_dir())
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception as exc:
        raise RuntimeError("Не удалось определить корень программы для presets_v1") from exc


def _builtin_presets_dir_v1() -> Path:
    try:
        from config.config import get_builtin_presets_v1_dir

        path = Path(get_builtin_presets_v1_dir())
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception as exc:
        raise RuntimeError("Не удалось определить корень программы для presets_v1_builtin") from exc


def _load_template_contents() -> dict[str, str]:
    try:
        return load_repo_builtin_templates(
            _builtin_presets_dir_v1(),
            normalize_content=_normalize_template_header_v1,
        )
    except Exception as exc:
        log(f"Error reading V1 built-in templates: {exc}", "DEBUG")
        return {}


def _normalize_template_header_v1(content: str, preset_name: str) -> str:
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
        if stripped.startswith("# builtinversion:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if stripped.startswith("# modified:"):
            continue
        if stripped.startswith("# iconcolor:") or stripped.startswith("# description:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if stripped.startswith("#"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {name}")
    if not saw_template_origin:
        insert_at = 1 if out_header and out_header[0].startswith("# Preset:") else 0
        out_header.insert(insert_at, f"# TemplateOrigin: {name}")

    return "\n".join(out_header + body).rstrip("\n") + "\n"


_BUILTIN_VERSION_RE = re.compile(r"^\s*#\s*BuiltinVersion:\s*(.+?)\s*$", re.IGNORECASE)


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
