from __future__ import annotations

from ui.page_names import PageName
from log import log


def _resolve_page_label(page_name: PageName | str | None) -> str:
    if isinstance(page_name, PageName):
        return page_name.name
    text = str(page_name or "").strip()
    return text or "UNKNOWN_PAGE"


def log_page_metric(
    page_name: PageName | str | None,
    stage: str,
    elapsed_ms: float,
    *,
    budget_ms: int | None = None,
    extra: str | None = None,
) -> None:
    """Единая точка логирования метрик lifecycle страниц."""

    label = _resolve_page_label(page_name)
    stage_label = str(stage or "").strip() or "unknown"

    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0

    budget_suffix = f" / budget={int(budget_ms)}ms" if budget_ms is not None else ""
    extra_suffix = f" ({extra})" if extra else ""

    level = "⏱ STARTUP" if rounded >= 80 else "DEBUG"
    if budget_ms is not None and rounded > int(budget_ms):
        level = "WARNING"

    log(
        f"⏱ PageLifecycle: {label} {stage_label} {rounded}ms{budget_suffix}{extra_suffix}",
        level,
    )
