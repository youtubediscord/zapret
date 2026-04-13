# telegram_proxy/telegram_hosts.py
"""Auto-manage Telegram domains in Windows hosts file.

Ensures all required Telegram domains point to the proven WSS relay IP.
Called automatically when the Telegram Proxy page is opened.
Operates independently of HostsManager to avoid conflicts with DNS profile
selections — these entries are always active and never toggled by the user.
"""

from __future__ import annotations

from log.log import log


TELEGRAM_RELAY_IP = "149.154.167.220"

# Not used but known Telegram domains (do NOT add to hosts):
# kws1.web.telegram.org, kws1-1.web.telegram.org
# kws5.web.telegram.org, kws5-1.web.telegram.org
# zws1.web.telegram.org, zws1-1.web.telegram.org
# zws5.web.telegram.org, zws5-1.web.telegram.org
# pluto.web.telegram.org, pluto-1.web.telegram.org
# flora.web.telegram.org

TELEGRAM_DOMAINS: list[str] = [
    "zws4.web.telegram.org",
    "vesta.web.telegram.org",
    "vesta-1.web.telegram.org",
    "venus-1.web.telegram.org",
    "telegram.me",
    "telegram.dog",
    "telegram.space",
    "telesco.pe",
    "tg.dev",
    "telegram.org",
    "t.me",
    "api.telegram.org",
    "td.telegram.org",
    "venus.web.telegram.org",
    "web.telegram.org",
    "kws2-1.web.telegram.org",
    "kws2.web.telegram.org",
    "kws4-1.web.telegram.org",
    "kws4.web.telegram.org",
    "zws2-1.web.telegram.org",
    "zws2.web.telegram.org",
    "zws4-1.web.telegram.org",
]

_TELEGRAM_DOMAINS_LOWER: set[str] = {d.lower() for d in TELEGRAM_DOMAINS}


def ensure_telegram_hosts() -> tuple[bool, str]:
    """Check Windows hosts file and add/fix Telegram entries if needed.

    Returns ``(changed, message)``.
    *changed* is ``True`` when entries were added or corrected.
    """
    from hosts.hosts import safe_read_hosts_file, safe_write_hosts_file

    content = safe_read_hosts_file()
    if content is None:
        return False, "Не удалось прочитать файл hosts"

    # Parse existing entries: domain (lower) -> ip
    existing: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            existing[parts[1].lower()] = parts[0]

    # Determine what needs to change
    missing: list[str] = []
    wrong_ip: list[str] = []
    for domain in TELEGRAM_DOMAINS:
        ip = existing.get(domain.lower())
        if ip is None:
            missing.append(domain)
        elif ip != TELEGRAM_RELAY_IP:
            wrong_ip.append(domain)

    if not missing and not wrong_ip:
        log(f"Telegram hosts: все {len(TELEGRAM_DOMAINS)} записей актуальны")
        return False, f"Все {len(TELEGRAM_DOMAINS)} Telegram записей в hosts актуальны"

    # Rebuild content: remove stale Telegram entries AND old marker comments
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Remove our marker comment to avoid duplication
        if stripped == "# --- Telegram Proxy (auto-managed by Zapret 2 GUI) ---":
            continue
        if stripped and not stripped.startswith("#"):
            parts = stripped.split()
            if len(parts) >= 2 and parts[1].lower() in _TELEGRAM_DOMAINS_LOWER:
                continue  # will re-add below
        new_lines.append(line)

    # Trim trailing blank lines
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()

    # Append Telegram block
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines.append("\n")
    new_lines.append("\n")
    new_lines.append("# --- Telegram Proxy (auto-managed by Zapret 2 GUI) ---\n")
    for domain in TELEGRAM_DOMAINS:
        new_lines.append(f"{TELEGRAM_RELAY_IP} {domain}\n")

    if not safe_write_hosts_file("".join(new_lines)):
        return False, "Не удалось записать файл hosts"

    parts_msg: list[str] = []
    if missing:
        parts_msg.append(f"добавлено {len(missing)}")
    if wrong_ip:
        parts_msg.append(f"исправлено {len(wrong_ip)}")
    msg = f"Telegram hosts: {', '.join(parts_msg)}"
    log(msg)
    return True, msg
