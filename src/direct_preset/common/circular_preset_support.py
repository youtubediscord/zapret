from __future__ import annotations

import re
from typing import Any

from .source_preset_models import OutRangeSettings, SendSettings, SyndataSettings


_PRESET_HEADER_RE = re.compile(r"^#\s*Preset\s*:\s*(.+?)\s*$", re.IGNORECASE)
_CIRCULAR_NAME_RE = re.compile(r"\(circular\)", re.IGNORECASE)
_CIRCULAR_DESYNC_RE = re.compile(r"^--lua-desync=(?:circular|circular_quality)(?::|$)", re.IGNORECASE)


def is_circular_preset_name(name: object) -> bool:
    return bool(_CIRCULAR_NAME_RE.search(str(name or "")))


def preset_name_from_header_lines(header_lines: list[str] | tuple[str, ...] | None) -> str:
    for raw in header_lines or ():
        match = _PRESET_HEADER_RE.match(str(raw or "").strip())
        if match:
            return str(match.group(1) or "").strip()
    return ""


def is_circular_action_lines(action_lines: list[str] | tuple[str, ...] | None) -> bool:
    for raw in action_lines or ():
        if _CIRCULAR_DESYNC_RE.match(str(raw or "").strip()):
            return True
    return False


def is_circular_profile(profile: Any) -> bool:
    return is_circular_action_lines(getattr(profile, "action_lines", ()) or ())


def is_circular_source_preset(source: Any) -> bool:
    preset_name = preset_name_from_header_lines(getattr(source, "header_lines", ()) or ())
    if is_circular_preset_name(preset_name):
        return True
    for profile in getattr(source, "profiles", ()) or ():
        if is_circular_profile(profile):
            return True
    return False


def normalize_action_lines_for_preset(
    action_lines: list[str] | tuple[str, ...],
    *,
    rules_module,
    source_is_circular: bool = False,
):
    normalized = [str(line).strip() for line in action_lines if str(line).strip()]
    if source_is_circular or is_circular_action_lines(normalized):
        return normalized, tuple(), None
    return rules_module.normalize_action_lines(normalized)


def resolve_transport_settings(
    action_lines: list[str] | tuple[str, ...],
    *,
    rules_module,
    source_is_circular: bool = False,
) -> tuple[OutRangeSettings, SendSettings, SyndataSettings]:
    normalized = [str(line).strip() for line in action_lines if str(line).strip()]
    if source_is_circular or is_circular_action_lines(normalized):
        return OutRangeSettings(), SendSettings(), SyndataSettings()
    return (
        rules_module.parse_out_range(normalized),
        rules_module.parse_send(normalized),
        rules_module.parse_syndata(normalized),
    )


def editable_raw_args_text(
    action_lines: list[str] | tuple[str, ...],
    *,
    rules_module,
    source_is_circular: bool = False,
) -> str:
    normalized = [str(line).strip() for line in action_lines if str(line).strip()]
    if source_is_circular or is_circular_action_lines(normalized):
        return "\n".join(normalized).strip()
    return "\n".join(rules_module.strip_helper_lines(normalized)).strip()
