import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.feature_facades.runtime_parts import RuntimeObjects
from app.state_store import AppUiState, MainWindowStateStore
from winws_runtime.runners.preset_runner_support import PresetRunnerState
from winws_runtime.runtime.lifecycle_feedback import _runner_start_pid
from winws_runtime.runtime.status_flow import is_runner_transition_state, is_running
from winws_runtime.state import LaunchRuntimeService


class _RuntimeService:
    def __init__(
        self,
        *,
        launch_method: str = "zapret2_mode",
        phase: str = "stopped",
        running: bool = False,
        pid: int | None = None,
    ):
        self._snapshot = SimpleNamespace(
            launch_method=launch_method,
            phase=phase,
            running=running,
            pid=pid,
        )
        self.observed_details: list[dict] = []

    def snapshot(self):
        return self._snapshot

    def observe_process_details(self, details):
        normalized = dict(details or {})
        self.observed_details.append(normalized)
        winws2_pids = normalized.get("winws2.exe") or []
        if winws2_pids and isinstance(winws2_pids[0], int):
            self._snapshot = SimpleNamespace(
                launch_method="zapret2_mode",
                phase="running",
                running=True,
                pid=winws2_pids[0],
            )


class _ProcessMonitorManager:
    def __init__(self, details, observer=None, *, raise_on_refresh: bool = False):
        self.details = details
        self.observer = observer
        self.raise_on_refresh = raise_on_refresh
        self.refresh_count = 0

    def refresh_now(self):
        self.refresh_count += 1
        if self.raise_on_refresh:
            raise RuntimeError("refresh failed")
        if callable(self.observer):
            self.observer(self.details)
        return {"winws2.exe": [9999]}


class RuntimeProcessPidTests(unittest.TestCase):
    def test_current_process_pid_refreshes_runtime_and_reads_snapshot(self) -> None:
        runtime_service = _RuntimeService()
        objects = RuntimeObjects(runtime_service=runtime_service)
        manager = _ProcessMonitorManager(
            {"winws2.exe": [2222]},
            observer=objects.observe_process_details,
        )
        objects.process_monitor_manager = manager

        pid = objects.current_process_pid("zapret2_mode", refresh=True)

        self.assertEqual(pid, 2222)
        self.assertEqual(manager.refresh_count, 1)
        self.assertEqual(runtime_service.observed_details, [{"winws2.exe": [2222]}])

    def test_current_process_pid_refreshes_real_runtime_for_winws1(self) -> None:
        store = MainWindowStateStore(AppUiState())
        runtime_service = LaunchRuntimeService(store)
        runtime_service.begin_start(launch_method="zapret1_mode", expected_process="winws.exe")
        objects = RuntimeObjects(runtime_service=runtime_service)
        manager = _ProcessMonitorManager(
            {"winws.exe": [1111], "winws2.exe": [2222]},
            observer=objects.observe_process_details,
        )
        objects.process_monitor_manager = manager

        pid = objects.current_process_pid("zapret1_mode", refresh=True)

        self.assertEqual(pid, 1111)
        self.assertEqual(manager.refresh_count, 1)

    def test_current_process_pid_refreshes_real_runtime_for_winws2(self) -> None:
        store = MainWindowStateStore(AppUiState())
        runtime_service = LaunchRuntimeService(store)
        runtime_service.begin_start(launch_method="zapret2_mode", expected_process="winws2.exe")
        objects = RuntimeObjects(runtime_service=runtime_service)
        manager = _ProcessMonitorManager(
            {"winws.exe": [1111], "winws2.exe": [2222]},
            observer=objects.observe_process_details,
        )
        objects.process_monitor_manager = manager

        pid = objects.current_process_pid("zapret2_mode", refresh=True)

        self.assertEqual(pid, 2222)
        self.assertEqual(manager.refresh_count, 1)

    def test_current_process_pid_without_refresh_reads_existing_snapshot(self) -> None:
        runtime_service = _RuntimeService(
            launch_method="zapret2_mode",
            phase="running",
            running=True,
            pid=3333,
        )
        objects = RuntimeObjects(runtime_service=runtime_service)

        pid = objects.current_process_pid("zapret2_mode", refresh=False)

        self.assertEqual(pid, 3333)

    def test_current_process_pid_rejects_snapshot_for_other_launch_method(self) -> None:
        runtime_service = _RuntimeService(
            launch_method="zapret1_mode",
            phase="running",
            running=True,
            pid=1111,
        )
        objects = RuntimeObjects(runtime_service=runtime_service)

        pid = objects.current_process_pid("zapret2_mode", refresh=False)

        self.assertIsNone(pid)

    def test_current_process_pid_does_not_use_stale_snapshot_when_refresh_fails(self) -> None:
        runtime_service = _RuntimeService(
            launch_method="zapret2_mode",
            phase="running",
            running=True,
            pid=3333,
        )
        manager = _ProcessMonitorManager({}, raise_on_refresh=True)
        objects = RuntimeObjects(runtime_service=runtime_service, process_monitor_manager=manager)

        pid = objects.current_process_pid("zapret2_mode", refresh=True)

        self.assertIsNone(pid)
        self.assertEqual(manager.refresh_count, 1)

    def test_runner_start_pid_reads_runner_state_snapshot(self) -> None:
        runner = SimpleNamespace(
            get_runner_state_snapshot=lambda: SimpleNamespace(
                state=PresetRunnerState.RUNNING,
                pid=4444,
            ),
            running_process=SimpleNamespace(pid=5555),
        )

        with patch("winws_runtime.runners.runner_factory.get_current_runner", return_value=runner):
            self.assertEqual(_runner_start_pid(SimpleNamespace()), 4444)

    def test_runner_start_pid_does_not_fallback_to_running_process(self) -> None:
        runner = SimpleNamespace(
            get_runner_state_snapshot=lambda: SimpleNamespace(
                state=PresetRunnerState.IDLE,
                pid=None,
            ),
            running_process=SimpleNamespace(pid=5555),
        )

        with patch("winws_runtime.runners.runner_factory.get_current_runner", return_value=runner):
            self.assertIsNone(_runner_start_pid(SimpleNamespace()))

    def test_runner_transition_state_accepts_enum_value(self) -> None:
        self.assertTrue(is_runner_transition_state(PresetRunnerState.STARTING))

    def test_is_running_accepts_runner_state_enum_value(self) -> None:
        runner = SimpleNamespace(
            get_runner_state_snapshot=lambda: SimpleNamespace(state=PresetRunnerState.RUNNING),
        )
        runtime_owner = SimpleNamespace(
            _runtime_service=lambda: SimpleNamespace(
                snapshot=lambda: SimpleNamespace(phase="stopped", running=False)
            ),
            _runtime_api=lambda: SimpleNamespace(is_any_running=lambda silent=True: False),
        )

        with patch("winws_runtime.runners.runner_factory.get_current_runner", return_value=runner):
            self.assertTrue(is_running(runtime_owner))


if __name__ == "__main__":
    unittest.main()
