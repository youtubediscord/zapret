from __future__ import annotations

from pathlib import Path
import re

from log.log import log



_INLINE_OUT_RANGE_RE = re.compile(r":out_range=-[nd]\d+(?=(:|\s|$))", re.IGNORECASE)


def strip_out_range_from_strategy_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    out_lines: list[str] = []
    for raw in normalized.split("\n"):
        stripped = raw.strip()
        if stripped.lower().startswith("--out-range="):
            continue
        cleaned = _INLINE_OUT_RANGE_RE.sub("", raw)
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def sanitize_strategy_catalog_file(path: Path) -> bool:
    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        log(f"Failed to read strategy catalog {path}: {exc}", "DEBUG")
        return False

    sanitized = strip_out_range_from_strategy_text(original)
    if sanitized == original:
        return False

    try:
        path.write_text(sanitized, encoding="utf-8")
        log(f"Sanitized legacy out-range entries in strategy catalog: {path}", "DEBUG")
        return True
    except Exception as exc:
        log(f"Failed to sanitize strategy catalog {path}: {exc}", "DEBUG")
        return False


def sanitize_strategy_catalog_dir(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0

    changed = 0
    for file_path in sorted(path.glob("*.txt"), key=lambda item: item.name.lower()):
        changed += int(sanitize_strategy_catalog_file(file_path))
    return changed
