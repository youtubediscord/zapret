from __future__ import annotations

from pathlib import Path, PureWindowsPath

from blockcheck.strategy_scan_state import StrategyApplyResult
from blockcheck.strategy_scan_targeting import (
    default_target_for_protocol,
    format_stun_target,
    normalize_target_domain,
    resolve_games_ipset_paths,
    stun_target_parts,
)
from config.config import MAIN_DIRECTORY


def _line_option_values(line: str) -> list[str]:
    _name, separator, value = str(line or "").strip().partition("=")
    if not separator:
        return []
    return [part.strip().strip('"').strip("'") for part in value.split(",") if part.strip()]


def _domain_matches_hostlist_entry(target: str, entry: str) -> bool:
    target = normalize_target_domain(target) or ""
    entry = normalize_target_domain(str(entry or "").strip().lstrip(".")) or ""
    if entry.startswith("*."):
        entry = entry[2:]
    if not target or not entry:
        return False
    return target == entry or target.endswith(f".{entry}")


def _hostlist_line_domain(line: str) -> str:
    stripped = str(line or "").strip()
    if not stripped or stripped.startswith("#"):
        return ""
    stripped = stripped.split("#", 1)[0].strip()
    if not stripped:
        return ""
    return stripped.split()[0].strip()


def _hostlist_path_candidates(raw_path: str) -> list[Path]:
    clean = str(raw_path or "").strip().strip('"').strip("'").lstrip("@")
    if not clean:
        return []

    normalized = clean.replace("\\", "/")
    raw = Path(normalized)
    base = Path(str(MAIN_DIRECTORY or "").strip() or ".")
    file_name = PureWindowsPath(normalized).name

    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    candidates.append(base / normalized)
    if file_name:
        candidates.append(base / "lists" / file_name)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _hostlist_contains_target(raw_path: str, target: str) -> bool:
    for candidate in _hostlist_path_candidates(raw_path):
        try:
            with candidate.open("r", encoding="utf-8-sig", errors="ignore") as handle:
                for line in handle:
                    if _domain_matches_hostlist_entry(target, _hostlist_line_domain(line)):
                        return True
        except OSError:
            continue
    return False


def _ports_include(ports: str, wanted_port: int) -> bool:
    for raw_part in str(ports or "").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, _separator, end_text = part.partition("-")
            try:
                start = int(start_text.strip())
                end = int(end_text.strip())
            except ValueError:
                continue
            if start <= wanted_port <= end:
                return True
            continue
        try:
            if int(part) == wanted_port:
                return True
        except ValueError:
            continue
    return False


def _profile_accepts_tcp_https(profile) -> bool:
    for line in getattr(profile.match, "filter_lines", []) or []:
        stripped = str(line or "").strip().lower()
        if not stripped.startswith("--filter-tcp="):
            continue
        if _ports_include(stripped.partition("=")[2], 443):
            return True
    return False


def _profile_host_match_contains_target(profile, target: str) -> bool:
    for line in getattr(profile.match, "hostlist_domains_lines", []) or []:
        if any(_domain_matches_hostlist_entry(target, value) for value in _line_option_values(line)):
            return True

    for line in getattr(profile.match, "hostlist_lines", []) or []:
        if any(_hostlist_contains_target(value, target) for value in _line_option_values(line)):
            return True

    return False


def _find_existing_tcp_https_profile_for_target(profiles, target: str):
    normalized_target = normalize_target_domain(target) or ""
    if not normalized_target:
        return None
    for profile in profiles:
        if not _profile_accepts_tcp_https(profile):
            continue
        if _profile_host_match_contains_target(profile, normalized_target):
            return profile
    return None


def apply_profile_to_selected_preset(
    *,
    presets_feature,
    strategy_lines: list[str],
    match_target: str = "",
    scan_protocol: str = "",
) -> tuple[str, str]:
    from profile.parser import parse_preset_text
    from profile.serializer import (
        append_profile_from_template,
        serialize_preset,
        with_profile_enabled,
        with_profile_strategy_lines,
    )
    from settings.mode import ENGINE_WINWS2, ZAPRET2_MODE

    manifest = presets_feature.get_selected_source_preset_manifest(ZAPRET2_MODE)
    selected_file_name = str(getattr(manifest, "file_name", "") or "").strip()
    if not selected_file_name:
        raise RuntimeError("Не удалось определить выбранный пресет")

    source_text = presets_feature.read_preset_source_by_file_name(
        ZAPRET2_MODE,
        selected_file_name,
    )
    source = parse_preset_text(source_text, engine=ENGINE_WINWS2, source_name=selected_file_name)

    cleaned_strategy_lines = [line.strip() for line in strategy_lines if line and line.strip()]
    profile_source = "\n".join(cleaned_strategy_lines).rstrip("\n") + "\n"
    profile_preset = parse_preset_text(profile_source, engine=ENGINE_WINWS2, source_name=selected_file_name)
    if not profile_preset.profiles:
        raise RuntimeError("Не удалось собрать profile из найденной стратегии")

    known_preamble = {line.strip() for line in source.preamble_lines if line.strip()}
    for line in profile_preset.preamble_lines:
        stripped = str(line or "").strip()
        if not stripped or stripped in known_preamble:
            continue
        if source.preamble_lines and source.preamble_lines[-1].strip():
            source.preamble_lines.append("")
        source.preamble_lines.append(stripped)
        known_preamble.add(stripped)

    new_profile = profile_preset.profiles[0]
    existing_profile = next(
        (
            profile
            for profile in source.profiles
            if profile.match_signature and profile.match_signature == new_profile.match_signature
        ),
        None,
    )
    if existing_profile is None and str(scan_protocol or "").strip() == "tcp_https":
        existing_profile = _find_existing_tcp_https_profile_for_target(
            source.profiles,
            match_target,
        )
    if existing_profile is not None:
        source = with_profile_strategy_lines(
            source,
            existing_profile.index,
            list(getattr(new_profile.strategy, "strategy_lines", ()) or ()),
        )
        source = with_profile_enabled(source, existing_profile.index, True)
        operation = "updated"
    else:
        source = append_profile_from_template(source, new_profile, enabled=True, position="top")
        operation = "created"

    updated_text = serialize_preset(source)
    presets_feature.save_preset_source_by_file_name(
        ZAPRET2_MODE,
        selected_file_name,
        updated_text,
    )
    return selected_file_name, operation


def apply_strategy(
    *,
    presets_feature,
    profile_feature,
    strategy_args: str,
    strategy_name: str,
    scan_target: str,
    scan_protocol: str,
    scan_udp_games_scope: str,
    ) -> StrategyApplyResult:
    target = scan_target or default_target_for_protocol(scan_protocol)

    if scan_protocol == "stun_voice":
        target_host, target_port = stun_target_parts(target)
        if not target_host:
            target_host = "stun.l.google.com"
            target_port = 19302

        new_strategy_lines = [
            "--wf-udp-out=443-65535",
            "--filter-l7=stun,discord",
            "--payload=stun,discord_ip_discovery",
            strategy_args,
        ]
        applied_profile = f"voice, проверка {format_stun_target(target_host, target_port)}"
    elif scan_protocol == "udp_games":
        games_ipset_paths = resolve_games_ipset_paths(scan_udp_games_scope)
        probe_host, probe_port = stun_target_parts(target)
        if not probe_host:
            probe_host = "stun.cloudflare.com"
            probe_port = 3478

        new_strategy_lines = [
            "--wf-udp-out=443,50000-65535",
            "--filter-udp=443,50000-65535",
            *[f"--ipset={path}" for path in games_ipset_paths],
            strategy_args,
        ]
        shown_paths = ", ".join(games_ipset_paths[:3])
        if len(games_ipset_paths) > 3:
            shown_paths += f", ... (+{len(games_ipset_paths) - 3})"
        applied_profile = (
            f"Games UDP ipsets ({shown_paths}), "
            f"проверка {format_stun_target(probe_host, probe_port)}"
        )
    else:
        normalized_target = normalize_target_domain(target) or "discord.com"
        new_strategy_lines = [
            "--filter-tcp=443",
            f"--hostlist-domains={normalized_target}",
            "--out-range=-d8",
            strategy_args,
        ]
        applied_profile = normalized_target

    selected_file_name, operation = apply_profile_to_selected_preset(
        presets_feature=presets_feature,
        strategy_lines=new_strategy_lines,
        match_target=target,
        scan_protocol=scan_protocol,
    )

    return StrategyApplyResult(
        strategy_name=strategy_name,
        applied_profile=applied_profile,
        selected_file_name=selected_file_name,
        operation=operation,
    )
