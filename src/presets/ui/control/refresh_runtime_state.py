from __future__ import annotations

from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.additional_settings_load_runtime = OneShotWorkerRuntime()
        self.additional_settings_load_pending = False
        self.additional_settings_load_start_scheduled = False
        self.additional_settings_reload_after_preset_switch_scheduled = False
        self.additional_settings_save_runtime = OneShotWorkerRuntime()
        self.additional_settings_save_pending: list[tuple[str, bool, str]] = []
        self.additional_settings_save_start_scheduled = False
        self.additional_settings_request_id = 0
        self.additional_settings_save_request_id = 0
        self.additional_settings_dirty = True
        self.top_summary_runtime = OneShotWorkerRuntime()
        self.top_summary_pending = False
        self.top_summary_start_scheduled = False
        self.top_summary_reload_after_preset_switch_scheduled = False
        self.top_summary_request_id = 0
        self.program_settings_load_runtime = OneShotWorkerRuntime()
        self.program_settings_load_pending = False
        self.program_settings_load_start_scheduled = False
        self.program_settings_save_runtime = OneShotWorkerRuntime()
        self.program_settings_save_pending: list[tuple[str, bool]] = []
        self.program_settings_save_start_scheduled = False

    def queue_additional_settings_save(
        self,
        setting: str,
        enabled: bool,
        launch_method: str,
        *,
        front: bool = False,
    ) -> None:
        item = (str(setting or ""), bool(enabled), str(launch_method or ""))
        self.additional_settings_save_pending = [
            pending
            for pending in self.additional_settings_save_pending
            if not (pending[0] == item[0] and pending[2] == item[2])
        ]
        if front:
            self.additional_settings_save_pending.insert(0, item)
        else:
            self.additional_settings_save_pending.append(item)

    def queue_program_settings_save(self, action: str, enabled: bool, *, front: bool = False) -> None:
        item = (str(action or ""), bool(enabled))
        self.program_settings_save_pending = [
            pending for pending in self.program_settings_save_pending if pending[0] != item[0]
        ]
        if front:
            self.program_settings_save_pending.insert(0, item)
        else:
            self.program_settings_save_pending.append(item)

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
        self.additional_settings_reload_after_preset_switch_scheduled = False
        self.additional_settings_save_start_scheduled = False
        self.top_summary_start_scheduled = False
        self.top_summary_reload_after_preset_switch_scheduled = False
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
