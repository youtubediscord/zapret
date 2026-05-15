from __future__ import annotations

import re
from pathlib import Path

from settings.mode import (
    DEFAULT_LAUNCH_METHOD,
    ENGINE_WINWS1,
    ENGINE_WINWS2,
    engine_for_launch_method,
    is_preset_launch_method,
    normalize_launch_method,
)

from .parser import parse_preset_text
from .serializer import serialize_preset, with_profile_strategy_lines


_WINWS2_WSSIZE_LINE = "--lua-desync=wssize:wsize=1:scale=6"
_WINWS1_WSSIZE_LINES = ("--wssize", "1:6", "--wssize-forced-cutoff=0")


def get_advanced_settings_state(profile_services, launch_method: str = DEFAULT_LAUNCH_METHOD) -> dict[str, bool]:
    discord_restart = True
    try:
        from discord.discord_restart import get_discord_restart_setting

        discord_restart = bool(get_discord_restart_setting(default=True))
    except Exception:
        pass

    return {
        "discord_restart": discord_restart,
        "wssize_enabled": get_wssize_enabled(profile_services, launch_method=launch_method),
        "debug_log_enabled": get_debug_log_enabled(profile_services, launch_method=launch_method),
    }


def get_wssize_enabled(profile_services, *, launch_method: str = DEFAULT_LAUNCH_METHOD) -> bool:
    preset, _manifest = _load_selected_profile_preset(profile_services, launch_method)
    for profile in preset.profiles:
        if not _profile_tcp_includes_443(profile):
            continue
        if _profile_has_wssize(profile):
            return True
    return False


def set_wssize_enabled(profile_services, enabled: bool, *, launch_method: str = DEFAULT_LAUNCH_METHOD) -> bool:
    preset, _manifest = _load_selected_profile_preset(profile_services, launch_method)
    changed = False
    touched_any_tcp_443 = False

    for profile in list(preset.profiles):
        if not _profile_tcp_includes_443(profile):
            continue
        touched_any_tcp_443 = True
        current_lines = [str(line or "").strip() for line in profile.strategy.strategy_lines if str(line or "").strip()]
        cleaned = _remove_wssize_lines(preset.engine, current_lines)
        if enabled:
            next_lines = [*_wssize_lines_for_engine(preset.engine), *cleaned]
        else:
            next_lines = cleaned
        if next_lines == current_lines:
            continue
        preset = with_profile_strategy_lines(preset, profile.index, next_lines)
        changed = True

    if not touched_any_tcp_443:
        return False if enabled else True
    if changed:
        _save_selected_profile_preset(profile_services, preset, launch_method)
    return True


def get_debug_log_enabled(profile_services, *, launch_method: str = DEFAULT_LAUNCH_METHOD) -> bool:
    return bool(get_debug_log_file(profile_services, launch_method=launch_method))


def get_debug_log_file(profile_services, *, launch_method: str = DEFAULT_LAUNCH_METHOD) -> str:
    text, _manifest = _load_selected_source_text(profile_services, launch_method)
    return _extract_debug_log_file(text)


def set_debug_log_enabled(profile_services, enabled: bool, *, launch_method: str = DEFAULT_LAUNCH_METHOD) -> bool:
    text, manifest = _load_selected_source_text(profile_services, launch_method)
    display_name = str(getattr(manifest, "name", "") or "").strip() or Path(str(getattr(manifest, "file_name", "") or "")).stem
    rewritten = _rewrite_debug_log_setting(text, display_name, bool(enabled))
    if rewritten != text:
        _save_selected_source_text(profile_services, rewritten, launch_method)
    return True


def _load_selected_profile_preset(profile_services, launch_method: str):
    text, manifest = _load_selected_source_text(profile_services, launch_method)
    engine = _engine_for_method(launch_method)
    return parse_preset_text(text, engine=engine, source_name=getattr(manifest, "file_name", "")), manifest


def _save_selected_profile_preset(profile_services, preset, launch_method: str) -> None:
    _save_selected_source_text(profile_services, serialize_preset(preset), launch_method)


def _load_selected_source_text(profile_services, launch_method: str) -> tuple[str, object]:
    method = normalize_launch_method(launch_method, default="")
    if not is_preset_launch_method(method):
        raise ValueError(f"Unsupported profile settings launch method: {launch_method}")
    return profile_services._presets_feature.read_selected_preset_source(method)


def _save_selected_source_text(profile_services, source_text: str, launch_method: str) -> None:
    method = normalize_launch_method(launch_method, default="")
    if not is_preset_launch_method(method):
        raise ValueError(f"Unsupported profile settings launch method: {launch_method}")
    profile_services._presets_feature.save_selected_preset_source(method, source_text)


def _engine_for_method(launch_method: str) -> str:
    return engine_for_launch_method(launch_method)


def _wssize_lines_for_engine(engine: str) -> tuple[str, ...]:
    return _WINWS1_WSSIZE_LINES if str(engine or "").strip().lower() == ENGINE_WINWS1 else (_WINWS2_WSSIZE_LINE,)


def _profile_has_wssize(profile) -> bool:
    engine = str(getattr(profile, "engine", "") or "").strip().lower()
    lines = [str(line or "").strip().lower() for line in getattr(profile.strategy, "strategy_lines", ()) or () if str(line or "").strip()]
    if engine == ENGINE_WINWS1:
        return any(line.startswith("--wssize") for line in lines)
    return _WINWS2_WSSIZE_LINE in lines


def _remove_wssize_lines(engine: str, lines: list[str]) -> list[str]:
    if str(engine or "").strip().lower() != ENGINE_WINWS1:
        return [line for line in lines if line.lower() != _WINWS2_WSSIZE_LINE]

    cleaned: list[str] = []
    skip_next_value = False
    for line in lines:
        lowered = line.lower()
        if skip_next_value and re.fullmatch(r"\d+\s*:\s*\d+", lowered):
            skip_next_value = False
            continue
        skip_next_value = False
        if lowered.startswith("--wssize"):
            if lowered == "--wssize":
                skip_next_value = True
            continue
        cleaned.append(line)
    return cleaned


def _profile_tcp_includes_443(profile) -> bool:
    for line in profile.match.filter_lines:
        stripped = str(line or "").strip()
        if not stripped.lower().startswith("--filter-tcp="):
            continue
        value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
        if _ports_include_443(value):
            return True
    return False


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


def _extract_debug_log_file(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.lower().startswith("--debug="):
            continue
        value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
        return value.lstrip("@").replace("\\", "/").lstrip("/")
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
