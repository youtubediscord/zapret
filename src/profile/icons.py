from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
import hashlib
import re

from profile.match_filters import filter_values


@dataclass(frozen=True)
class ProfileIconSpec:
    icon_name: str
    color: str


_KNOWN_ICONS: dict[str, ProfileIconSpec] = {
    "youtube": ProfileIconSpec("simple:youtube:YT", "#FF0000"),
    "googlevideo": ProfileIconSpec("simple:youtube:YT", "#FF0000"),
    "discord": ProfileIconSpec("simple:discord:DI", "#5865F2"),
    "discord-updates": ProfileIconSpec("simple:discord:DI", "#5865F2"),
    "telegram": ProfileIconSpec("simple:telegram:TG", "#229ED9"),
    "whatsapp": ProfileIconSpec("simple:whatsapp:WA", "#25D366"),
    "facebook": ProfileIconSpec("simple:facebook:FB", "#1877F2"),
    "instagram": ProfileIconSpec("simple:instagram:IN", "#E4405F"),
    "twitter": ProfileIconSpec("simple:x:X", "#000000"),
    "twimg": ProfileIconSpec("simple:x:X", "#000000"),
    "steam": ProfileIconSpec("simple:steam:ST", "#66C0F4"),
    "epicgames": ProfileIconSpec("simple:epicgames:EG", "#313131"),
    "ubisoft": ProfileIconSpec("simple:ubisoft:UB", "#006EF5"),
    "github": ProfileIconSpec("simple:github:GH", "#F0F3F6"),
    "twitch": ProfileIconSpec("simple:twitch:TW", "#9146FF"),
    "soundcloud": ProfileIconSpec("simple:soundcloud:SC", "#FF5500"),
    "tiktok": ProfileIconSpec("simple:tiktok:TT", "#000000"),
    "itch": ProfileIconSpec("simple:itchdotio:IT", "#FA5C5C"),
    "google": ProfileIconSpec("simple:google:GO", "#4285F4"),
    "amazon": ProfileIconSpec("fa5b.amazon", "#FF9900"),
    "fandom": ProfileIconSpec("simple:fandom:FA", "#FA005A"),
    "microsoft": ProfileIconSpec("fa5b.microsoft", "#00BCF2"),
    "microsoft-store": ProfileIconSpec("fa5b.microsoft", "#00BCF2"),
    "anydesk": ProfileIconSpec("simple:anydesk:AD", "#EF443B"),
    "speedtest": ProfileIconSpec("simple:speedtest:ST", "#141526"),
    "cloudflare": ProfileIconSpec("simple:cloudflare:CF", "#F38020"),
    "digitalocean": ProfileIconSpec("simple:digitalocean:DO", "#0080FF"),
    "hetzner": ProfileIconSpec("simple:hetzner:HE", "#D50C2D"),
    "ovh": ProfileIconSpec("simple:ovh:OV", "#123F6D"),
    "warp": ProfileIconSpec("simple:cloudflare:CF", "#F6821F"),
    "roblox": ProfileIconSpec("simple:roblox:RB", "#E2231A"),
    "lol": ProfileIconSpec("simple:leagueoflegends:LO", "#C89B3C"),
    "riot": ProfileIconSpec("simple:riotgames:RI", "#D13639"),
    "valorant": ProfileIconSpec("simple:valorant:VA", "#FA4454"),
    "deepseek": ProfileIconSpec("simple:deepseek:DS", "#4D6BFE"),
    "obsidian": ProfileIconSpec("simple:obsidian:OB", "#7C3AED"),
    "rutracker": ProfileIconSpec("fa5s.link", "#6AA2FF"),
    "rutor": ProfileIconSpec("fa5s.link", "#6AA2FF"),
    "timeweb": ProfileIconSpec("fa5s.server", "#2F80ED"),
    "zapretkvn": ProfileIconSpec("fa5s.server", "#31C48D"),
    "tankix": ProfileIconSpec("fa5s.gamepad", "#8B5CF6"),
    "7tv": ProfileIconSpec("fa5s.tv", "#60A5FA"),
    "porn": ProfileIconSpec("fa5s.user-shield", "#EC4899"),
    "all": ProfileIconSpec("fa5s.globe", "#60A5FA"),
    "general": ProfileIconSpec("fa5s.list-ul", "#94A3B8"),
    "faceinsta": ProfileIconSpec("fa5s.users", "#E4405F"),
    "myhostlist": ProfileIconSpec("fa5s.list-ul", "#94A3B8"),
    "mycdnlist": ProfileIconSpec("fa5s.cloud", "#60A5FA"),
    "ntc": ProfileIconSpec("fa5s.globe", "#60A5FA"),
    "z-library": ProfileIconSpec("fa5s.book", "#22C55E"),
    "net-cdn77": ProfileIconSpec("fa5s.cloud", "#60A5FA"),
}

_ICON_ALIASES: dict[str, str] = {
    "youtube-v2": "youtube",
    "youtubeq": "youtube",
    "youtubegv": "youtube",
    "ytimg": "youtube",
    "i-ytimg": "youtube",
    "russia-youtubeq": "youtube",
    "russia-youtube-rtmps": "youtube",
    "russia-discord": "discord",
    "cloudflare-ipset": "cloudflare",
    "cloudflare-ipset-v6": "cloudflare",
    "cloudflare1": "cloudflare",
    "com-cloudflarecp": "cloudflare",
    "cloudfront": "amazon",
    "txrevive": "cloudflare",
    "lol-ru": "lol",
    "lol-euw": "lol",
    "com-leagueoflegends": "lol",
    "com-riotcdn": "riot",
    "com-valorant": "valorant",
    "com-z-library": "z-library",
    "10tv": "7tv",
    "rbxcdn": "roblox",
    "epicgames-fortnite": "epicgames",
    "unrealengine": "epicgames",
    "ubi": "ubisoft",
    "uplay": "ubisoft",
}

_NAMED_COLORS: dict[str, str] = {
    "cloudflare": "#F38020",
    "digitalocean": "#0080FF",
    "hetzner": "#D50C2D",
    "ovh": "#123F6D",
    "warp": "#F6821F",
    "timeweb": "#2F80ED",
    "zapretkvn": "#31C48D",
    "roblox": "#E2231A",
    "lol": "#C89B3C",
    "lol-ru": "#C89B3C",
    "lol-euw": "#C89B3C",
    "rutracker": "#6AA2FF",
    "rutor": "#6AA2FF",
}

_FALLBACK_PALETTE: tuple[str, ...] = (
    "#14B8A6",
    "#3B82F6",
    "#8B5CF6",
    "#EC4899",
    "#F97316",
    "#22C55E",
    "#06B6D4",
    "#EAB308",
)


def resolve_profile_icon(display_name: object, match_lines: tuple[str, ...] | list[str] = ()) -> ProfileIconSpec:
    match_tuple = tuple(match_lines or ())
    identities = _profile_identities(display_name, match_tuple)
    for identity in identities:
        icon = _explicit_icon_for_identity(identity)
        if icon is not None:
            return icon

    semantic_icon = _semantic_icon_from_text(display_name, match_tuple, identities)
    if semantic_icon is not None:
        return semantic_icon

    identity = identities[0] if identities else "profile"
    color = _NAMED_COLORS.get(identity) or _color_from_seed(identity)
    initials = _initials_from_identity(identity)
    return ProfileIconSpec(f"profile-initials:{initials}", color)


def _profile_identity(display_name: object, match_lines: tuple[str, ...]) -> str:
    identities = _profile_identities(display_name, match_lines)
    return identities[0] if identities else "profile"


def _profile_identities(display_name: object, match_lines: tuple[str, ...]) -> tuple[str, ...]:
    candidates: list[str] = []
    candidates.extend(_resource_values(match_lines))
    candidates.append(str(display_name or ""))
    identities: list[str] = []
    for candidate in candidates:
        normalized = _normalize_identity(candidate)
        if normalized and normalized not in identities:
            identities.append(normalized)
    return tuple(identities or ("profile",))


def _explicit_icon_for_identity(identity: str) -> ProfileIconSpec | None:
    key = _ICON_ALIASES.get(identity, identity)
    return _KNOWN_ICONS.get(key)


def _semantic_icon_from_text(
    display_name: object,
    match_lines: tuple[str, ...],
    identities: tuple[str, ...],
) -> ProfileIconSpec | None:
    haystack = " ".join(
        [
            str(display_name or ""),
            " ".join(str(line or "") for line in match_lines),
            " ".join(identities),
        ]
    ).lower()
    if any(token in haystack for token in ("исключения", "exclude", "exclusion")):
        return ProfileIconSpec("fa5s.minus-circle", "#FACC15")
    if any(token in haystack for token in ("blacklist", "rublacklist", "russia-blacklist")):
        return ProfileIconSpec("fa5s.shield-alt", "#94A3B8")
    if any(token in haystack for token in ("голос", "звон", "voice")):
        return ProfileIconSpec("fa5s.microphone", "#38BDF8")
    if any(token in haystack for token in ("league of legends", "riotgames", "riot games")):
        return _KNOWN_ICONS["lol"]
    if "valorant" in haystack:
        return _KNOWN_ICONS["valorant"]
    if "riot" in haystack:
        return _KNOWN_ICONS["riot"]
    if any(token in haystack for token in ("game", "games", "игр")):
        return ProfileIconSpec("fa5s.gamepad", "#8B5CF6")
    if "general" in haystack:
        return _KNOWN_ICONS["general"]
    if any(token in haystack for token in ("все сайты", "мои сайты", "all sites")):
        return _KNOWN_ICONS["all"]
    if any(token in haystack for token in ("18+", "porn", "xvideos", "xnxx")):
        return _KNOWN_ICONS["porn"]
    return None


def _resource_values(match_lines: tuple[str, ...]) -> list[str]:
    return [
        *filter_values(match_lines, "--hostlist"),
        *filter_values(match_lines, "--ipset"),
        *filter_values(match_lines, "--hostlist-domains"),
        *filter_values(match_lines, "--ipset-ip"),
    ]


def _normalize_identity(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/").lower()
    if not text:
        return ""
    if "/" in text:
        text = PurePosixPath(text).name
    else:
        text = PureWindowsPath(text).name
    text = re.sub(r"\.(txt|lst|list|json)$", "", text, flags=re.IGNORECASE)
    for prefix in ("ipset-", "hostlist-", "list-"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = re.split(r"[\s(]", text, maxsplit=1)[0]
    text = text.strip(".-_")
    if "." in text:
        parts = [part for part in text.split(".") if part]
        if len(parts) >= 2:
            text = parts[-2]
    return re.sub(r"[^a-z0-9а-яё-]+", "-", text, flags=re.IGNORECASE).strip("-") or "profile"


def _initials_from_identity(identity: str) -> str:
    words = [part for part in re.split(r"[^a-z0-9а-яё]+", str(identity or ""), flags=re.IGNORECASE) if part]
    if not words:
        return "P"
    if len(words) == 1:
        word = words[0]
        return (word[:2] if len(word) > 1 else word[:1]).upper()
    return (words[0][:1] + words[1][:1]).upper()


def _color_from_seed(seed: str) -> str:
    digest = hashlib.sha1(str(seed or "profile").encode("utf-8")).digest()
    return _FALLBACK_PALETTE[digest[0] % len(_FALLBACK_PALETTE)]


__all__ = ["ProfileIconSpec", "resolve_profile_icon"]
