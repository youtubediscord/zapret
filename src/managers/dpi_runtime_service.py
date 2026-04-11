from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ui.main_window_state import MainWindowStateStore


@dataclass(frozen=True, slots=True)
class DpiRuntimeSnapshot:
    phase: str = "stopped"
    running: bool = False
    expected_process: str = ""
    expected_preset_path: str = ""
    pid: int | None = None
    last_error: str = ""
    last_exit_code: int | None = None
    launch_method: str = ""


class DpiRuntimeService:
    """Единственная точка записи runtime-состояния DPI."""

    def __init__(self, app_instance_or_store) -> None:
        self.app = None
        self._direct_store = None
        if isinstance(app_instance_or_store, MainWindowStateStore):
            self._direct_store = app_instance_or_store
        else:
            self.app = app_instance_or_store

    def _store(self) -> MainWindowStateStore | None:
        if isinstance(self._direct_store, MainWindowStateStore):
            return self._direct_store
        store = getattr(self.app, "ui_state_store", None)
        if isinstance(store, MainWindowStateStore):
            return store
        return None

    def snapshot(self) -> DpiRuntimeSnapshot:
        store = self._store()
        if store is None:
            return DpiRuntimeSnapshot()
        try:
            state = store.snapshot()
            return DpiRuntimeSnapshot(
                phase=str(state.dpi_phase or "stopped").strip().lower() or "stopped",
                running=bool(state.dpi_running),
                expected_process=str(state.dpi_expected_process or "").strip().lower(),
                expected_preset_path=str(state.dpi_expected_preset_path or "").strip(),
                pid=state.dpi_pid if isinstance(state.dpi_pid, int) else None,
                last_error=str(state.dpi_last_error or "").strip(),
                last_exit_code=state.dpi_last_exit_code if isinstance(state.dpi_last_exit_code, int) else None,
                launch_method=str(getattr(state, "launch_method", "") or "").strip().lower(),
            )
        except Exception:
            return DpiRuntimeSnapshot()

    def current_phase(self) -> str:
        return self.snapshot().phase

    def is_running(self) -> bool:
        return bool(self.snapshot().running)

    def begin_start(
        self,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
        expected_preset_path: str = "",
    ) -> bool:
        changes = self._runtime_changes(
            phase="starting",
            running=False,
            expected_process=expected_process,
            expected_preset_path=expected_preset_path,
            pid=None,
            last_error="",
            last_exit_code=None,
        )
        if launch_method is not None:
            changes["launch_method"] = str(launch_method or "").strip().lower()
        return self._apply(**changes)

    def mark_autostart_pending(
        self,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        changes = self._runtime_changes(
            phase="autostart_pending",
            running=False,
            expected_process=expected_process,
            expected_preset_path="",
            pid=None,
            last_error="",
            last_exit_code=None,
        )
        if launch_method is not None:
            changes["launch_method"] = str(launch_method or "").strip().lower()
        return self._apply(**changes)

    def begin_stop(self) -> bool:
        snap = self.snapshot()
        return self._apply(
            **self._runtime_changes(
                phase="stopping",
                running=False,
                expected_process=snap.expected_process,
                expected_preset_path=snap.expected_preset_path,
                pid=snap.pid,
                last_error="",
                last_exit_code=None,
            )
        )

    def mark_running(
        self,
        *,
        pid: int | None = None,
        expected_process: str | None = None,
        expected_preset_path: str | None = None,
    ) -> bool:
        snap = self.snapshot()
        return self._apply(
            **self._runtime_changes(
                phase="running",
                running=True,
                expected_process=snap.expected_process if expected_process is None else expected_process,
                expected_preset_path=(
                    snap.expected_preset_path if expected_preset_path is None else expected_preset_path
                ),
                pid=pid if isinstance(pid, int) else snap.pid,
                last_error="",
                last_exit_code=None,
            )
        )

    def mark_start_failed(self, error: str, *, exit_code: int | None = None) -> bool:
        snap = self.snapshot()
        return self._apply(
            **self._runtime_changes(
                phase="failed",
                running=False,
                expected_process=snap.expected_process,
                expected_preset_path=snap.expected_preset_path,
                pid=None,
                last_error=error,
                last_exit_code=exit_code,
            )
        )

    def mark_stopped(self, *, clear_error: bool = True) -> bool:
        snap = self.snapshot()
        return self._apply(
            **self._runtime_changes(
                phase="stopped",
                running=False,
                expected_process="",
                expected_preset_path="",
                pid=None,
                last_error="" if clear_error else snap.last_error,
                last_exit_code=None if clear_error else snap.last_exit_code,
            )
        )

    def bootstrap_probe(
        self,
        running: bool,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        current_phase = self.current_phase()
        if running:
            phase = "running"
        elif current_phase == "autostart_pending":
            phase = "autostart_pending"
        else:
            phase = "stopped"

        changes = self._runtime_changes(
            phase=phase,
            running=bool(running),
            expected_process=expected_process if (running or phase == "autostart_pending") else "",
            expected_preset_path="",
            pid=None,
            last_error="",
            last_exit_code=None,
        )
        if launch_method is not None:
            changes["launch_method"] = str(launch_method or "").strip().lower()
        return self._apply(**changes)

    def observe_process_details(self, details: Mapping[str, Any] | None) -> bool:
        normalized = self._normalize_process_details(details)
        snap = self.snapshot()

        expected = snap.expected_process
        matched_name = expected
        matched_pids = normalized.get(expected, [])

        if not matched_pids and not expected:
            for candidate in ("winws.exe", "winws2.exe"):
                candidate_pids = normalized.get(candidate, [])
                if candidate_pids:
                    matched_name = candidate
                    matched_pids = candidate_pids
                    break

        matched_pid = matched_pids[0] if matched_pids else None

        if snap.phase in {"starting", "autostart_pending"}:
            if matched_pid is not None:
                return self.mark_running(
                    pid=matched_pid,
                    expected_process=matched_name or expected,
                    expected_preset_path=snap.expected_preset_path,
                )
            return False

        if snap.phase == "running":
            if matched_pid is not None:
                if matched_pid != snap.pid:
                    return self.mark_running(
                        pid=matched_pid,
                        expected_process=matched_name or expected,
                        expected_preset_path=snap.expected_preset_path,
                    )
                return False
            if expected:
                return self.mark_start_failed(f"{expected} не найден среди активных процессов")
            return False

        if snap.phase == "stopping":
            if matched_pid is not None:
                if matched_pid != snap.pid:
                    return self._apply(
                        **self._runtime_changes(
                            phase="stopping",
                            running=False,
                            expected_process=matched_name or expected,
                            expected_preset_path=snap.expected_preset_path,
                            pid=matched_pid,
                            last_error="",
                            last_exit_code=None,
                        )
                    )
                return False
            return self.mark_stopped(clear_error=True)

        return False

    def _apply(self, **changes) -> bool:
        store = self._store()
        if store is None or not changes:
            return False
        return bool(store.update(**changes))

    @staticmethod
    def _runtime_changes(
        *,
        phase: str,
        running: bool,
        expected_process: str,
        expected_preset_path: str,
        pid: int | None,
        last_error: str,
        last_exit_code: int | None,
    ) -> dict[str, object]:
        return {
            "dpi_phase": str(phase or "stopped").strip().lower() or "stopped",
            "dpi_running": bool(running),
            "dpi_expected_process": str(expected_process or "").strip().lower(),
            "dpi_expected_preset_path": str(expected_preset_path or "").strip(),
            "dpi_pid": int(pid) if isinstance(pid, int) else None,
            "dpi_last_error": str(last_error or "").strip(),
            "dpi_last_exit_code": int(last_exit_code) if isinstance(last_exit_code, int) else None,
        }

    @staticmethod
    def _normalize_process_details(details: Mapping[str, Any] | None) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        if not details:
            return out
        try:
            iterable = dict(details).items()
        except Exception:
            return out
        for key, value in iterable:
            name = str(key or "").strip().lower()
            if not name:
                continue
            if isinstance(value, list):
                out[name] = [item for item in value if isinstance(item, int)]
            elif isinstance(value, int):
                out[name] = [value]
            else:
                out[name] = []
        return out
