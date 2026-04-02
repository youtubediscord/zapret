from __future__ import annotations

import configparser
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from log import log


_DEFAULT_TEMPLATE_CONTENT = """\
# Preset: Default
# Created: 2026-01-01T00:00:00
# IconColor: #60cdff
# Description: Default Zapret 1 preset

--wf-tcp=443
--wf-udp=443
"""

_DELETED_SECTION = "deleted"


def get_deleted_preset_names_v1() -> set[str]:
    path = _deleted_presets_ini_path()
    try:
        if not path.exists():
            return set()
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        if not cfg.has_section(_DELETED_SECTION):
            return set()
        return {key for key, value in cfg.items(_DELETED_SECTION) if value.strip() == "1"}
    except Exception:
        return set()


def mark_preset_deleted_v1(name: str) -> bool:
    return _write_deleted_flag(name, present=True)


def unmark_preset_deleted_v1(name: str) -> bool:
    return _write_deleted_flag(name, present=False)


def clear_all_deleted_presets_v1() -> bool:
    path = _deleted_presets_ini_path()
    try:
        if not path.exists():
            return True
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        if cfg.has_section(_DELETED_SECTION):
            cfg.remove_section(_DELETED_SECTION)
        with path.open("w", encoding="utf-8") as handle:
            cfg.write(handle)
        return True
    except Exception:
        return False


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
    templates = _load_template_paths()
    if not templates:
        return 0

    presets_dir = _presets_dir_v1()
    deleted_lower = {name.lower() for name in get_deleted_preset_names_v1()}
    copied = 0

    for name, src_path in templates.items():
        if name.lower() in deleted_lower:
            continue
        dest = presets_dir / f"{name}.txt"
        if dest.exists():
            continue
        try:
            content = _normalize_template_header_v1(src_path.read_text(encoding="utf-8", errors="replace"), name)
            dest.write_text(content, encoding="utf-8")
            copied += 1
            unmark_preset_deleted_v1(name)
        except Exception as exc:
            log(f"Failed to copy V1 template '{name}' to presets: {exc}", "DEBUG")

    return copied


def update_changed_v1_templates_in_presets() -> int:
    templates = _load_template_paths()
    if not templates:
        return 0

    presets_dir = _presets_dir_v1()
    backups_dir = presets_dir / "_builtin_version_backups"
    updated = 0

    for name, src_path in templates.items():
        dest = presets_dir / f"{name}.txt"
        if not dest.exists():
            continue
        try:
            template_content = src_path.read_text(encoding="utf-8", errors="replace")
            template_version = _extract_builtin_version(template_content)
            if not template_version:
                continue

            existing_content = dest.read_text(encoding="utf-8", errors="replace")
            existing_version = _extract_builtin_version(existing_content)
            if not _is_newer_builtin_version(template_version, existing_version):
                continue

            try:
                backups_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                from_v = _sanitize_version_for_filename(existing_version)
                to_v = _sanitize_version_for_filename(template_version)
                backup_name = f"{dest.stem}__{timestamp}__{from_v}_to_{to_v}.txt"
                (backups_dir / backup_name).write_text(existing_content, encoding="utf-8")
            except Exception:
                pass

            dest.write_text(_normalize_template_header_v1(template_content, name), encoding="utf-8")
            updated += 1
        except Exception as exc:
            log(f"Failed to update V1 preset '{name}' from template: {exc}", "DEBUG")

    return updated


def overwrite_v1_templates_to_presets() -> tuple[int, int, list[str]]:
    templates = _load_template_paths()
    if not templates:
        return (0, 0, [])

    presets_dir = _presets_dir_v1()
    copied = 0
    failed: list[str] = []

    for name in sorted(templates.keys(), key=lambda value: value.lower()):
        src_path = templates[name]
        dest = presets_dir / f"{name}.txt"
        try:
            content = _normalize_template_header_v1(src_path.read_text(encoding="utf-8", errors="replace"), name)
            dest.write_text(content, encoding="utf-8")
            copied += 1
            unmark_preset_deleted_v1(name)
        except Exception as exc:
            failed.append(name)
            log(f"Failed to overwrite V1 preset '{name}' from template: {exc}", "DEBUG")

    return (copied, len(templates), failed)


def ensure_default_preset_exists_v1() -> bool:
    try:
        ensure_v1_templates_copied_to_presets()
        presets_dir = _presets_dir_v1()
        if (presets_dir / "Default.txt").exists():
            return True
        return next((path for path in sorted(presets_dir.glob("*.txt"), key=lambda item: item.name.lower())), None) is not None
    except Exception as exc:
        log(f"Error ensuring V1 default preset: {exc}", "DEBUG")
        return False


def _write_deleted_flag(name: str, *, present: bool) -> bool:
    path = _deleted_presets_ini_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(path, encoding="utf-8")
        if present:
            if not cfg.has_section(_DELETED_SECTION):
                cfg.add_section(_DELETED_SECTION)
            cfg.set(_DELETED_SECTION, name, "1")
        elif cfg.has_section(_DELETED_SECTION):
            cfg.remove_option(_DELETED_SECTION, name)
        with path.open("w", encoding="utf-8") as handle:
            cfg.write(handle)
        return True
    except Exception:
        return False


def _presets_dir_v1() -> Path:
    try:
        from config import get_zapret_userdata_dir

        base = (get_zapret_userdata_dir() or "").strip()
        if base:
            path = Path(base) / "presets_v1"
            path.mkdir(parents=True, exist_ok=True)
            return path
    except Exception:
        pass

    appdata = (os.environ.get("APPDATA") or "").strip()
    if appdata:
        path = Path(appdata) / "zapret" / "presets_v1"
        path.mkdir(parents=True, exist_ok=True)
        return path
    raise RuntimeError("APPDATA is required for presets_v1 directory")


def _templates_dir_v1() -> Path:
    try:
        from config import get_zapret_presets_v1_template_dir

        return Path(get_zapret_presets_v1_template_dir())
    except Exception:
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            return Path(appdata) / "zapret" / "presets_v1_template"
        raise RuntimeError("APPDATA is required for presets_v1_template directory")


def _deleted_presets_ini_path() -> Path:
    return _presets_dir_v1() / "deleted_presets.ini"


def _load_template_paths() -> dict[str, Path]:
    templates: dict[str, Path] = {}
    tpl_dir = _templates_dir_v1()
    try:
        if tpl_dir.is_dir():
            for path in tpl_dir.glob("*.txt"):
                if path.is_file() and not path.name.startswith("_"):
                    templates[path.stem] = path
    except Exception as exc:
        log(f"Error reading V1 templates dir: {exc}", "DEBUG")
    return templates


def _load_template_contents() -> dict[str, str]:
    contents: dict[str, str] = {}
    for name, path in _load_template_paths().items():
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        contents[clean_name] = _normalize_template_header_v1(content, clean_name)
    return contents


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
        if stripped.startswith("# created:") or stripped.startswith("# iconcolor:") or stripped.startswith("# description:"):
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
