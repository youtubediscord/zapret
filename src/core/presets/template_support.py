from __future__ import annotations

from .winws2_template_runtime import (
    get_builtin_base_from_copy_name_winws2,
    get_default_template_content_winws2,
    get_template_content_winws2,
    reset_user_overrides_to_builtin_winws2,
)
from .winws1_template_runtime import (
    get_builtin_base_from_copy_name_winws1,
    get_builtin_preset_content_winws1,
    get_default_template_content_winws1,
    get_template_content_winws1,
    reset_user_overrides_to_builtin_winws1,
)


def _resolve_reset_template_winws2_from_runtime(preset_name: str) -> str:
    content = get_template_content_winws2(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name_winws2(preset_name)
        if base:
            content = get_template_content_winws2(base)
    if not content:
        content = get_default_template_content_winws2()
    return str(content or "")


def _resolve_reset_template_winws1_from_runtime(preset_name: str) -> str:
    content = get_template_content_winws1(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name_winws1(preset_name)
        if base:
            content = get_template_content_winws1(base)
    if not content:
        content = get_default_template_content_winws1()
    if not content:
        content = get_builtin_preset_content_winws1("Default")
    return str(content or "")


def resolve_reset_template(launch_method: str, preset_name: str) -> str:
    method = str(launch_method or "").strip().lower()
    if method == "zapret2_mode":
        content = _resolve_reset_template_winws2_from_runtime(preset_name)
        return content if content else ""

    content = _resolve_reset_template_winws1_from_runtime(preset_name)
    return content if content else ""


def reset_all_templates(launch_method: str) -> tuple[int, int, list[str]]:
    method = str(launch_method or "").strip().lower()
    if method == "zapret2_mode":
        return reset_user_overrides_to_builtin_winws2()

    return reset_user_overrides_to_builtin_winws1()
