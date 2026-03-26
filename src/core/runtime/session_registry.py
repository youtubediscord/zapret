from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from core.paths import AppPaths
from core.presets.validator import ValidationReport, ValidationStepResult

from .models import SessionInfo


class SessionRegistry:
    def __init__(self, paths: AppPaths):
        self._paths = paths

    def write_session(self, engine: str, session: SessionInfo) -> None:
        path = self._paths.engine_paths(engine).ensure_directories().session_path
        path.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read_session(self, engine: str) -> SessionInfo | None:
        path = self._paths.engine_paths(engine).ensure_directories().session_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SessionInfo(**data)
        except Exception:
            return None

    def clear_session(self, engine: str) -> None:
        try:
            self._paths.engine_paths(engine).ensure_directories().session_path.unlink()
        except FileNotFoundError:
            pass

    def write_last_validation(self, engine: str, report: ValidationReport) -> None:
        path = self._paths.engine_paths(engine).ensure_directories().last_validation_path
        payload = {
            "success": bool(report.success),
            "steps": [
                {
                    "name": step.name,
                    "success": bool(step.success),
                    "returncode": int(step.returncode),
                    "stdout": step.stdout,
                    "stderr": step.stderr,
                    "config_path": str(step.config_path),
                }
                for step in report.steps
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read_last_validation(self, engine: str) -> ValidationReport | None:
        path = self._paths.engine_paths(engine).ensure_directories().last_validation_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            steps = [
                ValidationStepResult(
                    name=str(item.get("name") or ""),
                    success=bool(item.get("success")),
                    returncode=int(item.get("returncode") or 0),
                    stdout=str(item.get("stdout") or ""),
                    stderr=str(item.get("stderr") or ""),
                    config_path=Path(str(item.get("config_path") or "")),
                )
                for item in data.get("steps", [])
            ]
            return ValidationReport(success=bool(data.get("success")), steps=steps)
        except Exception:
            return None
