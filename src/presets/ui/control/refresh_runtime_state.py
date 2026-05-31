from __future__ import annotations

from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.additional_settings_load_runtime = OneShotWorkerRuntime()
        self.additional_settings_load_pending = False
        self.additional_settings_save_runtime = OneShotWorkerRuntime()
        self.additional_settings_save_pending: list[tuple[str, bool, str]] = []
        self.additional_settings_save_start_scheduled = False
        self.additional_settings_request_id = 0
        self.additional_settings_save_request_id = 0
        self.additional_settings_dirty = True
        self.top_summary_runtime = OneShotWorkerRuntime()
        self.top_summary_pending = False
        self.top_summary_request_id = 0
        self.program_settings_load_runtime = OneShotWorkerRuntime()
        self.program_settings_load_pending = False
        self.program_settings_save_runtime = OneShotWorkerRuntime()
        self.program_settings_save_pending: list[tuple[str, bool]] = []

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

    def stop_workers(self, *, log_fn=None) -> None:
        self.additional_settings_save_start_scheduled = False
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
