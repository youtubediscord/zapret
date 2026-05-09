from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Literal


EngineName = Literal["winws1", "winws2"]


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
    identity_key: str = ""

    @property
    def key(self) -> str:
        if self.identity_key:
            return self.identity_key
        if self.name:
            return _profile_identity_key("name", self.name)
        if self.match_signature:
            return _profile_identity_key("match", self.match_signature)
        content = "\n".join(segment.text for segment in self.segments)
        return _profile_identity_key("content", content)


@dataclass
class Preset:
    engine: EngineName
    header_lines: list[str]
    preamble_lines: list[str]
    profiles: list[Profile]
    source_name: str = ""
    footer_lines: list[str] = field(default_factory=list)


def _profile_identity_key(kind: str, value: str) -> str:
    digest = sha1(str(value or "").encode("utf-8", "surrogatepass")).hexdigest()[:16]
    return f"profile:{kind}:{digest}"
