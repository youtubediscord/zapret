from __future__ import annotations

import re
from typing import Optional

from log.log import log



def _normalize_strategy_selection_value(value: object) -> str:
    return str(value or "").strip() or "none"


def _collect_changed_strategy_selections(current: dict | None, requested: dict | None) -> dict[str, str]:
    current_map = {
        str(key or "").strip().lower(): _normalize_strategy_selection_value(val)
        for key, val in (current or {}).items()
        if str(key or "").strip()
    }
    changed: dict[str, str] = {}
    for key, value in (requested or {}).items():
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        normalized_value = _normalize_strategy_selection_value(value)
        if current_map.get(normalized_key, "none") == normalized_value:
            continue
        changed[normalized_key] = normalized_value
    return changed


def _log_startup_payload_metric(scope: str | None, section: str, elapsed_ms: float, *, extra: str | None = None) -> None:
    resolved_scope = str(scope or "").strip()
    if not resolved_scope:
        return
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    suffix = f" ({extra})" if extra else ""
    log(f"⏱ Startup UI Section: {resolved_scope} {section} {rounded}ms{suffix}", "⏱ STARTUP")


def _rewrite_preset_header_name(source_text: str, target_name: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    replaced = False

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.lower().startswith("# preset:"):
            lines[idx] = f"# Preset: {target_name}"
            replaced = True
            break
        if stripped and not stripped.startswith("#"):
            break

    if not replaced:
        lines.insert(0, f"# Preset: {target_name}")

    rewritten = "\n".join(lines).rstrip("\n")
    return rewritten + "\n"


def _rewrite_preset_headers(
    source_text: str,
    target_name: str,
    *,
    template_origin: str | None = None,
    preset_kind: str | None = None,
) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    header_end = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            header_end = idx
            break
    else:
        header_end = len(lines)

    header = lines[:header_end]
    body = lines[header_end:]
    out_header: list[str] = []
    saw_preset = False
    saw_template_origin = False
    saw_preset_kind = False

    for raw in header:
        stripped = raw.strip()
        lowered = stripped.lower()
        if lowered.startswith("# preset:"):
            out_header.append(f"# Preset: {target_name}")
            saw_preset = True
            continue
        if lowered.startswith("# templateorigin:"):
            if template_origin is not None:
                out_header.append(f"# TemplateOrigin: {template_origin}")
                saw_template_origin = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_template_origin = True
            continue
        if lowered.startswith("# presetkind:"):
            if preset_kind is not None:
                out_header.append(f"# PresetKind: {preset_kind}")
                saw_preset_kind = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_preset_kind = True
            continue
        if lowered.startswith("# modified:"):
            continue
        if lowered.startswith("# activepreset:"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {target_name}")

    insert_idx = 1 if out_header and out_header[0].startswith("# Preset:") else 0
    if template_origin is not None and not saw_template_origin:
        out_header.insert(insert_idx, f"# TemplateOrigin: {template_origin}")
        insert_idx += 1

    if preset_kind is not None and not saw_preset_kind:
        out_header.insert(insert_idx, f"# PresetKind: {preset_kind}")

    rewritten = "\n".join(out_header + body).rstrip("\n")
    return rewritten + "\n"


def _header_preset_kind(kind: str | None) -> str | None:
    normalized = str(kind or "").strip().lower()
    if normalized == "imported":
        return "imported"
    return None


def _normalize_direct_preset_source_text(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        line
        for line in text.splitlines()
        if not line.strip().lower().startswith("# activepreset:")
        and not line.strip().lower().startswith("# modified:")
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _extract_debug_log_file(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.lower().startswith("--debug="):
            continue
        value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
        value = value.lstrip("@").replace("\\", "/").lstrip("/")
        return value
    return ""


def _build_stable_debug_log_file(preset_name: str) -> str:
    safe_name = re.sub(r"[^\w.-]+", "_", str(preset_name or "").strip(), flags=re.UNICODE).strip("._")
    if not safe_name:
        safe_name = "preset"
    return f"logs/{safe_name}_debug.log"


def _default_debug_insert_index(lines: list[str]) -> int:
    insert_at = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("--lua-init="):
            insert_at = idx + 1
    if insert_at:
        return insert_at

    header_end = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            header_end = idx + 1
            continue
        break
    return header_end


def _rewrite_debug_log_setting(source_text: str, preset_name: str, enabled: bool) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    existing_value = ""
    existing_insert_at: int | None = None
    cleaned: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.lower().startswith("--debug="):
            if not existing_value:
                existing_value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
                existing_value = existing_value.lstrip("@").replace("\\", "/").lstrip("/")
                existing_insert_at = len(cleaned)
            continue
        cleaned.append(raw)

    if enabled:
        debug_file = existing_value or _build_stable_debug_log_file(preset_name)
        debug_line = f"--debug=@{debug_file}"
        insert_at = existing_insert_at if existing_insert_at is not None else _default_debug_insert_index(cleaned)
        if insert_at < 0:
            insert_at = 0
        if insert_at > len(cleaned):
            insert_at = len(cleaned)
        cleaned.insert(insert_at, debug_line)

    return "\n".join(cleaned).rstrip("\n") + "\n"


def _ports_include_443(value: str) -> bool:
    for raw_part in str(value or "").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start = int(start_s.strip())
                end = int(end_s.strip())
            except Exception:
                continue
            if start <= 443 <= end:
                return True
            continue
        try:
            if int(part) == 443:
                return True
        except Exception:
            continue
    return False


def _split_arg_lines(args_text: str) -> list[str]:
    return [str(raw or "").strip() for raw in str(args_text or "").splitlines() if str(raw or "").strip()]


def _join_arg_lines(lines: list[str]) -> str:
    return "\n".join(str(line or "").strip() for line in lines if str(line or "").strip()).strip()


def _settings_payload_to_dict(value) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
            if isinstance(data, dict):
                return dict(data)
        except Exception:
            pass

    payload: dict[str, object] = {}
    for field in (
        "enabled",
        "blob",
        "tls_mod",
        "autottl_delta",
        "autottl_min",
        "autottl_max",
        "tcp_flags_unset",
        "out_range",
        "out_range_mode",
        "send_enabled",
        "send_repeats",
        "send_ip_ttl",
        "send_ip6_ttl",
        "send_ip_id",
        "send_badsum",
    ):
        if hasattr(value, field):
            payload[field] = getattr(value, field)
    return payload


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)

