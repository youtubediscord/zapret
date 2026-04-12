from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app_state.main_window_state import MainWindowStateStore

_UNSET = object()


@dataclass(frozen=True, slots=True)
class LaunchRuntimeSnapshot:
    phase: str = "stopped"
    running: bool = False
    last_error: str = ""
    launch_method: str = ""


@dataclass(frozen=True, slots=True)
class LaunchRuntimeOwnershipMap:
    """Документирует честный контракт launch runtime state после чистки слоя."""

    canonical_writers: tuple[str, ...]
    canonical_readers: tuple[str, ...]
    allowed_auxiliary_writers: tuple[str, ...]
    single_source_of_truth: str


@dataclass(slots=True)
class _LaunchRuntimeTrackingState:
    """Приватный tracking state сервиса.

    Эти данные нужны только для внутреннего мониторинга процесса и не являются
    частью общего window-level UI state.
    """

    expected_process: str = ""
    pid: int | None = None


class LaunchRuntimeService:
    """Единственная точка записи runtime-состояния DPI."""

    @staticmethod
    def build_ownership_map() -> LaunchRuntimeOwnershipMap:
        """Явная карта владения DPI runtime state.

        Здесь фиксируется канонический контракт:
        - window-level состояние DPI хранится только в `MainWindowStateStore`;
        - писать в него должен `LaunchRuntimeService`, а не страницы и не window mixin;
        - публичный snapshot сервиса содержит только поля, реально нужные внешним читателям:
          `launch_method`, `phase`, `running`, `last_error`;
        - технические поля мониторинга процесса (`expected_process`, `pid`) живут только
          во внутреннем tracking state сервиса и не экспортируются в общий UI store;
        - UI читает уже готовое состояние из store/AppRuntimeState и не собирает
          параллельный источник истины локально.
        """

        return LaunchRuntimeOwnershipMap(
            canonical_writers=(
                "direct_launch.runtime.controller.DirectLaunchController._begin_runtime_start",
                "direct_launch.runtime.controller.DirectLaunchController._mark_runtime_running",
                "direct_launch.runtime.controller.DirectLaunchController._mark_runtime_failed",
                "direct_launch.runtime.controller.DirectLaunchController._begin_runtime_stop",
                "direct_launch.runtime.controller.DirectLaunchController._mark_runtime_stopped",
            ),
            canonical_readers=(
                "main.LupiDPIApp._apply_runner_failure_update",
                "direct_launch.runtime.lifecycle_feedback.verify_dpi_process_running",
                "direct_control.zapret1.page.Zapret1DirectControlPage._get_current_dpi_runtime_state",
                "ui.pages.control_page.ControlPage._get_current_dpi_runtime_state",
                "direct_control.zapret2.page.Zapret2DirectControlPage._on_ui_state_changed",
                "tray.SystemTrayManager._is_launch_running/_launch_phase via AppRuntimeState",
            ),
            allowed_auxiliary_writers=(
                "managers.initialization_manager.InitializationManager._init_process_monitor -> bootstrap_probe",
                "managers.launch_autostart_manager.LaunchAutostartManager._mark_runtime_stopped",
                "main.LupiDPIApp._apply_runner_failure_update",
            ),
            single_source_of_truth="app_state.main_window_state.MainWindowStateStore",
        )

    def __init__(self, app_instance_or_store) -> None:
        self.app = None
        self._direct_store = None
        self._tracking_state = _LaunchRuntimeTrackingState()
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

    def snapshot(self) -> LaunchRuntimeSnapshot:
        """Возвращает только публичную часть launch runtime state.

        Важно: внутренний process-tracking (`expected_process`, `pid`) здесь намеренно
        не экспортируется. Для внешнего кода это не часть общего UI/runtime контракта.
        """
        store = self._store()
        if store is None:
            return LaunchRuntimeSnapshot()
        try:
            state = store.snapshot()
            return LaunchRuntimeSnapshot(
                launch_method=str(state.launch_method or "").strip().lower(),
                phase=str(state.launch_phase or "stopped").strip().lower() or "stopped",
                running=bool(state.launch_running),
                last_error=str(state.launch_last_error or "").strip(),
            )
        except Exception:
            return LaunchRuntimeSnapshot()

    def current_phase(self) -> str:
        return self.snapshot().phase

    def is_running(self) -> bool:
        return bool(self.snapshot().running)

    def begin_start(
        self,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        self._set_tracking_state(expected_process=expected_process, pid=None)
        changes = self._runtime_changes(
            phase="starting",
            running=False,
            last_error="",
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
        self._set_tracking_state(expected_process=expected_process, pid=None)
        changes = self._runtime_changes(
            phase="autostart_pending",
            running=False,
            last_error="",
        )
        if launch_method is not None:
            changes["launch_method"] = str(launch_method or "").strip().lower()
        return self._apply(**changes)

    def begin_stop(self) -> bool:
        return self._apply(
            **self._runtime_changes(
                phase="stopping",
                running=False,
                last_error="",
            )
        )

    def mark_running(
        self,
        *,
        pid: int | None = None,
        expected_process: str | None = None,
    ) -> bool:
        tracked = self._tracking_state
        next_expected_process = tracked.expected_process if expected_process is None else str(expected_process or "").strip().lower()
        next_pid = pid if isinstance(pid, int) else tracked.pid
        self._set_tracking_state(expected_process=next_expected_process, pid=next_pid)
        return self._apply(
            **self._runtime_changes(
                phase="running",
                running=True,
                last_error="",
            )
        )

    def mark_start_failed(self, error: str) -> bool:
        self._set_tracking_state(pid=None)
        return self._apply(
            **self._runtime_changes(
                phase="failed",
                running=False,
                last_error=error,
            )
        )

    def mark_stopped(self, *, clear_error: bool = True) -> bool:
        snap = self.snapshot()
        self._set_tracking_state(expected_process="", pid=None)
        return self._apply(
            **self._runtime_changes(
                phase="stopped",
                running=False,
                last_error="" if clear_error else snap.last_error,
            )
        )

    def bootstrap_probe(
        self,
        running: bool,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        self._set_tracking_state(
            expected_process=expected_process if (running or self.current_phase() == "autostart_pending") else "",
            pid=None,
        )
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
            last_error="",
        )
        if launch_method is not None:
            changes["launch_method"] = str(launch_method or "").strip().lower()
        return self._apply(**changes)

    def observe_process_details(self, details: Mapping[str, Any] | None) -> bool:
        normalized = self._normalize_process_details(details)
        snap = self.snapshot()
        tracked = self._tracking_state

        expected = str(tracked.expected_process or "").strip().lower()
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
                )
            return False

        if snap.phase == "running":
            if matched_pid is not None:
                if matched_pid != tracked.pid:
                    return self.mark_running(
                        pid=matched_pid,
                        expected_process=matched_name or expected,
                    )
                return False
            if expected:
                return self.mark_start_failed(f"{expected} не найден среди активных процессов")
            return False

        if snap.phase == "stopping":
            if matched_pid is not None:
                if matched_pid != tracked.pid:
                    self._set_tracking_state(expected_process=matched_name or expected, pid=matched_pid)
                    return self._apply(
                        **self._runtime_changes(
                            phase="stopping",
                            running=False,
                            last_error="",
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
        last_error: str,
    ) -> dict[str, object]:
        return {
            "launch_phase": str(phase or "stopped").strip().lower() or "stopped",
            "launch_running": bool(running),
            "launch_last_error": str(last_error or "").strip(),
        }

    def _set_tracking_state(
        self,
        *,
        expected_process: str | None = None,
        pid: int | None | object = _UNSET,
    ) -> None:
        if expected_process is not None:
            self._tracking_state.expected_process = str(expected_process or "").strip().lower()
        if pid is not _UNSET:
            self._tracking_state.pid = int(pid) if isinstance(pid, int) else None

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
