from __future__ import annotations

from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.additional_settings_load_runtime = OneShotWorkerRuntime()
        self.additional_settings_load_state = LatestValueWorkerState(
            self.additional_settings_load_runtime,
            empty_value=False,
        )
        self.additional_settings_preset_switch_reload_state = LatestValueWorkerState(
            None,
            empty_value=False,
        )
        self.additional_settings_reload_after_preset_apply_pending = False
        self.additional_settings_save_runtime = OneShotWorkerRuntime()
        self.additional_settings_save_state = QueuedWorkerState[tuple[str, bool, str]](
            self.additional_settings_save_runtime,
        )
        self.additional_settings_request_id = 0
        self.additional_settings_save_request_id = 0
        self.additional_settings_dirty = True
        self.top_summary_runtime = OneShotWorkerRuntime()
        self.top_summary_state = LatestValueWorkerState(self.top_summary_runtime, empty_value=False)
        self.top_summary_preset_switch_reload_state = LatestValueWorkerState(
            None,
            empty_value=False,
        )
        self.top_summary_reload_after_preset_apply_pending = False
        self.top_summary_request_id = 0
        self.program_settings_load_runtime = OneShotWorkerRuntime()
        self.program_settings_load_state = LatestValueWorkerState(
            self.program_settings_load_runtime,
            empty_value=False,
        )
        self.program_settings_save_runtime = OneShotWorkerRuntime()
        self.program_settings_save_state = QueuedWorkerState[tuple[str, bool]](
            self.program_settings_save_runtime,
        )

    def queue_additional_settings_save(
        self,
        setting: str,
        enabled: bool,
        launch_method: str,
        *,
        front: bool = False,
    ) -> None:
        item = (str(setting or ""), bool(enabled), str(launch_method or ""))
        pending = self.additional_settings_save_state.pending
        pending[:] = [
            queued
            for queued in pending
            if not (queued[0] == item[0] and queued[2] == item[2])
        ]
        if front:
            pending.insert(0, item)
        else:
            pending.append(item)

    def queue_program_settings_save(self, action: str, enabled: bool, *, front: bool = False) -> None:
        item = (str(action or ""), bool(enabled))
        pending = self.program_settings_save_state.pending
        pending[:] = [
            queued for queued in pending if queued[0] != item[0]
        ]
        if front:
            pending.insert(0, item)
        else:
            pending.append(item)

    def has_pending_refresh(self) -> bool:
        return bool(self.additional_settings_dirty)

    def mark_presets_dirty(self) -> None:
        self.additional_settings_dirty = True

    def mark_additional_settings_applied(self) -> None:
        self.additional_settings_dirty = False

    def mark_additional_settings_written(self) -> None:
        self.additional_settings_request_id += 1
        self.additional_settings_dirty = False
        self.additional_settings_load_runtime.cancel()

    def next_additional_settings_request_id(self) -> int:
        self.additional_settings_request_id += 1
        return self.additional_settings_request_id

    def next_additional_settings_save_request_id(self) -> int:
        self.additional_settings_save_request_id += 1
        return self.additional_settings_save_request_id

    def next_top_summary_request_id(self) -> int:
        self.top_summary_request_id += 1
        return self.top_summary_request_id

    @property
    def additional_settings_load_pending(self) -> bool:
        return bool(self.additional_settings_load_state.pending)

    @additional_settings_load_pending.setter
    def additional_settings_load_pending(self, value: bool) -> None:
        self.additional_settings_load_state.pending = bool(value)

    @property
    def additional_settings_load_start_scheduled(self) -> bool:
        return bool(self.additional_settings_load_state.start_scheduled)

    @additional_settings_load_start_scheduled.setter
    def additional_settings_load_start_scheduled(self, value: bool) -> None:
        self.additional_settings_load_state.start_scheduled = bool(value)

    @property
    def additional_settings_reload_after_preset_switch_scheduled(self) -> bool:
        return bool(self.additional_settings_preset_switch_reload_state.start_scheduled)

    @additional_settings_reload_after_preset_switch_scheduled.setter
    def additional_settings_reload_after_preset_switch_scheduled(self, value: bool) -> None:
        self.additional_settings_preset_switch_reload_state.start_scheduled = bool(value)

    @property
    def additional_settings_save_pending(self) -> list[tuple[str, bool, str]]:
        return self.additional_settings_save_state.pending

    @additional_settings_save_pending.setter
    def additional_settings_save_pending(self, value: list[tuple[str, bool, str]]) -> None:
        self.additional_settings_save_state.pending[:] = [
            (str(item[0] or ""), bool(item[1]), str(item[2] or ""))
            for item in (value or [])
        ]

    @property
    def additional_settings_save_start_scheduled(self) -> bool:
        return bool(self.additional_settings_save_state.start_scheduled)

    @additional_settings_save_start_scheduled.setter
    def additional_settings_save_start_scheduled(self, value: bool) -> None:
        self.additional_settings_save_state.start_scheduled = bool(value)

    @property
    def top_summary_pending(self) -> bool:
        return bool(self.top_summary_state.pending)

    @top_summary_pending.setter
    def top_summary_pending(self, value: bool) -> None:
        self.top_summary_state.pending = bool(value)

    @property
    def top_summary_start_scheduled(self) -> bool:
        return bool(self.top_summary_state.start_scheduled)

    @top_summary_start_scheduled.setter
    def top_summary_start_scheduled(self, value: bool) -> None:
        self.top_summary_state.start_scheduled = bool(value)

    @property
    def top_summary_reload_after_preset_switch_scheduled(self) -> bool:
        return bool(self.top_summary_preset_switch_reload_state.start_scheduled)

    @top_summary_reload_after_preset_switch_scheduled.setter
    def top_summary_reload_after_preset_switch_scheduled(self, value: bool) -> None:
        self.top_summary_preset_switch_reload_state.start_scheduled = bool(value)

    @property
    def program_settings_load_pending(self) -> bool:
        return bool(self.program_settings_load_state.pending)

    @program_settings_load_pending.setter
    def program_settings_load_pending(self, value: bool) -> None:
        self.program_settings_load_state.pending = bool(value)

    @property
    def program_settings_load_start_scheduled(self) -> bool:
        return bool(self.program_settings_load_state.start_scheduled)

    @program_settings_load_start_scheduled.setter
    def program_settings_load_start_scheduled(self, value: bool) -> None:
        self.program_settings_load_state.start_scheduled = bool(value)

    @property
    def program_settings_save_pending(self) -> list[tuple[str, bool]]:
        return self.program_settings_save_state.pending

    @program_settings_save_pending.setter
    def program_settings_save_pending(self, value: list[tuple[str, bool]]) -> None:
        self.program_settings_save_state.pending[:] = [
            (str(item[0] or ""), bool(item[1]))
            for item in (value or [])
        ]

    @property
    def program_settings_save_start_scheduled(self) -> bool:
        return bool(self.program_settings_save_state.start_scheduled)

    @program_settings_save_start_scheduled.setter
    def program_settings_save_start_scheduled(self, value: bool) -> None:
        self.program_settings_save_state.start_scheduled = bool(value)

    def accept_additional_settings_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.additional_settings_request_id):
            return False
        self.mark_additional_settings_applied()
        return True

    def accept_worker_finish(self, worker, request_attr: str) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            runtime_attr = {
                "additional_settings_request_id": "additional_settings_load_runtime",
                "additional_settings_save_request_id": "additional_settings_save_runtime",
                "top_summary_request_id": "top_summary_runtime",
            }.get(str(request_attr or ""))
            current_runtime = getattr(self, str(runtime_attr or ""), None)
            current_worker = getattr(current_runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(self, request_attr, -1))
        except (TypeError, ValueError):
            return False

    def stop_workers(self, *, log_fn=None) -> None:
        self.additional_settings_load_start_scheduled = False
        self.additional_settings_preset_switch_reload_state.reset()
        self.additional_settings_reload_after_preset_apply_pending = False
        self.additional_settings_save_start_scheduled = False
        self.top_summary_start_scheduled = False
        self.top_summary_preset_switch_reload_state.reset()
        self.top_summary_reload_after_preset_apply_pending = False
        self.program_settings_load_start_scheduled = False
        self.program_settings_save_start_scheduled = False
        for runtime, label in (
            (self.additional_settings_load_runtime, "control additional settings load worker"),
            (self.additional_settings_save_runtime, "control additional settings save worker"),
            (self.top_summary_runtime, "control top summary worker"),
            (self.program_settings_load_runtime, "control program settings load worker"),
            (self.program_settings_save_runtime, "control program settings save worker"),
        ):
            runtime.stop(
                blocking=False,
                log_fn=log_fn,
                warning_prefix=label,
            )
            runtime.cancel()


def create_refresh_runtime() -> ModeControlRefreshRuntime:
    return ModeControlRefreshRuntime()
