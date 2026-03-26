from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class ValidationStepResult:
    name: str
    success: bool
    returncode: int
    stdout: str
    stderr: str
    config_path: Path


@dataclass(frozen=True)
class ValidationReport:
    success: bool
    steps: list[ValidationStepResult]


class PresetValidator:
    def __init__(self, paths):
        self._paths = paths

    def validate(self, adapter, compiled) -> ValidationReport:
        if not compiled.ok:
            return ValidationReport(success=False, steps=[])

        engine_paths = self._paths.engine_paths(adapter.engine_id).ensure_directories()
        source_lines = [line for line in compiled.source_text.splitlines() if line.strip()]
        steps: list[ValidationStepResult] = []

        for plan in adapter.build_validation_plans(compiled, engine_paths):
            plan.config_path.parent.mkdir(parents=True, exist_ok=True)
            config_lines = [str(arg).strip() for arg in plan.args if str(arg).strip()]
            config_lines.extend(compiled.preamble_lines)
            config_lines.extend(source_lines)
            plan.config_path.write_text("\n".join(config_lines).rstrip("\n") + "\n", encoding="utf-8")

            result = subprocess.run(
                [str(adapter.get_executable_path()), f"@{plan.config_path}"],
                cwd=str(adapter.get_bundle_root()),
                capture_output=True,
                text=True,
                timeout=30,
            )

            steps.append(
                ValidationStepResult(
                    name=plan.name,
                    success=result.returncode == 0,
                    returncode=int(result.returncode),
                    stdout=str(result.stdout or ""),
                    stderr=str(result.stderr or ""),
                    config_path=plan.config_path,
                )
            )

            if result.returncode != 0:
                return ValidationReport(success=False, steps=steps)

        return ValidationReport(success=True, steps=steps)
