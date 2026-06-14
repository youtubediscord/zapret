from __future__ import annotations

from dataclasses import dataclass
import re
import sys
from pathlib import Path


_STARTUP_METRIC_RE = re.compile(r"\bStartup (?P<marker>Startup[A-Za-z0-9]+):\s+(?P<ms>\d+)ms\b")
_PAGE_LIFECYCLE_WARMUP_RE = re.compile(r"\bPageLifecycle:\s+(?P<page>[A-Z0-9_]+)\s+warmup\s+(?P<ms>\d+)ms\b")
_STARTUP_PAGE_WARMUP_MARKER_RE = re.compile(r"^StartupPage[A-Za-z0-9]+WarmupQueued$")
_HIDDEN_TRAY_LAUNCH_MARKER = "Запуск приложения скрыто в трее"


@dataclass(frozen=True, slots=True)
class StartupMetric:
    marker: str
    elapsed_ms: int
    line_number: int
    line: str


@dataclass(frozen=True, slots=True)
class StartupLogContractResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()


_AFTER_INTERACTIVE_MARKERS: frozenset[str] = frozenset(
    {
        "StartupContinueAfterUiReadyDispatch",
        "StartupRuntimeInitQueued",
        "StartupRuntimePhaseTwoQueued",
        "StartupCoreReady",
        "StartupPostInit",
        "StartupPostInitResolveMethod",
        "StartupPostInitDeferredScheduled",
        "StartupDpiAutostart",
        "StartupPostInitQuickPhase",
        "StartupPostInitDeferredStart",
        "StartupPostInitDeferredDispatch",
        "StartupPostInitChecksQueued",
        "StartupPostInitChecksStarted",
        "StartupPostInitChecksFinished",
        "StartupNetworkDataWarmupQueued",
        "StartupPostInitNetworkDataWarmupStarted",
        "StartupBackendPageDataWarmupQueued",
        "StartupBackendPageDataWarmupStarted",
        "StartupProfileWarmupQueued",
        "StartupProfileWarmupStarted",
        "StartupPresetSetupUiWarmupQueued",
        "StartupPresetSetupUiWarmupFinished",
        "StartupUserPresetsWarmupQueued",
        "StartupUserPresetsWarmupStarted",
        "StartupSidebarSearchQueued",
        "StartupSidebarSearchReady",
        "StartupHiddenModeNavQueued",
        "StartupHiddenModeNavReady",
    }
)


def parse_startup_metrics(text: str) -> tuple[StartupMetric, ...]:
    metrics: list[StartupMetric] = []
    for line_number, line in enumerate(str(text or "").splitlines(), start=1):
        match = _STARTUP_METRIC_RE.search(line)
        if match is None:
            continue
        metrics.append(
            StartupMetric(
                marker=match.group("marker"),
                elapsed_ms=int(match.group("ms")),
                line_number=line_number,
                line=line.rstrip(),
            )
        )
    return tuple(metrics)


def _first_metric(metrics: tuple[StartupMetric, ...], marker: str) -> StartupMetric | None:
    for metric in metrics:
        if metric.marker == marker:
            return metric
    return None


def _must_start_after_interactive(marker: str) -> bool:
    if marker.startswith("StartupStep"):
        return True
    if marker in _AFTER_INTERACTIVE_MARKERS:
        return True
    return False


def validate_startup_log_contract(text: str) -> StartupLogContractResult:
    log_text = str(text or "")
    metrics = parse_startup_metrics(text)
    errors: list[str] = []
    warnings: list[str] = []
    hidden_tray_launch = _HIDDEN_TRAY_LAUNCH_MARKER in log_text

    if not metrics:
        return StartupLogContractResult(
            ok=False,
            errors=("В логе не найдены startup-метрики формата 'Startup <marker>: <ms>'.",),
        )

    for line_number, line in enumerate(log_text.splitlines(), start=1):
        match = _PAGE_LIFECYCLE_WARMUP_RE.search(line)
        if match is None:
            continue
        errors.append(
            "GUI-прогрев страницы создаёт или догревает Qt-страницу в startup-логе: "
            f"{match.group('page')} warmup {match.group('ms')}ms, строка {line_number}. "
            "Фоновый startup-прогрев должен греть данные через кэш, а не Qt-виджеты."
        )

    ttff = _first_metric(metrics, "StartupTTFF")
    interactive = _first_metric(metrics, "StartupInteractive")

    if ttff is None and hidden_tray_launch:
        warnings.append(
            "StartupTTFF не найден: приложение стартовало скрыто в трее, окно могли ещё не открывать."
        )
    elif ttff is None:
        errors.append("Не найдена метрика StartupTTFF: непонятно, когда окно впервые показалось.")
    if interactive is None:
        errors.append("Не найдена метрика StartupInteractive: непонятно, когда UI стал готов к кликам.")

    if (
        not hidden_tray_launch
        and ttff is not None
        and interactive is not None
        and interactive.elapsed_ms < ttff.elapsed_ms
    ):
        errors.append(
            "StartupInteractive раньше StartupTTFF: UI не может считаться готовым до первого показа окна "
            f"({interactive.elapsed_ms}ms < {ttff.elapsed_ms}ms)."
        )

    if interactive is None:
        return StartupLogContractResult(ok=False, errors=tuple(errors), warnings=tuple(warnings))

    for metric in metrics:
        if _STARTUP_PAGE_WARMUP_MARKER_RE.match(metric.marker):
            errors.append(
                f"{metric.marker} ставит GUI-прогрев страницы во время startup, строка {metric.line_number}. "
                "Во время запуска можно греть только данные через backend-кэш."
            )
            continue
        if not _must_start_after_interactive(metric.marker):
            continue
        if metric.elapsed_ms < interactive.elapsed_ms:
            errors.append(
                f"{metric.marker} начался раньше StartupInteractive: "
                f"{metric.elapsed_ms}ms < {interactive.elapsed_ms}ms, строка {metric.line_number}."
            )

    continue_dispatch = _first_metric(metrics, "StartupContinueAfterUiReadyDispatch")
    if continue_dispatch is not None and continue_dispatch.elapsed_ms < interactive.elapsed_ms:
        errors.append(
            "Продолжение startup запущено раньше готовности UI: "
            f"{continue_dispatch.elapsed_ms}ms < {interactive.elapsed_ms}ms."
        )

    core_ready = _first_metric(metrics, "StartupCoreReady")
    post_init = _first_metric(metrics, "StartupPostInit")
    if core_ready is not None and core_ready.elapsed_ms < interactive.elapsed_ms:
        errors.append(
            f"StartupCoreReady раньше StartupInteractive: {core_ready.elapsed_ms}ms < {interactive.elapsed_ms}ms."
        )
    if post_init is not None and core_ready is not None and post_init.elapsed_ms < core_ready.elapsed_ms:
        errors.append(
            f"StartupPostInit раньше StartupCoreReady: {post_init.elapsed_ms}ms < {core_ready.elapsed_ms}ms."
        )

    dpi_dispatch = _first_metric(metrics, "StartupPostInitDeferredStart")
    if dpi_dispatch is None:
        warnings.append("Не найдена StartupPostInitDeferredStart: возможно, DPI autostart был отключён или не дошёл до запуска.")
    elif post_init is not None and dpi_dispatch.elapsed_ms < post_init.elapsed_ms:
        errors.append(
            "DPI autostart начался раньше post-init: "
            f"{dpi_dispatch.elapsed_ms}ms < {post_init.elapsed_ms}ms."
        )

    return StartupLogContractResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Использование: python -m main.startup_log_contract <zapret_log.txt>")
        return 2

    path = Path(args[0])
    result = validate_startup_log_contract(path.read_text(encoding="utf-8", errors="replace"))
    if result.ok:
        print("Startup log contract: OK")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0

    print("Startup log contract: FAILED")
    for error in result.errors:
        print(f"ERROR: {error}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
