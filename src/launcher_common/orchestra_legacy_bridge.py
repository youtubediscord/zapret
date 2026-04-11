"""Orchestra-only bridge to the remaining legacy launch builders.

Direct selected-source preset flow must not depend on this module.
Only the old pure orchestra launch path may still delegate here.
"""

from __future__ import annotations


def calculate_required_filters(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl.calculate_required_filters(*args, **kwargs)


def apply_settings(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl._apply_settings(*args, **kwargs)


def clean_spaces(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl._clean_spaces(*args, **kwargs)


def get_strategy_display_name(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl.get_strategy_display_name(*args, **kwargs)


def get_active_targets_count(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl.get_active_targets_count(*args, **kwargs)


def validate_target_strategies(*args, **kwargs):
    from legacy_registry_launch import builder_common as _impl

    return _impl.validate_target_strategies(*args, **kwargs)


def combine_legacy_orchestra_strategies(**kwargs) -> dict:
    from legacy_registry_launch.zapret2_strategy_builder import combine_strategies_v2

    return combine_strategies_v2(is_orchestra=False, **kwargs)
