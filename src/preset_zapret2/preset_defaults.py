# preset_zapret2/preset_defaults.py
"""Preset templates management.

Templates are stored in `%APPDATA%/zapret/presets_v2_template/*.txt`.
They serve as the source-of-truth for preset reset operations.
Editable copies live in `%APPDATA%/zapret/presets_v2/*.txt`.

At startup, templates are synced into presets_v2/.
Missing presets are recreated, and existing presets can be force-updated
when template `# BuiltinVersion` is newer.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from safe_construct import safe_construct

_TEMPLATES_CACHE: Optional[dict[str, str]] = None
_TEMPLATE_BY_KEY: Optional[dict[str, str]] = None
_CANONICAL_NAME_BY_KEY: Optional[dict[str, str]] = None

_BUILTIN_VERSION_RE = re.compile(r"^\s*#\s*BuiltinVersion:\s*(.+?)\s*$", re.IGNORECASE)


def _extract_builtin_version(content: str) -> Optional[str]:
    """Extracts `# BuiltinVersion: X.Y` from preset header."""
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
        return tuple(int(x) for x in chunks)
    except Exception:
        return tuple()


def _is_newer_builtin_version(candidate: Optional[str], current: Optional[str]) -> bool:
    """Returns True when candidate version is strictly newer than current."""
    c = _version_to_tuple(candidate)
    cur = _version_to_tuple(current)
    if not c:
        return False
    if not cur:
        return True

    max_len = max(len(c), len(cur))
    c = c + (0,) * (max_len - len(c))
    cur = cur + (0,) * (max_len - len(cur))
    return c > cur


def _sanitize_version_for_filename(version: Optional[str]) -> str:
    raw = (version or "none").strip() or "none"
    sanitized = re.sub(r"[^0-9A-Za-z._-]+", "_", raw)
    return sanitized[:48] or "none"


def _template_sanity_ok(text: str) -> bool:
    """Quick sanity checks to skip obviously broken/truncated templates."""
    s = (text or "").strip()
    if not s:
        return False
    if "--lua-init=" not in s:
        return False
    if "--filter-" not in s:
        return False
    return True


def _normalize_template_header(content: str, preset_name: str) -> str:
    """Ensure # Preset matches the filename-derived name."""
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
        stripped = raw.strip()
        low = stripped.lower()
        if low.startswith("# preset:"):
            out_header.append(f"# Preset: {name}")
            saw_preset = True
            continue
        if low.startswith("# builtinversion:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if low.startswith("# created:") or low.startswith("# modified:") or low.startswith("# iconcolor:") or low.startswith("# description:"):
            out_header.append(raw.rstrip("\n"))
            continue
        if stripped.startswith("#"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {name}")

    return "\n".join(out_header + body).rstrip("\n") + "\n"


def _get_templates_dir() -> Path:
    """Returns path to presets_v2_template/ directory."""
    try:
        from config import get_zapret_presets_v2_template_dir
        return Path(get_zapret_presets_v2_template_dir())
    except Exception:
        return Path("")


def _load_templates_from_disk() -> dict[str, str]:
    """Loads templates from `%APPDATA%/zapret/presets_v2_template/*.txt`."""
    templates: dict[str, str] = {}

    templates_dir = _get_templates_dir()
    if not templates_dir.exists() or not templates_dir.is_dir():
        try:
            from log import log
            log(f"Preset templates directory not found: {templates_dir}", "ERROR")
        except Exception:
            pass
        return templates

    for file_path in sorted(templates_dir.glob("*.txt"), key=lambda p: p.name.lower()):
        raw_name = (file_path.stem or "").strip()
        name = raw_name
        if not name or name.startswith("_"):
            continue

        # Normalize core names to avoid case-related duplicates.
        low = name.lower()
        if low == "default":
            name = "Default"
        elif low == "gaming":
            name = "Gaming"

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        content = _normalize_template_header(content, name)
        if not _template_sanity_ok(content):
            continue

        templates[name] = content

    return templates


def invalidate_templates_cache() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY
    _TEMPLATES_CACHE = None
    _TEMPLATE_BY_KEY = None
    _CANONICAL_NAME_BY_KEY = None


# Keep old name as alias for compatibility during transition.
invalidate_builtin_preset_templates_cache = invalidate_templates_cache


def _ensure_templates_loaded() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY

    if _TEMPLATES_CACHE is None:
        templates = _load_templates_from_disk()
        _TEMPLATES_CACHE = {k: templates[k] for k in sorted(templates.keys(), key=lambda s: s.lower())}
        _TEMPLATE_BY_KEY = {
            canonical.lower(): content for canonical, content in _TEMPLATES_CACHE.items()
        }
        _CANONICAL_NAME_BY_KEY = {
            canonical.lower(): canonical for canonical in _TEMPLATES_CACHE.keys()
        }
        return

    if _TEMPLATE_BY_KEY is None:
        _TEMPLATE_BY_KEY = {
            canonical.lower(): content for canonical, content in (_TEMPLATES_CACHE or {}).items()
        }
    if _CANONICAL_NAME_BY_KEY is None:
        _CANONICAL_NAME_BY_KEY = {
            canonical.lower(): canonical for canonical in (_TEMPLATES_CACHE or {}).keys()
        }


def get_preset_templates() -> dict[str, str]:
    """Returns all preset templates {name: content}."""
    _ensure_templates_loaded()
    return _TEMPLATES_CACHE or {}


# Aliases for backward compatibility (other modules may still call these).
get_builtin_preset_templates = get_preset_templates


def get_preset_template_names() -> list[str]:
    """Returns sorted list of template names."""
    templates = get_preset_templates()
    return sorted(set(templates.keys()), key=lambda s: s.lower())


get_builtin_preset_names = get_preset_template_names


def get_template_content(name: str) -> Optional[str]:
    """Returns template content by name (case-insensitive)."""
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_TEMPLATE_BY_KEY or {}).get(key)


# Alias
get_builtin_preset_content = get_template_content


def get_template_canonical_name(name: str) -> Optional[str]:
    """Returns canonical template name (case-insensitive lookup)."""
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_CANONICAL_NAME_BY_KEY or {}).get(key)


get_builtin_preset_canonical_name = get_template_canonical_name


def has_template(name: str) -> bool:
    """Checks if a template with this name exists."""
    return get_template_canonical_name(name) is not None


# Alias (old code calls is_builtin_preset_name)
is_builtin_preset_name = has_template


def get_default_template_name() -> Optional[str]:
    """Returns the preferred default template name.

    Preference order:
    1) "Default" (if present)
    2) First template name in sorted order
    """
    canonical = get_template_canonical_name("Default")
    if canonical:
        return canonical
    names = get_preset_template_names()
    return names[0] if names else None


get_default_builtin_preset_name = get_default_template_name


def get_default_template_content() -> Optional[str]:
    name = get_default_template_name()
    if not name:
        return None
    return get_template_content(name)


get_default_builtin_preset_content = get_default_template_content


# ── Deleted presets tracking ──────────────────────────────────────────────

_DELETED_SECTION = "deleted"


def _get_deleted_presets_ini_path() -> Path:
    """Path to deleted_presets.ini inside presets_v2/ directory."""
    try:
        from config import get_zapret_presets_v2_dir
        return Path(get_zapret_presets_v2_dir()) / "deleted_presets.ini"
    except Exception:
        return Path("")


def get_deleted_preset_names() -> set[str]:
    """Returns set of preset names that user explicitly deleted."""
    import configparser
    path = _get_deleted_presets_ini_path()
    try:
        if not path.exists():
            return set()
        cfg = safe_construct(configparser.ConfigParser)
        cfg.read(path, encoding="utf-8")
        if not cfg.has_section(_DELETED_SECTION):
            return set()
        return {k for k, v in cfg.items(_DELETED_SECTION) if v.strip() == "1"}
    except Exception:
        return set()


def mark_preset_deleted(name: str) -> bool:
    """Records a preset name as deleted so it won't be auto-recreated from template."""
    import configparser
    import os
    path = _get_deleted_presets_ini_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cfg = safe_construct(configparser.ConfigParser)
        if path.exists():
            cfg.read(path, encoding="utf-8")
        if not cfg.has_section(_DELETED_SECTION):
            cfg.add_section(_DELETED_SECTION)
        cfg.set(_DELETED_SECTION, name, "1")
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def unmark_preset_deleted(name: str) -> bool:
    """Removes a preset from the deleted list."""
    import configparser
    path = _get_deleted_presets_ini_path()
    try:
        if not path.exists():
            return True
        cfg = safe_construct(configparser.ConfigParser)
        cfg.read(path, encoding="utf-8")
        if cfg.has_section(_DELETED_SECTION):
            cfg.remove_option(_DELETED_SECTION, name)
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def clear_all_deleted_presets() -> bool:
    """Clears the entire deleted presets list (restore all)."""
    import configparser
    path = _get_deleted_presets_ini_path()
    try:
        if not path.exists():
            return True
        cfg = safe_construct(configparser.ConfigParser)
        if cfg.has_section(_DELETED_SECTION):
            cfg.remove_section(_DELETED_SECTION)
        with path.open("w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


# ── Ensure templates are copied to presets ────────────────────────────────

def ensure_templates_copied_to_presets() -> bool:
    """Ensures built-in templates are present in presets and version-updated.

    Behavior:
    - Missing preset files are created from templates.
    - Existing preset files are overwritten only when template
      `# BuiltinVersion:` is strictly newer.
    - Deleted built-ins are restored automatically.
    - Before overwrite, old preset content is backed up to
      `<presets_dir>/_builtin_version_backups/`.
    - If an updated preset is currently active, `preset-zapret2.txt`
      is synced immediately.

    Returns True on success.
    """
    try:
        from config import get_zapret_presets_v2_dir
        from .preset_storage import get_active_preset_name, get_active_preset_path

        templates = get_preset_templates()
        if not templates:
            return True

        presets_dir = Path(get_zapret_presets_v2_dir())
        presets_dir.mkdir(parents=True, exist_ok=True)

        backups_dir = presets_dir / "_builtin_version_backups"
        deleted_lower = {d.lower() for d in get_deleted_preset_names()}
        active_key = (get_active_preset_name() or "").strip().lower()

        created_count = 0
        updated_count = 0
        restored_deleted_count = 0

        for name, content in templates.items():
            name_key = name.lower()
            dest = presets_dir / f"{name}.txt"
            template_version = _extract_builtin_version(content)
            was_deleted = name_key in deleted_lower

            needs_write = False
            created = False
            updated = False
            existing_content: Optional[str] = None
            existing_version: Optional[str] = None

            if not dest.exists():
                needs_write = True
                created = True
            else:
                try:
                    existing_content = dest.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    existing_content = None

                existing_version = _extract_builtin_version(existing_content or "")

                if _is_newer_builtin_version(template_version, existing_version):
                    needs_write = True
                    updated = True

                    # Backup current file before forced overwrite.
                    if existing_content is not None:
                        try:
                            backups_dir.mkdir(parents=True, exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            from_v = _sanitize_version_for_filename(existing_version)
                            to_v = _sanitize_version_for_filename(template_version)
                            backup_name = f"{dest.stem}__{timestamp}__{from_v}_to_{to_v}.txt"
                            (backups_dir / backup_name).write_text(existing_content, encoding="utf-8")
                        except Exception:
                            pass

            if needs_write:
                try:
                    dest.write_text(content, encoding="utf-8")
                except Exception:
                    continue

                if created:
                    created_count += 1
                if updated:
                    updated_count += 1
                if was_deleted and created:
                    restored_deleted_count += 1

                # Keep runtime active file in sync if this preset is active.
                if active_key and active_key == name_key:
                    try:
                        active_path = get_active_preset_path()
                        active_path.parent.mkdir(parents=True, exist_ok=True)
                        active_path.write_text(content, encoding="utf-8")
                    except Exception:
                        pass

            # If deleted marker exists for this built-in, clear it because
            # built-ins are now always auto-restored.
            if was_deleted:
                try:
                    unmark_preset_deleted(name)
                except Exception:
                    pass

        try:
            from log import log
            if created_count or updated_count or restored_deleted_count:
                log(
                    "Built-in preset sync complete: "
                    f"created={created_count}, updated={updated_count}, restored_deleted={restored_deleted_count}",
                    "INFO",
                )
        except Exception:
            pass

        return True
    except Exception as e:
        try:
            from log import log
            log(f"Error copying templates to presets: {e}", "ERROR")
        except Exception:
            pass
        return False


def overwrite_templates_to_presets() -> tuple[int, int, list[str]]:
    """Copy all templates from presets_v2_template/ -> presets_v2/ with overwrite.

    Every template file is copied even if destination already exists.
    Returns (copied_count, total_templates, failed_template_names).
    """
    try:
        from config import get_zapret_presets_v2_template_dir, get_zapret_presets_v2_dir
    except Exception:
        return (0, 0, [])

    templates_dir = Path(get_zapret_presets_v2_template_dir())
    presets_dir = Path(get_zapret_presets_v2_dir())

    try:
        presets_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return (0, 0, [])

    try:
        sources = [
            src
            for src in sorted(templates_dir.glob("*.txt"), key=lambda p: p.name.lower())
            if src.is_file() and not src.name.startswith("_")
        ]
    except Exception:
        return (0, 0, [])

    if not sources:
        return (0, 0, [])

    copied = 0
    failed: list[str] = []

    for src in sources:
        name = src.stem
        dest = presets_dir / src.name
        try:
            shutil.copy2(str(src), str(dest))
            copied += 1
            try:
                unmark_preset_deleted(name)
            except Exception:
                pass
        except Exception as e:
            failed.append(name)
            try:
                from log import log

                log(f"Failed to overwrite preset '{name}' from template: {e}", "DEBUG")
            except Exception:
                pass

    try:
        from log import log

        if copied or failed:
            log(
                "Template overwrite complete: "
                f"copied={copied}, total={len(sources)}, failed={len(failed)}",
                "INFO",
            )
    except Exception:
        pass

    return (copied, len(sources), failed)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT SETTINGS PARSER (unchanged logic, uses templates)
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_SETTINGS_CACHE = None


def get_default_category_settings() -> dict:
    """
    Parses the default template and returns default settings for all categories.
    Cached after first call.
    """
    global _DEFAULT_SETTINGS_CACHE

    if _DEFAULT_SETTINGS_CACHE is not None:
        return _DEFAULT_SETTINGS_CACHE

    from .txt_preset_parser import parse_preset_content

    template_name = "Default"

    try:
        template_name = get_default_template_name() or "Default"
        template = get_template_content(template_name)
        if not template:
            from log import log
            log(
                "Cannot parse default category settings: no preset templates found. "
                "Expected at least one file in: %APPDATA%/zapret/presets_v2_template/*.txt",
                "ERROR",
            )
            return {}

        preset_data = parse_preset_content(template)

        settings = {}
        for block in preset_data.categories:
            category_name = block.category
            if category_name not in settings:
                settings[category_name] = {
                    "filter_mode": block.filter_mode,
                    "tcp_enabled": False,
                    "tcp_port": "",
                    "tcp_args": "",
                    "udp_enabled": False,
                    "udp_port": "",
                    "udp_args": "",
                    "syndata_overrides_tcp": {},
                    "syndata_overrides_udp": {},
                }

            cat_settings = settings[category_name]
            overrides = getattr(block, "syndata_dict", None) or {}
            if overrides:
                target = "syndata_overrides_tcp" if block.protocol == "tcp" else "syndata_overrides_udp"
                cat_settings[target].update(overrides)

            if block.protocol == "tcp":
                cat_settings["tcp_enabled"] = True
                cat_settings["tcp_port"] = block.port
                cat_settings["tcp_args"] = block.strategy_args
                cat_settings["filter_mode"] = block.filter_mode
            elif block.protocol == "udp":
                cat_settings["udp_enabled"] = True
                cat_settings["udp_port"] = block.port
                cat_settings["udp_args"] = block.strategy_args
                if not cat_settings["tcp_enabled"]:
                    cat_settings["filter_mode"] = block.filter_mode

        _DEFAULT_SETTINGS_CACHE = settings
        return settings

    except Exception as e:
        from log import log
        log(f"Failed to parse template '{template_name}': {e}", "ERROR")
        return {}


def get_category_default_filter_mode(category_name: str) -> str:
    """Returns default filter_mode for a category from the default template."""
    settings = get_default_category_settings()
    if category_name in settings:
        return settings[category_name].get("filter_mode", "hostlist")
    return "hostlist"


def parse_syndata_from_args(args_str: str) -> dict:
    """Parses syndata settings from args string."""
    result = {
        "enabled": False,
        "blob": "tls_google",
        "tls_mod": "none",
        "autottl_delta": 0,
        "autottl_min": 3,
        "autottl_max": 20,
        "tcp_flags_unset": "none",
        "out_range": 0,
        "out_range_mode": "n",
        "send_enabled": False,
        "send_repeats": 0,
        "send_ip_ttl": 0,
        "send_ip6_ttl": 0,
        "send_ip_id": "none",
        "send_badsum": False,
    }

    import re

    syndata_match = re.search(r'--lua-desync=syndata:([^\n]+)', args_str)
    if syndata_match:
        result["enabled"] = True
        syndata_str = syndata_match.group(1)

        blob_match = re.search(r'blob=([^:]+)', syndata_str)
        if blob_match:
            result["blob"] = blob_match.group(1)

        autottl_match = re.search(r'ip_autottl=(-?\d+),(\d+)-(\d+)', syndata_str)
        if autottl_match:
            result["autottl_delta"] = int(autottl_match.group(1))
            result["autottl_min"] = int(autottl_match.group(2))
            result["autottl_max"] = int(autottl_match.group(3))

        tls_mod_match = re.search(r'tls_mod=([^:]+)', syndata_str)
        if tls_mod_match:
            result["tls_mod"] = tls_mod_match.group(1)

    send_match = re.search(r'--lua-desync=send:([^\n]+)', args_str)
    if send_match:
        result["send_enabled"] = True
        send_str = send_match.group(1)

        repeats_match = re.search(r'repeats=(\d+)', send_str)
        if repeats_match:
            result["send_repeats"] = int(repeats_match.group(1))

        ttl_match = re.search(r'ttl=(\d+)', send_str)
        if ttl_match:
            result["send_ip_ttl"] = int(ttl_match.group(1))

        ttl6_match = re.search(r'ttl6=(\d+)', send_str)
        if ttl6_match:
            result["send_ip6_ttl"] = int(ttl6_match.group(1))

        if 'badsum=true' in send_str:
            result["send_badsum"] = True

    out_range_match = re.search(r'--out-range=-([nd])(\d+)', args_str)
    if out_range_match:
        result["out_range_mode"] = out_range_match.group(1)
        result["out_range"] = int(out_range_match.group(2))

    return result


def get_category_default_syndata(category_name: str, protocol: str = "tcp") -> dict:
    """Returns default syndata settings for a category from the default template."""
    from .preset_model import SyndataSettings

    proto = (protocol or "").strip().lower()
    if proto in ("udp", "quic", "l7", "raw"):
        base = SyndataSettings.get_defaults_udp().to_dict()
        key = "syndata_overrides_udp"
    else:
        base = SyndataSettings.get_defaults().to_dict()
        key = "syndata_overrides_tcp"

    settings = get_default_category_settings()
    overrides = (settings.get(category_name) or {}).get(key) or {}
    if isinstance(overrides, dict) and overrides:
        base.update(overrides)

    return base


# ── Removed concepts (kept as no-ops for transition) ─────────────────────

# These were part of the old builtin/copy system and are no longer meaningful.
BUILTIN_COPY_SUFFIX = " (копия)"  # kept for migration code only


def get_builtin_copy_name(builtin_name: str) -> Optional[str]:
    """DEPRECATED: No longer used. Kept for migration compatibility."""
    canonical = get_template_canonical_name(builtin_name)
    if not canonical:
        return None
    return f"{canonical}{BUILTIN_COPY_SUFFIX}"


def get_builtin_base_from_copy_name(name: str) -> Optional[str]:
    """DEPRECATED: No longer used. Kept for migration compatibility."""
    raw = (name or "").strip()
    if not raw:
        return None

    # Support both "Name (копия)" and numbered variants like "Name (копия 2)".
    # Duplicate-of-duplicate names are also unwrapped recursively.
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

    return get_template_canonical_name(base)
