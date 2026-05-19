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
    folder_state: dict[str, object] | None = None,
    folder_scope: str = "winws2",
    empty_not_found_key: str,
    empty_none_key: str,
) -> UserPresetListPlan:
    from presets.icon_color import normalize_preset_icon_color
    from presets.folders import build_preset_folder_rows, load_preset_folder_state
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

    effective_folder_state = folder_state if folder_state is not None else load_preset_folder_state(folder_scope)

    if visible_entries:
        rows.extend(
            build_preset_folder_rows(
                all_presets={
                    file_name: {
                        **meta,
                        "icon_color": normalize_preset_icon_color(str(meta.get("icon_color") or "")),
                    }
                    for file_name, meta in all_presets.items()
                },
                visible_entries=visible_entries,
                active_file_name=active_file_name,
                folder_state=effective_folder_state,
                query=normalized_query,
            )
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
