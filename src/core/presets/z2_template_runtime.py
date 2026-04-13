from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from direct_preset.common.circular_preset_support import resolve_transport_settings
from direct_preset.common.source_preset_models import SendSettings, SyndataSettings
from direct_preset.engines import winws2_parser, winws2_rules
from log.log import log



_TEMPLATES_CACHE: Optional[dict[str, str]] = None
_TEMPLATE_BY_KEY: Optional[dict[str, str]] = None
_CANONICAL_NAME_BY_KEY: Optional[dict[str, str]] = None
_DEFAULT_SETTINGS_CACHE = None
_BUILTIN_VERSION_RE = re.compile(r"^\s*#\s*BuiltinVersion:\s*(.+?)\s*$", re.IGNORECASE)


def invalidate_templates_cache() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY, _DEFAULT_SETTINGS_CACHE
    _TEMPLATES_CACHE = None
    _TEMPLATE_BY_KEY = None
    _CANONICAL_NAME_BY_KEY = None
    _DEFAULT_SETTINGS_CACHE = None


def get_template_content(name: str) -> Optional[str]:
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_TEMPLATE_BY_KEY or {}).get(key)


def get_template_canonical_name(name: str) -> Optional[str]:
    _ensure_templates_loaded()
    key = (name or "").strip().lower()
    if not key:
        return None
    return (_CANONICAL_NAME_BY_KEY or {}).get(key)


def get_default_template_content() -> Optional[str]:
    canonical = get_template_canonical_name("Default")
    if canonical:
        return get_template_content(canonical)
    names = sorted((_TEMPLATES_CACHE or {}).keys(), key=lambda value: value.lower())
    if names:
        return (_TEMPLATES_CACHE or {}).get(names[0])
    return None


def get_builtin_base_from_copy_name(name: str) -> Optional[str]:
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
    return get_template_canonical_name(base)

def ensure_templates_copied_to_presets() -> bool:
    try:
        from config.config import get_zapret_presets_v2_dir


        templates = _load_template_contents()
        if not templates:
            return True

        presets_dir = Path(get_zapret_presets_v2_dir())
        presets_dir.mkdir(parents=True, exist_ok=True)
        backups_dir = presets_dir / "_builtin_version_backups"

        for name, content in templates.items():
            dest = presets_dir / f"{name}.txt"
            template_version = _extract_builtin_version(content)

            needs_write = False
            updated = False
            existing_content: Optional[str] = None
            existing_version: Optional[str] = None
            if not dest.exists():
                needs_write = True
            else:
                try:
                    existing_content = dest.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    existing_content = None
                existing_version = _extract_builtin_version(existing_content or "")
                if _is_newer_builtin_version(template_version, existing_version):
                    needs_write = True
                    updated = True
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
                if updated:
                    log(
                        f"Built-in preset updated from template version {existing_version or 'none'} "
                        f"to {template_version or 'none'}: {dest}",
                        "DEBUG",
                    )
        return True
    except Exception:
        return False


def overwrite_templates_to_presets() -> tuple[int, int, list[str]]:
    try:
        from config.config import get_zapret_presets_v2_dir

    except Exception:
        return (0, 0, [])

    presets_dir = Path(get_zapret_presets_v2_dir())
    try:
        presets_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return (0, 0, [])

    templates = _load_template_contents()
    if not templates:
        return (0, 0, [])

    copied = 0
    failed: list[str] = []
    for name in sorted(templates.keys(), key=lambda value: value.lower()):
        dest = presets_dir / f"{name}.txt"
        try:
            dest.write_text(templates[name], encoding="utf-8")
            copied += 1
        except Exception:
            failed.append(name)
    return (copied, len(templates), failed)


def get_default_category_settings() -> dict:
    global _DEFAULT_SETTINGS_CACHE
    if _DEFAULT_SETTINGS_CACHE is not None:
        return _DEFAULT_SETTINGS_CACHE

    template = get_default_template_content()
    if not template:
        return {}

    try:
        source = winws2_parser.parse(template)
        settings = {}
        for profile in source.profiles:
            protocol = str(getattr(profile, "protocol_kind", "") or "tcp").strip().lower() or "tcp"
            filter_mode = _detect_filter_mode(profile.match_lines)
            port = _detect_filter_port(profile.match_lines, protocol)
            helper_free_args = "\n".join(winws2_rules.strip_helper_lines(list(profile.action_lines))).strip()
            syndata_overrides = _extract_syndata_overrides(profile.action_lines, protocol)

            for target_key in tuple(getattr(profile, "canonical_target_keys", ()) or ()):
                category_name = _base_key_from_target_key(target_key)
                if category_name not in settings:
                    settings[category_name] = {
                        "filter_mode": filter_mode,
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
                if protocol == "udp":
                    cat_settings["udp_enabled"] = True
                    cat_settings["udp_port"] = port
                    cat_settings["udp_args"] = helper_free_args
                    cat_settings["syndata_overrides_udp"].update(syndata_overrides)
                    if not cat_settings["tcp_enabled"]:
                        cat_settings["filter_mode"] = filter_mode
                else:
                    cat_settings["tcp_enabled"] = True
                    cat_settings["tcp_port"] = port
                    cat_settings["tcp_args"] = helper_free_args
                    cat_settings["filter_mode"] = filter_mode
                    cat_settings["syndata_overrides_tcp"].update(syndata_overrides)

        _DEFAULT_SETTINGS_CACHE = settings
        return settings
    except Exception:
        return {}


def get_category_default_syndata(category_name: str, protocol: str = "tcp") -> dict:
    proto = (protocol or "").strip().lower()
    if proto in ("udp", "quic", "l7", "raw"):
        base = {
            "enabled": False,
            "blob": "tls_google",
            "tls_mod": "none",
            "autottl_delta": 0,
            "autottl_min": 3,
            "autottl_max": 20,
            "out_range": 8,
            "out_range_mode": "d",
            "tcp_flags_unset": "none",
            "send_enabled": False,
            "send_repeats": 2,
            "send_ip_ttl": 0,
            "send_ip6_ttl": 0,
            "send_ip_id": "none",
            "send_badsum": False,
        }
        key = "syndata_overrides_udp"
    else:
        base = {
            "enabled": True,
            "blob": "tls_google",
            "tls_mod": "none",
            "autottl_delta": 0,
            "autottl_min": 3,
            "autottl_max": 20,
            "out_range": 8,
            "out_range_mode": "d",
            "tcp_flags_unset": "none",
            "send_enabled": True,
            "send_repeats": 2,
            "send_ip_ttl": 0,
            "send_ip6_ttl": 0,
            "send_ip_id": "none",
            "send_badsum": False,
        }
        key = "syndata_overrides_tcp"

    overrides = (get_default_category_settings().get(category_name) or {}).get(key) or {}
    if isinstance(overrides, dict) and overrides:
        base.update(overrides)
    return base


def _ensure_templates_loaded() -> None:
    global _TEMPLATES_CACHE, _TEMPLATE_BY_KEY, _CANONICAL_NAME_BY_KEY
    if _TEMPLATES_CACHE is not None:
        return
    templates = _load_template_contents()
    _TEMPLATES_CACHE = {key: templates[key] for key in sorted(templates.keys(), key=lambda value: value.lower())}
    _TEMPLATE_BY_KEY = {canonical.lower(): content for canonical, content in _TEMPLATES_CACHE.items()}
    _CANONICAL_NAME_BY_KEY = {canonical.lower(): canonical for canonical in _TEMPLATES_CACHE.keys()}


def _base_key_from_target_key(target_key: str) -> str:
    text = str(target_key or "").strip().lower()
    for suffix in ("_tcp", "_udp", "_l7"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def _detect_filter_mode(match_lines: list[str]) -> str:
    for line in match_lines:
        lowered = str(line or "").strip().lower()
        if lowered.startswith("--ipset="):
            return "ipset"
        if lowered.startswith("--hostlist="):
            return "hostlist"
    return "hostlist"


def _detect_filter_port(match_lines: list[str], protocol: str) -> str:
    prefix = "--filter-udp=" if protocol == "udp" else "--filter-tcp="
    for line in match_lines:
        stripped = str(line or "").strip()
        if stripped.lower().startswith(prefix):
            return stripped.split("=", 1)[1].strip()
    return "443"


def _extract_syndata_overrides(action_lines: list[str], protocol: str) -> dict:
    proto = str(protocol or "").strip().lower()
    out_range, send, syndata = resolve_transport_settings(
        action_lines,
        rules_module=winws2_rules,
    )
    if proto != "tcp":
        send = SendSettings(enabled=False)

    defaults = {
        "enabled": False if proto in ("udp", "quic", "l7", "raw") else True,
        "blob": "tls_google",
        "tls_mod": "none",
        "autottl_delta": 0,
        "autottl_min": 3,
        "autottl_max": 20,
        "out_range": 8,
        "out_range_mode": "d",
        "tcp_flags_unset": "none",
        "send_enabled": False if proto in ("udp", "quic", "l7", "raw") else True,
        "send_repeats": 2,
        "send_ip_ttl": 0,
        "send_ip6_ttl": 0,
        "send_ip_id": "none",
        "send_badsum": False,
    }

    current = {
        "enabled": bool(syndata.enabled),
        "blob": syndata.blob,
        "tls_mod": syndata.tls_mod,
        "autottl_delta": syndata.autottl_delta,
        "autottl_min": syndata.autottl_min,
        "autottl_max": syndata.autottl_max,
        "out_range": out_range.value if out_range.enabled else 8,
        "out_range_mode": out_range.mode or "d",
        "tcp_flags_unset": syndata.tcp_flags_unset,
        "send_enabled": bool(send.enabled),
        "send_repeats": send.repeats,
        "send_ip_ttl": send.ip_ttl,
        "send_ip6_ttl": send.ip6_ttl,
        "send_ip_id": send.ip_id,
        "send_badsum": bool(send.badsum),
    }

    overrides = {}
    for key, value in current.items():
        if defaults.get(key) != value:
            overrides[key] = value
    return overrides


def _load_template_contents() -> dict[str, str]:
    from .z2_builtin_templates import list_repo_builtin_templates_v2

    return dict(list_repo_builtin_templates_v2())


def _normalize_template_header_v2(content: str, preset_name: str) -> str:
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
