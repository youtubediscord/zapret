from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import PresetDocument

_RESERVED_PREFIXES = (
    "--debug=@",
    "--pidfile=",
    "--writeable=",
    "--chdir=",
)


@dataclass(frozen=True)
class CompileIssue:
    code: str
    message: str


@dataclass(frozen=True)
class CompiledPreset:
    ok: bool
    preset_id: str
    preset_name: str
    source_text: str
    preamble_lines: list[str] = field(default_factory=list)
    effective_config_path: Path | None = None
    issues: list[CompileIssue] = field(default_factory=list)


class PresetCompiler:
    def __init__(self, paths):
        self._paths = paths

    def compile(self, adapter, preset: PresetDocument) -> CompiledPreset:
        source_text = (preset.source_text or "").replace("\r\n", "\n").replace("\r", "\n")
        issues = self._collect_issues(source_text)
        if issues:
            return CompiledPreset(
                ok=False,
                preset_id=preset.manifest.id,
                preset_name=preset.manifest.name,
                source_text=source_text,
                issues=issues,
            )

        engine_paths = self._paths.engine_paths(adapter.engine_id).ensure_directories()
        preamble_lines = [str(line).strip() for line in adapter.build_managed_preamble(engine_paths) if str(line).strip()]
        effective_lines = [*preamble_lines]
        effective_lines.extend(line for line in source_text.splitlines() if line.strip())
        text = "\n".join(effective_lines).rstrip("\n") + "\n"
        engine_paths.effective_config_path.write_text(text, encoding="utf-8")

        return CompiledPreset(
            ok=True,
            preset_id=preset.manifest.id,
            preset_name=preset.manifest.name,
            source_text=source_text,
            preamble_lines=preamble_lines,
            effective_config_path=engine_paths.effective_config_path,
            issues=[],
        )

    @staticmethod
    def _collect_issues(source_text: str) -> list[CompileIssue]:
        issues: list[CompileIssue] = []
        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            for prefix in _RESERVED_PREFIXES:
                if lowered.startswith(prefix):
                    issues.append(
                        CompileIssue(
                            code="reserved-option",
                            message=f"Preset contains reserved managed option: {line}",
                        )
                    )
                    return issues
        return issues
