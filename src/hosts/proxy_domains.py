"""Чтение hosts-каталога.

Каталог содержит поставляемый список профилей, сервисов, доменов и IP.
Пользовательский выбор хранится отдельно в `settings/settings.json`.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

from config.config import MAIN_DIRECTORY
from settings import store as settings_store


def _log(msg: str, level: str = "INFO") -> None:
    """Отложенный импорт log, чтобы модуль можно было импортировать без GUI."""
    try:
        from log.log import log as _log_impl  # type: ignore

        _log_impl(msg, level)
    except Exception:
        print(f"[{level}] {msg}")


@dataclass(frozen=True)
class HostsCatalog:
    dns_profiles: list[str]
    dns_profile_names: dict[str, str]
    services: dict[str, dict[str, list[str]]]
    service_entries: dict[str, list[tuple[str, list[str]]]]
    service_order: list[str]
    service_modes: dict[str, str]


_SERVICE_MODE_DNS = "dns"
_SERVICE_MODE_HOSTS = "hosts"
_LEGACY_SERVICE_MODE_DIRECT = "direct"
_CATALOG_DIR_NAME = "hosts_catalog"
_LEGACY_CATALOG_FILE_NAME = "hosts_catalog.json"
_HOSTS_PROFILE_ID = "hosts"
_HOSTS_PROFILE_NAME = "Вкл. (активировать hosts)"
_LEGACY_DIRECT_PROFILE_ID = "direct"

_CACHE_LOCK = threading.RLock()
_CACHE: HostsCatalog | None = None
_CACHE_TEXT: str | None = None
_CACHE_SIG: tuple[int, int] | None = None
_CACHE_PATH: Path | None = None
_CACHE_PROFILE_INDEX: dict[str, object] | None = None
_RECENT_SIG_PATH: Path | None = None
_RECENT_SIG: tuple[int, int] | None = None
_RECENT_SIG_CHECKED_AT = 0.0
_RECENT_SIG_TTL_SECONDS = 1.0
_MISSING_CATALOG_LOGGED = False


def _clean_str(value: object) -> str:
    return str(value or "").strip()


def _get_app_root() -> Path:
    """
    Возвращает корень для hosts-каталога.

    - source-режим: общий корень zapretgui, где лежит private_zapretgui;
    - exe-сборка: папка, где лежит exe.
    """
    if getattr(sys, "frozen", False):
        return Path(MAIN_DIRECTORY)
    return Path(__file__).resolve().parents[3]


def _get_hosts_catalog_candidates() -> list[Path]:
    root = _get_app_root()
    if getattr(sys, "frozen", False):
        json_root = root / "json"
    else:
        json_root = root / "private_zapretgui" / "resources" / "json"
    return [
        json_root / _CATALOG_DIR_NAME,
        json_root / _LEGACY_CATALOG_FILE_NAME,
    ]


def _get_hosts_catalog_path() -> Path:
    candidates = _get_hosts_catalog_candidates()
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def get_hosts_catalog_path() -> Path:
    return _get_hosts_catalog_path()


def _empty_catalog() -> HostsCatalog:
    return HostsCatalog(
        dns_profiles=[],
        dns_profile_names={},
        services={},
        service_entries={},
        service_order=[],
        service_modes={},
    )


def _normalize_profile(raw: object) -> tuple[str, str] | None:
    if not isinstance(raw, dict):
        return None
    profile_id = _clean_str(raw.get("id"))
    name = _clean_str(raw.get("name"))
    if not profile_id or not name:
        return None
    return profile_id, name


def _normalize_mode(raw: object) -> str:
    mode = _clean_str(raw).lower()
    if mode in {_SERVICE_MODE_HOSTS, _LEGACY_SERVICE_MODE_DIRECT}:
        return _SERVICE_MODE_HOSTS
    return _SERVICE_MODE_DNS


def _get_hosts_profile_id(profiles: list[str]) -> str:
    if _HOSTS_PROFILE_ID in profiles:
        return _HOSTS_PROFILE_ID
    if _LEGACY_DIRECT_PROFILE_ID in profiles:
        return _LEGACY_DIRECT_PROFILE_ID
    return _HOSTS_PROFILE_ID


def _ensure_hosts_profile(profiles: list[str], profile_names: dict[str, str]) -> None:
    if _HOSTS_PROFILE_ID in profile_names or _LEGACY_DIRECT_PROFILE_ID in profile_names:
        return
    profiles.append(_HOSTS_PROFILE_ID)
    profile_names[_HOSTS_PROFILE_ID] = _HOSTS_PROFILE_NAME


def _normalize_ip_values(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [_clean_str(item) for item in raw if _clean_str(item)]
    value = _clean_str(raw)
    return [value] if value else []


def _append_service_entry(
    *,
    profiles: list[str],
    services: dict[str, dict[str, list[str]]],
    service_entries: dict[str, list[tuple[str, list[str]]]],
    service_name: str,
    host: str,
    profile_id: str,
    ip: str,
) -> None:
    if not host or not ip or profile_id not in profiles:
        return
    profile_index = profiles.index(profile_id)
    row = [""] * len(profiles)
    row[profile_index] = ip
    service_entries.setdefault(service_name, []).append((host, row))
    service_map = services.setdefault(service_name, {})
    merged = list(service_map.get(host, [""] * len(profiles)))
    if len(merged) < len(profiles):
        merged.extend([""] * (len(profiles) - len(merged)))
    merged[profile_index] = ip
    service_map[host] = merged


def _append_service_row(
    *,
    profiles: list[str],
    services: dict[str, dict[str, list[str]]],
    service_entries: dict[str, list[tuple[str, list[str]]]],
    service_name: str,
    host: str,
    ips_by_profile: dict[str, str],
) -> None:
    if not host:
        return
    row = [""] * len(profiles)
    for profile_id, ip in ips_by_profile.items():
        if profile_id not in profiles or not ip:
            continue
        row[profiles.index(profile_id)] = ip
    if not any(row):
        return
    service_entries.setdefault(service_name, []).append((host, row))
    services.setdefault(service_name, {})[host] = list(row)


def _parse_hosts_catalog_json(text: str) -> HostsCatalog:
    try:
        data = json.loads(text or "{}")
    except Exception as exc:
        _log(f"Не удалось разобрать {_CATALOG_FILE_NAME}: {exc}", "WARNING")
        return _empty_catalog()

    if not isinstance(data, dict):
        _log(f"{_CATALOG_FILE_NAME} должен содержать JSON-объект", "WARNING")
        return _empty_catalog()

    profiles: list[str] = []
    profile_names: dict[str, str] = {}
    for raw_profile in data.get("profiles") or []:
        normalized = _normalize_profile(raw_profile)
        if normalized is None:
            continue
        profile_id, name = normalized
        if profile_id in profile_names:
            continue
        profiles.append(profile_id)
        profile_names[profile_id] = name

    services: dict[str, dict[str, list[str]]] = {}
    service_entries: dict[str, list[tuple[str, list[str]]]] = {}
    service_order: list[str] = []
    service_modes: dict[str, str] = {}

    for raw_service in data.get("services") or []:
        if not isinstance(raw_service, dict):
            continue
        service_name = _clean_str(raw_service.get("name"))
        if not service_name:
            continue

        mode = _normalize_mode(raw_service.get("mode"))
        if service_name not in service_order:
            service_order.append(service_name)
        services.setdefault(service_name, {})
        service_entries.setdefault(service_name, [])
        service_modes[service_name.casefold()] = mode

        if mode == _SERVICE_MODE_HOSTS:
            _ensure_hosts_profile(profiles, profile_names)
            hosts_profile_id = _get_hosts_profile_id(profiles)
            for raw_row in raw_service.get("hosts") or []:
                if not isinstance(raw_row, dict):
                    continue
                host = _clean_str(raw_row.get("host"))
                ip = _clean_str(raw_row.get("ip"))
                _append_service_entry(
                    profiles=profiles,
                    services=services,
                    service_entries=service_entries,
                    service_name=service_name,
                    host=host,
                    profile_id=hosts_profile_id,
                    ip=ip,
                )
            continue

        for raw_domain in raw_service.get("domains") or []:
            if not isinstance(raw_domain, dict):
                continue
            host = _clean_str(raw_domain.get("host") or raw_domain.get("domain"))
            raw_ips = raw_domain.get("ips")
            if not host or not isinstance(raw_ips, dict):
                continue

            values_by_profile: dict[str, list[str]] = {}
            for profile_id in profiles:
                if profile_id in {_HOSTS_PROFILE_ID, _LEGACY_DIRECT_PROFILE_ID}:
                    continue
                values = _normalize_ip_values(raw_ips.get(profile_id))
                if values:
                    values_by_profile[profile_id] = values

            row_count = max((len(values) for values in values_by_profile.values()), default=0)
            for row_index in range(row_count):
                row_values: dict[str, str] = {}
                for profile_id, values in values_by_profile.items():
                    if row_index < len(values):
                        row_values[profile_id] = values[row_index]
                _append_service_row(
                    profiles=profiles,
                    services=services,
                    service_entries=service_entries,
                    service_name=service_name,
                    host=host,
                    ips_by_profile=row_values,
                )

    return HostsCatalog(
        dns_profiles=profiles,
        dns_profile_names=profile_names,
        services=services,
        service_entries=service_entries,
        service_order=service_order,
        service_modes=service_modes,
    )


def _read_json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")


def _decode_json_bytes(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8", errors="replace") or "{}")


def _content_sig_entry(*, root: Path, path: Path, raw: bytes) -> tuple[str, int, int]:
    rel = path.relative_to(root).as_posix()
    return (rel, int(zlib.crc32(raw)), len(raw))


def _combine_content_sig(entries: list[tuple[str, int, int]]) -> tuple[int, int]:
    """Сворачивает записи (rel, crc32, size) в подпись каталога.

    Записи сортируются перед свёрткой, поэтому результат не зависит от порядка
    чтения файлов — загрузчик и watcher обязаны получать одно и то же значение.
    """
    checksum = 0
    total_size = 0
    for rel, raw_crc, size in sorted(entries):
        checksum = zlib.crc32(f"{rel}\0{raw_crc}\0{size}\0".encode("utf-8", errors="replace"), checksum)
        total_size += size
    return (int(checksum), int(total_size))


def _iter_json_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(
        child
        for child in path.iterdir()
        if child.is_file() and child.suffix.lower() == ".json"
    )


def _split_catalog_files(root: Path) -> list[Path]:
    """Канонический список файлов split-каталога.

    Единственный источник истины и для загрузчика, и для подписи watcher'а:
    расхождение набора файлов давало ложные «изменения» каталога.
    """
    files: list[Path] = []
    profiles_path = root / "dns_sources.json"
    if profiles_path.is_file():
        files.append(profiles_path)
    files.extend(_iter_json_files(root / "dns"))
    files.extend(_iter_json_files(root / "hosts"))
    return files


def _normalize_split_profiles(raw: object) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        raw_profiles = raw.get("dns_sources") or raw.get("profiles") or []
    elif isinstance(raw, list):
        raw_profiles = raw
    else:
        raw_profiles = []

    profiles: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_profile in raw_profiles:
        normalized = _normalize_profile(raw_profile)
        if normalized is None:
            continue
        profile_id, name = normalized
        if profile_id in {_HOSTS_PROFILE_ID, _LEGACY_DIRECT_PROFILE_ID} or profile_id in seen:
            continue
        seen.add(profile_id)
        profiles.append({"id": profile_id, "name": name})
    return profiles


def _normalize_split_services(raw: object, *, mode: str) -> list[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("services"), list):
        raw_services = raw.get("services") or []
    elif isinstance(raw, list):
        raw_services = raw
    else:
        raw_services = [raw]

    services: list[dict] = []
    for raw_service in raw_services:
        if not isinstance(raw_service, dict):
            continue
        service = dict(raw_service)
        service["mode"] = mode
        services.append(service)
    return services


def _load_split_catalog_data(path: Path) -> dict:
    data, _sig = _load_split_catalog_data_with_sig(path)
    return data


def _load_split_catalog_data_with_sig(path: Path) -> tuple[dict, tuple[int, int]]:
    sig_entries: list[tuple[str, int, int]] = []

    def read_json(service_path: Path) -> object:
        raw = service_path.read_bytes()
        sig_entries.append(_content_sig_entry(root=path, path=service_path, raw=raw))
        return _decode_json_bytes(raw)

    profiles_path = path / "dns_sources.json"
    profiles = _normalize_split_profiles(read_json(profiles_path) if profiles_path.is_file() else [])

    services: list[dict] = []
    for service_path in _iter_json_files(path / "dns"):
        try:
            services.extend(_normalize_split_services(read_json(service_path), mode=_SERVICE_MODE_DNS))
        except Exception as exc:
            _log(f"Не удалось прочитать DNS-сервис hosts-каталога {service_path.name}: {exc}", "WARNING")

    for service_path in _iter_json_files(path / "hosts"):
        try:
            services.extend(_normalize_split_services(read_json(service_path), mode=_SERVICE_MODE_HOSTS))
        except Exception as exc:
            _log(f"Не удалось прочитать hosts-сервис hosts-каталога {service_path.name}: {exc}", "WARNING")

    return {
        "version": 1,
        "profiles": profiles,
        "services": services,
    }, _combine_content_sig(sig_entries)


def _remember_recent_path_sig(path: Path, sig: tuple[int, int] | None) -> None:
    global _RECENT_SIG_PATH, _RECENT_SIG, _RECENT_SIG_CHECKED_AT
    if sig is None:
        return
    _RECENT_SIG_PATH = path
    _RECENT_SIG = sig
    _RECENT_SIG_CHECKED_AT = time.monotonic()


def _get_recent_path_sig(path: Path) -> tuple[int, int] | None:
    if _RECENT_SIG_PATH != path or _RECENT_SIG is None:
        return None
    if time.monotonic() - _RECENT_SIG_CHECKED_AT > _RECENT_SIG_TTL_SECONDS:
        return None
    return _RECENT_SIG


def _get_split_catalog_content_sig(path: Path) -> tuple[int, int]:
    sig_entries: list[tuple[str, int, int]] = []
    for child in _split_catalog_files(path):
        try:
            raw = child.read_bytes()
        except OSError:
            continue
        sig_entries.append(_content_sig_entry(root=path, path=child, raw=raw))
    return _combine_content_sig(sig_entries)


def _get_file_content_sig_from_raw(raw: bytes) -> tuple[int, int]:
    return (int(zlib.crc32(raw)), int(len(raw)))


def _get_file_content_sig(path: Path) -> tuple[int, int]:
    return _get_file_content_sig_from_raw(path.read_bytes())


def _get_path_sig(path: Path) -> tuple[int, int] | None:
    try:
        if path.is_dir():
            sig = _get_split_catalog_content_sig(path)
            _remember_recent_path_sig(path, sig)
            return sig
        sig = _get_file_content_sig(path)
        _remember_recent_path_sig(path, sig)
        return sig
    except Exception:
        return None


def _select_catalog_path() -> tuple[Path, list[Path], bool]:
    candidates = _get_hosts_catalog_candidates()
    existing = [path for path in candidates if path.exists()]
    if existing:
        return existing[0], candidates, True
    return candidates[0], candidates, False


def _load_catalog() -> HostsCatalog:
    global _CACHE, _CACHE_TEXT, _CACHE_SIG, _CACHE_PATH, _CACHE_PROFILE_INDEX, _MISSING_CATALOG_LOGGED

    with _CACHE_LOCK:
        path, candidates, exists = _select_catalog_path()

        if not exists:
            if not _MISSING_CATALOG_LOGGED:
                _log(
                    "hosts-каталог не найден. Ожидается внешняя папка или файл: "
                    + " | ".join(str(path) for path in candidates),
                    "WARNING",
                )
                _MISSING_CATALOG_LOGGED = True
        else:
            _MISSING_CATALOG_LOGGED = False

        has_cache = (
            _CACHE is not None
            and _CACHE_PATH is not None
            and _CACHE_SIG is not None
            and path.exists()
            and _CACHE_PATH == path
        )
        sig = None
        if has_cache:
            sig = _get_recent_path_sig(path)
            if sig is None:
                sig = _get_path_sig(path)

        if (
            has_cache
            and sig is not None
            and _CACHE_SIG == sig
        ):
            return _CACHE

        try:
            if path.exists() and path.is_dir():
                data, sig = _load_split_catalog_data_with_sig(path)
                text = json.dumps(data, ensure_ascii=False, sort_keys=True)
            else:
                raw = path.read_bytes() if path.exists() else b""
                text = raw.decode("utf-8", errors="replace") if raw else ""
                sig = _get_file_content_sig_from_raw(raw) if path.exists() else None
        except Exception as exc:
            _log(f"Не удалось прочитать hosts-каталог: {exc}", "WARNING")
            text = ""
            sig = None

        _CACHE_TEXT = text
        _CACHE = _parse_hosts_catalog_json(text)
        _CACHE_SIG = sig
        _CACHE_PATH = path
        _CACHE_PROFILE_INDEX = None
        _remember_recent_path_sig(path, sig)
        return _CACHE


def invalidate_hosts_catalog_cache() -> None:
    global _CACHE, _CACHE_TEXT, _CACHE_SIG, _CACHE_PATH, _CACHE_PROFILE_INDEX
    global _RECENT_SIG_PATH, _RECENT_SIG, _RECENT_SIG_CHECKED_AT
    with _CACHE_LOCK:
        _CACHE = None
        _CACHE_TEXT = None
        _CACHE_SIG = None
        _CACHE_PATH = None
        _CACHE_PROFILE_INDEX = None
        _RECENT_SIG_PATH = None
        _RECENT_SIG = None
        _RECENT_SIG_CHECKED_AT = 0.0


def get_hosts_catalog_signature() -> tuple[str, int, int] | None:
    """Возвращает сигнатуру текущего hosts-каталога: (path, revision, size)."""
    path, _candidates, _exists = _select_catalog_path()
    if not path.exists():
        return None
    with _CACHE_LOCK:
        sig = _get_recent_path_sig(path)
    if sig is None:
        sig = _get_path_sig(path)
    if sig is None:
        return None
    revision, size = sig
    return (str(path), revision, size)


def get_hosts_catalog_text() -> str:
    """Возвращает сырой текст hosts-каталога с учётом кэша."""
    _load_catalog()
    with _CACHE_LOCK:
        return _CACHE_TEXT or ""


def get_dns_profiles() -> list[str]:
    return list(_load_catalog().dns_profiles)


def get_dns_profile_display_name(profile_id: str) -> str:
    profile_id = _clean_str(profile_id)
    if not profile_id:
        return ""
    return _load_catalog().dns_profile_names.get(profile_id, profile_id)


def get_all_services() -> list[str]:
    return list(_load_catalog().service_order)


def get_service_domain_names(service_name: str) -> list[str]:
    entries = _load_catalog().service_entries.get(service_name, []) or []
    out: list[str] = []
    seen: set[str] = set()
    for domain, _ips in entries:
        key = domain.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(domain)
    return out


def get_service_domains(service_name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    entries = _load_catalog().service_entries.get(service_name, []) or []
    for domain, ips in entries:
        domain_key = _clean_str(domain).casefold()
        if not domain_key or domain_key in out:
            continue
        for ip in ips or []:
            ip_s = _clean_str(ip)
            if ip_s:
                out[domain_key] = ip_s
                break
    return out


def get_service_domain_ip_rows(service_name: str, profile_name: str) -> list[tuple[str, str]]:
    cat = _load_catalog()
    profile_id = _clean_str(profile_name)
    return _get_complete_profile_rows(cat, service_name, profile_id)


def _get_complete_profile_rows(cat: HostsCatalog, service_name: str, profile_id: str) -> list[tuple[str, str]]:
    if profile_id not in cat.dns_profiles:
        return []
    profile_index = cat.dns_profiles.index(profile_id)

    entries = cat.service_entries.get(service_name, []) or []
    if not entries:
        return []

    required_domains = {domain.casefold() for domain, _ips in entries if domain}
    out: list[tuple[str, str]] = []
    covered_domains: set[str] = set()
    for domain, ips in entries:
        if not ips or profile_index >= len(ips) or not ips[profile_index]:
            continue
        out.append((domain, ips[profile_index]))
        covered_domains.add(domain.casefold())

    if not required_domains or covered_domains != required_domains:
        return []
    return out


def get_service_available_dns_profiles(service_name: str) -> list[str]:
    cat = _load_catalog()
    return _get_service_available_dns_profiles_from_catalog(cat, service_name)


def _get_service_available_dns_profiles_from_catalog(cat: HostsCatalog, service_name: str) -> list[str]:
    entries = cat.service_entries.get(service_name, []) or []
    if not entries:
        return []

    available: list[str] = []
    for profile_id in cat.dns_profiles:
        if _get_complete_profile_rows(cat, service_name, profile_id):
            available.append(profile_id)
    return available


def _is_direct_profile_name(profile_name: str) -> bool:
    profile_id = _clean_str(profile_name).lower()
    display_name = get_dns_profile_display_name(profile_name).lower()
    text = f"{profile_id} {display_name}"
    return (
        profile_id in {_HOSTS_PROFILE_ID, _LEGACY_DIRECT_PROFILE_ID}
        or "вкл. (активировать hosts)" in text
        or "no proxy" in text
        or "direct" in text
        or "hosts" in text
    )


def _infer_direct_profile_index(cat: HostsCatalog) -> int | None:
    for index, profile_id in enumerate(cat.dns_profiles):
        profile_text = f"{profile_id} {cat.dns_profile_names.get(profile_id, '')}".lower()
        if (
            profile_id in {_HOSTS_PROFILE_ID, _LEGACY_DIRECT_PROFILE_ID}
            or "вкл. (активировать hosts)" in profile_text
            or "no proxy" in profile_text
            or "direct" in profile_text
            or "hosts" in profile_text
        ):
            return index
    return None


def _get_declared_service_mode(cat: HostsCatalog, service_name: str) -> str | None:
    key = _clean_str(service_name).casefold()
    if not key:
        return None
    return (cat.service_modes or {}).get(key)


def _service_has_proxy_ips(cat: HostsCatalog, service_name: str) -> bool:
    return _service_has_proxy_ips_with_direct_index(cat, service_name, _infer_direct_profile_index(cat))


def _service_has_proxy_ips_with_direct_index(cat: HostsCatalog, service_name: str, direct_idx: int | None) -> bool:
    declared_mode = _get_declared_service_mode(cat, service_name)
    if declared_mode == _SERVICE_MODE_HOSTS:
        return False
    if declared_mode == _SERVICE_MODE_DNS:
        return True

    entries = cat.service_entries.get(service_name, []) or []
    if not entries:
        return False

    proxy_indices = [i for i in range(len(cat.dns_profiles)) if direct_idx is None or i != direct_idx]
    if not proxy_indices:
        return False

    for _domain, ips in entries:
        direct_ip = ""
        if direct_idx is not None and ips and direct_idx < len(ips):
            direct_ip = _clean_str(ips[direct_idx])
        for idx in proxy_indices:
            if not ips or idx >= len(ips):
                continue
            ip = _clean_str(ips[idx])
            if not ip:
                continue
            if direct_ip and ip == direct_ip:
                continue
            return True
    return False


def service_has_proxy_profiles(service_name: str) -> bool:
    return _service_has_proxy_ips(_load_catalog(), service_name)


def _build_services_profile_index(cat: HostsCatalog) -> dict[str, object]:
    services = list(cat.service_order)
    available_by_service: dict[str, list[str]] = {}
    profile_domain_maps_by_service: dict[str, dict[str, dict[str, str]]] = {}
    profile_domain_ip_candidates_by_service: dict[str, dict[str, dict[str, list[str]]]] = {}
    domain_names_by_service: dict[str, list[str]] = {}
    direct_idx = _infer_direct_profile_index(cat)
    direct_profile = cat.dns_profiles[direct_idx] if direct_idx is not None else None
    profiles = list(cat.dns_profiles)

    for service_name in services:
        entries = cat.service_entries.get(service_name, []) or []
        domain_names: list[str] = []
        seen_domains: set[str] = set()
        for domain, _ips in entries:
            domain_key = _clean_str(domain).casefold()
            if not domain_key or domain_key in seen_domains:
                continue
            seen_domains.add(domain_key)
            domain_names.append(domain)
        domain_names_by_service[service_name] = domain_names

        required_domains = set(seen_domains)
        rows_by_profile: dict[str, list[tuple[str, str]]] = {profile_id: [] for profile_id in profiles}
        covered_by_profile: dict[str, set[str]] = {profile_id: set() for profile_id in profiles}
        for domain, ips in entries:
            domain_key = _clean_str(domain).casefold()
            if not domain_key:
                continue
            for profile_index, profile_id in enumerate(profiles):
                if not ips or profile_index >= len(ips):
                    continue
                ip_value = _clean_str(ips[profile_index])
                if not ip_value:
                    continue
                rows_by_profile[profile_id].append((domain_key, ip_value))
                covered_by_profile[profile_id].add(domain_key)

        service_maps: dict[str, dict[str, str]] = {}
        service_candidates: dict[str, dict[str, list[str]]] = {}
        available: list[str] = []
        for profile_id in profiles:
            rows = rows_by_profile.get(profile_id, [])
            if not required_domains or covered_by_profile.get(profile_id, set()) != required_domains:
                continue
            available.append(profile_id)
            domain_map: dict[str, str] = {}
            candidates: dict[str, list[str]] = {}
            for domain_key, ip_value in rows:
                domain_map.setdefault(domain_key, ip_value)
                values = candidates.setdefault(domain_key, [])
                if ip_value not in values:
                    values.append(ip_value)
            service_maps[profile_id] = domain_map
            service_candidates[profile_id] = candidates
        available_by_service[service_name] = available
        profile_domain_maps_by_service[service_name] = service_maps
        profile_domain_ip_candidates_by_service[service_name] = service_candidates

    return {
        "dns_profiles": list(cat.dns_profiles),
        "dns_profile_names": dict(cat.dns_profile_names),
        "services": services,
        "available_by_service": available_by_service,
        "has_proxy_by_service": {
            service_name: _service_has_proxy_ips_with_direct_index(cat, service_name, direct_idx)
            for service_name in services
        },
        "direct_profile": direct_profile,
        "domain_names_by_service": domain_names_by_service,
        "profile_domain_maps_by_service": profile_domain_maps_by_service,
        "profile_domain_ip_candidates_by_service": profile_domain_ip_candidates_by_service,
    }


def get_services_profile_index() -> dict[str, object]:
    global _CACHE_PROFILE_INDEX

    with _CACHE_LOCK:
        if _CACHE_PROFILE_INDEX is not None:
            return _CACHE_PROFILE_INDEX

    cat = _load_catalog()
    with _CACHE_LOCK:
        if _CACHE_PROFILE_INDEX is None:
            _CACHE_PROFILE_INDEX = _build_services_profile_index(cat)
        return _CACHE_PROFILE_INDEX


def get_service_domain_ip_map(service_name: str, profile_name: str) -> dict[str, str]:
    rows = get_service_domain_ip_rows(service_name, profile_name)
    if not rows:
        return {}

    out: dict[str, str] = {}
    for domain, ip in rows:
        domain_key = _clean_str(domain).casefold()
        if not domain_key or domain_key in out:
            continue
        out[domain_key] = ip
    return out


def load_user_hosts_selection() -> dict[str, str]:
    """Возвращает выбор пользователя: {service_name: profile_id}."""
    try:
        return dict(settings_store.get_hosts_selection() or {})
    except Exception as exc:
        _log(f"Не удалось прочитать выбор hosts из settings.json: {exc}", "WARNING")
        return {}


def save_user_hosts_selection(selected_profiles: dict[str, str]) -> bool:
    """Сохраняет выбор пользователя в settings.json."""
    try:
        return bool(settings_store.set_hosts_selection(dict(selected_profiles or {})))
    except Exception as exc:
        _log(f"Не удалось сохранить выбор hosts в settings.json: {exc}", "WARNING")
        return False


QUICK_SERVICES = [
    ("mdi.robot", "ChatGPT & Sora (OpenAI)", "#10a37f"),
    ("mdi.google", "Gemini AI", "#4285f4"),
    ("fa5s.brain", "Claude", "#cc9b7a"),
    ("fa5b.microsoft", "Microsoft (Copilot, Designer, Xbox)", "#00bcf2"),
    ("fa5b.twitter", "Grok", "#1da1f2"),
    ("fa5s.robot", "Manus", "#7c3aed"),
    ("fa5b.facebook-f", "Meta AI", "#1877f2"),
    ("fa5s.code", "Trae.ai", "#7c3aed"),
    ("fa5s.wind", "Windsurf", "#00a6ff"),
    ("fa5b.tiktok", "TikTok", "#ff0050"),
    ("fa5b.spotify", "Spotify", "#1db954"),
    ("fa5b.twitch", "Twitch", "#9146ff"),
    ("fa5s.sticky-note", "Notion", "#ffffff"),
    ("fa5s.language", "DeepL", "#0f2b46"),
    ("fa5s.palette", "Canva", "#00c4cc"),
    ("fa5s.microphone-alt", "ElevenLabs", "#ffffff"),
    ("fa5s.code", "JetBrains", "#fe315d"),
    ("fa5b.discord", "Discord", "#5865f2"),
    ("fa5b.youtube", "YouTube (иногда может не работать с ним! Отключите тумблер если YouTube не работает с пресетами)", "#ff0000"),
    ("fa5b.github", "GitHub", "#181717"),
    ("fa5b.whatsapp", "WhatsApp (работает обход если есть IPv6)", "#25d366"),
    ("fa5b.twitter", "x.com / Twitter", "#1da1f2"),
    ("fa5s.magnet", "Rutor", "#e74c3c"),
    ("fa5s.network-wired", "ntc.party (включить обход по IPv4)", "#3498db"),
    ("fa5b.discord", "Решение от Flowseal для стабильной работы голосовых серверов в Discord", "#5865f2"),
    ("fa5s.gamepad", "Supercell", "#f4b400"),
    ("fa5b.instagram", "Instagram", "#e4405f"),
    ("fa5s.box-open", "Остальное", "#6c757d"),
]
