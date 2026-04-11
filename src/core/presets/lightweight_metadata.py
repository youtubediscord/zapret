from __future__ import annotations

from pathlib import Path

from core.presets.list_metadata import read_preset_list_metadata


def build_lightweight_preset_metadata(
    path: Path,
    *,
    display_name: str,
    kind: str,
    is_builtin: bool,
) -> dict[str, object]:
    normalized_display_name = str(display_name or path.name).strip()
    normalized_kind = str(kind or "").strip() or "user"
    normalized_is_builtin = bool(is_builtin)

    try:
        return {
            **read_preset_list_metadata(path),
            "display_name": normalized_display_name,
            "kind": normalized_kind,
            "is_builtin": normalized_is_builtin,
        }
    except Exception:
        return {
            "description": "",
            "modified_display": "",
            "icon_color": "",
            "display_name": normalized_display_name,
            "kind": normalized_kind,
            "is_builtin": normalized_is_builtin,
        }
