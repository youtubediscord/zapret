from __future__ import annotations

from dataclasses import dataclass
import threading

from settings import schema


def normalize_language(language: str | None) -> str:
    candidate = str(language or schema.default_appearance()["ui_language"]).strip().lower()
    if candidate in schema.VALID_UI_LANGUAGES:
        return candidate
    return schema.default_appearance()["ui_language"]


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
    garland_enabled: bool
    snowflakes_enabled: bool


_warmed_page_initial_state_lock = threading.Lock()
_warmed_page_initial_state_cache: AppearancePageInitialStatePlan | None = None


def store_warmed_page_initial_state(state: AppearancePageInitialStatePlan) -> None:
    global _warmed_page_initial_state_cache
    with _warmed_page_initial_state_lock:
        _warmed_page_initial_state_cache = state


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
    return AppearanceTogglePlan(enabled=bool(enabled))

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
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_tinted_background(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_tinted_background

        set_tinted_background(bool(enabled))
    except Exception:
        pass
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_tinted_background_intensity(value: int) -> AppearanceOpacityPlan:
    normalized = int(value)
    try:
        from settings.store import set_tinted_background_intensity

        set_tinted_background_intensity(normalized)
    except Exception:
        pass
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
    return AppearanceTogglePlan(enabled=bool(enabled))

def save_snowflakes_enabled(enabled: bool) -> AppearanceTogglePlan:
    try:
        from settings.store import set_snowflakes_enabled

        set_snowflakes_enabled(bool(enabled))
    except Exception:
        pass
    return AppearanceTogglePlan(enabled=bool(enabled))

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
