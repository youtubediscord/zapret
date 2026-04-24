"""Args/helper logic для страницы деталей стратегии Z2."""

from __future__ import annotations

import re


def extract_desync_technique_from_arg(line: str) -> str | None:
    """Извлекает имя desync-техники из одной строки аргумента."""
    source = (line or "").strip()
    match = re.match(r"^--(?:lua-desync|dpi-desync)=([a-zA-Z0-9_-]+)", source)
    if not match:
        return None
    return match.group(1).strip().lower() or None


def map_desync_technique_to_tcp_phase(technique: str) -> str | None:
    """Сопоставляет desync-технику одной из внутренних TCP phase вкладок."""
    normalized = (technique or "").strip().lower()
    if not normalized:
        return None
    if normalized == "pass":
        return "multisplit"
    if normalized == "fake":
        return "fake"
    if normalized in ("multisplit", "fakedsplit", "hostfakesplit"):
        return "multisplit"
    if normalized in ("multidisorder", "fakeddisorder"):
        return "multidisorder"
    if normalized == "multidisorder_legacy":
        return "multidisorder_legacy"
    if normalized == "tcpseg":
        return "tcpseg"
    if normalized == "oob":
        return "oob"
    return "other"


def normalize_args_text(text: str) -> str:
    """Нормализует текст args для точного сравнения без потери порядка строк."""
    if not text:
        return ""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    return "\n".join(lines).strip()
