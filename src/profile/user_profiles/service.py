from __future__ import annotations

import re
from pathlib import Path

from core.paths import AppPaths
from settings.mode import ENGINE_WINWS1, ENGINE_WINWS2
from settings.store import get_user_profiles_settings, set_user_profiles_settings

from lists.core.layered_files import (
    delete_profile_user_list_file,
    ensure_profile_user_list_file,
    rename_profile_user_list_file,
    safe_list_file_name,
)

from ..models import EngineName, Profile
from ..parser import parse_preset_text
from ..strategy_catalog import load_strategy_catalogs
from ..template_catalog import load_profile_templates


_PORTS_RE = re.compile(r"^[0-9*,~-]+$")
_SLUG_RE = re.compile(r"[^a-z0-9а-яё]+", flags=re.IGNORECASE)
_RU_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
})


def create_user_profile(paths: AppPaths, *, name: str, protocol: str, ports: str) -> str:
    clean_name = _clean_name(name)
    _validate_unique_profile_name(paths, clean_name)
    clean_protocol = _clean_protocol(protocol)
    clean_ports = _clean_ports(ports, clean_protocol)
    profile_id = _unique_profile_id(_slugify(clean_name))
    hostlist = f"lists/{profile_id}.txt"
    ipset = f"lists/ipset-{profile_id}.txt"

    lists_root = Path(paths.user_root) / "lists"
    ensure_profile_user_list_file(lists_root, f"{profile_id}.txt")
    ensure_profile_user_list_file(lists_root, f"ipset-{profile_id}.txt")

    settings = get_user_profiles_settings()
    profiles = dict(settings.get("profiles") or {})
    profiles[profile_id] = {
        "name": clean_name,
        "protocol": clean_protocol,
        "ports": clean_ports,
        "hostlist": hostlist,
        "ipset": ipset,
    }
    set_user_profiles_settings({"version": 1, "profiles": profiles})
    return profile_id


def update_user_profile(paths: AppPaths, profile_id: str, *, name: str, protocol: str, ports: str) -> tuple[str, dict[str, str]]:
    clean_profile_id = str(profile_id or "").strip()
    if not clean_profile_id:
        raise ValueError("Profile id не должен быть пустым")
    settings = get_user_profiles_settings()
    profiles = dict(settings.get("profiles") or {})
    row = profiles.get(clean_profile_id)
    if not isinstance(row, dict):
        raise ValueError("Пользовательский profile не найден")

    old_name = str(row.get("name") or "").strip()
    clean_name = _clean_name(name)
    _validate_unique_profile_name(paths, clean_name, exclude_profile_id=clean_profile_id)
    clean_protocol = _clean_protocol(protocol)
    clean_ports = _clean_ports(ports, clean_protocol)

    old_hostlist = str(row.get("hostlist") or "").strip()
    old_ipset = str(row.get("ipset") or "").strip()
    new_stem = _unique_file_stem(_slugify(clean_name), exclude_profile_id=clean_profile_id)
    new_hostlist = f"lists/{new_stem}.txt"
    new_ipset = f"lists/ipset-{new_stem}.txt"
    _rename_user_list_file(paths, old_hostlist, new_hostlist)
    _rename_user_list_file(paths, old_ipset, new_ipset)

    updated_row = {
        "name": clean_name,
        "protocol": clean_protocol,
        "ports": clean_ports,
        "hostlist": new_hostlist,
        "ipset": new_ipset,
    }
    profiles[clean_profile_id] = updated_row
    set_user_profiles_settings({"version": 1, "profiles": profiles})
    return old_name, updated_row


def delete_user_profile(paths: AppPaths, profile_id: str) -> tuple[str, dict[str, str]]:
    clean_profile_id = str(profile_id or "").strip()
    if not clean_profile_id:
        raise ValueError("Profile id не должен быть пустым")
    settings = get_user_profiles_settings()
    profiles = dict(settings.get("profiles") or {})
    row = profiles.get(clean_profile_id)
    if not isinstance(row, dict):
        raise ValueError("Пользовательский profile не найден")

    old_name = str(row.get("name") or "").strip()
    del profiles[clean_profile_id]
    set_user_profiles_settings({"version": 1, "profiles": profiles})
    _delete_user_list_file(paths, str(row.get("hostlist") or ""))
    _delete_user_list_file(paths, str(row.get("ipset") or ""))
    return old_name, {
        "name": old_name,
        "protocol": str(row.get("protocol") or ""),
        "ports": str(row.get("ports") or ""),
        "hostlist": str(row.get("hostlist") or ""),
        "ipset": str(row.get("ipset") or ""),
    }


def load_user_profile_templates(paths: AppPaths, engine: EngineName | str) -> dict[str, Profile]:
    normalized_engine = str(engine or "").strip().lower()
    profiles = get_user_profiles_settings().get("profiles") or {}
    result: dict[str, Profile] = {}
    for profile_id, row in sorted(profiles.items()):
        text = _profile_text(row, paths=paths, engine=normalized_engine)
        if not text:
            continue
        try:
            preset = parse_preset_text(text, engine=normalized_engine, source_name="user_profiles")
        except Exception:
            continue
        if preset.profiles:
            result[f"user:{profile_id}"] = preset.profiles[0]
    return result


def _profile_text(row: object, *, paths: AppPaths, engine: str) -> str:
    if not isinstance(row, dict):
        return ""
    name = _clean_name(row.get("name"))
    protocol = _clean_protocol(row.get("protocol"))
    ports = _clean_ports(row.get("ports"), protocol)
    hostlist = str(row.get("hostlist") or "").strip()
    if not hostlist:
        return ""
    lines = [
        f"--name={name}",
        f"--filter-{protocol}={ports}",
        f"--hostlist={hostlist}",
    ]
    if engine == ENGINE_WINWS2:
        lines.append("--lua-desync=pass")
    elif engine == ENGINE_WINWS1:
        lines.extend(_first_strategy_lines(paths, engine=engine, protocol=protocol))
    return "\n".join(lines) + "\n"


def _first_strategy_lines(paths: AppPaths, *, engine: str, protocol: str) -> list[str]:
    if protocol == "l7":
        protocol = "udp"
    catalog = load_strategy_catalogs(paths, engine).get(protocol) or {}
    for entry in catalog.values():
        lines = [line.strip() for line in str(entry.args or "").splitlines() if line.strip()]
        if lines:
            return lines
    return []


def _clean_name(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Название profile не должно быть пустым")
    return text


def _clean_protocol(value: object) -> str:
    protocol = str(value or "").strip().lower()
    if protocol not in {"tcp", "udp", "l7"}:
        raise ValueError("Тип profile должен быть TCP, UDP или L7")
    return protocol


def _clean_ports(value: object, protocol: str = "tcp") -> str:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        raise ValueError("Значение фильтра profile не должно быть пустым")
    if str(protocol or "").strip().lower() == "l7":
        if not re.match(r"^[a-z0-9_,.-]+$", text, flags=re.IGNORECASE):
            raise ValueError("L7 можно указать словами через запятую, например stun,discord")
        return text
    if not _PORTS_RE.match(text):
        raise ValueError("Порты можно указать числами, диапазонами и запятыми")
    return text


def _slugify(value: str) -> str:
    text = value.strip().lower().translate(_RU_TRANSLIT)
    text = _SLUG_RE.sub("-", text).strip("-")
    return text or "profile"


def _unique_profile_id(base: str) -> str:
    profiles = get_user_profiles_settings().get("profiles") or {}
    candidate = base
    counter = 2
    while candidate in profiles:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _unique_file_stem(base: str, *, exclude_profile_id: str = "") -> str:
    profiles = get_user_profiles_settings().get("profiles") or {}
    used: set[str] = set()
    excluded = str(exclude_profile_id or "").strip()
    for profile_id, row in profiles.items():
        if str(profile_id or "").strip() == excluded or not isinstance(row, dict):
            continue
        for field in ("hostlist", "ipset"):
            value = str(row.get(field) or "").replace("\\", "/").strip()
            if not value:
                continue
            name = Path(value).name
            stem = name[:-4] if name.lower().endswith(".txt") else Path(name).stem
            if stem.startswith("ipset-"):
                stem = stem[6:]
            if stem:
                used.add(stem.casefold())
    candidate = base
    counter = 2
    while candidate.casefold() in used:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _validate_unique_profile_name(paths: AppPaths, name: str, *, exclude_profile_id: str = "") -> None:
    wanted = _name_key(name)
    if not wanted:
        return

    profiles = get_user_profiles_settings().get("profiles") or {}
    excluded = str(exclude_profile_id or "").strip()
    for profile_id, row in profiles.items():
        if str(profile_id or "").strip() == excluded:
            continue
        if isinstance(row, dict) and _name_key(row.get("name")) == wanted:
            raise ValueError("Пользовательский profile с таким названием уже есть")

    for system_name in _system_profile_names(paths):
        if _name_key(system_name) == wanted:
            raise ValueError("Такое название уже занято системным profile-ом")


def _system_profile_names(paths: AppPaths) -> set[str]:
    names: set[str] = set()
    for engine in (ENGINE_WINWS2, ENGINE_WINWS1):
        for profile in load_profile_templates(paths, engine).values():
            name = str(getattr(profile, "name", "") or getattr(profile, "display_name", "") or "").strip()
            if name:
                names.add(name)
    return names


def _name_key(value: object) -> str:
    return str(value or "").strip().casefold()


def _rename_user_list_file(paths: AppPaths, old_value: str, new_value: str) -> None:
    old_name = safe_list_file_name(old_value)
    new_name = safe_list_file_name(new_value)
    if not new_name:
        return
    lists_root = Path(paths.user_root) / "lists"
    rename_profile_user_list_file(lists_root, old_name, new_name)


def _delete_user_list_file(paths: AppPaths, value: str) -> None:
    name = safe_list_file_name(value)
    if not name:
        return
    delete_profile_user_list_file(Path(paths.user_root) / "lists", name)
