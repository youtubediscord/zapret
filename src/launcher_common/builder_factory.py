# launcher_common/builder_factory.py
"""
Factory module for strategy lists.
Выбирает между V1 и V2 реализациями в зависимости от режима.

For backwards compatibility, maintains the same API:
- combine_strategies(**kwargs) - main entry point
- calculate_required_filters(...)
- get_strategy_display_name(...)
- get_active_targets_count(...)
- validate_target_strategies(...)
"""

from log import log
from launcher_common.orchestra_legacy_bridge import (
    apply_settings as _apply_settings,
    calculate_required_filters,
    clean_spaces as _clean_spaces,
    combine_legacy_orchestra_strategies,
    get_active_targets_count,
    get_strategy_display_name,
    validate_target_strategies,
)
from strategy_menu import get_strategy_launch_method


def _combine_direct_source_preset(launch_method: str) -> dict:
    """Собирает прямой запуск из выбранного source preset, без legacy builders."""
    from core.presets.direct_facade import DirectPresetFacade
    from core.services import get_direct_flow_coordinator

    method = str(launch_method or "").strip().lower()
    snapshot = get_direct_flow_coordinator().get_startup_snapshot(method)
    facade = DirectPresetFacade.from_launch_method(method)
    selections = facade.get_strategy_selections() or {}
    active_targets = sum(1 for strategy_id in selections.values() if (strategy_id or "none") != "none")

    log(f"combine_strategies: using selected source preset for {method}: {snapshot.preset_path}", "DEBUG")

    return {
        "name": snapshot.display_name,
        "description": snapshot.display_name,
        "version": "source-preset",
        "provider": "direct_preset_core",
        "author": "DirectPresetCore",
        "updated": "2026",
        "all_sites": True,
        "args": f"@{snapshot.preset_path}",
        "_is_builtin": False,
        "_is_preset_file": True,
        "_direct_source_preset": True,
        "_is_v1": method == "direct_zapret1",
        "_is_orchestra": False,
        "_active_targets": active_targets,
    }


def _combine_direct_orchestra_source_preset() -> dict:
    """Собирает direct_zapret2_orchestra из active orchestra preset file."""
    from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

    if not ensure_default_preset_exists():
        raise RuntimeError("Active orchestra preset file is not prepared")

    manager = PresetManager()
    active_path = manager.get_active_preset_path()
    active_name = str(manager.get_active_preset_name() or "").strip() or "Default"
    selections = manager.get_strategy_selections() or {}
    active_targets = sum(1 for strategy_id in selections.values() if (strategy_id or "none") != "none")

    log(f"combine_strategies: using active orchestra preset file: {active_path}", "DEBUG")

    return {
        "name": f"Пресет оркестра: {active_name}",
        "description": f"Пресет оркестра: {active_name}",
        "version": "orchestra-preset",
        "provider": "preset_orchestra_zapret2",
        "author": "PresetOrchestraZ2",
        "updated": "2026",
        "all_sites": True,
        "args": f"@{active_path}",
        "_is_builtin": False,
        "_is_preset_file": True,
        "_direct_source_preset": False,
        "_is_v1": False,
        "_is_orchestra": True,
        "_active_targets": active_targets,
    }


def combine_strategies(**kwargs) -> dict:
    """
    Возвращает итоговую конфигурацию запуска для текущего режима.

    Для direct_zapret1/direct_zapret2 больше не строит запуск из category selections:
    в этих режимах источником истины является выбранный source preset.

    Returns:
        dict с ключами:
        - args: командная строка
        - name: отображаемое имя
        - _active_targets: количество активных target'ов
        - _is_orchestra: флаг оркестратора (только V2)
    """
    launch_method = get_strategy_launch_method()

    if launch_method in {"direct_zapret1", "direct_zapret2"}:
        return _combine_direct_source_preset(launch_method)

    if launch_method == "direct_zapret2_orchestra":
        return _combine_direct_orchestra_source_preset()

    # orchestra пока остаётся на legacy V2 builder.
    is_orchestra = launch_method == "direct_zapret2_orchestra"

    log(f"combine_strategies: using V2 (winws2.exe), orchestra={is_orchestra}", "DEBUG")
    return combine_legacy_orchestra_strategies(**kwargs)
