from __future__ import annotations

import atexit
import sys
import time
from typing import Callable

from app_notifications import advisory_notification
from log.log import log


def collect_startup_checks_payload(*, verbose_logging_enabled: bool) -> dict:
    started_at = time.perf_counter()
    notifications: list[dict] = []

    from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
    from startup.check_start import collect_startup_notifications, check_goodbyedpi, check_mitmproxy

    preload_service_status("BFE")

    bfe_ok, bfe_notification = ensure_bfe_running()
    if bfe_notification is not None:
        notifications.append(bfe_notification)
    if not bfe_ok:
        log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")

    startup_notifications = collect_startup_notifications()
    notifications.extend(startup_notifications or [])
    log(
        "Startup notifications collected: "
        f"count={len(startup_notifications or [])}",
        "⏱ STARTUP",
    )

    has_gdpi, gdpi_msg = check_goodbyedpi()
    if has_gdpi and gdpi_msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=gdpi_msg,
                source="startup.goodbyedpi",
                queue="startup",
                duration=15000,
                dedupe_key="startup.goodbyedpi",
            )
        )

    has_mitmproxy, mitmproxy_msg = check_mitmproxy()
    if has_mitmproxy and mitmproxy_msg:
        notifications.append(
            advisory_notification(
                level="warning",
                title="Проверка при запуске",
                content=mitmproxy_msg,
                source="startup.mitmproxy",
                queue="startup",
                duration=15000,
                dedupe_key="startup.mitmproxy",
            )
        )

    try:
        from startup.kaspersky import _check_kaspersky_antivirus, build_kaspersky_notification

        kaspersky_detected = bool(_check_kaspersky_antivirus())
        log(
            f"Kaspersky startup check: detected={'yes' if kaspersky_detected else 'no'}",
            "⏱ STARTUP",
        )
        if kaspersky_detected:
            kaspersky_notification = build_kaspersky_notification()
            if kaspersky_notification is not None:
                log("Обнаружен антивирус Kaspersky", "⚠️ KASPERSKY")
                notifications.append(kaspersky_notification)
    except Exception:
        pass

    if verbose_logging_enabled:
        from startup.admin_check_debug import debug_admin_status

        debug_admin_status()

    try:
        atexit.register(bfe_cleanup)
    except Exception:
        pass

    return {
        "notifications": notifications,
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
    }


def collect_deferred_maintenance_payload() -> dict:
    started_at = time.perf_counter()
    telega_found_path = None
    notifications: list[dict] = []

    try:
        try:
            from startup.telega_check import _check_telega_installed, build_telega_notification

            telega_found_path = _check_telega_installed()
            log(
                "Telega deferred check: "
                f"found={'yes' if bool(telega_found_path) else 'no'}"
                + (f", value={telega_found_path}" if telega_found_path else ""),
                "⏱ STARTUP",
            )
            if telega_found_path:
                log(f"Обнаружена Telega Desktop: {telega_found_path}", "🚨 TELEGA")
                telega_notification = build_telega_notification(found_path=str(telega_found_path))
                if telega_notification is not None:
                    notifications.append(telega_notification)
        except Exception:
            telega_found_path = None
    except Exception as exc:
        log(f"Ошибка поздних служебных проверок: {exc}", "❌ ERROR")
    finally:
        try:
            log(
                f"Deferred maintenance notifications collected: count={len(notifications)}",
                "⏱ STARTUP",
            )
        except Exception:
            pass

    return {
        "notifications": notifications,
        "telega_found_path": telega_found_path,
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
    }


def run_startup_update_check() -> dict:
    from updater.startup_update_check import check_for_update_sync

    return check_for_update_sync()


def run_cpu_diagnostic() -> None:
    import threading as _threads
    import traceback as _traceback
    import time as _time

    _time.sleep(15)
    try:
        import psutil as _psutil

        this_proc = _psutil.Process()
        this_proc.cpu_percent(interval=None)
        _time.sleep(1)

        log("=== CPU DIAGNOSTIC: начало ===", "INFO")
        log(f"Активных тредов Python: {_threads.active_count()}", "INFO")

        frames = sys._current_frames()
        for tid, frame in frames.items():
            thread = next((item for item in _threads.enumerate() if item.ident == tid), None)
            name = thread.name if thread else f"tid-{tid}"
            stack = "".join(_traceback.format_stack(frame)).strip()
            log(f"[STACK '{name}']\n{stack[-1200:]}", "INFO")

        samples_gui = []
        for idx in range(5):
            cpu_gui = this_proc.cpu_percent(interval=2.0)
            samples_gui.append(cpu_gui)
            winws_parts = []
            for proc in _psutil.process_iter(["name", "cpu_percent"]):
                try:
                    proc_name = (proc.info.get("name") or "").lower()
                    if proc_name in ("winws.exe", "winws2.exe"):
                        winws_parts.append(f"{proc_name}={proc.cpu_percent():.1f}%")
                except Exception:
                    pass
            winws_str = ", ".join(winws_parts) if winws_parts else "не запущен"
            log(f"[CPU {idx + 1}/5] Python GUI: {cpu_gui:.1f}%  |  winws: {winws_str}", "INFO")

        avg = sum(samples_gui) / len(samples_gui) if samples_gui else 0
        log(f"=== CPU DIAGNOSTIC DONE: avg Python GUI = {avg:.1f}% ===", "INFO")

        if avg > 20:
            try:
                from collections import Counter

                sample_counts: dict = Counter()
                for _ in range(50):
                    _time.sleep(0.1)
                    frames2 = sys._current_frames()
                    for tid2, frame2 in frames2.items():
                        thread2 = next((item for item in _threads.enumerate() if item.ident == tid2), None)
                        thread_name = thread2.name if thread2 else f"tid-{tid2}"
                        stack2 = _traceback.extract_stack(frame2)
                        key = thread_name + " | " + " -> ".join(
                            f"{frame.filename.split('/')[-1].split(chr(92))[-1]}:{frame.lineno}:{frame.name}"
                            for frame in stack2[-4:]
                        )
                        sample_counts[key] += 1
                top = sample_counts.most_common(15)
                report = "\n".join(f"  {count:3d}x  {key}" for key, count in top)
                log(f"[SAMPLING top-15 hotspots (50 samples x 100ms)]\n{report}", "INFO")
            except Exception as exc:
                log(f"Sampling error: {exc}", "WARNING")
    except Exception as exc:
        log(f"CPU diagnostic error: {exc}", "WARNING")


def build_global_exception_handler() -> Callable[[type[BaseException], BaseException, object], None]:
    def _global_exception_handler(exctype, value, tb_obj) -> None:
        import traceback as tb

        try:
            error_msg = "".join(tb.format_exception(exctype, value, tb_obj))
        except Exception as format_error:
            try:
                base_error = "".join(tb.format_exception_only(exctype, value)).strip()
            except Exception:
                base_error = f"{getattr(exctype, '__name__', exctype)}: {value!r}"
            error_msg = f"{base_error}\n[traceback formatting failed: {format_error!r}]"
        log(f"UNCAUGHT EXCEPTION: {error_msg}", level="❌ CRITICAL")

    return _global_exception_handler
