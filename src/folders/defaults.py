from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache
from typing import Any

COMMON_FOLDER_KEY = "common"
PINNED_FOLDER_KEY = "pinned"


_WINWS2_PRESET_FOLDERS: tuple[tuple[str, str, bool], ...] = (
    ("all-tcp-udp", "ALL TCP & UDP", False),
    (COMMON_FOLDER_KEY, "Общие", True),
    ("1-9-9", "1.9.9", False),
    ("game-filter", "Game filter", False),
    ("circular", "Circular", False),
)

_WINWS1_PRESET_FOLDERS: tuple[tuple[str, str, bool], ...] = (
    ("all-sites", "Все сайты", False),
    ("1-9-9a", "1.9.9a", False),
    ("alt", "ALT", False),
    ("games", "Игры", False),
    ("youtube", "YouTube", False),
    ("discord", "Discord", False),
    ("providers", "Провайдеры", False),
    ("bolvan", "Bolvan", False),
    ("fake-tls", "Fake TLS", False),
    ("split-md5-ttl", "Split / MD5 / TTL", False),
    (COMMON_FOLDER_KEY, "Общие", True),
)

_PROFILE_FOLDERS: tuple[tuple[str, str, bool], ...] = (
    ("youtube", "YouTube", False),
    ("discord", "Discord", False),
    ("github", "GitHub", False),
    ("messengers", "Мессенджеры", False),
    ("social", "Соцсети", False),
    ("games", "Игры", False),
    ("roblox", "Roblox", False),
    ("amazon", "Amazon", False),
    ("hosters", "Хостеры", False),
    ("sites", "Сайты", False),
    ("zapretkvn", "ZapretKVN", False),
    (COMMON_FOLDER_KEY, "Общие", True),
    ("all-sites", "Все сайты", False),
)


def build_default_preset_folders(scope_key: object = "winws2") -> dict[str, Any]:
    return _build_default_state(_preset_folder_specs_for_scope(scope_key))


def build_default_profile_folders() -> dict[str, Any]:
    return _build_default_state(_PROFILE_FOLDERS)


def classify_preset_folder(name: object, scope_key: object = "winws2") -> str:
    text = str(name or "").strip().lower()
    if _is_winws1_scope(scope_key):
        return _classify_winws1_preset_folder(text)
    if "all tcp" in text and "udp" in text:
        return "all-tcp-udp"
    if "1.9.9" in text:
        return "1-9-9"
    if "game filter" in text:
        return "game-filter"
    if "circular" in text:
        return "circular"
    return COMMON_FOLDER_KEY


def classify_profile_folder(text: object) -> str:
    value = str(text or "").strip().lower()
    if not value:
        return COMMON_FOLDER_KEY
    if _has_any_token(value, ("youtube", "googlevideo", "ytimg")):
        return "youtube"
    if _has_any_token(value, ("discord", "vencord")):
        return "discord"
    if _has_any_token(value, ("github", "ghcr.io")):
        return "github"
    if _has_any_token(value, ("telegram", "whatsapp", "viber", "signal", "mtproto")):
        return "messengers"
    if _has_any_token(value, ("facebook", "instagram", "tiktok", "twitter", "x.com", "vk")):
        return "social"
    if _has_any_token(value, ("roblox", "rbxcdn")):
        return "roblox"
    if _has_any_token(value, ("amazon", "awsapps", "awsglobalaccelerator", "cloudfront")):
        return "amazon"
    if _has_any_token(
        value,
        (
            "game",
            "epicgames",
            "epic games",
            "fortnite",
            "unrealengine",
            "ubisoft",
            "ubi.com",
            "uplay",
            "valorant",
            "riot",
            "steam",
            "itch.io",
            "tanki",
            "tankix",
            "lol",
            "league of legends",
            "battlenet",
            "battle.net",
            "wow",
            "dead by daylight",
        ),
    ):
        return "games"
    if _has_any_token(
        value,
        (
            "akamai",
            "cloudflare",
            "datacamp",
            "digitalocean",
            "fastly",
            "frantech",
            "google cloud",
            "ipset-google",
            "hetzner",
            "novoserve",
            "ovh",
            "railway",
            "usa google",
            "warp",
            "worldstream",
        ),
    ):
        return "hosters"
    if _has_any_token(value, ("timeweb", "zapretkvn")):
        return "zapretkvn"
    if _looks_like_all_sites_profile(value):
        return "all-sites"
    if _mentions_site_or_list(value):
        return "sites"
    return COMMON_FOLDER_KEY


def _has_any_token(value: str, tokens: tuple[str, ...]) -> bool:
    """Токен обязан начинаться на границе слова: `x.com` не находится в
    `wix.com`, `lol` — в `trololo`. Правая граница не требуется — `game`
    покрывает `games`, `steam` — `steamcommunity`."""
    return any(_token_pattern(token).search(value) for token in tokens)


@lru_cache(maxsize=256)
def _token_pattern(token: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9а-яё]){re.escape(token)}")


def _build_default_state(folder_specs: tuple[tuple[str, str, bool], ...]) -> dict[str, Any]:
    return {
        "version": 1,
        "folders": {
            key: {
                "name": name,
                "order": index,
                "collapsed": False,
                "system": system,
            }
            for index, (key, name, system) in enumerate(folder_specs)
        },
        "items": {},
    }


def _preset_folder_specs_for_scope(scope_key: object) -> tuple[tuple[str, str, bool], ...]:
    return _WINWS1_PRESET_FOLDERS if _is_winws1_scope(scope_key) else _WINWS2_PRESET_FOLDERS


def _is_winws1_scope(scope_key: object) -> bool:
    return str(scope_key or "").strip().lower() == "winws1"


def _classify_winws1_preset_folder(text: str) -> str:
    if not text:
        return COMMON_FOLDER_KEY
    if "1.9.9a" in text:
        return "1-9-9a"
    if any(token in text for token in ("allsite", "allsites", "all-site", "all sites", "все сайты")):
        return "all-sites"
    if "alt" in text:
        return "alt"
    if any(token in text for token in ("game filter", "game", "valorant", "lol", "league of legends")):
        return "games"
    if any(token in text for token in ("ytdis", "bystro", "youtube")):
        return "youtube"
    if "discord" in text:
        return "discord"
    if any(token in text for token in ("mgts", "rosmts", "rosmega", "ufanet", "shigulovski")):
        return "providers"
    if "bolvan" in text:
        return "bolvan"
    if "faketls" in text:
        return "fake-tls"
    if any(
        token in text
        for token in (
            "split",
            "md5sig",
            "ttl",
            "padencap",
            "wssize",
            "badseq",
            "sniext",
            "datanoack",
            "multisplit",
        )
    ):
        return "split-md5-ttl"
    return COMMON_FOLDER_KEY


def _looks_like_all_sites_profile(text: str) -> bool:
    if any(token in text for token in ("allsite", "all-site", "all sites", "все сайты")):
        return True
    has_include = any(token in text for token in ("--hostlist=", "--hostlist-domains=", "--ipset=", "--ipset-ip="))
    has_exclude = any(token in text for token in ("--hostlist-exclude", "--ipset-exclude"))
    return has_exclude and not has_include


def _mentions_site_or_list(text: str) -> bool:
    if any(token in text for token in ("--hostlist=", "--hostlist-domains=", "--ipset=", "--ipset-ip=")):
        return True
    return bool(re.search(r"\b[a-z0-9-]+\.(?:ru|com|org|net|io|gg|tv)\b", text))


def clone_default_preset_folders(scope_key: object = "winws2") -> dict[str, Any]:
    return deepcopy(build_default_preset_folders(scope_key))


def clone_default_profile_folders() -> dict[str, Any]:
    return deepcopy(build_default_profile_folders())


__all__ = [
    "COMMON_FOLDER_KEY",
    "PINNED_FOLDER_KEY",
    "build_default_preset_folders",
    "build_default_profile_folders",
    "classify_preset_folder",
    "classify_profile_folder",
    "clone_default_preset_folders",
    "clone_default_profile_folders",
]
