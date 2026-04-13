from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProfileSegment:
    kind: str
    text: str
    target_keys: tuple[str, ...] = ()
    selector_value: str = ""
    selector_family: str = ""
    selector_is_positive: bool = False


@dataclass
class FilterProfile:
    match_lines: list[str]
    action_lines: list[str]
    segments: list[ProfileSegment] = field(default_factory=list, repr=False)
    protocol_kind: str = ""
    canonical_target_keys: tuple[str, ...] = ()


@dataclass
class SourcePreset:
    header_lines: list[str]
    preamble_lines: list[str]
    profiles: list[FilterProfile]


@dataclass(frozen=True)
class PresetTargetView:
    target_key: str
    display_name: str


@dataclass(frozen=True)
class OutRangeSettings:
    enabled: bool = False
    value: int = 0
    mode: str = "n"
    raw_line: str = ""


@dataclass(frozen=True)
class SendSettings:
    enabled: bool = False
    repeats: int = 2
    ip_ttl: int = 0
    ip6_ttl: int = 0
    ip_id: str = "none"
    badsum: bool = False
    raw_line: str = ""


@dataclass(frozen=True)
class SyndataSettings:
    enabled: bool = False
    blob: str = "tls_google"
    tls_mod: str = "none"
    autottl_delta: int = 0
    autottl_min: int = 3
    autottl_max: int = 20
    tcp_flags_unset: str = "none"
    raw_line: str = ""


@dataclass(frozen=True)
class PresetTargetDetails:
    target_key: str
    display_name: str
    current_strategy: str
    out_range_settings: OutRangeSettings
    send_settings: SendSettings
    syndata_settings: SyndataSettings
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TargetContext:
    target_key: str
    profile_index: int
    display_name: str
    protocol_kind: str
    filter_mode: str
    selector_family: str
    selector_value: str
    strategy_candidates: tuple[str, ...]
    related_profiles: tuple["TargetProfileSnapshot", ...] = ()
    metadata: Any = None


@dataclass(frozen=True)
class TargetProfileSnapshot:
    profile_index: int
    protocol_kind: str
    match_lines: tuple[str, ...]
    action_lines: tuple[str, ...]
    target_keys: tuple[str, ...]
