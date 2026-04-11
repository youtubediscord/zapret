"""Helper'ы форматирования и domain-chip workflow для Blockcheck page."""

from __future__ import annotations


DETAILS_MAX_LEN = 140


def truncate_detail(text: str, max_len: int = DETAILS_MAX_LEN) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "..."


def format_result_detail(result) -> str:
    from blockcheck.models import TestStatus

    if result.status == TestStatus.OK:
        status_text = "OK"
    elif result.status == TestStatus.TIMEOUT:
        status_text = "TIMEOUT"
    elif result.status == TestStatus.UNSUPPORTED:
        status_text = "UNSUP"
    else:
        status_text = result.error_code or result.status.value.upper()

    detail = (result.detail or "").strip()
    base = f"{status_text}: {detail}" if detail else status_text

    if result.time_ms:
        if result.time_ms >= 1000:
            base += f" | {result.time_ms / 1000:.1f}s"
        else:
            base += f" | {result.time_ms:.0f}ms"

    return base


def result_family_label(result) -> str:
    raw = result.raw_data or {}
    family = str(raw.get("ip_family") or "").strip().lower()
    if family in ("ipv4", "ip4", "v4", "4"):
        return "IPv4"
    if family in ("ipv6", "ip6", "v6", "6"):
        return "IPv6"
    return "AUTO"


def sort_results_by_family(results: list):
    order = {"IPv4": 0, "IPv6": 1, "AUTO": 2}
    return sorted(results, key=lambda r: order.get(result_family_label(r), 3))


def build_family_tooltip(results: list) -> str:
    lines: list[str] = []
    for result in sort_results_by_family(results):
        family = result_family_label(result)
        lines.append(f"{family}: {format_result_detail(result)}")
    return "\n".join(lines)


def build_target_detail_text(tests: list) -> str:
    from blockcheck.models import TestStatus, TestType

    ordered_types = [
        ("HTTP", TestType.HTTP),
        ("TLS1.2", TestType.TLS_12),
        ("TLS1.3", TestType.TLS_13),
        ("ISP", TestType.ISP_PAGE),
        ("DNS", TestType.DNS_UDP),
        ("DNS", TestType.DNS_DOH),
        ("Ping", TestType.PING),
    ]

    per_type: dict[TestType, list] = {}
    for test in tests:
        per_type.setdefault(test.test_type, []).append(test)

    parts: list[str] = []
    for label, test_type in ordered_types:
        grouped = per_type.get(test_type) or []
        if not grouped:
            continue
        if len(grouped) == 1:
            chosen = grouped[0]
            parts.append(f"{label}: {format_result_detail(chosen)}")
            continue

        sorted_group = sort_results_by_family(grouped)
        summary = " / ".join(
            f"{result_family_label(result)} {format_result_detail(result)}"
            for result in sorted_group
        )
        parts.append(f"{label}: {summary}")
    return " | ".join(parts)


def load_domain_chips(*, load_domains_fn, add_chip_fn) -> None:
    try:
        for domain in load_domains_fn():
            add_chip_fn(domain)
    except Exception:
        pass


def add_domain_chip(*, domain: str, flow_widget, flow_layout, chip_cls, on_removed) -> None:
    chip = chip_cls(domain, parent=flow_widget)
    chip.removed.connect(on_removed)
    index = max(0, flow_layout.count() - 1)
    flow_layout.insertWidget(index, chip)


def remove_domain_chip(*, domain: str, flow_layout, chip_cls) -> bool:
    for i in range(flow_layout.count()):
        item = flow_layout.itemAt(i)
        if item and item.widget() and isinstance(item.widget(), chip_cls):
            if getattr(item.widget(), "_domain", None) == domain:
                widget = item.widget()
                flow_layout.removeWidget(widget)
                widget.deleteLater()
                return True
    return False


def collect_extra_domains(*, flow_layout, chip_cls) -> list[str]:
    domains: list[str] = []
    for i in range(flow_layout.count()):
        item = flow_layout.itemAt(i)
        if item and item.widget() and isinstance(item.widget(), chip_cls):
            domains.append(item.widget()._domain)
    return domains
