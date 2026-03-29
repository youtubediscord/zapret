"""Preset target list for the new direct source-preset UI flow.

This widget is the direct_zapret1/direct_zapret2 list entry point.
It builds from PresetTargetView[] plus optional metadata enrichment.

The old UnifiedStrategiesList remains only for orchestra / legacy registry-driven pages.
"""

from .unified_strategies_list import UnifiedStrategiesList


class PresetTargetsList(UnifiedStrategiesList):
    """Thin named wrapper so the new direct UI no longer depends on legacy widget naming."""

