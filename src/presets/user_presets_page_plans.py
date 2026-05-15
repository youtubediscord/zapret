from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UserPresetListPlan:
    rows: list[dict[str, object]]
    total_presets: int
    visible_presets: int
    query: str


def build_preset_rows_plan(
    *,
    all_presets: dict[str, dict[str, object]],
    query: str,
    active_file_name: str,
    language: str,
    hierarchy,
    empty_not_found_key: str,
    empty_none_key: str,
) -> UserPresetListPlan:
    from presets.icon_color import normalize_preset_icon_color
    from app.text_catalog import tr as tr_catalog

    normalized_query = str(query or "").strip().lower()
    builtin_by_file = {
        file_name: bool(meta.get("is_builtin", False))
        for file_name, meta in all_presets.items()
    }

    rows: list[dict[str, object]] = []
    visible_entries: list[dict[str, object]] = []

    for file_name, meta in all_presets.items():
        display_name = str(meta.get("display_name") or file_name).strip()
        if normalized_query and normalized_query not in display_name.lower():
            continue
        visible_entries.append(
            {
                "file_name": file_name,
                "display_name": display_name,
                "is_builtin": builtin_by_file.get(file_name, False),
            }
        )

    ordered_names = hierarchy.list_presets_flat(
        visible_entries,
        is_builtin_resolver=lambda file_name: builtin_by_file.get(str(file_name or ""), False),
    )

    for file_name in ordered_names:
        preset = all_presets.get(file_name)
        if not preset:
            continue
        display_name = str(preset.get("display_name") or file_name).strip()
        is_builtin = builtin_by_file.get(file_name, False)
        meta = hierarchy.get_preset_meta(file_name)
        rows.append(
            {
                "kind": "preset",
                "name": display_name,
                "file_name": file_name,
                "description": str(preset.get("description") or ""),
                "date": str(preset.get("modified_display") or ""),
                "is_active": bool(file_name and file_name == str(active_file_name or "").strip()),
                "is_builtin": is_builtin,
                "icon_color": normalize_preset_icon_color(str(preset.get("icon_color") or "")),
                "depth": 0,
                "is_pinned": bool(meta.get("pinned", False)),
                "rating": int(meta.get("rating", 0) or 0),
            }
        )

    if not rows:
        if normalized_query:
            rows.append(
                {
                    "kind": "empty",
                    "text": tr_catalog(
                        empty_not_found_key,
                        language=language,
                        default="По этому поиску пресетов нет. Измените запрос или очистите строку поиска.",
                    ),
                }
            )
        else:
            rows.append(
                {
                    "kind": "empty",
                    "text": tr_catalog(
                        empty_none_key,
                        language=language,
                        default="Пресеты не найдены. Создайте новый пресет или импортируйте txt-файл.",
                    ),
                }
            )

    return UserPresetListPlan(
        rows=rows,
        total_presets=len(all_presets),
        visible_presets=len(visible_entries),
        query=normalized_query,
    )
