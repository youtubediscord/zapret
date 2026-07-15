from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_keyboard_navigation_lists_do_not_use_native_single_selection() -> None:
    targets = {
        "src/profile/ui/profile_strategy_list_widget.py",
        "src/profile/ui/profiles_list.py",
        "src/profile/ui/profile_order_list.py",
        "src/presets/ui/common/user_presets_build.py",
        "src/dns/ui/choice_list.py",
        "src/dns/ui/adapter_list.py",
    }

    for path in sorted(targets):
        source = _source(path)
        assert "SelectionMode.SingleSelection" not in source, path
        assert "SelectionMode.NoSelection" in source, path


def test_keyboard_row_delegates_paint_focused_current_row() -> None:
    targets = {
        "src/profile/ui/profile_strategy_list_widget.py",
        "src/profile/ui/profile_list_delegate.py",
        "src/ui/presets_menu/delegate.py",
        "src/dns/ui/choice_list.py",
        "src/dns/ui/adapter_list.py",
    }

    for path in sorted(targets):
        source = _source(path)
        assert "State_HasFocus" in source, path
