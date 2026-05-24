from __future__ import annotations

from dataclasses import dataclass

from .strategy_catalog import StrategyEntry
from .strategy_state import ProfileStrategyState


@dataclass(frozen=True)
class ProfileListFileEditorState:
    kind: str = ""
    display_path: str = ""
    text: str = ""
    editable: bool = False
    invalid_lines: tuple[tuple[int, str], ...] = ()
    error_text: str = ""


@dataclass(frozen=True)
class ProfileListItem:
    key: str
    persistent_key: str
    profile_index: int
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
    group_name: str
    order: int
    order_is_manual: bool = False
    group_collapsed: bool = False
    user_profile_id: str = ""


@dataclass(frozen=True)
class ProfileListPayload:
    items: tuple[ProfileListItem, ...]
    selected_preset_file_name: str
    selected_preset_name: str
    normalized_split_profiles: int = 0
    normalized_created_profiles: int = 0


@dataclass(frozen=True)
class ProfileSetupPayload:
    item: ProfileListItem
    strategy_entries: dict[str, StrategyEntry]
    strategy_states: dict[str, ProfileStrategyState]
    raw_profile_text: str
    raw_strategy_text: str
    match_summary: str
    editable_filter_kind: str = ""
    editable_filter_value: str = ""
    editable_filter_enabled: bool = True
    editable_filter_role: str = "primary"
    editable_filter_kinds: tuple[str, ...] = ()
    in_range: str = "x"
    out_range: str = "a"
    current_strategy_state: ProfileStrategyState = ProfileStrategyState()
