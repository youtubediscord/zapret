from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from .target_metadata_loader import load_target_metadata


@dataclass(frozen=True)
class TargetPresentationMetadata:
    target_key: str
    base_key: str
    display_name: str
    protocol: str
    ports: str
    command_group: str
    order: int
    icon_name: str
    icon_color: str
    description: str = ""
    tooltip: str = ""
    strategy_type: str = "tcp"
    base_filter: str = ""
    base_filter_hostlist: str = ""
    base_filter_ipset: str = ""
    requires_all_ports: bool = False
    strip_payload: bool = False


def _humanize_base_key(base_key: str) -> str:
    parts = [part for part in str(base_key or "").replace("-", "_").split("_") if part]
    if not parts:
        return "Target"
    return " ".join(part[:1].upper() + part[1:] for part in parts)


class TargetMetadataService:
    def _load_target_metadata(self) -> dict:
        # Canonical target metadata service enriches only parser-derived target keys.
        return load_target_metadata()

    @staticmethod
    def base_key_from_target_key(target_key: str) -> str:
        text = str(target_key or "").strip().lower()
        for suffix in ("_tcp", "_udp", "_l7"):
            if text.endswith(suffix):
                return text[: -len(suffix)]
        return text

    @staticmethod
    def protocol_from_target_key(target_key: str) -> str:
        text = str(target_key or "").strip().lower()
        if text.endswith("_udp"):
            return "UDP"
        if text.endswith("_l7"):
            return "L7"
        return "TCP"

    def get_metadata(self, target_key: str) -> TargetPresentationMetadata:
        normalized_target_key = str(target_key or "").strip().lower()
        base_key = self.base_key_from_target_key(normalized_target_key)
        protocol = self.protocol_from_target_key(normalized_target_key)
        items = self._load_target_metadata()

        raw = items.get(normalized_target_key)
        if not raw:
            for candidate in items.values():
                aliases = str((candidate or {}).get("aliases") or "").strip().lower()
                alias_tokens = [token.strip() for token in aliases.split(",") if token.strip()]
                if normalized_target_key in alias_tokens:
                    raw = candidate
                    break
        if not raw:
            raw = items.get(base_key) or {}
        display_name = str(raw.get("full_name") or _humanize_base_key(base_key)).strip() or target_key
        ports = str(raw.get("ports") or "").strip()
        strategy_type = str(raw.get("strategy_type") or "").strip().lower() or ("udp" if protocol == "UDP" else "tcp")
        return TargetPresentationMetadata(
            target_key=normalized_target_key,
            base_key=base_key,
            display_name=display_name,
            protocol=str(raw.get("protocol") or protocol).strip() or protocol,
            ports=ports,
            command_group=str(raw.get("command_group") or "default").strip() or "default",
            order=int(raw.get("order", 999) or 999),
            icon_name=str(raw.get("icon_name") or "fa5s.globe").strip() or "fa5s.globe",
            icon_color=str(raw.get("icon_color") or "#2196F3").strip() or "#2196F3",
            description=str(raw.get("description") or "").strip(),
            tooltip=str(raw.get("tooltip") or "").replace("\\n", "\n"),
            strategy_type=strategy_type,
            base_filter=str(raw.get("base_filter") or "").strip(),
            base_filter_hostlist=str(raw.get("base_filter_hostlist") or "").strip(),
            base_filter_ipset=str(raw.get("base_filter_ipset") or "").strip(),
            requires_all_ports=bool(raw.get("requires_all_ports", False)),
            strip_payload=bool(raw.get("strip_payload", False)),
        )

    def build_ui_item(self, target_key: str):
        metadata = self.get_metadata(target_key)
        return SimpleNamespace(
            key=metadata.target_key,
            full_name=metadata.display_name,
            description=metadata.description,
            tooltip=metadata.tooltip,
            protocol=metadata.protocol,
            ports=metadata.ports,
            order=metadata.order,
            command_order=metadata.order,
            command_group=metadata.command_group,
            icon_name=metadata.icon_name,
            icon_color=metadata.icon_color,
            base_filter=metadata.base_filter,
            base_filter_hostlist=metadata.base_filter_hostlist,
            base_filter_ipset=metadata.base_filter_ipset,
            strategy_type=metadata.strategy_type,
            requires_all_ports=metadata.requires_all_ports,
            strip_payload=metadata.strip_payload,
        )

    @staticmethod
    def should_include_in_basic_ui(target_key: str) -> bool:
        normalized = str(target_key or "").strip().lower()
        if not normalized:
            return False
        if normalized.startswith("inline_"):
            return False
        return True
