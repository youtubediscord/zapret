from __future__ import annotations


class ModeControlRefreshRuntime:
    def __init__(self) -> None:
        self.additional_settings_worker = None
        self.additional_settings_save_worker = None
        self.additional_settings_save_pending = None
        self.additional_settings_request_id = 0
        self.additional_settings_save_request_id = 0
        self.additional_settings_dirty = True
        self.top_summary_worker = None
        self.top_summary_pending = False
        self.top_summary_request_id = 0
        self.program_settings_load_worker = None
        self.program_settings_load_pending = False
        self.program_settings_load_request_id = 0
        self.program_settings_save_worker = None
        self.program_settings_save_pending = None
        self.program_settings_save_request_id = 0

    def has_pending_refresh(self) -> bool:
        return bool(self.additional_settings_dirty)

    def mark_presets_dirty(self) -> None:
        self.additional_settings_dirty = True

    def mark_additional_settings_applied(self) -> None:
        self.additional_settings_dirty = False
        self.additional_settings_worker = None

    def mark_additional_settings_written(self) -> None:
        self.additional_settings_request_id += 1
        self.additional_settings_dirty = False
        self.additional_settings_worker = None

    def next_additional_settings_request_id(self) -> int:
        self.additional_settings_request_id += 1
        return self.additional_settings_request_id

    def next_additional_settings_save_request_id(self) -> int:
        self.additional_settings_save_request_id += 1
        return self.additional_settings_save_request_id

    def next_program_settings_save_request_id(self) -> int:
        self.program_settings_save_request_id += 1
        return self.program_settings_save_request_id

    def next_program_settings_load_request_id(self) -> int:
        self.program_settings_load_request_id += 1
        return self.program_settings_load_request_id

    def next_top_summary_request_id(self) -> int:
        self.top_summary_request_id += 1
        return self.top_summary_request_id

    def accept_additional_settings_result(self, request_id: int) -> bool:
        if int(request_id) != int(self.additional_settings_request_id):
            return False
        self.mark_additional_settings_applied()
        return True


def create_refresh_runtime() -> ModeControlRefreshRuntime:
    return ModeControlRefreshRuntime()
