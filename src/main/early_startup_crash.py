from __future__ import annotations

import datetime as _datetime
import os
import sys
import traceback
from types import TracebackType


def _app_dir() -> str:
    executable = getattr(sys, "executable", "") or ""
    if executable:
        return os.path.dirname(os.path.abspath(executable))
    return os.getcwd()


def _crash_log_path() -> str:
    return os.path.join(_app_dir(), "logs", "crashes", "early_startup_crash.log")


def write_early_startup_crash(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    path = _crash_log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n=== Early startup crash ===\n")
            handle.write(f"Time: {_datetime.datetime.now().isoformat(timespec='seconds')}\n")
            handle.write(f"Executable: {getattr(sys, 'executable', '')}\n")
            handle.write(f"Working directory: {os.getcwd()}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=handle)
    except Exception:
        pass


def install_early_startup_crash_handler() -> None:
    if getattr(sys, "_zapret_early_startup_crash_handler_installed", False):
        return

    previous_excepthook = sys.excepthook

    def _excepthook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        write_early_startup_crash(exc_type, exc, tb)
        previous_excepthook(exc_type, exc, tb)

    sys.excepthook = _excepthook
    sys._zapret_early_startup_crash_handler_installed = True


__all__ = ["install_early_startup_crash_handler", "write_early_startup_crash"]
