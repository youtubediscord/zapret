from __future__ import annotations

import re

from .source_preset_models import OutRangeSettings


_OUT_RANGE_STANDALONE_RE = re.compile(r"^--out-range=(?P<expr>.+)$", re.IGNORECASE)
_OUT_RANGE_INLINE_RE = re.compile(r":out_range=(?P<expr>\"[^\"]+\"|'[^']+'|[^:\s]+)(?=(:|\s|$))", re.IGNORECASE)

_OUT_RANGE_SIMPLE_AUTO_RE = re.compile(r"^a$", re.IGNORECASE)
_OUT_RANGE_SIMPLE_NEVER_RE = re.compile(r"^x$", re.IGNORECASE)
_OUT_RANGE_SIMPLE_RE = re.compile(r"^-(?P<mode>[nd])(?P<value>\d+)$", re.IGNORECASE)
_OUT_RANGE_LEGACY_SIMPLE_RE = re.compile(r"^(?P<mode>[nd]?)(?P<value>\d+)$", re.IGNORECASE)
_OUT_RANGE_BOUND_RE = r"(?:[ndspb]?\d+)"
_OUT_RANGE_RANGE_RE = re.compile(
    rf"^(?:{_OUT_RANGE_BOUND_RE}(?:-|<){_OUT_RANGE_BOUND_RE}|(?:-|<){_OUT_RANGE_BOUND_RE}|{_OUT_RANGE_BOUND_RE}-)$",
    re.IGNORECASE,
)

DEFAULT_OUT_RANGE_VALUE = 8
DEFAULT_OUT_RANGE_MODE = "d"
VALUELESS_OUT_RANGE_MODES = {"a", "x"}
SIMPLE_OUT_RANGE_MODES = VALUELESS_OUT_RANGE_MODES | {"n", "d"}


def _strip_outer_quotes(value: str) -> str:
    text = str(value or "").strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    return text.strip()


def normalize_out_range_expression(expression: object) -> str:
    return _strip_outer_quotes(str(expression or "")).strip().lower()


def normalize_simple_out_range_mode(mode: object, *, default: str = DEFAULT_OUT_RANGE_MODE) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in SIMPLE_OUT_RANGE_MODES:
        return normalized
    fallback = str(default or DEFAULT_OUT_RANGE_MODE).strip().lower()
    return fallback if fallback in SIMPLE_OUT_RANGE_MODES else DEFAULT_OUT_RANGE_MODE


def is_valuefree_out_range_mode(mode: object) -> bool:
    return normalize_simple_out_range_mode(mode) in VALUELESS_OUT_RANGE_MODES


def build_simple_out_range_expression(
    mode: object,
    value: object,
    *,
    default_mode: str = DEFAULT_OUT_RANGE_MODE,
    default_value: int = DEFAULT_OUT_RANGE_VALUE,
) -> str:
    normalized_mode = normalize_simple_out_range_mode(mode, default=default_mode)
    if normalized_mode in VALUELESS_OUT_RANGE_MODES:
        return normalized_mode

    try:
        normalized_value = int(value or 0)
    except Exception:
        normalized_value = 0

    if normalized_value <= 0:
        normalized_mode = DEFAULT_OUT_RANGE_MODE
        normalized_value = DEFAULT_OUT_RANGE_VALUE if int(default_value or 0) <= 0 else int(default_value)

    return f"-{normalized_mode}{normalized_value}"


def is_simple_out_range_expression(expression: object) -> bool:
    expr = normalize_out_range_expression(expression)
    return bool(
        _OUT_RANGE_SIMPLE_AUTO_RE.match(expr)
        or _OUT_RANGE_SIMPLE_NEVER_RE.match(expr)
        or _OUT_RANGE_SIMPLE_RE.match(expr)
        or _OUT_RANGE_LEGACY_SIMPLE_RE.match(expr)
    )


def is_simple_out_range(settings: OutRangeSettings | None) -> bool:
    if settings is None:
        return True
    expr = normalize_out_range_expression(getattr(settings, "expression", "") or "")
    if expr:
        return is_simple_out_range_expression(expr)
    mode = str(getattr(settings, "mode", "") or "").strip().lower()
    return mode in SIMPLE_OUT_RANGE_MODES


def has_explicit_out_range(settings: OutRangeSettings | None) -> bool:
    if settings is None:
        return False
    expr = normalize_out_range_expression(getattr(settings, "expression", "") or "")
    if expr:
        return True
    mode = normalize_simple_out_range_mode(getattr(settings, "mode", ""))
    return bool(getattr(settings, "enabled", False) and (mode in VALUELESS_OUT_RANGE_MODES or int(getattr(settings, "value", 0) or 0) > 0))


def parse_out_range_expression(expression: object, *, raw_line: str = "") -> OutRangeSettings | None:
    expr = normalize_out_range_expression(expression)
    if not expr:
        return None

    if _OUT_RANGE_SIMPLE_AUTO_RE.match(expr):
        return OutRangeSettings(
            enabled=True,
            value=0,
            mode="a",
            expression="a",
            raw_line=raw_line,
        )

    if _OUT_RANGE_SIMPLE_NEVER_RE.match(expr):
        return OutRangeSettings(
            enabled=True,
            value=0,
            mode="x",
            expression="x",
            raw_line=raw_line,
        )

    simple_match = _OUT_RANGE_SIMPLE_RE.match(expr)
    if simple_match:
        mode = simple_match.group("mode").lower()
        value = int(simple_match.group("value"))
        return OutRangeSettings(
            enabled=True,
            value=value,
            mode=mode,
            expression=f"-{mode}{value}",
            raw_line=raw_line,
        )

    legacy_match = _OUT_RANGE_LEGACY_SIMPLE_RE.match(expr)
    if legacy_match:
        mode = legacy_match.group("mode").lower() or "n"
        value = int(legacy_match.group("value"))
        return OutRangeSettings(
            enabled=True,
            value=value,
            mode=mode,
            expression=f"-{mode}{value}",
            raw_line=raw_line,
        )

    if _OUT_RANGE_RANGE_RE.match(expr):
        return OutRangeSettings(
            enabled=True,
            value=0,
            mode="",
            expression=expr,
            raw_line=raw_line,
        )

    return None


def default_out_range_settings() -> OutRangeSettings:
    return OutRangeSettings(
        enabled=True,
        value=DEFAULT_OUT_RANGE_VALUE,
        mode=DEFAULT_OUT_RANGE_MODE,
        expression=f"-{DEFAULT_OUT_RANGE_MODE}{DEFAULT_OUT_RANGE_VALUE}",
    )


def canonical_out_range_argument(settings: OutRangeSettings | None = None) -> str:
    resolved = settings or default_out_range_settings()
    expr = normalize_out_range_expression(getattr(resolved, "expression", "") or "")
    if expr:
        parsed = parse_out_range_expression(expr, raw_line=str(getattr(resolved, "raw_line", "") or ""))
        if parsed is not None:
            return f"--out-range={parsed.expression or expr}"

    return f"--out-range={build_simple_out_range_expression(resolved.mode, getattr(resolved, 'value', 0))}"


def cleanup_action_line_after_inline_out_range(line: str) -> str:
    cleaned = _OUT_RANGE_INLINE_RE.sub("", str(line or "").strip())
    cleaned = re.sub(r"::+", ":", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r":(?=\s|$)", "", cleaned)
    return cleaned.strip()


def normalize_out_range_action_lines(
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

        standalone_match = _OUT_RANGE_STANDALONE_RE.match(stripped)
        if standalone_match:
            parsed = parse_out_range_expression(standalone_match.group("expr"), raw_line=stripped)
            if parsed is not None:
                resolved_out_range = parsed
                if normalize_out_range_expression(standalone_match.group("expr")) != (parsed.expression or ""):
                    fixes.append("canonicalized_out_range")
                if normalized_body and "removed_duplicate_out_range" not in fixes:
                    fixes.append("removed_duplicate_out_range")
                continue
            fixes.append("replaced_invalid_out_range")
            continue

        inline_match = _OUT_RANGE_INLINE_RE.search(stripped)
        if inline_match:
            parsed = parse_out_range_expression(inline_match.group("expr"), raw_line=stripped)
            if parsed is not None and resolved_out_range is None:
                resolved_out_range = parsed
            normalized_body.append(stripped)
            continue

        normalized_body.append(stripped)

    if resolved_out_range is None and default_if_missing and normalized_body:
        resolved_out_range = default_out_range_settings()
        fixes.append("applied_default_out_range")

    if has_explicit_out_range(resolved_out_range):
        return [canonical_out_range_argument(resolved_out_range), *normalized_body], tuple(dict.fromkeys(fixes)), resolved_out_range
    return list(normalized_body), tuple(dict.fromkeys(fixes)), resolved_out_range


def parse_out_range(action_lines: list[str]) -> OutRangeSettings:
    for line in action_lines:
        stripped = line.strip()

        standalone_match = _OUT_RANGE_STANDALONE_RE.match(stripped)
        if standalone_match:
            parsed = parse_out_range_expression(standalone_match.group("expr"), raw_line=stripped)
            if parsed is not None:
                return parsed

        inline_match = _OUT_RANGE_INLINE_RE.search(stripped)
        if inline_match:
            parsed = parse_out_range_expression(inline_match.group("expr"), raw_line=stripped)
            if parsed is not None:
                return parsed

    return OutRangeSettings()
