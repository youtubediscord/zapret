from __future__ import annotations

from .mode_logic import keep_payload_in_identity


def compose_action_lines_for_strategy_selection(
    *,
    strategy_args: list[str],
    details,
    rules_module,
) -> list[str]:
    return list(
        rules_module.compose_action_lines(
            rules_module.strip_helper_lines(strategy_args),
            details.out_range_settings,
            rules_module.parse_send(strategy_args),
            rules_module.parse_syndata(strategy_args),
        )
    )


def normalize_strategy_identity(
    *,
    action_lines: list[str] | tuple[str, ...],
    match_lines: list[str] | tuple[str, ...] | None,
    candidates: tuple[str, ...] | list[str] | None,
    keep_payload_in_identity: bool,
    rules_module,
) -> list[str]:
    lines = [str(line).strip() for line in action_lines if str(line).strip()]
    payload_lines = [
        str(line).strip()
        for line in (match_lines or ())
        if str(line).strip().lower().startswith("--payload=")
    ]
    if keep_payload_in_identity:
        lines = payload_lines + lines

    normalized_lines: list[str] = []
    for line in lines:
        lowered = line.strip().lower()
        if lowered.startswith("--out-range="):
            continue
        if not keep_payload_in_identity and lowered.startswith("--payload="):
            continue
        if lowered == "--payload=all":
            continue
        cleaned = line
        try:
            cleaned = rules_module._cleanup_action_line_after_inline_out_range(cleaned)  # type: ignore[attr-defined]
        except Exception:
            pass
        if cleaned:
            normalized_lines.append(cleaned)
    return normalized_lines


def normalized_strategy_identities(
    *,
    action_lines: list[str] | tuple[str, ...],
    match_lines: list[str] | tuple[str, ...] | None,
    candidates: tuple[str, ...] | list[str] | None,
    rules_module,
    normalize_args_fn,
) -> tuple[str, ...]:
    variants: list[str] = []

    primary_lines = normalize_strategy_identity(
        action_lines=action_lines,
        match_lines=match_lines,
        candidates=candidates,
        keep_payload_in_identity=keep_payload_in_identity(candidates),
        rules_module=rules_module,
    )
    primary = str(normalize_args_fn(primary_lines) or "").strip()
    if primary:
        variants.append(primary)

    secondary_lines = normalize_strategy_identity(
        action_lines=action_lines,
        match_lines=match_lines,
        candidates=candidates,
        keep_payload_in_identity=False,
        rules_module=rules_module,
    )
    secondary = str(normalize_args_fn(secondary_lines) or "").strip()
    if secondary and secondary not in variants:
        variants.append(secondary)

    return tuple(variants)
