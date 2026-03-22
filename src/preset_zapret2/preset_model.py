# preset_zapret2/preset_model.py
"""
Data models for preset system.

Preset = collection of category configurations with metadata.
Each category has TCP and/or UDP strategy arguments.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


DEFAULT_PRESET_ICON_COLOR = "#60cdff"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")


def normalize_preset_icon_color(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if _HEX_COLOR_RGB_RE.fullmatch(raw):
        return raw.lower()
    if _HEX_COLOR_RGBA_RE.fullmatch(raw):
        lowered = raw.lower()
        return f"#{lowered[1:7]}"
    return DEFAULT_PRESET_ICON_COLOR


@dataclass
class SyndataSettings:
    """
    Syndata/Send settings for a category.

    These control advanced DPI bypass parameters.
    """
    # Syndata parameters
    enabled: bool = True
    blob: str = "tls_google"
    tls_mod: str = "none"
    autottl_delta: int = 0
    autottl_min: int = 3
    autottl_max: int = 20
    out_range: int = 8
    out_range_mode: str = "n"  # "n" (packets count) or "d" (delay)
    tcp_flags_unset: str = "none"

    # Send parameters
    send_enabled: bool = True
    send_repeats: int = 2
    send_ip_ttl: int = 0
    send_ip6_ttl: int = 0
    send_ip_id: str = "none"
    send_badsum: bool = False

    def to_dict(self) -> Dict:
        """Converts to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "blob": self.blob,
            "tls_mod": self.tls_mod,
            "autottl_delta": self.autottl_delta,
            "autottl_min": self.autottl_min,
            "autottl_max": self.autottl_max,
            "out_range": self.out_range,
            "out_range_mode": self.out_range_mode,
            "tcp_flags_unset": self.tcp_flags_unset,
            "send_enabled": self.send_enabled,
            "send_repeats": self.send_repeats,
            "send_ip_ttl": self.send_ip_ttl,
            "send_ip6_ttl": self.send_ip6_ttl,
            "send_ip_id": self.send_ip_id,
            "send_badsum": self.send_badsum,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SyndataSettings":
        """Creates SyndataSettings from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            blob=data.get("blob", "tls_google"),
            tls_mod=data.get("tls_mod", "none"),
            autottl_delta=data.get("autottl_delta", 0),
            autottl_min=data.get("autottl_min", 3),
            autottl_max=data.get("autottl_max", 20),
            out_range=data.get("out_range", 8),
            out_range_mode=data.get("out_range_mode", "n"),
            tcp_flags_unset=data.get("tcp_flags_unset", "none"),
            send_enabled=data.get("send_enabled", True),
            send_repeats=data.get("send_repeats", 2),
            send_ip_ttl=data.get("send_ip_ttl", 0),
            send_ip6_ttl=data.get("send_ip6_ttl", 0),
            send_ip_id=data.get("send_ip_id", "none"),
            send_badsum=data.get("send_badsum", False),
        )

    @classmethod
    def get_defaults(cls) -> "SyndataSettings":
        """Returns default settings instance."""
        return cls()

    @classmethod
    def get_defaults_udp(cls) -> "SyndataSettings":
        """
        Defaults for UDP/QUIC/L7 categories.

        NOTE: syndata/send are TCP-only (SYN-based) and must be disabled for UDP.
        out_range is still used for UDP.
        """
        return cls(enabled=False, send_enabled=False)


@dataclass
class CategoryConfig:
    """
    Configuration for a single category (e.g., youtube, discord).

    A category can have separate TCP and UDP strategies.
    Strategy is identified by strategy_id (e.g., "youtube_tcp_split").
    Args are generated from strategy_id via strategies_registry.

    Attributes:
        name: Category name (e.g., "youtube", "discord")
        strategy_id: ID of selected strategy (e.g., "youtube_tcp_split", "none")
        tcp_args: TCP strategy arguments (e.g., "--lua-desync=multisplit:pos=1,midsld")
        udp_args: UDP strategy arguments (e.g., "--lua-desync=fake:blob=quic1")
        tcp_enabled: Whether TCP strategy is enabled
        udp_enabled: Whether UDP strategy is enabled
        filter_mode: "hostlist" or "ipset" - how domains are filtered
        tcp_port: Port for TCP filter (default "443")
        udp_port: Port for UDP filter (default "443")
        syndata: Syndata/Send settings for this category
        sort_order: Sort order for strategies list ("default", "name_asc", "name_desc")
    """
    name: str
    strategy_id: str = "none"  # ID of selected strategy
    tcp_args: str = ""
    udp_args: str = ""
    tcp_enabled: bool = True
    udp_enabled: bool = True
    filter_mode: str = "hostlist"  # "hostlist" or "ipset"
    filter_file: str = ""  # Original filter file path from preset (e.g., "lists/russia-youtube-rtmps.txt")
    tcp_port: str = "443"
    udp_port: str = "443"
    syndata_tcp: SyndataSettings = field(default_factory=SyndataSettings)
    syndata_udp: SyndataSettings = field(default_factory=SyndataSettings.get_defaults_udp)
    sort_order: str = "default"  # "default", "name_asc", "name_desc"

    def get_hostlist_file(self) -> str:
        """Returns hostlist filename for this category with relative path.

        If filter_file is set and filter_mode is hostlist, returns the original
        filter_file path. Otherwise falls back to generated path.
        """
        if self.filter_file and self.filter_mode == "hostlist":
            return self.filter_file
        return f"lists/{self.name}.txt"

    def get_ipset_file(self) -> str:
        """Returns ipset filename for this category with relative path.

        If filter_file is set and filter_mode is ipset, returns the original
        filter_file path. Otherwise falls back to generated path with ipset- prefix.
        """
        if self.filter_file and self.filter_mode == "ipset":
            return self.filter_file
        return f"lists/ipset-{self.name}.txt"

    def get_filter_file(self) -> str:
        """Returns filter file based on filter_mode.

        Uses original filter_file if available, otherwise falls back
        to generated paths.
        """
        if self.filter_file:
            return self.filter_file
        if self.filter_mode == "ipset":
            return f"lists/ipset-{self.name}.txt"
        return f"lists/{self.name}.txt"

    def has_tcp(self) -> bool:
        """Returns True if TCP strategy is configured."""
        return bool(self.tcp_args.strip())

    def has_udp(self) -> bool:
        """Returns True if UDP strategy is configured."""
        return bool(self.udp_args.strip())

    def get_full_tcp_args(self) -> str:
        """Возвращает полные TCP аргументы включая syndata/send/out-range

        Правильный порядок: out-range → send → syndata → strategy
        """
        parts = []

        # 1. Out-range
        out_range_arg = self._get_out_range_args(self.syndata_tcp)
        if out_range_arg:
            parts.append(out_range_arg)

        # 2. Send параметры
        if self.syndata_tcp.send_enabled:
            send_arg = self._get_send_args(self.syndata_tcp)
            if send_arg:
                parts.append(send_arg)

        # 3. Syndata параметры
        if self.syndata_tcp.enabled:
            syndata_arg = self._get_syndata_args(self.syndata_tcp)
            if syndata_arg:
                parts.append(syndata_arg)

        # 4. Базовые tcp_args (strategy)
        if self.tcp_args:
            parts.append(self.tcp_args)

        return "\n".join(parts)

    def get_full_udp_args(self) -> str:
        """Возвращает полные UDP аргументы включая out-range

        NOTE: syndata/send применяются только к TCP SYN, для UDP/QUIC не поддерживаются.

        Правильный порядок: out-range → strategy
        """
        parts = []

        # 1. Out-range
        out_range_arg = self._get_out_range_args(self.syndata_udp)
        if out_range_arg:
            parts.append(out_range_arg)

        # 2. Базовые udp_args (strategy)
        if self.udp_args:
            parts.append(self.udp_args)

        return "\n".join(parts)

    def _get_syndata_args(self, settings: SyndataSettings) -> str:
        """Генерирует --lua-desync=syndata:blob=...:ip_autottl=... из SyndataSettings"""
        if not settings.enabled:
            return ""

        parts = []
        parts.append(f"blob={settings.blob}")

        if settings.tls_mod != "none":
            parts.append(f"tls_mod={settings.tls_mod}")

        # ip_autottl формат: -2,3-20 (delta,min-max)
        if settings.autottl_delta != 0:
            autottl_str = f"{settings.autottl_delta},{settings.autottl_min}-{settings.autottl_max}"
            parts.append(f"ip_autottl={autottl_str}")

        if settings.tcp_flags_unset != "none":
            parts.append(f"tcp_flags_unset={settings.tcp_flags_unset}")

        return f"--lua-desync=syndata:{':'.join(parts)}"

    def _get_out_range_args(self, settings: SyndataSettings) -> str:
        """Генерирует --out-range=-n8 из SyndataSettings"""
        if settings.out_range == 0:
            return ""

        mode_suffix = "d" if settings.out_range_mode == "d" else "n"
        return f"--out-range=-{mode_suffix}{settings.out_range}"

    def _get_send_args(self, settings: SyndataSettings) -> str:
        """Генерирует --lua-desync=send:repeats=2:ttl=0 из SyndataSettings"""
        if not settings.send_enabled:
            return ""

        parts = []

        if settings.send_repeats != 0:
            parts.append(f"repeats={settings.send_repeats}")

        if settings.send_ip_ttl != 0:
            parts.append(f"ttl={settings.send_ip_ttl}")

        if settings.send_ip6_ttl != 0:
            parts.append(f"ttl6={settings.send_ip6_ttl}")

        if settings.send_ip_id != "none":
            parts.append(f"ip_id={settings.send_ip_id}")

        if settings.send_badsum:
            parts.append("badsum=true")

        if not parts:
            return ""

        return f"--lua-desync=send:{':'.join(parts)}"

    def to_dict(self) -> Dict:
        """Converts to dictionary for serialization."""
        d = {
            "name": self.name,
            "strategy_id": self.strategy_id,
            "tcp_args": self.tcp_args,
            "udp_args": self.udp_args,
            "tcp_enabled": self.tcp_enabled,
            "udp_enabled": self.udp_enabled,
            "filter_mode": self.filter_mode,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
            # Per-protocol advanced settings
            "syndata_tcp": self.syndata_tcp.to_dict(),
            "syndata_udp": self.syndata_udp.to_dict(),
            "sort_order": self.sort_order,
        }
        if self.filter_file:
            d["filter_file"] = self.filter_file
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "CategoryConfig":
        """Creates CategoryConfig from dictionary."""
        # Backward compatibility:
        # - older versions stored a single "syndata" dict (TCP-only in practice)
        syndata_tcp_data = data.get("syndata_tcp") or data.get("syndata") or {}
        syndata_tcp = SyndataSettings.from_dict(syndata_tcp_data) if syndata_tcp_data else SyndataSettings.get_defaults()

        syndata_udp_data = data.get("syndata_udp") or {}
        udp_base = SyndataSettings.get_defaults_udp().to_dict()
        if isinstance(syndata_udp_data, dict) and syndata_udp_data:
            udp_base.update(syndata_udp_data)
        syndata_udp = SyndataSettings.from_dict(udp_base)

        return cls(
            name=data.get("name", "unknown"),
            strategy_id=data.get("strategy_id", "none"),
            tcp_args=data.get("tcp_args", ""),
            udp_args=data.get("udp_args", ""),
            tcp_enabled=data.get("tcp_enabled", True),
            udp_enabled=data.get("udp_enabled", True),
            filter_mode=data.get("filter_mode", "hostlist"),
            filter_file=data.get("filter_file", ""),
            tcp_port=data.get("tcp_port", "443"),
            udp_port=data.get("udp_port", "443"),
            syndata_tcp=syndata_tcp,
            syndata_udp=syndata_udp,
            sort_order=data.get("sort_order", "default"),
        )


@dataclass
class Preset:
    """
    Complete preset configuration.

    A preset contains:
    - Metadata (name, timestamps)
    - Base arguments (lua-init, wf-*, blobs)
    - Category configurations (youtube, discord, etc.)

    Attributes:
        name: Preset name
        created: Creation timestamp (ISO format)
        modified: Last modification timestamp (ISO format)
        description: Optional description
        categories: Dict of category name -> CategoryConfig
        base_args: Base arguments (lua-init, wf-tcp-out, blobs)
    """
    name: str
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    modified: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""
    icon_color: str = DEFAULT_PRESET_ICON_COLOR
    categories: Dict[str, CategoryConfig] = field(default_factory=dict)
    base_args: str = ""
    _raw_blocks: list = field(default_factory=list)  # [(cat_key, protocol, raw_text)] for lossless save

    # Default base args for new presets
    DEFAULT_BASE_ARGS = """--lua-init=@lua/zapret-lib.lua
--lua-init=@lua/zapret-antidpi.lua
--lua-init=@lua/zapret-auto.lua
--lua-init=@lua/custom_funcs.lua
--lua-init=@lua/custom_diag.lua
--lua-init=@lua/zapret-multishake.lua

--ctrack-disable=0
--ipcache-lifetime=8400
--ipcache-hostname=1

--wf-tcp-out=80,443,1080,2053,2083,2087,2096,8443
--wf-udp-out=80,443"""

    def __post_init__(self):
        """Initialize base_args with default if empty."""
        self.icon_color = normalize_preset_icon_color(self.icon_color)
        if not self.base_args:
            self.base_args = self.DEFAULT_BASE_ARGS

    def get_category(self, name: str) -> Optional[CategoryConfig]:
        """Gets category config by name."""
        return self.categories.get(name)

    def set_category(self, config: CategoryConfig) -> None:
        """Sets or updates category config."""
        self.categories[config.name] = config
        self.touch()

    def remove_category(self, name: str) -> bool:
        """Removes category. Returns True if removed."""
        if name in self.categories:
            del self.categories[name]
            self.touch()
            return True
        return False

    def list_categories(self) -> List[str]:
        """Returns list of category names."""
        return list(self.categories.keys())

    def touch(self) -> None:
        """Updates modified timestamp."""
        self.modified = datetime.now().isoformat()

    def get_enabled_categories(self) -> List[CategoryConfig]:
        """Returns list of categories with at least one enabled protocol."""
        result = []
        for cat in self.categories.values():
            if (cat.tcp_enabled and cat.has_tcp()) or (cat.udp_enabled and cat.has_udp()):
                result.append(cat)
        return result

    def to_dict(self) -> Dict:
        """Converts to dictionary for serialization."""
        return {
            "name": self.name,
            "created": self.created,
            "modified": self.modified,
            "description": self.description,
            "icon_color": self.icon_color,
            "base_args": self.base_args,
            "categories": {
                name: cat.to_dict()
                for name, cat in self.categories.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Preset":
        """Creates Preset from dictionary."""
        categories = {}
        for name, cat_data in data.get("categories", {}).items():
            categories[name] = CategoryConfig.from_dict(cat_data)

        return cls(
            name=data.get("name", "Unnamed"),
            created=data.get("created", datetime.now().isoformat()),
            modified=data.get("modified", datetime.now().isoformat()),
            description=data.get("description", ""),
            icon_color=data.get("icon_color", DEFAULT_PRESET_ICON_COLOR),
            base_args=data.get("base_args", ""),
            categories=categories,
        )

def validate_preset(preset: Preset) -> List[str]:
    """
    Validates preset configuration.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []

    if not preset.name or not preset.name.strip():
        errors.append("Preset name is required")

    if not preset.base_args or not preset.base_args.strip():
        errors.append("Base arguments are required")

    # Check for required lua-init
    if "--lua-init=" not in preset.base_args:
        errors.append("Base args must include --lua-init")

    # Check categories
    for name, cat in preset.categories.items():
        if cat.tcp_enabled and cat.has_tcp():
            if "--lua-desync=" not in cat.tcp_args and "--dpi-desync=" not in cat.tcp_args:
                errors.append(f"Category {name} TCP: missing desync arguments")

        if cat.udp_enabled and cat.has_udp():
            if "--lua-desync=" not in cat.udp_args and "--dpi-desync=" not in cat.udp_args:
                errors.append(f"Category {name} UDP: missing desync arguments")

    return errors
