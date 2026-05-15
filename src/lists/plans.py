from __future__ import annotations

from lists.commands import (
    extract_domain,
    get_custom_domains_base_set,
    get_custom_ipru_base_set,
    get_custom_ipset_base_set,
    get_netrogat_base_set,
    normalize_ipset_entry,
    split_domains,
    split_ip_entries,
)
from lists.state import (
    CustomDomainsAddPlan,
    CustomDomainsStatusPlan,
    CustomIpRuAddPlan,
    CustomIpRuStatusPlan,
    CustomIpSetAddPlan,
    CustomIpSetStatusPlan,
    CustomNetrogatAddPlan,
    CustomNetrogatStatusPlan,
)

def build_custom_domains_status_plan(text: str) -> CustomDomainsStatusPlan:
    lines = [
        line.strip()
        for line in str(text or "").split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    base_set = get_custom_domains_base_set()
    valid_domains: list[str] = []

    for line in lines:
        domain = extract_domain(line)
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

    domain = extract_domain(text)
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


def build_custom_ipset_status_plan(text: str) -> CustomIpSetStatusPlan:
    lines = [
        line.strip()
        for line in str(text or "").split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    base_set = get_custom_ipset_base_set()
    valid_entries: set[str] = set()

    for line in lines:
        for item in split_ip_entries(line):
            norm = normalize_ipset_entry(item)
            if norm:
                valid_entries.add(norm)

    invalid_lines: list[tuple[int, str]] = []
    for i, raw_line in enumerate(str(text or "").split("\n"), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for item in split_ip_entries(line):
            if not normalize_ipset_entry(item):
                invalid_lines.append((i, item))

    return CustomIpSetStatusPlan(
        total_count=len(base_set.union(valid_entries)),
        base_count=len(base_set),
        user_count=len({ip for ip in valid_entries if ip not in base_set}),
        invalid_lines=invalid_lines,
    )


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

    norm = normalize_ipset_entry(text)
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


def build_custom_ipru_status_plan(text: str) -> CustomIpRuStatusPlan:
    lines = [
        line.strip()
        for line in str(text or "").split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    base_set = get_custom_ipru_base_set()
    valid_entries: set[str] = set()

    for line in lines:
        for item in split_ip_entries(line):
            norm = normalize_ipset_entry(item)
            if norm:
                valid_entries.add(norm)

    invalid_lines: list[tuple[int, str]] = []
    for i, raw_line in enumerate(str(text or "").split("\n"), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for item in split_ip_entries(line):
            if not normalize_ipset_entry(item):
                invalid_lines.append((i, item))

    return CustomIpRuStatusPlan(
        total_count=len(base_set.union(valid_entries)),
        base_count=len(base_set),
        user_count=len({ip for ip in valid_entries if ip not in base_set}),
        invalid_lines=invalid_lines,
    )


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

    for part in split_ip_entries(text):
        norm = normalize_ipset_entry(part)
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


def build_custom_netrogat_status_plan(text: str) -> CustomNetrogatStatusPlan:
    from lists.commands import normalize_netrogat_domain

    lines = [
        line.strip()
        for line in str(text or "").split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    base_set = get_netrogat_base_set()
    valid_entries: set[str] = set()

    for line in lines:
        for item in split_domains(line):
            norm = normalize_netrogat_domain(item)
            if norm:
                valid_entries.add(norm)

    return CustomNetrogatStatusPlan(
        total_count=len(base_set.union(valid_entries)),
        base_count=len(base_set),
        user_count=len({d for d in valid_entries if d not in base_set}),
    )


def build_add_custom_netrogat_plan(*, raw_text: str, current_text: str) -> CustomNetrogatAddPlan:
    from lists.commands import normalize_netrogat_domain

    raw = str(raw_text or "").strip()
    if not raw:
        return CustomNetrogatAddPlan(
            level=None,
            title="",
            content="",
            new_text=None,
            clear_input=False,
        )

    parts = split_domains(raw)
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
        norm = normalize_netrogat_domain(part)
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
