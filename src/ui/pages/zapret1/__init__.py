# ui/pages/zapret1/__init__.py
"""Zapret1 UI pages."""
from .direct_control_page import Zapret1DirectControlPage
from .direct_zapret1_page import Zapret1StrategiesPage
from .user_presets_page import Zapret1UserPresetsPage
from .strategy_detail_page_v1 import Zapret1StrategyDetailPage
from .preset_detail_page import Zapret1PresetDetailPage

__all__ = [
    'Zapret1DirectControlPage',
    'Zapret1StrategiesPage',
    'Zapret1PresetDetailPage',
    'Zapret1UserPresetsPage',
    'Zapret1StrategyDetailPage',
]
