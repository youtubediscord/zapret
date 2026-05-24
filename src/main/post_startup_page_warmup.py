from __future__ import annotations

from dataclasses import dataclass
import time

from app.page_names import PageName
from log.log import log
from main.post_startup_gate import bind_startup_gate, is_startup_host_alive
from main.post_startup_threading import schedule_after
from settings.dpi.strategy_settings import get_strategy_launch_method
from ui.navigation.layout_plan import iter_sidebar_layout_entries
from ui.navigation.schema import get_mode_entry_page


@dataclass(frozen=True, slots=True)
class PageWarmupSpec:
    page_name: PageName
    metric_name: str
    delay_ms: int = 450
    budget_ms: int = 300


PAGE_WARMUP_PRIORITY: tuple[PageName, ...] = (
    PageName.ZAPRET2_USER_PRESETS,
    PageName.ZAPRET2_PRESET_SETUP,
    PageName.ZAPRET1_USER_PRESETS,
    PageName.ZAPRET1_PRESET_SETUP,
    PageName.LOGS,
    PageName.PREMIUM,
    PageName.APPEARANCE,
    PageName.NETWORK,
    PageName.HOSTS,
    PageName.BLOCKCHECK,
    PageName.TELEGRAM_PROXY,
    PageName.AUTOSTART,
    PageName.ABOUT,
)


def _metric_name_for_page(page_name: PageName) -> str:
    parts = [
        part.title()
        for part in str(getattr(page_name, "name", "") or "").lower().split("_")
        if part
    ]
    suffix = "".join(parts) or "Page"
    return f"StartupPage{suffix}WarmupQueued"


def page_warmup_plan_for_method(method: str | None) -> tuple[PageWarmupSpec, ...]:
    entry_page = get_mode_entry_page(method)
    sidebar_pages: list[PageName] = []
    for entry in iter_sidebar_layout_entries(method):
        if getattr(entry, "kind", "") != "page":
            continue
        page_name = getattr(entry, "page_name", None)
        if not isinstance(page_name, PageName):
            continue
        if page_name == entry_page:
            continue
        if page_name not in sidebar_pages:
            sidebar_pages.append(page_name)

    priority = {page_name: index for index, page_name in enumerate(PAGE_WARMUP_PRIORITY)}
    pages = sorted(
        sidebar_pages,
        key=lambda page_name: (
            priority.get(page_name, len(priority)),
            sidebar_pages.index(page_name),
        ),
    )

    return tuple(
        PageWarmupSpec(
            page_name=page_name,
            delay_ms=450 if index == 0 else 180,
            metric_name=_metric_name_for_page(page_name),
            budget_ms=300,
        )
        for index, page_name in enumerate(pages)
    )


def install_page_warmup(
    startup_host,
    *,
    log_startup_metric,
    plan: tuple[PageWarmupSpec, ...] | None = None,
) -> None:
    resolved_plan = plan
    if resolved_plan is None:
        resolved_plan = page_warmup_plan_for_method(get_strategy_launch_method())

    def _metric_detail(index: int, delay_ms: int) -> str:
        page_name = resolved_plan[index].page_name.name if index < len(resolved_plan) else "unknown"
        if index == 0:
            return f"{page_name}, {delay_ms}ms after interactive"
        return f"{page_name}, {delay_ms}ms after previous warmup"

    def _run_page_warmup_spec(index: int) -> None:
        if not is_startup_host_alive(startup_host):
            return
        if index >= len(resolved_plan):
            return

        spec = resolved_plan[index]
        started_at = time.perf_counter()
        try:
            startup_host.warm_page(spec.page_name)
        except Exception as exc:
            log(f"Фоновый прогрев страницы {spec.page_name.name} не выполнен: {exc}", "DEBUG")

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if elapsed_ms > int(spec.budget_ms):
            log(
                f"Фоновый прогрев страницы {spec.page_name.name} занял {elapsed_ms:.0f}ms "
                f"при бюджете {int(spec.budget_ms)}ms",
                "WARNING",
            )

        _schedule_page_warmup_spec(index + 1)

    def _schedule_page_warmup_spec(index: int) -> None:
        if not is_startup_host_alive(startup_host):
            return
        if index >= len(resolved_plan):
            return

        spec = resolved_plan[index]
        delay_ms = max(0, int(spec.delay_ms))
        log(
            f"Фоновый прогрев страницы {spec.page_name.name} отложен на {delay_ms}ms",
            "DEBUG",
        )
        log_startup_metric(spec.metric_name, _metric_detail(index, delay_ms))
        schedule_after(
            delay_ms,
            lambda: is_startup_host_alive(startup_host) and _run_page_warmup_spec(index),
        )

    def _schedule_page_warmup() -> None:
        _schedule_page_warmup_spec(0)

    bind_startup_gate(
        startup_host.startup_interactive_ready,
        _schedule_page_warmup,
        is_ready=lambda: bool(startup_host.startup_state.interactive_logged),
    )


__all__ = [
    "PAGE_WARMUP_PRIORITY",
    "PageWarmupSpec",
    "install_page_warmup",
    "page_warmup_plan_for_method",
]
