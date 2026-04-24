from __future__ import annotations

from ..common.out_range import (
    canonical_out_range_argument,
    cleanup_action_line_after_inline_out_range as _cleanup_action_line_after_inline_out_range,
    default_out_range_settings,
    has_explicit_out_range,
    normalize_out_range_action_lines as normalize_action_lines,
    parse_out_range,
)
from ..common.source_preset_models import OutRangeSettings, SendSettings, SyndataSettings


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
    if has_explicit_out_range(out_range):
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
