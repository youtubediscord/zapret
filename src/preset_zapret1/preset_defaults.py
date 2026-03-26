# preset_zapret1/preset_defaults.py
"""Builtin preset templates for Zapret 1.

Template sync flow:
  1. Templates live in %APPDATA%/zapret/presets_v1_template/
  2. ensure_v1_templates_copied_to_presets() copies missing → presets_v1/
  3. ensure_default_preset_exists_v1() guarantees Default exists
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from log import log

_BUILTIN_DIR = Path(__file__).resolve().parent / "builtin_presets"

# Fallback template if builtin file is missing (e.g. PyInstaller, broken install)
_DEFAULT_TEMPLATE_CONTENT = """\
# Preset: Default
# Created: 2026-01-01T00:00:00
# IconColor: #60cdff
# Description: Default Zapret 1 preset

--wf-tcp=443
--wf-udp=443
"""

_TEMPLATES_CACHE_V1: Optional[dict[str, str]] = None
_TEMPLATE_BY_KEY_V1: Optional[dict[str, str]] = None
_CANONICAL_NAME_BY_KEY_V1: Optional[dict[str, str]] = None
_DELETED_SECTION_V1 = "deleted"


def _get_v1_templates_dir() -> Path:
    """Returns the presets_v1_template/ directory path."""
    try:
        from config import get_zapret_presets_v1_template_dir
        return Path(get_zapret_presets_v1_template_dir())
    except Exception:
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            return Path(appdata) / "zapret" / "presets_v1_template"
        return Path.home() / "AppData" / "Roaming" / "zapret" / "presets_v1_template"


def _get_deleted_presets_ini_path_v1() -> Path:
    try:
        from config import get_zapret_userdata_dir

        return Path(get_zapret_userdata_dir()) / "presets_v1" / "deleted_presets.ini"
    except Exception:
        return Path("")


def get_deleted_preset_names_v1() -> set[str]:
    import configparser

    path = _get_deleted_presets_ini_path_v1()
    try:
        if not path.exists():
            return set()
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        if not cfg.has_section(_DELETED_SECTION_V1):
            return set()
        return {k for k, v in cfg.items(_DELETED_SECTION_V1) if v.strip() == "1"}
    except Exception:
        return set()


def mark_preset_deleted_v1(name: str) -> bool:
    import configparser

    path = _get_deleted_presets_ini_path_v1()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(path, encoding="utf-8")
        if not cfg.has_section(_DELETED_SECTION_V1):
            cfg.add_section(_DELETED_SECTION_V1)
        cfg.set(_DELETED_SECTION_V1, name, "1")
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def unmark_preset_deleted_v1(name: str) -> bool:
    import configparser

    path = _get_deleted_presets_ini_path_v1()
    try:
        if not path.exists():
            return True
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        if cfg.has_section(_DELETED_SECTION_V1):
            cfg.remove_option(_DELETED_SECTION_V1, name)
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def clear_all_deleted_presets_v1() -> bool:
    import configparser

    path = _get_deleted_presets_ini_path_v1()
    try:
        if not path.exists():
            return True
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        if cfg.has_section(_DELETED_SECTION_V1):
            cfg.remove_section(_DELETED_SECTION_V1)
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def _load_v1_templates_from_disk() -> dict[str, Path]:
    """Reads *.txt from presets_v1_template/, returns {name: path}."""
    templates: dict[str, Path] = {}
    tpl_dir = _get_v1_templates_dir()
    try:
        if tpl_dir.is_dir():
            for f in tpl_dir.glob("*.txt"):
                if f.is_file() and not f.name.startswith("_"):
                    templates[f.stem] = f
    except Exception as e:
        log(f"Error reading V1 templates dir: {e}", "DEBUG")
    return templates


def _normalize_template_header_v1(content: str, preset_name: str) -> str:
    """Ensures # Preset corresponds to template filename."""
    name = str(preset_name or "").strip()
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    header_end = 0
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            header_end = i
            break
    else:
        header_end = len(lines)

    header = lines[:header_end]
    body = lines[header_end:]

    out_header: list[str] = []
    saw_preset = False
    for raw in header:
        stripped = raw.strip().lower()
        if stripped.startswith("# preset:"):
            out_header.append(f"# Preset: {name}")
            saw_preset = True
            continue
        if stripped.startswith("# builtinversion:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if stripped.startswith("# created:") or stripped.startswith("# modified:") or stripped.startswith("# iconcolor:") or stripped.startswith("# description:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if stripped.startswith("#"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {name}")

    return "\n".join(out_header + body).rstrip("\n") + "\n"


def _load_v1_template_contents_from_disk() -> dict[str, str]:
    """Reads normalized template contents from presets_v1_template/*.txt."""
    templates: dict[str, str] = {}
    for name, path in _load_v1_templates_from_disk().items():
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        templates[clean_name] = _normalize_template_header_v1(content, clean_name)
    return templates


def invalidate_templates_cache_v1() -> None:
    global _TEMPLATES_CACHE_V1, _TEMPLATE_BY_KEY_V1, _CANONICAL_NAME_BY_KEY_V1
    _TEMPLATES_CACHE_V1 = None
    _TEMPLATE_BY_KEY_V1 = None
    _CANONICAL_NAME_BY_KEY_V1 = None


def _ensure_templates_loaded_v1() -> None:
    global _TEMPLATES_CACHE_V1, _TEMPLATE_BY_KEY_V1, _CANONICAL_NAME_BY_KEY_V1

    if _TEMPLATES_CACHE_V1 is None:
        templates = _load_v1_template_contents_from_disk()
        _TEMPLATES_CACHE_V1 = {k: templates[k] for k in sorted(templates.keys(), key=lambda s: s.lower())}
        _TEMPLATE_BY_KEY_V1 = {
            canonical.lower(): content for canonical, content in _TEMPLATES_CACHE_V1.items()
        }
        _CANONICAL_NAME_BY_KEY_V1 = {
            canonical.lower(): canonical for canonical in _TEMPLATES_CACHE_V1.keys()
        }
        return

    if _TEMPLATE_BY_KEY_V1 is None:
        _TEMPLATE_BY_KEY_V1 = {
            canonical.lower(): content for canonical, content in (_TEMPLATES_CACHE_V1 or {}).items()
        }
    if _CANONICAL_NAME_BY_KEY_V1 is None:
        _CANONICAL_NAME_BY_KEY_V1 = {
            canonical.lower(): canonical for canonical in (_TEMPLATES_CACHE_V1 or {}).keys()
        }


def get_template_content_v1(name: str) -> Optional[str]:
    """Returns template content from presets_v1_template/ by name (case-insensitive)."""
    _ensure_templates_loaded_v1()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_TEMPLATE_BY_KEY_V1 or {}).get(key)


def get_template_canonical_name_v1(name: str) -> Optional[str]:
    """Returns canonical template name from presets_v1_template/ (case-insensitive)."""
    _ensure_templates_loaded_v1()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_CANONICAL_NAME_BY_KEY_V1 or {}).get(key)


def get_default_template_name_v1() -> Optional[str]:
    """Returns default template name from presets_v1_template/ if available."""
    canonical = get_template_canonical_name_v1("Default")
    if canonical:
        return canonical
    _ensure_templates_loaded_v1()
    names = sorted((_TEMPLATES_CACHE_V1 or {}).keys(), key=lambda s: s.lower())
    return names[0] if names else None


def get_default_template_content_v1() -> Optional[str]:
    """Returns default template content from presets_v1_template/ if available."""
    name = get_default_template_name_v1()
    if not name:
        return None
    return get_template_content_v1(name)


def get_builtin_base_from_copy_name_v1(name: str) -> Optional[str]:
    """Returns canonical base template name for '(...копия N)' names."""
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
    return get_template_canonical_name_v1(base)


def ensure_v1_templates_copied_to_presets() -> int:
    """Copy missing templates from presets_v1_template/ → presets_v1/.

    Only copies files that do NOT already exist in presets_v1/.
    Returns number of files copied.
    """
    from .preset_storage import get_presets_dir_v1

    templates = _load_v1_templates_from_disk()
    if not templates:
        return 0

    presets_dir = get_presets_dir_v1()
    deleted_lower = {name.lower() for name in get_deleted_preset_names_v1()}
    copied = 0
    for name, src_path in templates.items():
        if name.lower() in deleted_lower:
            continue
        dest = presets_dir / f"{name}.txt"
        if not dest.exists():
            try:
                shutil.copy2(str(src_path), str(dest))
                copied += 1
                try:
                    unmark_preset_deleted_v1(name)
                except Exception:
                    pass
            except Exception as e:
                log(f"Failed to copy V1 template '{name}' to presets: {e}", "DEBUG")

    if copied:
        log(f"Copied {copied} V1 templates to {presets_dir}", "DEBUG")
    return copied


def update_changed_v1_templates_in_presets() -> int:
    """Update existing presets in presets_v1/ when template BuiltinVersion is strictly newer.

    Only updates presets whose template carries a `# BuiltinVersion:` header
    with a version strictly greater than the one in the user's file
    (missing version = 0, so any versioned template triggers the first update).

    User-created presets (names not matching any builtin template) are never
    touched.  Before overwriting, the old file is backed up to
    presets_v1/_builtin_version_backups/.

    If the updated preset is the currently active one, preset-zapret1.txt is
    also refreshed immediately.

    Returns number of files updated.
    """
    from .preset_storage import (
        get_presets_dir_v1,
        get_active_preset_name_v1,
        get_active_preset_path_v1,
    )
    from preset_zapret2.preset_defaults import (
        _extract_builtin_version,
        _is_newer_builtin_version,
        _sanitize_version_for_filename,
    )

    invalidate_templates_cache_v1()

    templates = _load_v1_templates_from_disk()
    if not templates:
        return 0

    presets_dir = get_presets_dir_v1()
    backups_dir = presets_dir / "_builtin_version_backups"
    active_name = (get_active_preset_name_v1() or "").strip().lower()
    updated = 0

    for name, src_path in templates.items():
        dest = presets_dir / f"{name}.txt"
        if not dest.exists():
            continue  # New file — handled by ensure_v1_templates_copied_to_presets

        try:
            template_content = src_path.read_text(encoding="utf-8", errors="replace")
            template_version = _extract_builtin_version(template_content)

            if not template_version:
                continue  # No BuiltinVersion in template → never auto-update

            existing_content = dest.read_text(encoding="utf-8", errors="replace")
            existing_version = _extract_builtin_version(existing_content)

            if not _is_newer_builtin_version(template_version, existing_version):
                continue  # Template not strictly newer → skip

            # Backup old file before overwriting.
            try:
                backups_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                from_v = _sanitize_version_for_filename(existing_version)
                to_v = _sanitize_version_for_filename(template_version)
                backup_name = f"{dest.stem}__{timestamp}__{from_v}_to_{to_v}.txt"
                (backups_dir / backup_name).write_text(existing_content, encoding="utf-8")
            except Exception:
                pass

            shutil.copy2(str(src_path), str(dest))
            updated += 1
            log(f"V1 preset '{name}' updated to BuiltinVersion {template_version}", "INFO")

            # If this preset is currently active, sync preset-zapret1.txt too.
            if active_name and active_name == name.lower():
                try:
                    active_path = get_active_preset_path_v1()
                    shutil.copy2(str(src_path), str(active_path))
                    log(f"V1 active file synced for updated preset '{name}'", "DEBUG")
                except Exception:
                    pass

        except Exception as e:
            log(f"Failed to update V1 preset '{name}' from template: {e}", "DEBUG")

    if updated:
        log(f"Updated {updated} V1 preset(s) from builtin templates", "INFO")
    return updated


def overwrite_v1_templates_to_presets() -> tuple[int, int, list[str]]:
    """Copy all templates from presets_v1_template/ -> presets_v1/ with overwrite.

    Every template file is copied even if destination already exists.
    Returns (copied_count, total_templates, failed_template_names).
    """
    from .preset_storage import get_presets_dir_v1

    templates = _load_v1_templates_from_disk()
    if not templates:
        return (0, 0, [])

    presets_dir = get_presets_dir_v1()
    copied = 0
    failed: list[str] = []

    for name in sorted(templates.keys(), key=lambda s: s.lower()):
        src_path = templates[name]
        dest = presets_dir / f"{name}.txt"
        try:
            shutil.copy2(str(src_path), str(dest))
            copied += 1
            try:
                unmark_preset_deleted_v1(name)
            except Exception:
                pass
        except Exception as e:
            failed.append(name)
            log(f"Failed to overwrite V1 preset '{name}' from template: {e}", "DEBUG")

    if copied:
        log(f"Overwrote {copied}/{len(templates)} V1 presets from templates in {presets_dir}", "DEBUG")
    return (copied, len(templates), failed)


def get_builtin_preset_content_v1(name: str) -> Optional[str]:
    """Returns template content by name.

    Source priority:
    1) External presets_v1_template/ (source of truth)
    2) Embedded default fallback for "Default"
    """
    # External templates (source of truth)
    content = get_template_content_v1(name)
    if content:
        return content

    # Self-healing: return hardcoded default if file missing
    if name.lower() == "default":
        return _normalize_template_header_v1(_DEFAULT_TEMPLATE_CONTENT, "Default")
    return None


def get_default_builtin_preset_name_v1() -> Optional[str]:
    """Returns name of the default builtin preset."""
    template_name = get_default_template_name_v1()
    return template_name


def get_all_builtin_preset_names_v1() -> list[str]:
    """Returns sorted list of all builtin preset names (excluding Default)."""
    _ensure_templates_loaded_v1()
    template_names = sorted((_TEMPLATES_CACHE_V1 or {}).keys(), key=lambda s: s.lower())
    return [n for n in template_names if n.lower() != "default"]


def ensure_default_preset_exists_v1() -> bool:
    """Ensures presets_v1/ is populated and Default preset exists.

    Flow:
      1. Copy missing templates from presets_v1_template/ → presets_v1/
      2. If Default still missing, create from embedded fallback

    Returns True if Default preset exists or was created successfully.
    """
    try:
        from core.services import get_direct_flow_coordinator

        get_direct_flow_coordinator().ensure_launch_profile(
            "direct_zapret1",
            require_filters=False,
        )
        return True
    except Exception as e:
        log(f"Error ensuring direct_zapret1 launch config: {e}", "DEBUG")
        return False
