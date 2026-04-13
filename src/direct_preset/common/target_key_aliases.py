from __future__ import annotations

from .target_metadata_loader import load_target_metadata


def resolve_canonical_target_key(target_key: str) -> str:
    normalized = str(target_key or "").strip().lower()
    if not normalized:
        return ""

    for canonical_key, payload in load_target_metadata().items():
        aliases = str((payload or {}).get("aliases") or "").strip().lower()
        if not aliases:
            continue
        alias_tokens = [token.strip() for token in aliases.split(",") if token.strip()]
        if normalized in alias_tokens:
            return str(canonical_key or "").strip().lower() or normalized

    return normalized
