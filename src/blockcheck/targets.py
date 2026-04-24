"""Target loading — domains.txt, tcp_16_20_targets.json, user domains, defaults."""

import json
import logging
import os
import re
import sys
from pathlib import Path

from blockcheck.config import TCP_TARGET_MAX_COUNT, TCP_TARGETS_PER_PROVIDER
from config.config import MAIN_DIRECTORY

logger = logging.getLogger(__name__)

# User domains file — stored next to the installed program
USER_DOMAINS_FILE = "blockcheck_user_domains.txt"


def _data_dir() -> Path:
    """Return path to blockcheck/data/ directory (bundled, read-only in PyInstaller)."""
    return Path(__file__).parent / "data"


def _user_data_path() -> Path:
    """Return path to user domains file (writable)."""
    return Path(MAIN_DIRECTORY) / USER_DOMAINS_FILE


def _iter_data_file_candidates(filename: str, filepath: str | Path | None = None) -> list[Path]:
    """Build candidate paths for bundled/external blockcheck data files."""
    if filepath is not None:
        return [Path(filepath)]

    app_dir = Path(MAIN_DIRECTORY)

    candidates: list[Path] = [
        app_dir / "blockcheck" / "data" / filename,
        app_dir / "data" / filename,
    ]

    candidates.append(_data_dir() / filename)

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


# ---------------------------------------------------------------------------
# Built-in domain list
# ---------------------------------------------------------------------------

def load_domains(filepath: str | Path | None = None) -> list[str]:
    """Load domain list from file (one domain per line, # comments)."""
    domains, _ = load_domains_with_source(filepath)
    return domains


def load_domains_with_source(filepath: str | Path | None = None) -> tuple[list[str], str]:
    """Load domains and return (domains, source_info)."""
    candidates = _iter_data_file_candidates("domains.txt", filepath)
    fallback_domains = get_default_https_targets_domains()

    for candidate in candidates:
        if not candidate.exists():
            continue

        try:
            domains = []
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    domains.append(line)

            if domains:
                return domains, f"file:{candidate}"
            return fallback_domains, f"fallback:empty:{candidate}"
        except OSError as e:
            logger.warning("Failed to load domains from %s: %s", candidate, e)
            return fallback_domains, f"fallback:invalid:{candidate}"

    if candidates:
        return fallback_domains, f"fallback:missing:{candidates[0]}"
    return fallback_domains, "fallback:missing:domains.txt"


# ---------------------------------------------------------------------------
# User custom domains (writable, persisted)
# ---------------------------------------------------------------------------

def load_user_domains() -> list[str]:
    """Load user-added custom domains from file."""
    path = _user_data_path()
    if not path.exists():
        return []
    try:
        domains = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line)
        return domains
    except OSError:
        return []


def save_user_domains(domains: list[str]) -> None:
    """Save user custom domains to file."""
    path = _user_data_path()
    try:
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for d in domains:
            d = d.strip().lower()
            if d and d not in seen:
                seen.add(d)
                unique.append(d)
        path.write_text("\n".join(unique) + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to save user domains: %s", e)


def add_user_domain(domain: str) -> bool:
    """Add a domain to user list. Returns True if added (not duplicate)."""
    domain = _normalize_domain(domain)
    if not domain:
        return False
    domains = load_user_domains()
    if domain in domains:
        return False
    domains.append(domain)
    save_user_domains(domains)
    return True


def remove_user_domain(domain: str) -> bool:
    """Remove a domain from user list. Returns True if removed."""
    domain = _normalize_domain(domain)
    domains = load_user_domains()
    if domain not in domains:
        return False
    domains.remove(domain)
    save_user_domains(domains)
    return True


def _normalize_domain(domain: str) -> str:
    """Normalize a domain: strip protocol, path, whitespace."""
    domain = domain.strip()
    # Strip protocol
    domain = re.sub(r"^https?://", "", domain)
    # Strip path, query, fragment
    domain = domain.split("/")[0].split("?")[0].split("#")[0]
    # Strip port
    if ":" in domain:
        domain = domain.rsplit(":", 1)[0]
    return domain.lower().strip()


# ---------------------------------------------------------------------------
# TCP 16-20KB targets
# ---------------------------------------------------------------------------

def load_tcp_targets_with_source(filepath: str | Path | None = None) -> tuple[list[dict], str]:
    """Load TCP targets and return (targets, source_info)."""
    candidates = _iter_data_file_candidates("tcp_16_20_targets.json", filepath)

    for filepath_candidate in candidates:
        if not filepath_candidate.exists():
            continue

        try:
            data = json.loads(filepath_candidate.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data, f"file:{filepath_candidate}"
            return get_default_tcp_16_20_targets(), f"fallback:empty:{filepath_candidate}"
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load tcp targets from %s: %s", filepath_candidate, e)
            return get_default_tcp_16_20_targets(), f"fallback:invalid:{filepath_candidate}"

    if candidates:
        return get_default_tcp_16_20_targets(), f"fallback:missing:{candidates[0]}"
    return get_default_tcp_16_20_targets(), "fallback:missing:tcp_16_20_targets.json"


def load_tcp_targets(filepath: str | Path | None = None) -> list[dict]:
    """Load TCP 16-20KB test targets from JSON file."""
    targets, _ = load_tcp_targets_with_source(filepath)
    return targets


def select_tcp_targets(
    targets: list[dict],
    max_count: int = TCP_TARGET_MAX_COUNT,
    per_provider_cap: int = TCP_TARGETS_PER_PROVIDER,
) -> list[dict]:
    """Select a diverse subset of TCP targets.

    Selection strategy:
    1) round-robin across providers for fairness;
    2) up to ``per_provider_cap`` entries per provider;
    3) stop at ``max_count``.
    """
    if not targets or max_count <= 0:
        return []

    if per_provider_cap <= 0:
        per_provider_cap = 1

    by_provider: dict[str, list[dict]] = {}
    for t in targets:
        prov = str(t.get("provider") or "unknown")
        by_provider.setdefault(prov, []).append(t)

    provider_order = list(by_provider.keys())
    provider_taken = {provider: 0 for provider in provider_order}
    provider_index = {provider: 0 for provider in provider_order}

    selected: list[dict] = []
    while len(selected) < max_count:
        added_this_round = False

        for provider in provider_order:
            if provider_taken[provider] >= per_provider_cap:
                continue

            idx = provider_index[provider]
            items = by_provider[provider]
            if idx >= len(items):
                continue

            selected.append(items[idx])
            provider_index[provider] += 1
            provider_taken[provider] += 1
            added_this_round = True

            if len(selected) >= max_count:
                break

        if not added_this_round:
            break

    return selected


# ---------------------------------------------------------------------------
# Default targets
# ---------------------------------------------------------------------------

def get_default_https_targets() -> list[dict]:
    """Default HTTPS targets for blockcheck."""
    return [
        # Social / Messaging
        {"name": "Discord", "value": "https://discord.com"},
        {"name": "Discord GW", "value": "https://gateway.discord.gg"},
        {"name": "Discord CDN", "value": "https://cdn.discordapp.com"},
        {"name": "Telegram", "value": "https://telegram.org"},
        {"name": "Telegram Web", "value": "https://web.telegram.org"},
        # Video
        {"name": "YouTube", "value": "https://www.youtube.com"},
        {"name": "YouTube Short", "value": "https://youtu.be"},
        {"name": "r2---sn-jvhnu5g-c35k.googlevideo.com", "value": "r2---sn-jvhnu5g-c35k.googlevideo.com"},
        {"name": "rr5---sn-c0q7lnz7.googlevideo.com", "value": "rr5---sn-c0q7lnz7.googlevideo.com"},
        {"name": "rr2---sn-axq7sn7z.googlevideo.com", "value": "rr2---sn-axq7sn7z.googlevideo.com"},
        {"name": "rr4---sn-q4flrnsd.googlevideo.com", "value": "rr4---sn-q4flrnsd.googlevideo.com"},
        {"name": "YT Images", "value": "https://i.ytimg.com"},
        # Search / Cloud
        {"name": "Google", "value": "https://www.google.com"},
        {"name": "Cloudflare", "value": "https://www.cloudflare.com"},
        # Other commonly blocked
        {"name": "RuTracker", "value": "https://rutracker.org"},
        {"name": "LinkedIn", "value": "https://www.linkedin.com"},
        {"name": "Instagram", "value": "https://www.instagram.com"},
        {"name": "Facebook", "value": "https://www.facebook.com"},
        {"name": "Twitter/X", "value": "https://x.com"},
        {"name": "Spotify", "value": "https://www.spotify.com"},
    ]


def get_default_https_targets_domains() -> list[str]:
    """Extract domain names from default HTTPS targets."""
    return [
        re.sub(r"^https?://", "", t["value"]).rstrip("/").split("/")[0]
        for t in get_default_https_targets()
    ]


def get_default_stun_targets() -> list[dict]:
    """Default STUN/UDP targets.

    Note: stun.discord.gg no longer resolves via DNS on many ISPs.
    Discord voice uses media servers directly, not public STUN.
    """
    return [
        {"name": "Google STUN", "value": "STUN:stun.l.google.com:19302"},
        {"name": "CF STUN", "value": "STUN:stun.cloudflare.com:3478"},
        {"name": "Twilio STUN", "value": "STUN:global.stun.twilio.com:3478"},
        {"name": "Telegram STUN", "value": "STUN:stun.telegram.org:3478"},
        {"name": "Telegram VoIP STUN", "value": "STUN:stun.voip.telegram.org:3478"},
    ]


def get_default_ping_targets() -> list[dict]:
    """Default ICMP ping targets."""
    return [
        {"name": "CF DNS", "value": "PING:1.1.1.1"},
        {"name": "Google DNS", "value": "PING:8.8.8.8"},
    ]


def get_default_tcp_16_20_targets() -> list[dict]:
    """Fallback TCP 16-20KB test targets (used when JSON file is missing)."""
    return [
        {"id": "CA.CF-01", "provider": "Cloudflare", "name": "CF-01", "url": "https://aegis.audioeye.com/assets/index.js"},
        {"id": "DE.HE-01", "provider": "Hetzner", "name": "HE-01", "url": "https://www.industrialport.net/wp-content/uploads/custom-fonts/2022/10/Lato-Bold.ttf"},
        {"id": "FR.OVH-01", "provider": "OVH", "name": "OVH-01", "url": "https://proof.ovh.net/files/1Mb.dat"},
    ]


def get_all_default_targets() -> list[dict]:
    """Get all default targets combined."""
    return (
        get_default_https_targets()
        + get_default_stun_targets()
        + get_default_ping_targets()
    )


def build_targets_with_user_domains(extra_domains: list[str] | None = None) -> list[dict]:
    """Build full target list: defaults + user domains + extra domains."""
    targets = get_all_default_targets()

    # Load persisted user domains
    user_domains = load_user_domains()

    # Merge extra domains (from GUI input)
    if extra_domains:
        for d in extra_domains:
            d = _normalize_domain(d)
            if d and d not in user_domains:
                user_domains.append(d)

    # Convert user domains to HTTPS targets, skip duplicates
    existing_hosts = set()
    for t in targets:
        v = t["value"]
        if not v.startswith(("PING:", "STUN:")):
            host = re.sub(r"^https?://", "", v).rstrip("/").split("/")[0].lower()
            existing_hosts.add(host)

    for domain in user_domains:
        if domain not in existing_hosts:
            # Use domain as display name (capitalize first letter)
            name = domain.split(".")[0].capitalize() if "." in domain else domain
            targets.insert(-5, {"name": f"[U] {name}", "value": f"https://{domain}"})
            existing_hosts.add(domain)

    return targets
