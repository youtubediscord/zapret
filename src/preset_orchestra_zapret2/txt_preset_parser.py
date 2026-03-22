# presets/txt_preset_parser.py
"""
Parser for Zapret 2 txt preset files.

Parses preset-zapret2.txt into structured data and back.
Supports:
- Base args (lua-init, wf-*, blob=*)
- Category blocks separated by --new
- Category detection from --hostlist/--ipset
- Protocol detection from --filter-tcp/--filter-udp
"""

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Dict, List, Optional, Tuple, Set

from log import log

_CATEGORY_FILTER_CACHE: Optional[Dict[str, List[Tuple[str, Set[str]]]]] = None
_CATEGORY_INFO_CACHE: Optional[Dict[str, Dict]] = None


def invalidate_category_inference_cache() -> None:
    """
    Invalidates internal caches used for category inference.

    Important for user categories: blocks that use `--hostlist-domains=...` or
    `--ipset-ip=...` can't be mapped to a category via filename, so we rely on
    matching against categories base filters. If categories change at runtime,
    this cache must be cleared to avoid falling back to `category=unknown`.
    """
    global _CATEGORY_FILTER_CACHE, _CATEGORY_INFO_CACHE
    _CATEGORY_FILTER_CACHE = None
    _CATEGORY_INFO_CACHE = None


_PLACEHOLDER_HOSTLIST_FILES = {"unknown.txt"}
_PLACEHOLDER_IPSET_FILES = {"ipset-unknown.txt"}

_CATEGORY_BLOCK_START_PREFIXES = (
    "--filter-tcp",
    "--filter-udp",
    "--filter-l7",
    "--hostlist=",
    "--hostlist-domains=",
    "--hostlist-exclude=",
    "--ipset=",
    "--ipset-exclude=",
    "--ipset-ip=",
)

_FILTER_SELECTOR_PREFIXES = (
    "--filter-",
    "--hostlist=",
    "--hostlist-domains=",
    "--hostlist-exclude=",
    "--ipset=",
    "--ipset-exclude=",
    "--ipset-ip=",
)


def _normalize_category_key(value: str) -> str:
    return str(value or "").strip().lower()


def _uses_placeholder_unknown_list_file(block: "CategoryBlock") -> bool:
    """
    Returns True if a block references placeholder list files:
      - --hostlist=.../unknown.txt
      - --ipset=.../ipset-unknown.txt
    """
    try:
        for raw in (block.args or "").splitlines():
            line = raw.strip()
            if not line.startswith("--") or "=" not in line:
                continue

            key, _sep, value = line.partition("=")
            key_l = key.strip().lower()
            if key_l not in ("--hostlist", "--ipset"):
                continue

            value = value.strip().strip('"').strip("'")
            if value.startswith("@"):
                value = value[1:]

            filename = PureWindowsPath(value).name.lower()
            if key_l == "--hostlist" and filename in _PLACEHOLDER_HOSTLIST_FILES:
                return True
            if key_l == "--ipset" and filename in _PLACEHOLDER_IPSET_FILES:
                return True
    except Exception:
        return False

    return False


def _drop_placeholder_unknown_categories(blocks: List["CategoryBlock"]) -> List["CategoryBlock"]:
    """
    Drops whole categories that reference placeholder list files.

    If a category has both TCP and UDP blocks, and at least one block references
    a placeholder file, all blocks for that category are removed.
    """
    drop_keys = {
        _normalize_category_key(b.category)
        for b in (blocks or [])
        if _uses_placeholder_unknown_list_file(b)
    }
    drop_keys.discard("")
    if not drop_keys:
        return blocks

    kept = [b for b in (blocks or []) if _normalize_category_key(b.category) not in drop_keys]
    try:
        log(
            "Removed category blocks with placeholder list files: "
            + ", ".join(sorted(drop_keys)),
            "WARNING",
        )
    except Exception:
        pass
    return kept


@dataclass
class CategoryBlock:
    """
    Represents a single category block in preset file.

    A block ends before --new or EOF and may start with --filter-* or list selectors.
    Category is extracted from --hostlist=xxx.txt / --ipset=xxx.txt (supports multiple).

    Attributes:
        category: Category name extracted from hostlist/ipset (e.g., "youtube", "discord")
        protocol: "tcp" or "udp" - from --filter-tcp/--filter-udp
        filter_mode: "hostlist" or "ipset" - which filter type is used
        filter_file: Full filename from filter (e.g., "youtube.txt")
        port: Port number from filter (e.g., "443")
        args: Full argument string for this block (including filter and strategy args)
        strategy_args: Just the strategy part (--lua-desync=... or --dpi-desync=...)
        syndata_dict: Parsed syndata/send/out-range parameters (optional)
    """
    category: str
    protocol: str  # "tcp" or "udp"
    filter_mode: str  # "hostlist" or "ipset"
    filter_file: str  # "youtube.txt"
    port: str  # "443"
    args: str  # Full args string for the block
    strategy_args: str = ""  # Just strategy part (--lua-desync=...)
    syndata_dict: Optional[Dict] = None  # Parsed syndata/send/out-range

    def get_key(self) -> str:
        """Returns unique key for this block: category:protocol"""
        return f"{self.category}:{self.protocol}"


@dataclass
class PresetData:
    """
    Represents parsed preset file data.

    Attributes:
        name: Preset name from # Preset: line
        active_preset: Active preset name from # ActivePreset: line (for preset-zapret2.txt)
        base_args: Arguments before first --filter-* (lua-init, wf-*, blob=*)
        categories: List of category blocks
        raw_header: Raw header lines (comments at start)
    """
    name: str = "Unnamed"
    active_preset: Optional[str] = None
    base_args: str = ""
    categories: List[CategoryBlock] = field(default_factory=list)
    raw_header: str = ""

    def get_category_block(self, category: str, protocol: str = "tcp") -> Optional[CategoryBlock]:
        """
        Finds category block by category name and protocol.

        Args:
            category: Category name (e.g., "youtube")
            protocol: "tcp" or "udp"

        Returns:
            CategoryBlock if found, None otherwise
        """
        for block in self.categories:
            if block.category == category and block.protocol == protocol:
                return block
        return None

    def get_all_categories(self) -> List[str]:
        """Returns list of unique category names"""
        return list(set(block.category for block in self.categories))

    def has_category(self, category: str) -> bool:
        """Checks if preset has this category (any protocol)"""
        return any(block.category == category for block in self.categories)

    def deduplicate_categories(self) -> None:
        """
        Removes duplicate category blocks from the list.

        Uses category:protocol as unique key. If duplicates exist,
        keeps the LAST occurrence (most recent update).

        Example:
            Before: [youtube:tcp, discord:tcp, youtube:tcp]
            After:  [discord:tcp, youtube:tcp]
        """
        seen = {}  # key -> index
        unique_blocks = []

        for block in self.categories:
            key = block.get_key()  # "category:protocol"

            # If we've seen this key before, remove the old one
            if key in seen:
                # Replace old block with new one
                old_index = seen[key]
                unique_blocks[old_index] = None  # Mark for removal

            # Add new block
            seen[key] = len(unique_blocks)
            unique_blocks.append(block)

        # Filter out None entries (replaced blocks)
        self.categories = [b for b in unique_blocks if b is not None]


def extract_category_from_args(args: str) -> Tuple[str, str, str]:
    """
    Extracts category name, filter mode and filter file from args.

    Supports:
    - --hostlist=youtube.txt -> ("youtube", "hostlist", "youtube.txt")
    - --hostlist=youtube-hosts.txt -> ("youtube", "hostlist", "youtube-hosts.txt")
    - --ipset=discord.txt -> ("discord", "ipset", "discord.txt")
    - --hostlist=lists/youtube.txt -> ("youtube", "hostlist", "lists/youtube.txt")

    Args:
        args: Argument string to parse

    Returns:
        Tuple of (category, filter_mode, filter_file) or ("unknown", "", "")
    """
    # Match --hostlist=path/file.txt or --ipset=path/file.txt
    # Extract just the filename part for category detection
    match = re.search(r'--(hostlist|ipset)=([^\s]+)', args)
    if not match:
        # Fallback to domain or IP filters without file paths
        domains_match = re.search(r'--hostlist-domains=([^\s]+)', args)
        if domains_match:
            return ("unknown", "hostlist", domains_match.group(1))
        ipset_ip_match = re.search(r'--ipset-ip=([^\s]+)', args)
        if ipset_ip_match:
            return ("unknown", "ipset", ipset_ip_match.group(1))
        return ("unknown", "", "")

    filter_mode = match.group(1)  # "hostlist" or "ipset"
    filter_path = match.group(2)  # full path or just filename

    # Get just the filename (remove path)
    # Path() on non-Windows does not treat backslashes as separators,
    # so we must handle Windows paths explicitly.
    filter_file = PureWindowsPath(filter_path).name

    # Extract category from filename (remove extension and common suffixes)
    # youtube.txt -> youtube
    # youtube-hosts.txt -> youtube
    # discord-ips.txt -> discord
    base_name = Path(filter_file).stem  # Remove .txt

    # Remove common suffixes
    suffixes_to_remove = ['-hosts', '-ips', '-ipset', '-hostlist', '_hosts', '_ips']
    category = base_name
    for suffix in suffixes_to_remove:
        if category.endswith(suffix):
            category = category[:-len(suffix)]
            break

    # Remove ipset- prefix (common for ipset files)
    # e.g., ipset-youtube.txt -> youtube
    if category.startswith('ipset-'):
        category = category[6:]  # Remove 'ipset-'

    return (category.lower(), filter_mode, filter_path)


def extract_categories_from_args(args: str) -> List[Tuple[str, str, str]]:
    """
    Extracts all categories referenced by --hostlist= / --ipset= selectors.

    Keeps original order and removes exact duplicates.
    """
    out: List[Tuple[str, str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()

    for mode, value in re.findall(r'--(hostlist|ipset)=([^\s]+)', args):
        cat, filter_mode, filter_file = extract_category_from_args(f"--{mode}={value}")
        item = (cat, filter_mode, filter_file)
        if item in seen:
            continue
        seen.add(item)
        out.append(item)

    return out


def _extract_selector_context_tokens(args: str, *, filter_mode: str) -> List[str]:
    """
    Extracts context tokens for canonical category inference of one selector.

    For multi-selector blocks we resolve each `--hostlist=` / `--ipset=` entry
    separately. Keep transport filters and matching *-exclude selectors so
    infer_category_key_from_args() can map aliases (e.g. twitch -> twitch_tcp).
    """
    selector_mode = (filter_mode or "hostlist").strip().lower() or "hostlist"
    wanted_exclude = "--hostlist-exclude=" if selector_mode == "hostlist" else "--ipset-exclude="

    tokens: List[str] = []
    seen: Set[str] = set()
    for token in re.findall(r"--[^\s]+", args or ""):
        token = token.strip()
        if not token:
            continue

        token_l = token.lower()
        keep = (
            token_l.startswith("--filter-tcp=")
            or token_l.startswith("--filter-udp=")
            or token_l.startswith("--filter-l7=")
            or token_l.startswith("--payload=")
            or token_l.startswith(wanted_exclude)
        )

        if not keep or token in seen:
            continue

        seen.add(token)
        tokens.append(token)

    return tokens


def _canonicalize_list_category_key(
    *,
    category_key: str,
    filter_mode: str,
    filter_file: str,
    protocol_hint: str,
    block_args: str,
) -> str:
    """
    Resolves list-derived category aliases to canonical keys from categories.txt.

    Examples:
      - twitch -> twitch_tcp
      - discord -> discord_tcp
      - roblox + udp filter -> roblox_udp
    """
    normalized_key = _normalize_category_key(category_key)
    if not normalized_key:
        return "unknown"

    categories_info = _load_category_info() or {}

    # Already canonical.
    if normalized_key in categories_info:
        return normalized_key

    # Fast path for common `<name>_<protocol>` category keys.
    protocol_n = str(protocol_hint or "").strip().lower()
    if protocol_n in ("tcp", "udp"):
        protocol_candidate = f"{normalized_key}_{protocol_n}"
        if protocol_candidate in categories_info:
            return protocol_candidate

    # Fallback: infer by block transport context + this exact selector.
    selector_mode = (filter_mode or "hostlist").strip().lower() or "hostlist"
    selector_value = str(filter_file or "").strip()

    synthetic_tokens = _extract_selector_context_tokens(block_args, filter_mode=selector_mode)
    if selector_value:
        synthetic_tokens.append(f"--{selector_mode}={selector_value}")

    if synthetic_tokens:
        inferred_key, _inferred_mode = infer_category_key_from_args("\n".join(synthetic_tokens))
        if inferred_key != "unknown":
            return inferred_key

    return normalized_key


_WINDOWS_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\\\/]|\\\\\\\\)")


def _is_windows_abs(path: str) -> bool:
    return bool(_WINDOWS_ABS_RE.match(path))


def _normalize_path_value_for_preset(
    value: str,
    *,
    main_directory: str,
    folder_root: str,
    default_subdir: str,
) -> str:
    """
    Normalizes known file path values for winws2 preset files.

    Goal: keep preset portable by storing paths relative to app working dir
    (e.g. `lists/...`, `bin/...`) when the path points inside the app folder.
    """
    raw = (value or "").strip()
    if not raw:
        return value

    at_prefix = "@" if raw.startswith("@") else ""
    if at_prefix:
        raw = raw[1:]

    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return value

    # Absolute: try to relativize to folder_root or MAIN_DIRECTORY.
    if _is_windows_abs(raw) or Path(raw).is_absolute():
        try:
            rel_folder = PureWindowsPath(raw).relative_to(PureWindowsPath(folder_root))
        except Exception:
            rel_folder = None

        if rel_folder is not None:
            return f"{at_prefix}{default_subdir}/{rel_folder.as_posix()}"

        try:
            rel_main = PureWindowsPath(raw).relative_to(PureWindowsPath(main_directory))
        except Exception:
            rel_main = None

        if rel_main is not None:
            return f"{at_prefix}{rel_main.as_posix()}"

        return f"{at_prefix}{str(PureWindowsPath(raw))}"

    # Relative with explicit folders: normalize separators to `/`.
    if "/" in raw or "\\" in raw:
        return f"{at_prefix}{PureWindowsPath(raw).as_posix()}"

    # Bare filename -> assume default_subdir/.
    return f"{at_prefix}{default_subdir}/{raw}"


def _should_normalize_bin_value(value: str) -> bool:
    """Returns True only for values that are actual *.bin file references."""
    raw = (value or "").strip()
    if not raw:
        return False

    if raw.startswith("@"):
        raw = raw[1:]

    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return False

    lowered = raw.lower()
    # Inline payload/modifier values are NOT paths.
    if lowered.startswith("0x") or lowered.startswith("!") or lowered.startswith("^"):
        return False

    # Only *.bin should be normalized into bin/... paths.
    return lowered.endswith(".bin")


def _normalize_known_path_line(line: str) -> str:
    """
    Normalizes specific known args that contain file paths.

    This is intentionally conservative: only rewrites options where a value is
    expected to be a file path.
    """
    try:
        from config import MAIN_DIRECTORY, LISTS_FOLDER, BIN_FOLDER

        main_directory = MAIN_DIRECTORY
        lists_folder = LISTS_FOLDER
        bin_folder = BIN_FOLDER
    except Exception:
        return line

    key, sep, value = line.partition("=")
    if not sep:
        return line

    key_l = key.strip().lower()

    if key_l in ("--hostlist", "--ipset", "--hostlist-exclude", "--ipset-exclude"):
        norm_value = _normalize_path_value_for_preset(
            value,
            main_directory=main_directory,
            folder_root=lists_folder,
            default_subdir="lists",
        )
        return f"{key.strip()}={norm_value}"

    if key_l in (
        "--dpi-desync-fake-syndata",
        "--dpi-desync-fake-tls",
        "--dpi-desync-fake-quic",
        "--dpi-desync-split-seqovl-pattern",
    ):
        if not _should_normalize_bin_value(value):
            return line
        norm_value = _normalize_path_value_for_preset(
            value,
            main_directory=main_directory,
            folder_root=bin_folder,
            default_subdir="bin",
        )
        return f"{key.strip()}={norm_value}"

    return line


def _normalize_ports(value: str) -> str:
    tokens = [t.strip() for t in value.split(',') if t.strip()]
    normalized = []
    for token in tokens:
        if token == "*":
            normalized.append("*")
            continue
        if "-" in token:
            start, end = token.split("-", 1)
            if start.isdigit() and end.isdigit():
                normalized.append(f"{int(start)}-{int(end)}")
                continue
        if token.isdigit():
            normalized.append(str(int(token)))
            continue
        normalized.append(token)

    def _sort_key(item: str) -> tuple:
        if item == "*":
            return (2, 0, 0, item)
        if "-" in item:
            start, end = item.split("-", 1)
            if start.isdigit() and end.isdigit():
                return (1, int(start), int(end), item)
        if item.isdigit():
            return (0, int(item), 0, item)
        return (3, 0, 0, item)

    normalized.sort(key=_sort_key)
    return ",".join(normalized)


def _normalize_csv(value: str) -> str:
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    parts.sort()
    return ",".join(parts)


def _normalize_filter_token(token: str) -> str:
    token = token.strip()
    if not token.startswith("--"):
        return ""

    key, sep, value = token.partition("=")
    key = key.lower()
    value = value.strip().strip('"').strip("'")
    if value.startswith("@"):
        value = value[1:]

    if key in ("--filter-tcp", "--filter-udp"):
        if not sep:
            return key
        return f"{key}={_normalize_ports(value)}"
    if key == "--filter-l7":
        if not sep:
            return key
        return f"{key}={_normalize_csv(value)}"
    if key in ("--hostlist", "--ipset", "--hostlist-exclude", "--ipset-exclude"):
        if not sep:
            return key
        return f"{key}={PureWindowsPath(value).name}"
    if key in ("--hostlist-domains", "--ipset-ip", "--payload"):
        if not sep:
            return key
        return f"{key}={_normalize_csv(value)}"

    return ""


def _extract_filter_tokens(args: str) -> List[str]:
    tokens = []
    for raw in re.split(r"\s+", args.strip()):
        if not raw:
            continue
        normalized = _normalize_filter_token(raw)
        if normalized:
            tokens.append(normalized)
    return tokens


def _load_category_filters(*, force_reload: bool = False) -> Dict[str, List[Tuple[str, Set[str]]]]:
    global _CATEGORY_FILTER_CACHE
    if not force_reload and _CATEGORY_FILTER_CACHE is not None:
        return _CATEGORY_FILTER_CACHE

    try:
        from .catalog import load_categories
        categories = load_categories()
    except Exception as e:
        log(f"Category filters unavailable: {e}", "DEBUG")
        categories = {}

    filters: Dict[str, List[Tuple[str, Set[str]]]] = {}
    for key, data in categories.items():
        variants: List[Tuple[str, set[str]]] = []
        for mode_key, mode_name in (
            ("base_filter", "base"),
            ("base_filter_ipset", "ipset"),
            ("base_filter_hostlist", "hostlist"),
        ):
            raw = data.get(mode_key)
            if not raw:
                continue
            token_set = set(_extract_filter_tokens(raw))
            if token_set:
                variants.append((mode_name, token_set))
        if variants:
            filters[key] = variants

    _CATEGORY_FILTER_CACHE = filters
    return _CATEGORY_FILTER_CACHE


def _load_category_info(*, force_reload: bool = False) -> Dict[str, Dict]:
    global _CATEGORY_INFO_CACHE
    if not force_reload and _CATEGORY_INFO_CACHE is not None:
        return _CATEGORY_INFO_CACHE

    try:
        from .catalog import load_categories
        _CATEGORY_INFO_CACHE = load_categories()
    except Exception as e:
        log(f"Category info unavailable: {e}", "DEBUG")
        _CATEGORY_INFO_CACHE = {}

    return _CATEGORY_INFO_CACHE


def infer_category_key_from_args(args: str) -> Tuple[str, Optional[str]]:
    tokens = set(_extract_filter_tokens(args))
    if not tokens:
        return ("unknown", None)

    # Domain/IP based blocks can't be categorized by filename, so if categories
    # were changed during runtime (user_categories.txt), stale caches would
    # incorrectly return "unknown". Prefer a fresh view for these blocks.
    needs_fresh = any(
        t.startswith("--hostlist-domains=") or t.startswith("--ipset-ip=")
        for t in tokens
    )

    filters = _load_category_filters(force_reload=needs_fresh)
    if not filters:
        return ("unknown", None)

    mode_priority = {"ipset": 2, "hostlist": 1, "base": 0}
    user_key_re = re.compile(r"^user_category_(\d+)$")

    def _user_rank(key: str) -> tuple[int, int]:
        """
        Prefer user_category_N when matching is ambiguous.
        This prevents user categories from being mis-detected as built-ins when they share the same filter tokens.
        """
        m = user_key_re.fullmatch(str(key or "").strip().lower())
        if not m:
            return (1, 10**9)
        try:
            return (0, int(m.group(1)))
        except Exception:
            return (0, 10**9)

    matches = []
    for key in sorted(filters.keys()):
        for mode, base_tokens in filters[key]:
            if base_tokens and base_tokens.issubset(tokens):
                matches.append((len(base_tokens), mode_priority.get(mode, -1), _user_rank(key), key, mode))

    if not matches:
        # One more retry: categories may have changed without cache invalidation
        # (e.g., user added/edited a user category).
        if not needs_fresh:
            invalidate_category_inference_cache()
            filters = _load_category_filters(force_reload=True)
            if filters:
                for key in sorted(filters.keys()):
                    for mode, base_tokens in filters[key]:
                        if base_tokens and base_tokens.issubset(tokens):
                            matches.append((len(base_tokens), mode_priority.get(mode, -1), _user_rank(key), key, mode))
        if not matches:
            return ("unknown", None)

    matches.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    best_score, best_priority, best_user_rank, best_key, best_mode = matches[0]

    if len(matches) > 1:
        second = matches[1]
        if second[0] == best_score and second[1] == best_priority and second[3] != best_key:
            log(f"Ambiguous category match for filters: {best_key} vs {second[3]}", "DEBUG")

    return (best_key, best_mode)


def extract_protocol_and_port(args: str) -> Tuple[str, str]:
    """
    Extracts protocol and port from filter args.

    Args:
        args: Argument string

    Returns:
        Tuple of (protocol, port) - e.g., ("tcp", "443") or ("udp", "443")
    """
    # Check for --filter-tcp=port or --filter-udp=port
    # Support single port (443) or multiple ports (80,443)
    tcp_match = re.search(r'--filter-tcp=([\d,\-\*]+)', args)
    if tcp_match:
        return ("tcp", tcp_match.group(1))

    udp_match = re.search(r'--filter-udp=([\d,\-\*]+)', args)
    if udp_match:
        return ("udp", udp_match.group(1))

    # L7 filters (treated as UDP-like in the preset system)
    l7_match = re.search(r'--filter-l7=([^\s\n]+)', args)
    if l7_match:
        return ("udp", l7_match.group(1))

    return ("tcp", "443")  # Default


def extract_strategy_args(
    args: str,
    *,
    category_key: Optional[str] = None,
    filter_mode: Optional[str] = None,
) -> str:
    """
    Extracts just the strategy arguments from block args.

    Removes --filter-*, --hostlist=*, --ipset=* to get just the strategy.

    Args:
        args: Full block arguments

    Returns:
        Strategy arguments only (e.g., "--lua-desync=multisplit:pos=1,midsld")
    """
    base_filter_tokens: Set[str] = set()
    try:
        category_key_n = (category_key or "").strip().lower()
        if category_key_n and category_key_n != "unknown":
            filters = _load_category_filters()
            variants = filters.get(category_key_n) if filters else None
            if variants:
                want = (filter_mode or "").strip().lower()
                # Prefer exact mode match; fallback to any variant for this category.
                for mode, token_set in variants:
                    if want and mode == want:
                        base_filter_tokens = set(token_set)
                        break
                if not base_filter_tokens:
                    base_filter_tokens = set(variants[0][1])
    except Exception:
        base_filter_tokens = set()

    tokens = re.findall(r"--[^\s]+", args or "")
    strategy_tokens = []

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        token = re.sub(r':strategy=\d+', '', token)

        # Skip tokens that are part of category base_filter (important for L7 payload filters),
        # otherwise they accumulate on each preset sync.
        try:
            normalized = _normalize_filter_token(token)
        except Exception:
            normalized = ""
        if base_filter_tokens and normalized and normalized in base_filter_tokens:
            continue

        token_l = token.lower()
        # Skip filter/list selector tokens and non-strategy transport helpers.
        if token_l.startswith(_FILTER_SELECTOR_PREFIXES):
            continue
        if token_l.startswith('--out-range'):
            continue
        if token_l.startswith('--lua-desync=syndata:') or \
           token_l == '--lua-desync=syndata' or \
           token_l.startswith('--lua-desync=send:') or \
           token_l == '--lua-desync=send':
            continue

        strategy_tokens.append(token)

    return '\n'.join(strategy_tokens)


def extract_syndata_from_args(args: str) -> Dict:
    """
    Extracts syndata parameters from format: --lua-desync=syndata:blob=value:ip_autottl=-2,3-20

    Args:
        args: Argument string to parse

    Returns:
        Dict with syndata parameters. If the `--lua-desync=syndata:` line is absent,
        returns `{"enabled": False}`.
    """
    result = {'enabled': False}

    # Format: --lua-desync=syndata:blob=tls_google:ip_autottl=-2,3-20
    match = re.search(r'--lua-desync=syndata:([^\s\n]+)', args)
    if match:
        result['enabled'] = True
        syndata_str = match.group(1)
        # Format: blob=tls_google:ip_autottl=-2,3-20:tls_mod=value
        parts = syndata_str.split(':')
        saw_autottl = False

        for part in parts:
            if '=' not in part:
                continue
            key, value = part.split('=', 1)

            if key == 'blob':
                result['blob'] = value
            elif key == 'tls_mod':
                result['tls_mod'] = value
            elif key == 'ip_autottl':
                saw_autottl = True
                # Format: -2,3-20 (delta,min-max)
                autottl_match = re.match(r'(-?\d+),(\d+)-(\d+)', value)
                if autottl_match:
                    result['autottl_delta'] = int(autottl_match.group(1))
                    result['autottl_min'] = int(autottl_match.group(2))
                    result['autottl_max'] = int(autottl_match.group(3))
            elif key == 'tcp_flags_unset':
                result['tcp_flags_unset'] = value

        # OFF is represented by omitting `ip_autottl` from the syndata line
        # (see CategoryConfig._get_syndata_args). Preserve that as delta=0 so UI
        # does not snap back to defaults after active-file reload.
        if not saw_autottl:
            result['autottl_delta'] = 0

        return result

    return result


def extract_out_range_from_args(args: str) -> Dict:
    """
    Extracts --out-range=-n8 or --out-range=-d100

    Args:
        args: Argument string to parse

    Returns:
        Dict with out_range parameters (empty if not found)
    """
    match = re.search(r'--out-range=-([nd])(\d+)', args)
    if not match:
        return {}

    mode = match.group(1) or "n"
    value = int(match.group(2))

    return {
        'out_range': value,
        'out_range_mode': mode
    }


def extract_send_from_args(args: str) -> Dict:
    """
    Extracts send parameters from format: --lua-desync=send:repeats=2:ttl=0

    Args:
        args: Argument string to parse

    Returns:
        Dict with send parameters. If the `--lua-desync=send:` line is absent,
        returns `{"send_enabled": False}`.
    """
    result = {'send_enabled': False}

    # Format: --lua-desync=send:repeats=2:ttl=0
    match = re.search(r'--lua-desync=send:([^\s\n]+)', args)
    if match:
        result['send_enabled'] = True
        send_str = match.group(1)
        # Format: repeats=2:ttl=0:badsum=true
        parts = send_str.split(':')

        for part in parts:
            if '=' not in part:
                continue
            key, value = part.split('=', 1)

            if key == 'repeats':
                result['send_repeats'] = int(value)
            elif key == 'ttl':
                result['send_ip_ttl'] = int(value)
            elif key == 'ttl6':
                result['send_ip6_ttl'] = int(value)
            elif key == 'ip_id':
                result['send_ip_id'] = value
            elif key == 'badsum':
                result['send_badsum'] = value.lower() == 'true'

        return result

    return result


def parse_preset_file(file_path: Path) -> PresetData:
    """
    Parses txt preset file into PresetData structure.

    File format:
    ```
    # Preset: My Config
    # ActivePreset: my_config

    --lua-init=@lua/zapret-lib.lua
    --wf-tcp-out=443
    --blob=tls7:@bin/tls_clienthello_7.bin

    --filter-tcp=443
    --hostlist=youtube.txt
    --lua-desync=multisplit:pos=1,midsld

    --new

    --filter-udp=443
    --hostlist=youtube.txt
    --lua-desync=fake:blob=quic1
    ```

    Args:
        file_path: Path to preset file

    Returns:
        PresetData with parsed content

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Preset file not found: {file_path}")

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        log(f"Error reading preset file {file_path}: {e}", "ERROR")
        raise

    return parse_preset_content(content)


def parse_preset_content(content: str) -> PresetData:
    """
    Parses preset content string into PresetData.

    Args:
        content: Raw preset file content

    Returns:
        PresetData with parsed content
    """
    data = PresetData()

    lines = content.split('\n')

    # Phase 1: Parse header comments
    header_lines = []
    content_start_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#'):
            header_lines.append(line)

            # Extract preset name
            name_match = re.match(r'#\s*Preset:\s*(.+)', stripped, re.IGNORECASE)
            if name_match:
                data.name = name_match.group(1).strip()

            # Extract active preset
            active_match = re.match(r'#\s*ActivePreset:\s*(.+)', stripped, re.IGNORECASE)
            if active_match:
                data.active_preset = active_match.group(1).strip()

            # Also check "Strategy:" for compatibility
            strategy_match = re.match(r'#\s*Strategy:\s*(.+)', stripped, re.IGNORECASE)
            if strategy_match and data.name == "Unnamed":
                data.name = strategy_match.group(1).strip()


        elif stripped:
            # First non-comment, non-empty line
            content_start_idx = i
            break
        else:
            # Empty line in header
            header_lines.append(line)
            content_start_idx = i + 1

    data.raw_header = '\n'.join(header_lines)

    # Phase 2: Split into base_args and category blocks
    # Base args = everything before first category marker
    # Category blocks = separated by --new

    remaining_lines = lines[content_start_idx:]

    # Find first category marker to split base_args.
    # Some custom blocks may start with --hostlist/--ipset before --filter-*.
    first_block_idx = None
    for i, line in enumerate(remaining_lines):
        stripped = line.strip().lower()
        if stripped.startswith(_CATEGORY_BLOCK_START_PREFIXES):
            first_block_idx = i
            break

    if first_block_idx is None:
        # No category blocks, all is base_args
        data.base_args = '\n'.join(line for line in remaining_lines if line.strip())
        return data

    # Split base_args
    base_lines = remaining_lines[:first_block_idx]
    data.base_args = '\n'.join(line.strip() for line in base_lines if line.strip())

    # Phase 3: Parse category blocks
    block_lines = remaining_lines[first_block_idx:]

    # Split by --new
    blocks_raw = []
    current_block = []

    for line in block_lines:
        stripped = line.strip()
        if stripped == '--new':
            if current_block:
                blocks_raw.append(current_block)
                current_block = []
        elif stripped and not stripped.startswith('#'):  # Ignore comments
            current_block.append(stripped)

    # Don't forget last block
    if current_block:
        blocks_raw.append(current_block)

    # Parse each block
    for block_lines_list in blocks_raw:
        block_args = '\n'.join(block_lines_list)

        # Skip blocks without any selectors or port filters (empty/junk blocks)
        has_selectors = bool(re.search(r'--(hostlist|ipset|hostlist-domains|ipset-ip)=', block_args))
        has_filter = bool(re.search(r'--filter-(tcp|udp|l7)=', block_args))
        if not has_selectors and not has_filter:
            continue

        base_protocol, base_port = extract_protocol_and_port(block_args)
        has_port_filter = has_filter

        # Extract category info
        categories_from_lists = extract_categories_from_args(block_args)
        category, filter_mode, filter_file = extract_category_from_args(block_args)
        inferred_category, inferred_mode = infer_category_key_from_args(block_args)
        category_entries: List[Tuple[str, str, str]] = []

        if categories_from_lists:
            for list_category, list_mode, list_file in categories_from_lists:
                mode = (list_mode or "hostlist").strip().lower() or "hostlist"
                canonical_key = _canonicalize_list_category_key(
                    category_key=list_category,
                    filter_mode=mode,
                    filter_file=list_file,
                    protocol_hint=base_protocol,
                    block_args=block_args,
                )
                category_entries.append((canonical_key, mode, list_file))

            # Filter out unknown categories (not in categories.txt)
            # Skip filtering if categories catalog is unavailable (e.g., in tests)
            categories_info = _load_category_info() or {}
            if categories_info:
                category_entries = [
                    (key, mode, file) for key, mode, file in category_entries
                    if key in categories_info
                ]
                if not category_entries:
                    continue
        else:
            if inferred_category != "unknown":
                category = inferred_category
                if not filter_mode and inferred_mode in ("ipset", "hostlist"):
                    filter_mode = inferred_mode
            if not filter_mode:
                filter_mode = "hostlist"
            category_entries.append((category, filter_mode, filter_file))

        for category_key, category_mode, category_file in category_entries:
            if not category_mode:
                category_mode = "hostlist"

            # Exclude base_filter tokens (including --payload for L7 categories) from strategy_args,
            # otherwise they accumulate on each sync and blow up the preset file.
            strategy_args = extract_strategy_args(
                block_args,
                category_key=category_key,
                filter_mode=category_mode,
            )

            protocol = base_protocol
            port = base_port
            if category_key != "unknown" and not has_port_filter:
                cat_info = _load_category_info().get(category_key)
                if cat_info:
                    proto_raw = str(cat_info.get("protocol", "")).upper()
                    if "UDP" in proto_raw or "QUIC" in proto_raw or "L7" in proto_raw:
                        protocol = "udp"
                    elif proto_raw:
                        protocol = "tcp"
                    ports_raw = cat_info.get("ports")
                    if ports_raw:
                        port = str(ports_raw).strip()

            # Extract syndata/send/out-range parameters.
            # NOTE: syndata/send are TCP-only (SYN-based). For UDP/QUIC we intentionally ignore them.
            syndata_dict = {}
            syndata_dict.update(extract_out_range_from_args(block_args))
            if protocol == "tcp":
                syndata_dict.update(extract_syndata_from_args(block_args))
                syndata_dict.update(extract_send_from_args(block_args))

                # Clean up: if autottl is already present in a separate syndata line,
                # strip redundant `:ip_autottl=...` fragments from strategy lines.
                if syndata_dict.get("autottl_delta") is not None and \
                   syndata_dict.get("autottl_min") is not None and \
                   syndata_dict.get("autottl_max") is not None and strategy_args:
                    autottl_str = f"{syndata_dict['autottl_delta']},{syndata_dict['autottl_min']}-{syndata_dict['autottl_max']}"
                    # Only strip exact matches to avoid breaking strategies that intentionally differ.
                    strategy_args = re.sub(rf":ip_autottl={re.escape(autottl_str)}(?=(:|$))", "", strategy_args)
                    strategy_args = re.sub(rf":ip6_autottl={re.escape(autottl_str)}(?=(:|$))", "", strategy_args)

            block = CategoryBlock(
                category=category_key,
                protocol=protocol,
                filter_mode=category_mode,
                filter_file=category_file,
                port=port,
                args=block_args,
                strategy_args=strategy_args,
                syndata_dict=syndata_dict if syndata_dict else None
            )

            data.categories.append(block)

    # Deduplicate in case file already contains duplicates
    data.deduplicate_categories()

    return data


def generate_preset_content(data: PresetData, include_header: bool = True) -> str:
    """
    Generates preset file content from PresetData.

    Args:
        data: PresetData structure
        include_header: Whether to include header comments

    Returns:
        Generated preset file content
    """
    lines = []

    # Header
    if include_header:
        if isinstance(getattr(data, "raw_header", None), str) and data.raw_header.strip():
            # If caller provided a raw header, preserve it as-is.
            # This is important for Created/Modified/Description metadata which some writers embed.
            lines.extend(data.raw_header.rstrip("\n").splitlines())
            if not lines or lines[-1].strip():
                lines.append("")
        else:
            lines.append(f"# Preset: {data.name}")
            if data.active_preset:
                lines.append(f"# ActivePreset: {data.active_preset}")

            lines.append("")

    # Base args
    if data.base_args:
        for line in data.base_args.split('\n'):
            if line.strip():
                lines.append(_normalize_known_path_line(line.strip()))
        lines.append("")

    # Category blocks (stable ordering by categories.txt)
    blocks = _drop_placeholder_unknown_categories(list(data.categories))
    try:
        from .catalog import load_categories

        categories_info = load_categories()

        def _key(item: tuple[int, CategoryBlock]) -> tuple:
            idx, block = item
            proto = (block.protocol or "").lower()
            proto_rank = 0 if proto == "tcp" else (1 if proto == "udp" else 2)

            # Custom user categories must come first in the preset to have priority.
            # The GUI generates keys as `user_category_N`.
            cat_key = str(block.category or "").strip().lower()
            info = categories_info.get(cat_key) if categories_info else None
            try:
                is_user_cat = re.fullmatch(r"user_category_(\d+)", cat_key) is not None
            except Exception:
                is_user_cat = False

            if info:
                file_order = info.get("_file_order")
                try:
                    file_i = int(file_order) if file_order is not None else 999999
                except Exception:
                    file_i = 999999
            else:
                file_i = 999999

            if is_user_cat:
                return (0, file_i, proto_rank, block.category, idx)

            if info:
                # Categories are ordered strictly by section appearance in categories.txt.
                return (1, file_i, proto_rank, block.category, idx)

            # Unknown categories: keep original relative order, but after known ones.
            return (2, 999999, proto_rank, idx)

        blocks = [b for _, b in sorted(enumerate(blocks), key=_key)]
    except Exception:
        pass

    for i, block in enumerate(blocks):
        # Add block args
        for line in block.args.split('\n'):
            if line.strip():
                lines.append(_normalize_known_path_line(line.strip()))

        # Add --new separator (except for last block)
        if i < len(blocks) - 1:
            lines.append("")
            lines.append("--new")
            lines.append("")

    return '\n'.join(lines)


def generate_preset_file(data: PresetData, output_path: Path, atomic: bool = True) -> bool:
    """
    Generates and writes preset file from PresetData.

    Uses atomic write (temp file + rename) for safety.

    Args:
        data: PresetData structure
        output_path: Path to write file
        atomic: Use atomic write (temp + rename)

    Returns:
        True if successful
    """
    import os
    import tempfile
    import time

    output_path = Path(output_path)
    content = generate_preset_content(data)

    try:
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            # Atomic write: write to temp file, then rename
            fd, temp_path = tempfile.mkstemp(
                suffix='.txt',
                prefix='preset_',
                dir=output_path.parent
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Atomic replace: safe even if target exists.
                try:
                    os.replace(temp_path, output_path)
                except PermissionError as e:
                    # Windows: destination may be locked briefly (winws2 / watcher).
                    # Retry a bit, then fall back to direct in-place write.
                    if os.name != "nt":
                        raise

                    last_exc = e
                    delay = 0.03
                    for _attempt in range(15):
                        time.sleep(delay)
                        try:
                            os.replace(temp_path, output_path)
                            last_exc = None
                            break
                        except PermissionError as e2:
                            last_exc = e2
                            delay = min(delay * 1.6, 0.2)

                    if last_exc is not None:
                        # Best-effort: write directly to destination.
                        output_path.write_text(content, encoding='utf-8')
                        try:
                            if os.path.exists(temp_path):
                                os.unlink(temp_path)
                        except Exception:
                            pass
                        try:
                            log(f"Atomic replace blocked; wrote preset file in-place: {output_path}", "DEBUG")
                        except Exception:
                            pass

            except Exception:
                # Cleanup temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        else:
            # Direct write
            output_path.write_text(content, encoding='utf-8')

        log(f"Preset file written: {output_path}", "DEBUG")
        return True

    except Exception as e:
        log(f"Error writing preset file {output_path}: {e}", "ERROR")
        return False


def update_category_in_preset(
    file_path: Path,
    category: str,
    protocol: str,
    new_strategy_args: str
) -> bool:
    """
    Updates strategy arguments for a specific category in preset file.

    Preserves file structure, only modifies the strategy args for the category.

    Args:
        file_path: Path to preset file
        category: Category name (e.g., "youtube")
        protocol: "tcp" or "udp"
        new_strategy_args: New strategy arguments

    Returns:
        True if updated successfully
    """
    try:
        data = parse_preset_file(file_path)

        # Find the block
        block = data.get_category_block(category, protocol)
        if not block:
            log(f"Category {category}:{protocol} not found in preset", "WARNING")
            return False

        # Preserve everything in the block, only replace "strategy" lines.
        # This avoids silently dropping advanced lines like:
        # --out-range, --lua-desync=send, --lua-desync=syndata, --payload, etc.
        existing_lines = [ln.strip() for ln in (block.args or "").splitlines() if ln.strip()]

        old_strategy = extract_strategy_args(
            block.args or "",
            category_key=block.category,
            filter_mode=block.filter_mode,
        )
        old_strategy_lines = [ln.strip() for ln in old_strategy.splitlines() if ln.strip()]
        old_set = set(old_strategy_lines)

        new_lines = [ln.strip() for ln in (new_strategy_args or "").splitlines() if ln.strip()]

        insert_at = None
        for i, ln in enumerate(existing_lines):
            if ln in old_set:
                insert_at = i
                break

        kept_lines = [ln for ln in existing_lines if ln not in old_set]

        if insert_at is None:
            insert_at = len(kept_lines)

        updated_lines = kept_lines[:insert_at] + new_lines + kept_lines[insert_at:]

        block.args = "\n".join(updated_lines)
        block.strategy_args = "\n".join(new_lines).strip()

        # Write back
        return generate_preset_file(data, file_path)

    except Exception as e:
        log(f"Error updating category in preset: {e}", "ERROR")
        return False
