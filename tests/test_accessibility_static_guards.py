from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

IMPORTANT_CONTROL_MARKERS = (
    "PushButton(",
    "PrimaryPushButton(",
    "ToolButton(",
    "PrimaryToolButton(",
    "TransparentToolButton(",
    "LineEdit(",
    "SearchLineEdit(",
    "ComboBox(",
    "CheckBox(",
    "SwitchButton(",
    "PlainTextEdit(",
    "TextEdit(",
    "QListWidget(",
    "QTableWidget(",
)

ACCESSIBILITY_MARKERS = (
    "set_control_accessibility",
    "set_state_text",
    "set_item_accessible_text",
    "set_segmented_items_accessibility",
    "enable_keyboard_click",
    "enable_keyboard_toggle",
    "accessibility",
)

KEYBOARD_COLLECTION_WIDGET_MARKERS = (
    "QListWidget(",
    "(QListWidget):",
    "ListView(",
    "(ListView):",
    "QTableWidget(",
    "(QTableWidget):",
    "TableWidget(",
    "(TableWidget):",
    "SegmentedWidget(",
)

KEYBOARD_COLLECTION_ACCESS_MARKERS = (
    "keyPressEvent",
    "focusInEvent",
    "currentItemChanged",
    "currentChanged",
    "currentCellChanged",
    "set_segmented_items_accessibility",
    "AccessibleTextRole",
    "setFocusPolicy(Qt.FocusPolicy.StrongFocus)",
    "screenReaderStateText",
    "enable_keyboard_click",
    "enable_keyboard_toggle",
    "set_item_accessible_text",
)


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ui_files_with_important_controls_keep_accessibility_wiring() -> None:
    missing: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel_path = path.relative_to(ROOT).as_posix()
        if rel_path.startswith("src/themes/cache/"):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if not any(marker in source for marker in IMPORTANT_CONTROL_MARKERS):
            continue
        if any(marker in source for marker in ACCESSIBILITY_MARKERS):
            continue
        missing.append(rel_path)

    assert missing == []


def test_collection_controls_keep_keyboard_or_row_accessibility() -> None:
    missing: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel_path = path.relative_to(ROOT).as_posix()
        if rel_path.startswith("src/themes/cache/"):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if not any(marker in source for marker in KEYBOARD_COLLECTION_WIDGET_MARKERS):
            continue
        if any(marker in source for marker in KEYBOARD_COLLECTION_ACCESS_MARKERS):
            continue
        missing.append(rel_path)

    assert missing == []


def test_profile_shell_keeps_toolbar_accessibility_helper() -> None:
    source = _source("src/profile/ui/shell.py")

    assert "from profile.ui.shell_accessibility import apply_profile_shell_accessibility" in source
    assert "apply_profile_shell_accessibility(" in source
    for control_name in (
        "add_profile_btn",
        "request_btn",
        "view_menu_btn",
        "order_btn",
        "info_btn",
        "profile_search_input",
    ):
        assert f"{control_name}={control_name}" in source


def test_user_presets_build_keeps_accessibility_helper_for_toolbar_and_list() -> None:
    source = _source("src/presets/ui/common/user_presets_build.py")

    assert (
        "from presets.ui.common.user_presets_accessibility import apply_user_presets_accessibility"
        in source
    )
    assert source.count("apply_user_presets_accessibility(") >= 2
    for control_name in (
        "get_configs_btn",
        "create_btn",
        "import_btn",
        "open_folder_btn",
        "reset_all_btn",
        "presets_info_btn",
        "info_btn",
        "preset_search_input",
        "presets_list",
    ):
        assert f"{control_name}={control_name}" in source


def test_premium_build_keeps_button_accessibility_helper() -> None:
    source = _source("src/donater/ui/build.py")

    assert "apply_premium_button_accessibility" in source
    for keyword in (
        "activate_btn=activate_btn",
        "open_bot_btn=open_bot_btn",
        "refresh_btn=refresh_btn",
        "change_key_btn=change_key_btn",
        "test_btn=test_btn",
        "extend_btn=extend_btn",
    ):
        assert keyword in source


def test_notification_infobar_keeps_accessibility_for_dynamic_actions() -> None:
    source = _source("src/ui/window_notification_center.py")

    assert "self._set_infobar_accessibility(bar" in source
    assert "self._set_infobar_action_button_accessibility(btn, action, button_text)" in source
    assert 'name = f"Действие уведомления: {button_text}"' in source
