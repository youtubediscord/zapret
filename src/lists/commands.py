from __future__ import annotations

import os
import re
import subprocess
import threading
import ipaddress
from typing import Optional
from urllib.parse import urlparse

from log.log import log
from lists.core.paths import get_list_final_path, get_list_user_path, get_lists_dir
from lists.state import (
    CustomDomainsLoadState,
    CustomDomainsSaveState,
    CustomIpRuLoadState,
    CustomIpRuSaveState,
    CustomIpSetLoadState,
    CustomIpSetSaveState,
    CustomNetrogatLoadState,
    CustomNetrogatSaveState,
    HostlistActionResult,
    HostlistEntriesState,
    HostlistFolderInfo,
    ListsFolderCategoryInfo,
)

LISTS_FOLDER = get_lists_dir()
NETROGAT_PATH = get_list_final_path("netrogat")
OTHER_USER_PATH = get_list_user_path("other")

_FOLDER_INFO_CACHE_LOCK = threading.Lock()
_FOLDER_INFO_CACHE: dict[tuple[str, tuple[tuple[str, int, int], ...]], ListsFolderCategoryInfo] = {}
_LINE_COUNT_BUFFER_SIZE = 1024 * 1024


def split_domains(text: str) -> list[str]:
    parts = re.split(r"[\s,;]+", str(text or ""))
    result: list[str] = []

    for part in parts:
        part = part.strip().lower()
        if not part or part.startswith("#"):
            if part:
                result.append(part)
            continue
        result.extend(_split_glued_domains(part))

    return result


def _split_glued_domains(text: str) -> list[str]:
    if not text or len(text) < 5:
        return [text] if text else []

    valid_tld_pattern = (
        r"\.(com|ru|org|net|io|me|by|uk|de|fr|it|es|nl|pl|ua|kz|su|co|tv|cc|to|ai|gg|info|biz|xyz|dev|app|pro|online|store|cloud|shop|blog|tech|site|рф)$"
    )
    if re.search(valid_tld_pattern, text, re.IGNORECASE):
        glued_pattern = r"(\.(com|ru|org|net|io|me))([a-z]{2,}[a-z0-9-]*\.[a-z]{2,})$"
        match = re.search(glued_pattern, text, re.IGNORECASE)
        if match:
            end_of_first = match.start() + len(match.group(1))
            first_domain = text[:end_of_first]
            second_domain = match.group(3)
            return [first_domain, second_domain]
        return [text]

    return [text]


def extract_domain(text: str) -> Optional[str]:
    text = str(text or "").strip()

    marker = ""
    if text.startswith("^"):
        marker = "^"
        text = text[1:].strip()
        if not text:
            return None

    if text.startswith("."):
        text = text[1:]

    if "://" in text or text.startswith("www."):
        if not text.startswith(("http://", "https://")):
            text = "https://" + text
        try:
            parsed = urlparse(text)
            domain = parsed.netloc or parsed.path.split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            domain = domain.split(":")[0]
            if domain.startswith("."):
                domain = domain[1:]
            domain = domain.lower()
            return f"{marker}{domain}" if marker else domain
        except Exception:
            pass

    domain = text.split("/")[0].split(":")[0].lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain.startswith("."):
        domain = domain[1:]

    if re.match(r"^[a-z]{2,10}$", domain):
        return f"{marker}{domain}" if marker else domain

    if "." in domain and len(domain) > 3:
        if re.match(r"^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$", domain):
            return f"{marker}{domain}" if marker else domain

    return None


def _is_ipset_file_name(file_name: str) -> bool:
    lower = (file_name or "").lower()
    return lower.startswith("ipset-") or "ipset" in lower or "subnet" in lower


def _count_plain_lines_fast(path: str) -> int:
    total = 0
    has_data = False
    last_byte = b""

    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_LINE_COUNT_BUFFER_SIZE)
            if not chunk:
                break
            has_data = True
            total += chunk.count(b"\n")
            last_byte = chunk[-1:]

    if has_data and last_byte != b"\n":
        total += 1
    return total


def _count_effective_lines_fast(path: str) -> int:
    total = 0
    remainder = b""

    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_LINE_COUNT_BUFFER_SIZE)
            if not chunk:
                break

            data = remainder + chunk
            lines = data.split(b"\n")
            remainder = lines.pop() if lines else b""

            for raw_line in lines:
                stripped = raw_line.rstrip(b"\r").strip()
                if stripped and not stripped.startswith(b"#"):
                    total += 1

    if remainder:
        stripped = remainder.rstrip(b"\r").strip()
        if stripped and not stripped.startswith(b"#"):
            total += 1

    return total


def _count_lines_from_entries(
    entries: list[tuple[str, str, int, int]],
    *,
    max_files: int,
    skip_comments: bool,
) -> int:
    total = 0
    counter = (
        _count_effective_lines_fast
        if skip_comments
        else _count_plain_lines_fast
    )

    for _file_name, path, _mtime_ns, _size in entries[:max_files]:
        try:
            total += counter(path)
        except Exception:
            continue
    return total


def _scan_lists_folder() -> tuple[bool, list[tuple[str, str, int, int]], list[tuple[str, str, int, int]]]:
    if not os.path.isdir(LISTS_FOLDER):
        return False, [], []

    hostlist_files: list[tuple[str, str, int, int]] = []
    ipset_files: list[tuple[str, str, int, int]] = []

    try:
        with os.scandir(LISTS_FOLDER) as entries:
            for entry in entries:
                try:
                    if not entry.is_file():
                        continue
                except OSError:
                    continue

                file_name = entry.name
                if not file_name.lower().endswith(".txt"):
                    continue

                try:
                    stat = entry.stat()
                except OSError:
                    continue

                item = (
                    file_name,
                    entry.path,
                    int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
                    int(stat.st_size),
                )

                if _is_ipset_file_name(file_name):
                    ipset_files.append(item)
                else:
                    hostlist_files.append(item)
    except OSError:
        return False, [], []

    hostlist_files.sort(key=lambda item: item[0].lower())
    ipset_files.sort(key=lambda item: item[0].lower())
    return True, hostlist_files, ipset_files


def _build_lists_folder_category_info(category: str) -> ListsFolderCategoryInfo:
    folder_exists, hostlist_files, ipset_files = _scan_lists_folder()
    if not folder_exists:
        return ListsFolderCategoryInfo(False, 0, 0, LISTS_FOLDER, category)

    normalized_category = (category or "").strip().lower()
    if normalized_category == "ipset":
        entries = ipset_files
        skip_comments = True
    else:
        normalized_category = "hostlist"
        entries = hostlist_files
        skip_comments = False

    signature = tuple((name.lower(), mtime_ns, size) for name, _path, mtime_ns, size in entries)
    cache_key = (normalized_category, signature)

    with _FOLDER_INFO_CACHE_LOCK:
        cached = _FOLDER_INFO_CACHE.get(cache_key)
    if cached is not None:
        return cached

    info = ListsFolderCategoryInfo(
        folder_exists=True,
        files_count=len(entries),
        lines_count=_count_lines_from_entries(
            entries,
            max_files=12,
            skip_comments=skip_comments,
        ),
        folder=LISTS_FOLDER,
        category=normalized_category,
    )

    with _FOLDER_INFO_CACHE_LOCK:
        _FOLDER_INFO_CACHE[cache_key] = info
        if len(_FOLDER_INFO_CACHE) > 8:
            keys = list(_FOLDER_INFO_CACHE.keys())[-8:]
            _FOLDER_INFO_CACHE = {
                key: _FOLDER_INFO_CACHE[key]
                for key in keys
            }
    return info


def load_hostlist_folder_info() -> ListsFolderCategoryInfo:
    return _build_lists_folder_category_info("hostlist")


def load_ipset_folder_info() -> ListsFolderCategoryInfo:
    return _build_lists_folder_category_info("ipset")


def load_folder_info() -> HostlistFolderInfo:
    hostlist_info = load_hostlist_folder_info()
    ipset_info = load_ipset_folder_info()

    return HostlistFolderInfo(
        folder_exists=hostlist_info.folder_exists and ipset_info.folder_exists,
        hostlist_files_count=hostlist_info.files_count,
        ipset_files_count=ipset_info.files_count,
        hostlist_lines=hostlist_info.lines_count,
        ipset_lines=ipset_info.lines_count,
        folder=LISTS_FOLDER,
    )


def open_lists_folder() -> None:
    os.startfile(LISTS_FOLDER)


def rebuild_hostlists() -> None:
    from lists.hostlists_manager import startup_hostlists_check

    startup_hostlists_check()


def startup_lists_check() -> tuple[bool, bool]:
    from lists.hostlists_manager import startup_hostlists_check
    from lists.ipsets_manager import startup_ipsets_check

    return bool(startup_hostlists_check()), bool(startup_ipsets_check())


def load_domains_entries() -> HostlistEntriesState:
    from lists.hostlists_manager import ensure_hostlists_exist

    ensure_hostlists_exist()
    entries: list[str] = []
    if os.path.exists(OTHER_USER_PATH):
        with open(OTHER_USER_PATH, "r", encoding="utf-8") as fh:
            entries = [line.strip() for line in fh if line.strip()]
    return HostlistEntriesState(entries=entries)


def load_custom_domains_text() -> CustomDomainsLoadState:
    from lists.hostlists_manager import ensure_hostlists_exist

    ensure_hostlists_exist()
    lines: list[str] = []
    if os.path.exists(OTHER_USER_PATH):
        with open(OTHER_USER_PATH, "r", encoding="utf-8") as fh:
            lines = [line.strip() for line in fh if line.strip()]
    return CustomDomainsLoadState(text="\n".join(lines), lines_count=len(lines))


def save_domains_entries(entries: list[str]) -> bool:
    from lists.hostlists_manager import rebuild_other_files

    os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
    with open(OTHER_USER_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(entries) + ("\n" if entries else ""))
    try:
        rebuild_other_files()
    except Exception:
        pass
    return True


def save_custom_domains_text(text: str) -> CustomDomainsSaveState:
    from lists.hostlists_manager import rebuild_other_files

    os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)

    saved_lines: list[str] = []
    normalized_lines: list[str] = []

    for raw_line in str(text or "").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            saved_lines.append(line)
            normalized_lines.append(line)
            continue

        for item in split_domains(line):
            domain = extract_domain(item)
            if domain:
                if domain not in saved_lines:
                    saved_lines.append(domain)
                    normalized_lines.append(domain)
            else:
                normalized_lines.append(item)

    with open(OTHER_USER_PATH, "w", encoding="utf-8") as fh:
        for item in saved_lines:
            fh.write(f"{item}\n")

    try:
        rebuild_other_files()
    except Exception:
        pass

    return CustomDomainsSaveState(
        normalized_text="\n".join(normalized_lines),
        saved_lines=saved_lines,
        saved_count=len(saved_lines),
    )


def get_custom_domains_base_set() -> set[str]:
    try:
        from lists.hostlists_manager import get_base_domains_set

        return get_base_domains_set()
    except Exception:
        return set()


def split_ip_entries(text: str) -> list[str]:
    parts = re.split(r"[\s,;]+", str(text or ""))
    return [part.strip() for part in parts if part.strip()]


def normalize_ipset_entry(text: str) -> str | None:
    line = str(text or "").strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        try:
            parsed = urlparse(line)
            host = parsed.netloc or parsed.path.split("/")[0]
            host = host.split(":")[0]
            line = host
        except Exception:
            pass

    if "-" in line:
        return None

    if "/" in line:
        try:
            net = ipaddress.ip_network(line, strict=False)
            return net.with_prefixlen
        except Exception:
            return None

    try:
        addr = ipaddress.ip_address(line)
        return str(addr)
    except Exception:
        return None


def get_custom_ipset_base_set() -> set[str]:
    try:
        from lists.ipsets_manager import get_ipset_all_base_set

        return get_ipset_all_base_set()
    except Exception:
        return set()


def load_custom_ipset_text() -> CustomIpSetLoadState:
    from lists.ipsets_manager import ensure_ipset_all_user_file

    ensure_ipset_all_user_file()
    state = load_ipset_all_entries()
    return CustomIpSetLoadState(
        text="\n".join(state.entries),
        lines_count=len(state.entries),
        base_set=set(state.base_set or set()),
    )


def save_custom_ipset_text(text: str) -> CustomIpSetSaveState:
    entries: list[str] = []
    normalized_lines: list[str] = []

    for raw_line in str(text or "").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            entries.append(line)
            normalized_lines.append(line)
            continue

        for item in split_ip_entries(line):
            norm = normalize_ipset_entry(item)
            if norm:
                if norm not in entries:
                    entries.append(norm)
                    normalized_lines.append(norm)
            else:
                normalized_lines.append(item)

    save_ipset_all_entries(entries)
    return CustomIpSetSaveState(
        normalized_text="\n".join(normalized_lines),
        saved_lines=entries,
        saved_count=len(entries),
    )


def get_custom_ipru_base_set() -> set[str]:
    try:
        from lists.ipsets_manager import get_ipset_ru_base_set

        return get_ipset_ru_base_set()
    except Exception:
        return set()


def load_custom_ipru_text() -> CustomIpRuLoadState:
    state = load_ipset_ru_entries()
    return CustomIpRuLoadState(
        text="\n".join(state.entries),
        lines_count=len(state.entries),
        base_set=set(state.base_set or set()),
    )


def save_custom_ipru_text(text: str) -> CustomIpRuSaveState:
    entries: list[str] = []
    normalized_lines: list[str] = []

    for raw_line in str(text or "").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            entries.append(line)
            normalized_lines.append(line)
            continue

        for item in split_ip_entries(line):
            norm = normalize_ipset_entry(item)
            if norm:
                if norm not in entries:
                    entries.append(norm)
                    normalized_lines.append(norm)
            else:
                normalized_lines.append(item)

    save_ipset_ru_entries(entries)
    return CustomIpRuSaveState(
        normalized_text="\n".join(normalized_lines),
        saved_lines=entries,
        saved_count=len(entries),
    )


def load_custom_netrogat_text() -> CustomNetrogatLoadState:
    state = load_netrogat_entries()
    return CustomNetrogatLoadState(
        text="\n".join(state.entries),
        lines_count=len(state.entries),
        base_set=set(state.base_set or set()),
    )


def save_custom_netrogat_text(text: str) -> CustomNetrogatSaveState:
    from lists.netrogat_manager import _normalize_domain

    domains: list[str] = []
    normalized_lines: list[str] = []

    for raw_line in str(text or "").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            domains.append(line)
            normalized_lines.append(line)
            continue

        for item in split_domains(line):
            norm = _normalize_domain(item)
            if norm:
                if norm not in domains:
                    domains.append(norm)
                    normalized_lines.append(norm)
            else:
                normalized_lines.append(item)

    success = save_netrogat_entries(domains)
    return CustomNetrogatSaveState(
        success=bool(success),
        normalized_text="\n".join(normalized_lines),
        saved_lines=domains,
        saved_count=len(domains),
    )


def get_netrogat_base_set() -> set[str]:
    try:
        from lists.netrogat_manager import get_netrogat_base_set

        return get_netrogat_base_set()
    except Exception:
        return set()


def normalize_netrogat_domain(text: str) -> str | None:
    from lists.netrogat_manager import _normalize_domain

    return _normalize_domain(text)


def open_domains_user_file() -> None:
    from lists.hostlists_manager import ensure_hostlists_exist

    ensure_hostlists_exist()
    if os.path.exists(OTHER_USER_PATH):
        subprocess.run(["explorer", "/select,", OTHER_USER_PATH])
    else:
        os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
        subprocess.run(["explorer", os.path.dirname(OTHER_USER_PATH)])


def reset_domains_file() -> bool:
    from lists.hostlists_manager import reset_other_user_file

    return bool(reset_other_user_file())


def load_ipset_all_entries() -> HostlistEntriesState:
    from lists.ipsets_manager import (
        IPSET_ALL_USER_PATH,
        ensure_ipset_all_user_file,
        get_ipset_all_base_set,
    )

    ensure_ipset_all_user_file()
    entries: list[str] = []
    if os.path.exists(IPSET_ALL_USER_PATH):
        with open(IPSET_ALL_USER_PATH, "r", encoding="utf-8") as fh:
            entries = [line.strip() for line in fh if line.strip()]
    return HostlistEntriesState(entries=entries, base_set=get_ipset_all_base_set())


def save_ipset_all_entries(entries: list[str]) -> bool:
    from lists.ipsets_manager import IPSET_ALL_USER_PATH, sync_ipset_all_after_user_change

    os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
    with open(IPSET_ALL_USER_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(entries) + ("\n" if entries else ""))
    return bool(sync_ipset_all_after_user_change())


def open_ipset_all_user_file() -> None:
    from lists.ipsets_manager import IPSET_ALL_USER_PATH, ensure_ipset_all_user_file

    ensure_ipset_all_user_file()
    if os.path.exists(IPSET_ALL_USER_PATH):
        subprocess.run(["explorer", "/select,", IPSET_ALL_USER_PATH])
    else:
        os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
        subprocess.run(["explorer", os.path.dirname(IPSET_ALL_USER_PATH)])


def load_netrogat_entries() -> HostlistEntriesState:
    from lists.netrogat_manager import ensure_netrogat_user_file, get_netrogat_base_set, load_netrogat

    ensure_netrogat_user_file()
    return HostlistEntriesState(entries=load_netrogat(), base_set=get_netrogat_base_set())


def save_netrogat_entries(domains: list[str]) -> bool:
    from lists.netrogat_manager import save_netrogat

    return bool(save_netrogat(domains))


def open_netrogat_user_file() -> None:
    from lists.netrogat_manager import NETROGAT_USER_PATH, ensure_netrogat_user_file

    ensure_netrogat_user_file()
    if NETROGAT_USER_PATH and os.path.exists(NETROGAT_USER_PATH):
        subprocess.run(["explorer", "/select,", NETROGAT_USER_PATH])
    else:
        subprocess.run(["explorer", LISTS_FOLDER])


def open_netrogat_final_file() -> None:
    from lists.netrogat_manager import ensure_netrogat_exists

    ensure_netrogat_exists()
    if NETROGAT_PATH and os.path.exists(NETROGAT_PATH):
        subprocess.run(["explorer", "/select,", NETROGAT_PATH])
    else:
        subprocess.run(["explorer", LISTS_FOLDER])


def add_missing_netrogat_defaults() -> int:
    from lists.netrogat_manager import ensure_netrogat_base_defaults

    return int(ensure_netrogat_base_defaults())


def open_lists_folder_action() -> HostlistActionResult:
    try:
        open_lists_folder()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыта папка листов",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия папки: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть папку:\n{e}",
        )


def rebuild_hostlists_action() -> HostlistActionResult:
    try:
        rebuild_hostlists()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Хостлисты обновлены",
            infobar_level="success",
            infobar_title="Готово",
            infobar_content="Хостлисты обновлены",
            reload_info=True,
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка перестроения: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось перестроить:\n{e}",
        )


def open_domains_user_file_action() -> HostlistActionResult:
    try:
        open_domains_user_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт пользовательский список доменов (lists/user/other.txt)",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия файла: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть:\n{e}",
        )


def reset_domains_file_action() -> HostlistActionResult:
    try:
        if reset_domains_file():
            return HostlistActionResult(
                ok=True,
                log_level="INFO",
                log_message="Сброшен пользовательский список доменов",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                reload_domains=True,
                append_domains_status_suffix=" • ✅ Сброшено",
            )
        return HostlistActionResult(
            ok=False,
            log_level="WARNING",
            log_message="Не удалось сбросить my hostlist",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content="Не удалось сбросить my hostlist",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка сброса hostlist: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось сбросить:\n{e}",
        )


def open_ipset_all_user_file_action() -> HostlistActionResult:
    try:
        open_ipset_all_user_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт пользовательский IP-список (lists/user/ipset-all.txt)",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия пользовательского IP-списка: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть:\n{e}",
        )


def open_netrogat_user_file_action() -> HostlistActionResult:
    try:
        open_netrogat_user_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт пользовательский список исключений доменов (lists/user/netrogat.txt)",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия пользовательского списка исключений доменов: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть:\n{e}",
        )


def open_netrogat_final_file_action() -> HostlistActionResult:
    try:
        open_netrogat_final_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт итоговый файл netrogat.txt",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия итогового netrogat.txt: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть итоговый файл: {e}",
        )


def add_missing_netrogat_defaults_action() -> HostlistActionResult:
    added = add_missing_netrogat_defaults()
    if added == 0:
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Системная база уже содержит все домены по умолчанию",
            infobar_level="success",
            infobar_title="Готово",
            infobar_content="Системная база уже содержит все домены по умолчанию.",
            invalidate_excl_base_cache=True,
        )
    return HostlistActionResult(
        ok=True,
        log_level="INFO",
        log_message=f"Восстановлено доменов в системной базе: {added}",
        infobar_level="success",
        infobar_title="Готово",
        infobar_content=f"Восстановлено доменов в системной базе: {added}",
        invalidate_excl_base_cache=True,
        reload_exclusions=True,
    )


def open_ipset_ru_user_file_action() -> HostlistActionResult:
    try:
        open_ipset_ru_user_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт пользовательский список IP-исключений (lists/user/ipset-ru.txt)",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия пользовательского списка IP-исключений: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть:\n{e}",
        )


def open_ipset_ru_final_file_action() -> HostlistActionResult:
    try:
        open_ipset_ru_final_file()
        return HostlistActionResult(
            ok=True,
            log_level="INFO",
            log_message="Открыт итоговый файл ipset-ru.txt",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
        )
    except Exception as e:
        return HostlistActionResult(
            ok=False,
            log_level="ERROR",
            log_message=f"Ошибка открытия итогового ipset-ru.txt: {e}",
            infobar_level="warning",
            infobar_title="Ошибка",
            infobar_content=f"Не удалось открыть итоговый файл: {e}",
        )


def load_ipset_ru_entries() -> HostlistEntriesState:
    from lists.ipsets_manager import (
        IPSET_RU_USER_PATH,
        ensure_ipset_ru_user_file,
        get_ipset_ru_base_set,
    )

    ensure_ipset_ru_user_file()
    entries: list[str] = []
    if os.path.exists(IPSET_RU_USER_PATH):
        with open(IPSET_RU_USER_PATH, "r", encoding="utf-8") as fh:
            entries = [line.strip() for line in fh if line.strip()]
    return HostlistEntriesState(entries=entries, base_set=get_ipset_ru_base_set())


def save_ipset_ru_entries(entries: list[str]) -> bool:
    from lists.ipsets_manager import IPSET_RU_USER_PATH, sync_ipset_ru_after_user_change

    os.makedirs(os.path.dirname(IPSET_RU_USER_PATH), exist_ok=True)
    with open(IPSET_RU_USER_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(entries) + ("\n" if entries else ""))
    return bool(sync_ipset_ru_after_user_change())


def open_ipset_ru_user_file() -> None:
    from lists.ipsets_manager import IPSET_RU_USER_PATH, ensure_ipset_ru_user_file

    ensure_ipset_ru_user_file()
    if IPSET_RU_USER_PATH and os.path.exists(IPSET_RU_USER_PATH):
        subprocess.run(["explorer", "/select,", IPSET_RU_USER_PATH])
    else:
        subprocess.run(["explorer", LISTS_FOLDER])


def open_ipset_ru_final_file() -> None:
    from lists.ipsets_manager import IPSET_RU_PATH, rebuild_ipset_ru_files

    rebuild_ipset_ru_files()
    if IPSET_RU_PATH and os.path.exists(IPSET_RU_PATH):
        subprocess.run(["explorer", "/select,", IPSET_RU_PATH])
    else:
        subprocess.run(["explorer", LISTS_FOLDER])
