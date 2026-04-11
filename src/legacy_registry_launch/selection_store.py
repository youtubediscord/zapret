from __future__ import annotations

"""Legacy selections store.

Important:
- direct_zapret1/direct_zapret2 should read/write selections through DirectPresetFacade;
- this module remains only for orchestra and registry-driven legacy flows;
- the old `direct_selection_store.py` name is intentionally retired so the new
  direct source-preset path does not keep looking like a selections-dict system.
"""

from log import log

from strategy_menu.launch_method_store import get_strategy_launch_method

_legacy_selections_cache = None
_legacy_selections_cache_time = 0
_legacy_selections_cache_method = None
_legacy_selections_cache_preset_mtime = None
LEGACY_SELECTIONS_CACHE_TTL = 5.0


def invalidate_direct_selections_cache():
    """Сбрасывает кэш legacy-выборов стратегий."""
    global _legacy_selections_cache_time, _legacy_selections_cache_method, _legacy_selections_cache_preset_mtime
    _legacy_selections_cache_time = 0
    _legacy_selections_cache_method = None
    _legacy_selections_cache_preset_mtime = None


def get_direct_strategy_selections() -> dict:
    """Возвращает сохранённые выборы стратегий.

    Для direct_zapret1/direct_zapret2 использует новый DirectPresetFacade.
    Для orchestra/legacy режимов остаётся selections-dict path.
    """
    import time

    global _legacy_selections_cache
    global _legacy_selections_cache_time, _legacy_selections_cache_preset_mtime, _legacy_selections_cache_method

    method = get_strategy_launch_method()

    cache_mtime = None
    if method == "direct_zapret1":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret1")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None
    elif method == "direct_zapret2":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret2")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None

    current_time = time.time()
    if (
        _legacy_selections_cache is not None
        and current_time - _legacy_selections_cache_time < LEGACY_SELECTIONS_CACHE_TTL
        and _legacy_selections_cache_method == method
        and _legacy_selections_cache_preset_mtime == cache_mtime
    ):
        return _legacy_selections_cache.copy()

    try:
        selections: dict[str, str] = {}
        default_selections: dict[str, str] = {}

        if method == "direct_zapret2":
            try:
                from core.presets.direct_facade import DirectPresetFacade

                selections = DirectPresetFacade.from_launch_method("direct_zapret2").get_strategy_selections() or {}
            except Exception as e:
                log(f"Ошибка чтения selected source preset для выбора стратегий direct_zapret2: {e}", "DEBUG")
                selections = {}
        elif method == "direct_zapret1":
            try:
                from core.presets.direct_facade import DirectPresetFacade

                selections = DirectPresetFacade.from_launch_method("direct_zapret1").get_strategy_selections() or {}
            except Exception as e:
                log(f"Ошибка чтения selected source preset для выбора стратегий direct_zapret1: {e}", "DEBUG")
                selections = {}
        else:
            from legacy_registry_launch.strategies_registry import registry

            default_selections = registry.get_default_selections()
            selections = dict(default_selections)

        for key, default_value in default_selections.items():
            if key not in selections:
                if method in ("direct_zapret1", "direct_zapret2"):
                    continue
                else:
                    selections[key] = default_value

        _legacy_selections_cache = selections
        _legacy_selections_cache_time = current_time
        _legacy_selections_cache_method = method
        _legacy_selections_cache_preset_mtime = cache_mtime
        return selections
    except Exception as e:
        log(f"Ошибка загрузки выборов стратегий: {e}", "❌ ERROR")
        import traceback

        log(traceback.format_exc(), "DEBUG")
        if method in ("direct_zapret1", "direct_zapret2"):
            return {}
        from legacy_registry_launch.strategies_registry import registry

        return registry.get_default_selections()


def set_direct_strategy_selections(selections: dict) -> bool:
    """Сохраняет выборы стратегий."""
    try:
        method = get_strategy_launch_method()
        if method == "direct_zapret2":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            payload = {
                target_key: strategy_id
                for target_key, strategy_id in (selections or {}).items()
                if str(target_key or "").strip()
            }
            facade.set_strategy_selections(payload, save_and_sync=True)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret2)", "DEBUG")
            return True

        if method == "direct_zapret1":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret1")
            payload = {
                target_key: strategy_id
                for target_key, strategy_id in (selections or {}).items()
                if str(target_key or "").strip()
            }
            success = bool(facade.set_strategy_selections(payload, save_and_sync=True))
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret1)", "DEBUG")
            return success

        return False
    except Exception as e:
        log(f"Ошибка сохранения выборов: {e}", "❌ ERROR")
        return False


def get_direct_strategy_for_target(target_key: str) -> str:
    """Получает выбранную стратегию для конкретного target'а."""
    method = get_strategy_launch_method()
    if method in ("direct_zapret2", "direct_zapret1"):
        selections = get_direct_strategy_selections()
        return selections.get(target_key, "none") or "none"

    from legacy_registry_launch.strategies_registry import registry

    target_info = registry.get_target_info(target_key)
    if target_info:
        return target_info.default_strategy
    return "none"


def set_direct_strategy_for_target(target_key: str, strategy_id: str) -> bool:
    """Сохраняет выбранную стратегию для target'а."""
    method = get_strategy_launch_method()

    if method == "direct_zapret2":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_strategy_selection(
                target_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected source preset direct_zapret2: {e}", "DEBUG")
            return False

    if method == "direct_zapret1":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").set_strategy_selection(
                target_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected source preset direct_zapret1: {e}", "DEBUG")
            return False

    return False
