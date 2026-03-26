# ui/nav_mode_config.py
"""Mode-based navigation visibility configuration.

Single source of truth for which pages are visible in the sidebar
per launch method. Import and use get_nav_visibility(method) in
_sync_nav_visibility() instead of a hardcoded targets dict.

Adding a new mode-specific page:
  1. Add the rule to get_nav_visibility() below.
  2. Add _add(PageName.YOUR_PAGE) to _init_navigation() in main_window.py
     (right after CONTROL/ZAPRET2_DIRECT_CONTROL block).
  3. Add icon + label to _NAV_ICONS / _NAV_LABELS in main_window.py.
"""

from ui.page_names import PageName


def get_nav_visibility(method: str) -> dict[PageName, bool]:
    """Return {PageName: should_be_visible} for the given launch method.

    All pages listed here must be present in _nav_items (added via _add()
    in _init_navigation). Pages absent from the dict are not touched.
    """
    m = (method or "").strip().lower()

    is_direct_zapret2          = m == "direct_zapret2"
    is_direct_zapret2_orchestra = m == "direct_zapret2_orchestra"
    is_direct_zapret1          = m == "direct_zapret1"
    is_pure_orchestra          = m == "orchestra"

    # zapret2 family (direct or orchestra variant)
    is_zapret2_family = is_direct_zapret2 or is_direct_zapret2_orchestra

    return {
        # ── Верх: "Управление" vs "Стратегии" (direct_zapret2 entry point) ───
        # CONTROL скрыта для direct_zapret2 (заменена на ZAPRET2_DIRECT_CONTROL)
        # и для direct_zapret1 (заменена на ZAPRET1_DIRECT_CONTROL)
        # и для direct_zapret2_orchestra (заменена на ZAPRET2_ORCHESTRA_CONTROL)
        PageName.CONTROL:                  not is_direct_zapret2 and not is_direct_zapret1 and not is_direct_zapret2_orchestra,
        PageName.ZAPRET2_DIRECT_CONTROL:   is_direct_zapret2,
        PageName.ZAPRET2_ORCHESTRA_CONTROL: is_direct_zapret2_orchestra,

        # ── Strategy entry-point pages (one visible at a time) ───────────────
        PageName.ORCHESTRA:                is_pure_orchestra,
        PageName.ZAPRET1_DIRECT_CONTROL:   is_direct_zapret1,

        # ── Orchestra settings (tabbed page) ─────────────────────────────────
        PageName.ORCHESTRA_SETTINGS:       is_pure_orchestra,
    }
