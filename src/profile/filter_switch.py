from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from .editable_settings import EditableProfileSettings, normalize_filter_value
from .list_file_editor import profile_list_file_exists


_SERVICE_EXCLUDE_HOSTLIST_NAME = "netrogat.txt"
_SERVICE_EXCLUDE_IPSET_NAMES = ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt")
_SERVICE_EXCLUDE_IPSET_NAME_SET = frozenset(_SERVICE_EXCLUDE_IPSET_NAMES)


@dataclass(frozen=True, slots=True)
class FilterKindSwitchCandidate:
    filter_kind: str
    filter_value: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class FilterKindSwitchResolution:
    allowed: bool
    filter_kind: str
    filter_value: str
    reason: str = ""


def build_filter_kind_candidate(settings: EditableProfileSettings, filter_kind: str) -> FilterKindSwitchCandidate:
    current_kind = str(settings.filter_kind or "hostlist").strip().lower()
    target_kind = str(filter_kind or "").strip().lower()
    if not settings.filter_editable:
        return FilterKindSwitchCandidate(target_kind, "", "not_editable")
    if current_kind not in {"hostlist", "ipset"} or target_kind not in {"hostlist", "ipset"}:
        return FilterKindSwitchCandidate(target_kind, "", "unsupported_kind")

    target_value = _filter_value_for_kind_switch(settings, target_kind)
    if not target_value:
        return FilterKindSwitchCandidate(target_kind, "", "missing_pair")
    return FilterKindSwitchCandidate(target_kind, target_value)


def resolve_filter_kind_switch(
    settings: EditableProfileSettings,
    filter_kind: str,
    app_paths: Any,
) -> FilterKindSwitchResolution:
    current_kind = str(settings.filter_kind or "hostlist").strip().lower()
    candidate = build_filter_kind_candidate(settings, filter_kind)
    if candidate.reason:
        return FilterKindSwitchResolution(False, candidate.filter_kind, candidate.filter_value, candidate.reason)

    if candidate.filter_kind != current_kind and not _filter_files_available(app_paths, candidate.filter_value):
        return FilterKindSwitchResolution(False, candidate.filter_kind, candidate.filter_value, "missing_file")
    return FilterKindSwitchResolution(True, candidate.filter_kind, candidate.filter_value)


def _filter_value_for_kind_switch(settings: EditableProfileSettings, filter_kind: str) -> str:
    current_kind = str(settings.filter_kind or "hostlist").strip().lower()
    target_kind = str(filter_kind or "").strip().lower()
    current_value = str(settings.filter_value or "").strip()
    if target_kind == current_kind:
        return normalize_filter_value(current_value, target_kind, filter_role=settings.filter_role)
    if str(settings.filter_role or "").strip().lower() == "exclude":
        return _paired_exclude_filter_value(current_value, current_kind, target_kind)
    if "," in current_value:
        return ""
    return _paired_primary_filter_value(current_value, current_kind, target_kind)


def _paired_exclude_filter_value(value: str, current_kind: str, target_kind: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    values = _filter_reference_values(raw)
    if current_kind == "hostlist" and target_kind == "ipset":
        if len(values) != 1:
            return ""
        path = PureWindowsPath(values[0])
        if path.name.lower() != _SERVICE_EXCLUDE_HOSTLIST_NAME:
            return ""
        return ",".join(_replace_filter_path_name(values[0], path, name) for name in _SERVICE_EXCLUDE_IPSET_NAMES)

    if current_kind == "ipset" and target_kind == "hostlist":
        names = [PureWindowsPath(item).name.lower() for item in values]
        if len(names) != len(_SERVICE_EXCLUDE_IPSET_NAMES) or frozenset(names) != _SERVICE_EXCLUDE_IPSET_NAME_SET:
            return ""
        path = PureWindowsPath(values[0])
        return _replace_filter_path_name(values[0], path, _SERVICE_EXCLUDE_HOSTLIST_NAME)

    return ""


def _paired_primary_filter_value(value: str, current_kind: str, target_kind: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    path = PureWindowsPath(raw)
    name = path.name
    if not name:
        return raw

    lower_name = name.lower()
    if target_kind == "ipset" and lower_name == "other.txt":
        return _replace_filter_path_name(raw, path, "ipset-all.txt")
    if target_kind == "hostlist" and lower_name == "ipset-all.txt":
        return _replace_filter_path_name(raw, path, "other.txt")

    suffix = "".join(path.suffixes)
    stem = name[: -len(suffix)] if suffix else name
    normalized_stem = stem.lower()
    if current_kind == "hostlist" and target_kind == "ipset":
        if normalized_stem.startswith(("ipset-", "ipset_")):
            return raw
        return _replace_filter_path_name(raw, path, f"ipset-{stem}{suffix}")
    if current_kind == "ipset" and target_kind == "hostlist":
        if normalized_stem.startswith(("ipset-", "ipset_")):
            return _replace_filter_path_name(raw, path, f"{stem[6:]}{suffix}")
        return ""
    return normalize_filter_value(raw, target_kind)


def _replace_filter_path_name(raw: str, path: PureWindowsPath, new_name: str) -> str:
    parent = str(path.parent)
    if not parent or parent == ".":
        return new_name
    separator = "\\" if "\\" in raw else "/"
    return f"{parent}{separator}{new_name}"


def _filter_files_available(app_paths: Any, filter_value: str) -> bool:
    lists_root = Path(getattr(app_paths, "user_root", "")) / "lists"
    if not lists_root.exists():
        return False
    for value in _filter_reference_values(filter_value):
        if not _looks_like_list_file_reference(value):
            continue
        if not profile_list_file_exists(lists_root, value):
            return False
    return True


def _filter_reference_values(filter_value: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in str(filter_value or "").split(","):
        value = part.strip().strip('"').strip("'").lstrip("@")
        if value:
            values.append(value)
    return tuple(values)


def _looks_like_list_file_reference(value: str) -> bool:
    normalized = str(value or "").strip().replace("\\", "/")
    return normalized.startswith("lists/") or "/" in normalized or normalized.lower().endswith((".txt", ".lst", ".list"))
