from __future__ import annotations

from dataclasses import replace
import re

from ..common.source_preset_models import OutRangeSettings, SendSettings, SyndataSettings


_OUT_RANGE_STANDALONE_RE = re.compile(r"^--out-range=-(?P<mode>[nd])(?P<value>\d+)$", re.IGNORECASE)
_OUT_RANGE_LEGACY_STANDALONE_RE = re.compile(r"^--out-range=(?P<mode>[nd]?)(?P<value>\d+)$", re.IGNORECASE)
_OUT_RANGE_INLINE_RE = re.compile(r":out_range=-(?P<mode>[nd])(?P<value>\d+)(?=(:|\s|$))", re.IGNORECASE)
DEFAULT_OUT_RANGE_VALUE = 8
DEFAULT_OUT_RANGE_MODE = "d"


def default_out_range_settings() -> OutRangeSettings:
    return OutRangeSettings(enabled=True, value=DEFAULT_OUT_RANGE_VALUE, mode=DEFAULT_OUT_RANGE_MODE)


def canonical_out_range_argument(settings: OutRangeSettings | None = None) -> str:
    resolved = settings or default_out_range_settings()
    mode = "d" if str(resolved.mode or "").strip().lower() == "d" else "n"
    value = int(resolved.value or 0)
    if value <= 0:
        value = DEFAULT_OUT_RANGE_VALUE
        mode = DEFAULT_OUT_RANGE_MODE
    return f"--out-range=-{mode}{value}"


def _cleanup_action_line_after_inline_out_range(line: str) -> str:
    cleaned = _OUT_RANGE_INLINE_RE.sub("", str(line or "").strip())
    cleaned = re.sub(r"::+", ":", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r":(?=\s|$)", "", cleaned)
    return cleaned.strip()


def normalize_action_lines(
    action_lines: list[str],
    *,
    default_if_missing: bool = True,
) -> tuple[list[str], tuple[str, ...], OutRangeSettings | None]:
    fixes: list[str] = []
    resolved_out_range: OutRangeSettings | None = None
    normalized_body: list[str] = []

    for line in action_lines:
        stripped = str(line or "").strip()
        if not stripped:
            continue

        canonical_match = _OUT_RANGE_STANDALONE_RE.match(stripped)
        if canonical_match:
            resolved_out_range = OutRangeSettings(
                enabled=True,
                value=int(canonical_match.group("value")),
                mode=canonical_match.group("mode").lower(),
                raw_line=stripped,
            )
            if normalized_body and "removed_duplicate_out_range" not in fixes:
                fixes.append("removed_duplicate_out_range")
            continue

        legacy_match = _OUT_RANGE_LEGACY_STANDALONE_RE.match(stripped)
        if legacy_match:
            resolved_out_range = OutRangeSettings(
                enabled=True,
                value=int(legacy_match.group("value")),
                mode=(legacy_match.group("mode").lower() or "n"),
                raw_line=stripped,
            )
            fixes.append("canonicalized_out_range")
            continue

        if stripped.lower().startswith("--out-range="):
            fixes.append("replaced_invalid_out_range")
            continue

        inline_match = _OUT_RANGE_INLINE_RE.search(stripped)
        if inline_match:
            if resolved_out_range is None:
                resolved_out_range = OutRangeSettings(
                    enabled=True,
                    value=int(inline_match.group("value")),
                    mode=inline_match.group("mode").lower(),
                    raw_line=stripped,
                )
            normalized_body.append(stripped)
            continue

        normalized_body.append(stripped)

    if resolved_out_range is None and default_if_missing and normalized_body:
        resolved_out_range = default_out_range_settings()
        fixes.append("applied_default_out_range")

    if resolved_out_range and resolved_out_range.enabled and int(resolved_out_range.value or 0) > 0:
        return [canonical_out_range_argument(resolved_out_range), *normalized_body], tuple(dict.fromkeys(fixes)), resolved_out_range
    return list(normalized_body), tuple(dict.fromkeys(fixes)), resolved_out_range


def parse_out_range(action_lines: list[str]) -> OutRangeSettings:
    for line in action_lines:
        stripped = line.strip()
        match = _OUT_RANGE_STANDALONE_RE.match(stripped)
        if match:
            return OutRangeSettings(
                enabled=True,
                value=int(match.group("value")),
                mode=match.group("mode").lower(),
                raw_line=stripped,
            )
        legacy_match = _OUT_RANGE_LEGACY_STANDALONE_RE.match(stripped)
        if legacy_match:
            mode = legacy_match.group("mode").lower() or "n"
            return OutRangeSettings(
                enabled=True,
                value=int(legacy_match.group("value")),
                mode=mode,
                raw_line=stripped,
            )
        inline_match = _OUT_RANGE_INLINE_RE.search(stripped)
        if inline_match:
            return OutRangeSettings(
                enabled=True,
                value=int(inline_match.group("value")),
                mode=inline_match.group("mode").lower(),
                raw_line=stripped,
            )
    return OutRangeSettings()


def parse_send(action_lines: list[str]) -> SendSettings:
    for line in action_lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered == "--lua-desync=send" or lowered.startswith("--lua-desync=send:"):
            payload = stripped.split("=", 1)[1].split(":", 1)[1] if ":" in stripped.split("=", 1)[1] else ""
            parts = {}
            for token in payload.split(":"):
                if "=" in token:
                    key, value = token.split("=", 1)
                    parts[key.strip().lower()] = value.strip()
                elif token:
                    parts[token.strip().lower()] = "1"
            return SendSettings(
                enabled=True,
                repeats=int(parts.get("repeats", "2") or 2),
                ip_ttl=int(parts.get("ip_ttl", "0") or 0),
                ip6_ttl=int(parts.get("ip6_ttl", "0") or 0),
                ip_id=str(parts.get("ip_id", "none") or "none"),
                badsum=bool(parts.get("badsum")),
                raw_line=stripped,
            )
    return SendSettings()


def parse_syndata(action_lines: list[str]) -> SyndataSettings:
    for line in action_lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered == "--lua-desync=syndata" or lowered.startswith("--lua-desync=syndata:"):
            payload = stripped.split("=", 1)[1].split(":", 1)[1] if ":" in stripped.split("=", 1)[1] else ""
            parts = {}
            for token in payload.split(":"):
                if "=" in token:
                    key, value = token.split("=", 1)
                    parts[key.strip().lower()] = value.strip()
            delta = 0
            autottl_min = 3
            autottl_max = 20
            autottl = str(parts.get("ip_autottl", "") or "")
            if autottl:
                try:
                    delta_part, range_part = autottl.split(",", 1)
                    min_part, max_part = range_part.split("-", 1)
                    delta = int(delta_part)
                    autottl_min = int(min_part)
                    autottl_max = int(max_part)
                except Exception:
                    pass
            return SyndataSettings(
                enabled=True,
                blob=str(parts.get("blob", "tls_google") or "tls_google"),
                tls_mod=str(parts.get("tls_mod", "none") or "none"),
                autottl_delta=delta,
                autottl_min=autottl_min,
                autottl_max=autottl_max,
                tcp_flags_unset=str(parts.get("tcp_flags_unset", "none") or "none"),
                raw_line=stripped,
            )
    return SyndataSettings()


def strip_helper_lines(action_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in action_lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("--out-range="):
            continue
        if lowered == "--lua-desync=send" or lowered.startswith("--lua-desync=send:"):
            continue
        if lowered == "--lua-desync=syndata" or lowered.startswith("--lua-desync=syndata:"):
            continue
        if stripped:
            out.append(stripped)
    return out


def compose_action_lines(strategy_args: list[str], out_range: OutRangeSettings, send: SendSettings, syndata: SyndataSettings) -> list[str]:
    result: list[str] = []
    if out_range.enabled and out_range.value > 0:
        result.append(canonical_out_range_argument(out_range))
    if send.enabled:
        parts = [f"repeats={send.repeats}"]
        if send.ip_ttl:
            parts.append(f"ip_ttl={send.ip_ttl}")
        if send.ip6_ttl:
            parts.append(f"ip6_ttl={send.ip6_ttl}")
        if send.ip_id not in ("", "none"):
            parts.append(f"ip_id={send.ip_id}")
        if send.badsum:
            parts.append("badsum")
        result.append("--lua-desync=send" + (":" + ":".join(parts) if parts else ""))
    if syndata.enabled:
        parts = [f"blob={syndata.blob}"]
        if syndata.tls_mod not in ("", "none"):
            parts.append(f"tls_mod={syndata.tls_mod}")
        if syndata.autottl_delta:
            parts.append(
                f"ip_autottl={syndata.autottl_delta},{syndata.autottl_min}-{syndata.autottl_max}"
            )
        if syndata.tcp_flags_unset not in ("", "none"):
            parts.append(f"tcp_flags_unset={syndata.tcp_flags_unset}")
        result.append("--lua-desync=syndata" + (":" + ":".join(parts) if parts else ""))
    result.extend(line.strip() for line in strategy_args if str(line).strip())
    return result
