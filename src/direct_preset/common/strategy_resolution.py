from __future__ import annotations

from typing import Callable


def normalize_args(lines: list[str] | tuple[str, ...]) -> str:
    return "\n".join(sorted(str(line).strip().lower() for line in lines if str(line).strip()))


def normalized_strategy_identities(
    *,
    action_lines: list[str] | tuple[str, ...],
    direct_mode: str | None,
    match_lines: list[str] | tuple[str, ...] | None,
    candidates: tuple[str, ...] | list[str] | None,
    resolve_mode_logic_fn: Callable[[str | None], object | None],
    rules_module,
) -> tuple[str, ...]:
    mode_logic = resolve_mode_logic_fn(direct_mode)
    if mode_logic is None:
        normalized = normalize_args([str(line).strip() for line in action_lines if str(line).strip()])
        return (normalized,) if normalized else ()
    return tuple(
        mode_logic.normalized_strategy_identities(
            action_lines=action_lines,
            match_lines=match_lines,
            candidates=candidates,
            rules_module=rules_module,
            normalize_args_fn=normalize_args,
        )
    )


def strategy_lookup_for_candidates(
    *,
    candidates: tuple[str, ...],
    direct_mode: str | None,
    catalogs: dict,
    strategy_lookup_cache: dict[tuple[tuple[str, ...], str], dict[str, str]] | None,
    identities_fn: Callable[[list[str] | tuple[str, ...], str | None, list[str] | tuple[str, ...] | None, tuple[str, ...] | list[str] | None], tuple[str, ...]],
) -> dict[str, str]:
    resolved_mode = str(direct_mode or "").strip().lower()
    cache_key = (tuple(candidates or ()), resolved_mode)
    cache = strategy_lookup_cache if strategy_lookup_cache is not None else {}
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    lookup: dict[str, str] = {}
    for name in cache_key[0]:
        for entry in catalogs.get(name, {}).values():
            identities = identities_fn(entry.args.splitlines(), resolved_mode, None, candidates)
            for normalized in identities:
                if not normalized:
                    continue
                lookup.setdefault(normalized, entry.strategy_id)

    if strategy_lookup_cache is not None:
        strategy_lookup_cache[cache_key] = lookup
    return lookup


def infer_strategy_id(
    *,
    action_lines: list[str],
    candidates: tuple[str, ...],
    direct_mode: str | None,
    match_lines: list[str] | tuple[str, ...] | None,
    catalogs: dict,
    strategy_lookup_cache: dict[tuple[tuple[str, ...], str], dict[str, str]] | None,
    identities_fn: Callable[[list[str] | tuple[str, ...], str | None, list[str] | tuple[str, ...] | None, tuple[str, ...] | list[str] | None], tuple[str, ...]],
) -> str:
    identities = identities_fn(action_lines, direct_mode, match_lines, candidates)
    if not identities:
        return "none"
    lookup = strategy_lookup_for_candidates(
        candidates=candidates,
        direct_mode=direct_mode,
        catalogs=catalogs,
        strategy_lookup_cache=strategy_lookup_cache,
        identities_fn=identities_fn,
    )
    for normalized in identities:
        matched = lookup.get(normalized)
        if matched:
            return matched
    return "custom"
