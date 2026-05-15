from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.state_store import AppUiState, MainWindowStateStore
from settings.mode import ALL_WINWS_EXE_NAMES, normalize_launch_method
from winws_runtime.runtime.process_probe import is_winws_process_pid_alive

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
    missing_probe_count: int = 0


class LaunchRuntimeService:
    """Единственная точка записи runtime-состояния DPI."""

    @staticmethod
    def build_initial_ui_state(
        *,
        launch_method: str = "",
        dpi_autostart_enabled: bool = False,
        gui_autostart_enabled: bool = False,
        launch_supported: bool = False,
    ) -> AppUiState:
        """Создаёт начальный UI-state с runtime-полями через runtime-контракт."""

        phase = "autostart_pending" if bool(dpi_autostart_enabled and launch_supported) else "stopped"
        return AppUiState(
            launch_method=normalize_launch_method(launch_method, default=""),
            launch_phase=phase,
            launch_running=False,
            autostart_enabled=bool(gui_autostart_enabled),
        )

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
                "winws_runtime.state.LaunchRuntimeService.build_initial_ui_state",
                "winws_runtime.state.LaunchRuntimeService.begin_start",
                "winws_runtime.state.LaunchRuntimeService.mark_running",
                "winws_runtime.state.LaunchRuntimeService.mark_start_failed",
                "winws_runtime.state.LaunchRuntimeService.begin_stop",
                "winws_runtime.state.LaunchRuntimeService.mark_stopped",
                "winws_runtime.state.LaunchRuntimeService.bootstrap_probe",
                "winws_runtime.state.LaunchRuntimeService.observe_process_details",
                "winws_runtime.state.LaunchRuntimeService.set_busy",
            ),
            canonical_readers=(
                "app.feature_facades.runtime_parts.RuntimeEvents.handle_runner_failure",
                "winws_runtime.runtime.lifecycle_feedback.verify_dpi_process_running",
                "presets.ui.control.zapret1.page.Zapret1ModeControlPage._get_current_dpi_runtime_state",
                "presets.ui.control.zapret2.page.Zapret2ModeControlPage._on_ui_state_changed",
                "tray.SystemTrayManager._is_launch_running/_launch_phase via RuntimeFeature.snapshot",
            ),
            allowed_auxiliary_writers=(
                "нет: внешние места должны вызывать методы LaunchRuntimeService",
            ),
            single_source_of_truth="app.state_store.MainWindowStateStore",
        )

    def __init__(self, store: MainWindowStateStore) -> None:
        self._store_ref = store
        self._tracking_state = _LaunchRuntimeTrackingState()

    def _store(self) -> MainWindowStateStore | None:
        store = self._store_ref
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

    def set_busy(self, busy: bool, text: str = "") -> bool:
        store = self._store()
        if store is None:
            return False
        return bool(store.set_launch_busy(bool(busy), str(text or "")))

    def begin_start(
        self,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        self._set_tracking_state(expected_process=expected_process, pid=None, missing_probe_count=0)
        changes = self._runtime_changes(
            phase="starting",
            running=False,
            last_error="",
        )
        if launch_method is not None:
            changes["launch_method"] = normalize_launch_method(launch_method, default="")
        return self._apply(**changes)

    def mark_autostart_pending(
        self,
        *,
        launch_method: str | None = None,
        expected_process: str = "",
    ) -> bool:
        self._set_tracking_state(expected_process=expected_process, pid=None, missing_probe_count=0)
        changes = self._runtime_changes(
            phase="autostart_pending",
            running=False,
            last_error="",
        )
        if launch_method is not None:
            changes["launch_method"] = normalize_launch_method(launch_method, default="")
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
        self._set_tracking_state(
            expected_process=next_expected_process,
            pid=next_pid,
            missing_probe_count=0,
        )
        return self._apply(
            **self._runtime_changes(
                phase="running",
                running=True,
                last_error="",
            )
        )

    def mark_start_failed(self, error: str) -> bool:
        self._set_tracking_state(pid=None, missing_probe_count=0)
        return self._apply(
            **self._runtime_changes(
                phase="failed",
                running=False,
                last_error=error,
            )
        )

    def mark_stopped(self, *, clear_error: bool = True) -> bool:
        snap = self.snapshot()
        self._set_tracking_state(expected_process="", pid=None, missing_probe_count=0)
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
            missing_probe_count=0,
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
            changes["launch_method"] = normalize_launch_method(launch_method, default="")
        return self._apply(**changes)

    def observe_process_details(self, details: Mapping[str, Any] | None) -> bool:
        normalized = self._normalize_process_details(details)
        snap = self.snapshot()
        tracked = self._tracking_state

        expected = str(tracked.expected_process or "").strip().lower()
        matched_name = expected
        matched_pids = normalized.get(expected, [])

        if not matched_pids and not expected:
            for candidate in ALL_WINWS_EXE_NAMES:
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
                self._set_tracking_state(missing_probe_count=0)
                return False
            tracked_pid = tracked.pid
            if tracked_pid is not None and is_winws_process_pid_alive(tracked_pid, expected or matched_name):
                self._set_tracking_state(missing_probe_count=0)
                return False
            miss_count = self._increment_missing_probe_count()
            if miss_count < 3:
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
        missing_probe_count: int | None = None,
    ) -> None:
        if expected_process is not None:
            self._tracking_state.expected_process = str(expected_process or "").strip().lower()
        if pid is not _UNSET:
            self._tracking_state.pid = int(pid) if isinstance(pid, int) else None
        if missing_probe_count is not None:
            self._tracking_state.missing_probe_count = max(0, int(missing_probe_count))

    def _increment_missing_probe_count(self) -> int:
        next_value = int(getattr(self._tracking_state, "missing_probe_count", 0) or 0) + 1
        self._set_tracking_state(missing_probe_count=next_value)
        return next_value

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
