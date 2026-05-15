from __future__ import annotations

import webbrowser
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalActionResult:
    ok: bool
    error: str = ""


def open_url(url: str) -> ExternalActionResult:
    target = str(url or "").strip()
    if not target:
        return ExternalActionResult(ok=False, error="Пустая ссылка")
    try:
        webbrowser.open(target)
        return ExternalActionResult(ok=True)
    except Exception as exc:
        return ExternalActionResult(ok=False, error=str(exc))
