from __future__ import annotations

from dataclasses import dataclass

from .strategy_catalog import StrategyEntry
from .strategy_state import ProfileStrategyState


@dataclass(frozen=True)
class ProfileListItem:
    key: str
    persistent_key: str
    profile_index: int
    template_id: str
    display_name: str
    enabled: bool
    in_preset: bool
    strategy_id: str
    strategy_name: str
    match_lines: tuple[str, ...]
    list_type: str
    rating: str
    favorite: bool
    group: str
    order: int


@dataclass(frozen=True)
class ProfileListPayload:
    items: tuple[ProfileListItem, ...]
    strategy_names_by_profile: dict[str, dict[str, str]]
    selected_preset_file_name: str
    selected_preset_name: str


@dataclass(frozen=True)
class ProfileSetupPayload:
    item: ProfileListItem
    strategy_entries: dict[str, StrategyEntry]
    raw_profile_text: str
    raw_strategy_text: str
    match_summary: str
    editable_filter_kind: str = ""
    editable_filter_value: str = ""
    editable_filter_enabled: bool = True
    in_range: str = "x"
    out_range: str = "a"
    current_strategy_state: ProfileStrategyState = ProfileStrategyState()
