from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PureWindowsPath
import re
from typing import Literal

from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2

EngineName = Literal[ENGINE_WINWS1, ENGINE_WINWS2]


@dataclass
class ProfileSegment:
    kind: str
    text: str
    name: str = ""
    value: str = ""


@dataclass
class ProfileMatch:
    filter_lines: list[str] = field(default_factory=list)
    hostlist_lines: list[str] = field(default_factory=list)
    ipset_lines: list[str] = field(default_factory=list)
    hostlist_exclude_lines: list[str] = field(default_factory=list)
    hostlist_auto_lines: list[str] = field(default_factory=list)
    ipset_exclude_lines: list[str] = field(default_factory=list)
    hostlist_domains_lines: list[str] = field(default_factory=list)
    inline_ipset_lines: list[str] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)

    def all_lines(self) -> list[str]:
        return [
            *self.filter_lines,
            *self.hostlist_lines,
            *self.ipset_lines,
            *self.hostlist_exclude_lines,
            *self.hostlist_auto_lines,
            *self.ipset_exclude_lines,
            *self.hostlist_domains_lines,
            *self.inline_ipset_lines,
            *self.other_lines,
        ]


@dataclass
class ProfileActionArg:
    raw: str
    key: str = ""
    value: str = ""
    is_flag: bool = False


@dataclass
class ProfileAction:
    raw_line: str
    func_name: str
    args: list[ProfileActionArg] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    payload: str = "all"
    in_range: str = "x"
    out_range: str = "a"


@dataclass
class Winws2Strategy:
    actions: list[ProfileAction] = field(default_factory=list)
    strategy_lines: list[str] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)


@dataclass
class Winws1Strategy:
    dpi_desync_lines: list[str] = field(default_factory=list)
    dup_lines: list[str] = field(default_factory=list)
    wssize_lines: list[str] = field(default_factory=list)
    ip_id_lines: list[str] = field(default_factory=list)
    strategy_lines: list[str] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)


StrategyModel = Winws1Strategy | Winws2Strategy


@dataclass
class Profile:
    id: str
    index: int
    engine: EngineName
    display_name: str
    enabled: bool
    match: ProfileMatch
    strategy: StrategyModel
    segments: list[ProfileSegment] = field(default_factory=list)
    new_line: str = ""
    name: str = ""
    match_signature: str = ""
    persistent_key: str = ""

    @property
    def key(self) -> str:
        return self.id


@dataclass
class Preset:
    engine: EngineName
    header_lines: list[str]
    preamble_lines: list[str]
    profiles: list[Profile]
    source_name: str = ""
    footer_lines: list[str] = field(default_factory=list)


def build_profile_persistent_key(name: str, match_signature: str) -> str:
    clean_name = str(name or "").strip()
    if clean_name:
        return f"name:{clean_name}"
    return f"sig:{_logical_match_signature(match_signature)}"


def build_profile_logical_key(match_signature: str) -> str:
    return _logical_match_signature(match_signature)


def _logical_match_signature(match_signature: str) -> str:
    parts: list[str] = []
    for raw_part in str(match_signature or "").strip().split("|"):
        part = raw_part.strip()
        if not part:
            continue
        if part.startswith("hostlist=") or part.startswith("ipset="):
            _name, _sep, value = part.partition("=")
            normalized = _logical_list_value(value)
            if normalized:
                parts.append(f"list={normalized}")
                continue
        parts.append(part)
    return "|".join(sorted(parts))


def _logical_list_value(value: str) -> str:
    name = PureWindowsPath(str(value or "").replace("\\", "/")).name.lower().strip()
    if not name:
        return ""
    name = re.sub(r"\.(txt|lst|list|json)$", "", name, flags=re.IGNORECASE)
    for prefix in ("ipset-", "hostlist-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()
