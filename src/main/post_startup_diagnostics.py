from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log
from main.post_startup_diagnostic_workers import build_global_exception_handler, run_cpu_diagnostic
from main.runtime_state import is_cpu_diagnostic_enabled
from main.post_startup_threading import enqueue_subsystem_task


def install_cpu_diagnostic() -> None:
    if is_cpu_diagnostic_enabled():
        enqueue_subsystem_task("diagnostics", "CPUDiagnostic", run_cpu_diagnostic)


def _auto_qt_event_diag_enabled() -> bool:
    raw = os.environ.get("ZAPRET_AUTO_QT_EVENT_DIAGNOSTIC")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return False


class _QtEventDiagBridge(QObject):
    install_requested = pyqtSignal()


def install_qt_event_diagnostic_probe() -> None:
    if not _auto_qt_event_diag_enabled():
        return

    qt_event_diag_bridge = _QtEventDiagBridge()

    def _install_qt_event_diag() -> None:
        try:
            from PyQt6.QtWidgets import QApplication
            from main.qt_event_diagnostics import install_qt_event_diagnostic

            install_qt_event_diagnostic(
                QApplication.instance(),
                interval_ms=5000,
                top_n=14,
                max_reports=8,
            )
        except Exception as exc:
            log(f"Qt event auto diagnostic install failed: {exc}", "WARNING")

    qt_event_diag_bridge.install_requested.connect(_install_qt_event_diag)

    def _auto_qt_event_diag_probe() -> None:
        try:
            import time as _time
            import psutil as _psutil

            _time.sleep(18)
            proc = _psutil.Process()
            proc.cpu_percent(interval=None)
            cpu = float(proc.cpu_percent(interval=5.0))
            log(f"Auto Qt event diagnostic CPU sample: {cpu:.1f}%", "INFO")
            if cpu >= 15.0:
                log("Auto Qt event diagnostic enabled due to high GUI CPU", "WARNING")
                qt_event_diag_bridge.install_requested.emit()
        except Exception as exc:
            log(f"Auto Qt event diagnostic probe failed: {exc}", "DEBUG")

    enqueue_subsystem_task("diagnostics", "QtEventAutoDiagnosticProbe", _auto_qt_event_diag_probe)


def install_global_exception_handler() -> None:
    sys.excepthook = build_global_exception_handler()
