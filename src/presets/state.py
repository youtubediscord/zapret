from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PresetSelectionState:
    """Текущее состояние выбранного source preset-а.

    Source preset остаётся единственным источником истины для direct-запуска.
    Не возвращать runtime launch.txt, временные копии или fallback-пути как
    каноническое состояние выбранного preset-а.

    Исключение ниже по цепочке запуска: winws2 runner может создать временный
    @config-файл как адаптер для самого winws2.exe. Такой файл не является
    выбранным preset-ом и не должен попадать в UI, settings или manifest.
    """

    method: str
    engine: str
    selected_preset_file_name: str
    selected_preset_name: str
    selected_source_path: str
    display_name: str
    summary: str
    selected_profile_key: str = ""
    selected_profile_name: str = ""
    profile_count: int = 0
    enabled_profile_count: int = 0
    active_strategy_count: int = 0
