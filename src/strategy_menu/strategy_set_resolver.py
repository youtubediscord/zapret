from __future__ import annotations

from typing import Optional


def get_current_strategy_set() -> Optional[str]:
    """
    Возвращает текущий набор стратегий без зависимости от legacy registry-пакета.

    Сейчас это нужно и новому direct/orchestra preset-слою, и старому
    registry-driven слою. Поэтому источник истины должен жить в нейтральном
    helper-модуле, а не внутри `legacy_registry_launch`.
    """
    try:
        from strategy_menu.launch_method_store import get_strategy_launch_method
        from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode

        method = get_strategy_launch_method()

        if method == "direct_zapret2":
            try:
                ui_mode = (get_direct_zapret2_ui_mode() or "").strip().lower()
            except Exception:
                ui_mode = ""
            if ui_mode in ("basic", "advanced"):
                return ui_mode

        method_to_set = {
            "direct_zapret2": None,
            "direct_zapret1": "zapret1",
            "orchestra": None,
        }
        return method_to_set.get(method, None)
    except Exception:
        return None
