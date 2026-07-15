from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re

from lists.core.layered_files import (
    layered_list_file,
    profile_list_file_available,
    read_profile_user_list_text,
    safe_list_file_name,
    write_profile_user_list_text,
)
from lists.core.files import read_text_file_safe

from .models import Profile


@dataclass(frozen=True)
class ProfileListFileReference:
    kind: str = ""
    file_name: str = ""
    display_path: str = ""
    base_display_path: str = ""
    user_display_path: str = ""
    editable: bool = False
    error_text: str = ""


@dataclass(frozen=True)
class ProfileListFileText:
    final_text: str = ""
    base_text: str = ""
    user_text: str = ""


_FILE_MATCH_NAMES = {
    "--hostlist": "hostlist",
    "--ipset": "ipset",
    "--hostlist-exclude": "hostlist",
    "--ipset-exclude": "ipset",
}

_SERVICE_LIST_FILES = {
    "ipset-dns.txt",
    "ipset-exclude.txt",
}


def profile_list_file_reference(profile: Profile, lists_root: Path) -> ProfileListFileReference:
    for wanted_names in (("--hostlist", "--ipset"), ("--hostlist-exclude", "--ipset-exclude")):
        for segment in getattr(profile, "segments", ()) or ():
            name = str(getattr(segment, "name", "") or "").strip().lower()
            if name not in wanted_names:
                continue
            kind = _FILE_MATCH_NAMES.get(name, "")
            value = str(getattr(segment, "value", "") or "").strip().strip('"').strip("'").lstrip("@")
            if not value:
                return ProfileListFileReference(kind=kind, editable=False, error_text="В profile указан пустой файл списка.")
            if "," in value:
                return ProfileListFileReference(
                    kind=kind,
                    editable=False,
                    error_text="В profile указано несколько файлов списка. Разделите profile на отдельные строки.",
                )
            file_name = safe_list_file_name(value)
            if not file_name:
                return ProfileListFileReference(
                    kind=kind,
                    editable=False,
                    error_text="Не удалось определить имя файла списка.",
                )
            if file_name.lower() in _SERVICE_LIST_FILES:
                return ProfileListFileReference(
                    kind=kind,
                    file_name=file_name,
                    display_path=f"lists/{file_name}",
                    editable=False,
                    error_text="Это служебный список. Он используется profile-ом, но не редактируется из GUI.",
                )
            return ProfileListFileReference(
                kind=kind,
                file_name=file_name,
                display_path=f"lists/{file_name}",
                base_display_path=f"lists/base/{file_name}",
                user_display_path=f"lists/user/{file_name}",
                editable=True,
            )
    return ProfileListFileReference(
        editable=False,
        error_text="У этого profile нет отдельного hostlist/ipset-файла для редактирования.",
    )


def read_profile_list_file_text(lists_root: Path, reference: ProfileListFileReference) -> str:
    return read_profile_list_file_text_parts(lists_root, reference).final_text


def read_profile_list_file_text_parts(lists_root: Path, reference: ProfileListFileReference) -> ProfileListFileText:
    if not reference.editable or not reference.file_name:
        return ProfileListFileText()
    paths = layered_list_file(lists_root, reference.file_name)
    user_text = read_profile_user_list_text(lists_root, reference.file_name)
    base_text = read_text_file_safe(str(paths.base_path)) or ""
    # Превью «итогового» текста собирается из живых слоёв: файл lists/<file>
    # на диске может отставать (чтение больше не пересобирает его). Диск
    # используется только когда слоёв нет вовсе — например, скачанный список
    # без base/user.
    if base_text or user_text:
        final_text = _join_visible_layers(base_text, user_text)
    else:
        final_text = read_text_file_safe(str(paths.final_path)) or ""
    return ProfileListFileText(
        final_text=final_text,
        base_text=base_text,
        user_text=user_text,
    )


def write_profile_list_file_text(lists_root: Path, reference: ProfileListFileReference, text: str) -> None:
    if not reference.editable or not reference.file_name:
        raise ValueError(reference.error_text or "Файл списка недоступен для редактирования.")
    invalid_lines = validate_profile_list_file_text(reference.kind, text)
    if invalid_lines:
        line, value = invalid_lines[0]
        raise ValueError(f"Строка {line}: неверная запись `{value}`.")
    write_profile_user_list_text(lists_root, reference.file_name, text)


def validate_profile_list_file_text(kind: str, text: str) -> tuple[tuple[int, str], ...]:
    normalized_kind = str(kind or "").strip().lower()
    invalid: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(str(text or "").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if normalized_kind == "ipset":
            if not _valid_ipset_line(line):
                invalid.append((line_number, line))
            continue
        if not _valid_hostlist_line(line):
            invalid.append((line_number, line))
    return tuple(invalid)


def count_profile_list_entries(text: str) -> int:
    return sum(
        1
        for line in str(text or "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def profile_list_file_exists(lists_root: Path, value: str) -> bool:
    file_name = safe_list_file_name(value)
    if not file_name:
        return False
    return profile_list_file_available(lists_root, file_name)


def _valid_ipset_line(line: str) -> bool:
    if "-" in line:
        return False
    try:
        if "/" in line:
            ipaddress.ip_network(line, strict=False)
        else:
            ipaddress.ip_address(line)
        return True
    except Exception:
        return False


def _valid_hostlist_line(line: str) -> bool:
    value = str(line or "").strip().lower()
    if value.startswith("^"):
        value = value[1:].strip()
    if value.startswith("*."):
        value = value[2:].strip()
    if value.startswith("."):
        value = value[1:].strip()
    if not value or "://" in value or "/" in value or ":" in value:
        return False
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        pass
    try:
        ascii_domain = value.encode("idna").decode("ascii")
    except Exception:
        return False
    if len(ascii_domain) > 253 or "." not in ascii_domain:
        return False
    labels = ascii_domain.rstrip(".").split(".")
    if len(labels) < 2:
        return False
    # Числового TLD не существует (RFC 3696): такое значение — IP-подобная
    # запись, которой место в ipset, а не в hostlist.
    if labels[-1].isdigit():
        return False
    label_re = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
    return all(label_re.fullmatch(label or "") for label in labels)


def _join_visible_layers(base_text: str, user_text: str) -> str:
    chunks = []
    for text in (base_text, user_text):
        value = str(text or "").strip()
        if value:
            chunks.append(value)
    if not chunks:
        return ""
    return "\n".join(chunks) + "\n"
