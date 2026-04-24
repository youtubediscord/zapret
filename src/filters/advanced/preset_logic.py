from __future__ import annotations


def compose_action_lines_for_strategy_selection(
    *,
    strategy_args: list[str],
    details,
    rules_module,
) -> list[str]:
    return list(
        rules_module.compose_action_lines(
            strategy_args,
            details.out_range_settings,
            details.send_settings,
            details.syndata_settings,
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
    _ = (match_lines, candidates, keep_payload_in_identity)
    lines = rules_module.strip_helper_lines([str(line).strip() for line in action_lines if str(line).strip()])
    normalized_lines: list[str] = []
    for line in lines:
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
    _ = (match_lines, candidates)
    lines = normalize_strategy_identity(
        action_lines=action_lines,
        match_lines=None,
        candidates=None,
        keep_payload_in_identity=True,
        rules_module=rules_module,
    )
    normalized = str(normalize_args_fn(lines) or "").strip()
    return (normalized,) if normalized else ()
