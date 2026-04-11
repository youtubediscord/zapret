from __future__ import annotations

import os
import ipaddress
import re
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from config import LISTS_FOLDER, NETROGAT_PATH, OTHER_USER_PATH
from log import log


@dataclass(slots=True)
class HostlistFolderInfo:
    folder_exists: bool
    hostlist_files_count: int
    ipset_files_count: int
    hostlist_lines: int
    ipset_lines: int
    folder: str


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


class HostlistPageController:
    @staticmethod
    def split_domains(text: str) -> list[str]:
        parts = re.split(r"[\s,;]+", str(text or ""))
        result: list[str] = []

        for part in parts:
            part = part.strip().lower()
            if not part or part.startswith("#"):
                if part:
                    result.append(part)
                continue
            result.extend(HostlistPageController._split_glued_domains(part))

        return result

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _is_ipset_file_name(file_name: str) -> bool:
        lower = (file_name or "").lower()
        return lower.startswith("ipset-") or "ipset" in lower or "subnet" in lower

    @staticmethod
    def _count_lines(folder: str, file_names: list[str], *, max_files: int, skip_comments: bool) -> int:
        total = 0
        for file_name in file_names[:max_files]:
            try:
                path = os.path.join(folder, file_name)
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    if skip_comments:
                        total += sum(1 for line in fh if line.strip() and not line.startswith("#"))
                    else:
                        total += sum(1 for _ in fh)
            except Exception:
                continue
        return total

    @staticmethod
    def load_folder_info() -> HostlistFolderInfo:
        if not os.path.exists(LISTS_FOLDER):
            return HostlistFolderInfo(False, 0, 0, 0, 0, LISTS_FOLDER)

        txt_files = [name for name in os.listdir(LISTS_FOLDER) if name.endswith(".txt")]
        ipset_files = [name for name in txt_files if HostlistPageController._is_ipset_file_name(name)]
        hostlist_files = [name for name in txt_files if name not in ipset_files]

        return HostlistFolderInfo(
            folder_exists=True,
            hostlist_files_count=len(hostlist_files),
            ipset_files_count=len(ipset_files),
            hostlist_lines=HostlistPageController._count_lines(LISTS_FOLDER, hostlist_files, max_files=12, skip_comments=False),
            ipset_lines=HostlistPageController._count_lines(LISTS_FOLDER, ipset_files, max_files=12, skip_comments=True),
            folder=LISTS_FOLDER,
        )

    @staticmethod
    def open_lists_folder() -> None:
        os.startfile(LISTS_FOLDER)

    @staticmethod
    def rebuild_hostlists() -> None:
        from utils.hostlists_manager import startup_hostlists_check

        startup_hostlists_check()

    @staticmethod
    def load_domains_entries() -> HostlistEntriesState:
        from utils.hostlists_manager import ensure_hostlists_exist

        ensure_hostlists_exist()
        entries: list[str] = []
        if os.path.exists(OTHER_USER_PATH):
            with open(OTHER_USER_PATH, "r", encoding="utf-8") as fh:
                entries = [line.strip() for line in fh if line.strip()]
        return HostlistEntriesState(entries=entries)

    @staticmethod
    def load_custom_domains_text() -> CustomDomainsLoadState:
        from utils.hostlists_manager import ensure_hostlists_exist

        ensure_hostlists_exist()
        lines: list[str] = []
        if os.path.exists(OTHER_USER_PATH):
            with open(OTHER_USER_PATH, "r", encoding="utf-8") as fh:
                lines = [line.strip() for line in fh if line.strip()]
        return CustomDomainsLoadState(text="\n".join(lines), lines_count=len(lines))

    @staticmethod
    def save_domains_entries(entries: list[str]) -> bool:
        from utils.hostlists_manager import rebuild_other_files

        os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
        with open(OTHER_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        try:
            rebuild_other_files()
        except Exception:
            pass
        return True

    @staticmethod
    def save_custom_domains_text(text: str) -> CustomDomainsSaveState:
        from utils.hostlists_manager import rebuild_other_files

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

            for item in HostlistPageController.split_domains(line):
                domain = HostlistPageController.extract_domain(item)
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

    @staticmethod
    def get_custom_domains_base_set() -> set[str]:
        try:
            from utils.hostlists_manager import get_base_domains_set

            return get_base_domains_set()
        except Exception:
            return set()

    @staticmethod
    def build_custom_domains_status_plan(text: str) -> CustomDomainsStatusPlan:
        lines = [
            line.strip()
            for line in str(text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        base_set = HostlistPageController.get_custom_domains_base_set()
        valid_domains: list[str] = []

        for line in lines:
            domain = HostlistPageController.extract_domain(line)
            if domain:
                valid_domains.append(domain)

        user_set = {d for d in valid_domains if d}
        user_count = len({d for d in user_set if d not in base_set})
        base_count = len(base_set)
        total_count = len(base_set.union(user_set))
        return CustomDomainsStatusPlan(
            total_count=total_count,
            base_count=base_count,
            user_count=user_count,
        )

    @staticmethod
    def build_add_custom_domain_plan(*, raw_text: str, current_text: str) -> CustomDomainsAddPlan:
        text = str(raw_text or "").strip()
        if not text:
            return CustomDomainsAddPlan(
                level=None,
                title="",
                content="",
                new_text=None,
                clear_input=False,
            )

        domain = HostlistPageController.extract_domain(text)
        if not domain:
            return CustomDomainsAddPlan(
                level="warning",
                title="Ошибка",
                content=(
                    "Не удалось распознать домен:\n"
                    f"{text}\n\n"
                    "Введите корректный домен (например: example.com)"
                ),
                new_text=None,
                clear_input=False,
            )

        current_domains = [
            line.strip().lower()
            for line in str(current_text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        if domain.lower() in current_domains:
            return CustomDomainsAddPlan(
                level="info",
                title="Информация",
                content=f"Домен уже добавлен:\n{domain}",
                new_text=None,
                clear_input=False,
            )

        next_text = str(current_text or "")
        if next_text and not next_text.endswith("\n"):
            next_text += "\n"
        next_text += domain

        return CustomDomainsAddPlan(
            level=None,
            title="",
            content="",
            new_text=next_text,
            clear_input=True,
        )

    @staticmethod
    def split_ip_entries(text: str) -> list[str]:
        parts = re.split(r"[\s,;]+", str(text or ""))
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
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

    @staticmethod
    def get_custom_ipset_base_set() -> set[str]:
        try:
            from utils.ipsets_manager import get_ipset_all_base_set

            return get_ipset_all_base_set()
        except Exception:
            return set()

    @staticmethod
    def load_custom_ipset_text() -> CustomIpSetLoadState:
        from utils.ipsets_manager import ensure_ipset_all_user_file

        ensure_ipset_all_user_file()
        state = HostlistPageController.load_ipset_all_entries()
        return CustomIpSetLoadState(
            text="\n".join(state.entries),
            lines_count=len(state.entries),
            base_set=set(state.base_set or set()),
        )

    @staticmethod
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

            for item in HostlistPageController.split_ip_entries(line):
                norm = HostlistPageController.normalize_ipset_entry(item)
                if norm:
                    if norm not in entries:
                        entries.append(norm)
                        normalized_lines.append(norm)
                else:
                    normalized_lines.append(item)

        HostlistPageController.save_ipset_all_entries(entries)
        return CustomIpSetSaveState(
            normalized_text="\n".join(normalized_lines),
            saved_lines=entries,
            saved_count=len(entries),
        )

    @staticmethod
    def build_custom_ipset_status_plan(text: str) -> CustomIpSetStatusPlan:
        lines = [
            line.strip()
            for line in str(text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        base_set = HostlistPageController.get_custom_ipset_base_set()
        valid_entries: set[str] = set()

        for line in lines:
            for item in HostlistPageController.split_ip_entries(line):
                norm = HostlistPageController.normalize_ipset_entry(item)
                if norm:
                    valid_entries.add(norm)

        invalid_lines: list[tuple[int, str]] = []
        for i, raw_line in enumerate(str(text or "").split("\n"), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            for item in HostlistPageController.split_ip_entries(line):
                if not HostlistPageController.normalize_ipset_entry(item):
                    invalid_lines.append((i, item))

        return CustomIpSetStatusPlan(
            total_count=len(base_set.union(valid_entries)),
            base_count=len(base_set),
            user_count=len({ip for ip in valid_entries if ip not in base_set}),
            invalid_lines=invalid_lines,
        )

    @staticmethod
    def build_add_custom_ipset_plan(*, raw_text: str, current_text: str) -> CustomIpSetAddPlan:
        text = str(raw_text or "").strip()
        if not text:
            return CustomIpSetAddPlan(
                level=None,
                title="",
                content="",
                new_text=None,
                clear_input=False,
            )

        norm = HostlistPageController.normalize_ipset_entry(text)
        if not norm:
            return CustomIpSetAddPlan(
                level="warning",
                title="Ошибка",
                content=(
                    "Не удалось распознать IP или подсеть.\n"
                    "Примеры:\n"
                    "- 1.2.3.4\n"
                    "- 10.0.0.0/8\n"
                    "Диапазоны a-b не поддерживаются."
                ),
                new_text=None,
                clear_input=False,
            )

        current_entries = [
            line.strip().lower()
            for line in str(current_text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        if norm.lower() in current_entries:
            return CustomIpSetAddPlan(
                level="info",
                title="Информация",
                content=f"Запись уже есть:\n{norm}",
                new_text=None,
                clear_input=False,
            )

        next_text = str(current_text or "")
        if next_text and not next_text.endswith("\n"):
            next_text += "\n"
        next_text += norm

        return CustomIpSetAddPlan(
            level=None,
            title="",
            content="",
            new_text=next_text,
            clear_input=True,
        )

    @staticmethod
    def get_custom_ipru_base_set() -> set[str]:
        try:
            from utils.ipsets_manager import get_ipset_ru_base_set

            return get_ipset_ru_base_set()
        except Exception:
            return set()

    @staticmethod
    def load_custom_ipru_text() -> CustomIpRuLoadState:
        state = HostlistPageController.load_ipset_ru_entries()
        return CustomIpRuLoadState(
            text="\n".join(state.entries),
            lines_count=len(state.entries),
            base_set=set(state.base_set or set()),
        )

    @staticmethod
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

            for item in HostlistPageController.split_ip_entries(line):
                norm = HostlistPageController.normalize_ipset_entry(item)
                if norm:
                    if norm not in entries:
                        entries.append(norm)
                        normalized_lines.append(norm)
                else:
                    normalized_lines.append(item)

        HostlistPageController.save_ipset_ru_entries(entries)
        return CustomIpRuSaveState(
            normalized_text="\n".join(normalized_lines),
            saved_lines=entries,
            saved_count=len(entries),
        )

    @staticmethod
    def build_custom_ipru_status_plan(text: str) -> CustomIpRuStatusPlan:
        lines = [
            line.strip()
            for line in str(text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        base_set = HostlistPageController.get_custom_ipru_base_set()
        valid_entries: set[str] = set()

        for line in lines:
            for item in HostlistPageController.split_ip_entries(line):
                norm = HostlistPageController.normalize_ipset_entry(item)
                if norm:
                    valid_entries.add(norm)

        invalid_lines: list[tuple[int, str]] = []
        for i, raw_line in enumerate(str(text or "").split("\n"), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            for item in HostlistPageController.split_ip_entries(line):
                if not HostlistPageController.normalize_ipset_entry(item):
                    invalid_lines.append((i, item))

        return CustomIpRuStatusPlan(
            total_count=len(base_set.union(valid_entries)),
            base_count=len(base_set),
            user_count=len({ip for ip in valid_entries if ip not in base_set}),
            invalid_lines=invalid_lines,
        )

    @staticmethod
    def build_add_custom_ipru_plan(*, raw_text: str, current_text: str) -> CustomIpRuAddPlan:
        text = str(raw_text or "").strip()
        if not text:
            return CustomIpRuAddPlan(
                level=None,
                title="",
                content="",
                new_text=None,
                clear_input=False,
            )

        added: list[str] = []
        invalid: list[str] = []
        skipped: list[str] = []
        current_entries = [
            line.strip().lower()
            for line in str(current_text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        for part in HostlistPageController.split_ip_entries(text):
            norm = HostlistPageController.normalize_ipset_entry(part)
            if not norm:
                invalid.append(part)
                continue
            if norm.lower() in current_entries or norm.lower() in [a.lower() for a in added]:
                skipped.append(norm)
                continue
            added.append(norm)

        if not added and invalid:
            return CustomIpRuAddPlan(
                level="warning",
                title="Ошибка",
                content="Не удалось распознать IP или подсеть.\nПримеры: 1.2.3.4 или 10.0.0.0/8",
                new_text=None,
                clear_input=False,
            )

        if not added and skipped:
            if len(skipped) == 1:
                return CustomIpRuAddPlan(
                    level="info",
                    title="Информация",
                    content=f"Запись уже есть:\n{skipped[0]}",
                    new_text=None,
                    clear_input=False,
                )
            return CustomIpRuAddPlan(
                level="info",
                title="Информация",
                content=f"Все записи уже есть ({len(skipped)})",
                new_text=None,
                clear_input=False,
            )

        next_text = str(current_text or "")
        if next_text and not next_text.endswith("\n"):
            next_text += "\n"
        next_text += "\n".join(added)

        if skipped:
            return CustomIpRuAddPlan(
                level="success",
                title="Добавлено",
                content=f"Добавлено IP-исключений. Пропущено уже существующих: {len(skipped)}",
                new_text=next_text,
                clear_input=True,
            )

        return CustomIpRuAddPlan(
            level=None,
            title="",
            content="",
            new_text=next_text,
            clear_input=True,
        )

    @staticmethod
    def load_custom_netrogat_text() -> CustomNetrogatLoadState:
        state = HostlistPageController.load_netrogat_entries()
        return CustomNetrogatLoadState(
            text="\n".join(state.entries),
            lines_count=len(state.entries),
            base_set=set(state.base_set or set()),
        )

    @staticmethod
    def save_custom_netrogat_text(text: str) -> CustomNetrogatSaveState:
        from utils.netrogat_manager import _normalize_domain

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

            for item in HostlistPageController.split_domains(line):
                norm = _normalize_domain(item)
                if norm:
                    if norm not in domains:
                        domains.append(norm)
                        normalized_lines.append(norm)
                else:
                    normalized_lines.append(item)

        success = HostlistPageController.save_netrogat_entries(domains)
        return CustomNetrogatSaveState(
            success=bool(success),
            normalized_text="\n".join(normalized_lines),
            saved_lines=domains,
            saved_count=len(domains),
        )

    @staticmethod
    def build_custom_netrogat_status_plan(text: str) -> CustomNetrogatStatusPlan:
        from utils.netrogat_manager import _normalize_domain

        lines = [
            line.strip()
            for line in str(text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        base_set = HostlistPageController.get_netrogat_base_set()
        valid_entries: set[str] = set()

        for line in lines:
            for item in HostlistPageController.split_domains(line):
                norm = _normalize_domain(item)
                if norm:
                    valid_entries.add(norm)

        return CustomNetrogatStatusPlan(
            total_count=len(base_set.union(valid_entries)),
            base_count=len(base_set),
            user_count=len({d for d in valid_entries if d not in base_set}),
        )

    @staticmethod
    def get_netrogat_base_set() -> set[str]:
        try:
            from utils.netrogat_manager import get_netrogat_base_set

            return get_netrogat_base_set()
        except Exception:
            return set()

    @staticmethod
    def build_add_custom_netrogat_plan(*, raw_text: str, current_text: str) -> CustomNetrogatAddPlan:
        from utils.netrogat_manager import _normalize_domain

        raw = str(raw_text or "").strip()
        if not raw:
            return CustomNetrogatAddPlan(
                level=None,
                title="",
                content="",
                new_text=None,
                clear_input=False,
            )

        parts = HostlistPageController.split_domains(raw)
        if not parts:
            return CustomNetrogatAddPlan(
                level="warning",
                title="Ошибка",
                content="Не удалось распознать домен.",
                new_text=None,
                clear_input=False,
            )

        current_domains = [
            line.strip().lower()
            for line in str(current_text or "").split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        added: list[str] = []
        skipped: list[str] = []
        invalid: list[str] = []

        for part in parts:
            if part.startswith("#"):
                continue
            norm = _normalize_domain(part)
            if not norm:
                invalid.append(part)
                continue
            if norm.lower() in current_domains or norm.lower() in [a.lower() for a in added]:
                skipped.append(norm)
                continue
            added.append(norm)

        if not added and not skipped and invalid:
            return CustomNetrogatAddPlan(
                level="warning",
                title="Ошибка",
                content="Не удалось распознать домены.",
                new_text=None,
                clear_input=False,
            )

        if not added and skipped:
            if len(skipped) == 1:
                return CustomNetrogatAddPlan(
                    level="info",
                    title="Информация",
                    content=f"Домен уже есть: {skipped[0]}",
                    new_text=None,
                    clear_input=False,
                )
            return CustomNetrogatAddPlan(
                level="info",
                title="Информация",
                content=f"Все домены уже есть ({len(skipped)})",
                new_text=None,
                clear_input=False,
            )

        next_text = str(current_text or "")
        if next_text and not next_text.endswith("\n"):
            next_text += "\n"
        next_text += "\n".join(added)

        if skipped:
            return CustomNetrogatAddPlan(
                level="success",
                title="Добавлено",
                content=f"Добавлено доменов. Пропущено уже существующих: {len(skipped)}",
                new_text=next_text,
                clear_input=True,
            )

        return CustomNetrogatAddPlan(
            level=None,
            title="",
            content="",
            new_text=next_text,
            clear_input=True,
        )

    @staticmethod
    def open_domains_user_file() -> None:
        from utils.hostlists_manager import ensure_hostlists_exist

        ensure_hostlists_exist()
        if os.path.exists(OTHER_USER_PATH):
            subprocess.run(["explorer", "/select,", OTHER_USER_PATH])
        else:
            os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
            subprocess.run(["explorer", os.path.dirname(OTHER_USER_PATH)])

    @staticmethod
    def reset_domains_file() -> bool:
        from utils.hostlists_manager import reset_other_file_from_template

        return bool(reset_other_file_from_template())

    @staticmethod
    def load_ipset_all_entries() -> HostlistEntriesState:
        from utils.ipsets_manager import (
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

    @staticmethod
    def save_ipset_all_entries(entries: list[str]) -> bool:
        from utils.ipsets_manager import IPSET_ALL_USER_PATH, sync_ipset_all_after_user_change

        os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
        with open(IPSET_ALL_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        return bool(sync_ipset_all_after_user_change())

    @staticmethod
    def open_ipset_all_user_file() -> None:
        from utils.ipsets_manager import IPSET_ALL_USER_PATH, ensure_ipset_all_user_file

        ensure_ipset_all_user_file()
        if os.path.exists(IPSET_ALL_USER_PATH):
            subprocess.run(["explorer", "/select,", IPSET_ALL_USER_PATH])
        else:
            os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
            subprocess.run(["explorer", os.path.dirname(IPSET_ALL_USER_PATH)])

    @staticmethod
    def load_netrogat_entries() -> HostlistEntriesState:
        from utils.netrogat_manager import ensure_netrogat_user_file, get_netrogat_base_set, load_netrogat

        ensure_netrogat_user_file()
        return HostlistEntriesState(entries=load_netrogat(), base_set=get_netrogat_base_set())

    @staticmethod
    def save_netrogat_entries(domains: list[str]) -> bool:
        from utils.netrogat_manager import save_netrogat

        return bool(save_netrogat(domains))

    @staticmethod
    def open_netrogat_user_file() -> None:
        from utils.netrogat_manager import NETROGAT_USER_PATH, ensure_netrogat_user_file

        ensure_netrogat_user_file()
        if NETROGAT_USER_PATH and os.path.exists(NETROGAT_USER_PATH):
            subprocess.run(["explorer", "/select,", NETROGAT_USER_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def open_netrogat_final_file() -> None:
        from utils.netrogat_manager import ensure_netrogat_exists

        ensure_netrogat_exists()
        if NETROGAT_PATH and os.path.exists(NETROGAT_PATH):
            subprocess.run(["explorer", "/select,", NETROGAT_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def add_missing_netrogat_defaults() -> int:
        from utils.netrogat_manager import ensure_netrogat_base_defaults

        return int(ensure_netrogat_base_defaults())

    @staticmethod
    def open_lists_folder_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_lists_folder()
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

    @staticmethod
    def rebuild_hostlists_action() -> HostlistActionResult:
        try:
            HostlistPageController.rebuild_hostlists()
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

    @staticmethod
    def open_domains_user_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_domains_user_file()
            return HostlistActionResult(
                ok=True,
                log_level="INFO",
                log_message="Открыт файл other.user.txt",
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

    @staticmethod
    def reset_domains_file_action() -> HostlistActionResult:
        try:
            if HostlistPageController.reset_domains_file():
                return HostlistActionResult(
                    ok=True,
                    log_level="INFO",
                    log_message="Файл other.user.txt сброшен",
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

    @staticmethod
    def open_ipset_all_user_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_ipset_all_user_file()
            return HostlistActionResult(
                ok=True,
                log_level="INFO",
                log_message="Открыт файл ipset-all.user.txt",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
            )
        except Exception as e:
            return HostlistActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка открытия ipset-all.user.txt: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть:\n{e}",
            )

    @staticmethod
    def open_netrogat_user_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_netrogat_user_file()
            return HostlistActionResult(
                ok=True,
                log_level="INFO",
                log_message="Открыт файл netrogat.user.txt",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
            )
        except Exception as e:
            return HostlistActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка открытия netrogat.user.txt: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть:\n{e}",
            )

    @staticmethod
    def open_netrogat_final_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_netrogat_final_file()
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

    @staticmethod
    def add_missing_netrogat_defaults_action() -> HostlistActionResult:
        added = HostlistPageController.add_missing_netrogat_defaults()
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

    @staticmethod
    def open_ipset_ru_user_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_ipset_ru_user_file()
            return HostlistActionResult(
                ok=True,
                log_level="INFO",
                log_message="Открыт файл ipset-ru.user.txt",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
            )
        except Exception as e:
            return HostlistActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка открытия ipset-ru.user.txt: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть:\n{e}",
            )

    @staticmethod
    def open_ipset_ru_final_file_action() -> HostlistActionResult:
        try:
            HostlistPageController.open_ipset_ru_final_file()
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

    @staticmethod
    def load_ipset_ru_entries() -> HostlistEntriesState:
        from utils.ipsets_manager import (
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

    @staticmethod
    def save_ipset_ru_entries(entries: list[str]) -> bool:
        from utils.ipsets_manager import IPSET_RU_USER_PATH, sync_ipset_ru_after_user_change

        os.makedirs(os.path.dirname(IPSET_RU_USER_PATH), exist_ok=True)
        with open(IPSET_RU_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        return bool(sync_ipset_ru_after_user_change())

    @staticmethod
    def open_ipset_ru_user_file() -> None:
        from utils.ipsets_manager import IPSET_RU_USER_PATH, ensure_ipset_ru_user_file

        ensure_ipset_ru_user_file()
        if IPSET_RU_USER_PATH and os.path.exists(IPSET_RU_USER_PATH):
            subprocess.run(["explorer", "/select,", IPSET_RU_USER_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def open_ipset_ru_final_file() -> None:
        from utils.ipsets_manager import IPSET_RU_PATH, rebuild_ipset_ru_files

        rebuild_ipset_ru_files()
        if IPSET_RU_PATH and os.path.exists(IPSET_RU_PATH):
            subprocess.run(["explorer", "/select,", IPSET_RU_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])
