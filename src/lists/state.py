from __future__ import annotations

from dataclasses import dataclass

@dataclass(slots=True)
class HostlistFolderInfo:
    folder_exists: bool
    hostlist_files_count: int
    ipset_files_count: int
    hostlist_lines: int
    ipset_lines: int
    folder: str


@dataclass(slots=True)
class ListsFolderCategoryInfo:
    folder_exists: bool
    files_count: int
    lines_count: int
    folder: str
    category: str


@dataclass(slots=True)
class HostlistEntriesState:
    entries: list[str]
    base_set: set[str] | None = None


@dataclass(slots=True)
class CustomDomainsLoadState:
    text: str
    lines_count: int


@dataclass(slots=True)
class CustomDomainsSaveState:
    normalized_text: str
    saved_lines: list[str]
    saved_count: int


@dataclass(slots=True)
class CustomDomainsStatusPlan:
    total_count: int
    base_count: int
    user_count: int


@dataclass(slots=True)
class CustomDomainsAddPlan:
    level: str | None
    title: str
    content: str
    new_text: str | None
    clear_input: bool


@dataclass(slots=True)
class CustomIpSetLoadState:
    text: str
    lines_count: int
    base_set: set[str]


@dataclass(slots=True)
class CustomIpSetSaveState:
    normalized_text: str
    saved_lines: list[str]
    saved_count: int


@dataclass(slots=True)
class CustomIpSetStatusPlan:
    total_count: int
    base_count: int
    user_count: int
    invalid_lines: list[tuple[int, str]]


@dataclass(slots=True)
class CustomIpSetAddPlan:
    level: str | None
    title: str
    content: str
    new_text: str | None
    clear_input: bool


@dataclass(slots=True)
class CustomIpRuLoadState:
    text: str
    lines_count: int
    base_set: set[str]


@dataclass(slots=True)
class CustomIpRuSaveState:
    normalized_text: str
    saved_lines: list[str]
    saved_count: int


@dataclass(slots=True)
class CustomIpRuStatusPlan:
    total_count: int
    base_count: int
    user_count: int
    invalid_lines: list[tuple[int, str]]


@dataclass(slots=True)
class CustomIpRuAddPlan:
    level: str | None
    title: str
    content: str
    new_text: str | None
    clear_input: bool


@dataclass(slots=True)
class CustomNetrogatLoadState:
    text: str
    lines_count: int
    base_set: set[str]


@dataclass(slots=True)
class CustomNetrogatSaveState:
    success: bool
    normalized_text: str
    saved_lines: list[str]
    saved_count: int


@dataclass(slots=True)
class CustomNetrogatStatusPlan:
    total_count: int
    base_count: int
    user_count: int


@dataclass(slots=True)
class CustomNetrogatAddPlan:
    level: str | None
    title: str
    content: str
    new_text: str | None
    clear_input: bool


@dataclass(slots=True)
class HostlistActionResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    reload_info: bool = False
    reload_domains: bool = False
    reload_exclusions: bool = False
    append_domains_status_suffix: str = ""
    append_exclusions_status_suffix: str = ""
    invalidate_excl_base_cache: bool = False
