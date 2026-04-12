from __future__ import annotations

from typing import Any


_LABEL_ORDER = {
    "recommended": 0,
    "stable": 1,
    None: 2,
    "none": 2,
    "experimental": 3,
    "game": 4,
    "caution": 5,
}


class StrategyDetailPageV1Controller:
    @staticmethod
    def normalize_target_info(target_key: str, target_info: Any) -> dict[str, Any]:
        if isinstance(target_info, dict):
            info = dict(target_info)
            info.setdefault("key", target_key)
            info.setdefault("full_name", target_key)
            info.setdefault("description", "")
            info.setdefault("base_filter", "")
            info.setdefault("base_filter_hostlist", "")
            info.setdefault("base_filter_ipset", "")
            return info

        return {
            "key": getattr(target_info, "key", target_key),
            "full_name": getattr(target_info, "full_name", target_key),
            "description": getattr(target_info, "description", ""),
            "protocol": getattr(target_info, "protocol", ""),
            "ports": getattr(target_info, "ports", ""),
            "icon_name": getattr(target_info, "icon_name", ""),
            "icon_color": getattr(target_info, "icon_color", "#909090"),
            "base_filter": getattr(target_info, "base_filter", ""),
            "base_filter_hostlist": getattr(target_info, "base_filter_hostlist", ""),
            "base_filter_ipset": getattr(target_info, "base_filter_ipset", ""),
        }

    @staticmethod
    def sorted_strategy_items(strategies: dict[str, dict], sort_mode: str) -> list[dict]:
        items = [s for s in (strategies or {}).values() if s.get("id")]

        if sort_mode == "alpha_asc":
            return sorted(items, key=lambda s: (s.get("name", "")).lower())
        if sort_mode == "alpha_desc":
            return sorted(items, key=lambda s: (s.get("name", "")).lower(), reverse=True)

        return sorted(
            items,
            key=lambda s: (
                _LABEL_ORDER.get(s.get("label"), 2),
                (s.get("name", "")).lower(),
            ),
        )

    @staticmethod
    def default_strategy_id(strategies: dict[str, dict], sort_mode: str) -> str:
        for item in StrategyDetailPageV1Controller.sorted_strategy_items(strategies, sort_mode):
            sid = str(item.get("id") or "").strip()
            if sid and sid != "none":
                return sid
        return "none"

    @staticmethod
    def strategy_display_name(strategy_id: str, strategies: dict[str, dict], tr) -> str:
        sid = (strategy_id or "").strip()
        if not sid or sid == "none":
            return tr("page.z1_strategy_detail.tree.disabled.name", "Выключено")
        if sid == "custom":
            return tr("page.z1_strategy_detail.tree.custom.name", "Свой набор")
        info = (strategies or {}).get(sid)
        if info:
            return info.get("name", sid)
        return sid
