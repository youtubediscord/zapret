"""Парсер hosts.ini — каталога публичных DNS/прокси-профилей.

hosts.ini содержит список общедоступных DNS/прокси-серверов и сопоставление
«домен → IP прокси» для сервисов, геозаблокированных из России (ChatGPT,
Spotify, AMD, Autodesk и др.).  Эти сервисы блокируют российские IP
самостоятельно (GeoIP), а не по решению РКН — DPI/zapret тут не поможет.

Механизм работы:
  1. Пользователь выбирает DNS-профиль (Zapret DNS, XBOX DNS, Comss DNS и т.д.)
  2. Приложение прописывает в системный hosts IP выбранного ПУБЛИЧНОГО
     прокси-сервера для каждого домена
  3. Браузер подключается к прокси-IP (TLS, SNI = домен), прокси проксирует
     запрос к реальному серверу от нероссийского IP

IP-адреса в hosts.ini принадлежат публичным прокси-серверам сообщества,
а НЕ автору приложения.  Весь код парсинга — в этом файле, открыт для аудита.
"""

from __future__ import annotations

import os
import sys
import re
import ipaddress
import configparser
import threading
from dataclasses import dataclass
from pathlib import Path

from safe_construct import safe_construct


class _CaseConfigParser(configparser.ConfigParser):
    """ConfigParser that preserves option key casing."""

    def optionxform(self, optionstr: str) -> str:  # type: ignore[override]
        return optionstr

def _log(msg: str, level: str = "INFO") -> None:
    """Отложенный импорт log (PyQt6) чтобы модуль можно было импортировать без GUI."""
    try:
        from log import log as _log_impl  # type: ignore
        _log_impl(msg, level)
    except Exception:
        print(f"[{level}] {msg}")


@dataclass(frozen=True)
class HostsCatalog:
    dns_profiles: list[str]
    services: dict[str, dict[str, list[str]]]
    service_entries: dict[str, list[tuple[str, list[str]]]]
    service_order: list[str]
    service_modes: dict[str, str]


_SERVICE_MODE_DNS = "dns"
_SERVICE_MODE_DIRECT = "direct"

_SERVICE_MODE_SECTIONS = {
    _SERVICE_MODE_DNS: {
        "services_dns",
        "dns_services",
    },
    _SERVICE_MODE_DIRECT: {
        "services_direct",
        "direct_services",
    },
}


_SPECIAL_SECTIONS = {
    "dns",
    # meta sections from older formats (must not be treated as services)
    "static",
    "profiles",
    "selectedprofiles",
    "selectedstatic",
    # managed IPv6 metadata sections
    "__ipv6_status__",
    "__ipv6_dns_providers__",
    *_SERVICE_MODE_SECTIONS[_SERVICE_MODE_DNS],
    *_SERVICE_MODE_SECTIONS[_SERVICE_MODE_DIRECT],
}

_MISSING_IP_MARKERS = {
    "-",
    "—",
    "none",
    "null",
    "off",
    "disabled",
    "откл",
    "откл.",
}

_CACHE_LOCK = threading.RLock()
_CACHE: HostsCatalog | None = None
_CACHE_TEXT: str | None = None
_CACHE_SIG: tuple[int, int] | None = None  # (mtime_ns, size)
_CACHE_PATH: Path | None = None
_MISSING_CATALOG_LOGGED: bool = False

_IPV6_MANAGED_BEGIN = "# >>> zapretgui:ipv6 managed begin >>>"
_IPV6_MANAGED_END = "# <<< zapretgui:ipv6 managed end <<<"
_IPV6_STATUS_SECTION = "__ipv6_status__"
_IPV6_PROVIDERS_SECTION = "__ipv6_dns_providers__"
_IPV6_MANAGED_RE = re.compile(
    re.escape(_IPV6_MANAGED_BEGIN) + r".*?" + re.escape(_IPV6_MANAGED_END),
    flags=re.DOTALL,
)


def _get_app_root() -> Path:
    """
    Возвращает корень приложения для поиска внешних файлов.

    - В source-режиме: корень репозитория (рядом с папкой `hosts/`).
    - В exe-сборке (PyInstaller frozen): папка, где лежит exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # hosts/proxy_domains.py -> hosts/ -> project root
    return Path(__file__).resolve().parent.parent


def _get_catalog_hosts_ini_candidates() -> list[Path]:
    """
    Каталог доменов/профилей (без настроек пользователя).

    Канонический путь: `<app_root>/json/hosts.ini`:
    - source: `<repo>/json/hosts.ini`
    - exe: `<exe_dir>/json/hosts.ini`
    """
    root = _get_app_root()

    return [
        root / "json" / "hosts.ini",
    ]


def _get_catalog_hosts_ini_path() -> Path:
    candidates = _get_catalog_hosts_ini_candidates()
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _get_user_hosts_ini_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "zapret" / "user_hosts.ini"
    return Path.home() / ".config" / "zapret" / "user_hosts.ini"


def _parse_bool(value: str) -> bool:
    v = (value or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on", "enabled", "enable")


def get_hosts_catalog_ini_path() -> Path:
    return _get_catalog_hosts_ini_path()


def get_user_hosts_ini_path() -> Path:
    return _get_user_hosts_ini_path()


def _check_ipv6_connectivity() -> bool:
    """Проверяет доступность IPv6 через DNSForceManager (ленивый импорт)."""
    try:
        from dns.dns_force import DNSForceManager  # type: ignore
    except Exception:
        return False

    try:
        return bool(DNSForceManager.check_ipv6_connectivity())
    except Exception:
        return False


def _collect_provider_ipv6_entries() -> list[tuple[str, str]]:
    """Возвращает список (ключ, IPv6-адреса) из DNS_PROVIDERS."""
    try:
        from dns.dns_providers import DNS_PROVIDERS  # type: ignore
    except Exception as e:
        _log(f"Не удалось импортировать DNS_PROVIDERS для IPv6 секций: {e}", "DEBUG")
        return []

    entries: list[tuple[str, str]] = []
    for category, providers in (DNS_PROVIDERS or {}).items():
        if not isinstance(providers, dict):
            continue

        for provider_name, data in providers.items():
            if not isinstance(data, dict):
                continue

            raw_ipv6 = data.get("ipv6", [])
            if isinstance(raw_ipv6, str):
                ipv6_values = [x.strip() for x in raw_ipv6.replace(",", " ").split() if x.strip()]
            elif isinstance(raw_ipv6, list):
                ipv6_values = [str(x).strip() for x in raw_ipv6 if str(x).strip()]
            else:
                ipv6_values = []

            if not ipv6_values:
                continue

            key = f"{(category or '').strip()} / {(provider_name or '').strip()}"
            entries.append((key, ", ".join(ipv6_values)))

    return entries


def _build_ipv6_managed_block() -> str:
    entries = _collect_provider_ipv6_entries()
    lines: list[str] = [
        _IPV6_MANAGED_BEGIN,
        f"[{_IPV6_STATUS_SECTION}]",
        "enabled = 1",
        "source = provider_ipv6_probe",
        "",
        f"[{_IPV6_PROVIDERS_SECTION}]",
    ]

    if entries:
        for key, value in entries:
            lines.append(f"{key} = {value}")
    else:
        lines.append("providers = none")

    lines.append(_IPV6_MANAGED_END)
    return "\n".join(lines)


def _upsert_ipv6_managed_block(text: str) -> tuple[str, bool]:
    source = text or ""
    block = _build_ipv6_managed_block()

    if _IPV6_MANAGED_BEGIN in source and _IPV6_MANAGED_END in source:
        updated = _IPV6_MANAGED_RE.sub(block, source, count=1)
        return updated, updated != source

    stripped = source.rstrip()
    if stripped:
        updated = f"{stripped}\n\n{block}\n"
    else:
        updated = f"{block}\n"

    return updated, updated != source


def ensure_ipv6_catalog_sections_if_available() -> tuple[bool, bool]:
    """
    Если у провайдера доступен IPv6, гарантирует наличие managed IPv6 секций
    в каталоге `./json/hosts.ini`.

    Returns:
        (changed, ipv6_available)
    """
    ipv6_available = _check_ipv6_connectivity()
    if not ipv6_available:
        return (False, False)

    path = _get_catalog_hosts_ini_path()
    if not path.exists():
        _log(f"IPv6 секции hosts.ini не добавлены: файл не найден ({path})", "DEBUG")
        return (False, True)

    try:
        current = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        _log(f"Не удалось прочитать hosts.ini для обновления IPv6 секций: {e}", "WARNING")
        return (False, True)

    updated, changed = _upsert_ipv6_managed_block(current)
    if not changed:
        return (False, True)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    except Exception as e:
        _log(f"Не удалось обновить IPv6 секции в hosts.ini: {e}", "WARNING")
        return (False, True)

    invalidate_hosts_catalog_cache()
    _log(f"hosts.ini обновлен: добавлены managed IPv6 секции ({path})", "INFO")
    return (True, True)


def _parse_hosts_ini(text: str) -> HostsCatalog:
    dns_profiles: list[str] = []
    services: dict[str, dict[str, list[str]]] = {}
    service_entries: dict[str, list[tuple[str, list[str]]]] = {}
    service_order: list[str] = []
    service_modes: dict[str, str] = {}

    current_section: str | None = None
    current_mode_scope: str | None = None
    pending_domain: str | None = None
    pending_ips: list[str] = []
    # Named-profile format: maps profile_index → ip (set when "ProfileName: IP" lines are used).
    pending_named: dict[int, str] = {}

    def normalize_service_key(service_name: str) -> str:
        return (service_name or "").strip().casefold()

    def set_service_mode(service_name: str, mode: str | None) -> None:
        if mode not in (_SERVICE_MODE_DNS, _SERVICE_MODE_DIRECT):
            return
        key = normalize_service_key(service_name)
        if not key:
            return
        service_modes[key] = mode

    def ensure_service(service_name: str) -> None:
        if service_name not in services:
            services[service_name] = {}
            service_entries[service_name] = []
            service_order.append(service_name)

    def append_service_entry(service_name: str, domain: str, ips: list[str]) -> None:
        ensure_service(service_name)
        service_entries[service_name].append((domain, ips))
        services[service_name][domain] = ips

    def _build_ips() -> list[str]:
        """Resolve pending domain's IPs. Named format wins over positional."""
        if pending_named:
            ips = [""] * len(dns_profiles)
            for idx, ip in pending_named.items():
                if 0 <= idx < len(ips):
                    ips[idx] = ip
            return ips
        return list(pending_ips)

    def flush_domain() -> None:
        nonlocal pending_domain, pending_ips, pending_named
        if not current_section:
            pending_domain = None
            pending_ips = []
            pending_named = {}
            return

        sec = current_section.strip()
        if not sec or sec.lower() in _SPECIAL_SECTIONS:
            pending_domain = None
            pending_ips = []
            pending_named = {}
            return

        if pending_domain:
            ips = _build_ips()
            append_service_entry(sec, pending_domain, ips)
            if current_mode_scope:
                set_service_mode(sec, current_mode_scope)
        pending_domain = None
        pending_ips = []
        pending_named = {}

    def flush_section() -> None:
        flush_domain()

    for raw in (text or "").splitlines():
        line = raw.strip()

        # Comments / empty
        if not line or line.startswith("#"):
            # Empty line ends current domain block in service sections.
            if current_section and current_section.strip().lower() not in _SPECIAL_SECTIONS:
                flush_domain()
            continue

        # Section header
        if line.startswith("[") and line.endswith("]"):
            flush_section()
            current_section = line[1:-1].strip()
            sec_norm = current_section.lower()
            if sec_norm in _SERVICE_MODE_SECTIONS[_SERVICE_MODE_DNS]:
                current_mode_scope = _SERVICE_MODE_DNS
            elif sec_norm in _SERVICE_MODE_SECTIONS[_SERVICE_MODE_DIRECT]:
                current_mode_scope = _SERVICE_MODE_DIRECT
            elif sec_norm == "dns":
                current_mode_scope = None
            continue

        if not current_section:
            continue

        sec_norm = current_section.strip().lower()
        if sec_norm == "dns":
            dns_profiles.append(line)
            continue

        # Optional service-mode sections:
        # [SERVICES_DNS] / [SERVICES_DIRECT]
        # - may be used as markers (scope for following service sections)
        # - may contain explicit service names (one per line)
        if sec_norm in _SERVICE_MODE_SECTIONS[_SERVICE_MODE_DNS]:
            set_service_mode(line, _SERVICE_MODE_DNS)
            continue

        if sec_norm in _SERVICE_MODE_SECTIONS[_SERVICE_MODE_DIRECT]:
            set_service_mode(line, _SERVICE_MODE_DIRECT)
            continue

        # Service section: support three formats:
        #
        # 1) Named-profile format (NEW – only 2–3 providers needed):
        #    domain.tld
        #    Zapret DNS: 82.22.36.11
        #    Comss DNS: 95.182.120.241
        #    (profiles not listed get empty string → unavailable in UI)
        #
        # 2) Catalog format (positional, backward-compat):
        #    domain.tld
        #    ip_for_profile_0
        #    ip_for_profile_1  (use "-" / "none" for unavailable)
        #
        # 3) Raw hosts lines:
        #    1.2.3.4 domain.tld

        # --- Named-profile detection (only when inside a domain block) ---
        if pending_domain is not None and dns_profiles:
            named_idx: int | None = None
            named_ip_val: str = ""
            for sep in (":", "="):
                if sep in line:
                    left, _, right = line.partition(sep)
                    left_s = left.strip()
                    right_s = right.strip()
                    for i, pname in enumerate(dns_profiles):
                        if left_s.lower() == pname.strip().lower():
                            named_idx = i
                            named_ip_val = "" if right_s.lower() in _MISSING_IP_MARKERS else right_s
                            break
                    if named_idx is not None:
                        break
            if named_idx is not None:
                pending_named[named_idx] = named_ip_val
                continue

        # --- Raw hosts lines: "IP domain.tld" (IPv4/IPv6) ---
        parts = line.split()
        if len(parts) >= 2:
            ip_candidate = parts[0].strip()
            host_candidate = parts[1].strip()
            is_ip = False
            try:
                ipaddress.ip_address(ip_candidate)
                is_ip = True
            except ValueError:
                is_ip = False

            if is_ip and host_candidate and not host_candidate.startswith("#"):
                # We are switching mode: raw hosts lines don't belong to the pending domain block.
                flush_domain()

                # Strict direct-only support: we only place the IP into the explicit "direct" profile column.
                direct_idx: int | None = None
                for i, profile_name in enumerate(dns_profiles):
                    if _is_direct_profile_name(profile_name):
                        direct_idx = i
                        break

                ips = [""] * len(dns_profiles)
                if direct_idx is not None and direct_idx < len(ips):
                    ips[direct_idx] = ip_candidate

                # Store raw-host entries under their section, so UI can toggle a whole group.
                sec = current_section.strip()
                if sec and sec.lower() not in _SPECIAL_SECTIONS:
                    append_service_entry(sec, host_candidate, ips)
                    if current_mode_scope:
                        set_service_mode(sec, current_mode_scope)
                continue

        # --- Positional format: domain line then N IP lines ---
        if pending_domain is None:
            pending_domain = line
            pending_ips = []
            pending_named = {}
        else:
            ip_value = line
            if ip_value.strip().lower() in _MISSING_IP_MARKERS:
                ip_value = ""
            pending_ips.append(ip_value)

    flush_section()

    return HostsCatalog(
        dns_profiles=dns_profiles,
        services=services,
        service_entries=service_entries,
        service_order=service_order,
        service_modes=service_modes,
    )


def _get_path_sig(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        mtime_ns = getattr(st, "st_mtime_ns", None)
        if mtime_ns is None:
            mtime_ns = int(st.st_mtime * 1_000_000_000)
        return (int(mtime_ns), int(st.st_size))
    except Exception:
        return None


def _select_catalog_path() -> tuple[Path, list[Path], bool]:
    candidates = _get_catalog_hosts_ini_candidates()
    existing = [p for p in candidates if p.exists()]
    if existing:
        return (existing[0], candidates, True)
    return (candidates[0], candidates, False)


def _load_catalog() -> HostsCatalog:
    global _CACHE, _CACHE_TEXT, _CACHE_SIG, _CACHE_PATH, _MISSING_CATALOG_LOGGED

    with _CACHE_LOCK:
        path, candidates, exists = _select_catalog_path()

        if not exists:
            if not _MISSING_CATALOG_LOGGED:
                _log(
                    "hosts.ini не найден. Ожидается внешний файл по одному из путей: "
                    + " | ".join(str(p) for p in candidates),
                    "WARNING",
                )
                _MISSING_CATALOG_LOGGED = True
        else:
            _MISSING_CATALOG_LOGGED = False

        sig = _get_path_sig(path) if path.exists() else None
        if (
            _CACHE is not None
            and _CACHE_PATH is not None
            and _CACHE_SIG is not None
            and sig is not None
            and _CACHE_PATH == path
            and _CACHE_SIG == sig
        ):
            return _CACHE

        try:
            text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        except Exception as e:
            _log(f"Не удалось прочитать hosts.ini: {e}", "WARNING")
            text = ""

        _CACHE_TEXT = text
        _CACHE = _parse_hosts_ini(text)
        _CACHE_SIG = sig
        _CACHE_PATH = path
        return _CACHE


def invalidate_hosts_catalog_cache() -> None:
    global _CACHE, _CACHE_TEXT, _CACHE_SIG, _CACHE_PATH
    with _CACHE_LOCK:
        _CACHE = None
        _CACHE_TEXT = None
        _CACHE_SIG = None
        _CACHE_PATH = None


def get_hosts_catalog_signature() -> tuple[str, int, int] | None:
    """
    Возвращает сигнатуру текущего каталога hosts.ini: (path, mtime_ns, size).
    None если файл отсутствует/не читается.
    """
    path, _candidates, _exists = _select_catalog_path()
    if not path.exists():
        return None
    sig = _get_path_sig(path)
    if sig is None:
        return None
    mtime_ns, size = sig
    return (str(path), mtime_ns, size)


def get_hosts_catalog_text() -> str:
    """Возвращает сырой текст каталога hosts.ini (с учётом кэша/инвалидции)."""
    _load_catalog()
    with _CACHE_LOCK:
        return _CACHE_TEXT or ""


def get_dns_profiles() -> list[str]:
    return list(_load_catalog().dns_profiles)


def get_all_services() -> list[str]:
    return list(_load_catalog().service_order)

def get_service_domain_names(service_name: str) -> list[str]:
    """Возвращает список доменов сервиса (без привязки к профилю)."""
    cat = _load_catalog()
    domains = cat.services.get(service_name, {}) or {}
    return list(domains.keys())


def get_service_domains(service_name: str) -> dict[str, str]:
    """Домены сервиса (IP по умолчанию = профиль 0)."""
    cat = _load_catalog()
    domains = cat.services.get(service_name, {}) or {}
    out: dict[str, str] = {}
    for domain, ips in domains.items():
        if ips and ips[0]:
            out[domain] = ips[0]
    return out


def get_service_domain_ip_rows(service_name: str, profile_name: str) -> list[tuple[str, str]]:
    """Возвращает список (domain, ip) для сервиса под выбранный профиль, сохраняя дубликаты домена."""
    cat = _load_catalog()
    if profile_name not in cat.dns_profiles:
        return []
    profile_index = cat.dns_profiles.index(profile_name)

    entries = cat.service_entries.get(service_name, []) or []
    out: list[tuple[str, str]] = []
    for domain, ips in entries:
        if not ips or profile_index >= len(ips) or not ips[profile_index]:
            return []
        out.append((domain, ips[profile_index]))
    return out


def get_service_available_dns_profiles(service_name: str) -> list[str]:
    """
    Возвращает список DNS-профилей, доступных для сервиса.

    Профиль доступен если ДЛЯ КАЖДОГО домена сервиса есть IP на этом индексе.
    """
    cat = _load_catalog()
    domains = cat.services.get(service_name, {}) or {}
    if not domains:
        return []

    available: list[str] = []
    for profile_index, profile_name in enumerate(cat.dns_profiles):
        ok = True
        for ips in domains.values():
            if not ips or profile_index >= len(ips) or not ips[profile_index]:
                ok = False
                break
        if ok:
            available.append(profile_name)
    return available


def _is_direct_profile_name(profile_name: str) -> bool:
    name = (profile_name or "").strip().lower()
    if not name:
        return False
    return (
        "вкл. (активировать hosts)" in name
        or "no proxy" in name
        or "direct" in name
    )


def _infer_direct_profile_index(cat: HostsCatalog) -> int | None:
    # First try: by name (stable for user renames of other profiles).
    for i, profile_name in enumerate(cat.dns_profiles):
        if _is_direct_profile_name(profile_name):
            return i

    # Fallback: choose profile column with the most distinct IPs across the whole catalog.
    if not cat.dns_profiles:
        return None

    distinct: list[set[str]] = [set() for _ in cat.dns_profiles]
    for domains in (cat.services or {}).values():
        for ips in (domains or {}).values():
            for idx, ip in enumerate((ips or [])[: len(distinct)]):
                ip = (ip or "").strip()
                if ip:
                    distinct[idx].add(ip)

    best_idx = 0
    best_count = -1
    for idx, values in enumerate(distinct):
        if len(values) > best_count:
            best_count = len(values)
            best_idx = idx
    return best_idx


def _get_proxy_profile_indices(cat: HostsCatalog) -> list[int]:
    direct_idx = _infer_direct_profile_index(cat)
    if direct_idx is None:
        return list(range(len(cat.dns_profiles)))
    return [i for i in range(len(cat.dns_profiles)) if i != direct_idx]


def _get_declared_service_mode(cat: HostsCatalog, service_name: str) -> str | None:
    key = (service_name or "").strip().casefold()
    if not key:
        return None
    return (cat.service_modes or {}).get(key)


def _service_has_proxy_ips(cat: HostsCatalog, service_name: str) -> bool:
    """
    True если у сервиса есть ХОТЯ БЫ ОДИН домен с IP в proxy/hide колонках.

    Proxy/hide колонки определяются автоматически (все профили кроме "direct"/"Вкл. (активировать hosts)").
    """
    declared_mode = _get_declared_service_mode(cat, service_name)
    if declared_mode == _SERVICE_MODE_DIRECT:
        return False
    if declared_mode == _SERVICE_MODE_DNS:
        return True

    domains = cat.services.get(service_name, {}) or {}
    if not domains:
        return False

    direct_idx = _infer_direct_profile_index(cat)
    proxy_indices = [i for i in range(len(cat.dns_profiles)) if direct_idx is None or i != direct_idx]
    if not proxy_indices:
        return False

    for ips in domains.values():
        direct_ip = ""
        if direct_idx is not None and ips and direct_idx < len(ips):
            direct_ip = (ips[direct_idx] or "").strip()
        for idx in proxy_indices:
            if not ips or idx >= len(ips):
                continue
            ip = (ips[idx] or "").strip()
            if not ip:
                continue
            # Do not treat copies of the "direct" column as proxy/hide IPs.
            if direct_ip and ip == direct_ip:
                continue
            return True
    return False


def get_service_has_geohide_ips(service_name: str) -> bool:
    """
    Back-compat API for UI: returns True if service has proxy/hide IPs.

    Note: historically this was tied to GeoHide DNS naming, but now detection is name-agnostic
    to support user-renamed DNS profile titles. Explicit mode sections in hosts.ini
    ([SERVICES_DNS]/[SERVICES_DIRECT]) have priority over inferred detection.
    """
    return _service_has_proxy_ips(_load_catalog(), service_name)


def get_service_domain_ip_map(service_name: str, profile_name: str) -> dict[str, str]:
    """Возвращает {domain: ip} для сервиса под выбранный профиль, или {} если профиль неполный."""
    rows = get_service_domain_ip_rows(service_name, profile_name)
    if not rows:
        return {}

    out: dict[str, str] = {}
    for domain, ip in rows:
        out[domain] = ip
    return out


def load_user_hosts_selection() -> dict[str, str]:
    """
    Возвращает выбор пользователя: {service_name: profile_name}.

    Хранится отдельно от каталога доменов в `%APPDATA%/zapret/user_hosts.ini`.
    """
    user_path = get_user_hosts_ini_path()
    path = user_path
    migrate_to_new_path = False

    if not user_path.exists():
        # Back-compat: earlier builds could store the selection in `%APPDATA%/zapret/hosts.ini`.
        legacy_path = user_path.with_name("hosts.ini")
        if legacy_path.exists():
            try:
                with legacy_path.open("r", encoding="utf-8", errors="replace") as f:
                    sample = f.read(64 * 1024).lower()
                if "[profiles]" in sample or "[selectedprofiles]" in sample:
                    path = legacy_path
                    migrate_to_new_path = True
            except Exception:
                pass

    if not path.exists():
        return {}

    try:
        parser = safe_construct(_CaseConfigParser, strict=False)
        parser.read(path, encoding="utf-8")
    except Exception as e:
        _log(f"Не удалось прочитать user_hosts.ini: {e}", "WARNING")
        return {}

    section = None
    if parser.has_section("profiles"):
        section = "profiles"
    elif parser.has_section("SelectedProfiles"):
        # compatibility
        section = "SelectedProfiles"

    if not section:
        return {}

    out: dict[str, str] = {}
    for service_name, profile_name in parser.items(section):
        service_name = (service_name or "").strip()
        profile_name = (profile_name or "").strip()
        if service_name and profile_name:
            out[service_name] = profile_name

    if migrate_to_new_path and out:
        save_user_hosts_selection(out)
    return out


def save_user_hosts_selection(selected_profiles: dict[str, str]) -> bool:
    """Сохраняет выбор пользователя в `%APPDATA%/zapret/user_hosts.ini`."""
    path = get_user_hosts_ini_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = safe_construct(_CaseConfigParser)
        parser["profiles"] = {}

        for service_name in sorted((selected_profiles or {}).keys(), key=lambda s: s.lower()):
            profile_name = (selected_profiles.get(service_name) or "").strip()
            service_name = (service_name or "").strip()
            if service_name and profile_name:
                parser["profiles"][service_name] = profile_name

        with path.open("w", encoding="utf-8") as f:
            f.write("# Zapret GUI: hosts selection\n")
            parser.write(f)
        return True
    except Exception as e:
        _log(f"Не удалось сохранить user_hosts.ini: {e}", "WARNING")
        return False


# ═══════════════════════════════════════════════════════════════
# UI hints (иконки/цвета) — без доменов и IP
# Формат: (иконка_qtawesome, название, цвет_иконки)
# ═══════════════════════════════════════════════════════════════

QUICK_SERVICES = [
    # AI сервисы
    ("fa5b.discord", "Discord TCP", "#5865f2"),
    ("fa5b.youtube", "YouTube TCP", "#ff0000"),
    ("fa5b.github", "GitHub TCP", "#181717"),
    ("fa5b.discord", "Discord Voice", "#5865f2"),
    ("mdi.robot", "ChatGPT", "#10a37f"),
    ("mdi.google", "Gemini", "#4285f4"),
    ("mdi.google", "Gemini AI", "#4285f4"),
    ("fa5s.brain", "Claude", "#cc9b7a"),
    ("fa5b.microsoft", "Copilot", "#00bcf2"),
    ("fa5b.twitter", "Grok", "#1da1f2"),
    ("fa5s.robot", "Manus", "#7c3aed"),
    # Соцсети
    ("fa5b.instagram", "Instagram", "#e4405f"),
    ("fa5b.facebook-f", "Facebook", "#1877f2"),
    ("mdi.at", "Threads", "#ffffff"),
    ("fa5b.tiktok", "TikTok", "#ff0050"),
    # Медиа и развлечения
    ("fa5b.spotify", "Spotify", "#1db954"),
    ("fa5s.film", "Netflix", "#e50914"),
    ("fa5b.twitch", "Twitch", "#9146ff"),
    ("fa5b.soundcloud", "SoundCloud", "#ff5500"),
    # Продуктивность
    ("fa5s.sticky-note", "Notion", "#ffffff"),
    ("fa5s.language", "DeepL", "#0f2b46"),
    ("fa5s.palette", "Canva", "#00c4cc"),
    ("fa5s.envelope", "ProtonMail", "#6d4aff"),
    # Разработка
    ("fa5s.microphone-alt", "ElevenLabs", "#ffffff"),
    ("fa5b.github", "GitHub Copilot", "#ffffff"),
    ("fa5s.code", "JetBrains", "#fe315d"),
    ("fa5s.bolt", "Codeium", "#09b6a2"),
    # Торренты
    ("fa5s.magnet", "RuTracker", "#3498db"),
    ("fa5s.magnet", "Rutor", "#e74c3c"),
    # Другое
    ("fa5s.images", "Pixabay", "#00ab6c"),
    ("fa5s.box-open", "Другое", "#6c757d"),
]
