from __future__ import annotations

import os

from core.paths import AppPaths
from core.presets.repository import PresetRepository
from core.presets.selection_service import PresetSelectionService

from .models import EngineStatus, SessionInfo
from .process_control import read_pid_file
from .session_registry import SessionRegistry


def is_pid_running(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


class StatusService:
    def __init__(
        self,
        paths: AppPaths,
        repository: PresetRepository,
        selection: PresetSelectionService,
        registry: SessionRegistry,
    ):
        self._paths = paths
        self._repository = repository
        self._selection = selection
        self._registry = registry

    def get_status(self, engine: str) -> EngineStatus:
        selected = self._selection.get_selected_preset(engine)
        session = self._registry.read_session(engine)

        selected_id = selected.manifest.id if selected is not None else None
        selected_name = selected.manifest.name if selected is not None else None

        if session is None:
            return EngineStatus(
                state="stopped",
                pid=None,
                selected_preset_id=selected_id,
                selected_preset_name=selected_name,
                running_preset_id=None,
                running_preset_name=None,
                effective_config_path=None,
                log_path=None,
            )

        return self._status_with_session(engine, session, selected_id, selected_name)

    def _status_with_session(
        self,
        engine: str,
        session: SessionInfo,
        selected_id: str | None,
        selected_name: str | None,
    ) -> EngineStatus:
        engine_paths = self._paths.engine_paths(engine).ensure_directories()
        pid_from_file = read_pid_file(engine_paths.worker_pid_path)
        current = session
        state = "unknown"
        pid = session.pid

        if pid_from_file is not None and pid_from_file != session.pid:
            current = SessionInfo(
                engine=session.engine,
                preset_id=session.preset_id,
                preset_name=session.preset_name,
                pid=pid_from_file,
                started_at=session.started_at,
                effective_config_path=session.effective_config_path,
                log_path=session.log_path,
            )
            self._registry.write_session(engine, current)
            pid = pid_from_file
        elif is_pid_running(session.pid):
            state = "running"

        return EngineStatus(
            state=state,
            pid=pid,
            selected_preset_id=selected_id,
            selected_preset_name=selected_name,
            running_preset_id=current.preset_id,
            running_preset_name=current.preset_name,
            effective_config_path=current.effective_config_path,
            log_path=current.log_path,
        )
