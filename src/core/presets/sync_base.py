from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PresetSyncLayer(Protocol):
    def sync_preset(self, preset, changed_category: str | None = None) -> bool: ...
