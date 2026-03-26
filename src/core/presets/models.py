from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PresetManifest:
    id: str
    name: str
    file_name: str
    created_at: str
    updated_at: str
    kind: str = "user"


@dataclass(frozen=True)
class PresetDocument:
    manifest: PresetManifest
    source_text: str
