from __future__ import annotations

from blockcheck.strategy_scan_state import StrategyApplyResult
from blockcheck.strategy_scan_targeting import (
    default_target_for_protocol,
    format_stun_target,
    normalize_target_domain,
    resolve_games_ipset_paths,
    stun_target_parts,
)

def generate_blob_lines_for_apply(strategy_args: str) -> list[str]:
    try:
        from blobs.service import find_used_blobs, get_blobs

        used = find_used_blobs(strategy_args)
        if not used:
            return []
        blobs = get_blobs()
        return [f"--blob={name}:{blobs[name]}" for name in sorted(used) if name in blobs]
    except Exception:
        return []


def apply_profile_to_selected_preset(
    *,
    presets_feature,
    strategy_lines: list[str],
    blob_lines: list[str],
) -> tuple[str, str]:
    from profile.parser import parse_preset_text
    from profile.serializer import serialize_preset, with_profile_enabled, with_profile_strategy_lines
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
    for line in [*blob_lines, *profile_preset.preamble_lines]:
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
    if existing_profile is not None:
        source = with_profile_strategy_lines(
            source,
            existing_profile.index,
            list(getattr(new_profile.strategy, "strategy_lines", ()) or ()),
        )
        source = with_profile_enabled(source, existing_profile.index, True)
    else:
        raise RuntimeError(
            "В выбранном preset нет profile с такими условиями проверки. "
            "Сначала создайте нужный profile, затем примените найденную стратегию повторно."
        )

    updated_text = serialize_preset(source)
    presets_feature.save_preset_source_by_file_name(
        ZAPRET2_MODE,
        selected_file_name,
        updated_text,
    )
    return selected_file_name, "updated"


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
    blob_lines = generate_blob_lines_for_apply(strategy_args)

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
        blob_lines=blob_lines,
    )

    return StrategyApplyResult(
        strategy_name=strategy_name,
        applied_profile=applied_profile,
        selected_file_name=selected_file_name,
        operation=operation,
    )
