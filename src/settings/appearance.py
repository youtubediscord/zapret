from __future__ import annotations

from dataclasses import dataclass
import threading

from settings import schema


def normalize_language(language: str | None) -> str:
    candidate = str(language or schema.default_appearance()["ui_language"]).strip().lower()
    if candidate in schema.VALID_UI_LANGUAGES:
        return candidate
    return schema.default_appearance()["ui_language"]


def normalize_sidebar_icon_style(style: str | None) -> str:
    candidate = str(style or schema.default_appearance()["sidebar_icon_style"]).strip().lower()
    if candidate in schema.VALID_SIDEBAR_ICON_STYLES:
        return candidate
    return str(schema.default_appearance()["sidebar_icon_style"])


@dataclass(slots=True)
class AppearanceDisplayModePlan:
    requested_mode: str
    effective_mode: str


@dataclass(slots=True)
class AppearanceUiLanguagePlan:
    language: str


@dataclass(slots=True)
class AppearanceBackgroundPresetPlan:
    preset: str


@dataclass(slots=True)
class AppearanceMicaPlan:
    enabled: bool


@dataclass(slots=True)
class AppearanceOpacityPlan:
    value: int


@dataclass(slots=True)
class AppearanceTogglePlan:
    enabled: bool


@dataclass(slots=True)
class AppearanceSidebarIconStylePlan:
    style: str


@dataclass(slots=True)
class AppearanceAccentColorPlan:
    hex_color: str | None


@dataclass(slots=True)
class AppearanceTintedSettingsPlan:
    follow_windows_accent: bool
    tinted_background: bool
    tinted_intensity: int


@dataclass(slots=True)
class AppearanceRknBackgroundPlan:
    value: str | None


@dataclass(slots=True)
class AppearancePremiumEffectsPlan:
    garland_enabled: bool
    snowflakes_enabled: bool


@dataclass(slots=True)
class AppearancePremiumStatusPlan:
    effective_preset: str | None
    garland_checked: bool
    snowflakes_checked: bool
    disable_garland: bool
    disable_snowflakes: bool


@dataclass(slots=True)
class AppearancePageInitialStatePlan:
    display_mode: str
    ui_language: str
    background_preset: str
    rkn_background: str | None
    mica_enabled: bool
    window_opacity: int
    accent_color: str | None
    follow_windows_accent: bool
    tinted_background: bool
    tinted_intensity: int
    animations_enabled: bool
    smooth_scroll_enabled: bool
    editor_smooth_scroll_enabled: bool
    sidebar_icon_style: str
    garland_enabled: bool
    snowflakes_enabled: bool


_warmed_page_initial_state_lock = threading.Lock()
_warmed_page_initial_state_cache: AppearancePageInitialStatePlan | None = None
_warmed_ui_language_lock = threading.Lock()
_warmed_ui_language_cache: str | None = None
_warmed_rkn_background_lock = threading.Lock()
_warmed_rkn_background_cache: str | None = None
_warmed_background_preset_lock = threading.Lock()
_warmed_background_preset_cache: str | None = None
_warmed_mica_enabled_lock = threading.Lock()
_warmed_mica_enabled_cache: bool | None = None
_warmed_window_opacity_lock = threading.Lock()
_warmed_window_opacity_cache: int | None = None
_warmed_accent_color_lock = threading.Lock()
_warmed_accent_color_cache: str | None = None
_warmed_tinted_settings_lock = threading.Lock()
_warmed_tinted_settings_cache: AppearanceTintedSettingsPlan | None = None
_warmed_animations_enabled_lock = threading.Lock()
_warmed_animations_enabled_cache: bool | None = None
_warmed_smooth_scroll_enabled_lock = threading.Lock()
_warmed_smooth_scroll_enabled_cache: bool | None = None
_warmed_editor_smooth_scroll_enabled_lock = threading.Lock()
_warmed_editor_smooth_scroll_enabled_cache: bool | None = None
_warmed_sidebar_icon_style_lock = threading.Lock()
_warmed_sidebar_icon_style_cache: str | None = None
_warmed_premium_effects_lock = threading.Lock()
_warmed_premium_effects_cache: AppearancePremiumEffectsPlan | None = None


def store_warmed_ui_language(language: str | None) -> None:
    global _warmed_ui_language_cache
    with _warmed_ui_language_lock:
        _warmed_ui_language_cache = normalize_language(language)


def peek_warmed_ui_language() -> str | None:
    with _warmed_ui_language_lock:
        return _warmed_ui_language_cache


def clear_warmed_ui_language_cache() -> None:
    global _warmed_ui_language_cache
    with _warmed_ui_language_lock:
        _warmed_ui_language_cache = None


def store_warmed_rkn_background(value: str | None) -> None:
    global _warmed_rkn_background_cache
    normalized = str(value or "").strip().replace("\\", "/") or None
    with _warmed_rkn_background_lock:
        _warmed_rkn_background_cache = normalized


def peek_warmed_rkn_background() -> str | None:
    with _warmed_rkn_background_lock:
        return _warmed_rkn_background_cache


def clear_warmed_rkn_background_cache() -> None:
    global _warmed_rkn_background_cache
    with _warmed_rkn_background_lock:
        _warmed_rkn_background_cache = None


def store_warmed_background_preset(preset: str | None) -> None:
    global _warmed_background_preset_cache
    default = str(schema.default_appearance()["background_preset"])
    normalized = str(preset or default).strip() or default
    if normalized not in schema.VALID_BACKGROUND_PRESETS:
        normalized = default
    with _warmed_background_preset_lock:
        _warmed_background_preset_cache = normalized


def peek_warmed_background_preset() -> str | None:
    with _warmed_background_preset_lock:
        return _warmed_background_preset_cache


def clear_warmed_background_preset_cache() -> None:
    global _warmed_background_preset_cache
    with _warmed_background_preset_lock:
        _warmed_background_preset_cache = None


def store_warmed_mica_enabled(enabled: bool | None) -> None:
    global _warmed_mica_enabled_cache
    normalized = bool(schema.default_appearance()["mica_enabled"]) if enabled is None else bool(enabled)
    with _warmed_mica_enabled_lock:
        _warmed_mica_enabled_cache = normalized


def peek_warmed_mica_enabled() -> bool | None:
    with _warmed_mica_enabled_lock:
        return _warmed_mica_enabled_cache


def clear_warmed_mica_enabled_cache() -> None:
    global _warmed_mica_enabled_cache
    with _warmed_mica_enabled_lock:
        _warmed_mica_enabled_cache = None


def store_warmed_window_opacity(value: int | None) -> None:
    global _warmed_window_opacity_cache
    default = int(schema.default_window()["opacity"])
    try:
        normalized = int(default if value is None else value)
    except Exception:
        normalized = default
    normalized = max(0, min(100, normalized))
    with _warmed_window_opacity_lock:
        _warmed_window_opacity_cache = normalized


def peek_warmed_window_opacity() -> int | None:
    with _warmed_window_opacity_lock:
        return _warmed_window_opacity_cache


def clear_warmed_window_opacity_cache() -> None:
    global _warmed_window_opacity_cache
    with _warmed_window_opacity_lock:
        _warmed_window_opacity_cache = None


def store_warmed_accent_color(hex_color: str | None) -> None:
    global _warmed_accent_color_cache
    normalized = str(hex_color or "").strip() or None
    with _warmed_accent_color_lock:
        _warmed_accent_color_cache = normalized


def peek_warmed_accent_color() -> str | None:
    with _warmed_accent_color_lock:
        return _warmed_accent_color_cache


def clear_warmed_accent_color_cache() -> None:
    global _warmed_accent_color_cache
    with _warmed_accent_color_lock:
        _warmed_accent_color_cache = None


def store_warmed_tinted_settings(
    follow_windows_accent: bool | None,
    tinted_background: bool | None,
    tinted_intensity: int | None,
) -> None:
    global _warmed_tinted_settings_cache
    defaults = schema.default_appearance()
    try:
        intensity = int(defaults["tinted_background_intensity"] if tinted_intensity is None else tinted_intensity)
    except Exception:
        intensity = int(defaults["tinted_background_intensity"])
    plan = AppearanceTintedSettingsPlan(
        follow_windows_accent=(
            bool(defaults["follow_windows_accent"])
            if follow_windows_accent is None
            else bool(follow_windows_accent)
        ),
        tinted_background=(
            bool(defaults["tinted_background"])
            if tinted_background is None
            else bool(tinted_background)
        ),
        tinted_intensity=max(0, min(30, intensity)),
    )
    with _warmed_tinted_settings_lock:
        _warmed_tinted_settings_cache = plan


def peek_warmed_tinted_settings() -> AppearanceTintedSettingsPlan | None:
    with _warmed_tinted_settings_lock:
        return _warmed_tinted_settings_cache


def clear_warmed_tinted_settings_cache() -> None:
    global _warmed_tinted_settings_cache
    with _warmed_tinted_settings_lock:
        _warmed_tinted_settings_cache = None


def store_warmed_animations_enabled(enabled: bool | None) -> None:
    global _warmed_animations_enabled_cache
    normalized = bool(schema.default_appearance()["animations_enabled"]) if enabled is None else bool(enabled)
    with _warmed_animations_enabled_lock:
        _warmed_animations_enabled_cache = normalized


def peek_warmed_animations_enabled() -> bool | None:
    with _warmed_animations_enabled_lock:
        return _warmed_animations_enabled_cache


def clear_warmed_animations_enabled_cache() -> None:
    global _warmed_animations_enabled_cache
    with _warmed_animations_enabled_lock:
        _warmed_animations_enabled_cache = None


def store_warmed_smooth_scroll_enabled(enabled: bool | None) -> None:
    global _warmed_smooth_scroll_enabled_cache
    normalized = bool(schema.default_appearance()["smooth_scroll_enabled"]) if enabled is None else bool(enabled)
    with _warmed_smooth_scroll_enabled_lock:
        _warmed_smooth_scroll_enabled_cache = normalized


def peek_warmed_smooth_scroll_enabled() -> bool | None:
    with _warmed_smooth_scroll_enabled_lock:
        return _warmed_smooth_scroll_enabled_cache


def clear_warmed_smooth_scroll_enabled_cache() -> None:
    global _warmed_smooth_scroll_enabled_cache
    with _warmed_smooth_scroll_enabled_lock:
        _warmed_smooth_scroll_enabled_cache = None


def store_warmed_editor_smooth_scroll_enabled(enabled: bool | None) -> None:
    global _warmed_editor_smooth_scroll_enabled_cache
    normalized = bool(schema.default_appearance()["editor_smooth_scroll_enabled"]) if enabled is None else bool(enabled)
    with _warmed_editor_smooth_scroll_enabled_lock:
        _warmed_editor_smooth_scroll_enabled_cache = normalized


def peek_warmed_editor_smooth_scroll_enabled() -> bool | None:
    with _warmed_editor_smooth_scroll_enabled_lock:
        return _warmed_editor_smooth_scroll_enabled_cache


def clear_warmed_editor_smooth_scroll_enabled_cache() -> None:
    global _warmed_editor_smooth_scroll_enabled_cache
    with _warmed_editor_smooth_scroll_enabled_lock:
        _warmed_editor_smooth_scroll_enabled_cache = None


def store_warmed_sidebar_icon_style(style: str | None) -> None:
    global _warmed_sidebar_icon_style_cache
    with _warmed_sidebar_icon_style_lock:
        _warmed_sidebar_icon_style_cache = normalize_sidebar_icon_style(style)


def peek_warmed_sidebar_icon_style() -> str | None:
    with _warmed_sidebar_icon_style_lock:
        return _warmed_sidebar_icon_style_cache


def clear_warmed_sidebar_icon_style_cache() -> None:
    global _warmed_sidebar_icon_style_cache
    with _warmed_sidebar_icon_style_lock:
        _warmed_sidebar_icon_style_cache = None


def store_warmed_premium_effects(garland_enabled: bool | None, snowflakes_enabled: bool | None) -> None:
    global _warmed_premium_effects_cache
    defaults = schema.default_appearance()
    plan = AppearancePremiumEffectsPlan(
        garland_enabled=bool(defaults["garland_enabled"]) if garland_enabled is None else bool(garland_enabled),
        snowflakes_enabled=bool(defaults["snowflakes_enabled"]) if snowflakes_enabled is None else bool(snowflakes_enabled),
    )
    with _warmed_premium_effects_lock:
        _warmed_premium_effects_cache = plan


def peek_warmed_premium_effects() -> AppearancePremiumEffectsPlan | None:
    with _warmed_premium_effects_lock:
        return _warmed_premium_effects_cache


def clear_warmed_premium_effects_cache() -> None:
    global _warmed_premium_effects_cache
    with _warmed_premium_effects_lock:
        _warmed_premium_effects_cache = None


def store_warmed_page_initial_state(state: AppearancePageInitialStatePlan) -> None:
    global _warmed_page_initial_state_cache
    with _warmed_page_initial_state_lock:
        _warmed_page_initial_state_cache = state
    store_warmed_ui_language(state.ui_language)
    store_warmed_background_preset(state.background_preset)
    store_warmed_mica_enabled(state.mica_enabled)
    store_warmed_window_opacity(state.window_opacity)
    store_warmed_accent_color(state.accent_color)
    store_warmed_tinted_settings(state.follow_windows_accent, state.tinted_background, state.tinted_intensity)
    store_warmed_rkn_background(state.rkn_background)
    store_warmed_animations_enabled(state.animations_enabled)
    store_warmed_smooth_scroll_enabled(state.smooth_scroll_enabled)
    store_warmed_editor_smooth_scroll_enabled(state.editor_smooth_scroll_enabled)
    store_warmed_premium_effects(state.garland_enabled, state.snowflakes_enabled)


def clear_warmed_page_initial_state_cache() -> None:
    global _warmed_page_initial_state_cache
    with _warmed_page_initial_state_lock:
        _warmed_page_initial_state_cache = None


def consume_warmed_page_initial_state() -> AppearancePageInitialStatePlan | None:
    global _warmed_page_initial_state_cache
    with _warmed_page_initial_state_lock:
        state = _warmed_page_initial_state_cache
        _warmed_page_initial_state_cache = None
        return state


def build_default_page_initial_state() -> AppearancePageInitialStatePlan:
    appearance_defaults = schema.default_appearance()
    window_defaults = schema.default_window()
    return AppearancePageInitialStatePlan(
        display_mode=str(appearance_defaults["display_mode"]),
        ui_language=normalize_language(str(appearance_defaults["ui_language"])),
        background_preset=str(appearance_defaults["background_preset"]),
        rkn_background=None,
        mica_enabled=bool(appearance_defaults["mica_enabled"]),
        window_opacity=int(window_defaults["opacity"]),
        accent_color=None,
        follow_windows_accent=bool(appearance_defaults["follow_windows_accent"]),
        tinted_background=bool(appearance_defaults["tinted_background"]),
        tinted_intensity=int(appearance_defaults["tinted_background_intensity"]),
        animations_enabled=bool(appearance_defaults["animations_enabled"]),
        smooth_scroll_enabled=bool(appearance_defaults["smooth_scroll_enabled"]),
        editor_smooth_scroll_enabled=bool(appearance_defaults["editor_smooth_scroll_enabled"]),
        sidebar_icon_style=normalize_sidebar_icon_style(str(appearance_defaults["sidebar_icon_style"])),
        garland_enabled=bool(appearance_defaults["garland_enabled"]),
        snowflakes_enabled=bool(appearance_defaults["snowflakes_enabled"]),
    )


def _plan_str(values: dict, key: str, default: str) -> str:
    return str(values.get(key) or default)


def _plan_bool(values: dict, key: str, default: bool) -> bool:
    return bool(values.get(key, default))


def _plan_int(values: dict, key: str, default: int) -> int:
    try:
        return int(values.get(key, default))
    except Exception:
        return int(default)


def _plan_nullable_str(values: dict, key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_page_initial_state() -> AppearancePageInitialStatePlan:
    appearance_defaults = schema.default_appearance()
    window_defaults = schema.default_window()
    try:
        from settings.store import read_settings

        data = read_settings()
        appearance = dict(data.get("appearance") or {})
        window = dict(data.get("window") or {})
    except Exception:
        appearance = {}
        window = {}

    return AppearancePageInitialStatePlan(
        display_mode=_plan_str(appearance, "display_mode", appearance_defaults["display_mode"]),
        ui_language=normalize_language(_plan_str(appearance, "ui_language", appearance_defaults["ui_language"])),
        background_preset=_plan_str(appearance, "background_preset", appearance_defaults["background_preset"]),
        rkn_background=_plan_nullable_str(appearance, "rkn_background"),
        mica_enabled=_plan_bool(appearance, "mica_enabled", bool(appearance_defaults["mica_enabled"])),
        window_opacity=_plan_int(window, "opacity", int(window_defaults["opacity"])),
        accent_color=_plan_nullable_str(appearance, "accent_color"),
        follow_windows_accent=_plan_bool(appearance, "follow_windows_accent", bool(appearance_defaults["follow_windows_accent"])),
        tinted_background=_plan_bool(appearance, "tinted_background", bool(appearance_defaults["tinted_background"])),
        tinted_intensity=_plan_int(appearance, "tinted_background_intensity", int(appearance_defaults["tinted_background_intensity"])),
        animations_enabled=_plan_bool(appearance, "animations_enabled", bool(appearance_defaults["animations_enabled"])),
        smooth_scroll_enabled=_plan_bool(appearance, "smooth_scroll_enabled", bool(appearance_defaults["smooth_scroll_enabled"])),
        editor_smooth_scroll_enabled=_plan_bool(appearance, "editor_smooth_scroll_enabled", bool(appearance_defaults["editor_smooth_scroll_enabled"])),
        sidebar_icon_style=normalize_sidebar_icon_style(
            _plan_str(appearance, "sidebar_icon_style", appearance_defaults["sidebar_icon_style"])
        ),
        garland_enabled=_plan_bool(appearance, "garland_enabled", bool(appearance_defaults["garland_enabled"])),
        snowflakes_enabled=_plan_bool(appearance, "snowflakes_enabled", bool(appearance_defaults["snowflakes_enabled"])),
    )


def warm_page_initial_state_cache() -> AppearancePageInitialStatePlan:
    state = load_page_initial_state()
    store_warmed_page_initial_state(state)
    return state


def load_display_mode() -> str:
    try:
        from settings.store import get_display_mode

        return str(get_display_mode() or "dark")
    except Exception:
        return "dark"

def save_display_mode(mode: str) -> AppearanceDisplayModePlan:
    effective_mode = str(mode or "dark")
    try:
        from settings.store import get_display_mode, set_display_mode

        set_display_mode(mode)
        effective_mode = str(get_display_mode() or effective_mode)
    except Exception:
        pass
    return AppearanceDisplayModePlan(
        requested_mode=str(mode or "dark"),
        effective_mode=effective_mode,
    )

def load_ui_language() -> AppearanceUiLanguagePlan:
    try:
        from settings.store import get_ui_language

        lang = normalize_language(get_ui_language())
    except Exception:
        lang = "ru"
    return AppearanceUiLanguagePlan(language=lang)

def save_ui_language(language: str) -> AppearanceUiLanguagePlan:
    lang = normalize_language(language)
    try:
        from settings.store import set_ui_language

        set_ui_language(lang)
    except Exception:
        pass
    store_warmed_ui_language(lang)
    return AppearanceUiLanguagePlan(language=lang)

def load_background_preset() -> AppearanceBackgroundPresetPlan:
    try:
        from settings.store import get_background_preset

        preset = str(get_background_preset() or "standard")
    except Exception:
        preset = "standard"
    return AppearanceBackgroundPresetPlan(preset=preset)

def save_background_preset(preset: str) -> AppearanceBackgroundPresetPlan:
    normalized = str(preset or "standard")
    try:
        from settings.store import set_background_preset

        set_background_preset(normalized)
    except Exception:
        pass
    store_warmed_background_preset(normalized)
    return AppearanceBackgroundPresetPlan(preset=normalized)

def load_mica_enabled() -> AppearanceMicaPlan:
    try:
        from settings.store import get_mica_enabled

        enabled = bool(get_mica_enabled())
    except Exception:
        enabled = True
    return AppearanceMicaPlan(enabled=enabled)

def save_mica_enabled(enabled: bool) -> AppearanceMicaPlan:
    try:
        from settings.store import set_mica_enabled

        set_mica_enabled(bool(enabled))
    except Exception:
        pass
    store_warmed_mica_enabled(bool(enabled))
    return AppearanceMicaPlan(enabled=bool(enabled))

def load_window_opacity() -> AppearanceOpacityPlan:
    try:
        from settings.store import get_window_opacity

        value = int(get_window_opacity())
    except Exception:
        value = 100
    return AppearanceOpacityPlan(value=value)

def save_window_opacity(value: int) -> AppearanceOpacityPlan:
    normalized = int(value)
    try:
        from settings.store import set_window_opacity

        set_window_opacity(normalized)
    except Exception:
        pass
    store_warmed_window_opacity(normalized)
    return AppearanceOpacityPlan(value=normalized)

def load_animations_enabled() -> AppearanceTogglePlan:
    try:
        from settings.store import get_animations_enabled

        enabled = bool(get_animations_enabled())
    except Exception:
        enabled = False
    return AppearanceTogglePlan(enabled=enabled)

def save_animations_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_animations_enabled

        set_animations_enabled(bool(enabled))
    except Exception:
        pass
    store_warmed_animations_enabled(bool(enabled))
    return AppearanceTogglePlan(enabled=bool(enabled))

def load_smooth_scroll_enabled() -> AppearanceTogglePlan:
    try:
        from settings.store import get_smooth_scroll_enabled

        enabled = bool(get_smooth_scroll_enabled())
    except Exception:
        enabled = False
    return AppearanceTogglePlan(enabled=enabled)

def save_smooth_scroll_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_smooth_scroll_enabled

        set_smooth_scroll_enabled(bool(enabled))
    except Exception:
        pass
    store_warmed_smooth_scroll_enabled(bool(enabled))
    return AppearanceTogglePlan(enabled=bool(enabled))

def load_editor_smooth_scroll_enabled() -> AppearanceTogglePlan:
    try:
        from settings.store import get_editor_smooth_scroll_enabled

        enabled = bool(get_editor_smooth_scroll_enabled())
    except Exception:
        enabled = False
    return AppearanceTogglePlan(enabled=enabled)

def save_editor_smooth_scroll_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_editor_smooth_scroll_enabled

        set_editor_smooth_scroll_enabled(bool(enabled))
    except Exception:
        pass
    store_warmed_editor_smooth_scroll_enabled(bool(enabled))
    return AppearanceTogglePlan(enabled=bool(enabled))


def load_sidebar_icon_style() -> AppearanceSidebarIconStylePlan:
    try:
        from settings.store import get_sidebar_icon_style

        style = normalize_sidebar_icon_style(get_sidebar_icon_style())
    except Exception:
        style = normalize_sidebar_icon_style(None)
    return AppearanceSidebarIconStylePlan(style=style)


def save_sidebar_icon_style(style: str) -> AppearanceSidebarIconStylePlan:
    normalized = normalize_sidebar_icon_style(style)
    try:
        from settings.store import set_sidebar_icon_style

        set_sidebar_icon_style(normalized)
    except Exception:
        pass
    store_warmed_sidebar_icon_style(normalized)
    return AppearanceSidebarIconStylePlan(style=normalized)


def load_accent_color() -> AppearanceAccentColorPlan:
    try:
        from settings.store import get_accent_color

        hex_color = get_accent_color()
    except Exception:
        hex_color = None
    return AppearanceAccentColorPlan(hex_color=hex_color)

def save_accent_color(hex_color: str) -> AppearanceAccentColorPlan:
    normalized = str(hex_color or "").strip()
    try:
        from settings.store import set_accent_color

        if normalized:
            set_accent_color(normalized)
    except Exception:
        pass
    store_warmed_accent_color(normalized or None)
    return AppearanceAccentColorPlan(hex_color=normalized or None)

def load_tinted_settings() -> AppearanceTintedSettingsPlan:
    try:
        from settings.store import (
            get_follow_windows_accent,
            get_tinted_background,
            get_tinted_background_intensity,
        )

        follow = bool(get_follow_windows_accent())
        tinted = bool(get_tinted_background())
        intensity = int(get_tinted_background_intensity())
    except Exception:
        follow = False
        tinted = False
        intensity = 50
    return AppearanceTintedSettingsPlan(
        follow_windows_accent=follow,
        tinted_background=tinted,
        tinted_intensity=intensity,
    )

def save_follow_windows_accent(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_follow_windows_accent

        set_follow_windows_accent(bool(enabled))
    except Exception:
        pass
    current = peek_warmed_tinted_settings()
    store_warmed_tinted_settings(
        bool(enabled),
        None if current is None else current.tinted_background,
        None if current is None else current.tinted_intensity,
    )
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_tinted_background(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_tinted_background

        set_tinted_background(bool(enabled))
    except Exception:
        pass
    current = peek_warmed_tinted_settings()
    store_warmed_tinted_settings(
        None if current is None else current.follow_windows_accent,
        bool(enabled),
        None if current is None else current.tinted_intensity,
    )
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_tinted_background_intensity(value: int) -> AppearanceOpacityPlan:
    normalized = int(value)
    try:
        from settings.store import set_tinted_background_intensity

        set_tinted_background_intensity(normalized)
    except Exception:
        pass
    current = peek_warmed_tinted_settings()
    store_warmed_tinted_settings(
        None if current is None else current.follow_windows_accent,
        None if current is None else current.tinted_background,
        normalized,
    )
    return AppearanceOpacityPlan(value=normalized)

def load_windows_system_accent() -> AppearanceAccentColorPlan:
    try:
        from settings.store import get_windows_system_accent

        hex_color = get_windows_system_accent()
    except Exception:
        hex_color = None
    return AppearanceAccentColorPlan(hex_color=hex_color)

def load_rkn_background() -> AppearanceRknBackgroundPlan:
    try:
        from settings.store import get_rkn_background

        value = get_rkn_background()
    except Exception:
        value = None
    return AppearanceRknBackgroundPlan(value=value)

def save_rkn_background(value: str | None) -> AppearanceRknBackgroundPlan:
    normalized = str(value).strip().replace("\\", "/") if value is not None else None
    try:
        from settings.store import set_rkn_background

        set_rkn_background(normalized)
    except Exception:
        pass
    store_warmed_rkn_background(normalized)
    return AppearanceRknBackgroundPlan(value=normalized or None)

def load_premium_effects() -> AppearancePremiumEffectsPlan:
    try:
        from settings.store import get_garland_enabled, get_snowflakes_enabled

        garland = bool(get_garland_enabled())
        snowflakes = bool(get_snowflakes_enabled())
    except Exception:
        garland = False
        snowflakes = False
    return AppearancePremiumEffectsPlan(
        garland_enabled=garland,
        snowflakes_enabled=snowflakes,
    )

def save_garland_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_garland_enabled

        set_garland_enabled(bool(enabled))
    except Exception:
        pass
    current = peek_warmed_premium_effects()
    store_warmed_premium_effects(bool(enabled), None if current is None else current.snowflakes_enabled)
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_snowflakes_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_snowflakes_enabled

        set_snowflakes_enabled(bool(enabled))
    except Exception:
        pass
    current = peek_warmed_premium_effects()
    store_warmed_premium_effects(None if current is None else current.garland_enabled, bool(enabled))
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_selected_theme(theme_name: str) -> bool:
    from settings.store import set_selected_theme

    return bool(set_selected_theme(str(theme_name or "").strip()))

def build_premium_status_plan(
    *,
    is_premium: bool,
    current_preset: str,
    was_garland_enabled: bool,
    was_snowflakes_enabled: bool,
    premium_effects: AppearancePremiumEffectsPlan,
) -> AppearancePremiumStatusPlan:
    effective_preset = None
    if not is_premium and current_preset in ("amoled", "rkn_chan"):
        effective_preset = "standard"

    return AppearancePremiumStatusPlan(
        effective_preset=effective_preset,
        garland_checked=premium_effects.garland_enabled if is_premium else False,
        snowflakes_checked=premium_effects.snowflakes_enabled if is_premium else False,
        disable_garland=bool((not is_premium) and was_garland_enabled),
        disable_snowflakes=bool((not is_premium) and was_snowflakes_enabled),
    )
